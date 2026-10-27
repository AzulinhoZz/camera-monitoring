import os
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from supabase import create_client

from app.permissions import get_user_profile, has_camera_access
from app.streaming import stream_path, verify_stream

security = HTTPBearer()
gateway_security = HTTPBasic(auto_error=False)
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
    token: Optional[str] = Field(default=None, repr=False)
    ip: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = Field(default=None, repr=False)
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


def authorize_stream_read(token, path, client=None):
    try:
        claims = verify_stream(token, path)
        client = client or create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
        camera = client.table("cameras").select("id, user_id, organization_id").eq("id", claims["camera_id"]).execute()
        if not camera.data:
            raise ValueError("camera missing")
        row = camera.data[0]
        if row.get("user_id") != claims["owner_id"] or row.get("organization_id") != claims["organization_id"]:
            raise ValueError("camera scope changed")
        if not has_camera_access(get_user_profile(claims["sub"], ""), claims["camera_id"]):
            raise ValueError("access revoked")
        return claims
    except Exception:
        raise HTTPException(status_code=403, detail="Stream authorization denied") from None


@router.post("/mediamtx")
def authenticate_mediamtx_stream(
    payload: MediaMTXAuthPayload,
    credentials: Optional[HTTPBasicCredentials] = Depends(gateway_security),
):
    expected = os.getenv("MEDIAMTX_GATEWAY_SECRET", "")
    if (len(expected) < 32 or not credentials or credentials.username != "gateway"
            or not secrets.compare_digest(credentials.password.encode(), expected.encode())):
        raise HTTPException(status_code=401, detail="Gateway authentication required")
    if payload.protocol not in ("hls", "rtsp") or payload.action not in ("read", "publish"):
        raise HTTPException(status_code=403, detail="Stream action denied")
    try:
        client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
        if payload.action == "publish":
            publisher_key = os.getenv("MEDIAMTX_PUBLISH_SECRET", "")
            if (len(publisher_key) < 32 or payload.user != "publisher"
                    or not secrets.compare_digest((payload.password or "").encode(), publisher_key.encode())):
                raise ValueError("publisher denied")
            camera_id = payload.path.removeprefix("cam_")
            if stream_path(camera_id) != payload.path:
                raise ValueError("path denied")
            camera = client.table("cameras").select("id").eq("id", camera_id).execute()
            if not camera.data:
                raise ValueError("camera missing")
            return {"status": "authorized"}
        claims = authorize_stream_read(payload.token or payload.password or "", payload.path, client)
        return {"status": "authorized", "expireAt": datetime.fromtimestamp(claims["exp"], timezone.utc).isoformat()}
    except Exception:
        raise HTTPException(status_code=403, detail="Stream authorization denied") from None


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
