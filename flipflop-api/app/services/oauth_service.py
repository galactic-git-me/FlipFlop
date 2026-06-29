import structlog
import httpx
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.customer import Customer

log = structlog.get_logger(__name__)
settings = get_settings()


class OAuthService:
    """Service for handling OAuth2 authentication with Google and GitHub."""

    @staticmethod
    async def get_google_auth_url() -> str:
        """Generate Google OAuth authorization URL."""
        google_client_id = settings.google_client_id
        redirect_uri = settings.google_redirect_uri
        return (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={google_client_id}&"
            f"redirect_uri={redirect_uri}&"
            "response_type=code&"
            "scope=openid%20email%20profile&"
            "access_type=offline"
        )

    @staticmethod
    async def get_github_auth_url() -> str:
        """Generate GitHub OAuth authorization URL."""
        github_client_id = settings.github_client_id
        redirect_uri = settings.github_redirect_uri
        return (
            "https://github.com/login/oauth/authorize?"
            f"client_id={github_client_id}&"
            f"redirect_uri={redirect_uri}&"
            "scope=user:email"
        )

    @staticmethod
    async def exchange_google_code(code: str) -> dict:
        """Exchange Google auth code for access token and user info."""
        try:
            async with httpx.AsyncClient() as client:
                # Exchange code for token
                token_response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": settings.google_redirect_uri,
                    },
                )
                token_response.raise_for_status()
                token_data = token_response.json()

                # Get user info using access token
                user_response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {token_data['access_token']}"},
                )
                user_response.raise_for_status()
                return user_response.json()
        except httpx.HTTPError as e:
            log.error("oauth.google_exchange_failed", error=str(e))
            raise

    @staticmethod
    async def exchange_github_code(code: str) -> dict:
        """Exchange GitHub auth code for access token and user info."""
        try:
            async with httpx.AsyncClient() as client:
                # Exchange code for token
                token_response = await client.post(
                    "https://github.com/login/oauth/access_token",
                    data={
                        "client_id": settings.github_client_id,
                        "client_secret": settings.github_client_secret,
                        "code": code,
                    },
                    headers={"Accept": "application/json"},
                )
                token_response.raise_for_status()
                token_data = token_response.json()

                if "error" in token_data:
                    raise ValueError(f"GitHub error: {token_data.get('error_description', token_data['error'])}")

                # Get user info
                user_response = await client.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {token_data['access_token']}"},
                )
                user_response.raise_for_status()
                return user_response.json()
        except httpx.HTTPError as e:
            log.error("oauth.github_exchange_failed", error=str(e))
            raise

    @staticmethod
    async def get_or_create_user_from_google(
        db: AsyncSession,
        google_user: dict,
    ) -> Customer:
        """Get or create customer from Google user info."""
        google_id = str(google_user.get("id"))
        email = google_user.get("email", "").lower()
        name = google_user.get("name", "")

        if not email:
            raise ValueError("Google user email not provided")

        # Check if user exists by Google ID
        result = await db.execute(
            select(Customer).where(Customer.google_id == google_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            log.info("oauth.google_login_existing", customer_id=existing.id, google_id=google_id)
            return existing

        # Check if email exists (allow linking)
        result = await db.execute(
            select(Customer).where(Customer.email == email)
        )
        existing_email = result.scalar_one_or_none()
        if existing_email:
            # Link Google account to existing customer
            log.info("oauth.google_account_linked", customer_id=existing_email.id, google_id=google_id)
            existing_email.google_id = google_id
            existing_email.google_email = email
            if not existing_email.oauth_provider:
                existing_email.oauth_provider = "google"
            existing_email.updated_at = datetime.now(timezone.utc)
            db.add(existing_email)
            await db.commit()
            await db.refresh(existing_email)
            return existing_email

        # Create new customer
        customer = Customer(
            email=email,
            name=name,
            google_id=google_id,
            google_email=email,
            oauth_provider="google",
            password_hash="oauth-provider",  # OAuth users don't have passwords
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(customer)
        await db.flush()
        await db.commit()
        await db.refresh(customer)
        log.info("oauth.google_account_created", customer_id=customer.id, google_id=google_id)
        return customer

    @staticmethod
    async def get_or_create_user_from_github(
        db: AsyncSession,
        github_user: dict,
    ) -> Customer:
        """Get or create customer from GitHub user info."""
        github_id = github_user.get("id")
        username = github_user.get("login", "")
        email = github_user.get("email")
        name = github_user.get("name") or username

        if not github_id or not username:
            raise ValueError("GitHub user ID or username not provided")

        # GitHub might not provide email, generate one if needed
        if not email:
            email = f"{username}@github.user"
        else:
            email = email.lower()

        # Check if user exists by GitHub ID
        result = await db.execute(
            select(Customer).where(Customer.github_id == github_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            log.info("oauth.github_login_existing", customer_id=existing.id, github_id=github_id)
            return existing

        # Check if email exists (allow linking)
        result = await db.execute(
            select(Customer).where(Customer.email == email)
        )
        existing_email = result.scalar_one_or_none()
        if existing_email:
            # Link GitHub account
            log.info("oauth.github_account_linked", customer_id=existing_email.id, github_id=github_id)
            existing_email.github_id = github_id
            existing_email.github_username = username
            if not existing_email.oauth_provider:
                existing_email.oauth_provider = "github"
            existing_email.updated_at = datetime.now(timezone.utc)
            db.add(existing_email)
            await db.commit()
            await db.refresh(existing_email)
            return existing_email

        # Create new customer
        customer = Customer(
            email=email,
            name=name,
            github_id=github_id,
            github_username=username,
            oauth_provider="github",
            password_hash="oauth-provider",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(customer)
        await db.flush()
        await db.commit()
        await db.refresh(customer)
        log.info("oauth.github_account_created", customer_id=customer.id, github_id=github_id)
        return customer
