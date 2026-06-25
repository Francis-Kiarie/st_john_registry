import uuid
from sqlalchemy import Column, String, Enum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database import Base
from .enums import UnitStatus

class Corp(Base):
    __tablename__ = "corps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corp_code = Column(String(10), unique=True, nullable=False)  # e.g. "MM"
    region_code = Column(String(10), nullable=False)             # e.g. "RV"
    name = Column(String(100), nullable=False)
    county = Column(String(100), nullable=False)
    region = Column(String(100), nullable=False)

    # Leadership positions (stored as text — appointed separately via MemberRole)
    meeting_venue = Column(String(200))
    contact_phone = Column(String(20))
    contact_email = Column(String(100))

    status = Column(Enum(UnitStatus), default=UnitStatus.active, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    divisions = relationship("Division", back_populates="corp", cascade="all, delete-orphan")