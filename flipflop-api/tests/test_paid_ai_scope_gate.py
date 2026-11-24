import pytest

from app.services.getting_started_jobs import validate_ai_setup_checklist_update


PAID = [{"offer_id": "local_ai_setup", "payment_status": "paid"}]


def test_paid_ai_completion_requires_recorded_customer_scope_confirmation():
    with pytest.raises(ValueError, match="customer's approval"):
        validate_ai_setup_checklist_update(
            action="ai_services_complete",
            status="complete",
            purchased_ai_services=PAID,
            scope_confirmed=False,
        )


def test_paid_ai_completion_accepts_confirmed_scope():
    validate_ai_setup_checklist_update(
        action="ai_services_complete",
        status="complete",
        purchased_ai_services=PAID,
        scope_confirmed=True,
    )


def test_paid_ai_cannot_be_marked_not_required_even_with_confirmation():
    with pytest.raises(ValueError, match="complete the purchased setup"):
        validate_ai_setup_checklist_update(
            action="ai_services_complete",
            status="not_required",
            purchased_ai_services=PAID,
            scope_confirmed=True,
        )


def test_no_paid_ai_purchase_does_not_require_scope_confirmation():
    validate_ai_setup_checklist_update(
        action="ai_services_complete",
        status="complete",
        purchased_ai_services=[],
        scope_confirmed=False,
    )
