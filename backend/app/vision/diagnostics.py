"""Technical health signals; never classify a person or persist an incident."""
import math


def diagnose(snapshot, frame_age, target_fps=2.0):
    if not math.isfinite(target_fps) or not .1<=target_fps<=60:target_fps=2.0
    codes=[]
    if not snapshot.healthy or snapshot.state!='streaming':codes.append('capture_unavailable')
    if frame_age>3:codes.append('frame_stale')
    if snapshot.inference_frames==0:codes.append('inference_not_ready')
    elif snapshot.inference_fps<target_fps:codes.append('inference_below_target')
    if snapshot.inference_dropped>0:codes.append('inference_drops_observed')
    return {'codes':codes,'target_fps':target_fps,'ready':not any(code!='inference_drops_observed' for code in codes),
            'scope':'technical_health_only'}
