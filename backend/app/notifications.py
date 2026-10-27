import os
import logging
from typing import List, Optional
from supabase import create_client

logger = logging.getLogger("notifications")

_firebase_initialized = False

def init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return True

    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "/code/firebase_credentials.json")

    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                _firebase_initialized = True
                logger.info("Firebase Admin SDK initialized successfully from file")
                return True
            else:
                logger.warning(f"Firebase service account file not found at {cred_path}. Push notifications will be logged.")
                return False
        else:
            _firebase_initialized = True
            return True
    except Exception as e:
        logger.error(f"Error initializing Firebase Admin SDK: {e}")
        return False


def get_user_fcm_tokens(user_id: str) -> List[str]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        return []

    try:
        client = create_client(url, key)
        res = client.table("user_device_tokens").select("fcm_token").eq("user_id", user_id).execute()
        if res.data:
            return [row["fcm_token"] for row in res.data if row.get("fcm_token")]
    except Exception as e:
        logger.warning(f"Failed to fetch FCM tokens for user {user_id}: {e}")
    return []


def remove_fcm_token(fcm_token: str):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        return

    try:
        client = create_client(url, key)
        client.table("user_device_tokens").delete().eq("fcm_token", fcm_token).execute()
        logger.info("Removed invalid FCM token")
    except Exception as e:
        logger.error(f"Failed to delete invalid FCM token: {e}")


def send_motion_push_notification(
    user_id: str,
    camera_id: str,
    camera_name: str,
    description: str
):
    tokens = get_user_fcm_tokens(user_id)
    if not tokens:
        logger.info(f"No FCM tokens found for user {user_id}. Skipping push notification.")
        return

    firebase_ready = init_firebase()
    if not firebase_ready:
        logger.info(f"Firebase not configured. Simulated FCM Push for user {user_id}: {camera_name} - {description}")
        return

    try:
        from firebase_admin import messaging

        for token in tokens:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=f"¡Alerta en {camera_name}!",
                    body=description,
                ),
                data={
                    "camera_id": camera_id,
                    "camera_name": camera_name,
                    "event_type": "motion_detected",
                },
                token=token,
            )

            try:
                response = messaging.send(message)
                logger.info("FCM notification dispatched")
            except Exception as send_err:
                logger.warning("FCM notification dispatch failed")
                # Remove expired or invalid token
                remove_fcm_token(token)

    except Exception as e:
        logger.error(f"Failed to send FCM push notification: {e}")
