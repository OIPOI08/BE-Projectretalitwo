
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import require_admin, get_current_user
from ..schemas import TaskCreate, TaskStatusUpdate
from ..supabase import db

router = APIRouter(prefix="/api/tasks", tags=["Tugas"])

ALLOWED_STATUSES = ["pending", "proses", "selesai", "dibatalkan"]
ALLOWED_PRIORITIES = ["rendah", "normal", "tinggi"]


def validate_status(status: str):
    if status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Status harus pending, proses, selesai, atau dibatalkan.",
        )


def validate_priority(priority: str):
    if priority not in ALLOWED_PRIORITIES:
        raise HTTPException(
            status_code=400,
            detail="Prioritas harus rendah, normal, atau tinggi.",
        )


def validate_tour_leader(assigned_to: str):
    profile = (
        db.table("profiles")
        .select("id, role, is_active")
        .eq("id", assigned_to)
        .maybe_single()
        .execute()
        .data
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Pengguna penerima tugas tidak ditemukan.",
        )

    if profile.get("role") != "tour_leader":
        raise HTTPException(
            status_code=400,
            detail="Tugas hanya bisa diberikan kepada Tour Leader.",
        )

    if not profile.get("is_active", True):
        raise HTTPException(
            status_code=400,
            detail="Akun Tour Leader tidak aktif.",
        )


# ADMIN: melihat semua tugas
@router.get("")
def get_tasks(_=Depends(require_admin)):
    result = (
        db.table("tasks")
        .select("*, profiles(full_name), kloter(name)")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


# ADMIN: membuat tugas
@router.post("")
def create_task(
    payload: TaskCreate,
    _=Depends(require_admin),
):
    data = payload.model_dump()

    validate_status(data["status"])
    validate_priority(data["priority"])

    if data.get("assigned_to"):
        validate_tour_leader(data["assigned_to"])

    result = db.table("tasks").insert(data).execute()
    return result.data


# TOUR LEADER: melihat tugas miliknya sendiri
@router.get("/mine")
def get_my_tasks(current=Depends(get_current_user)):
    profile = current["profile"]

    if profile.get("role") != "tour_leader":
        raise HTTPException(
            status_code=403,
            detail="Endpoint ini khusus untuk Tour Leader.",
        )

    result = (
        db.table("tasks")
        .select("*, kloter(name)")
        .eq("assigned_to", profile["id"])
        .order("created_at", desc=True)
        .execute()
    )

    return result.data


# TOUR LEADER: memperbarui status tugas miliknya sendiri
@router.patch("/{task_id}/status")
def update_my_task_status(
    task_id: str,
    payload: TaskStatusUpdate,
    current=Depends(get_current_user),
):
    profile = current["profile"]

    if profile.get("role") != "tour_leader":
        raise HTTPException(
            status_code=403,
            detail="Endpoint ini khusus untuk Tour Leader.",
        )

    validate_status(payload.status)

    result = (
        db.table("tasks")
        .update({
            "status": payload.status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", task_id)
        .eq("assigned_to", profile["id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Tugas tidak ditemukan atau bukan milik Anda.",
        )

    return {
        "message": "Status tugas berhasil diperbarui.",
        "data": result.data,
    }


# ADMIN: mengubah tugas
@router.patch("/{task_id}")
def update_task(
    task_id: str,
    payload: TaskCreate,
    _=Depends(require_admin),
):
    data = payload.model_dump(exclude_unset=True)

    if not data:
        raise HTTPException(
            status_code=400,
            detail="Tidak ada data yang diperbarui.",
        )

    if "status" in data:
        validate_status(data["status"])

    if "priority" in data:
        validate_priority(data["priority"])

    if "assigned_to" in data and data["assigned_to"]:
        validate_tour_leader(data["assigned_to"])

    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = (
        db.table("tasks")
        .update(data)
        .eq("id", task_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Tugas tidak ditemukan.",
        )

    return result.data


# ADMIN: menghapus tugas
@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    _=Depends(require_admin),
):
    result = (
        db.table("tasks")
        .delete()
        .eq("id", task_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Tugas tidak ditemukan.",
        )

    return {
        "message": "Tugas berhasil dihapus.",
        "data": result.data,
    }