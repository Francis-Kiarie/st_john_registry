import uuid
from sqlalchemy import Column, String, Enum, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database import Base
import enum

class UserRole(str, enum.Enum):
    corp_admin = "corp_admin"               # full access to all divisions in a corp
    division_superintendent = "division_superintendent"  # full access to own division
    division_secretary = "division_secretary"            # data entry for own division
    viewer = "viewer"                       # read-only

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # A user is scoped to either a corp or a division
    corp_id = Column(UUID(as_uuid=True), ForeignKey("corps.id"), nullable=True)
    division_id = Column(UUID(as_uuid=True), ForeignKey("divisions.id"), nullable=True)

    full_name = Column(String(150), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    corp = relationship("Corp", foreign_keys=[corp_id])
    division = relationship("Division", foreign_keys=[division_id])