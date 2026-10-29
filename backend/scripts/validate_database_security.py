"""Creates its own networkless PostgreSQL instance. No DSN or production target."""
from pathlib import Path
import subprocess
import sys
import tempfile
import io
import tarfile
from unittest.mock import patch
import time
from uuid import uuid4

IMAGE = "postgres@sha256:baa22e6286bf832cb147b8bb5aa9d8bc999846d69c21d11bf63f58fbeed1fa48"


def main():
    name = f"camera-security-{uuid4().hex[:12]}"
    root = Path(__file__).resolve().parents[2]
    def psql(*args):
        return subprocess.run(["docker", "exec", name, "psql", "-U", "test_admin", "-d", "camera_test",
                               "-v", "ON_ERROR_STOP=1", *args], check=True, capture_output=True, text=True).stdout
    created = False
    try:
        subprocess.run(["docker", "run", "--rm", "-d", "--name", name, "--network", "none", "--tmpfs", "/var/lib/postgresql/data:rw,size=256m,mode=0700",
                        "-e", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE], check=True, capture_output=True)
        created = True
        # Copy only synthetic SQL and migrations through stdin. No checkout bind,
        # credentials, ignored files or daemon-local path assumptions.
        paths=list((root/'backend/migrations').rglob('*.sql')) + [root/'backend/app/tests'/name for name in (
            'setup_test_db.sql','run_real_postgres_security_tests.sql','run_vision_postgres_tests.sql')]
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as bundle:
            for path in paths:bundle.add(path,arcname=str(path.relative_to(root)),recursive=False)
        subprocess.run(['docker','exec',name,'mkdir','-p','/repo'],check=True,capture_output=True)
        subprocess.run(['docker','exec','-i',name,'tar','-xf','-','-C','/repo'],input=archive.getvalue(),check=True,capture_output=True)
        for _ in range(100):
            if subprocess.run(["docker", "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"], capture_output=True).returncode == 0:
                break
            time.sleep(.1)
        else:
            raise RuntimeError("disposable PostgreSQL did not become ready")
        subprocess.run(["docker", "exec", name, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1",
                        "-c", "CREATE ROLE test_admin SUPERUSER LOGIN;", "-c", "CREATE ROLE authenticated NOSUPERUSER;",
                        "-c", "CREATE ROLE anon NOSUPERUSER;", "-c", "CREATE ROLE service_role NOSUPERUSER BYPASSRLS;",
                        "-c", "CREATE DATABASE camera_test OWNER test_admin;"], check=True, capture_output=True)
        psql("-f", "/repo/backend/app/tests/setup_test_db.sql")
        for path in sorted((root / "backend/migrations").glob("[0-9]*.sql")):
            psql("-f", "/repo/backend/migrations/" + path.name)
        output = psql("-f", "/repo/backend/app/tests/run_real_postgres_security_tests.sql")
        assert "PASS:" in output
        print(output.split("PASS:")[-1].strip())
        print(psql("-f", "/repo/backend/app/tests/run_vision_postgres_tests.sql").split("PASS:")[-1].strip())
        sys.path.insert(0,str(root / "backend"))
        artifact_directory=tempfile.mkdtemp(prefix="camera-phase3-workflow-")
        with patch.dict('os.environ',{'SUPABASE_URL':'','SUPABASE_SECRET_KEY':'','FIREBASE_CREDENTIALS_PATH':'','GOOGLE_APPLICATION_CREDENTIALS':''}):
            from vision_workflow_fixture import run as run_vision_fixture
            run_vision_fixture(psql,artifact_directory)
        print("Synthetic workflow artifacts:",artifact_directory)
        psql("-c", """INSERT INTO public.camera_events(id,camera_id,event_type,vision_metadata,evidence_path,is_protected,review_status)
          VALUES('77777777-7777-7777-7777-777777777777','c1000000-0000-0000-0000-000000000001','vision_intrusion','{}','fixture/kept.jpg',true,'reviewed_ok');""")
        psql("-f", "/repo/backend/migrations/rollback/011_vision_rules_and_events.sql")
        assert psql("-tAc", "SELECT count(*) FROM public.camera_events WHERE id='77777777-7777-7777-7777-777777777777' AND evidence_path='fixture/kept.jpg' AND is_protected AND review_status='reviewed_ok'").strip()=="1"
        psql("-c", "DELETE FROM public.camera_events WHERE id='77777777-7777-7777-7777-777777777777'")
        assert psql("-tAc", "SELECT count(*) FROM public.camera_events").strip()=="12"
        psql("-f", "/repo/backend/migrations/011_vision_rules_and_events.sql")
        psql("-f", "/repo/backend/migrations/012_event_query_indexes.sql")
        assert "PASS:" in psql("-f", "/repo/backend/app/tests/run_vision_postgres_tests.sql")
        print("PASS: vision rollback preserves legacy events; reapply passes")
        psql("-f", "/repo/backend/migrations/rollback/010_security_helpers_and_atomic_grants.sql")
        assert psql("-tAc", "SELECT to_regprocedure('public.grant_camera_access_for_actor(uuid,uuid,uuid)') IS NULL").strip() == "t"
        assert psql("-tAc", "SELECT count(*) FROM public.cameras").strip() == "12"
        psql("-f", "/repo/backend/migrations/010_security_helpers_and_atomic_grants.sql")
        assert "PASS:" in psql("-f", "/repo/backend/app/tests/run_real_postgres_security_tests.sql")
        print("PASS: rollback preserves cameras; reapply and security assertions pass")
        psql("-c", """SET ROLE postgres;
          INSERT INTO organizations(id,name) VALUES ('11111111-1111-1111-1111-111111111111','Lock A'),('22222222-2222-2222-2222-222222222222','Lock B');
          UPDATE profiles SET organization_id='11111111-1111-1111-1111-111111111111';
          UPDATE profiles SET role='administrador_flota' WHERE id='d3921003-4c3d-4925-91b3-5efaf8bace03';
          UPDATE cameras SET organization_id='11111111-1111-1111-1111-111111111111' WHERE id='c1000000-0000-0000-0000-000000000001';""")
        sql="""SET application_name='phase2-grant-lock-test'; BEGIN; SET LOCAL ROLE service_role;
          SELECT grant_camera_access_for_actor('d3921003-4c3d-4925-91b3-5efaf8bace03','c1000000-0000-0000-0000-000000000001','e2831002-3b2c-4925-91b3-5efaf8bace02');
          SELECT pg_sleep(3); COMMIT;"""
        holder=subprocess.Popen(["docker","exec",name,"psql","-U","test_admin","-d","camera_test","-v","ON_ERROR_STOP=1","-c",sql],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            for _ in range(80):
                active=psql("-tAc","SELECT count(*) FROM pg_stat_activity WHERE application_name='phase2-grant-lock-test' AND wait_event='PgSleep'").strip()
                if active=='1':break
                time.sleep(.02)
            else:raise RuntimeError("grant transaction did not hold locks")
            try:
                psql("-c","SET lock_timeout='200ms'; SET ROLE postgres; UPDATE profiles SET organization_id='22222222-2222-2222-2222-222222222222' WHERE id='e2831002-3b2c-4925-91b3-5efaf8bace02';")
            except subprocess.CalledProcessError as error:
                if 'lock timeout' not in error.stderr:raise
            else:raise RuntimeError("concurrent organization change was not blocked")
            holder.communicate(timeout=8)
            if holder.returncode:raise RuntimeError("grant transaction failed")
        finally:
            if holder.poll() is None:holder.terminate();holder.communicate(timeout=5)
        print("PASS: concurrent organization change blocked until atomic grant transaction completes")
        before_indexes=psql('-tAc','SELECT count(*) FROM camera_events').strip()
        psql('-f','/repo/backend/migrations/rollback/012_event_query_indexes.sql')
        assert psql('-tAc','SELECT count(*) FROM camera_events').strip()==before_indexes
        assert psql('-tAc',"SELECT to_regclass('public.idx_camera_events_rule_window_v1') IS NULL").strip()=='t'
        for _ in range(2):psql('-f','/repo/backend/migrations/012_event_query_indexes.sql')
        plan=psql('-tAc',"SET enable_seqscan=off; EXPLAIN SELECT id FROM camera_events WHERE camera_id='c1000000-0000-0000-0000-000000000001' AND vision_metadata->>'rule_id'='fixture-rule' ORDER BY detected_at DESC,id DESC LIMIT 30")
        assert 'idx_camera_events_rule_window_v1' in plan
        print('PASS: concurrent indexes valid/idempotent; rollback preserves rows; rule index access path available (not production latency proof)')
        from backup_restore_fixture import run as restore_fixture
        restore_directory=tempfile.mkdtemp(prefix='camera-phase6-restore-')
        restore_fixture(name,restore_directory)
        print('Encrypted backup/restore fixture artifacts:',restore_directory)
    except subprocess.CalledProcessError as exc:
        # SQL fixtures are synthetic, and this runner never has production bindings.
        raise RuntimeError(exc.stderr or "disposable SQL command failed") from None
    finally:
        if created:
            subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True)


if __name__ == "__main__":
    main()
