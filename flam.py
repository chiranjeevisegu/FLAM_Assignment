import click, time, uuid
from tabulate import tabulate
from job_store import JobStore
from dlq import DLQ
from config import load_config, save_config
from worker import Worker
from datetime import datetime
import threading

store = JobStore()

@click.group()
def cli():
    """FLAM (QueueCTL) - CLI Job Queue"""
    pass

@cli.command()
@click.argument("command")
@click.option("--max-retries", default=None, type=int, help="Max number of retries")
@click.option("--priority", default=1, type=int, help="Job priority (1-5, higher = sooner)")
@click.option("--run-at", default=None, help="Schedule time in UTC, format: YYYY-MM-DDTHH:MM:SSZ")
def enqueue(command, max_retries, priority, run_at):
    """
    Enqueue a new job with optional priority and scheduled time.

    Examples:
      python flam.py enqueue "echo hello"
      python flam.py enqueue "echo urgent job" --priority 5
      python flam.py enqueue "echo delayed job" --run-at 2025-11-09T10:00:00Z
    """
    run_at_ts = 0
    if run_at:
        from datetime import datetime
        try:
            run_at_ts = datetime.strptime(run_at, "%Y-%m-%dT%H:%M:%SZ").timestamp()
        except ValueError:
            click.echo("❌ Invalid --run-at format. Use YYYY-MM-DDTHH:MM:SSZ (UTC).")
            return

    cfg = load_config()
    mr = max_retries if max_retries is not None else cfg.get("max_retries", 3)
    store.enqueue(command, max_retries=mr, priority=priority, run_at=run_at_ts)

@cli.command(name="list")
@click.option("--state", default=None)
def _list(state):
    """List jobs (optionally by state)"""
    rows = store.list_jobs(state)
    if not rows:
        click.echo("No jobs found.")
        return

    def format_ts(ts):
        try:
            if not ts or ts == 0:
                return ""
            return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except:
            return ts

    formatted_rows = []
    for r in rows:
        id_, cmd, state, attempts, max_retries, created_at, updated_at, next_run_at, priority, last_dur, last_exit = r
        formatted_rows.append((
            id_,
            cmd,
            state,
            attempts,
            max_retries,
            format_ts(created_at),
            format_ts(updated_at),
            format_ts(next_run_at),
            priority,
            last_dur,
            last_exit
        ))

    headers = [
        "ID", "COMMAND", "STATE", "ATTEMPTS", "MAX_RETRIES",
        "CREATED_AT (UTC)", "UPDATED_AT (UTC)", "NEXT_RUN_AT (UTC)",
        "PRIORITY", "LAST_DUR", "LAST_EXIT"
    ]
    click.echo(tabulate(formatted_rows, headers=headers, tablefmt="github"))


@cli.command()
def status():
    """Show queue metrics and performance summary"""
    m = store.metrics()
    from tabulate import tabulate
    table = [
        ["total_jobs", m["total"]],
        ["completed", m["completed"]],
        ["dead", m["dead"]],
        ["avg_duration_s", round(m["avg_duration"], 3)],
        ["success_rate_%", round(m["success_rate"], 2)]
    ]
    print(tabulate(table, headers=["metric", "value"], tablefmt="github"))

@cli.command()
@click.option("--count", default=1, help="Number of worker threads")
def worker(count):
    """Start worker(s). Ctrl+C to stop gracefully."""
    stop_event = threading.Event()
    workers = [Worker(i+1, stop_event) for i in range(count)]
    for w in workers:
        w.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        click.echo("\n🛑 Shutting down workers...")
        stop_event.set()
        for w in workers:
            w.join()
        click.echo("🛑 All workers stopped.")

# DLQ group
@cli.group()
def dlq():
    """DLQ commands"""
    pass

@dlq.command("list")
def dlq_list():
    jobs = DLQ().list_dlq()
    if not jobs:
        click.echo("☠️ DLQ is empty.")
        return
    headers = ["ID","COMMAND","ATTEMPTS","MAX_RETRIES","CREATED_AT","MOVED_AT","ERROR"]
    click.echo(tabulate(jobs, headers=headers))

@dlq.command("retry")
@click.argument("job_id")
def dlq_retry(job_id):
    DLQ().retry_job(job_id)

@dlq.command("retry-all")
def dlq_retry_all():
    dlq = DLQ()
    jobs = dlq.list_dlq()
    if not jobs:
        click.echo("☠️ DLQ is empty.")
        return
    for j in jobs:
        dlq.retry_job(j[0])
    click.echo(f"♻️ Retried {len(jobs)} DLQ jobs — moved back to queue.")

@cli.group()
def config():
    """Config commands"""
    pass

@config.command("show")
def config_show():
    click.echo(load_config())

@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    cfg = load_config()
    if key not in cfg:
        click.echo(f"⚠️ Invalid config key: {key}")
        return
    try:
        cfg[key] = int(value)
    except:
        cfg[key] = value
    save_config(cfg)
    click.echo(f"✅ Updated {key} to {value}")

if __name__ == "__main__":
    cli()
