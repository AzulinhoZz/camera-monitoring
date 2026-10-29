import copy
import json
from pathlib import Path
import runpy
import pytest

ROOT=Path(__file__).resolve().parents[2]
MODULE=runpy.run_path(str(ROOT/'backend/scripts/evaluate_alert_quality.py'))


def fixture():return json.loads((ROOT/'backend/app/tests/fixtures/alert-quality.synthetic.json').read_text())


def test_duplicate_alerts_and_negative_scenes_are_false_positives():
    result=MODULE['evaluate'](fixture(),.5)
    assert (result['metrics']['all']['tp'],result['metrics']['all']['fp'],result['metrics']['all']['fn'])==(1,2,0)
    assert result['metrics']['all']['precision']==pytest.approx(1/3)
    assert result['negative_only_false_alerts_per_hour']==60
    assert MODULE['evaluate'](fixture(),.7)['metrics']['all']['fp']==0


def test_undefined_metrics_are_not_reported_as_perfect_quality():
    data=fixture();data['sequences']=data['sequences'][1:];data['sequences'][0]['predictions']=[]
    result=MODULE['evaluate'](data)['metrics']['all']
    assert result['precision'] is None and result['recall'] is None and result['f1'] is None


@pytest.mark.parametrize('issue',['rights','overlap','nan','duplicate','provenance'])
def test_invalid_or_unattributed_annotations_are_rejected(issue):
    data=fixture()
    if issue=='rights':data['rights_reference']=''
    if issue=='overlap':data['sequences'][0]['expected']*=2
    if issue=='nan':data['sequences'][0]['predictions'][0]['confidence']=float('nan')
    if issue=='duplicate':data['sequences'].append(copy.deepcopy(data['sequences'][0]))
    if issue=='provenance':data['dataset_kind']='authorized_video_annotations'
    with pytest.raises(ValueError):MODULE['evaluate'](data)
