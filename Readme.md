````
````
# ⚡ QueueCTL / FLAM — Fault-tolerant Lightweight Asynchronous Manager

*A Complete Python Job Queue System with Retries, Scheduling, DLQ, and Dashboard*

---

## Objective

Build a CLI-based background job management system that supports **job queuing, retries, exponential backoff, DLQ (Dead Letter Queue), scheduling, and a monitoring dashboard**.

This project fully implements the assignment requirements and all **bonus features** for extra credit.

---

## Included Deliverables

| File | Description |
|------|--------------|
| `flam.py` | CLI for enqueueing, running, listing, and managing jobs |
| `job_store.py` | SQLite-based persistent job store |
| `worker.py` | Worker threads to process jobs, handle retries and timeouts |
| `dlq.py` | Manage and retry failed jobs from the Dead Letter Queue |
| `config.py` | Load and update runtime settings |
| `dashboard.py` | Flask-based dashboard showing metrics and DLQ |
| `requirements.txt` | Python dependencies |
| `logs/` | Folder containing job logs |
| `queue.db` | SQLite database (auto-created) |

---

## Job Specification

Each job is stored in SQLite as a row with the following structure:

```json
{
  "id": "unique-job-id",
  "command": "echo Hello World",
  "state": "pending",
  "attempts": 0,
  "max_retries": 3,
  "created_at": 1700000000,
  "updated_at": 1700000000,
  "next_run_at": 0,
  "priority": 1,
  "last_duration": 0.0,
  "last_exit_code": null
}
````

---

## Job Lifecycle

| State        | Description                    |
| ------------ | ------------------------------ |
| `pending`    | Waiting to be processed        |
| `processing` | Currently being executed       |
| `completed`  | Finished successfully          |
| `failed`     | Retried with delay             |
| `dead`       | Moved to DLQ after all retries |

---

## CLI Commands

### Enqueue a Job

```bash
python flam.py enqueue "echo Hello FLAM"
```

Options:

* `--max-retries <int>`
* `--priority <1–5>`
* `--run-at <ISO-8601 timestamp>`

### Start Workers

```bash
python flam.py worker --count 3
```

Starts 3 parallel workers to process pending jobs.

### List Jobs

```bash
python flam.py list --state completed
```

Shows all completed jobs.

###  DLQ Management

```bash
python flam.py dlq list
python flam.py dlq retry <job_id>
python flam.py dlq retry-all
```

### Configuration

```bash
python flam.py config show
python flam.py config set timeout 15
```

###  Metrics Summary

```bash
python flam.py status
```

###  Dashboard

```bash
python dashboard.py
```

Visit: **[http://localhost:5000](http://localhost:5000)**
**Output**
![WhatsApp Image 2025-11-09 at 17 46 25_38e7252a](https://github.com/user-attachments/assets/f3e41679-13c5-4d76-ad24-cfc7848e38b9)
![WhatsApp Image 2025-11-09 at 17 46 50_d467e079](https://github.com/user-attachments/assets/12b4f792-5c8e-4e11-a75f-ffdd7a185a69)
![WhatsApp Image 2025-11-09 at 17 47 07_3987bf88](https://github.com/user-attachments/assets/fc83fc3f-b025-4a16-8e83-66d11c48005d)

---

##  Setup & Installation

### Step 1: Create Virtual Environment

```bash
python -m venv venv
```

### Step 2: Activate Environment

**Windows:**

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

**Linux/macOS:**

```bash
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Verify Config

```bash
python flam.py config show
```

Expected:

```
{'max_retries': 3, 'backoff_base': 2, 'poll_interval': 1, 'timeout': 10}
```

---

##  Architecture

```
CLI (flam.py)
    ↓
JobStore (SQLite)
    ↓
Worker Threads (Processing + Retry)
    ↓
DLQ + Logs
    ↓
Dashboard (Flask)
```

---

##  Core Functionality Tests

###  Test 1: Basic Job Execution

```bash
python flam.py enqueue "echo Hello FLAM"
python flam.py worker --count 1
```

**Expected Output:**

```
🧑‍🏭 Worker-1 started...
⚙️ Worker-1 executing: echo Hello FLAM
✅ Job <id> completed successfully
```

---

###  Test 2: Multi-Worker Processing

```bash
python flam.py enqueue "echo A"
python flam.py enqueue "echo B"
python flam.py worker --count 2
```

**Expected:** Parallel execution — no duplicates.

---

###  Test 3: Timeout Handling

```bash
python flam.py enqueue 'python -c "import time; time.sleep(30)"'
python flam.py worker --count 1
```

**Expected Output:**

```
⏳ Job <id> timed out after 10s
🔁 Retrying...
☠️ Job moved to DLQ after 3 retries. error=TimeoutExpired
```

