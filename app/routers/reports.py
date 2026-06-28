from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from uuid import UUID
from datetime import date
from typing import List
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.member import Member, EfficiencyRecord
from app.models.division import Division
from app.models.corp import Corp
from app.models.enums import MemberStatus, MemberRank, DivisionType
from app.models.user import User
from app.utils.auth import require_any_authenticated, require_secretary_or_above

router = APIRouter(prefix="/reports", tags=["Reports"])


# ── Report schemas (response shapes) ─────────────────────────────────────────

class MemberRollEntry(BaseModel):
    membership_number: str
    full_name: str
    current_rank: MemberRank
    specialist_track: str
    phone: str
    email: Optional[str]
    enrolled_date: date
    status: MemberStatus

    class Config:
        from_attributes = True

class DivisionRollReport(BaseModel):
    generated_on: date
    division_name: str
    division_code: str
    division_type: DivisionType
    corp_name: str
    total_members: int
    active_members: int
    members: List[MemberRollEntry]

class MemberEfficiencySummary(BaseModel):
    membership_number: str
    full_name: str
    current_rank: MemberRank
    public_duty_hours: float
    community_service_hours: float
    divisional_meetings_attended: int
    first_aid_exam_passed: bool
    annual_parade_attended: bool
    is_efficient: bool

class DivisionEfficiencyReport(BaseModel):
    generated_on: date
    division_name: str
    year: int
    total_assessed: int
    total_efficient: int
    efficiency_rate_percent: float
    members: List[MemberEfficiencySummary]

class DivisionSummary(BaseModel):
    division_name: str
    division_code: str
    division_type: str
    total_members: int
    active_members: int
    efficient_members: int
    efficiency_rate_percent: float

class CorpReturnReport(BaseModel):
    generated_on: date
    corp_name: str
    corp_code: str
    region: str
    county: str
    year: int
    total_divisions: int
    total_members: int
    total_active: int
    total_efficient: int
    overall_efficiency_rate_percent: float
    divisions: List[DivisionSummary]


# ── Division membership roll ───────────────────────────────────────────────────

@router.get("/division/{division_id}/roll", response_model=DivisionRollReport)
def division_membership_roll(
    division_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_authenticated)
):
    """
    Full membership roll for a division.
    Lists all members sorted by rank then name.
    Used for parades, inspections, and record-keeping.
    """
    division = db.query(Division).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")

    corp = division.corp

    # Scope check
    from app.models.user import UserRole
    if current_user.role != UserRole.corp_admin:
        if str(current_user.division_id) != str(division_id):
            raise HTTPException(status_code=403, detail="Access denied")

    # Fetch members ordered by rank ladder position then name
    rank_order = case(
        {
            MemberRank.div_superintendent: 1,
            MemberRank.div_officer: 2,
            MemberRank.acting_div_officer: 3,
            MemberRank.sergeant: 4,
            MemberRank.corporal: 5,
            MemberRank.member: 6,
        },
        value=Member.current_rank,
        else_=7
    )

    members = (
        db.query(Member)
        .filter(Member.division_id == division_id)
        .order_by(rank_order, Member.full_name)
        .all()
    )

    active = [m for m in members if m.status == MemberStatus.active]

    return DivisionRollReport(
        generated_on=date.today(),
        division_name=division.name,
        division_code=division.division_code,
        division_type=division.type,
        corp_name=corp.name,
        total_members=len(members),
        active_members=len(active),
        members=members
    )


# ── Division efficiency report ────────────────────────────────────────────────

@router.get("/division/{division_id}/efficiency", response_model=DivisionEfficiencyReport)
def division_efficiency_report(
    division_id: UUID,
    year: int = date.today().year,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_authenticated)
):
    """
    Annual efficiency report for a division.
    Shows each member's progress against the five BGR requirements.
    """
    division = db.query(Division).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")

    from app.models.user import UserRole
    if current_user.role != UserRole.corp_admin:
        if str(current_user.division_id) != str(division_id):
            raise HTTPException(status_code=403, detail="Access denied")

    # Join members with their efficiency record for the requested year
    results = (
        db.query(Member, EfficiencyRecord)
        .outerjoin(
            EfficiencyRecord,
            (EfficiencyRecord.member_id == Member.id) &
            (EfficiencyRecord.year == year)
        )
        .filter(
            Member.division_id == division_id,
            Member.status == MemberStatus.active
        )
        .order_by(Member.full_name)
        .all()
    )

    summaries = []
    for member, eff in results:
        summaries.append(MemberEfficiencySummary(
            membership_number=member.membership_number,
            full_name=member.full_name,
            current_rank=member.current_rank,
            public_duty_hours=float(eff.public_duty_hours) if eff else 0.0,
            community_service_hours=float(eff.community_service_hours) if eff else 0.0,
            divisional_meetings_attended=eff.divisional_meetings_attended if eff else 0,
            first_aid_exam_passed=eff.first_aid_exam_passed if eff else False,
            annual_parade_attended=eff.annual_parade_attended if eff else False,
            is_efficient=eff.is_efficient if eff else False,
        ))

    total = len(summaries)
    efficient = sum(1 for s in summaries if s.is_efficient)

    return DivisionEfficiencyReport(
        generated_on=date.today(),
        division_name=division.name,
        year=year,
        total_assessed=total,
        total_efficient=efficient,
        efficiency_rate_percent=round((efficient / total * 100), 1) if total else 0.0,
        members=summaries
    )


# ── Corp return report ────────────────────────────────────────────────────────

