from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Literal
import pymysql
import time
import socket
import subprocess
import requests
import platform
import hashlib

app = FastAPI(title="NetworkTester")

# Zezwolenie na połączenia z przeglądarki (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Połączenie z bazą danych MySQL
def get_db():
    return pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="app_user",
        password="SECRET_PASSWORD",
        database="app_db",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )

# Modele danych
class HostCreate(BaseModel):
    name: str
    target: str
    check_type: Literal['ICMP', 'TCP', 'HTTP']
    port: Optional[int] = None
    interval_seconds: Optional[int] = 60

class UserAuth(BaseModel):
    username: str
    password: str

# Prosta funkcja haszująca hasło (SHA-256)
def hashuj_haslo(haslo: str) -> str:
    return hashlib.sha256(haslo.encode()).hexdigest()

# 1. Test ICMP (Ping)
def test_icmp(target: str):
    if platform.system().lower() == "windows":
        cmd = ["ping", "-n", "1", "-w", "2000", target]
    else:
        cmd = ["ping", "-c", "1", "-W", "2", target]

    start_time = time.time()
    exit_code = subprocess.call(cmd)
    duration = round((time.time() - start_time) * 1000, 2)

    if exit_code == 0:
        return "UP", duration, None
    return "DOWN", duration, "Brak odpowiedzi ICMP"

# 2. Test TCP (Port) - zawsze zwraca 3 wartości: status, duration, error
def test_tcp(target: str, port: int):
    start_time = time.time()
    try:
        connection = socket.create_connection((target, port), timeout=2)
        connection.close()
        duration = round((time.time() - start_time) * 1000, 2)
        return "UP", duration, None
    except Exception:
        duration = round((time.time() - start_time) * 1000, 2)
        return "DOWN", duration, f"Port {port} nieosiagalny"

# 3. Test HTTP - zawsze zwraca 3 wartości: status, duration, error
def test_http(target: str):
    if not target.startswith("http://") and not target.startswith("https://"):
        url = "http://" + target
    else:
        url = target

    start_time = time.time()
    try:
        response = requests.get(url, timeout=2)
        duration = round((time.time() - start_time) * 1000, 2)

        if response.status_code < 500:
            return "UP", duration, None
        return "DOWN", duration, f"HTTP błąd {response.status_code}"
    except Exception:
        duration = round((time.time() - start_time) * 1000, 2)
        return "DOWN", duration, "Nie udalo sie polaczyc z adresem HTTP"


# --- ENDPOINTY AUTORYZACJI ---

@app.post("/register")
def register(user: UserAuth):
    conn = get_db()
    cursor = conn.cursor()

    # Sprawdzenie czy login już jest zajęty
    cursor.execute("SELECT id FROM users WHERE username = %s;", (user.username,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Taki użytkownik już istnieje")

    zahashowane = hashuj_haslo(user.password)
    # Zapis do kolumny 'password' zgodnie z Twoją strukturą tabeli
    cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s);", (user.username, zahashowane))
    conn.close()

    return {"message": "Rejestracja udana"}

@app.post("/login")
def login(user: UserAuth):
    conn = get_db()
    cursor = conn.cursor()

    zahashowane = hashuj_haslo(user.password)
    # Weryfikacja w kolumnie 'password'
    cursor.execute("SELECT id, username FROM users WHERE username = %s AND password = %s;", (user.username, zahashowane))
    uzytkownik = cursor.fetchone()
    conn.close()

    if not uzytkownik:
        raise HTTPException(status_code=401, detail="Błędny login lub hasło")

    return {"message": "Zalogowano", "username": uzytkownik["username"]}


# --- ENDPOINTY MONITORINGU ---

@app.get("/hosts")
def get_hosts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM monitored_hosts WHERE is_active = 1;")
    hosts = cursor.fetchall()
    conn.close()
    return hosts

@app.post("/hosts")
def create_host(host: HostCreate):
    conn = get_db()
    cursor = conn.cursor()

    sql = """
        INSERT INTO monitored_hosts (user_id, name, target, check_type, port, interval_seconds, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, 1);
    """
    cursor.execute(
        sql,
        (1, host.name, host.target, host.check_type, host.port, host.interval_seconds)
    )
    new_id = cursor.lastrowid
    conn.close()

    return {"message": "Host dodany", "id": new_id}

@app.post("/hosts/{host_id}/check")
def check_host(host_id: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM monitored_hosts WHERE id = %s;", (host_id,))
    host = cursor.fetchone()

    if not host:
        conn.close()
        raise HTTPException(status_code=404, detail="Host nie istnieje")

    target = host["target"]
    check_type = host["check_type"]
    port = host["port"]

    # Wybór testu
    if check_type == "ICMP":
        status, duration, error = test_icmp(target)
    elif check_type == "TCP":
        if not port:
            if ":" in target:
                parts = target.split(":")
                target = parts[0]
                port = int(parts[1])
            else:
                port = 80
        status, duration, error = test_tcp(target, port)
    elif check_type == "HTTP":
        status, duration, error = test_http(target)
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Nieznany typ testu")

    # Zapis wyniku pomiaru do tabeli check_logs
    sql = """
        INSERT INTO check_logs (host_id, status, response_time_ms)
        VALUES (%s, %s, %s);
    """
    cursor.execute(sql, (host_id, status, duration))
    conn.close()

    return {
        "host_id": host_id,
        "name": host["name"],
        "target": target,
        "status": status,
        "response_time_ms": duration,
        "error_message": error,
    }

@app.delete("/hosts/{host_id}")
def delete_host(host_id: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM monitored_hosts WHERE id = %s;", (host_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Host nie istnieje")

    cursor.execute("UPDATE monitored_hosts SET is_active = 0 WHERE id = %s;", (host_id,))
    conn.close()

    return {"message": "Host usunięty"}