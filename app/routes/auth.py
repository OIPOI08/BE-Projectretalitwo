
import hashlib
import hmac
import logging
import os
import secrets
import smtplib
import ssl

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, HTTPException

from ..config import (
    EMAIL_USER,
    EMAIL_APP_PASSWORD,
    SUPABASE_SERVICE_ROLE_KEY,
)
from ..schemas import (
    LoginRequest,
    ForgotPasswordRequest,
    VerifyResetOTPRequest,
    ResetPasswordRequest,
)
from ..supabase import auth_client, db


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

OTP_MINUTES = 5
RESET_TOKEN_MINUTES = 10
MAX_OTP_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60

OTP_HASH_SECRET = SUPABASE_SERVICE_ROLE_KEY


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def utc_now():
    return datetime.now(timezone.utc)


def parse_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def hash_otp(otp: str) -> str:
    if not OTP_HASH_SECRET:
        raise RuntimeError("OTP hash secret belum dikonfigurasi.")

    return hmac.new(
        OTP_HASH_SECRET.encode("utf-8"),
        otp.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def send_otp_email(email: str, otp: str):
    if not EMAIL_USER or not EMAIL_APP_PASSWORD:
        raise RuntimeError(
            "EMAIL_USER atau EMAIL_APP_PASSWORD belum dikonfigurasi."
        )

    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "465"))

    message = EmailMessage()
    message["Subject"] = "Kode OTP Reset Password - Retali Sistem"
    message["From"] = f"Retali Sistem <{EMAIL_USER}>"
    message["To"] = email

    message.set_content(
        f"""Halo,

Kode OTP untuk reset password Retali Sistem kamu adalah:

{otp}

Kode ini berlaku selama {OTP_MINUTES} menit.
Jangan bagikan kode ini kepada siapa pun.

Jika kamu tidak meminta reset password, abaikan email ini.
"""
    )

    if port == 465:
        with smtplib.SMTP_SSL(
            host,
            port,
            context=ssl.create_default_context(),
            timeout=15,
        ) as server:
            server.login(EMAIL_USER, EMAIL_APP_PASSWORD)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls(
                context=ssl.create_default_context()
            )
            server.ehlo()
            server.login(EMAIL_USER, EMAIL_APP_PASSWORD)
            server.send_message(message)


def get_profile_by_email(email: str):
    result = (
        db.table("profiles")
        .select("id,email")
        .ilike("email", email)
        .limit(1)
        .execute()
    )

    return result.data[0] if result.data else None


