import structlog
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.customer import Customer

log = structlog.get_logger(__name__)

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def hash_password(password: str) -> str:
    """Hash a plain text password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(customer_id: int) -> str:
    """
    Create a JWT access token with expiration.
    Token expires in 168 hours (1 week).
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.jwt_expiration_hours)

    payload = {
        "sub": str(customer_id),
        "iat": now,
        "exp": expires_at,
    }

    token = jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm
    )
    log.debug("auth.token_created", customer_id=customer_id, expires_at=expires_at.isoformat())
    return token


def verify_token(token: str) -> int | None:
    """
    Verify and decode a JWT token.
    Returns customer_id if valid, None if invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        customer_id_str = payload.get("sub")
        if customer_id_str is None:
            log.warning("auth.token_verify_failed", reason="missing_sub")
            return None
        return int(customer_id_str)
    except JWTError as e:
        log.warning("auth.token_verify_failed", error=str(e))
        return None
    except Exception as e:
        log.error("auth.token_verify_error", error=str(e))
        return None


async def signup(
    db: AsyncSession,
    email: str,
    password: str,
    name: str,
) -> tuple[Customer, str] | tuple[None, None]:
    """
    Create a new customer account.
    Returns (customer, access_token) on success, (None, None) if email already exists.
    """
    # Check if email already exists
    result = await db.execute(
        select(Customer).where(Customer.email == email.lower())
    )
    existing = result.scalar_one_or_none()

    if existing:
        log.warning("auth.signup_failed", reason="email_already_exists", email=email)
        return None, None

    # Create new customer
    password_hash = hash_password(password)
    customer = Customer(
        email=email.lower(),
        password_hash=password_hash,
        name=name,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(customer)
    await db.flush()  # Get the ID without committing yet

    # Generate token
    access_token = create_access_token(customer.id)

    await db.commit()
    log.info("auth.signup_success", customer_id=customer.id, email=email)

    return customer, access_token


async def login(
    db: AsyncSession,
    email: str,
    password: str,
) -> tuple[Customer, str] | tuple[None, None]:
    """
    Authenticate a customer and return access token.
    Returns (customer, access_token) on success, (None, None) if credentials invalid.
    """
    # Find customer by email
    result = await db.execute(
        select(Customer).where(Customer.email == email.lower())
    )
    customer = result.scalar_one_or_none()

    if not customer:
        log.warning("auth.login_failed", reason="customer_not_found", email=email)
        return None, None

    # Verify password
    if not verify_password(password, customer.password_hash):
        log.warning("auth.login_failed", reason="invalid_password", email=email)
        return None, None

    # Update last_login
    customer.last_login = datetime.now(timezone.utc)
    customer.updated_at = datetime.now(timezone.utc)
    db.add(customer)

    # Generate token
    access_token = create_access_token(customer.id)

    await db.commit()
    log.info("auth.login_success", customer_id=customer.id, email=email)

    return customer, access_token


async def get_customer_by_token(
    db: AsyncSession,
    token: str,
) -> Customer | None:
    """
    Get customer from a valid JWT token.
    Returns Customer if valid, None if invalid or not found.
    """
    customer_id = verify_token(token)
    if customer_id is None:
        return None

    result = await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        log.warning("auth.customer_not_found", customer_id=customer_id)
        return None

    return customer
