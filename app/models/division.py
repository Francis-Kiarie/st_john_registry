import uuid
from sqlalchemy import Column, String, Enum, DateTime, Date, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database import Base
from .enums import DivisionType, UnitStatus

class Division(Base):
    __tablename__ = "divisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corp_id = Column(UUID(as_uuid=True), ForeignKey("corps.id"), nullable=False)

    division_code = Column(String(10), nullable=False)  # e.g. "AD01"
    name = Column(String(100), nullable=False)
    type = Column(Enum(DivisionType), nullable=False)

    meeting_venue = Column(String(200))
    meeting_day = Column(String(20))    # e.g. "Tuesday"
    meeting_time = Column(String(20))   # e.g. "18:00"
    established_date = Column(Date)

    status = Column(Enum(UnitStatus), default=UnitStatus.active, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    corp = relationship("Corp", back_populates="divisions")
    members = relationship("Member", back_populates="division", cascade="all, delete-orphan")