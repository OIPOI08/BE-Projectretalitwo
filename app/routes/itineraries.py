from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import require_admin
from ..schemas import ItineraryCreate, ItineraryUpdate
from ..supabase import db


router = APIRouter(
    prefix="/api/itineraries",
    tags=["Manajemen Itinerary"],
)

ROLE_LABELS = {
    "tour_leader": "Tour Leader",
    "muthawif": "Muthawif",
}

VALID_STATUSES = {"draft", "published", "archived"}


# =====================================================
# HELPER
# =====================================================

def find_one(table: str, column: str, value):
    result = (
        db.table(table)
        .select("*")
        .eq(column, value)
        .limit(1)
        .execute()
    )

    rows = result.data or []
    return rows[0] if rows else None


def get_itinerary_or_404(itinerary_id: str):
    itinerary = find_one(
        "itineraries",
        "id",
        itinerary_id,
    )

    if not itinerary:
        raise HTTPException(
            status_code=404,
            detail="Itinerary tidak ditemukan.",
        )

    return itinerary


def validate_recipient_profiles(recipients):
    """
    Memastikan profil penerima benar-benar ada, aktif,
    dan memiliki role yang sesuai.
    """
    selected_ids = list(dict.fromkeys(
        str(profile_id)
        for rule in recipients
        if rule.recipient_mode == "selected"
        for profile_id in rule.profile_ids
    ))

    if not selected_ids:
        return

    profiles = (
        db.table("profiles")
        .select("id, full_name, email, role, is_active")
        .in_("id", selected_ids)
        .execute()
        .data or []
    )

    profiles_by_id = {
        str(profile["id"]): profile
        for profile in profiles
    }

    missing = [
        profile_id
        for profile_id in selected_ids
        if profile_id not in profiles_by_id
    ]

    if missing:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Profil penerima tidak ditemukan.",
                "profile_ids": missing,
            },
        )

    invalid = []

    for rule in recipients:
        if rule.recipient_mode != "selected":
            continue

        for profile_id in rule.profile_ids:
            profile = profiles_by_id[str(profile_id)]

            if (
                profile.get("role") != rule.recipient_role
                or not profile.get("is_active", False)
            ):
                invalid.append(str(profile_id))

    if invalid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    "Role penerima tidak sesuai atau akun tidak aktif."
                ),
                "profile_ids": list(dict.fromkeys(invalid)),
            },
        )


def get_recipient_rules(itinerary_id: str):
    rules = (
        db.table("itinerary_recipient_rules")
        .select("*")
        .eq("itinerary_id", itinerary_id)
        .order("created_at")
        .execute()
        .data or []
    )

    if not rules:
        return []

    rule_ids = [rule["id"] for rule in rules]

    recipient_links = (
        db.table("itinerary_recipient_users")
        .select("rule_id, profile_id")
        .in_("rule_id", rule_ids)
        .execute()
        .data or []
    )

    profile_ids = list(dict.fromkeys(
        item["profile_id"] for item in recipient_links
    ))

    profiles_by_id = {}

    if profile_ids:
        profiles = (
            db.table("profiles")
            .select("id, full_name, email, role")
            .in_("id", profile_ids)
            .execute()
            .data or []
        )

        profiles_by_id = {
            item["id"]: item
            for item in profiles
        }

    recipients_by_rule = {}

    for link in recipient_links:
        profile = profiles_by_id.get(link["profile_id"])

        if profile:
            recipients_by_rule.setdefault(
                link["rule_id"], []
            ).append(profile)

    response = []

    for rule in rules:
        role_label = ROLE_LABELS[rule["recipient_role"]]
        selected = recipients_by_rule.get(rule["id"], [])

        if rule["recipient_mode"] == "all":
            label = f"Semua {role_label}"
        elif selected:
            names = [
                person["full_name"]
                for person in selected
            ]

            if len(names) <= 2:
                label = ", ".join(names)
            else:
                label = (
                    f"{names[0]}, {names[1]} "
                    f"+{len(names) - 2} lainnya"
                )
        else:
            label = f"{role_label} belum dipilih"

        response.append({
            **rule,
            "recipients": selected,
            "recipient_label": label,
        })

    return response


