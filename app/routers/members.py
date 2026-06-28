from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import extract, or_
from uuid import UUID
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from app.utils.photos import save_member_photo, delete_member_photo
from app.models.user import User
from app.utils.auth import require_secretary_or_above, require_superintendent_or_above, require_any_authenticated, assert_division_access

from app.database import get_db
from app.models.member import (
    Member, DutyLog, EfficiencyRecord, StatusHistory, RankAppointment, AwardRecord
)
from app.models.division import Division
from app.models.enums import DutyType, MemberRank, SpecialistTrack
from app.schemas.member import (
    MemberCreate, MemberUpdate, MemberResponse,PaginatedMembers,
    DutyLogCreate, DutyLogResponse,
    EfficiencyRecordResponse, EfficiencyAssess,
    StatusChange, RankPromotion, RankAppointmentResponse,AwardCreate, AwardResponse,StatusHistoryResponse
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


@router.get("/", response_model=PaginatedMembers)
def list_members(
    division_id: UUID | None = None,
    corp_id: UUID | None = None,
    status: str | None = None,
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_authenticated)
):
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be 1 or greater")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")

    query = db.query(Member).join(Division)

    # Scope enforcement
    from app.models.user import UserRole
    if current_user.role == UserRole.corp_admin:
        query = query.filter(Division.corp_id == current_user.corp_id)
    else:
        query = query.filter(Member.division_id == current_user.division_id)

    # Optional filters
    if division_id:
        query = query.filter(Member.division_id == division_id)
    if corp_id:
        query = query.filter(Division.corp_id == corp_id)
    if status:
        query = query.filter(Member.status == status)

    total = query.count()
    members = (
        query
        .order_by(Member.full_name)
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return PaginatedMembers(
        total=total,
        page=page,
        limit=limit,
        pages=-(-total // limit),
        results=members
    )

# ── Search ────────────────────────────────────────────────────────────────────

@router.get("/search", response_model=List[MemberResponse])
def search_members(
    q: str,                                 # search term
    corp_id: UUID | None = None,            # narrow to a corp
    division_id: UUID | None = None,        # narrow to a division
    status: str | None = None,              # filter by status
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_authenticated)
):
    """
    Search members by:
    - Full name (partial, case-insensitive)
    - ID number (exact or partial)
    - Membership number (exact or partial)
    - Phone number (partial)

    Scope is automatically enforced:
    - Corp admin sees all members in their corp
    - Division roles see only their division
    """
    if len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Search term must be at least 2 characters")

    query = db.query(Member).join(Division)

    # Enforce scope based on user role
    from app.models.user import UserRole
    if current_user.role == UserRole.corp_admin:
        query = query.filter(Division.corp_id == current_user.corp_id)
    else:
        query = query.filter(Member.division_id == current_user.division_id)

    # Apply additional filters if provided
    if corp_id:
        query = query.filter(Division.corp_id == corp_id)
    if division_id:
        query = query.filter(Member.division_id == division_id)
    if status:
        query = query.filter(Member.status == status)

    # Search across four fields
    search_term = f"%{q.strip()}%"
    query = query.filter(
        or_(
            Member.full_name.ilike(search_term),
            Member.id_number.ilike(search_term),
            Member.membership_number.ilike(search_term),
            Member.phone.ilike(search_term),
        )
    )

    results = query.order_by(Member.full_name).limit(50).all()

    if not results:
        raise HTTPException(status_code=404, detail="No members found matching your search")

    return results

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

# ── Photo upload ──────────────────────────────────────────────────────────────

@router.post("/{member_id}/photo", response_model=MemberResponse)
async def upload_photo(
    member_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_secretary_or_above)
):
    member = get_or_404(db, member_id)

    # Enforce division scope
    assert_division_access(current_user, member.division_id)

    # Delete old photo if one exists
    if member.photo_url:
        delete_member_photo(member.photo_url)

    # Save new photo
    photo_url = await save_member_photo(file, str(member_id))
    member.photo_url = photo_url

    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}/photo", response_model=MemberResponse)
def delete_photo(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_secretary_or_above)
):
    member = get_or_404(db, member_id)
    assert_division_access(current_user, member.division_id)

    if member.photo_url:
        delete_member_photo(member.photo_url)
        member.photo_url = None
        db.commit()
        db.refresh(member)

    return member

# ── Rank promotion ────────────────────────────────────────────────────────────

# BGR rank ladder — promotion must follow this order
RANK_LADDER = [
    MemberRank.member,
    MemberRank.corporal,
    MemberRank.sergeant,
    MemberRank.acting_div_officer,
    MemberRank.div_officer,
    MemberRank.div_superintendent,
]

