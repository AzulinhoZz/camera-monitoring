# Camera Monitoring MVP — Starter

FastAPI + Supabase + MediaMTX for local development on macOS.

## Start

1. Copy `.env.example` to `.env` and fill the Supabase project URL and a server-only secret key (`sb_secret_...` or legacy service_role).
2. `python3 backend/scripts/prepare_release_wheels.py --output /tmp/camera-vision-wheels` (verified Python 3.12/Linux amd64 wheels; preparation works on any host).
3. `docker compose up --build -d` (BuildKit/additional contexts required; Linux amd64 image, emulation needed on ARM hosts).
4. `curl http://localhost:8000/health`
5. `curl http://localhost:8000/health/db`
6. `docker compose ps`

MediaMTX runs without root or Linux capabilities. Set `MEDIAMTX_UID` and `MEDIAMTX_GID` to the owner of `gateway/mediamtx.yml` (defaults: 1000/1000); keep that file private and readable by that owner. On Linux, obtain the IDs with `id -u` and `id -g`.

The `/health/db` endpoint verifies access to the `public.cameras` table. Camera APIs and the Android application are implemented; see the architecture and phase reports under `docs/ai-vision` for their verified scope. Do not expose port 8000 or 8554 publicly. The backend secret must never be shipped in Android.

## Camera Monitoring AI 2.0

The development implementation includes scoped vision rules/events, review and evidence, optional pose/action experiments, a paged Android event dashboard, expiring analyzed-frame overlays and a per-camera fleet supervisor. See [phase 5 completion](docs/ai-vision/PHASE_5_COMPLETION.md) for setup, measured limits and rollback. Production acceptance, managed integration, device verification and release hardening remain separate gates.

Phase 6 hardening is in progress: see the [initial hardening report](docs/ai-vision/PHASE_6_HARDENING_AND_RELEASE.md) and [release checklist](docs/ai-vision/RELEASE_CHECKLIST.md). The reviewed CI snapshot targets Python 3.12/Linux x86_64; it does not approve a production image or deployment.

The release candidate, image archive/SBOM and acceptance verdict are described in [phase 6 delivery](docs/ai-vision/PHASE_6_DELIVERY_AND_ACCEPTANCE.md). A successful build is not production approval; the readiness command returns NO_GO for unresolved gates.

The authorized follow-up [release remediation phase](docs/ai-vision/PHASE_7_RELEASE_REMEDIATION.md) begins with canonical cursor validation and bounded stream-token parsing. Production remains NO_GO until the native findings and external acceptance gates are resolved.
