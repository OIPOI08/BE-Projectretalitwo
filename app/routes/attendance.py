from fastapi import APIRouter, Depends
from ..dependencies import require_admin
from ..schemas import AttendanceCreate
from ..supabase import db

router = APIRouter(prefix="/api/attendance", tags=["Riwayat Absensi"])

@router.get("")
def get_attendance(_=Depends(require_admin)):
    return (
        db.table("attendance")
        .select("*, profiles(full_name)")
        .order("created_at", desc=True)
        .execute()
        .data
    )

@router.post("")
def create_attendance(payload: AttendanceCreate, _=Depends(require_admin)):
    return db.table("attendance").insert(payload.model_dump()).execute().data
