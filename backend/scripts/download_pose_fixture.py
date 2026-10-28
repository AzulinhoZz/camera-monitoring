"""Permitted NASA/public-domain and TensorFlow.js/Apache-2.0 fixtures. No third-party Python code is executed."""
import argparse,hashlib,io,os,tempfile,urllib.request,zipfile
from pathlib import Path

URL='https://files.pythonhosted.org/packages/f4/a2/70401a107d6d7466d64b466927e6b96fcefa99d57494b972608e2f8be50f/scikit_image-0.26.0-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl'
SIZE=13561683
WHEEL_SHA='7df650e79031634ac90b11e64a9eedaf5a5e06fcd09bcd03a34be01745744466'
HAND_URL='https://raw.githubusercontent.com/tensorflow/tfjs-models/c731b9ebbd6f4c9e8bf99b0df76bbdbf9c25b07f/hand-pose-detection/test_data/hands.jpg'
HAND_SHA='240c082e80128ff1ca8a83ce645e2ba4d8bc30f0967b7991cf5fa375bab489e1'
HAND_SIZE=54888
IMAGE_SHA='88431cd9653ccd539741b555fb0a46b61558b301d4110412b5bc28b5e3ea6cb5'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);parser.add_argument('--kind',choices=('body','hand'),default='body');args=parser.parse_args()
    path=Path(args.output)
    expected=HAND_SHA if args.kind=='hand' else IMAGE_SHA
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('refusing to overwrite existing fixture')
        print('Verified permitted fixture');return
    if args.kind=='hand':
        with urllib.request.urlopen(HAND_URL,timeout=30) as response:image=response.read(HAND_SIZE+1)
        if len(image)!=HAND_SIZE:raise ValueError('hand fixture size mismatch')
    else:
        with urllib.request.urlopen(URL,timeout=60) as response:data=response.read(SIZE+1)
        if len(data)!=SIZE or hashlib.sha256(data).hexdigest()!=WHEEL_SHA:raise ValueError('fixture source mismatch')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:image=archive.read('skimage/data/astronaut.png')
    if hashlib.sha256(image).hexdigest()!=expected:raise ValueError('fixture image mismatch')
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as target:
        target.write(image);name=Path(target.name)
    try:os.link(name,path)
    finally:name.unlink(missing_ok=True)
    print('Downloaded verified permitted fixture; see docs/ai-vision/PHASE_4_FIXTURE_REVIEW.md for license and attribution')

if __name__=='__main__':main()
