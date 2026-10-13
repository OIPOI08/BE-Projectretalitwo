from fastapi import APIRouter, Depends, HTTPException
from ..dependencies import require_admin
from ..schemas import TaskCreate
from ..supabase import db

router = APIRouter(prefix="/api/tasks", tags=["Tugas"])

@router.get("")
def get_tasks(_=Depends(require_admin)):
    return db.table("tasks").select("*, profiles(full_name), kloter(name)").order("created_at", desc=True).execute().data

@router.post("")
def create_task(payload: TaskCreate, _=Depends(require_admin)):
    result = db.table("tasks").insert(payload.model_dump()).execute()
    return result.data

@router.patch("/{task_id}")
def update_task(task_id: str, payload: TaskCreate, _=Depends(require_admin)):
    result = db.table("tasks").update(payload.model_dump(exclude_none=True)).eq("id", task_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Tugas tidak ditemukan.")
    return result.data

@router.delete("/{task_id}")
def delete_task(task_id: str, _=Depends(require_admin)):
    result = db.table("tasks").delete().eq("id", task_id).execute()
    return {"message": "Tugas dihapus", "data": result.data}
