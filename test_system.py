import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def req(url, method="GET", data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    request = urllib.request.Request(f"{BASE_URL}{url}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            content = resp.read().decode()
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode()
        return e.code, json.loads(content) if content else {}

def run_tests():
    log("=== RUNNING CAMERAMONITORING INTEGRATION TESTS ===")

    # 1. Health check
    status, res = req("/health")
    assert status == 200, f"Health check failed: {res}"
    log("Health check passed: " + json.dumps(res))

    # 2. Database health
    status, res = req("/health/db")
    assert status == 200, f"DB health check failed: {res}"
    log("DB health check passed: " + json.dumps(res))

    # 3. User 1 Login
    user1_email = "admin@cameramonitoring.com"
    user1_pass = "CameraMon123!"
    status, res = req("/auth/login", method="POST", data={"email": user1_email, "password": user1_pass})
    assert status == 200, f"Login failed for {user1_email}: {res}"
    token1 = res["access_token"]
    user1_id = res["user"]["id"]
    log(f"User 1 logged in successfully. User ID: {user1_id}")

    # 4. Get Current User /auth/me
    status, res = req("/auth/me", token=token1)
    assert status == 200 and res["email"] == user1_email, f"GET /auth/me failed: {res}"
    log("GET /auth/me passed: " + json.dumps(res))

    # 5. Create Camera for User 1
    cam_data = {
        "name": "Camara Entrada Principal",
        "rtsp_url": "rtsp://10.0.2.2:8554/camara1"
    }
    status, cam_res = req("/cameras", method="POST", data=cam_data, token=token1)
    assert status == 201, f"Create camera failed: {cam_res}"
    cam_id = cam_res["id"]
    log("Create camera passed: " + json.dumps(cam_res))

    # 6. Edit Camera for User 1 (PUT /cameras/{id})
    edit_data = {
        "name": "Camara Editada Principal",
        "rtsp_url": "rtsp://10.0.2.2:8554/camara1_edited"
    }
    status, edit_res = req(f"/cameras/{cam_id}", method="PUT", data=edit_data, token=token1)
    assert status == 200 and edit_res["name"] == "Camara Editada Principal", f"Edit camera failed: {edit_res}"
    log("Edit camera passed: " + json.dumps(edit_res))

    # 7. List Cameras for User 1
    status, list_res = req("/cameras", token=token1)
    assert status == 200 and list_res["total"] >= 1, f"List cameras failed: {list_res}"
    log(f"List cameras passed. Total cameras for User 1: {list_res['total']}")

    # 8. Get Specific Camera
    status, single_cam = req(f"/cameras/{cam_id}", token=token1)
    assert status == 200 and single_cam["id"] == cam_id, f"Get camera failed: {single_cam}"
    log("Get camera details passed: " + json.dumps(single_cam))

    # 9. Create Motion Event for Camera
    event_data = {
        "camera_id": cam_id,
        "event_type": "motion_detected",
        "description": "Prueba de alerta de movimiento OpenCV"
    }
    status, event_res = req("/events", method="POST", data=event_data, token=token1)
    assert status == 201, f"Create event failed: {event_res}"
    log("Create motion event passed: " + json.dumps(event_res))

    # 10. List Events for User 1
    status, events_list = req("/events", token=token1)
    assert status == 200 and events_list["total"] >= 1, f"List events failed: {events_list}"
    log(f"List events passed. Total events for User 1: {events_list['total']}")

    # 11. Test User Isolation (User 2)
    import subprocess
    cmd = """
import os, json
from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
try:
    client.auth.sign_up({"email": "user2@cameramonitoring.com", "password": "User2Pass123!"})
except: pass
for u in client.auth.admin.list_users():
    if u.email == "user2@cameramonitoring.com":
        client.auth.admin.update_user_by_id(u.id, {"email_confirm": True})
"""
    subprocess.run(["docker", "compose", "exec", "-T", "api", "python", "-c", cmd])

    status, u2_login = req("/auth/login", method="POST", data={"email": "user2@cameramonitoring.com", "password": "User2Pass123!"})
    assert status == 200, f"User 2 login failed: {u2_login}"
    token2 = u2_login["access_token"]

    # User 2 tries to edit User 1's camera -> 404/403
    status, u2_edit = req(f"/cameras/{cam_id}", method="PUT", data={"name": "Hacked Name"}, token=token2)
    assert status in (403, 404), f"User isolation broken! User 2 edited User 1's camera: {u2_edit}"
    log("Camera edit ownership protection PASSED: User 2 cannot edit User 1's camera")

    # User 2 tries to delete User 1's camera -> 404/403
    status, u2_del = req(f"/cameras/{cam_id}", method="DELETE", token=token2)
    assert status in (403, 404), f"User isolation broken! User 2 deleted User 1's camera: {u2_del}"
    log("Camera delete ownership protection PASSED: User 2 cannot delete User 1's camera")

    # 12. User 1 Deletes Camera
    status, del_res = req(f"/cameras/{cam_id}", method="DELETE", token=token1)
    assert status == 200, f"Delete camera failed: {del_res}"
    log("Delete camera passed: " + json.dumps(del_res))

    log("=== ALL SYSTEM INTEGRATION TESTS PASSED SUCCESSFULLY! ===", "SUCCESS")

if __name__ == "__main__":
    run_tests()
