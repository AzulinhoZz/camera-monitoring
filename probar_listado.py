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
    if not response.session:
        print(json.dumps({"error": "No se obtuvo sesión"}))
    else:
        print(json.dumps({"token": response.session.access_token}))
except Exception:
    print(json.dumps({"error": "Credenciales inválidas"}))
"""

result = subprocess.run(
    ["docker", "compose", "exec", "-T", "api", "python", "-c", script],
    input=json.dumps({"email": email, "password": password}),
    text=True,
    capture_output=True,
)

del password

if result.returncode != 0:
    print("Error de Docker:", result.stderr[:200])
    raise SystemExit(1)

try:
    data = json.loads(result.stdout)
except json.JSONDecodeError:
    print("Respuesta inesperada de Docker")
    raise SystemExit(1)

if "error" in data:
    print(data["error"])
    raise SystemExit(1)

request = urllib.request.Request(
    "http://localhost:8000/cameras",
    headers={"Authorization": "Bearer " + data["token"]},
)

try:
    with urllib.request.urlopen(request, timeout=15) as response:
        print("HTTP:", response.status)
        print(json.dumps(
            json.load(response),
            indent=2,
            ensure_ascii=False
        ))
except urllib.error.HTTPError as error:
    print("HTTP:", error.code)
    print("Respuesta:", error.read().decode())
