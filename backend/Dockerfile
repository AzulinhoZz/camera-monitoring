# Reviewed public Wolfi base; native findings remain a release gate.
FROM cgr.dev/chainguard/wolfi-base@sha256:771146c2dfc880902a185f060c3db5571473c46b267edd98c3119c83068dfb61
USER 0:0
# Packages are authenticated against the frozen upstream signed index, then pinned by SHA256.
RUN --mount=type=bind,from=osupdates,target=/os-updates,readonly \
    (cd /os-updates && sha256sum -c SHA256SUMS) && \
    set -- && while IFS= read -r constraint; do set -- "$@" "$constraint"; done < /os-updates/world.txt && \
    apk --no-network --no-cache --repositories-file /dev/null --repository /os-updates add "$@" && \
    python3.13 -m venv /venv
ENV PATH=/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
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
