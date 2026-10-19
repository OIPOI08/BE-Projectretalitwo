
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

from ..dependencies import require_admin
from ..schemas import ScanCreate
from ..supabase import db

router = APIRouter(
    prefix="/api/scans",
    tags=["Riwayat Scan"],
)


def get_scan_data(
    tour_leader_id: Optional[str] = None,
    kloter_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="Tanggal awal tidak boleh melewati tanggal akhir.",
        )

    # Filter berdasarkan kloter.
    # Menggunakan user_kloter karena satu TL bisa memiliki
    # hubungan dengan kloter melalui tabel relasi tersebut.
    if kloter_id:
        membership_result = (
            db.table("user_kloter")
            .select("user_id")
            .eq("kloter_id", kloter_id)
            .execute()
        )

        user_ids = list({
            item["user_id"]
            for item in (membership_result.data or [])
            if item.get("user_id")
        })

        if not user_ids:
            return []

        # Jika Tour Leader juga dipilih, pastikan ID-nya
        # memang termasuk dalam kloter yang dipilih.
        if tour_leader_id and tour_leader_id not in user_ids:
            return []

        if not tour_leader_id:
            query = (
                db.table("scans")
                .select("*, profiles(username, phone)")
                .in_("user_id", user_ids)
            )
        else:
            query = (
                db.table("scans")
                .select("*, profiles(username, phone)")
                .eq("user_id", tour_leader_id)
            )
    else:
        query = (
            db.table("scans")
            .select("*, profiles(username, phone)")
        )

        if tour_leader_id:
            query = query.eq("user_id", tour_leader_id)

    # Filter tanggal berdasarkan scanned_at (UTC).
    if start_date:
        start_datetime = datetime.combine(
            start_date,
            time.min,
            tzinfo=timezone.utc,
        )

        query = query.gte(
            "scanned_at",
            start_datetime.isoformat(),
        )

    if end_date:
        end_datetime = datetime.combine(
            end_date + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )

        query = query.lt(
            "scanned_at",
            end_datetime.isoformat(),
        )

    result = (
        query
        .order("scanned_at", desc=True)
        .execute()
    )

    rows = result.data or []

    # Ambil nama kloter dari relasi user_kloter.
    # Hasil ini tidak mengubah data asli di database.
    scanned_user_ids = list({
        row["user_id"]
        for row in rows
        if row.get("user_id")
    })

    user_kloter_map = {}

    if scanned_user_ids:
        membership_result = (
            db.table("user_kloter")
            .select("user_id, kloter_id")
            .in_("user_id", scanned_user_ids)
            .execute()
        )

        membership_rows = membership_result.data or []

        kloter_ids = list({
            item["kloter_id"]
            for item in membership_rows
            if item.get("kloter_id")
        })

        kloter_names = {}

        if kloter_ids:
            kloter_result = (
                db.table("kloter")
                .select("id, name")
                .in_("id", kloter_ids)
                .execute()
            )

            kloter_names = {
                item["id"]: item["name"]
                for item in (kloter_result.data or [])
            }

        for item in membership_rows:
            user_id = item.get("user_id")
            assigned_kloter_id = item.get("kloter_id")

            if user_id and assigned_kloter_id:
                user_kloter_map.setdefault(user_id, []).append({
                    "id": assigned_kloter_id,
                    "name": kloter_names.get(assigned_kloter_id),
                })

    for row in rows:
        profile = row.get("profiles") or {}
        profile["kloters"] = user_kloter_map.get(
            row.get("user_id"),
            [],
        )
        row["profiles"] = profile

    return rows


@router.get("")
def get_scans(
    tour_leader_id: Optional[str] = None,
    kloter_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    _=Depends(require_admin),
):
    rows = get_scan_data(
        tour_leader_id=tour_leader_id,
        kloter_id=kloter_id,
        start_date=start_date,
        end_date=end_date,
    )

    start = (page - 1) * page_size
    data = rows[start:start + page_size]
    total = len(rows)

    return {
        "data": data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (
                total + page_size - 1
            ) // page_size,
        },
    }


@router.get("/export")
def export_scans_excel(
    tour_leader_id: Optional[str] = None,
    kloter_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    _=Depends(require_admin),
):
    rows = get_scan_data(
        tour_leader_id=tour_leader_id,
        kloter_id=kloter_id,
        start_date=start_date,
        end_date=end_date,
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Riwayat Scan"

    sheet.append([
        "No",
        "ID Scan",
        "ID Tour Leader",
        "Nama Tour Leader",
        "Nomor Telepon TL",
        "Kloter",
        "Jenis Scan",
        "Lokasi",
        "Tanggal Scan",
    ])

    for index, row in enumerate(rows, start=1):
        profile = row.get("profiles") or {}
        kloters = profile.get("kloters") or []

        kloter_names = ", ".join(
            item["name"]
            for item in kloters
            if item.get("name")
        )

        sheet.append([
            index,
            row.get("id"),
            row.get("user_id"),
            profile.get("username"),
            profile.get("phone"),
            kloter_names,
            row.get("scan_type"),
            row.get("location"),
            row.get("scanned_at"),
        ])

    # Atur lebar kolom Excel.
    for column in sheet.columns:
        max_length = max(
            len(str(cell.value or ""))
            for cell in column
        )

        sheet.column_dimensions[
            column[0].column_letter
        ].width = min(max_length + 2, 35)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition":
                'attachment; filename="riwayat_scan.xlsx"'
        },
    )


@router.post("")
def create_scan(
    payload: ScanCreate,
    _=Depends(require_admin),
):
    try:
        result = (
            db.table("scans")
            .insert(payload.model_dump(exclude_none=True))
            .execute()
        )

        return {
            "message": "Data scan berhasil ditambahkan.",
            "data": result.data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menambahkan data scan: {str(exc)}",
        ) from exc
