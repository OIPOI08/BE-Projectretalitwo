from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import FRONTEND_URL
from .routes import (
    users,
    attendance,
    auth,
    dashboard,
    kloter,
    notifications,
    scans,
    tasks,
)

app = FastAPI(
    title="Retali Sistem API",
    version="1.0.0",
    description="Backend Python FastAPI + Supabase untuk dashboard Retali Sistem.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(kloter.router)
app.include_router(tasks.router)
app.include_router(attendance.router)
app.include_router(scans.router)
app.include_router(notifications.router)


@app.get("/")
def root():
    return {
        "message": "Retali Sistem API is running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}