from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_current_user, require_admin
from ..schemas import (
    ChecklistTaskCreate,
    ChecklistTaskUpdate,
    ChecklistQuestionCreate,
    ChecklistRecipientsCreate,
    ChecklistAnswerCreate,
)
from ..supabase import db


router = APIRouter(
    prefix="/api/checklist-tasks",
    tags=["Tugas Ceklis"],
)

RECIPIENT_ROLES = {"tour_leader", "muthawif"}
TASK_STATUSES = {"draft", "published", "archived"}


# =========================================================
# HELPER
# =========================================================

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


def get_task_or_404(task_id: str):
    task = find_one("checklist_tasks", "id", task_id)

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Tugas ceklis tidak ditemukan.",
        )

    return task


def get_assignment_or_404(assignment_id: str):
    assignment = find_one(
        "checklist_assignments",
        "id",
        assignment_id,
    )

    if not assignment:
        raise HTTPException(
            status_code=404,
            detail="Penugasan tugas tidak ditemukan.",
        )

    return assignment


def check_task_open(task: dict):
    if task["status"] != "published":
        raise HTTPException(
            status_code=409,
            detail="Tugas belum dipublikasikan atau sudah diarsipkan.",
        )

    now = datetime.now(timezone.utc)

    opens_at = datetime.fromisoformat(
        task["opens_at"].replace("Z", "+00:00")
    )

    closes_at = datetime.fromisoformat(
        task["closes_at"].replace("Z", "+00:00")
    )

    if now < opens_at:
        raise HTTPException(
            status_code=403,
            detail="Tugas belum dibuka.",
        )

    if now > closes_at:
        raise HTTPException(
            status_code=403,
            detail="Waktu pengerjaan tugas telah berakhir.",
        )


def check_assignment_owner(assignment: dict, current: dict):
    profile = current["profile"]

    if str(assignment["recipient_id"]) != str(profile["id"]):
        raise HTTPException(
            status_code=403,
            detail="Tugas ini bukan milik akun lu.",
        )

    if profile.get("role") not in RECIPIENT_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Akses hanya untuk Tour Leader atau Muthawif.",
        )


def get_owned_assignment(assignment_id: str, current: dict):
    assignment = get_assignment_or_404(assignment_id)
    check_assignment_owner(assignment, current)
    task = get_task_or_404(assignment["task_id"])

    return assignment, task


def check_answer_format(question: dict, answer):
    answer_type = question["answer_type"]
    options = question.get("options") or []

    valid = False

    if answer_type == "text":
        valid = isinstance(answer, str)

    elif answer_type == "yes_no":
        valid = isinstance(answer, bool)

    elif answer_type == "number":
        valid = (
            isinstance(answer, (int, float))
            and not isinstance(answer, bool)
        )

    elif answer_type == "single_choice":
        valid = isinstance(answer, str) and answer in options

    elif answer_type == "multiple_choice":
        valid = (
            isinstance(answer, list)
            and all(isinstance(item, str) for item in answer)
            and all(item in options for item in answer)
        )

    if answer is None or not valid:
        raise HTTPException(
            status_code=422,
            detail="Format jawaban tidak sesuai dengan tipe soal.",
        )


# =========================================================
# ADMIN: DAFTAR DAN BUAT TUGAS
# =========================================================

@router.get("")
def list_checklist_tasks(
    status: str | None = None,
    _=Depends(require_admin),
):
    if status is not None and status not in TASK_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Status tugas tidak valid.",
        )

    query = (
        db.table("checklist_tasks")
        .select("*")
        .order("created_at", desc=True)
    )

    if status:
        query = query.eq("status", status)

    tasks = query.execute().data or []
    response = []

    for task in tasks:
        task_id = task["id"]

        questions = (
            db.table("checklist_questions")
            .select("id")
            .eq("task_id", task_id)
            .execute()
            .data or []
        )

        assignments = (
            db.table("checklist_assignments")
            .select("id, recipient_id, status")
            .eq("task_id", task_id)
            .execute()
            .data or []
        )

        response.append({
            **task,
            "question_count": len(questions),
            "recipient_count": len(assignments),
            "submitted_count": sum(
                item["status"] == "submitted"
                for item in assignments
            ),
        })

    return response


@router.post("")
def create_checklist_task(
    payload: ChecklistTaskCreate,
    current=Depends(require_admin),
):
    data = payload.model_dump(mode="json")
    data["created_by"] = current["profile"]["id"]
    data["status"] = "draft"

    result = (
        db.table("checklist_tasks")
        .insert(data)
        .execute()
    )

    rows = result.data or []

    if not rows:
        raise HTTPException(
            status_code=500,
            detail="Tugas gagal dibuat.",
        )

    return rows[0]


