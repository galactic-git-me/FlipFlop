import smtplib
from html import escape
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
    return await send_build_status_email(
        customer_email, customer_name, order_reference, "shipped", order_id,
        carrier=carrier, tracking_number=tracking_number,
        tracking_url=tracking_url, estimated_delivery=estimated_delivery,
        update_kind="courier",
    )


STATUS_EMAIL_COPY = {
    "awaiting_sourcing": ("Order received", "Your order is safely with us and is queued for sourcing."),
    "parts_ordered": ("Parts ordered", "The parts for your build have been ordered and your build is moving forward."),
    "building": ("Build in progress", "Your components are now being assembled into your FlipFlop machine."),
    "qa": ("Performance testing", "Your machine has entered performance and quality testing."),
    "ready_to_ship": ("Built and ready to dispatch", "Your machine has passed the build stage and is being prepared for dispatch."),
    "shipped": ("Dispatched", "Your FlipFlop machine has been handed to the courier."),
    "completed": ("Delivered", "Your order is marked as delivered. Your private portal contains the latest support and build information."),
}


def render_build_status_email(
    customer_name: str,
    order_reference: str,
    status: str,
    order_id: int | None = None,
    *,
    carrier: str | None = None,
    tracking_number: str | None = None,
    tracking_url: str | None = None,
    estimated_delivery: object | None = None,
    update_kind: str = "status",
) -> tuple[str, str]:
    """Render the approval-ready branded transactional email template."""
    title, message = STATUS_EMAIL_COPY.get(status, ("Build update", f"Your order status is now {status.replace('_', ' ')}."))
    if update_kind == "courier":
        title = "Courier update"
        message = "The courier information for your order has been updated."
    portal_base = settings.frontend_url.rstrip("/")
    portal = f"{portal_base}/my-builds/{order_id}" if order_id else f"{portal_base}/my-builds"
    safe_name = escape(customer_name or "there")
    safe_reference = escape(order_reference)
    details = ""
    if carrier or tracking_number or estimated_delivery:
        tracking = escape(tracking_number or "Not available yet")
        tracking_html = f'<a href="{escape(tracking_url, quote=True)}">{tracking}</a>' if tracking_url and tracking_number else tracking
        details = f"""
        <div style=\"margin:24px 0;padding:18px;border:1px solid #d9e4f2;border-radius:12px;background:#f7fbff\">
          <strong>Delivery information</strong><br>
          Courier: {escape(carrier or 'Not specified')}<br>
          Tracking: {tracking_html}<br>
          Estimated delivery: {escape(str(estimated_delivery) if estimated_delivery else 'The courier will provide an estimate when available.')}
        </div>"""
    html_body = f"""<!doctype html><html><body style=\"margin:0;background:#f3f6fb;font-family:Arial,sans-serif;color:#152238\">
      <div style=\"max-width:640px;margin:32px auto;background:#ffffff;border-radius:18px;overflow:hidden;border:1px solid #dce5f0\">
        <div style=\"padding:26px 32px;background:#07152d;color:#ffffff\"><div style=\"font-size:12px;letter-spacing:3px;color:#68d7ff\">FLIPFLOP</div><h1 style=\"margin:14px 0 0;font-size:28px\">{escape(title)}</h1></div>
        <div style=\"padding:30px 32px\"><p>Hello {safe_name},</p><p style=\"line-height:1.6\">{escape(message)}</p><p><strong>Order:</strong> {safe_reference}</p>{details}<p style=\"margin-top:28px\"><a href=\"{escape(portal, quote=True)}\" style=\"display:inline-block;padding:13px 18px;border-radius:9px;background:#0b8cf0;color:#fff;text-decoration:none;font-weight:bold\">Open your private customer portal</a></p><p style=\"font-size:12px;line-height:1.5;color:#66758a\">Your portal contains the build status journey, delivery tracking, the exact 3D model, documents and support tools.</p></div>
      </div></body></html>"""
    subject = f"{title}: {order_reference}"
    return subject, html_body


async def send_build_status_email(
    customer_email: str,
    customer_name: str,
    order_reference: str,
    status: str,
    order_id: int | None = None,
    *,
    carrier: str | None = None,
    tracking_number: str | None = None,
    tracking_url: str | None = None,
    estimated_delivery: object | None = None,
    update_kind: str = "status",
) -> bool:
    if not smtp_is_configured():
        log.warning("Email not configured, skipping build status email", reference=order_reference, status=status)
        return False
    subject, html_body = render_build_status_email(
        customer_name, order_reference, status, order_id,
        carrier=carrier, tracking_number=tracking_number,
        tracking_url=tracking_url, estimated_delivery=estimated_delivery,
        update_kind=update_kind,
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or "noreply@flipflop.co.uk"
    msg["To"] = customer_email
    msg.attach(MIMEText(html_body, "html"))
    return _send(msg, order_reference)

async def send_order_status_email(customer_email: str, customer_name: str, order_reference: str, status: str, order_id: int | None = None) -> bool:
    return await send_build_status_email(customer_email, customer_name, order_reference, status, order_id)

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
