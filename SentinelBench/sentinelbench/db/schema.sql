CREATE TABLE IF NOT EXISTS completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    start_time DATETIME NOT NULL,
    completion_time DATETIME NOT NULL,
    user_agent TEXT,
    ip_address TEXT,
    user_id TEXT,
    host TEXT,
    url TEXT
);

CREATE INDEX IF NOT EXISTS idx_task_id ON completions(task_id);

CREATE TABLE IF NOT EXISTS views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    view_time DATETIME NOT NULL,
    user_agent TEXT,
    ip_address TEXT,
    user_id TEXT,
    host TEXT,
    url TEXT
);

CREATE INDEX IF NOT EXISTS idx_views_task_id ON views(task_id);
