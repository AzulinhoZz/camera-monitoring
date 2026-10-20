import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth import get_current_user

router = APIRouter(prefix="/events", tags=["Events"])


class EventCreate(BaseModel):
    camera_id: str
    event_type: str = Field(default="motion_detected")
    description: Optional[str] = "Movimiento detectado por OpenCV"


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

        # Get all cameras belonging to the user
        user_cameras = (
            client.table("cameras")
            .select("id, name")
            .eq("user_id", user["id"])
            .execute()
        )

        camera_map = {cam["id"]: cam["name"] for cam in user_cameras.data}

        if not camera_map:
            return {"total": 0, "events": []}

        valid_camera_ids = list(camera_map.keys())

        if camera_id:
            if camera_id not in camera_map:
                raise HTTPException(status_code=403, detail="No tiene acceso a esta cámara")
            target_ids = [camera_id]
        else:
            target_ids = valid_camera_ids

        result = (
            client.table("camera_events")
            .select("id, camera_id, event_type, detected_at, description")
            .in_("camera_id", target_ids)
            .order("detected_at", desc=True)
            .limit(100)
            .execute()
        )

        events = []
        for record in result.data:
            cam_id = record.get("camera_id")
            events.append({
                "id": record.get("id"),
                "camera_id": cam_id,
                "camera_name": camera_map.get(cam_id, "Cámara desconocida"),
                "event_type": record.get("event_type", "motion_detected"),
                "detected_at": record.get("detected_at"),
                "description": record.get("description", "Movimiento detectado"),
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


@router.post("", status_code=201)
def create_event(
    event: EventCreate,
    user: dict = Depends(get_current_user),
):
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        # Verify camera ownership
        cam_res = (
            client.table("cameras")
            .select("id, name, user_id")
            .eq("id", event.camera_id)
            .eq("user_id", user["id"])
            .execute()
        )

        if not cam_res.data:
            raise HTTPException(status_code=404, detail="Cámara no encontrada o no pertenece al usuario")

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
            "camera_name": cam_res.data[0]["name"],
            "event_type": record.get("event_type"),
            "detected_at": record.get("detected_at"),
            "description": record.get("description"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear el evento: {str(e)}",
        )
