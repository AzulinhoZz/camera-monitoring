import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import create_client

security = HTTPBearer()
router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginPayload(BaseModel):
    email: str
    password: str


class RefreshPayload(BaseModel):
    refresh_token: str


class FCMTokenPayload(BaseModel):
    fcm_token: str
    device_type: str = "android"


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

        return {
            "id": str(response.user.id),
            "email": response.user.email,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Token inválido o expirado",
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

        return {
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
            "user": {
                "id": str(res.user.id),
                "email": res.user.email,
            }
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Credenciales inválidas o error de autenticación",
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

        return {
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
            "user": {
                "id": str(res.user.id),
                "email": res.user.email,
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
