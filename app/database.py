import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

# Cloud SQL on Cloud Run uses a Unix socket via pg8000
# Local dev continues to use the .env DATABASE_URL with psycopg2
DATABASE_URL = settings.DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # detects stale connections
    pool_recycle=300,         # recycle connections every 5 minutes
    pool_size=5,              # small pool for Cloud Run
    max_overflow=2,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()