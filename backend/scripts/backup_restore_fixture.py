"""Encrypted backup/restore rehearsal, callable only inside the disposable runner.

Only generated camera data. Keys remain in memory: this is NOT an operational
backup/key-escrow service. Restores a fresh database in the same test cluster.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import time
from uuid import uuid4

import cv2
import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from app.clip_recorder import encode_clip_frames


def run(container, directory):
    if not re.fullmatch(r'camera-security-[a-f0-9]{12}',container):
        raise ValueError('only an owned disposable fixture container is supported')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    def command(*args, data=None):
        return subprocess.run(['docker','exec',*(['-i'] if data is not None else []),container,*args],input=data,check=True,capture_output=True).stdout
    def sql(query,db='camera_test'):
        return command('psql','-U','test_admin','-d',db,'-v','ON_ERROR_STOP=1','-tAc',query).decode().strip()
    camera=json.loads(sql("SELECT jsonb_build_object('id',id,'owner',user_id) FROM cameras ORDER BY id LIMIT 1"))
    event=str(uuid4());prefix=f"{camera['owner']}/{camera['id']}/{event}"
    source=directory/'source';source.mkdir(mode=0o700)
    jpeg=source/'snapshot.jpg';clip=source/'clip.mp4'
    pixels=np.full((72,128,3),(30,80,120),np.uint8)
    assert cv2.imwrite(str(jpeg),pixels)
    encode_clip_frames([pixels]*10,clip,5)
    sql(f"INSERT INTO camera_events(id,camera_id,event_type,evidence_path,clip_path,is_protected,review_status) VALUES('{event}','{camera['id']}','motion_detected','{prefix}.jpg','{prefix}.mp4',true,'reviewed_ok')")
    def state(db):
        tables=json.loads(sql("SELECT jsonb_agg(jsonb_build_array(schemaname,tablename) ORDER BY schemaname,tablename) FROM pg_tables WHERE schemaname IN ('public','auth','storage')",db))
        rows={}
        for schema,table in tables:
            ident='"'+schema.replace('"','""')+'"."'+table.replace('"','""')+'"'
            value=sql(f"SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM {ident} t",db)
            rows[schema+'.'+table]=hashlib.sha256(value.encode()).hexdigest()
        policies=sql("SELECT COALESCE(jsonb_agg(to_jsonb(p) ORDER BY schemaname,tablename,policyname),'[]'::jsonb) FROM pg_policies p WHERE schemaname IN ('public','auth','storage')",db)
        grants=sql("SELECT COALESCE(jsonb_agg(to_jsonb(g)-'table_catalog' ORDER BY table_schema,table_name,grantee,privilege_type),'[]'::jsonb) FROM information_schema.role_table_grants g WHERE table_schema IN ('public','auth','storage')",db)
        return {'table_hashes':rows,'policies_sha256':hashlib.sha256(policies.encode()).hexdigest(),'grants_sha256':hashlib.sha256(grants.encode()).hexdigest()}
    before=state('camera_test');started=time.monotonic()
    files={'db/database.dump':command('pg_dump','-U','test_admin','-d','camera_test','-Fc'),
           'db/globals.sql':command('pg_dumpall','-U','test_admin','--globals-only'),
           'storage/motion-evidence/'+prefix+'.jpg':jpeg.read_bytes(),
           'storage/motion-clips/'+prefix+'.mp4':clip.read_bytes()}
    manifest={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w') as archive:
        for name,data in files.items():
            member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o600
            archive.addfile(member,io.BytesIO(data))
    key=AESGCM.generate_key(bit_length=256);nonce=os.urandom(12);aad=b'camera-monitoring-disposable-backup-v1'
    encrypted=nonce+AESGCM(key).encrypt(nonce,stream.getvalue(),aad)
    target=directory/'fixture.backup.enc';target.write_bytes(encrypted);target.chmod(0o600)
    corrupted=bytearray(encrypted);corrupted[-1]^=1
    try:AESGCM(key).decrypt(bytes(corrupted[:12]),bytes(corrupted[12:]),aad)
    except InvalidTag:pass
    else:raise AssertionError('tampered backup was accepted')
    plaintext=AESGCM(key).decrypt(encrypted[:12],encrypted[12:],aad)
    restored={}
    with tarfile.open(fileobj=io.BytesIO(plaintext),mode='r:') as archive:
        for member in archive.getmembers():
            if not member.isfile() or member.name not in manifest or member.size>16*1024*1024:raise ValueError('invalid backup entry')
            restored[member.name]=archive.extractfile(member).read()
    assert {n:hashlib.sha256(d).hexdigest() for n,d in restored.items()}==manifest
    sql('CREATE DATABASE camera_restored OWNER test_admin',db='postgres')
    command('pg_restore','-U','test_admin','-d','camera_restored','--exit-on-error',data=restored['db/database.dump'])
    assert state('camera_restored')==before,'database rows, RLS policies or grants differ'
    destination=directory/'restored-storage';destination.mkdir(mode=0o700)
    for name,data in restored.items():
        if name.startswith('storage/'):
            relative=Path(name).relative_to('storage')
            path=destination/relative;path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);path.write_bytes(data);path.chmod(0o600)
    jpg=destination/'motion-evidence'/f'{prefix}.jpg';mp4=destination/'motion-clips'/f'{prefix}.mp4'
    assert cv2.imread(str(jpg)) is not None
    video=cv2.VideoCapture(str(mp4));ok,_=video.read();frames=int(video.get(cv2.CAP_PROP_FRAME_COUNT));video.release()
    assert ok and frames==10
    assert sql(f"SELECT count(*) FROM camera_events WHERE id='{event}' AND is_protected AND review_status='reviewed_ok' AND evidence_path='{prefix}.jpg' AND clip_path='{prefix}.mp4'",db='camera_restored')=='1'
    assert sql(f"SET ROLE authenticated; SET request.jwt.claim.sub='{camera['owner']}'; SELECT count(*) FROM camera_events WHERE id='{event}'",db='camera_restored').splitlines()[-1]=='1'
    assert sql(f"SET ROLE authenticated; SET request.jwt.claim.sub='{uuid4()}'; SELECT count(*) FROM camera_events WHERE id='{event}'",db='camera_restored').splitlines()[-1]=='0'
    result={'result':'PASS','scope':'generated data; new database in same disposable cluster; local storage directories, not managed Storage',
            'database_rows_policies_grants_equal':True,'protected_reviewed_media_preserved':True,'restored_jpeg_readable':True,'restored_mp4_frames':frames,
            'owner_read_allowed_stranger_denied':True,'tamper_rejected':True,'encrypted_backup_sha256':hashlib.sha256(encrypted).hexdigest(),
            'files_sha256':manifest,'elapsed_seconds':time.monotonic()-started,'key_persisted':False,
            'limits':'Globals backed up but roles already exist in same cluster. In-memory key is discarded; encrypted fixture is not usable as a future operational backup. No RPO/RTO acceptance.'}
    (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: encrypted fixture backup -> fresh database/storage -> rows/RLS/grants/media/owner isolation; corruption rejected')
    return result
