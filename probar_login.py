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

data = json.load(sys.stdin)
client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"]
)

try:
    response = client.auth.sign_in_with_password({
        "email": data["email"],
        "password": data["password"]
    })
    if not response.session:
        print(json.dumps({"error": "No se obtuvo sesión"}))
    else:
        print(json.dumps({"token": response.session.access_token}))
except Exception as e:
    print(json.dumps({"error": str(e)[:200]}))
"""

result = subprocess.run(
    ["docker", "compose", "exec", "-T", "api", "python", "-c", script],
    input=json.dumps({"email": email, "password": password}),
    text=True,
    capture_output=True
)

del password

if result.returncode != 0:
    print("Error al ejecutar Docker:", result.stderr[:300])
    raise SystemExit(1)

try:
    data = json.loads(result.stdout)
except json.JSONDecodeError:
    print("Respuesta inesperada del contenedor.")
    raise SystemExit(1)

if "error" in data:
    print("Error de login:", data["error"])
    raise SystemExit(1)

print("LOGIN EXITOSO")

request = urllib.request.Request(
    "http://localhost:8000/auth/me",
    headers={"Authorization": "Bearer " + data["token"]}
)

try:
    with urllib.request.urlopen(request, timeout=15) as response:
        print("HTTP:", response.status)
        print("Usuario:", response.read().decode())
except urllib.error.HTTPError as error:
    print("HTTP:", error.code)
    print("Respuesta:", error.read().decode())
