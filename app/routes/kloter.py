from fastapi import APIRouter, Depends, HTTPException
from ..dependencies import require_admin
from ..schemas import KloterCreate
from ..supabase import db

router = APIRouter(prefix="/api/kloter", tags=["Kloter"])

@router.get("")
def get_kloter(_=Depends(require_admin)):
    return db.table("kloter").select("*").order("created_at", desc=True).execute().data

@router.post("")
def create_kloter(payload: KloterCreate, _=Depends(require_admin)):
    result = db.table("kloter").insert(payload.model_dump()).execute()
    return result.data

@router.patch("/{kloter_id}")
def update_kloter(kloter_id: str, payload: KloterCreate, _=Depends(require_admin)):
    result = db.table("kloter").update(payload.model_dump(exclude_none=True)).eq("id", kloter_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Kloter tidak ditemukan.")
    return result.data

@router.delete("/{kloter_id}")
def delete_kloter(kloter_id: str, _=Depends(require_admin)):
    result = db.table("kloter").delete().eq("id", kloter_id).execute()
    return {"message": "Kloter dihapus", "data": result.data}
