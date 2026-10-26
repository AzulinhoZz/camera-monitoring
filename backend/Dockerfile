FROM python:3.12-slim
WORKDIR /code
COPY requirements.txt .
# Optional public CA bundle for environments with a trusted TLS egress proxy.
# Mounted only during build; no verification bypass and no credentials in image.
RUN --mount=type=secret,id=package_ca \
    if [ -f /run/secrets/package_ca ]; then \
        PIP_CERT=/run/secrets/package_ca pip install --no-cache-dir -r requirements.txt; \
    else pip install --no-cache-dir -r requirements.txt; fi
COPY --chown=65534:65534 app ./app
COPY --chown=65534:65534 vision-worker.example.json /config/vision.json
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
