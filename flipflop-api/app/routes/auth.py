import structlog
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, CustomerResponse, CustomerProfileUpdateRequest
from app.services.auth_service import signup, login, get_customer_by_token
from app.services.social_proof import record_login_event

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


async def get_current_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> object:
    """
    Dependency: extract and validate JWT token from Authorization header.
    Returns the current customer.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token = parts[1]
    customer = await get_customer_by_token(db, token)

    if not customer:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return customer


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup_endpoint(
    request: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Create a new customer account.

    **Request:**
    - `email`: Valid email address
    - `password`: Password (minimum 8 characters, or null for magic link)
    - `name`: Customer full name
    - `year_of_birth`: Optional - year of birth for age band & birthday offers
    - `marketing_opt_in`: Optional - opt-in to marketing (default false)
    - `acquisition_source`: Optional - how they found us (search/youtube/reddit/referral/ebay/other)
    - `acquisition_detail`: Optional - additional detail (e.g., referral code)

    **Response:**
    - `access_token`: JWT token for authentication
    - `token_type`: Always "bearer"
    """
    customer, access_token = await signup(
        db=db,
        email=request.email,
        name=request.name,
        password=request.password,
        year_of_birth=request.year_of_birth,
        marketing_opt_in=request.marketing_opt_in,
        acquisition_source=request.acquisition_source,
        acquisition_detail=request.acquisition_detail,
    )

    if not customer:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    return TokenResponse(access_token=access_token, token_type="bearer")


def _client_ip(http_request: Request) -> str | None:
    forwarded = http_request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return http_request.client.host if http_request.client else None


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(
    login_request: LoginRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate a customer and return access token.

    **Request:**
    - `email`: Registered email address
    - `password`: Account password

    **Response:**
    - `access_token`: JWT token for authentication
    - `token_type`: Always "bearer"
    """
    customer, access_token = await login(
        db=db,
        email=login_request.email,
        password=login_request.password,
    )

    if not customer:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    try:
        await record_login_event(
            db,
            customer_name=customer.name,
            ip=_client_ip(http_request),
        )
    except Exception as e:
        log.warning("social_proof.login_event_failed", error=str(e), customer_id=customer.id)

    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=CustomerResponse)
async def get_current_user_endpoint(
    customer: object = Depends(get_current_user),
) -> CustomerResponse:
    """
    Get current authenticated user profile.

    **Headers:**
    - `Authorization`: Bearer <access_token>

    **Response:**
    - Customer profile information (id, email, name, last_login, created_at, plus registration data)
    """
    return CustomerResponse.model_validate(customer)


@router.patch("/me", response_model=CustomerResponse)
async def update_customer_profile(
    request: CustomerProfileUpdateRequest,
    customer: object = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerResponse:
    """
    Update customer profile (progressive disclosure).
    
    **Headers:**
    - `Authorization`: Bearer <access_token>
    
    **Request:** All fields optional - only send fields you want to update
    - `name`: Update full name
    - `year_of_birth`: Year of birth for age band & birthday offers
    - `marketing_opt_in`: Marketing preference
    - `acquisition_source`: How they found us
    - `acquisition_detail`: Additional acquisition detail
    
    **Response:**
    - Updated customer profile
    """
    # Update only provided fields
    if request.name is not None:
        customer.name = request.name
    if request.year_of_birth is not None:
        customer.year_of_birth = request.year_of_birth
    if request.marketing_opt_in is not None:
        customer.marketing_opt_in = request.marketing_opt_in
    if request.acquisition_source is not None:
        customer.acquisition_source = request.acquisition_source
    if request.acquisition_detail is not None:
        customer.acquisition_detail = request.acquisition_detail
    
    customer.updated_at = datetime.now(timezone.utc)
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    
    log.info("auth.profile_updated", customer_id=customer.id)
    
    return CustomerResponse.model_validate(customer)
