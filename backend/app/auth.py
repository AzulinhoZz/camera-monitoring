import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from supabase import create_client

from app.permissions import get_user_profile, has_camera_access

security = HTTPBearer()
router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginPayload(BaseModel):
    email: str
    password: str


class RegisterPayload(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: str
    password: str = Field(min_length=8)


class ForgotPasswordPayload(BaseModel):
    email: str


class RefreshPayload(BaseModel):
    refresh_token: str


class FCMTokenPayload(BaseModel):
    fcm_token: str
    device_type: str = "android"


class MediaMTXAuthPayload(BaseModel):
    ip: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    path: str
    protocol: Optional[str] = "hls"
    action: Optional[str] = "read"


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials

    try:
        supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )

        response = supabase.auth.get_user(token)

        if not response.user:
            raise HTTPException(
                status_code=401,
                detail="Sesión no válida",
            )

        full_name = response.user.user_metadata.get("full_name") if response.user.user_metadata else None
        profile = get_user_profile(str(response.user.id), response.user.email, full_name)

        return profile

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Token inválido o expirado",
        )


@router.post("/mediamtx")
def authenticate_mediamtx_stream(payload: MediaMTXAuthPayload):
    """
    HTTP External Auth endpoint for MediaMTX gateway.
    Validates client authorization for HLS playlists, TS segments, and RTSP streams.
    """
    # 1. Allow internal publishing from local workers
    if payload.action == "publish" or payload.ip in ("127.0.0.1", "172.18.0.1", "localhost"):
        return {"status": "authorized"}

    token = payload.user or payload.password
    if not token or token == "":
        raise HTTPException(status_code=401, detail="Token de acceso a la transmisión requerido")

    # 2. Validate token against Supabase Auth
    try:
        supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )
        response = supabase.auth.get_user(token)
        if not response.user:
            raise HTTPException(status_code=401, detail="Token de transmisión no válido")

        full_name = response.user.user_metadata.get("full_name") if response.user.user_metadata else None
        user_profile = get_user_profile(str(response.user.id), response.user.email, full_name)

        # 3. Find camera matching stream_path
        cam_res = supabase.table("cameras").select("id, user_id, organization_id, rtsp_url").execute()
        target_camera_id = None
        for cam in (cam_res.data or []):
            formatted_path = f"cam_{cam['id'][:8]}" if cam.get("id") else ""
            if payload.path == cam.get("id") or payload.path == formatted_path or payload.path in cam.get("rtsp_url", ""):
                target_camera_id = cam["id"]
                break

        if not target_camera_id:
            raise HTTPException(status_code=404, detail="Cámara no encontrada")

        if not has_camera_access(user_profile, target_camera_id):
            raise HTTPException(status_code=403, detail="Sin permisos para acceder a esta transmisión HLS/RTSP")

        return {"status": "authorized"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Error al verificar autorización de transmisión: {str(e)}")


@router.post("/register", status_code=201)
def register(payload: RegisterPayload):
    try:
        supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )
        res = supabase.auth.sign_up({
            "email": payload.email.strip(),
            "password": payload.password,
            "options": {
                "data": {
                    "full_name": payload.full_name.strip()
                }
            }
        })

        if not res.user:
            raise HTTPException(status_code=400, detail="No se pudo registrar el usuario")

        session_data = None
        if res.session:
            session_data = {
                "access_token": res.session.access_token,
                "refresh_token": res.session.refresh_token,
            }

        profile = get_user_profile(str(res.user.id), res.user.email, payload.full_name.strip())

        return {
            "message": "Registro completado. Si Supabase requiere confirmación, revisa tu correo electrónico.",
            "user": {
                "id": str(res.user.id),
                "email": res.user.email,
                "full_name": profile["full_name"],
                "role": profile["role"],
            },
            "session": session_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error al registrar la cuenta: {str(e)}",
        )


@router.post("/login")
def login(payload: LoginPayload):
    try:
        supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )
        res = supabase.auth.sign_in_with_password({
            "email": payload.email.strip(),
            "password": payload.password,
        })
        if not res.session or not res.user:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        full_name = res.user.user_metadata.get("full_name") if res.user.user_metadata else None
        profile = get_user_profile(str(res.user.id), res.user.email, full_name)

        return {
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
            "user": {
                "id": str(res.user.id),
                "email": res.user.email,
                "full_name": profile["full_name"],
                "role": profile["role"],
            }
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Credenciales inválidas o error de autenticación",
        )


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordPayload):
    try:
        supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )
        supabase.auth.reset_password_for_email(payload.email.strip())
        return {"message": "Si el correo está registrado, enviamos instrucciones para restablecer tu contraseña."}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error al solicitar recuperación de contraseña: {str(e)}",
        )


@router.post("/refresh")
def refresh_token(payload: RefreshPayload):
    try:
        supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )
        res = supabase.auth.refresh_session(payload.refresh_token)
        if not res.session or not res.user:
            raise HTTPException(status_code=401, detail="Refresh token inválido o expirado")

        full_name = res.user.user_metadata.get("full_name") if res.user.user_metadata else None
        profile = get_user_profile(str(res.user.id), res.user.email, full_name)

        return {
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
            "user": {
                "id": str(res.user.id),
                "email": res.user.email,
                "full_name": profile["full_name"],
                "role": profile["role"],
            }
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Refresh token inválido o expirado",
        )


@router.post("/fcm-token")
def register_fcm_token(
    payload: FCMTokenPayload,
    user: dict = Depends(get_current_user),
):
    try:
        supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )
        res = supabase.table("user_device_tokens").upsert({
            "user_id": user["id"],
            "fcm_token": payload.fcm_token.strip(),
            "device_type": payload.device_type,
        }, on_conflict="fcm_token").execute()
        return {"status": "registered", "fcm_token": payload.fcm_token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registering FCM token: {str(e)}")


@router.delete("/fcm-token")
def unregister_fcm_token(
    payload: FCMTokenPayload,
    user: dict = Depends(get_current_user),
):
    try:
        supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )
        supabase.table("user_device_tokens").delete().eq("fcm_token", payload.fcm_token.strip()).eq("user_id", user["id"]).execute()
        return {"status": "unregistered"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error unregistering FCM token: {str(e)}")
