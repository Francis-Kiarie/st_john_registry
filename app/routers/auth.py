from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.corp import Corp
from app.models.division import Division
from app.schemas.auth import UserCreate, UserResponse, TokenResponse, LoginRequest, PasswordChange
from app.utils.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_corp_admin
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    # Only a corp_admin can create new users
    _: User = Depends(require_corp_admin)
):
    # Check email uniqueness
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate scope based on role
    if user_in.role == UserRole.corp_admin:
        if not user_in.corp_id:
            raise HTTPException(status_code=400, detail="corp_id required for corp_admin role")
        if not db.query(Corp).filter(Corp.id == user_in.corp_id).first():
            raise HTTPException(status_code=404, detail="Corp not found")

    elif user_in.role in {
        UserRole.division_superintendent,
        UserRole.division_secretary,
        UserRole.viewer
    }:
        if not user_in.division_id:
            raise HTTPException(status_code=400, detail="division_id required for this role")
        if not db.query(Division).filter(Division.id == user_in.division_id).first():
            raise HTTPException(status_code=404, detail="Division not found")

    user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
        corp_id=user_in.corp_id,
        division_id=user_in.division_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(login_in: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_in.email).first()
    if not user or not verify_password(login_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token, user=user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
def change_password(
    body: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"message": "Password updated successfully"}


@router.patch("/users/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_corp_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user