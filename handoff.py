#!/usr/bin/env python3
"""Ray's every-6h lead handoff.

Scrapes Indeed + ZipRecruiter (boards bonbon's network can't reach) into the
local Jobberworkee API, exports the fresh leads as JSON, and pushes to the
shared handoff repo. bonbon's sweep pulls the repo and imports by job ID
(INSERT OR REPLACE dedupes overlap between runs).

Stdlib only. Runs from cron:
    17 */6 * * * /home/rswan/miniconda3/bin/python3 /home/rswan/lead-handoff/handoff.py >> /home/rswan/lead-handoff/cron.log 2>&1
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

API = "http://127.0.0.1:8093"
REPO = "/home/rswan/lead-handoff"
PYTHON = "/home/rswan/miniconda3/bin/python3"
JW_DIR = "/home/rswan/jobberworkee"

QUERIES = [
    "Salesforce Architect",
    "Salesforce Technical Architect",
    "Agentforce",
    "Salesforce AI",
    "AI Solutions Architect",
    "AI Product Manager",
    "Technical Product Manager",
    "Salesforce Product Manager",
]
LOCATIONS = ["Houston, TX", "Remote"]
SITES = ["indeed", "zip_recruiter"]  # boards bonbon can't reach


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def api(method: str, path: str, body=None, timeout: int = 180):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def ensure_api() -> bool:
    for _ in range(3):
        try:
            if api("GET", "/health", timeout=10).get("ok"):
                return True
        except Exception:
            time.sleep(5)
    log("API down, trying to start it...")
    subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "backend.app.main:app",
         "--port", "8093", "--host", "127.0.0.1"],
        cwd=JW_DIR,
        stdout=open("/tmp/jw-api.log", "a"),
        stderr=subprocess.STDOUT,
    )
    for _ in range(12):
        time.sleep(10)
        try:
            if api("GET", "/health", timeout=10).get("ok"):
                log("API started OK")
                return True
        except Exception:
            pass
    return False


def scrape() -> list[dict]:
    payload = {
        "queries": QUERIES,
        "locations": LOCATIONS,
        "sites": SITES,
        "hours_old": 48,
        "results_per_query": 10,
        "country_indeed": "USA",
    }
    try:
        resp = api("POST", "/api/jobs/import-provider", payload, timeout=600)
    except Exception as exc:
        log(f"scrape failed ({exc}); retrying once with hours_old=72")
        payload["hours_old"] = 72
        resp = api("POST", "/api/jobs/import-provider", payload, timeout=600)
    jobs = resp.get("jobs", [])
    log(f"scrape done: imported_count={resp.get('imported_count')} jobs_in_response={len(jobs)}")
    return jobs


def git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True)


def main() -> int:
    os.makedirs(os.path.join(REPO, "leads"), exist_ok=True)
    os.makedirs(os.path.join(REPO, "watermarks"), exist_ok=True)

    if not ensure_api():
        log("FATAL: API not reachable, aborting")
        return 1

    jobs = scrape()

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    if jobs:
        path = os.path.join(REPO, "leads", f"{stamp}.json")
        with open(path, "w") as f:
            json.dump(jobs, f)
        log(f"wrote {len(jobs)} leads -> leads/{stamp}.json")
    else:
        log("no leads this run; nothing to export")

    wm_path = os.path.join(REPO, "watermarks", "rswan.json")
    wm = {}
    if os.path.exists(wm_path):
        wm = json.load(open(wm_path))
    wm.update({
        "last_run": datetime.now().isoformat(timespec="seconds"),
        "last_run_leads": len(jobs),
        "total_leads_exported": wm.get("total_leads_exported", 0) + len(jobs),
    })
    json.dump(wm, open(wm_path, "w"), indent=2)

    git("add", "leads", "watermarks")
    status = git("status", "--porcelain").stdout.strip()
    if status:
        git("commit", "-m", f"leads {stamp}: {len(jobs)} new")
        push = git("push")
        if push.returncode != 0:
            log(f"FATAL: git push failed: {push.stderr.strip()[:300]}")
            return 1
        log("pushed OK")
    else:
        log("nothing new to push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
