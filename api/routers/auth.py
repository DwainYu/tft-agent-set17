from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from api.models.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserInfo,
)
from api.services.auth_service import AuthService
from api.database import get_db
from api.core.security import decode_token

router = APIRouter(prefix="/auth", tags=["auth"])

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Dependency: extract and verify user from JWT Bearer token."""
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ------------------------------------------------------------------ routes


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest):
    """Register a new user and return tokens."""
    with get_db() as conn:
        svc = AuthService(conn)
        try:
            user = svc.register(body.phone, body.password, body.sms_code)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            )
        return svc.create_tokens(user["id"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Authenticate user and return tokens."""
    with get_db() as conn:
        svc = AuthService(conn)
        user = svc.verify_password(body.phone, body.password or "")
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid phone or password",
            )
        return svc.create_tokens(user["id"])


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: dict):
    """Refresh access token using a valid refresh token."""
    refresh_token = body.get("refresh_token", "")
    with get_db() as conn:
        svc = AuthService(conn)
        try:
            return svc.refresh_access_token(refresh_token)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
            )


@router.get("/me", response_model=UserInfo)
async def me(user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's info."""
    with get_db() as conn:
        svc = AuthService(conn)
        info = svc.get_user_by_id(user["sub"])
        if info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
    return info
