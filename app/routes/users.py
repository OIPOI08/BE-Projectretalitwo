
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import require_admin
from ..schemas import ProfileUpdate
from ..supabase import db

router = APIRouter(prefix="/api/users", tags=["Pengguna"])

ALLOWED_ROLES = ["admin", "user", "mekanik", "tour_leader"]


@router.get("")
def get_users(_=Depends(require_admin)):
    result = (
        db.table("profiles")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/{user_id}")
def get_user(user_id: str, _=Depends(require_admin)):
    result = (
        db.table("profiles")
        .select("*")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Pengguna tidak ditemukan."
        )

    return result.data


@router.patch("/{user_id}")
def update_user(
    user_id: str,
    payload: ProfileUpdate,
    _=Depends(require_admin),
):
    data = payload.model_dump(exclude_none=True)

    if not data:
        raise HTTPException(
            status_code=400,
            detail="Tidak ada data yang diperbarui."
        )

    if "role" in data and data["role"] not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Role tidak valid."
        )

    result = (
        db.table("profiles")
        .update(data)
        .eq("id", user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Pengguna tidak ditemukan."
        )

    return result.data