# =========================================================
# PENERIMA: LIHAT DAFTAR TUGAS
# PENTING: ROUTE INI HARUS SEBELUM /{task_id}
# =========================================================

@router.get("/my-assignments")
def get_my_assignments(
    current=Depends(get_current_user),
):
    profile = current["profile"]

    if profile.get("role") not in RECIPIENT_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Akses hanya untuk Tour Leader atau Muthawif.",
        )

    assignments = (
        db.table("checklist_assignments")
        .select("*")
        .eq("recipient_id", profile["id"])
        .order("assigned_at", desc=True)
        .execute()
        .data or []
    )

    response = []

    for assignment in assignments:
        task = find_one(
            "checklist_tasks",
            "id",
            assignment["task_id"],
        )

        if not task or task["status"] != "published":
            continue

        questions = (
            db.table("checklist_questions")
            .select("id")
            .eq("task_id", task["id"])
            .execute()
            .data or []
        )

        answers = (
            db.table("checklist_answers")
            .select("id, answer")
            .eq("assignment_id", assignment["id"])
            .execute()
            .data or []
        )

        response.append({
            **assignment,
            "task": task,
            "question_count": len(questions),
            "answered_count": sum(
                item.get("answer") is not None
                for item in answers
            ),
        })

    return response


# =========================================================
# ADMIN: DETAIL TUGAS
# =========================================================

@router.get("/{task_id}")
def get_checklist_task(
    task_id: str,
    _=Depends(require_admin),
):
    task = get_task_or_404(task_id)

    questions = (
        db.table("checklist_questions")
        .select("*")
        .eq("task_id", task_id)
        .order("sort_order")
        .execute()
        .data or []
    )

    assignments = (
        db.table("checklist_assignments")
        .select("*")
        .eq("task_id", task_id)
        .order("assigned_at", desc=True)
        .execute()
        .data or []
    )

    recipient_ids = list({
        item["recipient_id"] for item in assignments
    })

    profiles_by_id = {}

    if recipient_ids:
        profiles = (
            db.table("profiles")
            .select("id, username, full_name, email, role")
            .in_("id", recipient_ids)
            .execute()
            .data or []
        )

        profiles_by_id = {
            item["id"]: item for item in profiles
        }

    return {
        **task,
        "question_count": len(questions),
        "questions": questions,
        "assignments": [
            {
                **item,
                "recipient": profiles_by_id.get(
                    item["recipient_id"]
                ),
            }
            for item in assignments
        ],
    }


