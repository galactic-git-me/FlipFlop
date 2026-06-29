import structlog
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, CustomerResponse
from app.services.auth_service import signup, login, get_customer_by_token

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
    - `password`: Password (minimum 8 characters)
    - `name`: Customer full name

    **Response:**
    - `access_token`: JWT token for authentication
    - `token_type`: Always "bearer"
    """
    customer, access_token = await signup(
        db=db,
        email=request.email,
        password=request.password,
        name=request.name,
    )

    if not customer:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    return TokenResponse(access_token=access_token, token_type="bearer")


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(
    request: LoginRequest,
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
        email=request.email,
        password=request.password,
    )

    if not customer:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

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
    - Customer profile information (id, email, name, last_login, created_at)
    """
    return CustomerResponse.model_validate(customer)
