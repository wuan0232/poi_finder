PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    center_name VARCHAR(255),
    center_address VARCHAR(500),
    keyword VARCHAR(100),
    types_code VARCHAR(20),
    radius_m INTEGER,
    center_lng REAL,
    center_lat REAL,
    city VARCHAR(100) NOT NULL,
    keywords_json TEXT NOT NULL,
    providers_json TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    total INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pois (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    provider VARCHAR(20) NOT NULL,
    source_id VARCHAR(200),
    keyword VARCHAR(100) NOT NULL,
    name VARCHAR(300) NOT NULL,
    category VARCHAR(300),
    address VARCHAR(500),
    province VARCHAR(100),
    city VARCHAR(100),
    district VARCHAR(100),
    phone VARCHAR(100),
    longitude REAL,
    latitude REAL,
    distance_m INTEGER,
    extra_json TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS ix_pois_task_id ON pois(task_id);
CREATE INDEX IF NOT EXISTS ix_pois_task_provider ON pois(task_id, provider);
CREATE INDEX IF NOT EXISTS ix_pois_task_name ON pois(task_id, name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pois_task_provider_source
    ON pois(task_id, provider, source_id)
    WHERE source_id IS NOT NULL;
