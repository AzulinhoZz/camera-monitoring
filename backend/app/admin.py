import os
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth import get_current_user
from app.permissions import get_supabase_client

router = APIRouter(prefix="/admin", tags=["Admin"])


class DriverAddPayload(BaseModel):
    email: str


class TransportUnitCreatePayload(BaseModel):
    unit_number: str = Field(min_length=1, max_length=50)
    plate_number: Optional[str] = Field(None, max_length=50)


class CameraGrantPayload(BaseModel):
    camera_id: str
    user_id: str


def verify_fleet_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "administrador_flota":
        raise HTTPException(
            status_code=403,
            detail="Acceso restringido. Se requiere rol de Administrador de Flota."
        )
    return user


@router.get("/overview")
def get_fleet_overview(admin: dict = Depends(verify_fleet_admin)):
    client = get_supabase_client()
    if not client:
        raise HTTPException(status_code=500, detail="Database connection failed")

    org_id = admin.get("organization_id")
    try:
        # Drivers count in org
        drivers_res = client.table("profiles").select("id", count="exact").eq("organization_id", org_id).execute() if org_id else None
        drivers_count = drivers_res.count if drivers_res and drivers_res.count is not None else 0

        # Units count
        units_res = client.table("transport_units").select("id", count="exact").eq("organization_id", org_id).execute() if org_id else None
        units_count = units_res.count if units_res and units_res.count is not None else 0

        # Cameras count
        cams_res = client.table("cameras").select("id", count="exact").eq("organization_id", org_id).execute() if org_id else None
        cams_count = cams_res.count if cams_res and cams_res.count is not None else 0

        return {
            "organization_id": org_id,
            "drivers_count": drivers_count,
            "units_count": units_count,
            "cameras_count": cams_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener resumen de flota: {str(e)}")


@router.get("/drivers")
def list_drivers(admin: dict = Depends(verify_fleet_admin)):
    client = get_supabase_client()
    org_id = admin.get("organization_id")
    if not client or not org_id:
        return {"drivers": []}

    try:
        res = client.table("profiles").select("id, full_name, role, created_at").eq("organization_id", org_id).execute()
        return {"drivers": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar conductores: {str(e)}")


@router.get("/units")
def list_transport_units(admin: dict = Depends(verify_fleet_admin)):
    client = get_supabase_client()
    org_id = admin.get("organization_id")
    if not client or not org_id:
        return {"units": []}

    try:
        res = client.table("transport_units").select("id, unit_number, plate_number, created_at").eq("organization_id", org_id).execute()
        return {"units": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar unidades: {str(e)}")


@router.post("/units", status_code=201)
def create_transport_unit(
    payload: TransportUnitCreatePayload,
    admin: dict = Depends(verify_fleet_admin)
):
    client = get_supabase_client()
    org_id = admin.get("organization_id")
    if not client or not org_id:
        raise HTTPException(status_code=400, detail="El administrador no tiene una organización asignada")

    try:
        res = client.table("transport_units").insert({
            "organization_id": org_id,
            "unit_number": payload.unit_number.strip(),
            "plate_number": payload.plate_number.strip() if payload.plate_number else None
        }).execute()

        return res.data[0] if res.data else {"message": "Unidad creada"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al registrar unidad: {str(e)}")


@router.post("/camera-grants", status_code=201)
def grant_camera_access(
    payload: CameraGrantPayload,
    admin: dict = Depends(verify_fleet_admin)
):
    client = get_supabase_client()
    if not client:
        raise HTTPException(status_code=500, detail="Database error")

    org_id = admin.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=403, detail="Se requiere una organización")

    try:
        res = client.rpc("grant_camera_access_for_actor", {
            "p_actor_id": admin["id"], "p_camera_id": payload.camera_id,
            "p_recipient_id": payload.user_id,
        }).execute()
        if not res.data:
            raise HTTPException(status_code=503, detail="No se pudo guardar la concesión")
        return {"status": "granted", "grant": res.data[0]}
    except HTTPException:
        raise
    except Exception as exc:
        if getattr(exc, "code", None) == "42501":
            raise HTTPException(status_code=403, detail="Concesión fuera de su organización") from None
        # Missing/unapplied migration is a failure, never an unsafe local fallback.
        raise HTTPException(status_code=503, detail="No se pudo guardar la concesión") from None
