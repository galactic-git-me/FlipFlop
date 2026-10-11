import os
import smtplib
from html import escape
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlsplit
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


def _is_live_runtime() -> bool:
    runtime = os.getenv("FLIPFLOP_RUNTIME_ENV", settings.app_env or "dev").strip().lower()
    return runtime in {"live", "production", "prod"}


def _resolve_outbound_recipient(original: str, reference: str) -> str:
    """Route development mail to the private sink instead of a customer."""
    if _is_live_runtime():
        return original

    sink = settings.email_sandbox_recipient.strip()
    if not sink:
        log.error(
            "Development email suppressed: EMAIL_SANDBOX_RECIPIENT is not configured",
            reference=reference,
            intended_recipient=original,
        )
        return ""

    if sink != original:
        log.info(
            "Development email redirected to sandbox recipient",
            reference=reference,
            intended_recipient=original,
            sandbox_recipient=sink,
        )
    return sink


def _send(msg: MIMEMultipart, reference: str) -> bool:
    recipient = _resolve_outbound_recipient(msg.get("To", ""), reference)
    if not recipient:
        return False
    if msg.get("To"):
        msg.replace_header("To", recipient)
    else:
        msg["To"] = recipient

    if not _is_live_runtime() and not msg.get("Subject", "").startswith("[DEV]"):
        msg.replace_header("Subject", f"[DEV] {msg.get('Subject', '')}")

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
    "cancellation_pending": ("Cancellation requested", "We have paused sourcing and are reconciling the full refund for your order. Your private portal will show the latest status."),
    "cancelled": ("Order cancelled", "Your order has been cancelled and the full refund has been issued to your original payment method. Your bank may take additional time to display it."),
}

CASE_STATUS_EMAIL_COPY = {
    "received": ("Case received", "We have received your support case."),
    "claim_opened": ("Warranty claim opened", "Your warranty claim has been opened for review."),
    "reviewing": ("Case under review", "Our team is reviewing your case."),
    "approved": ("Warranty work approved", "The proposed warranty work has been approved. Please check your private portal for the latest details."),
    "awaiting_customer_return": ("Return needed for your repair", "We are waiting for your machine to be returned to us. Please check your private portal for the next steps."),
    "return_in_transit": ("Repair return on its way", "Your machine is on its way to us for inspection or repair."),
    "received_for_inspection": ("Machine received for inspection", "We have recorded your machine as received for inspection."),
    "repair_in_progress": ("Repair in progress", "Work on your repair is now in progress."),
    "waiting_for_parts": ("Repair update", "Your repair is waiting for parts. We will update your private portal as the case progresses."),
    "replacement_ordered": ("Replacement arranged", "A replacement has been arranged for your case."),
    "replacement_dispatched": ("Replacement dispatched", "Your replacement has been dispatched. Open your private portal for the latest delivery details."),
    "resolved": ("Case resolved", "Your support or warranty case has been marked as resolved."),
    "rejected": ("Warranty claim decision", "A decision has been recorded for your warranty claim. Please open your private portal or contact us if you need clarification."),
    "closed": ("Case closed", "Your support or warranty case has been closed."),
}


