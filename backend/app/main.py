import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth import get_current_user, router as auth_router
from app.stream_proxy import router as stream_router
from app.cameras import router as cameras_router
from app.events import router as events_router
from app.storage import router as storage_router
from app.admin import router as admin_router
from app.vision_api import router as vision_router
from app.motion_detector import motion_manager
from app.connectivity_checker import health_checker
from app.schedule_evaluator import SENSITIVITY_PRESETS
from app.zone_store import zone_store, validate_polygon

app = FastAPI(title="Camera Monitoring API", version="1.0.0")

app.include_router(auth_router)
app.include_router(stream_router)
app.include_router(cameras_router)
app.include_router(events_router)
app.include_router(storage_router)
app.include_router(admin_router)
app.include_router(vision_router)


class MotionConfigPayload(BaseModel):
    action: str = Field(default="start")
    sensitivity_preset: Optional[str] = Field(default="medium")
    min_area: Optional[int] = Field(default=1500, ge=100, le=100000)
    threshold: Optional[int] = Field(default=25, ge=5, le=255)
    cooldown_seconds: Optional[float] = Field(default=5.0, ge=1.0, le=300.0)
    schedule_type: Optional[str] = Field(default="24/7")
    schedule_days: Optional[List[str]] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
    start_time: Optional[str] = Field(default="00:00:00")
    end_time: Optional[str] = Field(default="23:59:59")
    timezone: Optional[str] = Field(default="America/Mexico_City")


class PointModel(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class ZoneCreatePayload(BaseModel):
    name: str = Field(default="Zona de Detección", min_length=1, max_length=100)
    polygon: List[PointModel] = Field(min_length=3)


class ZoneUpdatePayload(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    polygon: Optional[List[PointModel]] = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "camera-monitoring-api"}


@app.get("/health/db")
def database_health():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    try:
        client = create_client(url, key)
        client.table("cameras").select("id").limit(1).execute()
        return {"status": "ok", "database": "supabase"}
    except Exception:
        raise HTTPException(status_code=503, detail="Supabase connection failed")


@app.get("/auth/me")
def current_user(user: dict = Depends(get_current_user)):
    return user


@app.get("/cameras/{camera_id}/detect-motion")
def get_motion_detection_status(
    camera_id: str,
    user: dict = Depends(get_current_user),
):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    client = create_client(url, key)

    cam_res = (
        client.table("cameras")
        .select("id, user_id")
        .eq("id", camera_id)
        .eq("user_id", user["id"])
        .execute()
    )

    if not cam_res.data:
        raise HTTPException(status_code=404, detail="Cámara no encontrada o no tiene permisos")

    return motion_manager.get_status(camera_id)


@app.post("/cameras/{camera_id}/detect-motion")
def trigger_motion_detection(
    camera_id: str,
    payload: MotionConfigPayload = MotionConfigPayload(),
    user: dict = Depends(get_current_user),
):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    client = create_client(url, key)

    cam_res = (
        client.table("cameras")
        .select("id, name, rtsp_url, user_id")
        .eq("id", camera_id)
        .eq("user_id", user["id"])
        .execute()
    )

    if not cam_res.data:
        raise HTTPException(status_code=404, detail="Cámara no encontrada o no tiene permisos")

    camera = cam_res.data[0]

    if payload.action == "start":
        preset = payload.sensitivity_preset or "medium"
        if preset in SENSITIVITY_PRESETS:
            p = SENSITIVITY_PRESETS[preset]
            min_area = p["min_area"]
            threshold = p["threshold"]
            cooldown_seconds = p["cooldown_seconds"]
        else:
            min_area = payload.min_area or 1500
            threshold = payload.threshold or 25
            cooldown_seconds = payload.cooldown_seconds or 5.0

        res = motion_manager.start_detector(
            camera_id=camera["id"],
            rtsp_url=camera["rtsp_url"],
            min_area=min_area,
            threshold=threshold,
            cooldown_seconds=cooldown_seconds,
            sensitivity_preset=preset,
            schedule_type=payload.schedule_type or "24/7",
            schedule_days=payload.schedule_days,
            start_time=payload.start_time or "00:00:00",
            end_time=payload.end_time or "23:59:59",
            timezone=payload.timezone or "America/Mexico_City",
        )
        return res
    else:
        res = motion_manager.stop_detector(camera_id)
        return res


# Zone Management Endpoints
def _verify_camera_owner(camera_id: str, user_id: str):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    client = create_client(url, key)

    cam_res = (
        client.table("cameras")
        .select("id")
        .eq("id", camera_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not cam_res.data:
        raise HTTPException(status_code=404, detail="Cámara no encontrada o no tiene permisos")


@app.get("/cameras/{camera_id}/zones")
def list_zones(
    camera_id: str,
    user: dict = Depends(get_current_user),
):
    _verify_camera_owner(camera_id, user["id"])
    zones = zone_store.get_zones(camera_id)
    return {"total": len(zones), "zones": zones}


@app.post("/cameras/{camera_id}/zones", status_code=201)
def create_zone(
    camera_id: str,
    payload: ZoneCreatePayload,
    user: dict = Depends(get_current_user),
):
    _verify_camera_owner(camera_id, user["id"])
    poly_dicts = [{"x": p.x, "y": p.y} for p in payload.polygon]

    try:
        new_zone = zone_store.add_zone(camera_id, payload.name, poly_dicts)
        motion_manager.refresh_zones(camera_id)
        return new_zone
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.put("/cameras/{camera_id}/zones/{zone_id}")
def update_zone(
    camera_id: str,
    zone_id: str,
    payload: ZoneUpdatePayload,
    user: dict = Depends(get_current_user),
):
    _verify_camera_owner(camera_id, user["id"])
    poly_dicts = [{"x": p.x, "y": p.y} for p in payload.polygon] if payload.polygon else None

    try:
        updated = zone_store.update_zone(camera_id, zone_id, payload.name, poly_dicts)
        motion_manager.refresh_zones(camera_id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.delete("/cameras/{camera_id}/zones/{zone_id}")
def delete_zone(
    camera_id: str,
    zone_id: str,
    user: dict = Depends(get_current_user),
):
    _verify_camera_owner(camera_id, user["id"])
    zone_store.delete_zone(camera_id, zone_id)
    motion_manager.refresh_zones(camera_id)
    return {"message": "Zona de detección eliminada correctamente"}


@app.delete("/cameras/{camera_id}/zones")
def clear_all_zones(
    camera_id: str,
    user: dict = Depends(get_current_user),
):
    _verify_camera_owner(camera_id, user["id"])
    zone_store.clear_all_zones(camera_id)
    motion_manager.refresh_zones(camera_id)
    return {"message": "Modo de detección en toda la imagen activado"}


@app.on_event("startup")
def startup_event():
    motion_manager.restore_active_cameras()
    if not health_checker.is_alive():
        health_checker.start()


@app.on_event("shutdown")
def shutdown_event():
    health_checker.stop()
    motion_manager.stop_all()
