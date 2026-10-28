"""Original OpenCV overlay helpers. Geometry/effects do not classify actions."""
import cv2
import numpy as np

# Anatomical connections using the documented landmark indices; no face edges.
BODY_EDGES=((11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),
            (23,24),(23,25),(25,27),(24,26),(26,28),(27,29),(29,31),(28,30),(30,32))
HAND_EDGES=((0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
            (5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),
            (13,17),(0,17),(17,18),(18,19),(19,20))


def lm_px(point,width,height):
    """Normalized image position to valid pixel; outside image returns None."""
    if not 1<=width<=1280 or not 1<=height<=720:
        raise ValueError('invalid render dimensions')
    if not 0<=point.x<=1 or not 0<=point.y<=1:
        return None
    return min(width-1,round(point.x*(width-1))),min(height-1,round(point.y*(height-1)))


def draw_energy_line(canvas,start,end,color):
    """Decorative glow only. No classification or change to the original frame."""
    cv2.line(canvas,start,end,tuple(int(c*.25) for c in color),7,cv2.LINE_AA)
    cv2.line(canvas,start,end,color,3,cv2.LINE_AA)
    cv2.line(canvas,start,end,(240,240,240),1,cv2.LINE_AA)


def draw_skeleton(image,packet,scope,*,min_quality=.6,energy_effect=False,show_unscored_hands=False):
    packet.require_scope(scope)
    if not isinstance(image,np.ndarray) or image.dtype!=np.uint8 or image.ndim!=3 or image.shape[2]!=3:
        raise ValueError('expected uint8 BGR frame')
    height,width=image.shape[:2]
    if not 0<=min_quality<=1 or not 1<=width<=1280 or not 1<=height<=720:
        raise ValueError('invalid render limits')
    output=image.copy()
    for observation in packet.observations:
        points={p.index:lm_px(p,width,height) for p in observation.points if p.reliable(min_quality) or (show_unscored_hands and observation.kind=='hand' and observation.quality_basis=='detector_presence_only' and 0<=p.x<=1 and 0<=p.y<=1)}
        edges=BODY_EDGES if observation.kind=='pose_body' else HAND_EDGES
        color=(80,230,80) if observation.kind=='pose_body' else (255,180,40)
        for a,b in edges:
            if a in points and b in points:
                if energy_effect:draw_energy_line(output,points[a],points[b],color)
                else:cv2.line(output,points[a],points[b],color,2,cv2.LINE_AA)
        for point in points.values():cv2.circle(output,point,3,color,-1,cv2.LINE_AA)
    return output