def get_latest_unused_otp(email: str):
    result = (
        db.table("password_reset_otps")
        .select("*")
        .eq("email", email)
        .eq("used", False)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    return result.data[0] if result.data else None


# =========================================================
# LOGIN
# =========================================================

@router.post("/login")
def login(payload: LoginRequest):
    try:
        result = auth_client.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password,
        })

        session = result.session
        user = result.user

        if not session or not user:
            raise HTTPException(
                status_code=401,
                detail="Email atau password salah.",
            )

        profile_res = (
            db.table("profiles")
            .select("*")
            .eq("id", user.id)
            .single()
            .execute()
        )

        profile = profile_res.data

        if not profile:
            raise HTTPException(
                status_code=403,
                detail="Profile belum tersedia.",
            )

        if not profile.get("is_active", True):
            raise HTTPException(
                status_code=403,
                detail="Akun sedang tidak aktif.",
            )

        return {
            "message": "Login berhasil",
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "user": profile,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("ERROR LOGIN")
        raise HTTPException(
            status_code=401,
            detail="Email atau password salah.",
        )


# =========================================================
# FORGOT PASSWORD: GENERATE AND SEND OTP
# =========================================================

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    email = str(payload.email).strip().lower()

    generic_response = {
        "message": "Jika email terdaftar, kode OTP akan dikirim."
    }

    try:
        profile = get_profile_by_email(email)

        # Jangan membocorkan apakah email terdaftar.
        if not profile:
            return generic_response

        # Cooldown pengiriman ulang OTP.
        latest_res = (
            db.table("password_reset_otps")
            .select("created_at")
            .eq("email", email)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if latest_res.data:
            created_at = parse_datetime(
                latest_res.data[0]["created_at"]
            )

            if (
                utc_now() - created_at
                < timedelta(seconds=RESEND_COOLDOWN_SECONDS)
            ):
                return generic_response

        # Hapus OTP/token sebelumnya untuk email tersebut.
        db.table("password_reset_otps").delete().eq(
            "email", email
        ).execute()

        otp = f"{secrets.randbelow(1_000_000):06d}"

        insert_res = (
            db.table("password_reset_otps")
            .insert({
                "email": email,
                "otp_hash": hash_otp(otp),
                "expires_at": (
                    utc_now() + timedelta(minutes=OTP_MINUTES)
                ).isoformat(),
                "attempts": 0,
                "used": False,
                "verified": False,
                "reset_token_hash": None,
                "reset_token_expires_at": None,
            })
            .execute()
        )

        if not insert_res.data:
            raise RuntimeError("Gagal menyimpan OTP ke database.")

        try:
            send_otp_email(email, otp)
        except Exception:
            # Jangan tinggalkan OTP aktif jika email gagal dikirim.
            db.table("password_reset_otps").delete().eq(
                "email", email
            ).execute()
            raise

        return generic_response

    except HTTPException:
        raise
    except Exception:
        logger.exception("ERROR FORGOT PASSWORD")
        raise HTTPException(
            status_code=500,
            detail="Gagal memproses permintaan reset password.",
        )


# =========================================================
# VERIFY OTP
# =========================================================

@router.post("/verify-reset-otp")
def verify_reset_otp(payload: VerifyResetOTPRequest):
    email = str(payload.email).strip().lower()

    try:
        record = get_latest_unused_otp(email)

        if not record or record.get("verified", False):
            raise HTTPException(
                status_code=400,
                detail="OTP tidak valid atau sudah kedaluwarsa.",
            )

        if record["attempts"] >= MAX_OTP_ATTEMPTS:
            db.table("password_reset_otps").update({
                "used": True,
            }).eq("id", record["id"]).execute()

            raise HTTPException(
                status_code=400,
                detail="Batas percobaan OTP tercapai. Minta kode baru.",
            )

        if parse_datetime(record["expires_at"]) <= utc_now():
            db.table("password_reset_otps").update({
                "used": True,
            }).eq("id", record["id"]).execute()

            raise HTTPException(
                status_code=400,
                detail="OTP sudah kedaluwarsa. Minta kode baru.",
            )

        expected_hash = record["otp_hash"]
        provided_hash = hash_otp(payload.otp)

        if not hmac.compare_digest(expected_hash, provided_hash):
            attempts = record["attempts"] + 1

            db.table("password_reset_otps").update({
                "attempts": attempts,
                "used": attempts >= MAX_OTP_ATTEMPTS,
            }).eq("id", record["id"]).execute()

            raise HTTPException(
                status_code=400,
                detail="OTP tidak valid.",
            )

        reset_token = secrets.token_urlsafe(32)

        update_res = (
            db.table("password_reset_otps")
            .update({
                "verified": True,
                "reset_token_hash": hash_reset_token(reset_token),
                "reset_token_expires_at": (
                    utc_now()
                    + timedelta(minutes=RESET_TOKEN_MINUTES)
                ).isoformat(),
            })
            .eq("id", record["id"])
            .eq("used", False)
            .eq("verified", False)
            .execute()
        )

        if not update_res.data:
            raise HTTPException(
                status_code=400,
                detail="OTP sudah diproses. Minta kode baru.",
            )

        return {
            "message": "OTP berhasil diverifikasi.",
            "reset_token": reset_token,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("ERROR VERIFY RESET OTP")
        raise HTTPException(
            status_code=500,
            detail="Gagal memverifikasi OTP.",
        )


# =========================================================
# RESET PASSWORD
# =========================================================

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    email = str(payload.email).strip().lower()

    try:
        result = (
            db.table("password_reset_otps")
            .select("*")
            .eq("email", email)
            .eq("verified", True)
            .eq("used", False)
            .eq(
                "reset_token_hash",
                hash_reset_token(payload.reset_token),
            )
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        record = result.data[0] if result.data else None

        if not record:
            raise HTTPException(
                status_code=400,
                detail="Token reset tidak valid atau sudah digunakan.",
            )

        token_expiry = record.get("reset_token_expires_at")

        if (
            not token_expiry
            or parse_datetime(token_expiry) <= utc_now()
        ):
            db.table("password_reset_otps").update({
                "used": True,
            }).eq("id", record["id"]).execute()

            raise HTTPException(
                status_code=400,
                detail="Token reset kedaluwarsa. Ulangi proses OTP.",
            )

        profile = get_profile_by_email(email)

        if not profile:
            raise HTTPException(
                status_code=404,
                detail="Akun tidak ditemukan.",
            )

        # Konsumsi token sebelum mengubah password.
        # Jika update password gagal, minta OTP baru.
        claim_res = (
            db.table("password_reset_otps")
            .update({"used": True})
            .eq("id", record["id"])
            .eq("used", False)
            .select("id")
            .execute()
        )

        if not claim_res.data:
            raise HTTPException(
                status_code=400,
                detail="Token reset sudah digunakan.",
            )

        # Password autentikasi tetap dikelola Supabase Auth.
        db.auth.admin.update_user_by_id(
            profile["id"],
            {"password": payload.new_password},
        )

        return {
            "message": (
                "Password berhasil diperbarui. Silakan login kembali."
            )
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("ERROR RESET PASSWORD")
        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal memperbarui password. "
                "Periksa log backend dan minta OTP baru jika diperlukan."
            ),
        )