def get_itinerary_detail(itinerary_id: str):
    itinerary = get_itinerary_or_404(itinerary_id)

    days = (
        db.table("itinerary_days")
        .select("*")
        .eq("itinerary_id", itinerary_id)
        .order("day_number")
        .execute()
        .data or []
    )

    days_response = []

    for day in days:
        activities = (
            db.table("itinerary_activities")
            .select("*")
            .eq("itinerary_day_id", day["id"])
            .order("sort_order")
            .execute()
            .data or []
        )

        days_response.append({
            **day,
            "activities": activities,
        })

    recipient_rules = get_recipient_rules(itinerary_id)

    return {
        **itinerary,
        "day_count": len(days_response),
        "recipient_label": (
            ", ".join(
                rule["recipient_label"]
                for rule in recipient_rules
            )
            if recipient_rules
            else "Belum ditentukan"
        ),
        "recipient_rules": recipient_rules,
        "days": days_response,
    }


def cleanup_itinerary(itinerary_id: str | None):
    """
    Pembersihan best-effort jika proses pembuatan gagal.
    Tabel anak akan terhapus melalui ON DELETE CASCADE.
    """
    if not itinerary_id:
        return

    try:
        (
            db.table("itineraries")
            .delete()
            .eq("id", itinerary_id)
            .execute()
        )
    except Exception:
        pass


# =====================================================
# GET: DAFTAR ITINERARY UNTUK HALAMAN TABEL
# =====================================================

@router.get("")
def list_itineraries(
    status: str | None = None,
    search: str | None = None,
    _=Depends(require_admin),
):
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Status itinerary tidak valid.",
        )

    query = (
        db.table("itineraries")
        .select("*")
        .order("created_at", desc=True)
    )

    if status:
        query = query.eq("status", status)

    if search and search.strip():
        query = query.ilike(
            "title",
            f"%{search.strip()}%",
        )

    itineraries = query.execute().data or []
    response = []

    for itinerary in itineraries:
        days = (
            db.table("itinerary_days")
            .select("id")
            .eq("itinerary_id", itinerary["id"])
            .execute()
            .data or []
        )

        recipient_rules = get_recipient_rules(itinerary["id"])

        response.append({
            **itinerary,
            "day_count": len(days),
            "recipient_label": (
                ", ".join(
                    rule["recipient_label"]
                    for rule in recipient_rules
                )
                if recipient_rules
                else "Belum ditentukan"
            ),
            "recipient_rules": recipient_rules,
        })

    return response


# =====================================================
# POST: CREATE ITINERARY
# =====================================================

