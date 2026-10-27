"""Real MediaMTX/HLS authentication smoke, synthetic publisher and in-memory users.

No production DB or account; callback credentials are randomly generated in RAM.
"""
import base64
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials
from app import auth
from app.streaming import issue_stream, stream_path
from app.stream_proxy import proxy_hls
from fastapi.security import HTTPAuthorizationCredentials

IMAGE = "bluenviron/mediamtx@sha256:59e43552f3be43695b70c19424dc2a42fcec18075f88d91561a24ac5d70a586c"
CAMERA = {"id": "00000000-0000-0000-0000-000000000001", "user_id": "00000000-0000-0000-0000-000000000002", "organization_id": None}


class CameraQuery:
    def select(self, *a): return self
    def eq(self, key, value): self.match = value == CAMERA["id"]; return self
    def execute(self): return SimpleNamespace(data=[CAMERA] if self.match else [])


class Callback(BaseHTTPRequestHandler):
    calls = 0
    last_error = None
    def log_message(self, *args): pass  # Headers/body/credentials must not be logged.
    def do_GET(self):
        try:
            parts = self.path.split("?",1)[0].split("/")
            if len(parts) != 4 or parts[1] != "streams":
                self.send_response(404); self.end_headers(); return
            header = self.headers.get("Authorization", "")
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=header[7:]) if header.startswith("Bearer ") else None
            response = proxy_hls(parts[2], parts[3], SimpleNamespace(query_params={}), creds)
            self.send_response(response.status_code)
            self.send_header("Content-Type", response.media_type)
            self.end_headers(); self.wfile.write(response.body)
        except HTTPException as error:
            Callback.last_error = error.detail
            self.send_response(error.status_code); self.end_headers()
        except Exception:
            self.send_response(500); self.end_headers()

    def do_POST(self):
        Callback.calls += 1
        try:
            header = self.headers.get("Authorization", "")
            credentials = None
            if header.startswith("Basic "):
                name, _, password = base64.b64decode(header[6:]).decode().partition(":")
                credentials = HTTPBasicCredentials(username=name, password=password)
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            payload = auth.MediaMTXAuthPayload.model_validate_json(raw)
            data = auth.authenticate_mediamtx_stream(payload, credentials)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except HTTPException as error:
            Callback.last_error = error.detail
            self.send_response(error.status_code); self.end_headers()
        except Exception:
            self.send_response(403); self.end_headers()


def fetch(url, token=None):
    try:
        response = urlopen(Request(url, headers={"Authorization": "Bearer " + token} if token else {}), timeout=5)
        return response.status, response.read()
    except HTTPError as error:
        return error.code, b""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant',choices=('lowLatency','mpegts'),default='mpegts')
    args=parser.parse_args()
    for key in ("MEDIAMTX_GATEWAY_SECRET", "MEDIAMTX_PUBLISH_SECRET", "STREAM_TOKEN_SECRET", "MEDIAMTX_HLS_SECRET"):
        os.environ[key] = secrets.token_urlsafe(32)
    os.environ["SUPABASE_URL"] = "https://supabase.invalid"
    os.environ["SUPABASE_SECRET_KEY"] = "offline-test-placeholder"
    auth.create_client = lambda *a: SimpleNamespace(table=lambda name: CameraQuery())
    auth.get_user_profile = lambda identity, _: {"id": identity}
    auth.has_camera_access = lambda user, camera_id: user["id"] == CAMERA["user_id"] and camera_id == CAMERA["id"]
    server = ThreadingHTTPServer(("0.0.0.0", 0), Callback)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    name = f"gateway-security-{uuid4().hex[:12]}"
    created = False
    publisher = None
    try:
        with tempfile.TemporaryDirectory(prefix="gateway-security-") as directory:
            config = Path(directory) / "mediamtx.yml"
            original = Path(__file__).resolve().parents[2] / "gateway/mediamtx.yml"
            config.write_text(original.read_text().replace("hlsVariant: mpegts", f"hlsVariant: {args.variant}") + "\nhlsSegmentDuration: 1s\n")
            callback = f"http://gateway:{os.environ['MEDIAMTX_GATEWAY_SECRET']}@host.docker.internal:{server.server_port}/auth/mediamtx"
            subprocess.run(["docker", "run", "--rm", "-d", "--name", name,
                            "--add-host", "host.docker.internal:host-gateway", "-p", "127.0.0.1::8554", "-p", "127.0.0.1::8888",
                            "-e", "MTX_AUTHHTTPADDRESS=" + callback, "-e", "MTX_HLSCDNSECRET=" + os.environ["MEDIAMTX_HLS_SECRET"], "--mount", f"type=bind,src={config},dst=/mediamtx.yml,readonly", IMAGE],
                           check=True, capture_output=True)
            created = True
            def port(which):
                value = subprocess.run(["docker", "port", name, which], check=True, capture_output=True, text=True).stdout.strip()
                return int(value.rsplit(":", 1)[1])
            rtsp_port, hls_port = port("8554/tcp"), port("8888/tcp")
            os.environ["MEDIAMTX_HLS_INTERNAL_URL"] = f"http://127.0.0.1:{hls_port}"
            path = stream_path(CAMERA["id"])
            # Native publisher diagnostics are discarded: they may contain userinfo.
            publisher = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-re", "-f", "lavfi", "-i", "color=c=black:s=160x120:r=15",
                "-an", "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-g", "15", "-pix_fmt", "yuv420p",
                "-f", "rtsp", "-rtsp_transport", "tcp", f"rtsp://publisher:{os.environ['MEDIAMTX_PUBLISH_SECRET']}@127.0.0.1:{rtsp_port}/{path}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            url = f"http://127.0.0.1:{server.server_port}/streams/{CAMERA['id']}/index.m3u8"
            token = issue_stream(CAMERA["user_id"], CAMERA)["stream_token"]
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                try:
                    status, body = fetch(url, token)
                    if status == 200 and b"#EXTM3U" in body: break
                except (URLError, TimeoutError): pass
                if publisher.poll() is not None: raise RuntimeError("synthetic publisher failed")
                time.sleep(.2)
            else: raise RuntimeError(f"authenticated HLS readiness failed: {Callback.last_error}")
            assert fetch(url)[0] in (401, 403)
            assert fetch(url, "invalid")[0] in (401, 403)
            # Fetch the variant and a TS segment with the same Authorization header.
            for _ in range(3):
                candidates = [line for line in body.decode().splitlines() if line and not line.startswith("#")]
                assert candidates
                target = urljoin(url, candidates[0])
                assert fetch(target)[0] in (401, 403)
                status, next_body = fetch(target, token)
                if status != 200 or not next_body:
                    raise RuntimeError(f"HLS resource failed: status={status}, extension={target.rsplit('.',1)[-1].split('?',1)[0]}, detail={Callback.last_error}")
                if not target.endswith("m3u8"):
                    break
                url, body = target, next_body
            else: raise RuntimeError("HLS segment was not exercised")
            assert Callback.calls >= 1
            print("PASS: authenticated publish and proxy HLS playlist/variant/segment; anonymous and invalid tokens denied")
    except subprocess.CalledProcessError:
        raise RuntimeError("isolated gateway command failed; credential-bearing command suppressed") from None
    finally:
        if publisher and publisher.poll() is None:
            publisher.terminate(); publisher.wait(5)
        if created: subprocess.run(["docker", "stop", name], check=True, capture_output=True)
        server.shutdown(); server.server_close(); thread.join(2)


if __name__ == "__main__": main()