@router.get("/corp/{corp_id}/return", response_model=CorpReturnReport)
def corp_return_report(
    corp_id: UUID,
    year: int = date.today().year,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_authenticated)
):
    """
    Corp-wide membership return.
    Aggregates all divisions — total members, active members,
    and efficiency per division.
    Submitted to county level per BGR requirements.
    """
    corp = db.query(Corp).filter(Corp.id == corp_id).first()
    if not corp:
        raise HTTPException(status_code=404, detail="Corp not found")

    from app.models.user import UserRole
    if current_user.role != UserRole.corp_admin:
        raise HTTPException(status_code=403, detail="Corp admin access required")

    divisions = (
        db.query(Division)
        .filter(Division.corp_id == corp_id)
        .order_by(Division.division_code)
        .all()
    )

    division_summaries = []
    corp_total = corp_active = corp_efficient = 0

    for div in divisions:
        # Total and active members per division
        all_members = (
            db.query(Member)
            .filter(Member.division_id == div.id)
            .all()
        )
        active_members = [m for m in all_members if m.status == MemberStatus.active]

        # Efficiency count for the year
        efficient_count = (
            db.query(EfficiencyRecord)
            .filter(
                EfficiencyRecord.year == year,
                EfficiencyRecord.is_efficient == True,
                EfficiencyRecord.member_id.in_([m.id for m in active_members])
            )
            .count()
        )

        active_count = len(active_members)
        efficiency_rate = round(
            (efficient_count / active_count * 100), 1
        ) if active_count else 0.0

        division_summaries.append(DivisionSummary(
            division_name=div.name,
            division_code=div.division_code,
            division_type=div.type,
            total_members=len(all_members),
            active_members=active_count,
            efficient_members=efficient_count,
            efficiency_rate_percent=efficiency_rate,
        ))

        corp_total += len(all_members)
        corp_active += active_count
        corp_efficient += efficient_count

    overall_rate = round(
        (corp_efficient / corp_active * 100), 1
    ) if corp_active else 0.0

    return CorpReturnReport(
        generated_on=date.today(),
        corp_name=corp.name,
        corp_code=corp.corp_code,
        region=corp.region,
        county=corp.county,
        year=year,
        total_divisions=len(divisions),
        total_members=corp_total,
        total_active=corp_active,
        total_efficient=corp_efficient,
        overall_efficiency_rate_percent=overall_rate,
        divisions=division_summaries
    )


# ── Member profile report ─────────────────────────────────────────────────────

@router.get("/member/{member_id}/profile")
def member_profile_report(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_authenticated)
):
    """
    Full profile for a single member — personal details,
    rank history, all efficiency records, awards, and duty summary.
    Used for member cards and service records.
    """
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    division = member.division
    corp = division.corp

    # Duty totals
    from app.models.member import DutyLog
    from sqlalchemy import func as sqlfunc
    duty_totals = (
        db.query(
            DutyLog.duty_type,
            sqlfunc.sum(DutyLog.hours).label("total_hours"),
            sqlfunc.count(DutyLog.id).label("total_entries")
        )
        .filter(DutyLog.member_id == member_id)
        .group_by(DutyLog.duty_type)
        .all()
    )

    return {
        "generated_on": date.today().isoformat(),
        "member": {
            "membership_number": member.membership_number,
            "full_name": member.full_name,
            "id_number": member.id_number,
            "date_of_birth": member.date_of_birth.isoformat(),
            "gender": member.gender,
            "phone": member.phone,
            "email": member.email,
            "address": member.address,
            "employer_or_school": member.employer_or_school,
            "next_of_kin_name": member.next_of_kin_name,
            "next_of_kin_phone": member.next_of_kin_phone,
            "next_of_kin_relation": member.next_of_kin_relation,
            "enrolled_date": member.enrolled_date.isoformat(),
            "current_rank": member.current_rank,
            "specialist_track": member.specialist_track,
            "declaration_signed": member.declaration_signed,
            "medically_fit": member.medically_fit,
            "status": member.status,
            "photo_url": member.photo_url,
        },
        "division": {
            "name": division.name,
            "division_code": division.division_code,
            "type": division.type,
        },
        "corp": {
            "name": corp.name,
            "corp_code": corp.corp_code,
            "region": corp.region,
        },
        "rank_history": [
            {
                "rank": r.rank,
                "specialist_rank": r.specialist_rank,
                "appointed_date": r.appointed_date.isoformat(),
                "vacated_date": r.vacated_date.isoformat() if r.vacated_date else None,
                "appointed_by": r.appointed_by,
                "authorization_ref": r.authorization_ref,
                "is_current": r.is_current,
            }
            for r in sorted(member.rank_appointments, key=lambda x: x.appointed_date)
        ],
        "efficiency_records": [
            {
                "year": e.year,
                "public_duty_hours": float(e.public_duty_hours),
                "community_service_hours": float(e.community_service_hours),
                "divisional_meetings_attended": e.divisional_meetings_attended,
                "first_aid_exam_passed": e.first_aid_exam_passed,
                "annual_parade_attended": e.annual_parade_attended,
                "is_efficient": e.is_efficient,
            }
            for e in sorted(member.efficiency_records, key=lambda x: x.year, reverse=True)
        ],
        "awards": [
            {
                "award_name": a.award_name,
                "category": a.award_category,
                "awarded_date": a.awarded_date.isoformat(),
                "awarded_by": a.awarded_by,
                "certificate_number": a.certificate_number,
            }
            for a in member.award_records
        ],
        "duty_summary": [
            {
                "duty_type": row.duty_type,
                "total_hours": float(row.total_hours),
                "total_entries": row.total_entries,
            }
            for row in duty_totals
        ],
    }