from fastapi import APIRouter, Depends
from ..dependencies import require_admin
from ..supabase import db

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

def count_rows(table: str):
    result = db.table(table).select("id", count="exact", head=True).execute()
    return result.count or 0

@router.get("/stats")
def dashboard_stats(_=Depends(require_admin)):
    return {
        "total_scan": count_rows("scans"),
        "total_pengguna": count_rows("profiles"),
        "total_notifikasi": count_rows("notifications")
    }
