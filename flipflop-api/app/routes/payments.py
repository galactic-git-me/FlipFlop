"""Payment endpoints for Stripe integration."""

import structlog
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.customer import Customer
from app.models.order import Order, OrderStatus
from app.models.playbook import Playbook
from app.models.order_checkout_snapshot import OrderCheckoutSnapshot
from app.routes.admin_auth import get_current_admin
from app.schemas.payment import (
    PlaybookBuildConfig,
    CreatePaymentIntentRequest,
    PaymentIntentResponse,
    ConfirmPaymentRequest,
    PaymentConfirmation,
    PaymentStatusResponse,
    RefundRequest,
    RefundResponse,
)
from app.services.playbook_delivery import _checkout_build_mode, quote_playbook_delivery
from app.services.payment_service import PaymentService
from app.services.email_service import send_order_confirmation_email
from app.services.social_proof import record_order_event
from app.services.playbook_pricing import InvalidBuildError, price_playbook_build
from app.services.commercial_checkout import (
    load_checkout_policy, create_checkout_quote, accept_checkout_quote,
    accepted_summary, accepted_delivery,
    commercial_order_snapshot,
    checkout_snapshot_for_payment,
)
from app.services.software_catalogue import (
    effective_software_profile_for_playbook,
    serialize_customer_software_selection,
    validate_package_ids,
)
from app.services.product_software import (
    software_profile_for_curated_cell_from_db,
    software_profile_for_playbook_cell_from_db,
)
from app.services.storefront_delivery import delivery_choice, checkout_metadata, add_working_days, apply_component_delivery_estimate
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

log = structlog.get_logger(__name__)




router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/delivery-quotes")
async def delivery_quotes(
    build_config: PlaybookBuildConfig, db: AsyncSession = Depends(get_db),
) -> dict:
    return await quote_playbook_delivery(db, build_config)


