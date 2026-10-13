from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .supabase import auth_client, db


# Skema autentikasi Bearer untuk Swagger UI
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    # Pastikan token tersedia
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Token Bearer tidak ditemukan. Silakan gunakan Authorize."
        )

    token = credentials.credentials

    # Validasi token menggunakan Supabase Auth
    try:
        response = auth_client.auth.get_user(token)
        user = response.user

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Token tidak valid."
            )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Autentikasi gagal. Periksa token atau sesi login."
        )

    # Ambil profil pengguna dari database
    try:
        profile_res = (
            db.table("profiles")
            .select("*")
            .eq("id", user.id)
            .maybe_single()
            .execute()
        )

        profile = profile_res.data

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Gagal mengambil profil pengguna dari database."
        )

    if not profile:
        raise HTTPException(
            status_code=403,
            detail="Profile user belum dibuat."
        )

    return {
        "auth_user": user,
        "profile": profile
    }


def require_admin(
    current=Depends(get_current_user),
):
    if current["profile"].get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Akses hanya untuk admin."
        )

    return current
