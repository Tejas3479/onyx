"""Onyx Authentication API — thin JWT login for procurement officers."""

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import select

from database import User, async_session_maker
from models import TokenResponse, UserCreate, UserLogin, UserResponse

logger = logging.getLogger("onyx.auth_routes")

router = APIRouter(prefix="/auth", tags=["auth"])

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "onyx-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))  # 8 hours

# Password hashing
password_hash = PasswordHash((Argon2Hasher(),))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _create_token(user_id: str, email: str) -> str:
    """Create a JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str) -> User | None:
    """Validate JWT token and return the user. Returns None if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
    except jwt.exceptions.PyJWTError:
        return None

    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        return user


@router.post("/register", response_model=UserResponse)
async def register(req: UserCreate):
    """Register a new user account."""
    async with async_session_maker() as session:
        # Check if email already exists
        stmt = select(User).where(User.email == req.email)
        result = await session.execute(stmt)
        existing = result.scalars().first()

        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        user = User(
            name=req.name,
            email=req.email,
            hashed_password=password_hash.hash(req.password),
            department=req.department,
            organization=req.organization,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        logger.info("New user registered: %s (%s)", user.name, user.email)

        return UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            department=user.department,
            organization=user.organization,
            role=user.role,
        )


@router.post("/login", response_model=TokenResponse)
async def login(req: UserLogin):
    """Authenticate and return a JWT token."""
    async with async_session_maker() as session:
        stmt = select(User).where(User.email == req.email)
        result = await session.execute(stmt)
        user = result.scalars().first()

    if not user or not password_hash.verify(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_token(user.id, user.email)
    logger.info("User logged in: %s", user.email)

    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(token: str = Depends(oauth2_scheme)):
    """Get current user profile. Requires Authorization header."""
    user = await get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
        
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        department=user.department,
        organization=user.organization,
        role=user.role,
    )
