from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Current user dependency ───────────────────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    payload = decode_token(token)
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    return user


# ── Role-based access dependencies ───────────────────────────────────────────
# Use these in route handlers: current_user: User = Depends(require_corp_admin)

def require_corp_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.corp_admin:
        raise HTTPException(status_code=403, detail="Corp admin access required")
    return current_user

def require_superintendent_or_above(current_user: User = Depends(get_current_user)) -> User:
    allowed = {UserRole.corp_admin, UserRole.division_superintendent}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Superintendent or above required")
    return current_user

def require_secretary_or_above(current_user: User = Depends(get_current_user)) -> User:
    allowed = {
        UserRole.corp_admin,
        UserRole.division_superintendent,
        UserRole.division_secretary
    }
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Secretary or above required")
    return current_user

def require_any_authenticated(current_user: User = Depends(get_current_user)) -> User:
    return current_user


# ── Division scope guard ──────────────────────────────────────────────────────
# Ensures a division-level user can only access their own division

def assert_division_access(user: User, division_id: UUID):
    if user.role == UserRole.corp_admin:
        return  # corp admin sees everything
    if str(user.division_id) != str(division_id):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this division"
        )