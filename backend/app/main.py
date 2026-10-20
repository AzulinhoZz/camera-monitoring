import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth import get_current_user, router as auth_router
from app.cameras import router as cameras_router
from app.events import router as events_router
from app.motion_detector import motion_manager

app = FastAPI(title="Camera Monitoring API", version="1.0.0")

app.include_router(auth_router)
app.include_router(cameras_router)
app.include_router(events_router)


class MotionConfigPayload(BaseModel):
    action: str = Field(default="start")
    min_area: Optional[int] = Field(default=1500, ge=100, le=100000)
    threshold: Optional[int] = Field(default=25, ge=5, le=255)
    cooldown_seconds: Optional[float] = Field(default=5.0, ge=1.0, le=300.0)


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
        res = motion_manager.start_detector(
            camera_id=camera["id"],
            rtsp_url=camera["rtsp_url"],
            min_area=payload.min_area or 1500,
            threshold=payload.threshold or 25,
            cooldown_seconds=payload.cooldown_seconds or 5.0,
        )
        return res
    else:
        res = motion_manager.stop_detector(camera_id)
        return res


@app.on_event("startup")
def startup_event():
    motion_manager.restore_active_cameras()


@app.on_event("shutdown")
def shutdown_event():
    motion_manager.stop_all()