---

###  Test 4: DLQ Retry

```bash
python flam.py dlq list
python flam.py dlq retry <job_id>
```

**Expected Output:**

```
♻️ Retried DLQ job <id> — moved back to queue.
```

---

###  Test 5: Job Priority Queue

```bash
python flam.py enqueue "echo LOW PRIORITY" --priority 1
python flam.py enqueue "echo HIGH PRIORITY" --priority 5
python flam.py worker --count 1
```

**Expected:**

```
⚙️ Worker-1 executing: echo HIGH PRIORITY
✅ Job completed successfully
⚙️ Worker-1 executing: echo LOW PRIORITY
✅ Job completed successfully
```

---

###  Test 6: Scheduled Job

```bash
python flam.py enqueue "echo Scheduled Job" --run-at "2025-11-09T19:30:00Z"
python flam.py worker --count 1
```

**Expected:**

```
🧑‍🏭 Worker waiting for schedule...
⚙️ Worker executing: echo Scheduled Job
✅ Completed successfully
```

---

##  Bonus Features Implemented

| Bonus Feature      | Description                                                      |
| ------------------ | ---------------------------------------------------------------- |
| ⏳ Timeout Handling | Force-terminate long-running jobs                                |
| 🧮 Job Priority    | Execute high-priority jobs first                                 |
| ⏰ Scheduled Jobs   | Execute jobs only after given timestamp                          |
| 🗒️ Logging        | Per-job log files stored under `/logs`                           |
| 🌐 Dashboard       | Flask web interface with metrics and retry                       |
| 📊 Metrics         | CLI + dashboard summary (total, completed, failed, success rate) |

---

## Metrics & Dashboard

Start dashboard:

```bash
python dashboard.py
```

Visit: **[http://localhost:5000](http://localhost:5000)**

**Dashboard Includes:**

* Metric cards (total, completed, failed, avg duration, success rate)
* Pie & bar charts
* Recent jobs table
* DLQ table with retry buttons
* Auto-refresh every 10 seconds

---

##  Test Case Summary

| # | Test         | Command              | Expected                 |
| - | ------------ | -------------------- | ------------------------ |
| 1 | Basic Job    | `enqueue` + `worker` | Job completes            |
| 2 | Multi-Worker | `--count 2`          | Parallel execution       |
| 3 | Timeout      | `sleep 30`           | DLQ after 3 retries      |
| 4 | DLQ Retry    | `dlq retry`          | Moves back to queue      |
| 5 | Priority     | `--priority`         | High runs first          |
| 6 | Scheduling   | `--run-at`           | Executes at correct time |
| 7 | Metrics      | `status`             | Displays stats           |
| 8 | Dashboard    | `dashboard.py`       | Shows live UI            |

---

## Expected CLI Outputs

**Example Output:**

```
⚙️ Worker-1 executing: ping 127.0.0.1 -n 20
⏳ Job <id> timed out after 10s
☠️ Job moved to DLQ after 3 retries
```

**DLQ Example:**

```
ID           COMMAND                    ERROR
9a32...      ping 127.0.0.1 -n 20       TimeoutExpired
```

---

##  Future Enhancements

* Real-time WebSocket updates
* Authentication for dashboard
* Distributed backend using Redis/RabbitMQ
* Job tagging and grouping
* Email/Slack alerts for DLQ jobs

---

##  Assumptions

* All commands are trusted; no sandboxing.
* SQLite chosen for simplicity; suitable for single-node demos.
* Timeout behavior uses platform-specific process termination.
* Dashboard is minimal for hackathon demonstration.

---

## Submission Instructions

1. Include this README in your GitHub repository.
2. Include all Python scripts (`flam.py`, `worker.py`, etc.).
3. Add screenshots or a short 6–8 min video showing CLI + Dashboard demo.
4. Include your environment setup steps and expected outputs.

---

## 🏁 Conclusion

**FLAM** (Fault-tolerant Lightweight Asynchronous Manager) demonstrates:
✅ Robust asynchronous job handling
✅ Fault-tolerant retry logic
✅ Persistent queue management
✅ Scheduling, priority, and timeout
✅ Real-time web-based monitoring

It’s an end-to-end professional-grade job queue system — entirely written in Python.

---
## Demo Video Link:
https://drive.google.com/uc?id=1VdXDMg6RsCpPL5bwECzhmgq75yR9SksT&export=download

---

## 👨‍💻 Developer Info

**Name:** Chiranjeevi Segu
**Project:** FLAM — Fault-tolerant Lightweight Asynchronous Manager
**Tech Stack:** Python, SQLite, Flask, Click
**Duration:** 3 Days
**Role:** Developer, Tester, Designer

```
```
