import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import get_settings
import structlog

log = structlog.get_logger(__name__)
settings = get_settings()


async def send_order_confirmation_email(
    customer_email: str,
    customer_name: str,
    order_reference: str,
    build_summary: str,
    assigned_week: str,
) -> bool:
    """Send order confirmation email"""
    if not settings.smtp_host or not settings.smtp_user:
        log.warning("Email not configured, skipping confirmation email")
        return False

    subject = f"FlipFlop Order Confirmation: {order_reference}"
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Your FlipFlop Order is Confirmed!</h2>
            <p>Hello {customer_name},</p>
            <p>Thank you for ordering from FlipFlop. Your custom PC build is confirmed and will be built during week {assigned_week}.</p>
            <h3>Order Details</h3>
            <p><strong>Reference:</strong> {order_reference}</p>
            <p><strong>Build Summary:</strong></p>
            <pre>{build_summary}</pre>
            <p>You can track your order status at: https://flipflop.co.uk/order/{order_reference}</p>
            <p>For any questions, contact us at hello@flipflop.co.uk</p>
            <p>Best regards,<br>The FlipFlop Team</p>
        </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from or "noreply@flipflop.co.uk"
        msg["To"] = customer_email

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL(settings.smtp_host, 465) as server:
            server.login(settings.smtp_user, settings.smtp_pass)
            server.send_message(msg)

        log.info("Email sent", reference=order_reference, to=customer_email)
        return True

    except Exception as e:
        log.error("Email send failed", error=str(e), reference=order_reference)
        return False
