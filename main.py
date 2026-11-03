from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Literal
import pymysql
import time
import socket
import subprocess
import requests
import platform

app = FastAPI(title="NetworkTester")

# Zezwolenie na połączenia z przeglądarki (CORS - Cross-Origin Resource Sharing) - musi być dodane, aby przeglądarka nie blokowała zapytań z frontendu
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Funkcja zwracająca połączenie do bazy danych
def get_db():
    return pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="app_user",
        password="SECRET_PASSWORD",
        database="app_db",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True # dodaje autocommit, aby baza nie czekała na potwierdzenie operacji np. insert
    )


# Klasa walidacji danych. Ograniczam tylko do protokołów ICMP, TCP, HTTP
# port jest opcjonalny, ponieważ do ICMP nie potrzebujemy portu
class HostCreate(BaseModel):
    name: str
    target: str
    check_type: Literal['ICMP', 'TCP', 'HTTP']
    port: Optional[int] = None
    interval_seconds: Optional[int] = 60

# Funkcje testujące odpowiednie protokoły

# Testowa funkcja icmp
import platform

def test_icmp(target: str):
    # Wykrywamy system operacyjny
    if platform.system().lower() == "windows":
        # Windows: -n 1 (jeden pakiet), -w 2000 (timeout 2000 ms)
        cmd = ["ping", "-n", "1", "-w", "2000", target]
    else:
        # Linux: -c 1 (jeden pakiet), -W 2 (timeout 2 sekundy)
        cmd = ["ping", "-c", "1", "-W", "2", target]

    start_time = time.time()
    exit_code = subprocess.call(cmd)
    duration = round((time.time() - start_time) * 1000, 2)

    if exit_code == 0:
        return "UP", duration, None
    return "DOWN", duration, "Brak odpowiedzi ICMP" 


# TEstowa funkcja TCP
def test_tcp(target: str, port: int):

    start_time = time.time()
    # Aby wymusić zrobienie testu na protokole IPv4 zamiast IPv6 trzeba dodać gniazdo sieciowe

    try:
        connection = socket.create_connection((target, port), timeout = 2)
        connection.close()
        duration = round((time.time() - start_time) * 1000, 2)
        return "UP", duration
    except Exception:
        duration = round((time.time() - start_time) * 1000, 2)
        return "DOWN", duration, f"Port {port} nieosiagalny"

# Testowa funkcja HTTP
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
        return "DOWN", duration, f"HTTP error {response.status_code}"
    except Exception as e:
        duration = round((time.time() - start_time) * 1000, 2)
        return "DOWN", duration, "HTTP request failed"








# Funkcja testująca połączenie z bazą danych i zwracająca wynik ping-u protokołu ICMP
# Pobranie listy wszystkich monitorowanych hostów
@app.get("/hosts")
def get_hosts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM monitored_hosts WHERE is_active = 1;")
    hosts = cursor.fetchall()
    conn.close()
    return hosts


# Dodanie nowego hosta do monitorowania
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
        (
            1,
            host.name,
            host.target,
            host.check_type,
            host.port,
            host.interval_seconds,
        ),
    )
    new_id = cursor.lastrowid
    conn.close()

    return {"message": "Host dodany", "id": new_id}


# Ręczne wywołanie testu dla danego hosta i zapis do bazy
@app.post("/hosts/{host_id}/check")
def check_host(host_id: int):
    conn = get_db()
    cursor = conn.cursor()

    # 1. Pobieramy dane hosta z bazy
    cursor.execute("SELECT * FROM monitored_hosts WHERE id = %s;", (host_id,))
    host = cursor.fetchone()

    if not host:
        conn.close()
        raise HTTPException(
            status_code=404, detail=f"Host o ID {host_id} nie istnieje w bazie"
        )

    target = host["target"]
    check_type = host["check_type"]
    port = host["port"]

    # 2. Wybieramy odpowiedni test
    if check_type == "ICMP":
        status, duration, error = test_icmp(target)
    elif check_type == "TCP":
        # Jeśli port w bazie to None, próbujemy go wyciągnąć z adresu (np. 8.8.8.8:443)
        if not port:
            if ":" in target:
                parts = target.split(":")
                target = parts[0]
                port = int(parts[1])
            else:
                port = 80  # Domyślny port zapasowy, jeśli użytkownik żadnego nie podał

        status, duration, error = test_tcp(target, port)
    elif check_type == "HTTP":
        status, duration, error = test_http(target)
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Nieznany typ testu")

    # 3. Zapisujemy wynik do tabeli check_logs
    # 3. Zapisujemy wynik do tabeli check_logs (tylko to, co niezbędne do statystyk)
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


# Usuwanie hosta (Soft delete - ukrycie rekordu)
@app.delete("/hosts/{host_id}")
def delete_host(host_id: int):
    conn = get_db()
    cursor = conn.cursor()

    # Sprawdzamy czy host istnieje
    cursor.execute("SELECT id FROM monitored_hosts WHERE id = %s;", (host_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Host nie istnieje")

    # Zamiast DELETE FROM używamy UPDATE, aby zachować logi w bazie (soft delete)
    cursor.execute("UPDATE monitored_hosts SET is_active = 0 WHERE id = %s;", (host_id,))
    conn.close()

    return {"message": "Host usunięty"}

















