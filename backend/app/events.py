import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth import get_current_user
from app.permissions import has_camera_access, can_manage_camera, get_authorized_camera_ids

router = APIRouter(prefix="/events", tags=["Events"])


class EventCreate(BaseModel):
    camera_id: str
    event_type: str = Field(default="motion_detected")
    description: Optional[str] = "Movimiento detectado por OpenCV"


class ReviewAlertPayload(BaseModel):
    review_status: str = Field(pattern="^(reviewed_ok|help_requested)$")


@router.get("")
def list_events(
    camera_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        auth_camera_ids = get_authorized_camera_ids(user)
        if not auth_camera_ids:
            return {"total": 0, "events": []}

        if camera_id:
            if not has_camera_access(user, camera_id):
                raise HTTPException(status_code=403, detail="No tiene acceso a esta cámara")
            target_ids = [camera_id]
        else:
            target_ids = auth_camera_ids

        user_cameras = (
            client.table("cameras")
            .select("id, name")
            .in_("id", target_ids)
            .execute()
        )
        camera_map = {cam["id"]: cam["name"] for cam in (user_cameras.data or [])}

        result = (
            client.table("camera_events")
            .select("id, camera_id, event_type, detected_at, description, evidence_path, clip_path, is_protected, review_status, reviewed_at")
            .in_("camera_id", target_ids)
            .order("detected_at", desc=True)
            .limit(100)
            .execute()
        )

        events = []
        for record in result.data or []:
            cam_id = record.get("camera_id")
            ev_path = record.get("evidence_path")
            cl_path = record.get("clip_path")
            events.append({
                "id": record.get("id"),
                "camera_id": cam_id,
                "camera_name": camera_map.get(cam_id, "Cámara desconocida"),
                "event_type": record.get("event_type", "motion_detected"),
                "detected_at": record.get("detected_at"),
                "description": record.get("description", "Movimiento detectado"),
                "evidence_path": ev_path,
                "has_evidence": bool(ev_path),
                "clip_path": cl_path,
                "has_clip": bool(cl_path),
                "is_protected": bool(record.get("is_protected", False)),
                "review_status": record.get("review_status", "pending"),
                "reviewed_at": record.get("reviewed_at"),
            })

        return {
            "total": len(events),
            "events": events,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al listar los eventos: {str(e)}",
        )


@router.post("/{event_id}/review")
def review_event_alert(
    event_id: str,
    payload: ReviewAlertPayload,
    user: dict = Depends(get_current_user),
):
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        ev_res = client.table("camera_events").select("id, camera_id").eq("id", event_id).execute()
        if not ev_res.data:
            raise HTTPException(status_code=404, detail="Evento no encontrado")

        camera_id = ev_res.data[0]["camera_id"]
        if not has_camera_access(user, camera_id):
            raise HTTPException(status_code=403, detail="No tiene permisos para revisar este evento")

        now_iso = datetime.now(timezone.utc).isoformat()
        result = client.table("camera_events").update({
            "review_status": payload.review_status,
            "reviewed_at": now_iso
        }).eq("id", event_id).execute()
        if not result.data:
            raise HTTPException(status_code=503, detail="No se pudo guardar la revisión")

        return {
            "event_id": event_id,
            "review_status": payload.review_status,
            "reviewed_at": now_iso
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al registrar la revisión del evento: {str(e)}",
        )


@router.get("/{event_id}/evidence")
def get_event_evidence(
    event_id: str,
    user: dict = Depends(get_current_user),
):
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        event_res = (
            client.table("camera_events")
            .select("id, camera_id, evidence_path")
            .eq("id", event_id)
            .execute()
        )

        if not event_res.data:
            raise HTTPException(status_code=404, detail="Evento no encontrado")

        event = event_res.data[0]
        camera_id = event.get("camera_id")
        evidence_path = event.get("evidence_path")

        if not has_camera_access(user, camera_id):
            raise HTTPException(status_code=403, detail="No tiene permisos para acceder a esta evidencia")

        if not evidence_path:
            return {"event_id": event_id, "has_evidence": False, "signed_url": None}

        signed_url = None
        try:
            res = client.storage.from_("motion-evidence").create_signed_url(evidence_path, 1800)
            if isinstance(res, dict):
                signed_url = res.get("signedURL") or res.get("signedUrl") or res.get("signed_url")
            elif isinstance(res, str):
                signed_url = res
        except Exception as st_err:
            pass

        return {
            "event_id": event_id,
            "has_evidence": True,
            "evidence_path": evidence_path,
            "signed_url": signed_url
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener evidencia del evento: {str(e)}",
        )


@router.get("/{event_id}/clip")
def get_event_clip(
    event_id: str,
    user: dict = Depends(get_current_user),
):
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        event_res = (
            client.table("camera_events")
            .select("id, camera_id, clip_path")
            .eq("id", event_id)
            .execute()
        )

        if not event_res.data:
            raise HTTPException(status_code=404, detail="Evento no encontrado")

        event = event_res.data[0]
        camera_id = event.get("camera_id")
        clip_path = event.get("clip_path")

        if not has_camera_access(user, camera_id):
            raise HTTPException(status_code=403, detail="No tiene permisos para acceder a este clip")

        if not clip_path:
            return {"event_id": event_id, "has_clip": False, "signed_url": None}

        signed_url = None
        try:
            res = client.storage.from_("motion-clips").create_signed_url(clip_path, 1800)
            if isinstance(res, dict):
                signed_url = res.get("signedURL") or res.get("signedUrl") or res.get("signed_url")
            elif isinstance(res, str):
                signed_url = res
        except Exception as st_err:
            pass

        return {
            "event_id": event_id,
            "has_clip": True,
            "clip_path": clip_path,
            "signed_url": signed_url
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener clip del evento: {str(e)}",
        )


@router.post("", status_code=201)
def create_event(
    event: EventCreate,
    user: dict = Depends(get_current_user),
):
    try:
        if not can_manage_camera(user, event.camera_id):
            raise HTTPException(status_code=403, detail="Cámara no encontrada o no pertenece al usuario")

        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        res = (
            client.table("camera_events")
            .insert({
                "camera_id": event.camera_id,
                "event_type": event.event_type,
                "description": event.description,
            })
            .execute()
        )

        if not res.data:
            raise HTTPException(status_code=500, detail="Error al registrar el evento")

        record = res.data[0]

        return {
            "id": record.get("id"),
            "camera_id": record.get("camera_id"),
            "event_type": record.get("event_type"),
            "detected_at": record.get("detected_at"),
            "description": record.get("description"),
            "review_status": record.get("review_status", "pending"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear el evento: {str(e)}",
        )