@router.patch("/{task_id}")
def update_checklist_task(
    task_id: str,
    payload: ChecklistTaskUpdate,
    _=Depends(require_admin),
):
    task = get_task_or_404(task_id)

    data = payload.model_dump(
        mode="json",
        exclude_unset=True,
    )

    if not data:
        raise HTTPException(
            status_code=400,
            detail="Tidak ada data yang diperbarui.",
        )

    for field in ("title", "opens_at", "closes_at", "status"):
        if field in data and data[field] is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field} tidak boleh kosong.",
            )

    opens_value = data.get("opens_at", task["opens_at"])
    closes_value = data.get("closes_at", task["closes_at"])

    opens_at = datetime.fromisoformat(
        opens_value.replace("Z", "+00:00")
    )

    closes_at = datetime.fromisoformat(
        closes_value.replace("Z", "+00:00")
    )

    if closes_at <= opens_at:
        raise HTTPException(
            status_code=422,
            detail="Waktu tutup harus setelah waktu buka.",
        )

    if data.get("status") == "published":
        questions = (
            db.table("checklist_questions")
            .select("id")
            .eq("task_id", task_id)
            .execute()
            .data or []
        )

        assignments = (
            db.table("checklist_assignments")
            .select("id")
            .eq("task_id", task_id)
            .execute()
            .data or []
        )

        if not questions or not assignments:
            raise HTTPException(
                status_code=400,
                detail="Tambahkan soal dan penerima sebelum publikasi.",
            )

    data["updated_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    result = (
        db.table("checklist_tasks")
        .update(data)
        .eq("id", task_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Tugas gagal diperbarui.",
        )

    return result.data


# =========================================================
# ADMIN: TAMBAH SOAL
# =========================================================

@router.post("/{task_id}/questions")
def add_checklist_question(
    task_id: str,
    payload: ChecklistQuestionCreate,
    _=Depends(require_admin),
):
    task = get_task_or_404(task_id)

    if task["status"] != "draft":
        raise HTTPException(
            status_code=409,
            detail="Soal hanya dapat ditambahkan saat tugas berstatus draft.",
        )

    existing = (
        db.table("checklist_questions")
        .select("id")
        .eq("task_id", task_id)
        .eq("sort_order", payload.sort_order)
        .limit(1)
        .execute()
        .data or []
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Nomor urut soal sudah digunakan.",
        )

    data = payload.model_dump(
        mode="json",
        exclude_none=True,
    )
    data["task_id"] = task_id

    result = (
        db.table("checklist_questions")
        .insert(data)
        .execute()
    )

    rows = result.data or []

    if not rows:
        raise HTTPException(
            status_code=500,
            detail="Soal gagal ditambahkan.",
        )

    return rows[0]


# =========================================================
# ADMIN: TAMBAH PENERIMA
# =========================================================

@router.post("/{task_id}/recipients")
def assign_checklist_recipients(
    task_id: str,
    payload: ChecklistRecipientsCreate,
    _=Depends(require_admin),
):
    task = get_task_or_404(task_id)

    if task["status"] != "draft":
        raise HTTPException(
            status_code=409,
            detail="Penerima hanya dapat diatur saat tugas berstatus draft.",
        )

    recipient_ids = list(dict.fromkeys(
        str(item) for item in payload.recipient_ids
    ))

    profiles = (
        db.table("profiles")
        .select("id, full_name, email, role")
        .in_("id", recipient_ids)
        .execute()
        .data or []
    )

    profiles_by_id = {
        item["id"]: item for item in profiles
    }

    missing = [
        user_id for user_id in recipient_ids
        if user_id not in profiles_by_id
    ]

    if missing:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Profil penerima tidak ditemukan.",
                "user_ids": missing,
            },
        )

    invalid_roles = [
        item["id"]
        for item in profiles
        if item["role"] not in RECIPIENT_ROLES
    ]

    if invalid_roles:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Penerima harus Tour Leader atau Muthawif.",
                "user_ids": invalid_roles,
            },
        )

    existing = (
        db.table("checklist_assignments")
        .select("recipient_id")
        .eq("task_id", task_id)
        .in_("recipient_id", recipient_ids)
        .execute()
        .data or []
    )

    existing_ids = {
        item["recipient_id"] for item in existing
    }

    new_ids = [
        user_id for user_id in recipient_ids
        if user_id not in existing_ids
    ]

    if not new_ids:
        raise HTTPException(
            status_code=409,
            detail="Semua penerima sudah ditugaskan.",
        )

    result = (
        db.table("checklist_assignments")
        .insert([
            {
                "task_id": task_id,
                "recipient_id": user_id,
                "status": "assigned",
            }
            for user_id in new_ids
        ])
        .execute()
    )

    return {
        "message": "Penerima berhasil ditambahkan.",
        "added_count": len(result.data or []),
        "data": result.data or [],
    }


# =========================================================
# ADMIN: DAFTAR PENUGASAN
# =========================================================

@router.get("/{task_id}/assignments")
def get_checklist_assignments(
    task_id: str,
    _=Depends(require_admin),
):
    get_task_or_404(task_id)

    assignments = (
        db.table("checklist_assignments")
        .select("*")
        .eq("task_id", task_id)
        .order("assigned_at", desc=True)
        .execute()
        .data or []
    )

    questions = (
        db.table("checklist_questions")
        .select("id")
        .eq("task_id", task_id)
        .execute()
        .data or []
    )

    recipients = list({
        item["recipient_id"] for item in assignments
    })

    profiles_by_id = {}

    if recipients:
        profiles = (
            db.table("profiles")
            .select("id, username, full_name, email, role")
            .in_("id", recipients)
            .execute()
            .data or []
        )

        profiles_by_id = {
            item["id"]: item for item in profiles
        }

    response = []

    for assignment in assignments:
        answers = (
            db.table("checklist_answers")
            .select("id, answer")
            .eq("assignment_id", assignment["id"])
            .execute()
            .data or []
        )

        response.append({
            **assignment,
            "recipient": profiles_by_id.get(
                assignment["recipient_id"]
            ),
            "question_count": len(questions),
            "answered_count": sum(
                item.get("answer") is not None
                for item in answers
            ),
        })

    return response


# =========================================================
# PENERIMA: DETAIL TUGAS
# =========================================================

