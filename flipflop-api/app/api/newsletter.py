from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from secrets import token_urlsafe
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.customer import Customer
from app.models.newsletter_subscription import NewsletterSubscription
from app.routes.auth import get_current_user
from app.services.email_service import send_email_async
from app.config import get_settings

router = APIRouter(prefix="/newsletter", tags=["newsletter"])
CONSENT_VERSION = "footer-v1"
CONFIRMATION_HOURS = 48


class NewsletterSubscribeRequest(BaseModel):
    email: EmailStr | None = None
    consent: bool = False
    website: str = ""  # Honeypot field for basic bot filtering.


class NewsletterSubscribeResponse(BaseModel):
    status: str
    message: str


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _result_page(title: str, message: str, status_code: int = 200) -> HTMLResponse:
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><title>{escape(title)} · FlipFlop</title>
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#060608;color:#f0f2f5;font:16px/1.6 system-ui,sans-serif}}main{{width:min(34rem,calc(100% - 3rem));padding:2rem;border:1px solid #26334a;border-radius:1rem;background:linear-gradient(135deg,#111522,#0b1020);box-shadow:0 1rem 4rem #0008}}h1{{color:#b8ff3d;font-size:1.5rem}}a{{color:#8ab8ff}}.brand{{color:#ff8a2e;font-size:.7rem;letter-spacing:.18em;text-transform:uppercase}}</style></head>
<body><main><p class="brand">FlipFlop · Beautiful machines</p><h1>{escape(title)}</h1><p>{escape(message)}</p><p><a href="{escape(get_settings().frontend_url.rstrip('/'))}">Return to FlipFlop</a></p></main></body></html>"""
    return HTMLResponse(body, status_code=status_code, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.post("/subscribe", response_model=NewsletterSubscribeResponse, status_code=202)
async def subscribe_to_newsletter(
    payload: NewsletterSubscribeRequest,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> NewsletterSubscribeResponse:
    if payload.website.strip():
        return NewsletterSubscribeResponse(status="accepted", message="If you are not already subscribed, check your inbox for confirmation instructions.")
    if not payload.consent:
        raise HTTPException(status_code=400, detail="Please confirm that you want to receive the newsletter.")

    customer = None
    if authorization:
        customer = await get_current_user(authorization=authorization, db=db)
        email = customer.email.strip().lower()
    elif payload.email:
        email = str(payload.email).strip().lower()
    else:
        raise HTTPException(status_code=422, detail="An email address is required.")

    existing = await db.scalar(
        select(NewsletterSubscription)
        .where(NewsletterSubscription.email == email)
        .with_for_update()
    )
    if existing and existing.status == "active":
        if customer:
            existing.customer_id = customer.id
            customer.marketing_opt_in = True
            db.add(existing)
            db.add(customer)
            return NewsletterSubscribeResponse(status="subscribed", message="You are subscribed to the FlipFlop newsletter.")
        return NewsletterSubscribeResponse(
            status="accepted",
            message="If you are not already subscribed, check your inbox for confirmation instructions.",
        )

    now = datetime.now(timezone.utc)
    if customer:
        # A signed-in customer has explicitly opted in on this form, so no
        # second confirmation email is required. Keep the existing profile
        # preference in sync with the subscriber record.
        unsubscribe_token = token_urlsafe(32)
        if existing is None:
            existing = NewsletterSubscription(
                email=email,
                customer_id=customer.id,
                status="active",
                consent_at=now,
                consent_version=CONSENT_VERSION,
                confirmed_at=now,
                unsubscribe_token_hash=_hash_token(unsubscribe_token),
            )
            db.add(existing)
        else:
            existing.customer_id = customer.id
            existing.status = "active"
            existing.consent_at = now
            existing.consent_version = CONSENT_VERSION
            existing.confirmed_at = now
            existing.confirmation_token_hash = None
            existing.confirmation_expires_at = None
            existing.unsubscribe_token_hash = _hash_token(unsubscribe_token)
            existing.unsubscribed_at = None
        customer.marketing_opt_in = True
        db.add(customer)
        return NewsletterSubscribeResponse(status="subscribed", message="You are subscribed to the FlipFlop newsletter.")

    customer_for_email = await db.scalar(select(Customer).where(Customer.email == email))
    confirm_token = token_urlsafe(32)
    unsubscribe_token = token_urlsafe(32)
    if existing is None:
        existing = NewsletterSubscription(
            email=email,
            customer_id=customer_for_email.id if customer_for_email else None,
            status="pending",
            consent_at=now,
            consent_version=CONSENT_VERSION,
            confirmation_token_hash=_hash_token(confirm_token),
            confirmation_expires_at=now + timedelta(hours=CONFIRMATION_HOURS),
            unsubscribe_token_hash=_hash_token(unsubscribe_token),
        )
        db.add(existing)
    else:
        existing.customer_id = customer_for_email.id if customer_for_email else None
        existing.status = "pending"
        existing.consent_at = now
        existing.consent_version = CONSENT_VERSION
        existing.confirmed_at = None
        existing.unsubscribed_at = None
        existing.confirmation_token_hash = _hash_token(confirm_token)
        existing.confirmation_expires_at = now + timedelta(hours=CONFIRMATION_HOURS)
        existing.unsubscribe_token_hash = _hash_token(unsubscribe_token)

    settings = get_settings()
    base_url = settings.frontend_url.rstrip("/")
    confirmation_url = f"{base_url}/api/newsletter/confirm?{urlencode({'token': confirm_token})}"
    unsubscribe_url = f"{base_url}/api/newsletter/unsubscribe?{urlencode({'token': unsubscribe_token})}"
    email_body = f"""<html><body style="font-family:Arial,sans-serif;color:#202938">
