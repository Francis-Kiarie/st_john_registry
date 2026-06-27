from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import extract
from uuid import UUID
from datetime import date
from typing import List

from app.database import get_db
from app.models.member import (
    Member, DutyLog, EfficiencyRecord, StatusHistory, RankAppointment
)
from app.models.division import Division
from app.models.enums import DutyType, MemberRank
from app.schemas.member import (
    MemberCreate, MemberUpdate, MemberResponse,
    DutyLogCreate, DutyLogResponse,
    EfficiencyRecordResponse, EfficiencyAssess,
    StatusChange
)
from app.utils.membership import generate_membership_number

router = APIRouter(prefix="/members", tags=["Members"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_or_404(db: Session, member_id: UUID) -> Member:
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member

def recalculate_efficiency(record: EfficiencyRecord) -> bool:
    """Returns True if member meets all five BGR annual requirements."""
    return (
        record.public_duty_hours >= 30 and
        record.community_service_hours >= 24 and
        record.divisional_meetings_attended >= 12 and
        record.first_aid_exam_passed and
        record.annual_parade_attended
    )

def get_or_create_efficiency(db: Session, member_id: UUID, year: int) -> EfficiencyRecord:
    record = db.query(EfficiencyRecord).filter(
        EfficiencyRecord.member_id == member_id,
        EfficiencyRecord.year == year
    ).first()
    if not record:
        record = EfficiencyRecord(member_id=member_id, year=year)
        db.add(record)
        db.flush()
    return record


# ── Member registration ───────────────────────────────────────────────────────

@router.post("/", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def register_member(member_in: MemberCreate, db: Session = Depends(get_db)):
    # Verify division exists and load its corp
    division = db.query(Division).filter(Division.id == member_in.division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")

    corp = division.corp
    if not corp:
        raise HTTPException(status_code=404, detail="Corp not found for this division")

    # Check for duplicate national ID
    if db.query(Member).filter(Member.id_number == member_in.id_number).first():
        raise HTTPException(
            status_code=400,
            detail=f"A member with ID number '{member_in.id_number}' already exists"
        )

    # Generate membership number before creating the member
    membership_number = generate_membership_number(
        db=db,
        region_code=corp.region_code,
        corp_code=corp.corp_code,
        division_code=division.division_code
    )

    member = Member(
        **member_in.model_dump(),
        membership_number=membership_number,
        current_rank=MemberRank.member
    )
    db.add(member)
    db.flush()  # ← assigns member.id from postgres before referencing it below

    appointment = RankAppointment(
        member_id=member.id,
        rank=MemberRank.member,
        appointed_date=member_in.enrolled_date,
        appointed_by="System — initial enrollment",
        is_current=True
    )
    db.add(appointment)

    efficiency = EfficiencyRecord(
        member_id=member.id,
        year=member_in.enrolled_date.year
    )
    db.add(efficiency)

    db.commit()
    db.refresh(member)
    return member

# ── Member queries ────────────────────────────────────────────────────────────

@router.get("/", response_model=List[MemberResponse])
def list_members(
    division_id: UUID | None = None,
    corp_id: UUID | None = None,
    status: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(Member).join(Division)
    if division_id:
        query = query.filter(Member.division_id == division_id)
    if corp_id:
        query = query.filter(Division.corp_id == corp_id)
    if status:
        query = query.filter(Member.status == status)
    return query.all()

@router.get("/{member_id}", response_model=MemberResponse)
def get_member(member_id: UUID, db: Session = Depends(get_db)):
    return get_or_404(db, member_id)

@router.patch("/{member_id}", response_model=MemberResponse)
def update_member(member_id: UUID, member_in: MemberUpdate, db: Session = Depends(get_db)):
    member = get_or_404(db, member_id)
    for field, value in member_in.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    db.commit()
    db.refresh(member)
    return member


# ── Status changes ────────────────────────────────────────────────────────────

@router.post("/{member_id}/status", response_model=MemberResponse)
def change_status(member_id: UUID, change: StatusChange, db: Session = Depends(get_db)):
    member = get_or_404(db, member_id)

    if member.status == change.new_status:
        raise HTTPException(
            status_code=400,
            detail=f"Member is already {change.new_status}"
        )

    history = StatusHistory(
        member_id=member.id,
        old_status=member.status,
        new_status=change.new_status,
        changed_date=date.today(),
        changed_by=change.changed_by,
        bgr_regulation_ref=change.bgr_regulation_ref,
        reason=change.reason
    )
    db.add(history)
    member.status = change.new_status
    db.commit()
    db.refresh(member)
    return member


# ── Duty logs ─────────────────────────────────────────────────────────────────

@router.post("/{member_id}/duties", response_model=DutyLogResponse, status_code=201)
def log_duty(member_id: UUID, duty_in: DutyLogCreate, db: Session = Depends(get_db)):
    member = get_or_404(db, member_id)

    duty = DutyLog(member_id=member.id, **duty_in.model_dump())
    db.add(duty)

    # Update the efficiency record for the duty's year
    year = duty_in.duty_date.year
    record = get_or_create_efficiency(db, member.id, year)

    if duty_in.duty_type == DutyType.public_duty:
        record.public_duty_hours = float(record.public_duty_hours or 0) + duty_in.hours
    elif duty_in.duty_type == DutyType.community_service:
        record.community_service_hours = float(record.community_service_hours or 0) + duty_in.hours
    elif duty_in.duty_type == DutyType.divisional_meeting:
        record.divisional_meetings_attended = (record.divisional_meetings_attended or 0) + 1

    record.is_efficient = recalculate_efficiency(record)
    db.commit()
    db.refresh(duty)
    return duty

@router.get("/{member_id}/duties", response_model=List[DutyLogResponse])
def list_duties(member_id: UUID, year: int | None = None, db: Session = Depends(get_db)):
    get_or_404(db, member_id)
    query = db.query(DutyLog).filter(DutyLog.member_id == member_id)
    if year:
        query = query.filter(extract("year", DutyLog.duty_date) == year)
    return query.order_by(DutyLog.duty_date.desc()).all()


# ── Annual efficiency ─────────────────────────────────────────────────────────

@router.get("/{member_id}/efficiency", response_model=List[EfficiencyRecordResponse])
def get_efficiency(member_id: UUID, db: Session = Depends(get_db)):
    get_or_404(db, member_id)
    return (
        db.query(EfficiencyRecord)
        .filter(EfficiencyRecord.member_id == member_id)
        .order_by(EfficiencyRecord.year.desc())
        .all()
    )

@router.post("/{member_id}/efficiency/assess", response_model=EfficiencyRecordResponse)
def assess_efficiency(member_id: UUID, assess: EfficiencyAssess, db: Session = Depends(get_db)):
    """
    Records exam and parade results then recalculates efficiency.
    Called once per year by the division superintendent or secretary.
    """
    get_or_404(db, member_id)
    record = get_or_create_efficiency(db, member_id, assess.year)

    record.first_aid_exam_passed = assess.first_aid_exam_passed
    record.annual_parade_attended = assess.annual_parade_attended
    record.assessed_by = assess.assessed_by
    record.assessed_date = date.today()
    record.notes = assess.notes
    record.is_efficient = recalculate_efficiency(record)

    db.commit()
    db.refresh(record)
    return record