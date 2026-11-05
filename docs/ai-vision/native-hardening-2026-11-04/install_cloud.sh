#!/usr/bin/env bash
set -euo pipefail
cd /workspace/camera-monitoring
if [ ! -f backend/os-packages/APKINDEX.tar.gz ] || [ ! -f backend/scripts/run_cloud_backend_checks.py ]; then
  echo 'The reviewed feature-branch source is required; preserve existing changes and restore that source before setup.' >&2
  exit 1
fi
camera_setup_root=/workspace/.camera-tools/cloud-runtime
mkdir -p -m 700 "$camera_setup_root" /workspace/.camera-tools/buildx
export BUILDX_CONFIG=/workspace/.camera-tools/buildx
python3 backend/scripts/prepare_release_wheels.py --include-tests --output "$camera_setup_root/wheels"
python3 backend/scripts/prepare_os_packages.py --output "$camera_setup_root/os-packages"
docker buildx build --platform linux/amd64 --network none --build-context "wheels=$camera_setup_root/wheels" --build-context "osupdates=$camera_setup_root/os-packages" -t camera-monitoring-cloud:dev --load backend
python3 backend/scripts/download_vision_model.py --output "$camera_setup_root/models/yolox_s.onnx"
python3 backend/scripts/validate_release_image.py --image camera-monitoring-cloud:dev --model "$camera_setup_root/models/yolox_s.onnx" --output "$camera_setup_root/smoke"
python3 backend/scripts/run_cloud_backend_checks.py --image camera-monitoring-cloud:dev --wheels "$camera_setup_root/wheels" --output "$camera_setup_root/checks"
