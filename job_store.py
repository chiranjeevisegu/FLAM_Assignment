import sqlite3, time, uuid, os

DB_PATH = "queue.db"

class JobStore:
    def __init__(self, db_path=DB_PATH):
        need_init = not os.path.exists(db_path)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute('PRAGMA journal_mode=WAL;')
        if need_init:
            self._create_tables()
        else:
            self._ensure_columns()

    def _create_tables(self):
        self.conn.execute('''CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            command TEXT NOT NULL,
            state TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            created_at REAL,
            updated_at REAL,
            next_run_at REAL DEFAULT 0,
            priority INTEGER DEFAULT 1,
            last_duration REAL DEFAULT 0,
            last_exit_code INTEGER DEFAULT NULL
        )''')
        self.conn.execute('''CREATE TABLE IF NOT EXISTS dlq (
            id TEXT PRIMARY KEY,
            command TEXT,
            attempts INTEGER,
            max_retries INTEGER,
            created_at REAL,
            moved_at REAL,
            error TEXT
        )''')
        self.conn.commit()

    def _ensure_columns(self):
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(jobs)")
        cols = [r[1] for r in cur.fetchall()]
        expected = {
            "priority": "ALTER TABLE jobs ADD COLUMN priority INTEGER DEFAULT 1",
            "next_run_at": "ALTER TABLE jobs ADD COLUMN next_run_at REAL DEFAULT 0",
            "last_duration": "ALTER TABLE jobs ADD COLUMN last_duration REAL DEFAULT 0",
            "last_exit_code": "ALTER TABLE jobs ADD COLUMN last_exit_code INTEGER DEFAULT NULL"
        }
        for col, stmt in expected.items():
            if col not in cols:
                try:
                    self.conn.execute(stmt)
                except Exception:
                    pass
        self.conn.commit()

    def enqueue(self, command, max_retries=3, priority=1, run_at=0):
        job_id = str(uuid.uuid4())
        now = time.time()
        self.conn.execute("""
            INSERT INTO jobs (id, command, state, attempts, max_retries, created_at, updated_at, next_run_at, priority)
            VALUES (?, ?, 'pending', 0, ?, ?, ?, ?, ?)""",
            (job_id, command, max_retries, now, now, run_at or 0, priority))
        self.conn.commit()
        print(f"Job enqueued successfully: {job_id}")
        return job_id

    def update_job_state(self, job_id, state, last_duration=None, last_exit_code=None):
        now = time.time()
        if last_duration is None:
            self.conn.execute("UPDATE jobs SET state=?, updated_at=? WHERE id=?", (state, now, job_id))
        else:
            self.conn.execute("UPDATE jobs SET state=?, updated_at=?, last_duration=?, last_exit_code=? WHERE id=?",
                              (state, now, last_duration, last_exit_code, job_id))
        self.conn.commit()

    def list_jobs(self, state=None):
        cur = self.conn.cursor()
        cols = "id, command, state, attempts, max_retries, created_at, updated_at, next_run_at, priority, last_duration, last_exit_code"
        if state:
            cur.execute(f"SELECT {cols} FROM jobs WHERE state=? ORDER BY created_at ASC", (state,))
        else:
            cur.execute(f"SELECT {cols} FROM jobs ORDER BY created_at ASC")
        return cur.fetchall()

    def metrics(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM jobs")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM jobs WHERE state='completed'")
        completed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM jobs WHERE state='dead'")
        dead = cur.fetchone()[0]
        cur.execute("SELECT AVG(last_duration) FROM jobs WHERE last_duration>0")
        avg_dur = cur.fetchone()[0] or 0
        success_rate = (completed / (completed + dead)) * 100 if (completed + dead) > 0 else 0
        return {
            "total": total,
            "completed": completed,
            "dead": dead,
            "avg_duration": avg_dur,
            "success_rate": success_rate
        }

