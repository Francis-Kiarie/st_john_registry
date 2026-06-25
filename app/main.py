from fastapi import FastAPI
from .routers import corps, divisions, members

app = FastAPI(
    title="St. John Kenya – Member Registry",
    description="Corp and Division member registration and tracking system",
    version="1.0.0"
)

app.include_router(corps.router)
app.include_router(divisions.router)
app.include_router(members.router)

@app.get("/")
def root():
    return {"message": "St. John Kenya Registry API", "docs": "/docs"}