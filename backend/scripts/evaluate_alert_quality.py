"""Offline event-quality scoring. Does not run a model, download video or tune production."""
import argparse
from bisect import bisect_right
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

SCENARIOS={'day','night','rain','pets','shadows','occlusion','other'}


def number(value,minimum,maximum):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not minimum<=value<=maximum:
        raise ValueError('invalid numeric annotation')
    return value


def validate(document):
    if document.get('dataset_kind') not in ('synthetic','authorized_video_annotations') or document.get('split') not in ('calibration','test'):
        raise ValueError('dataset kind and split required')
    if not isinstance(document.get('rights_reference'),str) or not document['rights_reference'].strip():raise ValueError('rights reference required')
    sequences=document.get('sequences')
    if not isinstance(sequences,list) or not 1<=len(sequences)<=10000:raise ValueError('sequence budget')
    seen=set()
    for row in sequences:
        identifier=row['id']
        if not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',identifier) or identifier in seen:raise ValueError('unique pseudonymous sequence ID required')
        seen.add(identifier)
        if row['scenario'] not in SCENARIOS:raise ValueError('unknown scenario')
        duration=number(row['duration_seconds'],.1,86400)
        if document['dataset_kind']=='authorized_video_annotations' and not re.fullmatch('[a-f0-9]{64}',row.get('video_sha256','')):raise ValueError('video provenance hash required')
        if not isinstance(row['expected'],list) or not isinstance(row['predictions'],list) or max(len(row['expected']),len(row['predictions']))>10000:raise ValueError('event budget')
        windows=defaultdict(list)
        for event in row['expected']:
            start=number(event['start_seconds'],0,duration);end=number(event['end_seconds'],start,duration)
            if not re.fullmatch(r'[a-z_]{1,64}',event['event_type']):raise ValueError('event type')
            windows[event['event_type']].append((start,end))
        for spans in windows.values():
            spans.sort()
            if any(b[0]<=a[1] for a,b in zip(spans,spans[1:])):raise ValueError('same-type annotation windows must not overlap')
        for event in row['predictions']:
            number(event['at_seconds'],0,duration);number(event['confidence'],0,1)
            if not re.fullmatch(r'[a-z_]{1,64}',event['event_type']):raise ValueError('event type')
    return sequences


def metrics(tp,fp,fn,seconds):
    precision=tp/(tp+fp) if tp+fp else None;recall=tp/(tp+fn) if tp+fn else None
    return {'tp':tp,'fp':fp,'fn':fn,'precision':precision,'recall':recall,
            'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            'video_hours':seconds/3600,'false_alerts_per_video_hour':fp/(seconds/3600) if seconds else None}


def evaluate(document,threshold=.5):
    number(threshold,0,1);rows=validate(document);groups=defaultdict(lambda:[0,0,0,0.])
    negative_seconds=negative_fp=0
    for row in rows:
        matched=set();fp=0
        windows=defaultdict(list)
        for index,event in enumerate(row['expected']):windows[event['event_type']].append((event['start_seconds'],event['end_seconds'],index))
        for spans in windows.values():spans.sort()
        starts={kind:[span[0] for span in spans] for kind,spans in windows.items()}
        for prediction in sorted(row['predictions'],key=lambda p:p['at_seconds']):
            if prediction['confidence']<threshold:continue
            spans=windows.get(prediction['event_type'],[])
            position=bisect_right(starts.get(prediction['event_type'],[]),prediction['at_seconds'])-1
            match=spans[position][2] if position>=0 and prediction['at_seconds']<=spans[position][1] and spans[position][2] not in matched else None
            if match is None:fp+=1
            else:matched.add(match)
        counts=[len(matched),fp,len(row['expected'])-len(matched),row['duration_seconds']]
        for name in ('all',row['scenario']):
            groups[name]=[a+b for a,b in zip(groups[name],counts)]
        if not row['expected']:negative_seconds+=row['duration_seconds'];negative_fp+=fp
    return {'dataset_kind':document['dataset_kind'],'split':document['split'],'threshold':threshold,'not_evaluated_scenarios':sorted(SCENARIOS-{row['scenario'] for row in rows}),
            'metrics':{key:metrics(*value) for key,value in groups.items()},
            'negative_only_false_alerts_per_hour':negative_fp/(negative_seconds/3600) if negative_seconds else None,
            'limits':'One-to-one event-window comparison of supplied outputs, not frame mAP or model execution. Rights are operator-declared. No deployment/config changes.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--threshold',type=float,default=.5);args=p.parse_args()
    source=Path(args.input)
    if source.stat().st_size>16*1024*1024:p.error('annotation size budget')
    document=json.loads(source.read_text());result=evaluate(document,args.threshold)
    result['input_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    if document['split']=='calibration':result['calibration_curve']=[evaluate(document,t)['metrics']['all']|{'threshold':t} for t in (.3,.5,.7,.9)]
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2)+'\n');target.chmod(0o600)
    print(json.dumps({'result':'SCORED','dataset_kind':document['dataset_kind'],'sequences':len(document['sequences']),'scope':'offline_annotations_only'}))

if __name__=='__main__':main()
