import os
import time
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np
from supabase import create_client

from app.camera_config import config_store
from app.clip_recorder import FrameRingBuffer, dispatch_clip_recording
from app.evidence_uploader import dispatch_evidence_upload
from app.notifications import send_motion_push_notification
from app.schedule_evaluator import is_schedule_active
from app.zone_store import zone_store

logger = logging.getLogger("motion_detector")
logging.basicConfig(level=logging.INFO)


class MotionDetectorWorker(threading.Thread):
    def __init__(
        self,
        camera_id: str,
        rtsp_url: str,
        min_area: int = 1500,
        threshold: int = 25,
        cooldown_seconds: float = 5.0,
        sensitivity_preset: str = "medium",
        schedule_type: str = "24/7",
        schedule_days: Optional[List[str]] = None,
        start_time: str = "00:00:00",
        end_time: str = "23:59:59",
        timezone: str = "America/Mexico_City",
        frame_interval: float = 0.1,
        zones: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(daemon=True)
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.min_area = min_area
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.sensitivity_preset = sensitivity_preset
        self.schedule_type = schedule_type
        self.schedule_days = schedule_days or ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        self.start_time = start_time
        self.end_time = end_time
        self.timezone = timezone
        self.frame_interval = frame_interval
        self.zones = zones or []
        self.ring_buffer = FrameRingBuffer(maxlen=75)
        self.latest_frame: Optional[np.ndarray] = None
        self.running = True
        self.last_event_time = 0.0

    def stop(self):
        self.running = False

    def update_params(
        self,
        min_area: Optional[int] = None,
        threshold: Optional[int] = None,
        cooldown_seconds: Optional[float] = None,
        sensitivity_preset: Optional[str] = None,
        schedule_type: Optional[str] = None,
        schedule_days: Optional[List[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        timezone: Optional[str] = None,
        zones: Optional[List[Dict[str, Any]]] = None,
    ):
        if min_area is not None:
            self.min_area = min_area
        if threshold is not None:
            self.threshold = threshold
        if cooldown_seconds is not None:
            self.cooldown_seconds = cooldown_seconds
        if sensitivity_preset is not None:
            self.sensitivity_preset = sensitivity_preset
        if schedule_type is not None:
            self.schedule_type = schedule_type
        if schedule_days is not None:
            self.schedule_days = schedule_days
        if start_time is not None:
            self.start_time = start_time
        if end_time is not None:
            self.end_time = end_time
        if timezone is not None:
            self.timezone = timezone
        if zones is not None:
            self.zones = zones

    def log_event_to_db(self, description: str, frame: Optional[np.ndarray] = None):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SECRET_KEY")
        if not url or not key:
            logger.error("Supabase environment variables not set")
            return

        try:
            client = create_client(url, key)

            # Fetch camera user_id and name
            cam_res = client.table("cameras").select("id, name, user_id").eq("id", self.camera_id).execute()
            user_id = None
            camera_name = "Cámara IP"
            if cam_res.data:
                user_id = cam_res.data[0].get("user_id")
                camera_name = cam_res.data[0].get("name", "Cámara IP")

            insert_res = client.table("camera_events").insert({
                "camera_id": self.camera_id,
                "event_type": "motion_detected",
                "description": description,
            }).execute()

            event_id = None
            if insert_res.data and len(insert_res.data) > 0:
                event_id = insert_res.data[0].get("id")

            logger.info(f"Motion event recorded for camera {self.camera_id}: {description}")

            # Dispatch async evidence frame upload if frame and user_id exist
            if event_id and user_id and frame is not None:
                dispatch_evidence_upload(event_id, user_id, self.camera_id, frame)

            # Dispatch async short video clip recording (~5s pre-event + ~10s post-event)
            if event_id and user_id:
                pre_frames = self.ring_buffer.get_frames_copy()
                dispatch_clip_recording(
                    event_id=event_id,
                    user_id=user_id,
                    camera_id=self.camera_id,
                    pre_event_frames=pre_frames,
                    latest_frame_provider=lambda: self.latest_frame
                )

            # Send FCM Push Notification if user_id is present
            if user_id:
                send_motion_push_notification(
                    user_id=user_id,
                    camera_id=self.camera_id,
                    camera_name=camera_name,
                    description=description
                )

        except Exception as e:
            logger.error(f"Failed to insert motion event: {e}")

    def process_frame(self, frame: np.ndarray, first_frame: Optional[np.ndarray]) -> Tuple[bool, int, Optional[np.ndarray]]:
        """
        Process a single image frame for motion detection with polygon zone masking and schedule evaluation.
        Returns: (motion_detected, max_contour_area, updated_first_frame)
        """
        if frame is None or frame.size == 0:
            return False, 0, first_frame

        # Check if camera schedule is active right now
        if not is_schedule_active(
            schedule_type=self.schedule_type,
            schedule_days=self.schedule_days,
            start_time_str=self.start_time,
            end_time_str=self.end_time,
            tz_name=self.timezone
        ):
            return False, 0, first_frame

        height, width = frame.shape[:2]

        # Convert to grayscale and apply Gaussian blur to smooth high-frequency noise
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if first_frame is None:
            return False, 0, gray

        # Compute frame delta between background reference and current frame
        frame_delta = cv2.absdiff(first_frame, gray)
        thresh = cv2.threshold(frame_delta, self.threshold, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        # Polygon Zone Masking Engine
        if self.zones and len(self.zones) > 0:
            mask = np.zeros((height, width), dtype=np.uint8)
            has_valid_mask = False
            for zone in self.zones:
                polygon = zone.get("polygon")
                if polygon and len(polygon) >= 3:
                    pts = np.array(
                        [[int(pt["x"] * width), int(pt["y"] * height)] for pt in polygon],
                        dtype=np.int32
                    )
                    cv2.fillPoly(mask, [pts], 255)
                    has_valid_mask = True

            if has_valid_mask:
                thresh = cv2.bitwise_and(thresh, thresh, mask=mask)

        # Find contours
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion_detected = False
        max_area = 0
        for c in contours:
            area = cv2.contourArea(c)
            if area > max_area:
                max_area = int(area)
            if area >= self.min_area:
                motion_detected = True

        # Slowly blend current frame into background reference to adapt to lighting changes
        cv2.addWeighted(gray, 0.05, first_frame, 0.95, 0, first_frame)

        return motion_detected, max_area, first_frame

    def run(self):
        logger.info(f"Starting motion detector worker for camera {self.camera_id}")

        cap = None
        first_frame = None

        try:
            cap = cv2.VideoCapture(self.rtsp_url)
            if not cap.isOpened():
                logger.warning(f"Initial attempt to open RTSP stream failed: {self.rtsp_url}")

            while self.running:
                if cap is None or not cap.isOpened():
                    time.sleep(1.0)
                    if cap is not None:
                        cap.release()
                    cap = cv2.VideoCapture(self.rtsp_url)
                    first_frame = None
                    continue

                ret, frame = cap.read()
                if not ret or frame is None:
                    # Stream disconnected or buffering; retry connection
                    time.sleep(0.5)
                    first_frame = None
                    continue

                self.latest_frame = frame
                self.ring_buffer.append(frame)

                motion_detected, max_area, first_frame = self.process_frame(frame, first_frame)

                if motion_detected:
                    now = time.time()
                    if now - self.last_event_time >= self.cooldown_seconds:
                        self.last_event_time = now
                        desc = f"Movimiento detectado: área={max_area}px (mín={self.min_area}px, umbral={self.threshold})"
                        self.log_event_to_db(desc, frame=frame)

                time.sleep(self.frame_interval)

        except Exception as e:
            logger.error(f"Error in MotionDetectorWorker loop for camera {self.camera_id}: {e}")
        finally:
            if cap is not None:
                cap.release()
            logger.info(f"Motion detector worker stopped cleanly for camera {self.camera_id}")


class MotionDetectorManager:
    def __init__(self):
        self.workers: Dict[str, MotionDetectorWorker] = {}

    def start_detector(
        self,
        camera_id: str,
        rtsp_url: str,
        min_area: int = 1500,
        threshold: int = 25,
        cooldown_seconds: float = 5.0,
        sensitivity_preset: str = "medium",
        schedule_type: str = "24/7",
        schedule_days: Optional[List[str]] = None,
        start_time: str = "00:00:00",
        end_time: str = "23:59:59",
        timezone: str = "America/Mexico_City",
    ) -> Dict:
        cfg = config_store.set_config(
            camera_id=camera_id,
            motion_enabled=True,
            min_area=min_area,
            threshold=threshold,
            cooldown_seconds=cooldown_seconds,
            sensitivity_preset=sensitivity_preset,
            schedule_type=schedule_type,
            schedule_days=schedule_days,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone,
        )

        zones = zone_store.get_zones(camera_id)

        if camera_id in self.workers and self.workers[camera_id].is_alive():
            worker = self.workers[camera_id]
            worker.update_params(
                min_area=min_area,
                threshold=threshold,
                cooldown_seconds=cooldown_seconds,
                sensitivity_preset=sensitivity_preset,
                schedule_type=schedule_type,
                schedule_days=schedule_days,
                start_time=start_time,
                end_time=end_time,
                timezone=timezone,
                zones=zones
            )
            logger.info(f"Worker for camera {camera_id} is already active. Updated params, schedule and zones.")
            return self.get_status(camera_id)

        worker = MotionDetectorWorker(
            camera_id=camera_id,
            rtsp_url=rtsp_url,
            min_area=cfg["min_area"],
            threshold=cfg["threshold"],
            cooldown_seconds=cfg["cooldown_seconds"],
            sensitivity_preset=cfg["sensitivity_preset"],
            schedule_type=cfg["schedule_type"],
            schedule_days=cfg["schedule_days"],
            start_time=cfg["start_time"],
            end_time=cfg["end_time"],
            timezone=cfg["timezone"],
            zones=zones,
        )
        self.workers[camera_id] = worker
        worker.start()
        return self.get_status(camera_id)

    def refresh_zones(self, camera_id: str):
        if camera_id in self.workers and self.workers[camera_id].is_alive():
            zones = zone_store.get_zones(camera_id)
            self.workers[camera_id].update_params(zones=zones)
            logger.info(f"Refreshed detection zones for camera {camera_id}: {len(zones)} zones")

    def stop_detector(self, camera_id: str) -> Dict:
        cfg = config_store.get_config(camera_id)
        config_store.set_config(
            camera_id=camera_id,
            motion_enabled=False,
            min_area=cfg["min_area"],
            threshold=cfg["threshold"],
            cooldown_seconds=cfg["cooldown_seconds"],
            sensitivity_preset=cfg.get("sensitivity_preset", "medium"),
            schedule_type=cfg.get("schedule_type", "24/7"),
            schedule_days=cfg.get("schedule_days"),
            start_time=cfg.get("start_time", "00:00:00"),
            end_time=cfg.get("end_time", "23:59:59"),
            timezone=cfg.get("timezone", "America/Mexico_City"),
        )

        if camera_id in self.workers:
            self.workers[camera_id].stop()
            del self.workers[camera_id]
            logger.info(f"Stopped detector worker for camera {camera_id}")
        return self.get_status(camera_id)

    def get_status(self, camera_id: str) -> Dict:
        cfg = config_store.get_config(camera_id)
        is_active = camera_id in self.workers and self.workers[camera_id].is_alive()
        sched_active = is_schedule_active(
            schedule_type=cfg.get("schedule_type", "24/7"),
            schedule_days=cfg.get("schedule_days"),
            start_time_str=cfg.get("start_time", "00:00:00"),
            end_time_str=cfg.get("end_time", "23:59:59"),
            tz_name=cfg.get("timezone", "America/Mexico_City")
        )
        zones = zone_store.get_zones(camera_id)
        return {
            "is_active": is_active and sched_active,
            "motion_enabled": cfg["motion_enabled"],
            "is_schedule_active": sched_active,
            "camera_id": camera_id,
            "min_area": cfg["min_area"],
            "threshold": cfg["threshold"],
            "cooldown_seconds": cfg["cooldown_seconds"],
            "sensitivity_preset": cfg.get("sensitivity_preset", "medium"),
            "schedule_type": cfg.get("schedule_type", "24/7"),
            "schedule_days": cfg.get("schedule_days", ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]),
            "start_time": cfg.get("start_time", "00:00:00"),
            "end_time": cfg.get("end_time", "23:59:59"),
            "timezone": cfg.get("timezone", "America/Mexico_City"),
            "active_zones_count": len(zones),
            "zones": zones,
        }

    def restore_active_cameras(self):
        def _do_restore():
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SECRET_KEY")
            if not url or not key:
                logger.warning("Supabase credentials not available for restoring active cameras")
                return

            try:
                client = create_client(url, key)
                res = client.table("cameras").select("id, name, rtsp_url").execute()
                cameras = res.data or []

                restored_count = 0
                for cam in cameras:
                    cam_id = cam["id"]
                    rtsp_url = cam.get("rtsp_url")
                    if not rtsp_url:
                        continue

                    cfg = config_store.get_config(cam_id)
                    if cfg.get("motion_enabled", True):
                        self.start_detector(
                            camera_id=cam_id,
                            rtsp_url=rtsp_url,
                            min_area=cfg.get("min_area", 1500),
                            threshold=cfg.get("threshold", 25),
                            cooldown_seconds=cfg.get("cooldown_seconds", 5.0),
                            sensitivity_preset=cfg.get("sensitivity_preset", "medium"),
                            schedule_type=cfg.get("schedule_type", "24/7"),
                            schedule_days=cfg.get("schedule_days"),
                            start_time=cfg.get("start_time", "00:00:00"),
                            end_time=cfg.get("end_time", "23:59:59"),
                            timezone=cfg.get("timezone", "America/Mexico_City"),
                        )
                        restored_count += 1

                logger.info(f"Restored {restored_count} motion detector workers on server startup.")
            except Exception as e:
                logger.error(f"Error during restore_active_cameras: {e}")

        # Execute restoration in background thread so FastAPI startup is non-blocking
        threading.Thread(target=_do_restore, daemon=True).start()

    def stop_all(self):
        for camera_id, worker in self.workers.items():
            worker.stop()
        self.workers.clear()


motion_manager = MotionDetectorManager()
