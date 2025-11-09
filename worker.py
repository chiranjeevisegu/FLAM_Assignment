import threading
import time
import subprocess
import os
import signal
from job_store import JobStore
from config import load_config


class Worker(threading.Thread):
    def __init__(self, worker_id, stop_event):
        super().__init__(daemon=True)
        self.worker_id = worker_id
        self.store = JobStore()
        self.config = load_config()
        self.stop_event = stop_event

    def run(self):
        print(f"🧑‍🏭 Worker-{self.worker_id} started...")

        while not self.stop_event.is_set():
            job = self._get_pending_job()
            if not job:
                time.sleep(self.config.get("poll_interval", 1))
                continue

            job_id, command, state, attempts, max_retries, created_at, updated_at, next_run_at, priority, last_duration, last_exit_code = job

            if next_run_at and next_run_at > time.time():
                time.sleep(0.5)
                continue

            self.store.update_job_state(job_id, "processing")
            print(f"⚙️ Worker-{self.worker_id} executing: {command}")

            start_time = time.time()
            try:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                )

                try:
                    stdout, stderr = process.communicate(timeout=self.config.get("timeout", 10))
                except subprocess.TimeoutExpired:
                    # Timeout occurred — kill process
                    if os.name == "nt":
                        process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        process.terminate()
                    try:
                        process.wait(2)
                    except subprocess.TimeoutExpired:
                        process.kill()

                    stdout, stderr = process.communicate()
                    duration = time.time() - start_time
                    print(f"⏳ Job {job_id} timed out after {self.config.get('timeout', 10)}s")
                    self._save_logs(job_id, stdout, stderr)
                    self._handle_failure(job_id, attempts, max_retries, "TimeoutExpired")
                    continue

                #  PHASE-D — OUTPUT LOGGING
                self._save_logs(job_id, stdout, stderr)

                duration = time.time() - start_time
                exit_code = process.returncode

                if exit_code == 0:
                    self.store.update_job_state(job_id, "completed", last_duration=duration, last_exit_code=exit_code)
                    print(f"✅ Job {job_id} completed successfully in {duration:.2f}s")
                    self._remove_from_dlq(job_id)
                else:
                    self.store.conn.execute(
                        "UPDATE jobs SET last_duration=?, last_exit_code=? WHERE id=?",
                        (duration, exit_code, job_id)
                    )
                    self.store.conn.commit()
                    self._handle_failure(job_id, attempts, max_retries, f"ExitCode:{exit_code}")

            except Exception as e:
                duration = time.time() - start_time
                self.store.conn.execute(
                    "UPDATE jobs SET last_duration=?, last_exit_code=? WHERE id=?",
                    (duration, -1, job_id)
                )
                self.store.conn.commit()
                self._handle_failure(job_id, attempts, max_retries, str(e))

            time.sleep(0.2)

        print(f"🛑 Worker-{self.worker_id} stopping (graceful)")

    # NEW FUNCTION FOR LOGGING 
    def _save_logs(self, job_id, stdout, stderr):
        """Save stdout/stderr to a log file."""
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"{job_id}.log")
        with open(log_path, "w", encoding="utf-8") as f:
            if stdout:
                f.write(stdout)
            if stderr:
                f.write("\n[stderr]\n" + stderr)
        print(f"🗒️ Logs saved to {log_path}")

    # DEAD LETTER QUEUE HANDLER
    def _handle_failure(self, job_id, attempts, max_retries, error):
        attempts += 1
        base = self.config.get("backoff_base", 2)
        delay = base ** attempts
        if attempts > max_retries:
            from dlq import DLQ
            dlq = DLQ()
            dlq.conn.execute(
                "INSERT OR REPLACE INTO dlq (id, command, attempts, max_retries, created_at, moved_at, error) "
                "SELECT id, command, attempts, max_retries, created_at, strftime('%s','now'), ? FROM jobs WHERE id=?",
                (error, job_id)
            )
            dlq.conn.commit()
            self.store.update_job_state(job_id, "dead")
            print(f"☠️ Job {job_id} moved to DLQ after {attempts - 1} retries. error={error}")
        else:
            next_run = time.time() + delay
            self.store.conn.execute(
                "UPDATE jobs SET state=?, attempts=?, updated_at=?, next_run_at=? WHERE id=?",
                ("pending", attempts, time.time(), next_run, job_id)
            )
            self.store.conn.commit()
            print(f"🔁 Job {job_id} failed (attempt {attempts}) — retrying in {delay:.1f}s (error={error})")

    # REMOVE JOB FROM DLQ IF SUCCESS
    def _remove_from_dlq(self, job_id):
        try:
            from dlq import DLQ
            dlq = DLQ()
            dlq.conn.execute("DELETE FROM dlq WHERE id=?", (job_id,))
            dlq.conn.commit()
        except Exception:
            pass

    def _get_pending_job(self):
        cur = self.store.conn.execute(
            "SELECT id, command, state, attempts, max_retries, created_at, updated_at, next_run_at, priority, last_duration, last_exit_code "
            "FROM jobs WHERE state='pending' AND (next_run_at IS NULL OR next_run_at <= ?) "
            "ORDER BY priority DESC, created_at ASC LIMIT 1",
            (time.time(),)
        )
        return cur.fetchone()
