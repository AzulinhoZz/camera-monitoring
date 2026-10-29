"""Encrypted backup/restore rehearsal, callable only inside the disposable runner.

Only generated camera data. A private fixture key survives into a separate restore
process. This is NOT a managed key-escrow service. Restores roles in a second cluster.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import sys
from uuid import uuid4

import cv2
import numpy as np
from encrypted_backup import create_key, encrypt
from app.clip_recorder import encode_clip_frames


@contextmanager
def fresh_cluster():
    """Own a networkless cluster; never accept a caller-supplied database target."""
    from validate_database_security import IMAGE
    name="camera-restore-"+uuid4().hex[:12]
    created=False
    try:
        subprocess.run(["docker","run","--rm","-d","--name",name,"--network","none",
                        "--memory","384m","--cpus","1","--pids-limit","96",
                        "--tmpfs","/var/lib/postgresql/data:rw,size=256m,mode=0700",
                        "-e","POSTGRES_HOST_AUTH_METHOD=trust",IMAGE],check=True,capture_output=True,timeout=45)
        created=True
        for _ in range(100):
            ready=subprocess.run(["docker","exec",name,"pg_isready","-h","127.0.0.1","-U","postgres"],capture_output=True,timeout=5)
            if ready.returncode==0:break
            time.sleep(.1)
        else:raise RuntimeError("restore cluster not ready")
        yield name
    finally:
        if created:subprocess.run(["docker","rm","-f",name],capture_output=True,timeout=20,check=False)


def run(container, directory):
    if not re.fullmatch(r'camera-security-[a-f0-9]{12}',container):
        raise ValueError('only an owned disposable fixture container is supported')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    def command(*args, data=None):
        return subprocess.run(['docker','exec',*(['-i'] if data is not None else []),container,*args],input=data,check=True,capture_output=True,timeout=45).stdout
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
        indexes=sql("SELECT COALESCE(jsonb_agg(to_jsonb(i) ORDER BY schemaname,tablename,indexname),'[]'::jsonb) FROM pg_indexes i WHERE schemaname IN ('public','auth','storage')",db)
        return {'indexes_sha256':hashlib.sha256(indexes.encode()).hexdigest(),'table_hashes':rows,'policies_sha256':hashlib.sha256(policies.encode()).hexdigest(),'grants_sha256':hashlib.sha256(grants.encode()).hexdigest()}
    role_query="SELECT jsonb_agg(to_jsonb(r)-'oid' ORDER BY rolname) FROM pg_roles r WHERE rolname !~ '^pg_'"
    roles_before=sql(role_query,db='postgres')
    before=state('camera_test');started=time.monotonic()
    files={'db/database.dump':command('pg_dump','-U','test_admin','-d','camera_test','-Fc'),
           'db/globals.sql':command('pg_dumpall','-U','test_admin','--globals-only'),
           'storage/motion-evidence/'+prefix+'.jpg':jpeg.read_bytes(),
           'storage/motion-clips/'+prefix+'.mp4':clip.read_bytes()}
    manifest={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    source_tree=directory/'durable-source';source_tree.mkdir(mode=0o700)
    for name,data in files.items():
        path=source_tree/name;path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);path.write_bytes(data);path.chmod(0o600)
    key_directory=directory/'keys';key_directory.mkdir(mode=0o700)
    key_file=key_directory/'fixture.key';create_key(key_file)
    target=directory/'fixture.backup.enc';encrypt(source_tree,key_file,target)
    encrypted=target.read_bytes();corrupted=bytearray(encrypted);corrupted[-20]^=1
    damaged=directory/'altered.backup.enc';damaged.write_bytes(corrupted);damaged.chmod(0o600)
    script=Path(__file__).with_name('encrypted_backup.py')
    def restore_process(archive,destination):
        return subprocess.run([sys.executable,str(script),'restore','--key-file',str(key_file),
            '--archive',str(archive),'--destination',str(destination)],capture_output=True,timeout=45)
    rejected=directory/'rejected'
    assert restore_process(damaged,rejected).returncode!=0 and not rejected.exists(),'tampered backup accepted'
    recovered=directory/'authenticated-restore'
    result=restore_process(target,recovered)
    assert result.returncode==0,'independent durable-key restore failed'
    restored={name:(recovered/name).read_bytes() for name in files}
    assert {n:hashlib.sha256(data).hexdigest() for n,data in restored.items()}==manifest
    with fresh_cluster() as destination_container:
        container=destination_container
        # The fresh image owns only postgres. Keep its bootstrap CREATE out of
        # pg_dumpall, but replay all ALTERs and every other dumped role.
        globals_sql=restored['db/globals.sql'].decode()
        globals_sql='\n'.join(line for line in globals_sql.splitlines() if line!='CREATE ROLE postgres;')+'\n'
        command('psql','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1',data=globals_sql.encode())
        assert sql(role_query,db='postgres')==roles_before,'restored role attributes differ'
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
        result={'result':'PASS','scope':'generated data; roles and database restored in independent disposable cluster; local storage directories, not managed Storage',
                'independent_cluster':True,'globals_restored':True,'role_attributes_equal':True,'database_rows_policies_grants_equal':True,'indexes_equal':True,'protected_reviewed_media_preserved':True,'restored_jpeg_readable':True,'restored_mp4_frames':frames,
                'owner_read_allowed_stranger_denied':True,'tamper_rejected':True,'encrypted_backup_sha256':hashlib.sha256(encrypted).hexdigest(),
                'files_sha256':manifest,'elapsed_seconds':time.monotonic()-started,'key_persisted':True,'separate_restore_process':True,'key_permissions':'0600; parent 0700',
                'limits':'Globals replayed in independent cluster (bootstrap postgres CREATE excluded). Durable fixture key survives in a private local directory; no managed escrow, rotation, Storage or RPO/RTO acceptance.'}
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS: streamed encrypted fixture backup + durable key + separate restore process -> independent cluster/roles/database/storage -> rows/RLS/grants/media/owner isolation; corruption rejected')
        return result
