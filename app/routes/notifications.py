from fastapi import APIRouter, Depends, HTTPException
from ..dependencies import require_admin
from ..schemas import NotificationCreate
from ..supabase import db

router = APIRouter(prefix="/api/notifications", tags=["Notifikasi"])

@router.get("")
def get_notifications(_=Depends(require_admin)):
    return (
        db.table("notifications")
        .select("*, profiles(full_name)")
        .order("created_at", desc=True)
        .execute()
        .data
    )

@router.post("")
def create_notification(payload: NotificationCreate, _=Depends(require_admin)):
    return db.table("notifications").insert(payload.model_dump()).execute().data

@router.patch("/{notification_id}/read")
def mark_read(notification_id: str, _=Depends(require_admin)):
    result = (
        db.table("notifications")
        .update({"is_read": True, "read_at": "now()"})
        .eq("id", notification_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan.")
    return result.data