@router.post("/intent", response_model=PaymentIntentResponse, status_code=201)
async def create_payment_intent(
    request: CreatePaymentIntentRequest,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> PaymentIntentResponse:
    """
    Create a Stripe payment intent for a quote.

    **Request:**
    - `budget`: Quote total price in GBP
    - `customer_id`: Customer ID from database

    **Response:**
    - `client_secret`: Pass to frontend Stripe Elements
    - `publishable_key`: Stripe publishable key
    - `amount`: Payment amount in GBP
    - `currency`: Always "gbp"
    - `intent_id`: Stripe PaymentIntent ID

    **Example:**
    ```
    POST /api/payments/intent
    {
        "budget": 1200.00,
        "customer_id": 1
    }

    Response:
    {
        "client_secret": "pi_1234567890_secret_0987654321",
        "publishable_key": "pk_test_1234567890",
        "amount": 1200.00,
        "currency": "gbp",
        "intent_id": "pi_1234567890"
    }
    ```
    """
    if request.build_config is not None and request.build_config.case_id is None:
        raise HTTPException(status_code=422, detail="Select a verified case or chassis before paying for this build")

    # Validate customer exists
    result = await db.execute(
        select(Customer).where(Customer.id == request.customer_id)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        log.warning("payment.customer_not_found", customer_id=request.customer_id)
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    # A build_config always wins on price — never trust a client-supplied
    # amount for a real catalogue build.
    quote_data: dict = {}
    if request.build_config is not None:
        checkout_build_mode = _checkout_build_mode(request.build_config)
        try:
            priced = await price_playbook_build(
                db,
                playbook_id=request.build_config.playbook_id,
                slot_selections=request.build_config.slot_selections,
                case_id=request.build_config.case_id,
                build_mode=checkout_build_mode,
                curated_build_id=request.build_config.curated_build_id,
                upgrade_candidate_indexes=request.build_config.upgrade_candidate_indexes,
            )
        except InvalidBuildError as e:
            log.warning("payment.invalid_build_config", error=str(e))
            raise HTTPException(status_code=400, detail=str(e))
        fulfilment_type = "curated" if checkout_build_mode == "curated" else "custom"
        commercial_policy = await load_checkout_policy(db, request.build_config)
        if commercial_policy is not None:
            from app.routes.auth import get_current_user
            owner = await get_current_user(authorization if isinstance(authorization, str) else None, db)
            if owner.id != request.customer_id:
                raise HTTPException(403, "This checkout belongs to a different customer")
        playbook = await db.get(Playbook, priced.playbook_id)
        authored_profile = playbook.software_profile if playbook else None
        try:
            if request.build_config.curated_build_id:
                software_profile = await software_profile_for_curated_cell_from_db(
                    db,
                    request.build_config.curated_build_id,
                    priced.playbook_name,
                    authored_profile,
                )
            elif request.build_config.budget_tier:
                software_profile = await software_profile_for_playbook_cell_from_db(
                    db,
                    priced.playbook_name,
                    request.build_config.budget_tier,
                    authored_profile,
                )
            else:
                software_profile = effective_software_profile_for_playbook(priced.playbook_name, authored_profile)
            selected_software_ids = validate_package_ids(
                request.software_package_ids
                if request.software_package_ids is not None
                else software_profile["recommended_package_ids"]
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        delivery_option = request.delivery_option or ("fast_track" if request.speedy_delivery else "standard")
        if delivery_option == "flexible" and fulfilment_type not in {"curated", "custom"}:
            raise HTTPException(status_code=422, detail="Flexible delivery is available for curated and custom builds")
        choice = await delivery_choice(db, fulfilment_type, delivery_option == "fast_track", delivery_option == "flexible")
        try:
            if commercial_policy is None:
                choice = await apply_component_delivery_estimate(db, choice, [s.variant_id for s in priced.slots])
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        amount = priced.total + choice["fee_gbp"]
        quote_data = {
            "fulfilment_type": fulfilment_type,
            "playbook_id": priced.playbook_id,
            "playbook_name": priced.playbook_name,
            "curated_build_id": request.build_config.curated_build_id,
            "slots": [
                {
                    "slot_id": s.slot_id,
                    "slot_type": s.slot_type,
                    "variant_id": s.variant_id,
                    "title": s.title,
                    "price": s.price,
                }
                for s in priced.slots
            ],
            "case_id": priced.case_id,
            "case_name": priced.case_name,
            "case_price": priced.case_price,
            "chosen_week": request.build_config.chosen_week,
            "budget_tier": request.build_config.budget_tier,
            "parts_total": priced.parts_total,
            "labour": priced.labour,
            "overhead": priced.overhead,
            "playbook_upgrades": priced.applied_upgrades,
            **checkout_metadata(choice),
        }
        if commercial_policy is not None:
            accepted = await accept_checkout_quote(db, request.build_config, request.commercial_quote_id,
                delivery_option, request.customer_id, commercial_policy, quote_data)
            choice = accepted_delivery(accepted)
            amount = accepted.decision_json["quote"]["price_gbp"]
            quote_data.update(checkout_metadata(choice))
            quote_data["commercial_quote"] = accepted_summary(accepted)
            quote_data["parts_total"] = float(accepted.decision_json["quote"]["fixed_costs_gbp"]["landed_parts_including_risk"])
            quote_data["labour"] = float(accepted.decision_json["quote"]["fixed_costs_gbp"]["build_labour"])
            quote_data["overhead"] = float(accepted.decision_json["quote"]["fixed_costs_gbp"]["allocated_overhead"])
        elif request.commercial_quote_id is not None:
            raise HTTPException(409, "This build no longer has an enabled commercial pricing policy")
    else:
        amount = request.budget
        delivery_option = request.delivery_option or ("fast_track" if request.speedy_delivery else "standard")
        choice = await delivery_choice(db, "custom", delivery_option == "fast_track", delivery_option == "flexible")
        amount += choice["fee_gbp"]
        quote_data = checkout_metadata(choice)
    # Create payment intent using service
    try:
        # Opportunistically purge abandoned checkout PII; paid snapshots are
        # consumed by confirm/webhook in the order-creation transaction.
        from sqlalchemy import delete
        await db.execute(delete(OrderCheckoutSnapshot).where(OrderCheckoutSnapshot.expires_at < datetime.utcnow()))

        if quote_data.get("commercial_quote"):
            # Retain the accepted contract even if provider creation succeeds
            # but a later checkout-address transaction fails.
            accepted_id = quote_data["commercial_quote"]["quote_snapshot_id"]
            pending = (await db.execute(select(OrderCheckoutSnapshot).where(
                OrderCheckoutSnapshot.customer_id == request.customer_id,
                OrderCheckoutSnapshot.build_snapshot["commercial_quote"]["quote_snapshot_id"].as_integer() == accepted_id,
            ).with_for_update())).scalar_one_or_none()
            if pending is None:
                db.add(OrderCheckoutSnapshot(
                    payment_intent_id=f"commercial:{accepted_id}", customer_id=request.customer_id,
                    delivery_address=request.checkout_addresses.delivery.model_dump(),
                    billing_address=request.checkout_addresses.billing.model_dump(),
                    build_snapshot={**quote_data, "software_profile": software_profile,
                                    "software_package_ids": selected_software_ids},
                    expires_at=datetime.utcnow() + timedelta(days=30),
                ))
            await db.commit()

        payment_service = PaymentService()
        intent_data = await payment_service.create_payment_intent(
            customer_id=request.customer_id,
            budget=amount,
            quote_data=quote_data,
            metadata={
                **checkout_metadata(choice),
                "fulfilment_type": fulfilment_type if request.build_config is not None else "custom",
                "playbook_id": str(request.build_config.playbook_id) if request.build_config is not None else "",
                "curated_build_id": request.build_config.curated_build_id or "" if request.build_config else "",
                "slot_selections": ",".join(
                    f"{slot_id}:{variant_id}"
                    for slot_id, variant_id in sorted(request.build_config.slot_selections.items())
                ) if request.build_config else "",
                "case_id": str(request.build_config.case_id or "") if request.build_config else "",
                "validation_mode": request.build_config.validation_mode or "" if request.build_config else "",
                "software_package_ids": serialize_customer_software_selection(selected_software_ids) if request.build_config is not None else "",
                "chosen_week": request.build_config.chosen_week or "" if request.build_config else "",
                "upgrade_candidate_indexes": ",".join(map(str, request.build_config.upgrade_candidate_indexes)) if request.build_config else "",
                "budget_tier": request.build_config.budget_tier or "" if request.build_config else "",
                "commercial_quote_snapshot_id": str(quote_data.get("commercial_quote", {}).get("quote_snapshot_id", "")),
            },
            idempotency_key=(f"commercial:{request.customer_id}:{request.commercial_quote_id}:{delivery_option}"
                             if quote_data.get("commercial_quote") else None),
        )

        if request.build_config is not None:
            addresses = request.checkout_addresses
            existing_snapshot = await checkout_snapshot_for_payment(db, intent_data["intent_id"],
                request.customer_id, {"commercial_quote_snapshot_id": quote_data.get("commercial_quote", {}).get("quote_snapshot_id", "")})
            if existing_snapshot is not None and existing_snapshot.customer_id != request.customer_id:
                raise HTTPException(409, "Payment checkout owner does not match")
            if existing_snapshot is None:
                db.add(OrderCheckoutSnapshot(
                    payment_intent_id=intent_data["intent_id"],
                    customer_id=request.customer_id,
                    delivery_address=addresses.delivery.model_dump(),
                    billing_address=addresses.billing.model_dump(),
                    build_snapshot={
                        **quote_data,
                        "software_profile": software_profile,
                        "software_package_ids": selected_software_ids,
                    },
                    expires_at=datetime.utcnow() + timedelta(days=30),
                ))
            elif existing_snapshot.payment_intent_id.startswith("commercial:"):
                existing_snapshot.payment_intent_id = intent_data["intent_id"]
            await db.flush()

        log.info(
            "payment.intent_created",
            customer_id=request.customer_id,
            amount_gbp=amount,
        )

        return PaymentIntentResponse(
            **intent_data,
            delivery_option=choice.get("delivery_option"),
            delivery_days=choice.get("delivery_days"),
            delivery_promise=choice.get("promise"),
            delivery_estimate_source=choice.get("delivery_estimate_source", "configured_fulfilment_default"),
        )

    except ValueError as e:
        log.error(
            "payment.intent_creation_failed",
            error=str(e),
            customer_id=request.customer_id,
        )
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post("/confirm", response_model=PaymentConfirmation, status_code=201)
async def confirm_payment(
    request: ConfirmPaymentRequest,
    db: AsyncSession = Depends(get_db),
) -> PaymentConfirmation:
    """
    Confirm payment and create order.

    **Request:**
    - `intent_id`: Stripe PaymentIntent ID
    - `customer_id`: Customer ID

    **Response:**
    - `order_id`: Created Order ID
    - `status`: Order status (awaiting_sourcing)
    - `amount`: Order total price in GBP
    - `currency`: "gbp"
    - `payment_intent_id`: Stripe PaymentIntent ID
    - `created_at`: Order creation timestamp

    **Example:**
    ```
    POST /api/payments/confirm
    {
        "intent_id": "pi_1234567890",
        "customer_id": 1
    }

    Response:
    {
        "order_id": 42,
        "status": "awaiting_sourcing",
        "amount": 1200.00,
        "currency": "gbp",
        "payment_intent_id": "pi_1234567890",
        "created_at": "2024-06-29T12:00:00Z"
    }
    ```
    """
    # Validate customer exists
    result = await db.execute(
        select(Customer).where(Customer.id == request.customer_id)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        log.warning("payment.customer_not_found", customer_id=request.customer_id)
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    existing_order = (await db.execute(
        select(Order).where(
            Order.stripe_payment_intent_id == request.intent_id,
            Order.customer_id == request.customer_id,
        )
    )).scalar_one_or_none()
    if existing_order is not None:
        return PaymentConfirmation(
            order_id=existing_order.id,
            status=existing_order.status.value,
            fulfilment_status=existing_order.fulfilment_status.value,
            payment_status=existing_order.payment_status,
            amount=float(existing_order.customer_price),
            currency="gbp",
            payment_intent_id=request.intent_id,
            created_at=existing_order.created_at,
        )

    try:
        # Verify payment succeeded
        payment_service = PaymentService()
        payment_data = await payment_service.handle_payment_success(
            intent_id=request.intent_id,
            customer_id=request.customer_id,
            quote_data={},
        )

        if request.build_config is not None:
            metadata = payment_data["metadata"]
            submitted_selection = ",".join(
                f"{slot_id}:{variant_id}"
                for slot_id, variant_id in sorted(request.build_config.slot_selections.items())
            )
            if (
                str(metadata.get("playbook_id") or "") != str(request.build_config.playbook_id)
                or str(metadata.get("curated_build_id") or "") != str(request.build_config.curated_build_id or "")
                or str(metadata.get("slot_selections") or "") != submitted_selection
                or str(metadata.get("case_id") or "") != str(request.build_config.case_id or "")
                or str(metadata.get("validation_mode") or "") != str(request.build_config.validation_mode or "")
                or str(metadata.get("chosen_week") or "") != str(request.build_config.chosen_week or "")
                or str(metadata.get("upgrade_candidate_indexes") or "") != ",".join(map(str, request.build_config.upgrade_candidate_indexes))
                or str(metadata.get("budget_tier") or "") != str(request.build_config.budget_tier or "")
            ):
                raise HTTPException(status_code=409, detail="The paid build configuration does not match this order confirmation.")

        # Populate real specs + playbook link from the build config the
        # customer actually configured (re-validated against the catalogue,
        # not trusted as-is) instead of the old hardcoded specs={}.
        specs: dict = {}
        component_costs = 0.0
        overhead_amount = 0.0
        playbook_id = None
        address_snapshot = await checkout_snapshot_for_payment(db, request.intent_id,
            request.customer_id, payment_data["metadata"])
        if request.build_config is not None and (address_snapshot is None or not address_snapshot.build_snapshot):
            raise HTTPException(status_code=409, detail="The checkout build snapshot is missing. Please restart checkout.")
        if request.build_config is not None:
            snapshot = address_snapshot.build_snapshot
            playbook_id = request.build_config.playbook_id
            component_costs = float(snapshot.get("parts_total") or 0)
            overhead_amount = float(snapshot.get("overhead") or 0)
            specs = {
                "fulfilment_type": snapshot.get("fulfilment_type"),
                "playbook_id": snapshot.get("playbook_id"),
                "playbook_name": snapshot.get("playbook_name"),
                "curated_build_id": snapshot.get("curated_build_id"),
                "slots": snapshot.get("slots", []),
                "case_id": snapshot.get("case_id"),
                "case_name": snapshot.get("case_name"),
                "case_price": snapshot.get("case_price"),
                "chosen_week": snapshot.get("chosen_week"),
                "budget_tier": snapshot.get("budget_tier"),
                "software_profile": snapshot.get("software_profile"),
                "software_package_ids": snapshot.get("software_package_ids", []),
                "playbook_upgrades": snapshot.get("playbook_upgrades", []),
                **({"commercial_quote": snapshot["commercial_quote"]} if snapshot.get("commercial_quote") else {}),
                "delivery_address": address_snapshot.delivery_address,
                "billing_address": address_snapshot.billing_address,
            }

        accepted_specs = await commercial_order_snapshot(db, payment_data["metadata"],
                                                        request.customer_id, payment_data["amount"])
        if accepted_specs is not None:
            if address_snapshot is not None and address_snapshot.build_snapshot:
                specs = {**address_snapshot.build_snapshot, **specs,
                    "delivery_address": address_snapshot.delivery_address,
                    "billing_address": address_snapshot.billing_address}
            specs = {**specs, **accepted_specs}
            playbook_id = accepted_specs["playbook_id"]
            component_costs = accepted_specs["parts_total"]
            overhead_amount = float(accepted_specs.get("overhead") or 0)
        delivery_metadata = payment_data["metadata"]
        delivery_days = int(delivery_metadata.get("delivery_days") or 0)
        delivery_option = delivery_metadata.get("delivery_option", "standard")
        delivery_start = datetime.now(ZoneInfo("Europe/London")).replace(tzinfo=None)
        chosen_week = delivery_metadata.get("chosen_week") or (request.build_config.chosen_week if request.build_config else None)
        if accepted_specs is not None:
            delivery_start = datetime.fromisoformat(accepted_specs["commercial_quote"]["accepted_at"]).astimezone(ZoneInfo("Europe/London")).replace(tzinfo=None)
        elif chosen_week:
            try:
                year_text, week_text = chosen_week.split("-W", maxsplit=1)
                scheduled_start = datetime.fromisocalendar(int(year_text), int(week_text), 1)
                delivery_start = max(delivery_start, scheduled_start)
            except (ValueError, TypeError):
                pass
        promised_delivery_date = add_working_days(delivery_start, delivery_days) if delivery_days > 0 else None
        specs.update({
            "payment_evidence": payment_data.get("payment_evidence", {}),
            "delivery_option": delivery_option,
            "delivery_promise": delivery_metadata.get("delivery_promise"),
            "delivery_estimate_source": delivery_metadata.get("delivery_estimate_source", "configured_fulfilment_default"),
            "supplier_delivery_days": delivery_metadata.get("supplier_delivery_days") or None,
        })

        # Create order
        order = Order(
            order_id=f"ORD-{payment_data['intent_id'][-12:]}",  # Use last 12 chars of intent ID
            customer_id=request.customer_id,
            status=OrderStatus.AWAITING_SOURCING,
            payment_status="paid",
            customer_name=customer.name,
            customer_email=customer.email,
            specs=specs,
            customer_price=payment_data["amount"],
            fast_track_selected=delivery_option == "fast_track",
            fast_track_fee=float(payment_data["metadata"].get("delivery_fee_gbp", 0)),
            component_costs=component_costs,
            overhead_amount=overhead_amount,
            playbook_id=playbook_id,
            promised_delivery_date=promised_delivery_date,
            stripe_payment_intent_id=request.intent_id,
            notes=f"Payment processed via Stripe. Intent: {request.intent_id}",
        )

        db.add(order)
        if address_snapshot is not None:
            await db.delete(address_snapshot)
        await db.flush()  # Get the ID before commit
        order_id = order.id

        from app.services.getting_started_jobs import ensure_order_job
        order_build_type = str(specs.get("fulfilment_type") or "custom").lower().replace("-", "_")
        source_type = "curated_for_you" if order_build_type in {"curated", "curated_for_you"} else "made_by_you"
        await ensure_order_job(
            db,
            order_id=order.id,
            customer_id=request.customer_id,
            playbook_id=playbook_id,
            source_type=source_type,
        )

        await db.commit()

        log.info(
            "order.created_after_payment",
            order_id=order_id,
            customer_id=request.customer_id,
            amount_gbp=payment_data["amount"],
        )

        try:
            await record_order_event(
                db,
                customer_name=customer.name,
                address=customer.address,
                product_name="a custom PC build",
            )
        except Exception as e:
            log.warning("social_proof.order_event_failed", error=str(e), order_id=order_id)

        # Send confirmation email
        try:
            await send_order_confirmation_email(
                customer_email=customer.email,
                customer_name=customer.name,
                order_reference=order.order_id,
                build_summary="Custom PC build order received. Build will begin soon.",
                assigned_week="TBD",
                order_id=order.id,
            )
        except Exception as e:
            log.warning(
                "payment.email_send_failed",
                error=str(e),
                order_id=order_id,
                customer_email=customer.email,
            )

        return PaymentConfirmation(
            order_id=order_id,
            status=order.status.value,
            fulfilment_status=order.fulfilment_status.value,
            payment_status=order.payment_status,
            amount=payment_data["amount"],
            currency=payment_data["currency"],
            payment_intent_id=request.intent_id,
            created_at=order.created_at,
        )

    except ValueError as e:
        log.error(
            "payment.confirmation_failed",
            error=str(e),
            intent_id=request.intent_id,
            customer_id=request.customer_id,
        )
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except Exception as e:
        log.error(
            "payment.order_creation_failed",
            error=str(e),
            intent_id=request.intent_id,
            customer_id=request.customer_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create order after payment",
        )


@router.get("/status/{intent_id}", response_model=PaymentStatusResponse)
async def get_payment_status(intent_id: str) -> PaymentStatusResponse:
    """
    Get current payment status.

    **Path Parameters:**
    - `intent_id`: Stripe PaymentIntent ID

    **Response:**
    - `intent_id`: Stripe PaymentIntent ID
    - `status`: Payment status (processing, succeeded, etc.)
    - `amount`: Amount in GBP
    - `currency`: "gbp"
    - `created_at`: Creation timestamp

    **Example:**
    ```
    GET /api/payments/status/pi_1234567890

    Response:
    {
        "intent_id": "pi_1234567890",
        "status": "succeeded",
        "amount": 1200.00,
        "currency": "gbp",
        "created_at": "2024-06-29T12:00:00Z"
    }
    ```
    """
    try:
        payment_service = PaymentService()
        payment_data = await payment_service.get_payment_intent(intent_id)

        return PaymentStatusResponse(**payment_data)

    except ValueError as e:
        log.error(
            "payment.status_retrieval_failed",
            error=str(e),
            intent_id=intent_id,
        )
        raise HTTPException(
            status_code=404,
            detail="Payment intent not found",
        )


@router.post("/refund", response_model=RefundResponse)
async def refund_payment(request: RefundRequest, admin=Depends(get_current_admin)) -> RefundResponse:
    """
    Refund a successful payment.

    **Request:**
    - `intent_id`: Stripe PaymentIntent ID
    - `reason`: Refund reason (default: "customer_request")

    **Response:**
    - `refund_id`: Stripe Refund ID
    - `amount`: Refund amount in GBP
    - `status`: Refund status
    - `reason`: Refund reason

    **Example:**
    ```
    POST /api/payments/refund
    {
        "intent_id": "pi_1234567890",
        "reason": "customer_request"
    }

    Response:
    {
        "refund_id": "re_1234567890",
        "amount": 1200.00,
        "status": "succeeded",
        "reason": "customer_request"
    }
    ```
    """
    try:
        payment_service = PaymentService()
        refund_data = await payment_service.refund_payment(
            intent_id=request.intent_id,
            reason=request.reason,
        )

        log.info(
            "payment.refund_issued",
            refund_id=refund_data["refund_id"],
            intent_id=request.intent_id,
            amount_gbp=refund_data["amount"],
        )

        return RefundResponse(**refund_data)

    except ValueError as e:
        log.error(
            "payment.refund_failed",
            error=str(e),
            intent_id=request.intent_id,
        )
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
