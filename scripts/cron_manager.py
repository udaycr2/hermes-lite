#!/usr/bin/env python3
"""Cron job manager for Hermes Lite"""
import json
import sys
import subprocess
import uuid
from pathlib import Path
from datetime import datetime

CRON_DIR = Path(__file__).parent.parent / "cron"
JOBS_FILE = CRON_DIR / "jobs.json"

CRON_DIR.mkdir(exist_ok=True)

def load_jobs():
    if JOBS_FILE.exists():
        try:
            return json.loads(JOBS_FILE.read_text())
        except:
            return {}
    return {}

def save_jobs(jobs):
    JOBS_FILE.write_text(json.dumps(jobs, indent=2))

def create_job(schedule: str, command: str, name: str = None, enabled: bool = True):
    """Create a new cron job"""
    jobs = load_jobs()
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "id": job_id,
        "name": name or job_id,
        "schedule": schedule,
        "command": command,
        "enabled": enabled,
        "created": datetime.now().isoformat(),
        "last_run": None,
        "last_result": None
    }
    save_jobs(jobs)
    return jobs[job_id]

def list_jobs():
    return list(load_jobs().values())

def remove_job(job_id: str):
    jobs = load_jobs()
    if job_id in jobs:
        del jobs[job_id]
        save_jobs(jobs)
        return True
    return False

def run_job(job_id: str):
    jobs = load_jobs()
    if job_id not in jobs:
        return {"error": f"Job not found: {job_id}"}
    
    job = jobs[job_id]
    try:
        result = subprocess.run(
            job["command"],
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=Path.home()
        )
        job["last_run"] = datetime.now().isoformat()
        job["last_result"] = {
            "stdout": result.stdout[-1000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else "",
            "returncode": result.returncode
        }
        save_jobs(jobs)
        return job["last_result"]
    except subprocess.TimeoutExpired:
        return {"error": "Job timed out after 300s"}
    except Exception as e:
        return {"error": str(e)}

def enable_job(job_id: str, enabled: bool = True):
    jobs = load_jobs()
    if job_id in jobs:
        jobs[job_id]["enabled"] = enabled
        save_jobs(jobs)
        return jobs[job_id]
    return None

def install_cron():
    """Install all enabled jobs to system crontab"""
    jobs = load_jobs()
    enabled = [j for j in jobs.values() if j.get("enabled")]
    
    # Read current crontab
    try:
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    except:
        current = ""
    
    # Remove existing hermes-lite entries
    lines = [l for l in current.split('\n') if 'hermes-lite-cron' not in l]
    
    # Add new entries
    for job in enabled:
        # Convert schedule to cron format if needed
        schedule = job["schedule"]
        if schedule.startswith("every "):
            # Convert "every 1h" -> "0 * * * *"
            parts = schedule.split()
            if len(parts) == 2:
                val = parts[1]
                if val.endswith('h'):
                    schedule = f"0 * * * *"
                elif val.endswith('m'):
                    schedule = f"*/{val[:-1]} * * * *"
                elif val.endswith('d'):
                    schedule = f"0 0 * * *"
        
        cmd = f"{sys.executable} -m scripts.cron_manager run {job['id']} # hermes-lite-cron"
        lines.append(f"{schedule} {cmd}")
    
    # Write new crontab
    subprocess.run(["crontab", "-"], input='\n'.join(lines) + '\n', text=True)
    print(f"Installed {len(enabled)} cron jobs")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: cron_manager.py <create|list|remove|run|enable|disable|install> [args...]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "create" and len(sys.argv) >= 4:
        schedule = sys.argv[2]
        command = ' '.join(sys.argv[3:])
        name = sys.argv[4] if len(sys.argv) > 4 else None
        job = create_job(schedule, command, name)
        print(json.dumps(job, indent=2))
    
    elif action == "list":
        print(json.dumps(list_jobs(), indent=2))
    
    elif action == "remove" and len(sys.argv) >= 3:
        job_id = sys.argv[2]
        if remove_job(job_id):
            print(f"Removed job {job_id}")
        else:
            print(f"Job not found: {job_id}")
    
    elif action == "run" and len(sys.argv) >= 3:
        job_id = sys.argv[2]
        result = run_job(job_id)
        print(json.dumps(result, indent=2))
    
    elif action == "enable" and len(sys.argv) >= 3:
        job_id = sys.argv[2]
        job = enable_job(job_id, True)
        if job:
            print(json.dumps(job, indent=2))
        else:
            print(f"Job not found: {job_id}")
    
    elif action == "disable" and len(sys.argv) >= 3:
        job_id = sys.argv[2]
        job = enable_job(job_id, False)
        if job:
            print(json.dumps(job, indent=2))
        else:
            print(f"Job not found: {job_id}")
    
    elif action == "install":
        install_cron()
    
    else:
        print("Usage: cron_manager.py <create|list|remove|run|enable|disable|install> [args...]")
