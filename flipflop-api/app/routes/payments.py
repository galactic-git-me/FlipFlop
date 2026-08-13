"""Payment endpoints for Stripe integration."""

import structlog
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.customer import Customer
from app.models.order import Order, OrderStatus
from app.schemas.payment import (
    CreatePaymentIntentRequest,
    PaymentIntentResponse,
    ConfirmPaymentRequest,
    PaymentConfirmation,
    PaymentStatusResponse,
    RefundRequest,
    RefundResponse,
)
from app.services.payment_service import PaymentService
from app.services.email_service import send_order_confirmation_email
from app.services.social_proof import record_order_event
from app.services.playbook_pricing import InvalidBuildError, price_playbook_build

log = structlog.get_logger(__name__)


router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/intent", response_model=PaymentIntentResponse, status_code=201)
async def create_payment_intent(
    request: CreatePaymentIntentRequest,
    db: AsyncSession = Depends(get_db),
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
        try:
            priced = await price_playbook_build(
                db,
                playbook_id=request.build_config.playbook_id,
                slot_selections=request.build_config.slot_selections,
                case_id=request.build_config.case_id,
            )
        except InvalidBuildError as e:
            log.warning("payment.invalid_build_config", error=str(e))
            raise HTTPException(status_code=400, detail=str(e))
        amount = priced.total
        quote_data = {
            "playbook_id": priced.playbook_id,
            "playbook_name": priced.playbook_name,
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
            "parts_total": priced.parts_total,
            "labour": priced.labour,
            "overhead": priced.overhead,
        }
    else:
        amount = request.budget

    # Create payment intent using service
    try:
        payment_service = PaymentService()
        intent_data = await payment_service.create_payment_intent(
            customer_id=request.customer_id,
            budget=amount,
            quote_data=quote_data,
        )

        log.info(
            "payment.intent_created",
            customer_id=request.customer_id,
            amount_gbp=amount,
        )

        return PaymentIntentResponse(**intent_data)

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

    try:
        # Verify payment succeeded
        payment_service = PaymentService()
        payment_data = await payment_service.handle_payment_success(
            intent_id=request.intent_id,
            customer_id=request.customer_id,
            quote_data={},
        )

        # Populate real specs + playbook link from the build config the
        # customer actually configured (re-validated against the catalogue,
        # not trusted as-is) instead of the old hardcoded specs={}.
        specs: dict = {}
        component_costs = 0.0
        overhead_amount = 0.0
        playbook_id = None
        if request.build_config is not None:
            try:
                priced = await price_playbook_build(
                    db,
                    playbook_id=request.build_config.playbook_id,
                    slot_selections=request.build_config.slot_selections,
                    case_id=request.build_config.case_id,
                )
            except InvalidBuildError as e:
                log.error("payment.confirm_invalid_build_config", error=str(e))
                raise HTTPException(status_code=400, detail=str(e))
            playbook_id = priced.playbook_id
            component_costs = priced.parts_total
            overhead_amount = priced.overhead
            specs = {
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
            }

        # Create order
        order = Order(
            order_id=f"ORD-{payment_data['intent_id'][-12:]}",  # Use last 12 chars of intent ID
            customer_id=request.customer_id,
            status=OrderStatus.AWAITING_SOURCING,
            specs=specs,
            customer_price=payment_data["amount"],
            component_costs=component_costs,
            overhead_amount=overhead_amount,
            playbook_id=playbook_id,
            promised_delivery_date=None,  # No delivery estimation computed yet
            stripe_payment_intent_id=request.intent_id,
            notes=f"Payment processed via Stripe. Intent: {request.intent_id}",
        )

        db.add(order)
        await db.flush()  # Get the ID before commit
        order_id = order.id

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
async def refund_payment(request: RefundRequest) -> RefundResponse:
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
