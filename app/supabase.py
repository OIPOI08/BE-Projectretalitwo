from supabase import create_client, Client
from .config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY

# Client untuk proses Auth.
auth_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Service-role hanya dipakai oleh backend.
# JANGAN pernah expose key ini ke Next.js/frontend.
db: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
