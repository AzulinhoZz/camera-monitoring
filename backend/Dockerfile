# Frozen official base observed during phase 5; OS scan remains a release gate.
FROM python:3.12-slim@sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f
WORKDIR /code
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# One application layer avoids repeated full snapshots on constrained builders.
# Only the reviewed runtime assets below leave the readonly build-context mount.
RUN --mount=type=bind,target=/src,readonly \
    --mount=type=bind,from=wheels,target=/wheels,readonly \
    pip install --no-index --find-links=/wheels --no-cache-dir --only-binary=:all: --require-hashes -r /src/requirements-tooling.lock && \
    pip install --no-index --find-links=/wheels --no-cache-dir --only-binary=:all: --require-hashes -r /src/requirements-runtime.lock && \
    pip check && \
    mkdir -p /config /licenses /run/camera-leases && chmod 1777 /run/camera-leases && \
    cp -R /src/app /code/app && cp -R /src/migrations /code/migrations && \
    cp -R /src/licenses/. /licenses/ && \
    cp /src/vision-worker.example.json /config/vision.json && \
    cp /src/vision-detection.example.json /config/detection.json && \
    cp /src/vision-fleet.example.json /config/fleet.json && \
    cp /src/requirements-runtime.lock /src/requirements-tooling.lock /code/ && \
    chown -R 65534:65534 /code /config /licenses
USER 65534:65534
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
