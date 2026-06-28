from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer
from pathlib import Path
from app.routers import corps, divisions, members, auth, reports


bearer_scheme = HTTPBearer()

app = FastAPI(
    title="St. John Kenya – Member Registry",
    description="Corp and Division member registration and tracking system",
    version="1.0.0"
)

# Serve uploaded photos as static files
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