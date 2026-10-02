from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.token import TokenResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates an account and returns the user record — **not** a token; call `POST /auth/login` next.\n\n"
    "Passwords are bcrypt-hashed and never returned. Rate limited to 10 requests per minute per client IP.",
    responses={
        409: {"description": "Email already registered"},
        422: {"description": "Invalid email, or password shorter than 8 / longer than 128 characters"},
        429: {"description": "Rate limit exceeded — see `Retry-After`"},
    },
)
async def register(user_in: UserCreate, session: AsyncSession = Depends(get_db_session)):
    auth_service = AuthService(session)
    return await auth_service.register_user(user_in)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in and get an access token",
    description="Exchanges email and password for a JWT bearer token, valid for `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` "
    "(60 by default). Send it as `Authorization: Bearer <token>` on every other endpoint.\n\n"
    "There is no refresh token: when it expires, log in again. Rate limited to 10 requests per minute per client "
    "IP, which is what throttles credential stuffing.",
    responses={
        401: {"description": "Unknown email or wrong password — deliberately not distinguished, so the response cannot confirm an account exists"},
        429: {"description": "Rate limit exceeded — see `Retry-After`"},
    },
)
async def login(login_in: LoginRequest, session: AsyncSession = Depends(get_db_session)):
    auth_service = AuthService(session)
    return await auth_service.authenticate_user(login_in.email, login_in.password)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the authenticated user",
    description="Returns the account the bearer token belongs to. Useful as a cheap token-validity check: a 401 here "
    "means the token is expired or malformed.",
    responses={401: {"description": "Missing, malformed or expired bearer token"}},
)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user
