import getpass
import json
import subprocess
import urllib.request
import urllib.error

email = input("Correo de Supabase: ")
password = getpass.getpass("Contraseña: ")

script = """
import os, sys, json
from supabase import create_client

credentials = json.load(sys.stdin)
client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"]
)

try:
    response = client.auth.sign_in_with_password(credentials)
    print(json.dumps({"token": response.session.access_token}))
except Exception:
    print(json.dumps({"error": "No se pudo iniciar sesión"}))
"""

result = subprocess.run(
    ["docker", "compose", "exec", "-T", "api", "python", "-c", script],
    input=json.dumps({"email": email, "password": password}),
    text=True,
    capture_output=True
)

if result.returncode != 0:
    print("Error al ejecutar Docker:", result.stderr[:300])
    raise SystemExit(1)

data = json.loads(result.stdout)

if "error" in data:
    print(data["error"])
    raise SystemExit(1)

payload = json.dumps({
    "name": "Camara de prueba",
    "rtsp_url": "rtsp://192.0.2.10:554/stream1"
}).encode()

request = urllib.request.Request(
    "http://localhost:8000/cameras",
    data=payload,
    headers={
        "Authorization": "Bearer " + data["token"],
        "Content-Type": "application/json"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(request, timeout=15) as response:
        print("HTTP:", response.status)
        print("Cámara registrada:", response.read().decode())
except urllib.error.HTTPError as error:
    print("HTTP:", error.code)
    print("Respuesta:", error.read().decode())
