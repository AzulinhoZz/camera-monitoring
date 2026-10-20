# Camera Monitoring MVP — Starter

FastAPI + Supabase + MediaMTX for local development on macOS.

## Start

1. Copy `.env.example` to `.env` and fill the Supabase project URL and a server-only secret key (`sb_secret_...` or legacy service_role).
2. `docker compose up --build -d`
3. `curl http://localhost:8000/health`
4. `curl http://localhost:8000/health/db`
5. `docker compose ps`

The `/health/db` endpoint verifies access to the `public.cameras` table. No camera registration or Android application is implemented yet. Do not expose port 8000 or 8554 publicly. The backend secret must never be shipped in Android.
