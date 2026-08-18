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
)
async def register(user_in: UserCreate, session: AsyncSession = Depends(get_db_session)):
    """
    Register a new user.
    """
    auth_service = AuthService(session)
    return await auth_service.register_user(user_in)


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(login_in: LoginRequest, session: AsyncSession = Depends(get_db_session)):
    """
    Authenticate a user and return a JWT access token.
    """
    auth_service = AuthService(session)
    return await auth_service.authenticate_user(login_in.email, login_in.password)


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information (Protected Endpoint).
    """
    return current_user
