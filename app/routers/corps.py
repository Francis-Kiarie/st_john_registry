from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.database import get_db
from app.models.corp import Corp
from app.schemas.corp import CorpCreate, CorpUpdate, CorpResponse

router = APIRouter(prefix="/corps", tags=["Corps"])

@router.post("/", response_model=CorpResponse, status_code=status.HTTP_201_CREATED)
def create_corp(corp_in: CorpCreate, db: Session = Depends(get_db)):
    # Check for duplicate corp_code
    existing = db.query(Corp).filter(Corp.corp_code == corp_in.corp_code.upper()).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Corp with code '{corp_in.corp_code}' already exists"
        )
    corp = Corp(**corp_in.model_dump())
    corp.corp_code = corp.corp_code.upper()
    corp.region_code = corp.region_code.upper()
    db.add(corp)
    db.commit()
    db.refresh(corp)
    return corp

@router.get("/", response_model=List[CorpResponse])
def list_corps(db: Session = Depends(get_db)):
    return db.query(Corp).all()

@router.get("/{corp_id}", response_model=CorpResponse)
def get_corp(corp_id: UUID, db: Session = Depends(get_db)):
    corp = db.query(Corp).filter(Corp.id == corp_id).first()
    if not corp:
        raise HTTPException(status_code=404, detail="Corp not found")
    return corp

@router.patch("/{corp_id}", response_model=CorpResponse)
def update_corp(corp_id: UUID, corp_in: CorpUpdate, db: Session = Depends(get_db)):
    corp = db.query(Corp).filter(Corp.id == corp_id).first()
    if not corp:
        raise HTTPException(status_code=404, detail="Corp not found")
    for field, value in corp_in.model_dump(exclude_unset=True).items():
        setattr(corp, field, value)
    db.commit()
    db.refresh(corp)
    return corp