<h2>Confirm your FlipFlop newsletter signup</h2>
<p>Click the link below within {CONFIRMATION_HOURS} hours to confirm that you want occasional FlipFlop news and offers by email.</p>
<p><a href="{escape(confirmation_url)}">Confirm my signup</a></p>
<p>If you did not request this, you can cancel the signup here: <a href="{escape(unsubscribe_url)}">cancel this request</a>.</p>
<p>Beautiful machines, built to be admired.<br>FlipFlop</p></body></html>"""
    sent = await send_email_async(email, "Confirm your FlipFlop newsletter signup", email_body, "newsletter-confirmation")
    if not sent:
        raise HTTPException(status_code=503, detail="Newsletter signup is temporarily unavailable. Please try again later.")

    return NewsletterSubscribeResponse(
        status="pending_confirmation",
        message="If you are not already subscribed, check your inbox for confirmation instructions.",
    )


@router.get("/confirm", response_class=HTMLResponse)
async def confirm_newsletter_signup(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    now = datetime.now(timezone.utc)
    subscription = await db.scalar(
        select(NewsletterSubscription).where(
            NewsletterSubscription.confirmation_token_hash == _hash_token(token),
            NewsletterSubscription.status == "pending",
        )
    )
    if not subscription or not subscription.confirmation_expires_at or subscription.confirmation_expires_at < now:
        return _result_page("Signup link expired", "Please return to the footer and request a new confirmation email.", 410)

    subscription.status = "active"
    subscription.confirmed_at = now
    subscription.confirmation_token_hash = None
    subscription.confirmation_expires_at = None
    if subscription.customer_id is not None:
        customer = await db.get(Customer, subscription.customer_id)
        if customer:
            customer.marketing_opt_in = True
            db.add(customer)
    db.add(subscription)
    return _result_page("You’re subscribed", "Your FlipFlop newsletter signup is confirmed. You can unsubscribe from any newsletter email.")


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_from_newsletter(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    subscription = await db.scalar(
        select(NewsletterSubscription).where(
            NewsletterSubscription.unsubscribe_token_hash == _hash_token(token),
            NewsletterSubscription.status.in_(("pending", "active")),
        )
    )
    if not subscription:
        return _result_page("Link no longer active", "This signup has already been cancelled or the link has expired.", 410)

    subscription.status = "unsubscribed"
    subscription.unsubscribed_at = datetime.now(timezone.utc)
    subscription.confirmation_token_hash = None
    subscription.confirmation_expires_at = None
    subscription.unsubscribe_token_hash = None
    if subscription.customer_id is not None:
        customer = await db.get(Customer, subscription.customer_id)
        if customer:
            customer.marketing_opt_in = False
            db.add(customer)
    db.add(subscription)
    return _result_page("You’re unsubscribed", "You will not receive FlipFlop newsletter emails. You can sign up again from the footer whenever you like.")
