import os
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth import get_current_user
from app.streaming import issue_stream, stream_path
from app.rtsp_policy import policy_rtsp_url
from app.camera_config import config_store
from app.connectivity_checker import check_and_update_camera
from app.motion_detector import motion_manager
from app.permissions import has_camera_access, can_manage_camera, get_authorized_camera_ids

router = APIRouter(prefix="/cameras", tags=["Cameras"])


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    rtsp_url: str = Field(min_length=10, max_length=2048)


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    rtsp_url: Optional[str] = Field(None, min_length=1, max_length=2048)


def _format_camera(record: dict, user: Optional[dict] = None) -> dict:
    rtsp_url = record.get("rtsp_url", "")
    parsed = urlsplit(rtsp_url)
    path = stream_path(record["id"])
    # Remove any legacy userinfo/query credentials from client-visible data.
    host = parsed.hostname or ""
    host = f"[{host}]" if ":" in host else host
    port = f":{parsed.port}" if parsed.port else ""
    safe_rtsp_url = urlunsplit((parsed.scheme, host + port, parsed.path, "", ""))

    cfg = config_store.get_config(record["id"])

    result = {
        "id": record["id"],
        "user_id": record.get("user_id"),
        "name": record["name"],
        "rtsp_url": safe_rtsp_url,
        "status": record.get("status", "online"),
        "last_seen_at": record.get("last_seen_at") or record.get("created_at"),
        "created_at": record.get("created_at"),
        "stream_path": path,
        "hls_url": None,
        "motion_enabled": cfg.get("motion_enabled", True)
    }

    if user:
        try:
            result.update(issue_stream(user["id"], record))
        except RuntimeError:
            pass  # CRUD remains available; streaming fails closed until configured.
    return result


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

    try:
        policy_rtsp_url(camera.rtsp_url)
    except (ValueError, OSError):
        raise HTTPException(status_code=422, detail="Destino RTSP no autorizado por el servidor") from None

    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SECRET_KEY"],
    )

    insert_data = {
        "user_id": user["id"],
        "name": camera.name.strip(),
        "rtsp_url": camera.rtsp_url,
        "status": "online",
    }
    if user.get("organization_id"):
        insert_data["organization_id"] = user.get("organization_id")

    result = client.table("cameras").insert(insert_data).execute()

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

    return _format_camera(rec, user)


@router.get("")
def list_cameras(user: dict = Depends(get_current_user)):
    try:
        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        auth_ids = get_authorized_camera_ids(user)
        if not auth_ids:
            return {"total": 0, "cameras": []}

        result = (
            client.table("cameras")
            .select("id,user_id,organization_id,name,rtsp_url,status,created_at,last_seen_at")
            .in_("id", auth_ids)
            .order("created_at", desc=True)
            .execute()
        )

        formatted = [_format_camera(rec, user) for rec in result.data]

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
        if not has_camera_access(user, camera_id):
            raise HTTPException(status_code=404, detail="Cámara no encontrada o no tiene permisos")

        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        result = (
            client.table("cameras")
            .select("id,user_id,organization_id,name,rtsp_url,status,created_at,last_seen_at")
            .eq("id", camera_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Cámara no encontrada o no tiene permisos")

        return _format_camera(result.data[0], user)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener la cámara: {str(e)}",
        )


@router.get("/{camera_id}/stream-url")
def get_camera_stream_url(camera_id: str, user: dict = Depends(get_current_user)):
    if not has_camera_access(user, camera_id):
        raise HTTPException(status_code=403, detail="No tiene permisos para acceder a la transmisión de esta cámara")

    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SECRET_KEY"],
    )

    result = client.table("cameras").select("id, user_id, organization_id, name, rtsp_url").eq("id", camera_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    formatted = _format_camera(result.data[0], user)
    if not formatted["hls_url"]:
        raise HTTPException(status_code=503, detail="Streaming no configurado")
    return {
        "camera_id": camera_id,
        "stream_token": formatted["stream_token"],
        "stream_expires_at": formatted["stream_expires_at"],
        "hls_url": formatted["hls_url"],
        "stream_path": formatted["stream_path"]
    }


@router.post("/{camera_id}/check-connection")
def check_camera_connection_endpoint(camera_id: str, user: dict = Depends(get_current_user)):
    try:
        if not has_camera_access(user, camera_id):
            raise HTTPException(status_code=404, detail="Cámara no encontrada o no tiene permisos")

        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        result = (
            client.table("cameras")
            .select("id,user_id,name,rtsp_url")
            .eq("id", camera_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Cámara no encontrada o no tiene permisos")

        cam = result.data[0]
        check_and_update_camera(cam["id"], cam["rtsp_url"])

        fresh_res = client.table("cameras").select("*").eq("id", camera_id).execute()
        return _format_camera(fresh_res.data[0], user)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al verificar la conexión: {str(e)}",
        )


@router.put("/{camera_id}")
def update_camera(
    camera_id: str,
    camera_update: CameraUpdate,
    user: dict = Depends(get_current_user),
):
    try:
        if not can_manage_camera(user, camera_id):
            raise HTTPException(status_code=404, detail="Cámara no encontrada o no tiene permisos")

        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        existing_res = (
            client.table("cameras")
            .select("id, name, rtsp_url, user_id, organization_id")
            .eq("id", camera_id)
            .execute()
        )

        if not existing_res.data:
            raise HTTPException(status_code=404, detail="Cámara no encontrada o no tiene permisos")

        existing_cam = existing_res.data[0]
        update_data = {}

        if camera_update.name is not None and camera_update.name.strip():
            update_data["name"] = camera_update.name.strip()

        if camera_update.rtsp_url is not None and camera_update.rtsp_url.strip():
            parsed = urlsplit(camera_update.rtsp_url.strip())
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
            try:
                policy_rtsp_url(camera_update.rtsp_url.strip())
            except (ValueError, OSError):
                raise HTTPException(status_code=422, detail="Destino RTSP no autorizado por el servidor") from None
            update_data["rtsp_url"] = camera_update.rtsp_url.strip()

        if not update_data:
            return _format_camera(existing_cam, user)

        res = (
            client.table("cameras")
            .update(update_data)
            .eq("id", camera_id)
            .execute()
        )

        if not res.data:
            raise HTTPException(status_code=500, detail="Error al actualizar la cámara")

        updated_record = res.data[0]

        if "rtsp_url" in update_data and update_data["rtsp_url"] != existing_cam["rtsp_url"]:
            cfg = config_store.get_config(camera_id)
            if cfg.get("motion_enabled", True):
                motion_manager.stop_detector(camera_id)
                motion_manager.start_detector(
                    camera_id=camera_id,
                    rtsp_url=updated_record["rtsp_url"],
                    min_area=cfg.get("min_area", 1500),
                    threshold=cfg.get("threshold", 25),
                    cooldown_seconds=cfg.get("cooldown_seconds", 5.0),
                )

        return _format_camera(updated_record, user)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar la cámara: {str(e)}",
        )


@router.delete("/{camera_id}")
def delete_camera(camera_id: str, user: dict = Depends(get_current_user)):
    try:
        if not can_manage_camera(user, camera_id):
            raise HTTPException(status_code=404, detail="Cámara no encontrada o no tiene permisos")

        client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        motion_manager.stop_detector(camera_id)
        config_store.delete_config(camera_id)

        client.table("cameras").delete().eq("id", camera_id).execute()

        return {"message": "Cámara eliminada correctamente"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar la cámara: {str(e)}",
        )
