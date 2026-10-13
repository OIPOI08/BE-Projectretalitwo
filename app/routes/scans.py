from fastapi import APIRouter, Depends
from ..dependencies import require_admin
from ..schemas import ScanCreate
from ..supabase import db

router = APIRouter(prefix="/api/scans", tags=["Riwayat Scan"])

@router.get("")
def get_scans(_=Depends(require_admin)):
    return (
        db.table("scans")
        .select("*, profiles(full_name)")
        .order("scanned_at", desc=True)
        .execute()
        .data
    )

@router.post("")
def create_scan(payload: ScanCreate, _=Depends(require_admin)):
    return db.table("scans").insert(payload.model_dump()).execute().data
