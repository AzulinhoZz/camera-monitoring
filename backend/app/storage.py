from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from app.auth import get_current_user
from app.retention_manager import retention_manager

router = APIRouter(prefix="/storage", tags=["Storage"])


class RetentionConfigPayload(BaseModel):
    retention_days: int = Field(default=30)
    auto_cleanup_enabled: bool = Field(default=False)


class EventProtectPayload(BaseModel):
    is_protected: bool = Field(default=True)


@router.get("/stats")
def get_storage_stats(user: dict = Depends(get_current_user)):
    try:
        return retention_manager.get_storage_stats(user["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas de almacenamiento: {str(e)}")


@router.put("/retention")
def update_retention_policy(
    payload: RetentionConfigPayload,
    user: dict = Depends(get_current_user)
):
    try:
        return retention_manager.set_user_config(
            user_id=user["id"],
            retention_days=payload.retention_days,
            auto_cleanup_enabled=payload.auto_cleanup_enabled
        )
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar política de retención: {str(e)}")


@router.post("/cleanup")
def trigger_storage_cleanup(
    dry_run: bool = Query(True),
    user: dict = Depends(get_current_user)
):
    try:
        return retention_manager.cleanup_expired_evidence(user_id=user["id"], dry_run=dry_run)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al ejecutar limpieza de almacenamiento: {str(e)}")


@router.post("/events/{event_id}/protect")
def set_event_protection_status(
    event_id: str,
    payload: EventProtectPayload,
    user: dict = Depends(get_current_user)
):
    try:
        return retention_manager.set_event_protection(
            user_id=user["id"],
            event_id=event_id,
            is_protected=payload.is_protected
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar protección de evento: {str(e)}")
