"""Durable, retryable customer case-status notification outbox."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.customer import Customer
from app.models.customer_problem import CustomerProblem
from app.models.customer_problem_notification import CustomerProblemNotification
from app.models.order import Order
from app.services.alerts import emit_alert
from app.services.email_service import send_customer_case_status_email


log = logging.getLogger(__name__)
_MAX_ATTEMPTS = 8
_MAX_BATCH = 50


def _retry_delay(attempts: int) -> timedelta:
    return timedelta(minutes=min(360, 2 ** max(1, attempts)))


async def deliver_customer_problem_notification(notification_id: int) -> dict[str, str]:
    """Claim one outbox row, send its snapshot, and persist the delivery result."""
    async with AsyncSessionLocal() as db:
        notification = (await db.execute(
            select(CustomerProblemNotification)
            .where(CustomerProblemNotification.id == notification_id)
            .with_for_update(skip_locked=True)
        )).scalar_one_or_none()
        if not notification or notification.state != "pending":
            return {"status": "not_pending"}
        now = datetime.utcnow()
        if notification.last_attempt_at and now - notification.last_attempt_at < _retry_delay(notification.attempt_count):
            return {"status": "backoff"}
        if notification.attempt_count >= _MAX_ATTEMPTS:
            return {"status": "exhausted"}

        problem = await db.get(CustomerProblem, notification.problem_id)
        order = await db.get(Order, notification.order_id)
        customer = await db.get(Customer, order.customer_id) if order else None
        if not problem or not order or not customer or not customer.email:
            notification.state = "failed"
            notification.last_error = "recipient_or_case_unavailable"
            notification.attempt_count = _MAX_ATTEMPTS
            await db.commit()
            await emit_alert(
                code="customer_case_notification_unavailable",
                source=f"customer_problem_notification:{notification.id}",
                severity="critical",
                link_url="/problems",
                message=f"Customer case notification {notification.id} has no current case, order, or recipient email.",
            )
            return {"status": "failed"}

        notification.attempt_count += 1
        notification.last_attempt_at = now
        notification.last_error = None
        recipient = customer.email
        name = customer.name or "there"
        order_id = order.id
        case_reference = f"CASE-{problem.id}"
        status_code = notification.status_code
        tracking_snapshot = notification.repair_tracking_snapshot
        await db.commit()

    try:
        sent = await send_customer_case_status_email(
            recipient,
            name,
            case_reference,
            status_code,
            order_id,
            repair_tracking=tracking_snapshot,
        )
    except Exception as error:
        log.exception("customer_case_notification.send_failed", notification_id=notification_id)
        sent = False
        error_code = type(error).__name__[:100]
    else:
        error_code = "mailer_returned_false"

    async with AsyncSessionLocal() as db:
        saved = (await db.execute(
            select(CustomerProblemNotification)
            .where(CustomerProblemNotification.id == notification_id)
            .with_for_update()
        )).scalar_one_or_none()
        if not saved or saved.state != "pending":
            return {"status": "already_resolved"}
        if sent:
            saved.state = "sent"
            saved.sent_at = datetime.utcnow()
            saved.last_error = None
            await db.commit()
            return {"status": "sent"}
        saved.last_error = error_code
        terminal = saved.attempt_count >= _MAX_ATTEMPTS
        if terminal:
            saved.state = "failed"
        await db.commit()

    if terminal:
        await emit_alert(
            code="customer_case_notification_exhausted",
            source=f"customer_problem_notification:{notification_id}",
            severity="critical",
            link_url="/problems",
            message=f"Customer case notification {notification_id} failed after {_MAX_ATTEMPTS} attempts. Contact the customer and review mail delivery.",
        )
        return {"status": "failed"}
    return {"status": "pending"}


async def retry_pending_customer_problem_notifications() -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(
            select(CustomerProblemNotification.id)
            .where(
                CustomerProblemNotification.state == "pending",
                CustomerProblemNotification.attempt_count < _MAX_ATTEMPTS,
            )
            .order_by(CustomerProblemNotification.created_at.asc(), CustomerProblemNotification.id.asc())
            .limit(_MAX_BATCH)
        )).scalars().all()

    sent = failed = deferred = 0
    for notification_id in ids:
        result = await deliver_customer_problem_notification(notification_id)
        if result["status"] == "sent":
            sent += 1
        elif result["status"] == "failed":
            failed += 1
        else:
            deferred += 1
    return {"sent": sent, "failed": failed, "deferred": deferred}
