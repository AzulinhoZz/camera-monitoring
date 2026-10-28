"""Private fd-based MediaPipe backend, invoked by PoseProcess in a separate venv.

No API, network, source URL, secret, dynamic download or raw landmark logging.
"""
import hashlib
import importlib.metadata
import json
import mmap
import os
from pathlib import Path
import socket
import sys

MAX_BYTES=1280*720*3
MODEL_VERSION='mediapipe:0.10.32:tasks-source-0.10.21:full:v1'
MODELS={
 'pose_full.task':(9398078,'c1492ead320c87471d9ae324ee00d1e057636522e991d339ff8f07e90982d4aa'),
 'hand_full.task':(7819594,'e5fe265a93d7f530428a4b22f230598c3655de527c12deed889514bc890d0508'),
}


def receive(sock):
    data=bytearray()
    while not data.endswith(b'\n'):
        chunk=sock.recv(4096)
        if not chunk:raise EOFError
        data.extend(chunk)
        if len(data)>65536:raise ValueError('pose IPC limit')
    return json.loads(data)


def send(sock,message):
    data=json.dumps(message,separators=(',',':')).encode()+b'\n'
    if len(data)>65536:raise ValueError('pose IPC limit')
    sock.sendall(data)


def verify_models(root=None):
    # Verify before importing native MediaPipe or loading any graph.
    for name,version in {'mediapipe':'0.10.32','numpy':'2.5.4','opencv-contrib-python':'5.0.0.93','pydantic':'2.14.1'}.items():
        if importlib.metadata.version(name)!=version:raise ValueError('unapproved runtime version')
    root=Path(root) if root is not None else Path(sys.prefix)/'share/camera-monitoring/models'
    for name,(size,digest) in MODELS.items():
        path=root/name
        if path.stat().st_size!=size or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('unapproved bundled model')


def main():
    # Linux child dies with its supervisor; account for death before prctl.
    expected=int(sys.argv[3])
    import ctypes,signal
    if ctypes.CDLL(None,use_errno=True).prctl(1,signal.SIGKILL)!=0 or os.getppid()!=expected:
        return 2
    sock=socket.socket(fileno=int(sys.argv[1]))
    shared=mmap.mmap(int(sys.argv[2]),MAX_BYTES,access=mmap.ACCESS_READ)
    try:
        verify_models()
        models=Path(sys.prefix)/"share/camera-monitoring/models"
        import cv2
        import mediapipe as mp
        import numpy as np
        from .contracts import CameraScope
        from .landmarks import Landmark,LandmarkSet,LandmarkFrame
        cv2.setNumThreads(1)
        hello=receive(sock);scope=CameraScope.model_validate(hello['scope'])
        # Audited local bundles only. Tasks never receives a URL or asset download callback.
        from mediapipe.tasks.python import vision,BaseOptions
        pose_options=vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_buffer=(models/'pose_full.task').read_bytes(),delegate=BaseOptions.Delegate.CPU),num_poses=1,min_pose_detection_confidence=.6,min_pose_presence_confidence=.6)
        hand_options=vision.HandLandmarkerOptions(base_options=BaseOptions(model_asset_buffer=(models/'hand_full.task').read_bytes(),delegate=BaseOptions.Delegate.CPU),num_hands=2,min_hand_detection_confidence=.6,min_hand_presence_confidence=.6)
        with vision.PoseLandmarker.create_from_options(pose_options) as pose,vision.HandLandmarker.create_from_options(hand_options) as hands:
            send(sock,{'ready':True,'model_version':MODEL_VERSION})
            while True:
                request=receive(sock)
                if request.get('stop'):break
                width,height=request['width'],request['height']
                if not isinstance(width,int) or not isinstance(height,int) or not 1<=width<=1280 or not 1<=height<=720:
                    raise ValueError('invalid frame dimensions')
                pixels=np.frombuffer(shared,dtype=np.uint8,count=width*height*3).reshape(height,width,3).copy()
                rgb=cv2.cvtColor(pixels,cv2.COLOR_BGR2RGB)
                image=mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb)
                body=pose.detect(image);hand=hands.detect(image)
                observations=[]
                if body.pose_landmarks:
                    points=tuple(Landmark(index=i,x=p.x,y=p.y,z=p.z,visibility=p.visibility,presence=p.presence) for i,p in enumerate(body.pose_landmarks[0]) if i>=11)
                    observations.append(LandmarkSet(kind='pose_body',landmark_set_id=0,points=points))
                for i,result in enumerate(hand.hand_landmarks or []):
                    points=tuple(Landmark(index=n,x=p.x,y=p.y,z=p.z) for n,p in enumerate(result))
                    observations.append(LandmarkSet(kind='hand',landmark_set_id=i,quality_basis='detector_presence_only',points=points))
                packet=LandmarkFrame(**scope.model_dump(),worker_session_id=request['session'],frame_sequence=request['sequence'],timestamp=request['timestamp'],model_version=MODEL_VERSION,image_width=width,image_height=height,observations=tuple(observations))
                send(sock,{'packet':packet.model_dump(mode='json')})
    except (EOFError,BrokenPipeError):pass
    except Exception:
        try:send(sock,{'error':'pose_runtime_failed'})
        except Exception:pass
        return 1
    finally:
        shared.close();sock.close()
    return 0

if __name__=='__main__':raise SystemExit(main())
