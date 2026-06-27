from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime
from typing import Optional
from app.models.enums import DivisionType, UnitStatus

class DivisionBase(BaseModel):
    division_code: str      # e.g. "AD01" for Adult Division 01
    name: str
    type: DivisionType
    meeting_venue: Optional[str] = None
    meeting_day: Optional[str] = None
    meeting_time: Optional[str] = None
    established_date: Optional[date] = None

class DivisionCreate(DivisionBase):
    corp_id: UUID

class DivisionUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[DivisionType] = None
    meeting_venue: Optional[str] = None
    meeting_day: Optional[str] = None
    meeting_time: Optional[str] = None
    established_date: Optional[date] = None
    status: Optional[UnitStatus] = None

class DivisionResponse(DivisionBase):
    id: UUID
    corp_id: UUID
    status: UnitStatus
    created_at: datetime

    class Config:
        from_attributes = True