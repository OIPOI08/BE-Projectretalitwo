# Retali Sistem Backend

Stack:
- Python
- FastAPI
- Supabase Auth
- Supabase PostgreSQL
- Next.js sebagai frontend

## 1. Install

```bash
python -m venv venv
```

Windows:
```bash
venv\Scripts\activate
```

Install:
```bash
pip install -r requirements.txt
```

## 2. Environment

Copy `.env.example` menjadi `.env`, lalu isi:
- SUPABASE_URL
- SUPABASE_ANON_KEY
- SUPABASE_SERVICE_ROLE_KEY
- FRONTEND_URL=http://localhost:3000

SERVICE_ROLE_KEY hanya boleh berada di backend.

## 3. Database

Buka Supabase > SQL Editor.
Jalankan seluruh isi `supabase_schema.sql`.

## 4. Buat admin

Buat user di Supabase > Authentication > Users.
Setelah user dibuat, profile otomatis masuk ke `profiles`.

Kemudian jalankan:

```sql
update public.profiles
set role = 'admin'
where email = 'email-admin-kamu@example.com';
```

## 5. Jalankan backend

```bash
uvicorn app.main:app --reload --port 8000
```

API:
- http://localhost:8000
- Swagger: http://localhost:8000/docs

## Endpoint utama

POST `/api/auth/login`
GET `/api/dashboard/stats`
GET/PATCH `/api/users`
GET/POST/PATCH/DELETE `/api/kloter`
GET/POST/PATCH/DELETE `/api/tasks`
GET/POST `/api/attendance`
GET/POST `/api/scans`
GET/POST/PATCH `/api/notifications`

Semua endpoint selain login membutuhkan:
`Authorization: Bearer <access_token>`