async def send_customer_case_status_email(
    customer_email: str,
    customer_name: str,
    case_reference: str,
    status: str,
    order_id: int,
    repair_tracking: dict | None = None,
) -> bool:
    """Send a minimal status notice for a direct-storefront aftercare case."""
    if not smtp_is_configured():
        log.warning("Email not configured, skipping customer case update", reference=case_reference, status=status)
        return False
    title, message = CASE_STATUS_EMAIL_COPY.get(
        status,
        ("Case update", f"Your case status is now {status.replace('_', ' ')}."),
    )
    portal_base = settings.frontend_url.rstrip("/")
    portal = f"{portal_base}/my-builds/{order_id}#support"
    tracking_html = ""
    tracking_url = str((repair_tracking or {}).get("tracking_url") or "").strip()
    parsed_tracking_url = urlsplit(tracking_url)
    if (
        parsed_tracking_url.scheme == "https"
        and parsed_tracking_url.netloc
        and not parsed_tracking_url.username
        and not parsed_tracking_url.password
        and (repair_tracking or {}).get("tracking_number")
        and (repair_tracking or {}).get("carrier")
    ):
        purpose = "replacement shipment" if repair_tracking.get("purpose") == "replacement" else "return shipment"
        tracking_html = (
            f"<p><strong>{escape(purpose.title())}:</strong> {escape(str(repair_tracking['carrier']))} · "
            f"{escape(str(repair_tracking['tracking_number']))}<br>"
            f"<a href=\"{escape(tracking_url, quote=True)}\">Track with the carrier</a></p>"
        )
    html = f"""<!doctype html><html><body style="margin:0;background:#f3f6fb;font-family:Arial,sans-serif;color:#152238"><div style="max-width:640px;margin:32px auto;background:#fff;border:1px solid #dce5f0;border-radius:18px;overflow:hidden"><div style="padding:26px 32px;background:#07152d;color:#fff"><div style="font-size:12px;letter-spacing:3px;color:#68d7ff">FLIPFLOP</div><h1>{escape(title)}</h1></div><div style="padding:30px 32px;line-height:1.6"><p>Hello {escape(customer_name or 'there')},</p><p>{escape(message)}</p><p><strong>Case:</strong> {escape(case_reference)}</p>{tracking_html}<p><a href="{escape(portal, quote=True)}">View your private customer portal</a></p><p style="font-size:12px;color:#66758a">This update does not change your statutory rights or the terms of your warranty.</p></div></div></body></html>"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{title}: {case_reference}"
    msg["From"] = settings.smtp_from or "noreply@flipflop.co.uk"
    msg["To"] = customer_email
    msg.attach(MIMEText(html, "html"))
    return _send(msg, f"customer-case-{case_reference}-{status}")


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


async def send_courier_event_email(
    customer_email: str,
    customer_name: str,
    order_reference: str,
    description: str,
    *,
    order_id: int | None = None,
    tracking_url: str | None = None,
    live_map_url: str | None = None,
) -> bool:
    """Send one evidence-backed material courier update."""
    if not smtp_is_configured():
        log.warning("Email not configured, skipping courier event email", reference=order_reference)
        return False
    portal_base = settings.frontend_url.rstrip("/")
    portal = f"{portal_base}/my-builds/{order_id}" if order_id else f"{portal_base}/my-builds"
    links = []
    if tracking_url:
        links.append(f'<a href="{escape(tracking_url, quote=True)}">Track with the courier</a>')
    if live_map_url:
        links.append(f'<a href="{escape(live_map_url, quote=True)}">Open the courier live map</a>')
    link_html = " · ".join(links)
    html = f"""<!doctype html><html><body style="margin:0;background:#f3f6fb;font-family:Arial,sans-serif;color:#152238"><div style="max-width:640px;margin:32px auto;background:#fff;border:1px solid #dce5f0;border-radius:18px;overflow:hidden"><div style="padding:26px 32px;background:#07152d;color:#fff"><div style="font-size:12px;letter-spacing:3px;color:#68d7ff">FLIPFLOP</div><h1>Courier update</h1></div><div style="padding:30px 32px;line-height:1.6"><p>Hello {escape(customer_name or 'there')},</p><p>{escape(description)}</p><p><strong>Order:</strong> {escape(order_reference)}</p>{f'<p>{link_html}</p>' if link_html else ''}<p><a href="{escape(portal, quote=True)}">Open your private build portal</a></p></div></div></body></html>"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Courier update: {order_reference}"
    msg["From"] = settings.smtp_from or "noreply@flipflop.co.uk"
    msg["To"] = customer_email
    msg.attach(MIMEText(html, "html"))
    return _send(msg, f"courier-event-{order_reference}")


