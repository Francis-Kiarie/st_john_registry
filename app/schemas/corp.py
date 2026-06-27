from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.models.enums import UnitStatus

class CorpBase(BaseModel):
    corp_code: str          # e.g. "MM" for Maai Mahiu
    region_code: str        # e.g. "RV" for Rift Valley
    name: str
    county: str
    region: str
    meeting_venue: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None

class CorpCreate(CorpBase):
    pass

class CorpUpdate(BaseModel):
    name: Optional[str] = None
    county: Optional[str] = None
    region: Optional[str] = None
    meeting_venue: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    status: Optional[UnitStatus] = None

class CorpResponse(CorpBase):
    id: UUID
    status: UnitStatus
    created_at: datetime

    class Config:
        from_attributes = True