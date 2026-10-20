import os
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth import get_current_user
from app.camera_config import config_store
from app.motion_detector import motion_manager

router = APIRouter(prefix="/cameras", tags=["Cameras"])


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    rtsp_url: str = Field(min_length=10, max_length=2048)


def _format_camera(record: dict) -> dict:
    rtsp_url = record.get("rtsp_url", "")
    parsed = urlsplit(rtsp_url)
    path = parsed.path.lstrip('/') if parsed and parsed.path else ""
    if not path:
        path = f"cam_{record['id'][:8]}"

    cfg = config_store.get_config(record["id"])

    return {
        "id": record["id"],
        "user_id": record.get("user_id"),
        "name": record["name"],
        "rtsp_url": rtsp_url,
        "status": record.get("status", "online"),
        "created_at": record.get("created_at"),
        "stream_path": path,
        "hls_url": f"http://10.0.2.2:8888/{path}/index.m3u8",
        "motion_enabled": cfg.get("motion_enabled", True)
    }


@router.post("", status_code=201)
def create_camera(
    camera: CameraCreate,
    user: dict = Depends(get_current_user),
):
    parsed = urlsplit(camera.rtsp_url)

    if parsed.scheme not in ("rtsp", "rtsps") or not parsed.hostname:
        raise HTTPException(
            status_code=422,
            detail="Se requiere una URL RTSP válida",
        )

    if parsed.username or parsed.password:
        raise HTTPException(
            status_code=422,
            detail="Por ahora, utiliza una URL RTSP sin credenciales",
        )

    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SECRET_KEY"],
    )

    result = client.table("cameras").insert({
        "user_id": user["id"],
        "name": camera.name.strip(),
        "rtsp_url": camera.rtsp_url,
        "status": "online",
    }).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Error al crear la cámara")

    rec = result.data[0]

    # Automatically start motion detector worker for new camera by default
    motion_manager.start_detector(
        camera_id=rec["id"],
        rtsp_url=rec["rtsp_url"],
        min_area=1500,
        threshold=25,
        cooldown_seconds=5.0
    )

    return _format_camera(rec)


@router.get("")
def list_cameras(user: dict = Depends(get_current_user)):
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        result = (
            client.table("cameras")
            .select("id,user_id,name,rtsp_url,status,created_at")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )

        formatted = [_format_camera(rec) for rec in result.data]

        return {
            "total": len(formatted),
            "cameras": formatted,
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudieron consultar las cámaras: {str(e)}",
        )


@router.get("/{camera_id}")
def get_camera(camera_id: str, user: dict = Depends(get_current_user)):
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        result = (
            client.table("cameras")
            .select("id,user_id,name,rtsp_url,status,created_at")
            .eq("id", camera_id)
            .eq("user_id", user["id"])
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")

        return _format_camera(result.data[0])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener la cámara: {str(e)}",
        )


@router.delete("/{camera_id}")
def delete_camera(camera_id: str, user: dict = Depends(get_current_user)):
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        # Stop worker and delete config
        motion_manager.stop_detector(camera_id)
        config_store.delete_config(camera_id)

        result = (
            client.table("cameras")
            .delete()
            .eq("id", camera_id)
            .eq("user_id", user["id"])
            .execute()
        )

        return {"message": "Cámara eliminada correctamente"}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar la cámara: {str(e)}",
        )
