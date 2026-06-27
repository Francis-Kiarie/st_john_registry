from pydantic import BaseModel, EmailStr, field_validator
from uuid import UUID
from datetime import date, datetime
from typing import Optional
from app.models.enums import (
    MemberRank, SpecialistTrack, MemberStatus, DutyType, AwardCategory
)

class MemberBase(BaseModel):
    full_name: str
    id_number: str
    date_of_birth: date
    gender: str
    phone: str
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    employer_or_school: Optional[str] = None
    next_of_kin_name: Optional[str] = None
    next_of_kin_phone: Optional[str] = None
    next_of_kin_relation: Optional[str] = None
    enrolled_date: date
    specialist_track: SpecialistTrack = SpecialistTrack.none
    declaration_signed: bool = False
    medically_fit: bool = True
    registration_fee_paid_date: Optional[date] = None

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        allowed = {"male", "female", "other"}
        if v.lower() not in allowed:
            raise ValueError(f"gender must be one of {allowed}")
        return v.lower()

class MemberCreate(MemberBase):
    division_id: UUID

class MemberUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    employer_or_school: Optional[str] = None
    next_of_kin_name: Optional[str] = None
    next_of_kin_phone: Optional[str] = None
    next_of_kin_relation: Optional[str] = None
    specialist_track: Optional[SpecialistTrack] = None
    declaration_signed: Optional[bool] = None
    medically_fit: Optional[bool] = None
    registration_fee_paid_date: Optional[date] = None
    status: Optional[MemberStatus] = None

class MemberResponse(MemberBase):
    id: UUID
    division_id: UUID
    membership_number: str
    current_rank: MemberRank
    status: MemberStatus
    created_at: datetime

    class Config:
        from_attributes = True

# --- Duty log schemas ---

class DutyLogCreate(BaseModel):
    duty_date: date
    event_name: str
    location: Optional[str] = None
    duty_type: DutyType
    hours: float
    supervisor: Optional[str] = None
    notes: Optional[str] = None

class DutyLogResponse(DutyLogCreate):
    id: UUID
    member_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

# --- Efficiency record schemas ---

class EfficiencyRecordResponse(BaseModel):
    id: UUID
    member_id: UUID
    year: int
    public_duty_hours: float
    community_service_hours: float
    divisional_meetings_attended: int
    first_aid_exam_passed: bool
    annual_parade_attended: bool
    is_efficient: bool
    assessed_date: Optional[date] = None
    assessed_by: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True

class EfficiencyAssess(BaseModel):
    year: int
    first_aid_exam_passed: bool
    annual_parade_attended: bool
    assessed_by: str
    notes: Optional[str] = None

# --- Status change schema ---

class StatusChange(BaseModel):
    new_status: MemberStatus
    changed_by: str
    bgr_regulation_ref: Optional[str] = None
    reason: str