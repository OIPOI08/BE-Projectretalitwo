
import os
from pathlib import Path

from dotenv import load_dotenv


# =========================================================
# ENVIRONMENT CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)


# =========================================================
# SUPABASE CONFIGURATION
# =========================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:3000",
)


# =========================================================
# EMAIL / SMTP CONFIGURATION
# =========================================================

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

SMTP_HOST = os.getenv(
    "SMTP_HOST",
    "smtp.gmail.com",
)

SMTP_PORT = int(
    os.getenv("SMTP_PORT", "465")
)


# =========================================================
# ENVIRONMENT VALIDATION
# =========================================================

print("ENV PATH:", ENV_PATH)
print("SUPABASE_URL:", SUPABASE_URL)
print(
    "ANON KEY:",
    "ADA" if SUPABASE_ANON_KEY else "TIDAK ADA",
)
print(
    "SERVICE ROLE KEY:",
    "ADA" if SUPABASE_SERVICE_ROLE_KEY else "TIDAK ADA",
)
print(
    "EMAIL USER:",
    "ADA" if EMAIL_USER else "TIDAK ADA",
)
print(
    "EMAIL APP PASSWORD:",
    "ADA" if EMAIL_APP_PASSWORD else "TIDAK ADA",
)

if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL belum diisi di file .env."
    )

if not SUPABASE_ANON_KEY:
    raise RuntimeError(
        "SUPABASE_ANON_KEY belum diisi di file .env."
    )

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_ROLE_KEY belum diisi di file .env."
    )

if not 1 <= SMTP_PORT <= 65535:
    raise RuntimeError(
        "SMTP_PORT harus berada di antara 1 dan 65535."
    )