@router.post("")
def create_itinerary(
    payload: ItineraryCreate,
    current=Depends(require_admin),
):
    # Validasi sebelum membuat data induk.
    validate_recipient_profiles(payload.recipients)

    itinerary_id = None

    try:
        # 1. Simpan data utama.
        itinerary_result = (
            db.table("itineraries")
            .insert({
                "title": payload.title,
                "start_date": payload.start_date.isoformat(),
                "end_date": payload.end_date.isoformat(),
                "status": "draft",
                "created_by": current["profile"]["id"],
            })
            .execute()
        )

        itinerary_rows = itinerary_result.data or []

        if not itinerary_rows:
            raise HTTPException(
                status_code=500,
                detail="Itinerary gagal dibuat.",
            )

        itinerary_id = itinerary_rows[0]["id"]

        # 2. Buat satu baris untuk setiap hari dalam periode.
        day_inputs = {
            day.activity_date.isoformat(): day
            for day in payload.days
        }

        total_days = (
            payload.end_date - payload.start_date
        ).days + 1

        day_records = []

        for offset in range(total_days):
            activity_date = (
                payload.start_date
                + timedelta(days=offset)
            )

            day_input = day_inputs.get(
                activity_date.isoformat()
            )

            day_records.append({
                "itinerary_id": itinerary_id,
                "day_number": offset + 1,
                "activity_date": activity_date.isoformat(),
                "title": day_input.title if day_input else None,
            })

        (
            db.table("itinerary_days")
            .insert(day_records)
            .execute()
        )

        # Ambil ID hari untuk menghubungkan kegiatan.
        saved_days = (
            db.table("itinerary_days")
            .select("id, activity_date")
            .eq("itinerary_id", itinerary_id)
            .execute()
            .data or []
        )

        day_id_by_date = {
            str(day["activity_date"])[:10]: day["id"]
            for day in saved_days
        }

        # 3. Simpan semua kegiatan sesuai tanggalnya.
        activity_records = []

        for day_input in payload.days:
            day_id = day_id_by_date.get(
                day_input.activity_date.isoformat()
            )

            if not day_id:
                raise HTTPException(
                    status_code=500,
                    detail="Hari itinerary gagal disiapkan.",
                )

            for index, activity in enumerate(
                day_input.activities,
                start=1,
            ):
                activity_records.append({
                    "itinerary_day_id": day_id,
                    "activity_time": (
                        activity.activity_time.isoformat()
                        if activity.activity_time
                        else None
                    ),
                    "title": activity.title.strip(),
                    "description": activity.description,
                    "location": activity.location,
                    "sort_order": index,
                })

        if activity_records:
            (
                db.table("itinerary_activities")
                .insert(activity_records)
                .execute()
            )

        # 4. Simpan aturan penerima dan profil terpilih.
        for recipient in payload.recipients:
            rule_result = (
                db.table("itinerary_recipient_rules")
                .insert({
                    "itinerary_id": itinerary_id,
                    "recipient_role": recipient.recipient_role,
                    "recipient_mode": recipient.recipient_mode,
                })
                .execute()
            )

            rule_rows = rule_result.data or []

            if not rule_rows:
                raise HTTPException(
                    status_code=500,
                    detail="Aturan penerima gagal disimpan.",
                )

            rule_id = rule_rows[0]["id"]

            if recipient.recipient_mode == "selected":
                selected_records = [
                    {
                        "rule_id": rule_id,
                        "profile_id": str(profile_id),
                    }
                    for profile_id in recipient.profile_ids
                ]

                (
                    db.table("itinerary_recipient_users")
                    .insert(selected_records)
                    .execute()
                )

    except HTTPException:
        cleanup_itinerary(itinerary_id)
        raise

    except Exception:
        cleanup_itinerary(itinerary_id)

        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal membuat itinerary. "
                "Periksa koneksi, struktur tabel, dan data Supabase."
            ),
        )

    return get_itinerary_detail(itinerary_id)


# =====================================================
# GET: DETAIL ITINERARY
# =====================================================

@router.get("/{itinerary_id}")
def get_itinerary(
    itinerary_id: str,
    _=Depends(require_admin),
):
    return get_itinerary_detail(itinerary_id)


# =====================================================
# PATCH: UBAH JUDUL ATAU STATUS
# =====================================================

@router.patch("/{itinerary_id}")
def update_itinerary(
    itinerary_id: str,
    payload: ItineraryUpdate,
    _=Depends(require_admin),
):
    itinerary = get_itinerary_or_404(itinerary_id)

    data = payload.model_dump(
        exclude_unset=True,
        mode="json",
    )

    if not data:
        raise HTTPException(
            status_code=400,
            detail="Tidak ada data yang diperbarui.",
        )

    for field in ("title", "status"):
        if field in data and data[field] is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field} tidak boleh kosong.",
            )

    if "title" in data:
        data["title"] = data["title"].strip()

        if not data["title"]:
            raise HTTPException(
                status_code=422,
                detail="Judul itinerary tidak boleh kosong.",
            )

    if data.get("status") == "published":
        days = (
            db.table("itinerary_days")
            .select("id")
            .eq("itinerary_id", itinerary_id)
            .execute()
            .data or []
        )

        if days:
            day_ids = [day["id"] for day in days]

            activities = (
                db.table("itinerary_activities")
                .select("id")
                .in_("itinerary_day_id", day_ids)
                .limit(1)
                .execute()
                .data or []
            )
        else:
            activities = []

        rules = get_recipient_rules(itinerary_id)

        if not activities or not rules:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Tambahkan kegiatan dan penerima "
                    "sebelum memublikasikan itinerary."
                ),
            )

        if any(
            rule["recipient_mode"] == "selected"
            and not rule["recipients"]
            for rule in rules
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Pastikan setiap aturan penerima terpilih "
                    "memiliki profil penerima."
                ),
            )

    data["updated_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    result = (
        db.table("itineraries")
        .update(data)
        .eq("id", itinerary_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Itinerary gagal diperbarui.",
        )

    return get_itinerary_detail(itinerary["id"])