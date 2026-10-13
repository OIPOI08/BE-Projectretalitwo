import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

env_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:3000"
)

print("ENV PATH:", env_path)
print("SUPABASE_URL:", SUPABASE_URL)
print("ANON KEY:", "ADA" if SUPABASE_ANON_KEY else "TIDAK ADA")
print(
    "SERVICE ROLE KEY:",
    "ADA" if SUPABASE_SERVICE_ROLE_KEY else "TIDAK ADA"
)

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL belum diisi.")

if not SUPABASE_ANON_KEY:
    raise RuntimeError("SUPABASE_ANON_KEY belum diisi.")

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY belum diisi.")