from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.database import get_db
from app.models.division import Division
from app.models.corp import Corp
from app.schemas.division import DivisionCreate, DivisionUpdate, DivisionResponse

router = APIRouter(prefix="/divisions", tags=["Divisions"])

@router.post("/", response_model=DivisionResponse, status_code=status.HTTP_201_CREATED)
def create_division(div_in: DivisionCreate, db: Session = Depends(get_db)):
    # Verify corp exists
    corp = db.query(Corp).filter(Corp.id == div_in.corp_id).first()
    if not corp:
        raise HTTPException(status_code=404, detail="Corp not found")

    # Check division_code is unique within this corp
    existing = db.query(Division).filter(
        Division.corp_id == div_in.corp_id,
        Division.division_code == div_in.division_code.upper()
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Division code '{div_in.division_code}' already exists in this corp"
        )

    division = Division(**div_in.model_dump())
    division.division_code = division.division_code.upper()
    db.add(division)
    db.commit()
    db.refresh(division)
    return division

@router.get("/", response_model=List[DivisionResponse])
def list_divisions(corp_id: UUID | None = None, db: Session = Depends(get_db)):
    query = db.query(Division)
    if corp_id:
        query = query.filter(Division.corp_id == corp_id)
    return query.all()

@router.get("/{division_id}", response_model=DivisionResponse)
def get_division(division_id: UUID, db: Session = Depends(get_db)):
    division = db.query(Division).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")
    return division

@router.patch("/{division_id}", response_model=DivisionResponse)
def update_division(division_id: UUID, div_in: DivisionUpdate, db: Session = Depends(get_db)):
    division = db.query(Division).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")
    for field, value in div_in.model_dump(exclude_unset=True).items():
        setattr(division, field, value)
    db.commit()
    db.refresh(division)
    return division