async def send_delivery_followup_email(customer_email: str, customer_name: str, build_id: int, *, review_url: str, feedback_url: str | None = None) -> bool:
    """Send the post-delivery onboarding, support and review request."""
    if not smtp_is_configured():
        return False
    portal_base = settings.frontend_url.rstrip("/")
    portal = f"{portal_base}/my-builds/{build_id}"
    guide = f"{portal_base}/getting-started"
    support = f"{portal_base}/support"
    feedback = feedback_url or review_url
    html = f"""<!doctype html><html><body style=\"margin:0;background:#f3f6fb;font-family:Arial,sans-serif;color:#152238\"><div style=\"max-width:640px;margin:32px auto;background:#fff;border:1px solid #dce5f0;border-radius:18px;overflow:hidden\"><div style=\"padding:26px 32px;background:#07152d;color:#fff\"><div style=\"font-size:12px;letter-spacing:3px;color:#68d7ff\">FLIPFLOP</div><h1>Your build has arrived</h1></div><div style=\"padding:30px 32px;line-height:1.6\"><p>Hello {escape(customer_name or 'there')},</p><p>We hope your FlipFlop build arrived safely. Your 12-month warranty starts from the delivery date.</p><p><a href=\"{escape(portal, quote=True)}\">Open your private My Builds page</a></p><p><a href=\"{escape(guide, quote=True)}\">Read the getting started guide</a> · <a href=\"{escape(support, quote=True)}\">Get help</a></p><p>If you are happy with your build, we would really appreciate a review: <a href=\"{escape(feedback, quote=True)}\">leave feedback</a>.</p><p style=\"font-size:12px;color:#66758a\">If you bought through a marketplace, the feedback link takes you to that marketplace. Direct FlipFlop purchases use our review page.</p></div></div></body></html>"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your FlipFlop build has arrived — setup and feedback"
    msg["From"] = settings.smtp_from or "noreply@flipflop.co.uk"
    msg["To"] = customer_email
    msg.attach(MIMEText(html, "html"))
    return _send(msg, f"delivery-followup-build-{build_id}")


async def send_guest_portal_claim_email(
    customer_email: str,
    customer_name: str,
    build_name: str,
    claim_url: str,
    expires_at: object,
    order_reference: str,
) -> bool:
    """Send a one-time portal claim link to the verified direct-order email."""
    if not smtp_is_configured():
        log.warning("Email not configured, skipping portal claim email", order_reference=order_reference)
        return False
    expiry = escape(str(expires_at))
    url = escape(claim_url, quote=True)
    safe_name = escape(customer_name or "there")
    safe_build = escape(build_name or "your FlipFlop build")
    html = (
        '<!doctype html><html><body style="margin:0;background:#f3f6fb;font-family:Arial,sans-serif;color:#152238">'
        '<div style="max-width:640px;margin:32px auto;background:#fff;border:1px solid #dce5f0;border-radius:18px;overflow:hidden">'
        '<div style="padding:26px 32px;background:#07152d;color:#fff"><div style="font-size:12px;letter-spacing:3px;color:#68d7ff">FLIPFLOP</div>'
        '<h1>Your personal build portal is ready</h1></div><div style="padding:30px 32px;line-height:1.6">'
        f'<p>Hello {safe_name},</p><p>We have prepared a private portal for <strong>{safe_build}</strong>. '
        'Use the secure button below to open your order, build updates, delivery tracking and support information.</p>'
        f'<p><a href="{url}" style="display:inline-block;padding:13px 20px;background:#1267e8;color:#fff;text-decoration:none;border-radius:8px">Open my build portal</a></p>'
        '<p>On the page that opens, press “Open my build portal” to activate access. This extra step prevents email security scanners from using your one-time link.</p>'
        f'<p>This one-time link expires on {expiry}. You can then use the portal access created for this order.</p>'
        '<p>If you did not make this purchase, contact FlipFlop through your order confirmation.</p>'
        '</div></div></body></html>'
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your FlipFlop build portal — {order_reference}"
    msg["From"] = settings.smtp_from or "noreply@flipflop.co.uk"
    msg["To"] = customer_email
    msg.attach(MIMEText(html, "html"))
    return _send(msg, f"portal-claim-{order_reference}")


async def send_dispatched_guest_portal_email(
    customer_email: str,
    customer_name: str,
    build_name: str,
    claim_url: str,
    expires_at: object,
    order_reference: str,
    carrier: str | None,
    tracking_number: str | None,
    tracking_url: str | None,
) -> bool:
    """Send the direct guest's one-time portal link with dispatch details."""
    if not smtp_is_configured():
        log.warning("Email not configured, skipping dispatched portal email", order_reference=order_reference)
        return False
    settings = get_settings()
    safe_name = escape(customer_name or "there")
    safe_build = escape(build_name or "your FlipFlop build")
    safe_reference = escape(order_reference)
    safe_expiry = escape(str(expires_at))
    safe_url = escape(claim_url, quote=True)
    tracking = ""
    safe_tracking_url = False
    if tracking_url:
        try:
            parsed_tracking_url = urlsplit(tracking_url)
            safe_tracking_url = (
                parsed_tracking_url.scheme == "https"
                and bool(parsed_tracking_url.hostname)
                and not parsed_tracking_url.username
                and not parsed_tracking_url.password
            )
        except ValueError:
            safe_tracking_url = False
    if tracking_number:
        tracking_value = escape(tracking_number)
        if safe_tracking_url:
            tracking_value = f'<a href="{escape(tracking_url, quote=True)}">{tracking_value}</a>'
        tracking = (
            f'<p><strong>Carrier:</strong> {escape(carrier or "Courier")}<br>'
            f'<strong>Tracking:</strong> {tracking_value}</p>'
        )
    portal_base = settings.frontend_url.rstrip("/")
    html = (
        '<!doctype html><html><body style="margin:0;background:#f3f6fb;font-family:Arial,sans-serif;color:#152238">'
        '<div style="max-width:640px;margin:32px auto;background:#fff;border:1px solid #dce5f0;border-radius:18px;overflow:hidden">'
        '<div style="padding:26px 32px;background:#07152d;color:#fff"><div style="font-size:12px;letter-spacing:3px;color:#68d7ff">FLIPFLOP</div>'
        '<h1>Your build is on its way</h1></div><div style="padding:30px 32px;line-height:1.6">'
        f'<p>Hello {safe_name},</p><p>Your <strong>{safe_build}</strong> has been handed to the courier. '
        f'Order reference: <strong>{safe_reference}</strong>.</p>{tracking}'
        f'<p><a href="{safe_url}" style="display:inline-block;padding:13px 20px;background:#1267e8;color:#fff;text-decoration:none;border-radius:8px">Open my private build portal</a></p>'
        '<p>On the page that opens, press “Open my build portal” to activate access. This extra step prevents email security scanners from using your one-time link.</p>'
        f'<p>The one-time access link expires on {safe_expiry}. Your portal includes build documents, delivery updates and support information.</p>'
        f'<p><a href="{escape(portal_base + "/getting-started", quote=True)}">Getting started help</a></p>'
        '<p style="font-size:12px;color:#66758a">If you did not make this purchase, contact FlipFlop using your order details.</p>'
        '</div></div></body></html>'
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your FlipFlop build is on its way — {safe_reference}"
    msg["From"] = settings.smtp_from or "noreply@flipflop.co.uk"
    msg["To"] = customer_email
    msg.attach(MIMEText(html, "html"))
    return _send(msg, f"portal-dispatch-{order_reference}")

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
