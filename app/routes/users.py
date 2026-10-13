from fastapi import APIRouter, Depends, HTTPException
from ..dependencies import require_admin
from ..schemas import ProfileUpdate
from ..supabase import db

router = APIRouter(prefix="/api/users", tags=["Pengguna"])

@router.get("")
def get_users(_=Depends(require_admin)):
    result = db.table("profiles").select("*").order("created_at", desc=True).execute()
    return result.data

@router.get("/{user_id}")
def get_user(user_id: str, _=Depends(require_admin)):
    result = db.table("profiles").select("*").eq("id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    return result.data

@router.patch("/{user_id}")
def update_user(user_id: str, payload: ProfileUpdate, _=Depends(require_admin)):
    data = payload.model_dump(exclude_none=True)
    if data.get("role") and data["role"] not in ["admin", "user", "mekanik"]:
        raise HTTPException(status_code=400, detail="Role tidak valid.")

    result = db.table("profiles").update(data).eq("id", user_id).execute()
    return result.data
