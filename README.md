> Validación actual (4nov2026):253 backend y19 Android unitarias PASS; imagen nativa37 hallazgos (23High), **NO_GO**. [Entrega, límites y evidencia](docs/ai-vision/NATIVE_HARDENING_2026_11_04.md).

# Camera Monitoring AI 2.0 — Development candidate

FastAPI + Supabase + MediaMTX for local development on macOS.

## Start

1. Copy `.env.example` to `.env` and fill the Supabase project URL and a server-only secret key (`sb_secret_...` or legacy service_role).
2. `python3 backend/scripts/prepare_release_wheels.py --output /tmp/camera-vision-wheels` (verified Python 3.13/Linux amd64 wheels; preparation works on any host).
3. `python3 backend/scripts/prepare_os_packages.py --output /tmp/camera-os-packages` (hash-pinned packages, frozen authenticated index).
4. `docker compose up --build -d` (BuildKit/additional contexts required; Linux amd64 image, emulation needed on ARM hosts).
5. `curl http://localhost:8000/health`
6. `curl http://localhost:8000/health/db`
7. `docker compose ps`

MediaMTX runs without root or Linux capabilities. Set `MEDIAMTX_UID` and `MEDIAMTX_GID` to the owner of `gateway/mediamtx.yml` (defaults: 1000/1000); keep that file private and readable by that owner. On Linux, obtain the IDs with `id -u` and `id -g`.

The `/health/db` endpoint verifies access to the `public.cameras` table. Camera APIs and the Android application are implemented; see the architecture and phase reports under `docs/ai-vision` for their verified scope. Do not expose port 8000 or 8554 publicly. The backend secret must never be shipped in Android.

## Camera Monitoring AI 2.0

The development implementation includes scoped vision rules/events, review and evidence, optional pose/action experiments, a paged Android event dashboard, expiring analyzed-frame overlays and a per-camera fleet supervisor. See [phase 5 completion](docs/ai-vision/PHASE_5_COMPLETION.md) for setup, measured limits and rollback. Production acceptance, managed integration, device verification and release hardening remain separate gates.

Phase 6 hardening is in progress: see the [initial hardening report](docs/ai-vision/PHASE_6_HARDENING_AND_RELEASE.md) and [release checklist](docs/ai-vision/RELEASE_CHECKLIST.md). That historical CI snapshot targets Python 3.12/Linux x86_64; the current backend uses Python3.13, as documented in the native remediation report, and it does not approve a production image or deployment.

The release candidate, image archive/SBOM and acceptance verdict are described in [phase 6 delivery](docs/ai-vision/PHASE_6_DELIVERY_AND_ACCEPTANCE.md). A successful build is not production approval; the readiness command returns NO_GO for unresolved gates.

The authorized follow-up [release remediation phase](docs/ai-vision/PHASE_7_RELEASE_REMEDIATION.md) begins with canonical cursor validation and bounded stream-token parsing. Production remains NO_GO until the native findings and external acceptance gates are resolved.

## Product improvements and current acceptance

The [product delivery report](docs/ai-vision/PHASE_7_PRODUCT_DELIVERY.md) records pending-first camera navigation, rule/date/time incident search, safer evidence loading, Android transport hardening, the Guava advisory fix, offline alert scoring, encrypted backup/restore and measured isolated camera capacity. See the [operations guide](docs/ai-vision/PRODUCT_OPERATIONS.md) for reproducible commands and the [external validation matrix](docs/ai-vision/PRODUCT_VALIDATION_MATRIX.md) for device/staging/dataset acceptance still pending.

**Production remains NO_GO:** the historical product image scan reported200 matches; Android Maven scan is clean for its advisory snapshot only. No deployment or managed-project migration is included.

## Security revalidation — 2026-11-04

[Current revalidation](docs/ai-vision/REVALIDATION_2026_11_04.md): 243 backend and19 Android unit tests passed; device smoke APK compiled but not executed. Fresh scans found225 backend image matches and four advisories in pyasn10.6.4; Android Maven snapshot remains0. Staging was explicitly confirmed, but its HTTPS preflight is blocked by the runtime proxy. Production remains NO_GO.

## pyasn1 remediation — 2026-11-04

[Reviewed patch and validation](docs/ai-vision/PYASN1_REMEDIATION_2026_11_04.md): pyasn1 is pinned to0.6.5 by hash;247 backend tests pass and the installed Python advisory snapshot has0 affected packages. New image build/smoke pass; native findings decrease225→221 (82 High), removing exactly the four pyasn1 advisories. Production remains NO_GO; staging is still blocked by proxy CONNECT403, and device testing remains outside the current cloud-only scope.

## Current native hardening candidate

The backend now uses a public, digest-pinned Wolfi base with Python3.13, the same reviewed Python package versions, and an authenticated offline OS package set. [Native hardening report](docs/ai-vision/NATIVE_HARDENING_2026_11_04.md) records exact source, image and scan identities. Production remains NO_GO; no managed-project writes or deployment were performed.

For cloud backend checks without installing Python3.13 on the host, prepare the test wheels and run the suite inside the built runtime image:

```bash
python3 backend/scripts/prepare_release_wheels.py --include-tests --output /tmp/camera-vision-wheels
python3 backend/scripts/prepare_os_packages.py --output /tmp/camera-os-packages
docker build --platform linux/amd64 --network none --build-context wheels=/tmp/camera-vision-wheels --build-context osupdates=/tmp/camera-os-packages -t camera-monitoring:dev backend
python3 backend/scripts/run_cloud_backend_checks.py --image camera-monitoring:dev --wheels /tmp/camera-vision-wheels --output /tmp/camera-backend-checks
```

These commands use fixed snapshots and a dedicated networkless, non-root QA container; the QA-only executable tmpfs supports the timeout fixture. The production tmpfs remains noexec. Directory caches must be private and owned; stale/corrupt artifacts fail closed. Experimental pose setup remains a separate Python3.12 environment and must not be installed into the API interpreter.
