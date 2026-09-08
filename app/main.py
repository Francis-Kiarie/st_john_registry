import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.routers import corps, divisions, members, auth, reports

bearer_scheme = HTTPBearer()

app = FastAPI(
    title="St. John Kenya – Member Registry",
    description="Corp and Division member registration and tracking system",
    version="1.0.0"
)

# Read allowed origins from environment variable
# In production: set via Cloud Run env var
# In development: defaults to localhost
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:8081"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Only mount local static files in development
if not os.getenv("GCS_BUCKET_NAME"):
    Path("uploads/members").mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router)
app.include_router(corps.router)
app.include_router(divisions.router)
app.include_router(members.router)
app.include_router(reports.router)

@app.get("/")
def root():
    return {"message": "St. John Kenya Registry API", "docs": "/docs"}