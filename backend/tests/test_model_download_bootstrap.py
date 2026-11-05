"""A cold host must prepare the model before OpenCV or API dependencies are installed."""
import os
from pathlib import Path
import subprocess
import sys


def test_model_downloader_help_works_without_site_packages():
    script=Path(__file__).resolve().parents[1]/'scripts/download_vision_model.py'
    result=subprocess.run([sys.executable,'-S',str(script),'--help'],capture_output=True,text=True,
                          env={'PATH':os.environ.get('PATH',''),'PYTHONDONTWRITEBYTECODE':'1'},timeout=10)
    assert result.returncode==0, result.stderr
    assert '--output' in result.stdout
