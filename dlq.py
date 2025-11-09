import sqlite3, time
DB_PATH = "queue.db"

class DLQ:
    def __init__(self, db_path=DB_PATH):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)

    def list_dlq(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, command, attempts, max_retries, created_at, moved_at, error FROM dlq")
        return cur.fetchall()

    def retry_job(self, job_id):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM dlq WHERE id=?", (job_id,))
        job = cur.fetchone()
        if not job:
            print(f" No job found in DLQ with ID {job_id}")
            return

        id_, command, attempts, max_retries, created_at, moved_at, error = job

        cur.execute("SELECT id FROM jobs WHERE id=?", (id_,))
        exists = cur.fetchone()

        if exists:
            cur.execute("""
                UPDATE jobs
                SET state='pending', attempts=0, updated_at=?, next_run_at=?
                WHERE id=?
            """, (time.time(), 0, id_))
        else:
            cur.execute("""
                INSERT INTO jobs (id, command, state, attempts, max_retries, created_at, updated_at, next_run_at, priority)
                VALUES (?, ?, 'pending', 0, ?, ?, ?, 0, 1)
            """, (id_, command, max_retries, created_at, time.time()))
        cur.execute("DELETE FROM dlq WHERE id=?", (id_,))
        self.conn.commit()

        print(f"♻️ Retried DLQ job {id_} — moved back to queue.")
