import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import get_settings
from app.services.feature_flags import is_enabled, FeatureFlags
import structlog

log = structlog.get_logger(__name__)
settings = get_settings()


def smtp_credentials() -> tuple[str, str, str]:
    """IONOS uses the mailbox login for both IMAP and SMTP.

    Keep a separately configured SMTP password authoritative, but safely fall
    back to the existing IMAP mailbox credentials so the secret is not copied
    into multiple environment variables.
    """
    return (
        settings.smtp_host,
        settings.smtp_user or settings.imap_user,
        settings.smtp_pass or settings.imap_pass,
    )


def smtp_is_configured() -> bool:
    return all(smtp_credentials())

def _send(msg: MIMEMultipart, reference: str) -> bool:
    # Kill switch: EMAIL_DISPATCH_ENABLED can suppress all email
    if not is_enabled(FeatureFlags.EMAIL_DISPATCH_ENABLED):
        log.warning(
            "Email dispatch disabled by feature flag; suppressing send",
            reference=reference,
            to=msg.get("To"),
            subject=msg.get("Subject"),
        )
        return False
    try:
        smtp_host, smtp_user, smtp_password = smtp_credentials()
        with smtplib.SMTP_SSL(smtp_host, 465) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        log.info("Email sent", reference=reference, to=msg["To"])
        return True
    except Exception as exc:
        log.error("Email send failed", error=str(exc), reference=reference)
        return False

async def send_order_confirmation_email(customer_email: str, customer_name: str, order_reference: str, build_summary: str, assigned_week: str, order_id: int | None = None) -> bool:
    if not smtp_is_configured():
        log.warning("Email not configured, skipping confirmation email")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"FlipFlop Order Confirmation: {order_reference}"
    msg["From"] = settings.smtp_from or "noreply@flipflop.co.uk"
    msg["To"] = customer_email
    portal = f"https://theflipflop.shop/my-builds/{order_id}" if order_id else "https://theflipflop.shop/my-builds"
    msg.attach(MIMEText(f"<html><body><h2>Your FlipFlop Order is Confirmed</h2><p>Hello {customer_name},</p><p>Your custom PC build is confirmed for week {assigned_week}.</p><p><strong>Reference:</strong> {order_reference}</p><pre>{build_summary}</pre><p><a href=\"{portal}\">Open your customer portal</a></p></body></html>", "html"))
    return _send(msg, order_reference)

async def send_shipment_update_email(customer_email: str, customer_name: str, order_reference: str, carrier: str | None, tracking_number: str | None, tracking_url: str | None, estimated_delivery: object | None, order_id: int | None = None) -> bool:
    if not smtp_is_configured():
        log.warning("Email not configured, skipping shipment email")
        return False
    tracking = f'<a href="{tracking_url}">{tracking_number}</a>' if tracking_url and tracking_number else (tracking_number or "Not available yet")
    estimate = str(estimated_delivery) if estimated_delivery else "The courier will provide an estimate when available."
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your FlipFlop PC has shipped: {order_reference}"
    msg["From"] = settings.smtp_from or "noreply@flipflop.co.uk"
    msg["To"] = customer_email
    portal = f"https://theflipflop.shop/my-builds/{order_id}" if order_id else "https://theflipflop.shop/my-builds"
    msg.attach(MIMEText(f"<html><body><h2>Your FlipFlop PC is on its way</h2><p>Hello {customer_name},</p><p>Order <strong>{order_reference}</strong> has been dispatched.</p><p>Courier: {carrier or 'Not specified'}<br>Tracking: {tracking}<br>Estimated delivery: {estimate}</p><p><a href=\"{portal}\">Open your customer portal</a></p></body></html>", "html"))
    return _send(msg, order_reference)

async def send_order_status_email(customer_email: str, customer_name: str, order_reference: str, status: str, order_id: int | None = None) -> bool:
    if not smtp_is_configured():
        log.warning("Email not configured, skipping status email")
        return False
    messages = {
        "building": ("Your FlipFlop build has started", "Your components are now in the build queue."),
        "qa": ("Your FlipFlop build is being tested", "Your machine has reached quality assurance testing."),
        "completed": ("Your FlipFlop build has been delivered", "Your order is marked delivered. Your owner portal contains the latest available documents and support tools."),
    }
    subject, body = messages.get(status, ("Your FlipFlop order has been updated", f"Your order status is now {status.replace('_', ' ')}."))
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{subject}: {order_reference}"
    msg["From"] = settings.smtp_from or "noreply@flipflop.co.uk"
    msg["To"] = customer_email
    portal = f"https://theflipflop.shop/my-builds/{order_id}" if order_id else "https://theflipflop.shop/my-builds"
    msg.attach(MIMEText(f"<html><body><h2>{subject}</h2><p>Hello {customer_name},</p><p>{body}</p><p><a href=\"{portal}\">Open your customer portal</a></p></body></html>", "html"))
    return _send(msg, order_reference)

async def send_email_async(to: str, subject: str, body: str, reference: str = "generic") -> bool:
    """Generic async email sender for transactional emails."""
    if not smtp_is_configured():
        log.warning("Email not configured, skipping email", reference=reference, to=to)
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or "noreply@flipflop.co.uk"
    msg["To"] = to
    msg.attach(MIMEText(body, "html"))
    return _send(msg, reference)
