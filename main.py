from fastapi import FastAPI # klasa serwera aplikacji do zarzadzania routingiem czyli adresami url
import aiomysql # biblioteka do komunikacji z mysql
from contextlib import asynccontextmanager 
from pydantic import BaseModel
from typing import Optional, Literal


# Slownik ze wszystkimi parametrami do logowania z bazy
DB_CONF = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "app_user",
    "password": "SECRET_PASSWORD",
    "db": "app_db",
    "autocommit": True
}

db_pool = None

class HostCreate(BaseModel):
    name: str
    target: str
    check_type: Literal['ICMP', 'TCP', 'HTTP']
    port: Optional[int] = None
    interval_seconds: Optional[int] = 60

# Funkcja zarzadzajaca cyklem zycia

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool

    # Dzieki tej bibliotece mozemy uruchomic pule połaczeń przed startem serwera a to kod wykonywany przed jego startem
    db_pool = await aiomysql.create_pool(**DB_CONF) # inicjalizacja puli połączeń 
    print("Polaczono z baza danych")


    # Wstawienie domyslnego uzytkownika testowego z id o numerze 1, bo baza danych odrzuci operacje dodawania hosta z bledem klucza
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT IGNORE INTO users (id, username, email, password)
                VALUES (1, 'admin', 'admin@example.com', 'admin123');
            """)


    yield # Funkcja obsluguje zapytania i serwer działa. Wszystko przed yield funkcja wykonuje na starcie, a po podczas zamykania serwera

    # Po zatrzymaniu serwera pula jest zamykana
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        print("Pula polaczen zamknieta")


app = FastAPI(title="NetworkTester", lifespan=lifespan)

@app.get("/health")
async def health_check():
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1;")
            result = await cur.fetchone()
            return {"status": "ok", "db_connection": True, "ping": result[0]}


@app.post("/hosts", status_code=201)
async def create_host(host: HostCreate):
    query = """
        INSERT INTO monitored_hosts (user_id, name, target, check_type, port, interval_seconds)
        VALUES (%s, %s, %s, %s, %s, %s);
    """
    params = (1, host.name, host.target, host.check_type, host.port, host.interval_seconds)

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            new_id = cur.lastrowid
            return {"id": new_id, "message": "Host dodany do monitorowania", **host.model_dump()}


@app.get("/hosts")
async def list_hosts():
    query = """
        SELECT id, name, target, check_type, port, interval_seconds, is_active, created_at
        FROM monitored_hosts
        WHERE is_active = 1;
    """
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query)
            hosts = await cur.fetchall()
            return hosts



