from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional
from app.models.user import UserRole

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: UserRole
    corp_id: Optional[UUID] = None      # required for corp_admin
    division_id: Optional[UUID] = None  # required for division roles

class UserResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    role: UserRole
    corp_id: Optional[UUID] = None
    division_id: Optional[UUID] = None
    is_active: bool

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str