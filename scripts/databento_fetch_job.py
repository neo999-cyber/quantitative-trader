"""Wait for a Databento batch job and download its files into the lake mirror.

    .venv/bin/python scripts/databento_fetch_job.py <job_id> <target_dir>
"""
import json, sys, time
from pathlib import Path

import databento as db

from qr import secrets

job_id, target = sys.argv[1], Path(sys.argv[2]).expanduser()
client = db.Historical(secrets.require("DATABENTO_KEY"))
while True:
    jobs = {j["id"]: j for j in client.batch.list_jobs(states=["queued", "processing", "done", "expired"])}
    job = jobs.get(job_id)
    state = job["state"] if job else "unknown"
    print(time.strftime("%H:%M:%S"), state, flush=True)
    if state == "done":
        break
    if state in ("expired", "unknown"):
        sys.exit(f"job {job_id} {state}")
    time.sleep(60)
target.mkdir(parents=True, exist_ok=True)
files = client.batch.download(job_id=job_id, output_dir=target)
meta = {k: job.get(k) for k in ("id", "dataset", "schema", "symbols", "start", "end", "cost_usd", "billed_size", "record_count", "ts_received", "ts_process_done")}
meta["first_observed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
meta["files"] = [str(f) for f in files]
(target / "job.json").write_text(json.dumps(meta, indent=1, default=str))
print("downloaded", len(files), "files; cost_usd", job.get("cost_usd"), flush=True)
