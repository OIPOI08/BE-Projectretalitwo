
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from ..dependencies import require_admin
from ..schemas import ProfileUpdate
from ..supabase import db

router = APIRouter(prefix="/api/users", tags=["Pengguna"])

ALLOWED_ROLES = [
    "admin",
    "user",
    "tour_leader",
    "muthawif",
]

ASSIGNABLE_ROLES = [
    "tour_leader",
    "muthawif",
]


class UserKloterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kloter_id: str


@router.get("")
def get_users(
    role: str | None = None,
    _=Depends(require_admin),
):
    if role is not None and role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Role tidak valid.",
        )

    query = (
        db.table("profiles")
        .select("*")
        .order("created_at", desc=True)
    )

    if role is not None:
        query = query.eq("role", role)

    profiles_result = query.execute()
    profiles = profiles_result.data or []

    if not profiles:
        return []

    user_ids = [profile["id"] for profile in profiles]

    assignments_result = (
        db.table("user_kloter")
        .select("user_id, kloter_id")
        .in_("user_id", user_ids)
        .execute()
    )
    assignments = assignments_result.data or []

    kloter_ids = list(
        dict.fromkeys(
            assignment["kloter_id"]
            for assignment in assignments
        )
    )

    kloter_by_id = {}

    if kloter_ids:
        kloter_result = (
            db.table("kloter")
            .select("id, name")
            .in_("id", kloter_ids)
            .execute()
        )

        kloter_by_id = {
            item["id"]: item
            for item in (kloter_result.data or [])
        }

    assignments_by_user = {}

    for assignment in assignments:
        assignments_by_user.setdefault(
            assignment["user_id"], []
        ).append(assignment["kloter_id"])

    response = []

    for profile in profiles:
        assigned_kloter_ids = assignments_by_user.get(
            profile["id"], []
        )

        response.append({
            **profile,
            "kloters": [
                {
                    "id": kloter_id,
                    "name": kloter_by_id[kloter_id]["name"],
                }
                for kloter_id in assigned_kloter_ids
                if kloter_id in kloter_by_id
            ],
        })

    return response


@router.get("/{user_id}")
def get_user(
    user_id: str,
    _=Depends(require_admin),
):
    result = (
        db.table("profiles")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    profiles = result.data or []

    if not profiles:
        raise HTTPException(
            status_code=404,
            detail="Pengguna tidak ditemukan.",
        )

    profile = profiles[0]

    assignments_result = (
        db.table("user_kloter")
        .select("kloter_id")
        .eq("user_id", user_id)
        .execute()
    )

    assignments = assignments_result.data or []
    kloter_ids = list(
        dict.fromkeys(
            item["kloter_id"] for item in assignments
        )
    )

    kloters = []

    if kloter_ids:
        kloter_result = (
            db.table("kloter")
            .select("id, name")
            .in_("id", kloter_ids)
            .execute()
        )
        kloters = kloter_result.data or []

    return {
        **profile,
        "kloters": kloters,
    }


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
            detail="Tidak ada data yang diperbarui.",
        )

    if "role" in data and data["role"] not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Role tidak valid.",
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
            detail="Pengguna tidak ditemukan.",
        )

    return result.data


@router.get("/{user_id}/kloter")
def get_user_kloter(
    user_id: str,
    _=Depends(require_admin),
):
    profile_result = (
        db.table("profiles")
        .select("id")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    if not (profile_result.data or []):
        raise HTTPException(
            status_code=404,
            detail="Pengguna tidak ditemukan.",
        )

    result = (
        db.table("user_kloter")
        .select("id, user_id, kloter_id, assigned_at, created_at")
        .eq("user_id", user_id)
        .order("assigned_at", desc=True)
        .execute()
    )

    assignments = result.data or []
    kloter_ids = list(
        dict.fromkeys(
            item["kloter_id"] for item in assignments
        )
    )

    kloter_by_id = {}

    if kloter_ids:
        kloter_result = (
            db.table("kloter")
            .select("id, name")
            .in_("id", kloter_ids)
            .execute()
        )

        kloter_by_id = {
            item["id"]: item
            for item in (kloter_result.data or [])
        }

    return [
        {
            **assignment,
            "kloter": kloter_by_id.get(
                assignment["kloter_id"]
            ),
        }
        for assignment in assignments
    ]


@router.post("/{user_id}/kloter")
def assign_user_kloter(
    user_id: str,
    payload: UserKloterCreate,
    _=Depends(require_admin),
):
    profile_result = (
        db.table("profiles")
        .select("id, role")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    profiles = profile_result.data or []

    if not profiles:
        raise HTTPException(
            status_code=404,
            detail="Pengguna tidak ditemukan.",
        )

    if profiles[0]["role"] not in ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Hanya Tour Leader atau Muthawif "
                "yang dapat ditugaskan ke kloter."
            ),
        )

    kloter_result = (
        db.table("kloter")
        .select("id")
        .eq("id", payload.kloter_id)
        .limit(1)
        .execute()
    )

    if not (kloter_result.data or []):
        raise HTTPException(
            status_code=404,
            detail="Kloter tidak ditemukan.",
        )

    existing_result = (
        db.table("user_kloter")
        .select("id")
        .eq("user_id", user_id)
        .eq("kloter_id", payload.kloter_id)
        .limit(1)
        .execute()
    )

    if existing_result.data:
        raise HTTPException(
            status_code=409,
            detail="Pengguna sudah ditugaskan ke kloter tersebut.",
        )

    result = (
        db.table("user_kloter")
        .insert({
            "user_id": user_id,
            "kloter_id": payload.kloter_id,
        })
        .execute()
    )

    return {
        "message": "Penugasan kloter berhasil ditambahkan.",
        "data": result.data or [],
    }


@router.delete("/{user_id}/kloter/{kloter_id}")
def remove_user_kloter(
    user_id: str,
    kloter_id: str,
    _=Depends(require_admin),
):
    existing_result = (
        db.table("user_kloter")
        .select("id")
        .eq("user_id", user_id)
        .eq("kloter_id", kloter_id)
        .limit(1)
        .execute()
    )

    if not (existing_result.data or []):
        raise HTTPException(
            status_code=404,
            detail="Penugasan kloter tidak ditemukan.",
        )

    (
        db.table("user_kloter")
        .delete()
        .eq("user_id", user_id)
        .eq("kloter_id", kloter_id)
        .execute()
    )

    return {
        "message": "Penugasan kloter berhasil dihapus.",
    }
