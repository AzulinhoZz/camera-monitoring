"""Explicit, TLS-verified download of the audited ONNX. Never called at runtime."""
import argparse
import os
from pathlib import Path
import sys
import tempfile
from urllib.request import urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.vision.detection import MODEL_SIZE, verify_model

URL='https://media.githubusercontent.com/media/opencv/opencv_zoo/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/object_detection_yolox/object_detection_yolox_2022nov.onnx'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    path=Path(args.output)
    if path.exists():
        verify_model(path);print('Verified existing model');return
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as target:
            temporary=Path(target.name)
            total=0
            with urlopen(URL,timeout=60) as response:
                while chunk:=response.read(1024*1024):
                    total+=len(chunk)
                    if total>MODEL_SIZE:raise ValueError('model exceeds expected size')
                    target.write(chunk)
        verify_model(temporary)
        # Never overwrite an existing user file if another process won the race.
        os.link(temporary,path)
        os.chmod(path,0o644)  # Audited public weights, readable by non-root demo container.
        print('Downloaded and verified audited YOLOX_s model')
    finally:
        if temporary:temporary.unlink(missing_ok=True)


if __name__=='__main__':main()
