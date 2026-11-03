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

# Funkcje testujące odpowiednie protokoły

# Testowa funkcja icmp
def test_icmp(target: str):
    # polecenie jako lista parametrow
    # -c oznacza ilosc pakietow, w tym przypadku 1
    # -W oznacza timeout, w tym przypadku po 2 sekundach
    cmd = ["ping", "-c", "1", "-W", "2", target]
    start = time.time()

    exit_code = subprocess.call(cmd)
    duration = round((time.time() - start) * 1000, 2) # zmiana z milisekund na sekundy i zaokraglenie tego do 2 miejsc po przecinku

    if exit_code == 0:
        return "UP", duration
    else:
        return "DOWN", duration, "Brak odpowiedzi ping" 


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
    url = target

    start_time = time.time()

    try:
        response = requests.get(url, timeout = 2)
        duration = round((time.time() - start_time) * 1000, 2)

        if response.status_code < 500:
            return f"Status: UP \nCzas: {duration}"
        else:
            return f"Status: DOWN \nCzas: {duration} \nHTTP error: {response.status_code}"
    except Exception:
        duration = round((time.time() - start_time) * 1000, 2)
        return f"Status: DOWN \nCzas: {duration} \nHTTP error: request failed"





# Klasa walidacji danych. Ograniczam tylko do protokołów ICMP, TCP, HTTP
# port jest opcjonalny, ponieważ do ICMP nie potrzebujemy portu
class HostCreate(BaseModel):
    name: str
    target: str
    check_type: Literal['ICMP', 'TCP', 'HTTP']
    port: Optional[int] = None
    interval_seconds: Optional[int] = 60


# Funkcja testująca połączenie z bazą danych i zwracająca wynik ping-u protokołu ICMP
@app.get("/health")
def health_check():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 AS ping;")
    result = cursor.fetchone()
    conn.close()
    return {"status": "ok", "db_connection": True, "ping": result["ping"]}


# 4. Dodawanie nowego hosta
# Funkcja dodająca hosta 
@app.post("/hosts", status_code=201)
def create_host(host: HostCreate):
    conn = get_db()
    cursor = conn.cursor()

    
    cursor.execute("""
        INSERT IGNORE INTO users (id, username, email, password)
        VALUES (1, 'admin', 'admin@example.com', 'admin123');
    """)

    # Wstawanie hosta 
    sql = """
        INSERT INTO monitored_hosts (user_id, name, target, check_type, port, interval_seconds)
        VALUES (%s, %s, %s, %s, %s, %s);
    """
    values = (1, host.name, host.target, host.check_type, host.port, host.interval_seconds)
    cursor.execute(sql, values)
    new_id = cursor.lastrowid
    conn.close()

    return {"id": new_id, "message": "Host dodany", **host.model_dump()} # host.model_dump() rozpakowywuje dane i odsyła je w odpowiedzi wraz z id



# Funkcja pobierająca listę hostów
@app.get("/hosts")
def list_hosts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM monitored_hosts WHERE is_active = 1;")
    hosts = cursor.fetchall()
    conn.close()
    return hosts





















