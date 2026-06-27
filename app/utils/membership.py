from sqlalchemy.orm import Session
from sqlalchemy import text

def generate_membership_number(
    db: Session,
    region_code: str,
    corp_code: str,
    division_code: str
) -> str:
    """
    Generates the next membership number for a division.
    Format: {REGION_CODE}-{CORP_CODE}-{DIV_CODE}-{SEQ:04d}
    Example: RV-MM-AD01-0042

    The sequence is per-division — each division has its own counter.
    """
    # Count existing members in this division to get next sequence
    result = db.execute(
        text("""
            SELECT COUNT(*) FROM members m
            JOIN divisions d ON m.division_id = d.id
            JOIN corps c ON d.corp_id = c.id
            WHERE c.region_code = :region_code
              AND c.corp_code = :corp_code
              AND d.division_code = :division_code
        """),
        {
            "region_code": region_code.upper(),
            "corp_code": corp_code.upper(),
            "division_code": division_code.upper()
        }
    ).scalar()

    next_seq = (result or 0) + 1

    return (
        f"{region_code.upper()}-"
        f"{corp_code.upper()}-"
        f"{division_code.upper()}-"
        f"{next_seq:04d}"
    )