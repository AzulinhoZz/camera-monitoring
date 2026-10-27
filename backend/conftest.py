"""Offline by default: existing unit suites must never reach a real Supabase/camera."""
import socket
import sys
from unittest.mock import Mock

import pytest


class ClosedCapture:
    def __init__(self, *args, **kwargs): pass
    def isOpened(self): return False
    def read(self): return False, None
    def release(self): pass


@pytest.fixture(autouse=True)
def isolated_backends(monkeypatch, tmp_path, request):
    monkeypatch.setenv("CAMERA_LEASE_DIRECTORY", str(tmp_path / "capture-leases"))
    monkeypatch.setenv("STREAM_TOKEN_SECRET", "offline-stream-signing-secret-32-bytes-long")
    monkeypatch.setenv("MEDIAMTX_GATEWAY_SECRET", "offline-gateway-callback-32-bytes-long")
    monkeypatch.setenv("MEDIAMTX_HLS_SECRET", "offline-internal-hls-secret-32-bytes-long")
    monkeypatch.setenv("MEDIAMTX_PUBLISH_SECRET", "offline-publisher-secret-32-bytes-long")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.invalid")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "offline-test-placeholder")
    for key in ("FIREBASE_CREDENTIALS_PATH", "GOOGLE_APPLICATION_CREDENTIALS"):
        monkeypatch.delenv(key, raising=False)
    denied = Mock(side_effect=RuntimeError("Real Supabase disabled in offline unit tests"))
    monkeypatch.setattr("supabase.create_client", denied)
    for name, module in list(sys.modules.items()):
        if name.startswith("app.") and hasattr(module, "create_client"):
            monkeypatch.setattr(module, "create_client", denied)
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError("Network disabled in unit tests")
        return original(sock, address)

    def connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError("Network disabled in unit tests")
        return original_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    # These legacy lifecycle tests use emulator URLs and only assert thread state.
    # New vision tests decode synthetic/local video in disposable subprocesses.
    if request.node.path.name in ("test_motion_detector.py", "test_camera_crud.py"):
        monkeypatch.setattr("cv2.VideoCapture", ClosedCapture)
        monkeypatch.setattr("app.motion_detector.policy_rtsp_url", lambda value: value)
    if request.node.path.name == "test_connectivity.py":
        monkeypatch.setattr("app.connectivity_checker.policy_rtsp_url", lambda value: value)
    from app.camera_config import config_store
    from app.zone_store import zone_store
    from app.motion_detector import motion_manager
    from app.main import app
    monkeypatch.setattr(config_store, "file_path", str(tmp_path / "camera_configs.json"))
    monkeypatch.setattr(config_store, "_supabase_enabled", True)
    monkeypatch.setattr(zone_store, "_local_zones", {})
    yield
    motion_manager.stop_all()
    app.dependency_overrides.clear()
