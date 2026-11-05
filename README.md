# Camera Monitoring MVP

FastAPI + Supabase + MediaMTX + Android (Kotlin/Jetpack Compose).

## Local backend

1. Copy `.env.example` to `.env` and configure the Supabase project URL and a server-only secret key (`sb_secret_...` or legacy `service_role`).
2. Start Docker Desktop.
3. Run `docker compose up --build -d`.
4. Check `curl http://localhost:8000/health` and `curl http://localhost:8000/health/db`.
5. Check services with `docker compose ps`.

Never put the Supabase secret key in the Android app or expose the API/RTSP ports directly to the public internet.

## RTSP and HLS addressing

Use different addresses depending on where the client runs:

- FFmpeg on the Mac publishes to MediaMTX at `rtsp://127.0.0.1:8554/<stream-path>`.
- Containers on the Compose network reach MediaMTX at `rtsp://mediamtx:8554/<stream-path>`.
- Android emulator reaches the Mac host at `http://10.0.2.2:8888`.
- A physical phone on the same Wi-Fi needs the Mac's LAN IP, for example `http://192.168.x.x:8888`.
- A deployed app needs a reachable HTTPS HLS endpoint, normally behind a reverse proxy.

Set `HLS_BASE_URL` in the backend environment to the HLS base URL reachable by the target Android device. It defaults to `http://10.0.2.2:8888` for the Android emulator. Do not use that default for a physical phone.

The backend's RTSP camera URL is the source consumed by OpenCV. If the source is a stream published into this MediaMTX instance, store the Docker-network address (`rtsp://mediamtx:8554/<stream-path>`) so the API container can reach it. The Mac-side FFmpeg publisher still uses `127.0.0.1`.

## Supabase migrations

The SQL files under `backend/migrations` and `backend/app/migrations` must be reviewed and applied to the intended Supabase project in order. A file existing in GitHub does not mean it has been applied to production. Back up the database and verify the target project before running migrations, especially migration 009.

## Validation

Run backend tests from the repository root with:

```bash
cd backend
pytest -q
```

The live RTSP-to-HLS path, physical Android playback, FCM delivery, and production RLS/Storage policies still require environment-backed tests.
