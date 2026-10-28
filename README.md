# Camera Monitoring MVP — Starter

FastAPI + Supabase + MediaMTX for local development on macOS.

## Start

1. Copy `.env.example` to `.env` and fill the Supabase project URL and a server-only secret key (`sb_secret_...` or legacy service_role).
2. `docker compose up --build -d`
3. `curl http://localhost:8000/health`
4. `curl http://localhost:8000/health/db`
5. `docker compose ps`

The `/health/db` endpoint verifies access to the `public.cameras` table. Camera APIs and the Android application are implemented; see the architecture and phase reports under `docs/ai-vision` for their verified scope. Do not expose port 8000 or 8554 publicly. The backend secret must never be shipped in Android.

## Camera Monitoring AI 2.0

The development implementation includes scoped vision rules/events, review and evidence, optional pose/action experiments, a paged Android event dashboard, expiring analyzed-frame overlays and a per-camera fleet supervisor. See [phase 5 completion](docs/ai-vision/PHASE_5_COMPLETION.md) for setup, measured limits and rollback. Production acceptance, managed integration, device verification and release hardening remain separate gates.

Phase 6 hardening is in progress: see the [initial hardening report](docs/ai-vision/PHASE_6_HARDENING_AND_RELEASE.md) and [release checklist](docs/ai-vision/RELEASE_CHECKLIST.md). The reviewed CI snapshot targets Python 3.12/Linux x86_64; it does not approve a production image or deployment.