@router.get("/assignments/{assignment_id}")
def get_my_assignment_detail(
    assignment_id: str,
    current=Depends(get_current_user),
):
    assignment, task = get_owned_assignment(
        assignment_id,
        current,
    )

    questions = (
        db.table("checklist_questions")
        .select("*")
        .eq("task_id", task["id"])
        .order("sort_order")
        .execute()
        .data or []
    )

    answers = (
        db.table("checklist_answers")
        .select("*")
        .eq("assignment_id", assignment_id)
        .execute()
        .data or []
    )

    answers_by_question = {
        item["question_id"]: item
        for item in answers
    }

    return {
        "assignment": assignment,
        "task": task,
        "questions": [
            {
                **question,
                "saved_answer": (
                    answers_by_question[question["id"]]["answer"]
                    if question["id"] in answers_by_question
                    else None
                ),
            }
            for question in questions
        ],
    }


# =========================================================
# PENERIMA: SIMPAN JAWABAN
# =========================================================

@router.put("/assignments/{assignment_id}/answers")
def save_my_answer(
    assignment_id: str,
    payload: ChecklistAnswerCreate,
    current=Depends(get_current_user),
):
    assignment, task = get_owned_assignment(
        assignment_id,
        current,
    )

    check_task_open(task)

    if assignment["status"] == "submitted":
        raise HTTPException(
            status_code=409,
            detail="Tugas sudah dikumpulkan.",
        )

    question = (
        db.table("checklist_questions")
        .select("*")
        .eq("id", str(payload.question_id))
        .eq("task_id", task["id"])
        .limit(1)
        .execute()
        .data or []
    )

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Soal tidak ditemukan dalam tugas ini.",
        )

    check_answer_format(question[0], payload.answer)

    now = datetime.now(timezone.utc).isoformat()

    data = {
        "assignment_id": assignment_id,
        "question_id": str(payload.question_id),
        "answer": payload.answer,
        "answered_at": now,
    }

    result = (
        db.table("checklist_answers")
        .upsert(
            data,
            on_conflict="assignment_id,question_id",
        )
        .execute()
    )

    if assignment["status"] == "assigned":
        (
            db.table("checklist_assignments")
            .update({
                "status": "in_progress",
                "started_at": now,
            })
            .eq("id", assignment_id)
            .execute()
        )

    return {
        "message": "Jawaban berhasil disimpan.",
        "data": result.data or [],
    }


# =========================================================
# PENERIMA: KUMPULKAN TUGAS
# =========================================================

@router.post("/assignments/{assignment_id}/submit")
def submit_my_assignment(
    assignment_id: str,
    current=Depends(get_current_user),
):
    assignment, task = get_owned_assignment(
        assignment_id,
        current,
    )

    check_task_open(task)

    if assignment["status"] == "submitted":
        raise HTTPException(
            status_code=409,
            detail="Tugas sudah dikumpulkan.",
        )

    questions = (
        db.table("checklist_questions")
        .select("id, is_required")
        .eq("task_id", task["id"])
        .execute()
        .data or []
    )

    answers = (
        db.table("checklist_answers")
        .select("question_id, answer")
        .eq("assignment_id", assignment_id)
        .execute()
        .data or []
    )

    if not questions:
        raise HTTPException(
            status_code=400,
            detail="Tugas belum memiliki soal.",
        )

    answered_ids = {
        item["question_id"]
        for item in answers
        if item.get("answer") is not None
    }

    missing_required = [
        item["id"]
        for item in questions
        if item["is_required"]
        and item["id"] not in answered_ids
    ]

    if missing_required:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Masih ada soal wajib yang belum dijawab.",
                "question_ids": missing_required,
            },
        )

    result = (
        db.table("checklist_assignments")
        .update({
            "status": "submitted",
            "submitted_at": datetime.now(
                timezone.utc
            ).isoformat(),
        })
        .eq("id", assignment_id)
        .execute()
    )

    return {
        "message": "Tugas berhasil dikumpulkan.",
        "data": result.data or [],
    }


# =========================================================
# ADMIN: LIHAT JAWABAN PENERIMA
# =========================================================

@router.get("/assignments/{assignment_id}/answers")
def get_assignment_answers(
    assignment_id: str,
    _=Depends(require_admin),
):
    assignment = get_assignment_or_404(assignment_id)

    answers = (
        db.table("checklist_answers")
        .select("*")
        .eq("assignment_id", assignment_id)
        .execute()
        .data or []
    )

    question_ids = list({
        item["question_id"] for item in answers
    })

    questions_by_id = {}

    if question_ids:
        questions = (
            db.table("checklist_questions")
            .select(
                "id, question_text, answer_type, sort_order"
            )
            .in_("id", question_ids)
            .execute()
            .data or []
        )

        questions_by_id = {
            item["id"]: item for item in questions
        }

    return {
        "assignment": assignment,
        "answers": [
            {
                **answer,
                "question": questions_by_id.get(
                    answer["question_id"]
                ),
            }
            for answer in answers
        ],
    }