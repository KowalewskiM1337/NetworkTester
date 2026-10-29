USE app_db;

-- Tabela uzytkownikow panelu
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(50) NOT NULL,
    role VARCHAR(20) DEFAULT 'user'
)


-- Hosty dodane do monitorowania
CREATE TABLE IF NOT EXISTS monitored_hosts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    target VARCHAR(255) NOT NULL,
    check_type ENUM('ICMP', 'TCP', 'HTTP') NOT NULL,
    port INT NULL,
    interval_seconds INT DEFAULT 60,
    is_active TINYINT(1) DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE -- baza usunie automatycznie rekordy i logi, gdy uzytkownik usunie hosta z panelu
)

-- Logi pomiarow tj. czas odpowiedzi 
CREATE TABLE IF NOT EXISTS check_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    host_id INT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('UP', 'DOWN') NOT NULL,
    response_time_ms FLOAT NULL,
    http_status_code INT NULL,
    FOREIGN KEY (host_id) REFERENCES monitored_hosts(id) ON DELETE CASCADE,
    INDEX idx_host_time (host_id, timestamp)
)

-- Tabela awarii (do obliczania SLA)
CREATE TABLE IF NOT EXISTS incidents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    host_id INT NOT NULL,
    started_at DATETIME NOT NULL,
    resolved_at DATETIME NULL,
    duration_seconds INT NULL,
    FOREIGN KEY (host_id) REFERENCES monitored_hosts(id) ON DELETE CASCADE
)