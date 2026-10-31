from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Literal
import pymysql

app = FastAPI(title="NetworkTester")

# Funkcja zwracająca połączenie do bazy danych
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

    # Zapewniam, że użytkownik testowy id=1 istnieje w bazie jako test
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