@router.post("/{member_id}/rank", response_model=RankAppointmentResponse)
def promote_member(
    member_id: UUID,
    promotion: RankPromotion,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superintendent_or_above)
):
    """
    Promotes a member to a new rank.
    - Validates promotion follows the BGR ladder (no skipping ranks)
    - Closes the current rank appointment
    - Opens a new rank appointment
    - Updates member.current_rank
    """
    member = get_or_404(db, member_id)
    assert_division_access(current_user, member.division_id)

    # Validate the promotion follows the ladder
    current_index = RANK_LADDER.index(member.current_rank)
    new_index = RANK_LADDER.index(promotion.new_rank)

    if new_index <= current_index:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot promote to {promotion.new_rank}. "
                f"Member is already at {member.current_rank}. "
                f"Next valid rank is {RANK_LADDER[current_index + 1] if current_index + 1 < len(RANK_LADDER) else 'none — already at highest rank'}."
            )
        )

    if new_index > current_index + 1:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot skip ranks. "
                f"Member must be promoted to "
                f"{RANK_LADDER[current_index + 1]} before {promotion.new_rank}."
            )
        )

    # Close current rank appointment
    current_appointment = db.query(RankAppointment).filter(
        RankAppointment.member_id == member_id,
        RankAppointment.is_current == True
    ).first()

    if current_appointment:
        current_appointment.is_current = False
        current_appointment.vacated_date = promotion.appointed_date

    # Create new rank appointment
    new_appointment = RankAppointment(
        member_id=member.id,
        rank=promotion.new_rank,
        specialist_rank=promotion.specialist_rank,
        appointed_date=promotion.appointed_date,
        appointed_by=promotion.appointed_by,
        authorization_ref=promotion.authorization_ref,
        is_current=True
    )
    db.add(new_appointment)

    # Update member's current rank
    member.current_rank = promotion.new_rank
    if promotion.specialist_rank != SpecialistTrack.none:
        member.specialist_track = promotion.specialist_track

    db.commit()
    db.refresh(new_appointment)
    return new_appointment


@router.get("/{member_id}/rank/history", response_model=List[RankAppointmentResponse])
def get_rank_history(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_authenticated)
):
    get_or_404(db, member_id)
    return (
        db.query(RankAppointment)
        .filter(RankAppointment.member_id == member_id)
        .order_by(RankAppointment.appointed_date.desc())
        .all()
    )

# ── Awards ────────────────────────────────────────────────────────────────────

@router.post("/{member_id}/awards", response_model=AwardResponse, status_code=201)
def add_award(
    member_id: UUID,
    award_in: AwardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_secretary_or_above)
):
    """
    Record an award or honour for a member.
    Categories per BGR page 20: meritorious, bravery, service,
    donation, program, state_honour, divisional.
    """
    member = get_or_404(db, member_id)
    assert_division_access(current_user, member.division_id)

    award = AwardRecord(member_id=member.id, **award_in.model_dump())
    db.add(award)
    db.commit()
    db.refresh(award)
    return award


@router.get("/{member_id}/awards", response_model=List[AwardResponse])
def list_awards(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_authenticated)
):
    get_or_404(db, member_id)
    return (
        db.query(AwardRecord)
        .filter(AwardRecord.member_id == member_id)
        .order_by(AwardRecord.awarded_date.desc())
        .all()
    )


@router.delete("/{member_id}/awards/{award_id}", status_code=204)
def delete_award(
    member_id: UUID,
    award_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superintendent_or_above)
):
    """Remove an incorrectly recorded award — superintendent or above only."""
    member = get_or_404(db, member_id)
    assert_division_access(current_user, member.division_id)

    award = db.query(AwardRecord).filter(
        AwardRecord.id == award_id,
        AwardRecord.member_id == member_id
    ).first()
    if not award:
        raise HTTPException(status_code=404, detail="Award not found")

    db.delete(award)
    db.commit()

# ── Status history ────────────────────────────────────────────────────────────

@router.get("/{member_id}/status/history", response_model=List[StatusHistoryResponse])
def get_status_history(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_authenticated)
):
    """
    Full audit trail of status changes for a member.
    Every suspension, discharge, transfer, and reinstatement
    is recorded here with the reason and BGR regulation cited.
    """
    get_or_404(db, member_id)
    return (
        db.query(StatusHistory)
        .filter(StatusHistory.member_id == member_id)
        .order_by(StatusHistory.changed_date.desc())
        .all()
    )