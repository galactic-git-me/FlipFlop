import stripe
from app.config import get_settings
from typing import Dict, Any

settings = get_settings()
stripe.api_key = settings.stripe_secret_key


def create_checkout_session(
    order_reference: str,
    build_config: Dict[str, Any],
    customer_email: str,
    total_gbp: float,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create Stripe Checkout Session and return session URL"""
    line_items = _build_line_items(build_config, total_gbp)

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        customer_email=customer_email,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"order_reference": order_reference},
    )

    return session.url


def _build_line_items(build_config: Dict[str, Any], total_gbp: float) -> list:
    """Convert build config to Stripe line items"""
    line_items = []

    component_count = 0
    for slot_type, slot_data in build_config.items():
        if slot_type == "case":
            continue
        if isinstance(slot_data, dict) and "name" in slot_data:
            component_count += 1
            line_items.append({
                "price_data": {
                    "currency": "gbp",
                    "product_data": {
                        "name": slot_data.get("name", f"{slot_type.upper()} Component"),
                    },
                    "unit_amount": int(slot_data.get("display_price", 0) * 100),
                },
                "quantity": 1,
            })

    if "case" in build_config and isinstance(build_config["case"], dict):
        case_data = build_config["case"]
        line_items.append({
            "price_data": {
                "currency": "gbp",
                "product_data": {
                    "name": case_data.get("name", "Case"),
                },
                "unit_amount": int(case_data.get("rrp", 0) * 100),
            },
            "quantity": 1,
        })

    if not line_items:
        line_items.append({
            "price_data": {
                "currency": "gbp",
                "product_data": {
                    "name": "Custom PC Build",
                },
                "unit_amount": int(total_gbp * 100),
            },
            "quantity": 1,
        })

    return line_items


def verify_webhook_signature(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """Verify Stripe webhook signature and return event data"""
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )
        return event
    except ValueError:
        raise ValueError("Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid signature")
