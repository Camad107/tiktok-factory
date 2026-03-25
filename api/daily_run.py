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


def run():
    log("=== Daily run démarré ===")
    job_id = f"pred_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    log(f"Job ID: {job_id}")

    try:
        # Agent 1 — Contenu
        log("Agent 1: Contenu...")
        from workflows.prediction import agent_content
        content = agent_content.run()
        log(f"  Hook: {content.get('hook')} | Thème: {content.get('_theme')}")

        # Agent 2 — Prompts images
        log("Agent 2: Prompts images...")
        from workflows.prediction import agent_image_prompts
        image_prompts = agent_image_prompts.run({"content": content})
        log(f"  Seed: {image_prompts.get('seed')}")

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

        # Sauvegarder dans pred_jobs.json
        pred_jobs_file = DATA_DIR / "pred_jobs.json"
        try:
            pred_jobs = json.loads(pred_jobs_file.read_text()) if pred_jobs_file.exists() else {}
        except Exception:
            pred_jobs = {}

        pred_jobs[job_id] = {
            "id": job_id,
            "status": "done",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "agents": {
                "content":       {"status": "done", "result": content,        "error": None, "updated_at": datetime.now().isoformat()},
                "image_prompts": {"status": "done", "result": image_prompts,  "error": None, "updated_at": datetime.now().isoformat()},
                "images":        {"status": "done", "result": images_result,  "error": None, "updated_at": datetime.now().isoformat()},
                "publish":       {"status": "done", "result": publish_result, "error": None, "updated_at": datetime.now().isoformat()},
            }
        }
        pred_jobs_file.write_text(json.dumps(pred_jobs, indent=2))
        log(f"  Job sauvegardé.")
        log("=== Daily run terminé avec succès ===")

    except Exception:
        err = traceback.format_exc()
        log(f"ERREUR:\n{err}")
        sys.exit(1)


if __name__ == "__main__":
    run()
