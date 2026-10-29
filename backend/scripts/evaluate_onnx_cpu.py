"""Isolated CPU differential experiment, not a production adapter or accuracy claim.

Requires separately reviewed onnxruntime installed outside application deps.
Uses the existing verified model and identical preprocess/postprocess/NMS.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.vision.detection import YOLOXDetector,verify_model,MODEL_SHA256
from app.vision.worker import process_resources


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',required=True);p.add_argument('--body-fixture',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    review=json.loads((Path(__file__).resolve().parents[2]/'docs/ai-vision/PHASE_6_ONNX_RUNTIME_REVIEW.json').read_text())
    import onnxruntime as ort
    ort.disable_telemetry_events()
    if ort.__version__!=review['version']:raise ValueError('unreviewed ORT version')
    body=Path(a.body_fixture)
    if body.stat().st_size>2*1024*1024:raise ValueError('fixture budget')
    import hashlib
    if hashlib.sha256(body.read_bytes()).hexdigest()!='88431cd9653ccd539741b555fb0a46b61558b301d4110412b5bc28b5e3ea6cb5':raise ValueError('unreviewed body fixture')
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});cv2.setNumThreads(1)
    model=verify_model(a.model)
    options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1;options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
    session=ort.InferenceSession(model.read_bytes(),sess_options=options,providers=['CPUExecutionProvider'])
    class Net:
        def setInput(self,blob):self.blob=blob
        def forward(self):return session.run(None,{session.get_inputs()[0].name:self.blob})[0]
    native=YOLOXDetector(model);candidate=YOLOXDetector(model);candidate.net=Net()
    pixels=np.zeros((180,320,3),np.uint8);cv2.rectangle(pixels,(30,30),(120,120),(0,180,0),-1)
    frames={'generated_geometry':pixels,'public_body_fixture':cv2.imread(str(body))}
    results=[]
    for label,frame in frames.items():
        left=native.detect(frame);right=candidate.detect(frame)
        assert len(left)==len(right),'detection count differs'
        for x,y in zip(left,right):
            assert x.class_id==y.class_id and abs(x.confidence-y.confidence)<.01
            assert max(abs(getattr(x.bbox,k)-getattr(y.bbox,k)) for k in type(x.bbox).model_fields)<.01
        if label=='public_body_fixture':assert any(d.class_id==0 for d in left),'expected limited positive fixture'
        for name,detector in [('opencv',native),('onnxruntime_cpu',candidate)]:
            for _ in range(2):detector.detect(frame)
            samples=[]
            for _ in range(10):
                start=time.perf_counter();detector.detect(frame);samples.append((time.perf_counter()-start)*1000)
            ordered=sorted(samples)
            results.append({'fixture':label,'engine':name,'samples':len(samples),'latency_ms':{'p50':statistics.median(samples),'p95':ordered[-1]},'detections':len(left)})
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
    report={'result':'PASS','model_sha256':MODEL_SHA256,'onnxruntime':ort.__version__,'providers':session.get_providers(),
      'one_cpu_affinity':True,'results':results,'combined_process_resources':process_resources(),
      'scope':'two permitted frames only, identical adapter preprocessing/NMS; confidence and coordinates agree within .01. Not a natural dataset accuracy, exclusive memory, multicamera or GPU benchmark.',
      'production_runtime_changed':False,'decision':'keep OpenCV until native scan, representative dataset and target pipeline acceptance'}
    output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
