-- RETALI SISTEM
-- Jalankan file ini di Supabase SQL Editor.
-- Authentication user tetap dibuat lewat Supabase Auth.

create extension if not exists "pgcrypto";

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    full_name text not null,
    email text,
    phone text,
    role text not null default 'user'
        check (role in ('admin', 'user', 'mekanik')),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.kloter (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    description text,
    start_date date,
    end_date date,
    status text not null default 'aktif'
        check (status in ('aktif', 'selesai', 'nonaktif')),
    created_at timestamptz not null default now()
);

create table if not exists public.tasks (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    description text,
    assigned_to uuid references public.profiles(id) on delete set null,
    kloter_id uuid references public.kloter(id) on delete set null,
    status text not null default 'pending'
        check (status in ('pending', 'proses', 'selesai', 'dibatalkan')),
    priority text not null default 'normal'
        check (priority in ('rendah', 'normal', 'tinggi')),
    due_date date,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.attendance (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles(id) on delete cascade,
    type text not null default 'masuk'
        check (type in ('masuk', 'pulang', 'izin', 'sakit', 'alpa')),
    note text,
    created_at timestamptz not null default now()
);

create table if not exists public.scans (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles(id) on delete cascade,
    scan_type text not null default 'masuk'
        check (scan_type in ('masuk', 'pulang', 'lainnya')),
    location text,
    scanned_at timestamptz not null default now()
);

create table if not exists public.notifications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references public.profiles(id) on delete cascade,
    title text not null,
    message text not null,
    type text not null default 'info'
        check (type in ('info', 'success', 'warning', 'error')),
    is_read boolean not null default false,
    read_at timestamptz,
    created_at timestamptz not null default now()
);

-- Index agar query dashboard/history lebih cepat.
create index if not exists idx_tasks_assigned_to on public.tasks(assigned_to);
create index if not exists idx_tasks_kloter_id on public.tasks(kloter_id);
create index if not exists idx_attendance_user_id on public.attendance(user_id);
create index if not exists idx_scans_user_id on public.scans(user_id);
create index if not exists idx_scans_scanned_at on public.scans(scanned_at desc);
create index if not exists idx_notifications_user_id on public.notifications(user_id);
create index if not exists idx_notifications_created_at on public.notifications(created_at desc);

-- Trigger untuk membuat profile otomatis setelah user register di Supabase Auth.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, full_name, email)
    values (
        new.id,
        coalesce(new.raw_user_meta_data->>'full_name', split_part(coalesce(new.email, 'user'), '@', 1)),
        new.email
    )
    on conflict (id) do nothing;

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

-- RLS.
-- Frontend TIDAK mengakses tabel secara langsung.
-- Backend memakai service_role sehingga tetap bisa membaca/menulis data.
alter table public.profiles enable row level security;
alter table public.kloter enable row level security;
alter table public.tasks enable row level security;
alter table public.attendance enable row level security;
alter table public.scans enable row level security;
alter table public.notifications enable row level security;

-- Tidak membuat policy public.
-- Service role backend bypass RLS.
