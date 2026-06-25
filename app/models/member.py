import uuid
from sqlalchemy import (
    Column, String, Enum, DateTime, Date,
    Boolean, Numeric, Integer, Text, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database import Base
from .enums import (
    MemberRank, SpecialistTrack, MemberStatus,
    DutyType, AwardCategory
)

class Member(Base):
    __tablename__ = "members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    division_id = Column(UUID(as_uuid=True), ForeignKey("divisions.id"), nullable=False)

    # Membership number: {REGION_CODE}-{CORP_CODE}-{DIV_CODE}-{SEQ}
    # e.g. RV-MM-AD01-0042
    membership_number = Column(String(30), unique=True, nullable=False)

    # Personal details
    full_name = Column(String(150), nullable=False)
    id_number = Column(String(20), unique=True, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(10), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(100))
    address = Column(String(200))
    employer_or_school = Column(String(150))

    # Next of kin
    next_of_kin_name = Column(String(150))
    next_of_kin_phone = Column(String(20))
    next_of_kin_relation = Column(String(50))

    # St. John specifics
    enrolled_date = Column(Date, nullable=False)
    current_rank = Column(Enum(MemberRank), default=MemberRank.member, nullable=False)
    specialist_track = Column(Enum(SpecialistTrack), default=SpecialistTrack.none, nullable=False)
    declaration_signed = Column(Boolean, default=False, nullable=False)
    medically_fit = Column(Boolean, default=True, nullable=False)
    registration_fee_paid_date = Column(Date)
    photo_url = Column(String(300))

    status = Column(Enum(MemberStatus), default=MemberStatus.active, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    division = relationship("Division", back_populates="members")
    rank_appointments = relationship("RankAppointment", back_populates="member", cascade="all, delete-orphan")
    efficiency_records = relationship("EfficiencyRecord", back_populates="member", cascade="all, delete-orphan")
    duty_logs = relationship("DutyLog", back_populates="member", cascade="all, delete-orphan")
    award_records = relationship("AwardRecord", back_populates="member", cascade="all, delete-orphan")
    status_history = relationship("StatusHistory", back_populates="member", cascade="all, delete-orphan")


class RankAppointment(Base):
    __tablename__ = "rank_appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    rank = Column(Enum(MemberRank), nullable=False)
    specialist_rank = Column(Enum(SpecialistTrack), default=SpecialistTrack.none)
    appointed_date = Column(Date, nullable=False)
    vacated_date = Column(Date)
    appointed_by = Column(String(150))
    authorization_ref = Column(String(100))  # BGR regulation or letter ref
    is_current = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    member = relationship("Member", back_populates="rank_appointments")


class EfficiencyRecord(Base):
    __tablename__ = "efficiency_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    year = Column(Integer, nullable=False)

    # BGR annual requirements
    public_duty_hours = Column(Numeric(5, 1), default=0)      # target: ≥ 30
    community_service_hours = Column(Numeric(5, 1), default=0) # target: ≥ 24
    divisional_meetings_attended = Column(Integer, default=0)  # target: ≥ 12
    first_aid_exam_passed = Column(Boolean, default=False)
    annual_parade_attended = Column(Boolean, default=False)

    # Computed field — set True when all five requirements met
    is_efficient = Column(Boolean, default=False)

    assessed_date = Column(Date)
    assessed_by = Column(String(150))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    member = relationship("Member", back_populates="efficiency_records")


class DutyLog(Base):
    __tablename__ = "duty_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    duty_date = Column(Date, nullable=False)
    event_name = Column(String(200), nullable=False)
    location = Column(String(200))
    duty_type = Column(Enum(DutyType), nullable=False)
    hours = Column(Numeric(4, 1), nullable=False)
    supervisor = Column(String(150))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    member = relationship("Member", back_populates="duty_logs")


class AwardRecord(Base):
    __tablename__ = "award_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    award_name = Column(String(200), nullable=False)
    award_category = Column(Enum(AwardCategory), nullable=False)
    awarded_date = Column(Date, nullable=False)
    awarded_by = Column(String(150))
    certificate_number = Column(String(100))
    citation = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    member = relationship("Member", back_populates="award_records")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    old_status = Column(Enum(MemberStatus), nullable=False)
    new_status = Column(Enum(MemberStatus), nullable=False)
    changed_date = Column(Date, nullable=False)
    changed_by = Column(String(150), nullable=False)
    bgr_regulation_ref = Column(String(100))  # e.g. "BGR Reg. 14(b)"
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    member = relationship("Member", back_populates="status_history")