#!/usr/bin/env python3
"""Lance le pipeline prediction complet et envoie en inbox TikTok."""
import sys
import json
import uuid
import traceback
import os
from datetime import datetime
from pathlib import Path

# Setup paths
API_DIR = Path(__file__).parent
sys.path.insert(0, str(API_DIR))

# Charger le .env
_env_file = API_DIR.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

os.environ.setdefault("FAL_KEY", "1a1eb80d-0514-4bfd-aa09-1dcfe146d824:22e876a815145d09f03f47fdcde8ce17")

LOG_FILE = API_DIR.parent / "data" / "daily_run.log"
DATA_DIR = API_DIR.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


PRED_JOBS_FILE = DATA_DIR / "pred_jobs.json"


def _save_job(job: dict):
    try:
        store = json.loads(PRED_JOBS_FILE.read_text()) if PRED_JOBS_FILE.exists() else {}
    except Exception:
        store = {}
    store[job["id"]] = job
    PRED_JOBS_FILE.write_text(json.dumps(store, indent=2))


def run():
    log("=== Daily run démarré ===")
    job_id = f"pred_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    log(f"Job ID: {job_id}")

    created_at = datetime.now().isoformat()
    job = {
        "id": job_id,
        "status": "running",
        "created_at": created_at,
        "updated_at": created_at,
        "agents": {
            "content":       {"status": "pending", "result": None, "error": None, "updated_at": created_at},
            "image_prompts": {"status": "pending", "result": None, "error": None, "updated_at": created_at},
            "images":        {"status": "pending", "result": None, "error": None, "updated_at": created_at},
            "publish":       {"status": "pending", "result": None, "error": None, "updated_at": created_at},
        }
    }
    _save_job(job)

    def agent_done(name, result):
        now = datetime.now().isoformat()
        job["agents"][name] = {"status": "done", "result": result, "error": None, "updated_at": now}
        job["updated_at"] = now
        _save_job(job)

    def agent_error(name, err):
        now = datetime.now().isoformat()
        job["agents"][name] = {"status": "error", "result": None, "error": err, "updated_at": now}
        job["status"] = "error"
        job["updated_at"] = now
        _save_job(job)

    try:
        # Agent 1 — Contenu
        log("Agent 1: Contenu...")
        from workflows.prediction import agent_content
        content = agent_content.run()
        log(f"  Hook: {content.get('hook')} | Thème: {content.get('_theme')}")
        agent_done("content", content)

        # Agent 2 — Prompts images
        log("Agent 2: Prompts images...")
        from workflows.prediction import agent_image_prompts
        image_prompts = agent_image_prompts.run({"content": content})
        log(f"  Seed: {image_prompts.get('seed')}")
        agent_done("image_prompts", image_prompts)

        # Agent 3 — Images
        log("Agent 3: Génération images...")
        from workflows.prediction import agent_images
        content["_job_id"] = job_id
        images_result = agent_images.run({
            "content": content,
            "image_prompts": image_prompts,
            "job_id": job_id,
        })
        log(f"  Images générées: {list(images_result.get('images', {}).keys())}")
        agent_done("images", images_result)

        # Agent 4 — Publication
        log("Agent 4: Publication TikTok...")
        from workflows.prediction import agent_publish
        publish_result = agent_publish.run({
            "content": content,
            "images": images_result.get("images", {}),
            "job_id": job_id,
        })
        status = publish_result.get("publish", {}).get("status")
        message = publish_result.get("publish", {}).get("message", "")
        log(f"  Status: {status} — {message}")
        agent_done("publish", publish_result)

        job["status"] = "done"
        job["updated_at"] = datetime.now().isoformat()
        _save_job(job)
        log("=== Daily run terminé avec succès ===")

    except Exception:
        err = traceback.format_exc()
        log(f"ERREUR:\n{err}")
        # Marquer l'agent en cours comme en erreur
        for name, a in job["agents"].items():
            if a["status"] == "pending":
                agent_error(name, err)
                break
        sys.exit(1)


if __name__ == "__main__":
    run()
