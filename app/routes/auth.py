from fastapi import APIRouter, HTTPException
from ..schemas import LoginRequest
from ..supabase import auth_client, db

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/login")
def login(payload: LoginRequest):
    try:
        result = auth_client.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })

        session = result.session
        user = result.user

        if not session or not user:
            raise HTTPException(status_code=401, detail="Email atau password salah.")

        profile_res = db.table("profiles").select("*").eq("id", user.id).single().execute()
        profile = profile_res.data

        if not profile:
            raise HTTPException(status_code=403, detail="Profile belum tersedia.")

        if not profile.get("is_active", True):
            raise HTTPException(status_code=403, detail="Akun sedang tidak aktif.")

        return {
            "message": "Login berhasil",
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "user": profile
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Email atau password salah.")
