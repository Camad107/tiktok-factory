"""TikTok Voyance — API Backend"""
import os
import json
import uuid
import threading
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Body, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse

app = FastAPI(title="TikTok Voyance API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATIC_DIR = Path(__file__).parent.parent / "static"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

FAL_KEY = os.environ.get("FAL_KEY", "")
KIE_KEY = os.environ.get("KIE_KEY", "")
AGENT_ORDER = ["content", "image_prompts", "images", "voice", "video"]
PRED_AGENT_ORDER = ["content", "image_prompts", "images", "publish"]

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
JOBS_FILE = DATA_DIR / "jobs.json"
PRED_JOBS_FILE = DATA_DIR / "pred_jobs.json"
PENDULE_JOBS_FILE = DATA_DIR / "pendule_jobs.json"
VIDEO_JOBS_FILE = DATA_DIR / "video_jobs.json"


def _load_store(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def _save_store(path: Path, store: dict):
    try:
        path.write_text(json.dumps(store, indent=2))
    except Exception:
        pass


def _reset_running_jobs(store: dict):
    """Au démarrage, tout job/agent bloqué en 'running' est passé en 'error'."""
    for job in store.values():
        if job.get("status") == "running":
            job["status"] = "error"
        for ag in job.get("agents", {}).values():
            if ag.get("status") == "running":
                ag["status"] = "error"
                ag["error"] = "Service restarted — agent interrupted"


JOBS: dict[str, dict] = _load_store(JOBS_FILE)
PRED_JOBS: dict[str, dict] = _load_store(PRED_JOBS_FILE)
PENDULE_JOBS: dict[str, dict] = _load_store(PENDULE_JOBS_FILE)
PENDULE_AGENT_ORDER = ["image", "video"]
VIDEO_JOBS: dict[str, dict] = _load_store(VIDEO_JOBS_FILE)
RET_AGENT_ORDER = ["content", "prompts", "flux", "voice", "video", "publish"]
RET_JOBS_FILE = DATA_DIR / "retournement_jobs.json"

HIST_AGENT_ORDER = ["topic", "research", "prompt", "visual", "montage", "publish"]
HIST_JOBS_FILE = DATA_DIR / "histoire_jobs.json"
HIST_JOBS: dict[str, dict] = _load_store(HIST_JOBS_FILE)
_reset_running_jobs(HIST_JOBS)

HIST2_AGENT_ORDER = ["topic", "research", "prompt", "visual", "montage"]
HIST2_JOBS_FILE = DATA_DIR / "histoire2_jobs.json"
HIST2_JOBS: dict[str, dict] = _load_store(HIST2_JOBS_FILE)
_reset_running_jobs(HIST2_JOBS)
RET_SETTINGS_FILE = DATA_DIR / "retournement_settings.json"
RET_SOURCES_DIR = Path(__file__).parent.parent / "output" / "retournement_sources"
RET_OUTPUT_DIR = Path(__file__).parent.parent / "output" / "retournement"
RET_JOBS: dict[str, dict] = _load_store(RET_JOBS_FILE)
for _store in [JOBS, PRED_JOBS, PENDULE_JOBS, VIDEO_JOBS, RET_JOBS]:
    _reset_running_jobs(_store)
RET_SOURCES_DIR.mkdir(parents=True, exist_ok=True)
RET_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_UPLOAD_DIR = Path(__file__).parent.parent / "output" / "video_refs"
VIDEO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def make_job(job_id: str) -> dict:
    return {
        "id": job_id,
        "status": "idle",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "agents": {
            name: {"status": "pending", "result": None, "error": None, "updated_at": None}
            for name in AGENT_ORDER
        },
        "error": None,
    }


def update_agent(job_id: str, agent: str, status: str, result=None, error=None):
    JOBS[job_id]["agents"][agent] = {
        "status": status,
        "result": result,
        "error": error,
        "updated_at": datetime.now().isoformat(),
    }
    JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(JOBS_FILE, JOBS)


def run_agent_sync(job_id: str, agent_name: str, params: dict):
    """Lance un agent dans un thread, met à jour le job."""
    os.environ["FAL_KEY"] = FAL_KEY
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    from agents import agent_content, agent_image_prompts, agent_images, agent_voice, agent_video
    AGENTS = {
        "content": agent_content,
        "image_prompts": agent_image_prompts,
        "images": agent_images,
        "voice": agent_voice,
        "video": agent_video,
    }

    update_agent(job_id, agent_name, "running")
    JOBS[job_id]["status"] = "running"
    try:
        result = AGENTS[agent_name].run(params)
        update_agent(job_id, agent_name, "done", result=result)
        # Si c'est le dernier agent done, marquer job done
        all_done = all(
            JOBS[job_id]["agents"][a]["status"] == "done"
            for a in AGENT_ORDER
        )
        if all_done:
            JOBS[job_id]["status"] = "done"
        else:
            JOBS[job_id]["status"] = "idle"
    except Exception as e:
        err = traceback.format_exc()
        update_agent(job_id, agent_name, "error", error=err)
        JOBS[job_id]["status"] = "error"


# ─── Routes ────────────────────────────────────────────────────────────────

@app.get("/")
def index(wf: str = None):
    headers = {"Cache-Control": "no-store"}
    if wf == "prediction":
        return FileResponse(str(STATIC_DIR / "prediction.html"), headers=headers)
    if wf == "pendule":
        return FileResponse(str(STATIC_DIR / "pendule.html"), headers=headers)
    if wf == "video":
        return FileResponse(str(STATIC_DIR / "video.html"), headers=headers)
    if wf == "satisfying":
        return FileResponse(str(STATIC_DIR / "satisfying.html"), headers=headers)
    if wf == "retournement":
        return FileResponse(str(STATIC_DIR / "retournement.html"), headers=headers)
    if wf == "histoire":
        return FileResponse(str(STATIC_DIR / "histoire.html"), headers=headers)
    if wf == "histoire2":
        return FileResponse(str(STATIC_DIR / "histoire2.html"), headers=headers)
    if wf:
        return FileResponse(str(STATIC_DIR / "index.html"), headers=headers)
    return FileResponse(str(STATIC_DIR / "home.html"), headers=headers)


# ─── Prediction workflow routes ─────────────────────────────────────────────

def pred_run_agent_sync(job_id: str, agent_name: str, params: dict):
    os.environ["FAL_KEY"] = FAL_KEY
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from workflows.prediction import agent_content, agent_image_prompts, agent_images, agent_publish
    AGENTS = {"content": agent_content, "image_prompts": agent_image_prompts, "images": agent_images, "publish": agent_publish}

    # Migration : ajouter les agents manquants sur les anciens jobs
    for a in PRED_AGENT_ORDER:
        if a not in PRED_JOBS[job_id]["agents"]:
            PRED_JOBS[job_id]["agents"][a] = {"status": "pending", "result": None, "error": None, "updated_at": None}

    PRED_JOBS[job_id]["agents"][agent_name]["status"] = "running"
    PRED_JOBS[job_id]["agents"][agent_name]["updated_at"] = datetime.now().isoformat()
    PRED_JOBS[job_id]["status"] = "running"
    PRED_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    try:
        result = AGENTS[agent_name].run(params)
        PRED_JOBS[job_id]["agents"][agent_name] = {
            "status": "done", "result": result,
            "error": None, "updated_at": datetime.now().isoformat()
        }
        all_done = all(PRED_JOBS[job_id]["agents"][a]["status"] == "done" for a in PRED_AGENT_ORDER)
        PRED_JOBS[job_id]["status"] = "done" if all_done else "idle"
    except Exception:
        err = traceback.format_exc()
        PRED_JOBS[job_id]["agents"][agent_name] = {
            "status": "error", "result": None,
            "error": err, "updated_at": datetime.now().isoformat()
        }
        PRED_JOBS[job_id]["status"] = "error"
    PRED_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(PRED_JOBS_FILE, PRED_JOBS)


@app.post("/api/pred/jobs")
def pred_create_job():
    job_id = f"pred_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    PRED_JOBS[job_id] = {
        "id": job_id, "status": "idle",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "agents": {
            name: {"status": "pending", "result": None, "error": None, "updated_at": None}
            for name in PRED_AGENT_ORDER
        },
    }
    _save_store(PRED_JOBS_FILE, PRED_JOBS)
    return {"job_id": job_id}


@app.get("/api/pred/jobs")
def pred_list_jobs():
    store = _load_store(PRED_JOBS_FILE)
    PRED_JOBS.update(store)
    return {"jobs": sorted(PRED_JOBS.values(), key=lambda x: x["created_at"], reverse=True)}


@app.get("/api/pred/jobs/{job_id}")
def pred_get_job(job_id: str):
    store = _load_store(PRED_JOBS_FILE)
    PRED_JOBS.update(store)
    if job_id not in PRED_JOBS:
        raise HTTPException(404, "Job not found")
    return PRED_JOBS[job_id]


@app.post("/api/pred/jobs/{job_id}/run/{agent_name}")
def pred_run_agent(job_id: str, agent_name: str, body: dict = Body(default={})):
    if job_id not in PRED_JOBS:
        raise HTTPException(404, "Job not found")
    if agent_name not in PRED_AGENT_ORDER:
        raise HTTPException(400, f"Unknown agent: {agent_name}")

    job = PRED_JOBS[job_id]
    agents = job["agents"]
    params = {"job_id": job_id}

    if agent_name == "image_prompts":
        params["content"] = body.get("content") or (agents["content"].get("result") or {})
    elif agent_name == "images":
        params["content"] = body.get("content") or (agents["content"].get("result") or {})
        params["image_prompts"] = body.get("image_prompts") or (agents["image_prompts"].get("result") or {})
        for k, v in body.items():
            params[k] = v
    elif agent_name == "publish":
        params["content"] = body.get("content") or (agents["content"].get("result") or {})
        params["images"] = body.get("images") or ((agents["images"].get("result") or {}).get("images") or {})

    threading.Thread(target=pred_run_agent_sync, args=(job_id, agent_name, params), daemon=True).start()
    return {"ok": True, "agent": agent_name}

@app.get("/api/ping")
def ping():
    return {"status": "ok", "fal_configured": bool(FAL_KEY)}


@app.get("/verify")
def tiktok_verify_root():
    """Page de vérification TikTok — servi à la racine du domaine."""
    return HTMLResponse("""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="tiktok-developers-site-verification" content="RxUGHl4Ay0JfWDidYsuGbGDYrsQReOzh">
<title>Factory</title>
</head>
<body></body>
</html>""")


# ─── TikTok OAuth ────────────────────────────────────────────────────────────

@app.get("/oauth/tiktok")
def tiktok_oauth_start():
    """Redirige vers la page d'autorisation TikTok."""
    from tiktok_auth import get_auth_url
    return RedirectResponse(get_auth_url())


@app.get("/oauth/callback")
def tiktok_oauth_callback(request: Request, code: str = None, error: str = None, state: str = None):
    """Callback OAuth TikTok — échange le code contre un token."""
    if error:
        return HTMLResponse(f"<h2>Erreur TikTok OAuth</h2><p>{error}</p>")
    if not code:
        return HTMLResponse("<h2>Pas de code reçu</h2>")
    try:
        from tiktok_auth import exchange_code
        data = exchange_code(code)
        return HTMLResponse(f"""
        <html><body style="font-family:sans-serif;max-width:600px;margin:40px auto;padding:20px">
        <h2>✓ TikTok connecté</h2>
        <p>Token sauvegardé avec succès.</p>
        <p><b>Open ID :</b> {data.get('open_id', 'N/A')}</p>
        <p><b>Scope :</b> {data.get('scope', 'N/A')}</p>
        <p><a href="/tiktok/">← Retour à l'interface</a></p>
        </body></html>
        """)
    except Exception as e:
        return HTMLResponse(f"<h2>Erreur</h2><pre>{e}</pre>")


@app.get("/api/tiktok/status")
def tiktok_status():
    from tiktok_auth import load_token
    token = load_token()
    if not token:
        return {"connected": False, "auth_url": "/oauth/tiktok"}
    return {"connected": True, "open_id": token.get("open_id"), "scope": token.get("scope")}


@app.post("/api/tiktok/publish")
def tiktok_publish(body: dict = Body(default={})):
    """Publie les images d'un job prediction sur TikTok."""
    images = body.get("images", {})
    caption = body.get("caption", "Oracle du jour ✨")
    image_paths = [v for k, v in sorted(images.items()) if v]
    if not image_paths:
        raise HTTPException(400, "Pas d'images à publier")
    try:
        from tiktok_post import post_photo_carousel
        result = post_photo_carousel(image_paths, caption)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# ─── Video workflow routes ───────────────────────────────────────────────────

VIDEO_AGENT_ORDER = ["question", "video_gen", "overlay", "montage", "publish"]
VIDEO_SETTINGS_FILE = DATA_DIR / "video_settings.json"
VIDEO_SETTINGS: dict = _load_store(VIDEO_SETTINGS_FILE) if VIDEO_SETTINGS_FILE.exists() else {"first_frame_url": None, "last_frames": {}}


@app.post("/api/video/upload")
async def video_upload_frame(file: UploadFile = File(...), frame: str = "first", job_id: str = "global"):
    ext = Path(file.filename).suffix or ".jpg"
    filename = f"{job_id}_{frame}{ext}"
    dest = VIDEO_UPLOAD_DIR / filename
    dest.write_bytes(await file.read())
    public_url = f"https://factorytiktok.duckdns.org/output/video_refs/{filename}"
    return {"url": public_url, "path": str(dest)}


@app.get("/api/video/settings")
def video_get_settings():
    return VIDEO_SETTINGS


@app.patch("/api/video/settings")
def video_update_settings(body: dict = Body(default={})):
    if "first_frame_url" in body:
        VIDEO_SETTINGS["first_frame_url"] = body["first_frame_url"]
    if "last_frames" in body:
        VIDEO_SETTINGS.setdefault("last_frames", {}).update(body["last_frames"])
    _save_store(VIDEO_SETTINGS_FILE, VIDEO_SETTINGS)
    return VIDEO_SETTINGS


@app.post("/api/video/jobs")
def video_create_job():
    job_id = f"vid_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    VIDEO_JOBS[job_id] = {
        "id": job_id, "status": "idle",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "subject_id": None,
        "agents": {
            name: {"status": "pending", "result": None, "error": None}
            for name in VIDEO_AGENT_ORDER
        },
    }
    _save_store(VIDEO_JOBS_FILE, VIDEO_JOBS)
    return {"job_id": job_id}


@app.get("/api/video/jobs")
def video_list_jobs():
    VIDEO_JOBS.update(_load_store(VIDEO_JOBS_FILE))
    return {"jobs": sorted(VIDEO_JOBS.values(), key=lambda x: x["created_at"], reverse=True)}


@app.get("/api/video/jobs/{job_id}")
def video_get_job(job_id: str):
    VIDEO_JOBS.update(_load_store(VIDEO_JOBS_FILE))
    if job_id not in VIDEO_JOBS:
        raise HTTPException(404, "Job not found")
    return VIDEO_JOBS[job_id]


@app.patch("/api/video/jobs/{job_id}")
def video_update_job(job_id: str, body: dict = Body(default={})):
    if job_id not in VIDEO_JOBS:
        raise HTTPException(404, "Job not found")
    if "subject_id" in body:
        VIDEO_JOBS[job_id]["subject_id"] = body["subject_id"]
    VIDEO_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(VIDEO_JOBS_FILE, VIDEO_JOBS)
    return VIDEO_JOBS[job_id]


def _video_agent_run(job_id: str, agent_name: str):
    os.environ["FAL_KEY"] = FAL_KEY
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from workflows.video import agent_question, agent_video_gen, agent_overlay, agent_montage, agent_publish
    VAGENTS = {
        "question": agent_question,
        "video_gen": agent_video_gen,
        "overlay": agent_overlay,
        "montage": agent_montage,
        "publish": agent_publish,
    }

    job = VIDEO_JOBS[job_id]
    agents = job["agents"]
    settings = _load_store(VIDEO_SETTINGS_FILE)

    params = {
        "job_id": job_id,
        "first_frame_url": settings.get("first_frame_url", ""),
        "last_frames": settings.get("last_frames", {}),
    }
    if agent_name == "question":
        params["subject_id"] = job.get("subject_id")
    elif agent_name == "video_gen":
        params["question_result"] = agents["question"].get("result") or {}
    elif agent_name == "overlay":
        params["question_result"] = agents["question"].get("result") or {}
    elif agent_name == "montage":
        params["overlay_result"] = agents["overlay"].get("result") or {}
        params["video_result"] = agents["video_gen"].get("result") or {}
    elif agent_name == "publish":
        params["question_result"] = agents["question"].get("result") or {}
        params["montage_result"] = agents["montage"].get("result") or {}

    # Migration : ajouter les agents manquants sur les anciens jobs
    for a in VIDEO_AGENT_ORDER:
        if a not in VIDEO_JOBS[job_id]["agents"]:
            VIDEO_JOBS[job_id]["agents"][a] = {"status": "pending", "result": None, "error": None}

    VIDEO_JOBS[job_id]["agents"][agent_name]["status"] = "running"
    VIDEO_JOBS[job_id]["status"] = "running"
    VIDEO_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(VIDEO_JOBS_FILE, VIDEO_JOBS)

    try:
        result = VAGENTS[agent_name].run(params)
        VIDEO_JOBS[job_id]["agents"][agent_name] = {"status": "done", "result": result, "error": None}
        all_done = all(VIDEO_JOBS[job_id]["agents"][a]["status"] == "done" for a in VIDEO_AGENT_ORDER)
        VIDEO_JOBS[job_id]["status"] = "done" if all_done else "idle"
    except Exception:
        err = traceback.format_exc()
        VIDEO_JOBS[job_id]["agents"][agent_name] = {"status": "error", "result": None, "error": err}
        VIDEO_JOBS[job_id]["status"] = "error"
    VIDEO_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(VIDEO_JOBS_FILE, VIDEO_JOBS)


@app.post("/api/video/cron")
def video_cron():
    """Lance le pipeline vidéo complet automatiquement (cron midi Hanoï = 5h UTC)."""
    def full_pipeline():
        os.environ["FAL_KEY"] = FAL_KEY
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from workflows.video import agent_question, agent_video_gen, agent_overlay, agent_montage, agent_publish

        job_id = f"vid_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        VIDEO_JOBS[job_id] = {
            "id": job_id, "status": "running",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "subject_id": None,
            "agents": {
                name: {"status": "pending", "result": None, "error": None}
                for name in VIDEO_AGENT_ORDER
            },
        }
        _save_store(VIDEO_JOBS_FILE, VIDEO_JOBS)

        settings = _load_store(VIDEO_SETTINGS_FILE)
        base_params = {
            "job_id": job_id,
            "first_frame_url": settings.get("first_frame_url", ""),
            "last_frames": settings.get("last_frames", {}),
        }

        steps = [
            ("question",  lambda r: {**base_params}),
            ("video_gen", lambda r: {**base_params, "question_result": r["question"]}),
            ("overlay",   lambda r: {**base_params, "question_result": r["question"]}),
            ("montage",   lambda r: {**base_params, "overlay_result": r["overlay"], "video_result": r["video_gen"]}),
            ("publish",   lambda r: {**base_params, "question_result": r["question"], "montage_result": r["montage"]}),
        ]

        results = {}
        for agent_name, build_params in steps:
            VIDEO_JOBS[job_id]["agents"][agent_name]["status"] = "running"
            VIDEO_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
            _save_store(VIDEO_JOBS_FILE, VIDEO_JOBS)
            try:
                agents_map = {
                    "question": agent_question, "video_gen": agent_video_gen,
                    "overlay": agent_overlay, "montage": agent_montage, "publish": agent_publish,
                }
                result = agents_map[agent_name].run(build_params(results))
                results[agent_name] = result
                VIDEO_JOBS[job_id]["agents"][agent_name] = {"status": "done", "result": result, "error": None}
            except Exception:
                err = traceback.format_exc()
                VIDEO_JOBS[job_id]["agents"][agent_name] = {"status": "error", "result": None, "error": err}
                VIDEO_JOBS[job_id]["status"] = "error"
                VIDEO_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
                _save_store(VIDEO_JOBS_FILE, VIDEO_JOBS)
                return

        VIDEO_JOBS[job_id]["status"] = "done"
        VIDEO_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
        _save_store(VIDEO_JOBS_FILE, VIDEO_JOBS)

    threading.Thread(target=full_pipeline, daemon=True).start()
    return {"ok": True, "message": "Pipeline vidéo lancé"}


@app.post("/api/video/jobs/{job_id}/run/{agent_name}")
def video_run_agent(job_id: str, agent_name: str, body: dict = Body(default={})):
    if job_id not in VIDEO_JOBS:
        raise HTTPException(404, "Job not found")
    if agent_name not in VIDEO_AGENT_ORDER:
        raise HTTPException(400, f"Unknown agent: {agent_name}")
    if "subject_id" in body:
        VIDEO_JOBS[job_id]["subject_id"] = body["subject_id"]
        _save_store(VIDEO_JOBS_FILE, VIDEO_JOBS)
    threading.Thread(target=_video_agent_run, args=(job_id, agent_name), daemon=True).start()
    return {"ok": True, "agent": agent_name}


# ─── Retournement workflow routes ────────────────────────────────────────────

def _ret_run_agent_sync(job_id: str, agent_name: str, params: dict):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from workflows.retournement import agent_content as ret_content
    from workflows.retournement import agent_prompts as ret_prompts
    from workflows.retournement import agent_flux as ret_flux
    from workflows.retournement import agent_voice as ret_voice
    from workflows.retournement import agent_video as ret_video
    from workflows.retournement import agent_publish as ret_publish
    RAGENTS = {
        "content": ret_content, "prompts": ret_prompts, "flux": ret_flux,
        "voice": ret_voice, "video": ret_video, "publish": ret_publish,
    }
    for a in RET_AGENT_ORDER:
        if a not in RET_JOBS[job_id]["agents"]:
            RET_JOBS[job_id]["agents"][a] = {"status": "pending", "result": None, "error": None, "updated_at": None}

    RET_JOBS[job_id]["agents"][agent_name]["status"] = "running"
    RET_JOBS[job_id]["agents"][agent_name]["updated_at"] = datetime.now().isoformat()
    RET_JOBS[job_id]["status"] = "running"
    RET_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(RET_JOBS_FILE, RET_JOBS)
    try:
        result = RAGENTS[agent_name].run(params)
        RET_JOBS[job_id]["agents"][agent_name] = {"status": "done", "result": result, "error": None, "updated_at": datetime.now().isoformat()}
        all_done = all(RET_JOBS[job_id]["agents"][a]["status"] == "done" for a in RET_AGENT_ORDER)
        RET_JOBS[job_id]["status"] = "done" if all_done else "idle"
    except Exception:
        err = traceback.format_exc()
        RET_JOBS[job_id]["agents"][agent_name] = {"status": "error", "result": None, "error": err, "updated_at": datetime.now().isoformat()}
        RET_JOBS[job_id]["status"] = "error"
    RET_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(RET_JOBS_FILE, RET_JOBS)


@app.post("/api/retournement/jobs")
def ret_create_job():
    job_id = f"ret_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    RET_JOBS[job_id] = {
        "id": job_id, "status": "idle",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "agents": {a: {"status": "pending", "result": None, "error": None, "updated_at": None} for a in RET_AGENT_ORDER},
    }
    _save_store(RET_JOBS_FILE, RET_JOBS)
    return {"job_id": job_id}


@app.get("/api/retournement/jobs")
def ret_list_jobs():
    RET_JOBS.update(_load_store(RET_JOBS_FILE))
    return {"jobs": sorted(RET_JOBS.values(), key=lambda x: x["created_at"], reverse=True)}


@app.get("/api/retournement/jobs/{job_id}")
def ret_get_job(job_id: str):
    RET_JOBS.update(_load_store(RET_JOBS_FILE))
    if job_id not in RET_JOBS:
        raise HTTPException(404, "Job not found")
    return RET_JOBS[job_id]


@app.post("/api/retournement/jobs/{job_id}/run/{agent_name}")
def ret_run_agent(job_id: str, agent_name: str, body: dict = Body(default={})):
    if job_id not in RET_JOBS:
        raise HTTPException(404, "Job not found")
    if agent_name not in RET_AGENT_ORDER:
        raise HTTPException(400, f"Agent inconnu: {agent_name}")

    settings = _load_store(RET_SETTINGS_FILE)
    agents = RET_JOBS[job_id]["agents"]

    params = {"job_id": job_id, **body}

    if agent_name == "content":
        params["job_id"] = job_id

    elif agent_name == "prompts":
        params["content"] = (agents.get("content") or {}).get("result") or {}

    elif agent_name == "flux":
        params["content"] = (agents.get("content") or {}).get("result") or {}
        params["prompts"] = (agents.get("prompts") or {}).get("result") or {}
        params["flux"] = (agents.get("flux") or {}).get("result") or {}
        params["sources_dir"] = str(RET_SOURCES_DIR)
        # step passé depuis le body (A/B/C/all), déjà dans params via body

    elif agent_name == "voice":
        params["content"] = (agents.get("content") or {}).get("result") or {}

    elif agent_name == "video":
        params["content"] = (agents.get("content") or {}).get("result") or {}
        params["flux"] = (agents.get("flux") or {}).get("result") or {}
        params["voice"] = (agents.get("voice") or {}).get("result") or {}

    elif agent_name == "publish":
        params["content"] = (agents.get("content") or {}).get("result") or {}
        params["video"] = (agents.get("video") or {}).get("result") or {}

    threading.Thread(target=_ret_run_agent_sync, args=(job_id, agent_name, params), daemon=True).start()
    return {"ok": True, "agent": agent_name}


@app.get("/api/retournement/settings")
def ret_get_settings():
    settings = _load_store(RET_SETTINGS_FILE)
    return settings


@app.post("/api/retournement/settings")
def ret_save_settings(body: dict = Body(default={})):
    settings = _load_store(RET_SETTINGS_FILE)
    for key in ["sources_dir"]:
        if key in body:
            settings[key] = body[key]
    _save_store(RET_SETTINGS_FILE, settings)
    return settings


ARCANES_FILE = DATA_DIR / "arcanes.json"


@app.get("/api/retournement/arcanes")
def ret_get_arcanes():
    return json.loads(ARCANES_FILE.read_text())


@app.post("/api/retournement/arcanes")
def ret_save_arcanes(body: list = Body(default=[])):
    ARCANES_FILE.write_text(json.dumps(body, ensure_ascii=False, indent=2))
    return {"ok": True, "count": len(body)}


@app.post("/api/retournement/upload")
async def ret_upload_source(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png"):
        raise HTTPException(400, "Format non supporté — utilisez JPG ou PNG")

    raw = await file.read()

    # Compresser si > 1MB pour éviter le 413 de kie.ai
    MAX_BYTES = 1 * 1024 * 1024
    if len(raw) > MAX_BYTES:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        w, h = img.size
        if max(w, h) > 2048:
            ratio = 2048 / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        quality = 90
        while quality >= 40:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            raw = buf.getvalue()
            if len(raw) <= MAX_BYTES:
                break
            quality -= 10
        # Forcer extension .jpg après compression
        stem = Path(file.filename).stem
        filename = stem + ".jpg"
    else:
        filename = file.filename

    dest = RET_SOURCES_DIR / filename
    dest.write_bytes(raw)
    public_url = f"https://factorytiktok.duckdns.org/output/retournement_sources/{filename}"
    return {"filename": filename, "url": public_url, "path": str(dest)}


@app.get("/api/retournement/sources")
def ret_list_sources():
    files = list(RET_SOURCES_DIR.glob("*.jpg")) + list(RET_SOURCES_DIR.glob("*.jpeg")) + list(RET_SOURCES_DIR.glob("*.png"))
    return {"sources": [{"filename": f.name, "url": f"https://factorytiktok.duckdns.org/output/retournement_sources/{f.name}"} for f in sorted(files)]}


@app.delete("/api/retournement/sources/{filename}")
def ret_delete_source(filename: str):
    dest = RET_SOURCES_DIR / filename
    if not dest.exists() or not dest.is_file():
        raise HTTPException(404, "Fichier non trouvé")
    dest.unlink()
    return {"ok": True, "deleted": filename}


# ─── Legal pages ─────────────────────────────────────────────────────────────

@app.get("/terms")
def terms():
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Terms of Service — Factory</title>
<style>body{font-family:sans-serif;max-width:800px;margin:60px auto;padding:0 20px;color:#333;line-height:1.7}h1{color:#111}h2{margin-top:2em}</style>
</head><body>
<h1>Terms of Service</h1>
<p><em>Last updated: March 2026</em></p>
<h2>1. Service Description</h2>
<p>Factory is a content creation tool that generates oracle card posts and publishes them to TikTok via the TikTok Content Posting API. The service is operated for a single creator account.</p>
<h2>2. Use of TikTok Integration</h2>
<p>By connecting your TikTok account, you authorize this application to upload and publish video content on your behalf using the TikTok Content Posting API. You may revoke this access at any time through your TikTok account settings.</p>
<h2>3. Content</h2>
<p>All content published through this service is AI-generated oracle/tarot card content for entertainment purposes only. It does not constitute professional advice of any kind.</p>
<h2>4. Data</h2>
<p>We store only the OAuth access token required to publish content. No personal data beyond the TikTok Open ID is retained. Tokens are stored securely on our server and never shared with third parties.</p>
<h2>5. Limitation of Liability</h2>
<p>This service is provided as-is. We are not liable for any damages arising from use of this service or published content.</p>
<h2>6. Contact</h2>
<p>For any questions, contact the operator of this service.</p>
</body></html>""")


@app.get("/privacy")
def privacy():
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Privacy Policy — Factory</title>
<style>body{font-family:sans-serif;max-width:800px;margin:60px auto;padding:0 20px;color:#333;line-height:1.7}h1{color:#111}h2{margin-top:2em}</style>
</head><body>
<h1>Privacy Policy</h1>
<p><em>Last updated: March 2026</em></p>
<h2>1. Data We Collect</h2>
<p>When you authorize this application via TikTok OAuth, we receive and store:</p>
<ul>
<li>Your TikTok Open ID (anonymous identifier)</li>
<li>An OAuth access token and refresh token</li>
<li>The authorized scopes (video.upload, video.publish)</li>
</ul>
<p>We do not collect your name, email, profile picture, follower list, or any other personal information.</p>
<h2>2. How We Use Your Data</h2>
<p>The OAuth token is used solely to publish AI-generated content to your TikTok account via the Content Posting API. It is not used for any other purpose.</p>
<h2>3. Data Storage</h2>
<p>Tokens are stored in a JSON file on a private server. They are never transmitted to third parties.</p>
<h2>4. Data Retention</h2>
<p>Tokens are retained until you revoke access via TikTok settings or request deletion. To delete your data, revoke access in your TikTok account under <em>Settings → Security → Authorized Apps</em>.</p>
<h2>5. Third Parties</h2>
<p>This application interacts only with TikTok's official API (open.tiktokapis.com). No data is shared with any other third party.</p>
<h2>6. Contact</h2>
<p>For privacy requests, contact the operator of this service.</p>
</body></html>""")

@app.post("/api/jobs")
def create_job():
    job_id = f"voyance_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    JOBS[job_id] = make_job(job_id)
    return {"job_id": job_id}

@app.get("/api/jobs")
def list_jobs():
    return {"jobs": sorted(JOBS.values(), key=lambda x: x["created_at"], reverse=True)}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Job not found")
    return JOBS[job_id]

@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    JOBS.pop(job_id, None)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/run/{agent_name}")
def run_agent(job_id: str, agent_name: str, body: dict = Body(default={})):
    """Lance un agent spécifique. Le body peut contenir des overrides de params."""
    if job_id not in JOBS:
        raise HTTPException(404, "Job not found")
    if agent_name not in AGENT_ORDER:
        raise HTTPException(400, f"Unknown agent: {agent_name}")
    if JOBS[job_id]["agents"][agent_name]["status"] == "running":
        raise HTTPException(409, "Agent already running")

    job = JOBS[job_id]
    agents = job["agents"]

    # Construire les params automatiquement depuis les résultats précédents
    params: dict = {"job_id": job_id}

    if agent_name == "image_prompts":
        content = body.get("content") or (agents["content"].get("result") or {})
        params["content"] = content

    elif agent_name == "images":
        image_prompts = body.get("image_prompts") or (agents["image_prompts"].get("result") or {})
        params["image_prompts"] = image_prompts

    elif agent_name == "voice":
        content = body.get("content") or (agents["content"].get("result") or {})
        params["content"] = content

    elif agent_name == "video":
        params["images"] = body.get("images") or (agents["images"].get("result") or {})
        params["audio_segments"] = body.get("audio_segments") or (agents["voice"].get("result") or {})
        params["content"] = body.get("content") or (agents["content"].get("result") or {})

    # Merge any explicit overrides from body
    for k, v in body.items():
        if k not in params:
            params[k] = v

    thread = threading.Thread(
        target=run_agent_sync,
        args=(job_id, agent_name, params),
        daemon=True
    )
    thread.start()
    return {"ok": True, "agent": agent_name}


@app.post("/api/jobs/{job_id}/run-all")
def run_all(job_id: str):
    """Lance tous les agents en séquence dans un thread."""
    if job_id not in JOBS:
        raise HTTPException(404, "Job not found")

    def pipeline():
        os.environ["FAL_KEY"] = FAL_KEY
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from agents import agent_content, agent_image_prompts, agent_images, agent_voice, agent_video

        job = JOBS[job_id]
        JOBS[job_id]["status"] = "running"

        def upd(agent, status, result=None, error=None):
            update_agent(job_id, agent, status, result=result, error=error)

        try:
            upd("content", "running")
            content = agent_content.run()
            upd("content", "done", result=content)

            upd("image_prompts", "running")
            image_prompts = agent_image_prompts.run({"content": content})
            upd("image_prompts", "done", result=image_prompts)

            upd("images", "running")
            images_result = agent_images.run({"image_prompts": image_prompts, "job_id": job_id})
            upd("images", "done", result=images_result)

            upd("voice", "running")
            voice_result = agent_voice.run({"content": content, "job_id": job_id})
            upd("voice", "done", result=voice_result)

            upd("video", "running")
            video_result = agent_video.run({
                "job_id": job_id,
                "images": images_result,
                "audio_segments": voice_result,
                "content": content,
            })
            upd("video", "done", result=video_result)

            JOBS[job_id]["status"] = "done"
        except Exception as e:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = traceback.format_exc()
        JOBS[job_id]["updated_at"] = datetime.now().isoformat()

    thread = threading.Thread(target=pipeline, daemon=True)
    thread.start()
    return {"ok": True}


# ─── Pendule workflow routes ─────────────────────────────────────────────────

def pendule_run_agent_sync(job_id: str, agent_name: str, params: dict):
    os.environ["FAL_KEY"] = FAL_KEY
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from workflows.pendule import agent_image, agent_video
    AGENTS = {"image": agent_image, "video": agent_video}

    for a in PENDULE_AGENT_ORDER:
        if a not in PENDULE_JOBS[job_id]["agents"]:
            PENDULE_JOBS[job_id]["agents"][a] = {"status": "pending", "result": None, "error": None, "updated_at": None}

    PENDULE_JOBS[job_id]["agents"][agent_name]["status"] = "running"
    PENDULE_JOBS[job_id]["agents"][agent_name]["updated_at"] = datetime.now().isoformat()
    PENDULE_JOBS[job_id]["status"] = "running"
    PENDULE_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(PENDULE_JOBS_FILE, PENDULE_JOBS)

    try:
        result = AGENTS[agent_name].run(params)
        PENDULE_JOBS[job_id]["agents"][agent_name] = {
            "status": "done", "result": result,
            "error": None, "updated_at": datetime.now().isoformat()
        }
        all_done = all(PENDULE_JOBS[job_id]["agents"][a]["status"] == "done" for a in PENDULE_AGENT_ORDER)
        PENDULE_JOBS[job_id]["status"] = "done" if all_done else "idle"
    except Exception:
        err = traceback.format_exc()
        PENDULE_JOBS[job_id]["agents"][agent_name] = {
            "status": "error", "result": None,
            "error": err, "updated_at": datetime.now().isoformat()
        }
        PENDULE_JOBS[job_id]["status"] = "error"
    PENDULE_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(PENDULE_JOBS_FILE, PENDULE_JOBS)


@app.post("/api/pendule/jobs")
def pendule_create_job():
    job_id = f"pendule_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    PENDULE_JOBS[job_id] = {
        "id": job_id, "status": "idle",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "agents": {
            name: {"status": "pending", "result": None, "error": None, "updated_at": None}
            for name in PENDULE_AGENT_ORDER
        },
    }
    _save_store(PENDULE_JOBS_FILE, PENDULE_JOBS)
    return {"job_id": job_id}


@app.get("/api/pendule/jobs")
def pendule_list_jobs():
    return {"jobs": sorted(PENDULE_JOBS.values(), key=lambda x: x["created_at"], reverse=True)}


@app.get("/api/pendule/jobs/{job_id}")
def pendule_get_job(job_id: str):
    if job_id not in PENDULE_JOBS:
        raise HTTPException(404, "Job not found")
    return PENDULE_JOBS[job_id]


@app.post("/api/pendule/jobs/{job_id}/run/{agent_name}")
def pendule_run_agent(job_id: str, agent_name: str, body: dict = Body(default={})):
    if job_id not in PENDULE_JOBS:
        raise HTTPException(404, "Job not found")
    if agent_name not in PENDULE_AGENT_ORDER:
        raise HTTPException(400, f"Unknown agent: {agent_name}")

    job = PENDULE_JOBS[job_id]
    params = {"job_id": job_id}

    if agent_name == "video":
        image_result = job["agents"].get("image", {}).get("result") or {}
        params["image_path"] = body.get("image_path") or image_result.get("image_path")

    threading.Thread(target=pendule_run_agent_sync, args=(job_id, agent_name, params), daemon=True).start()
    return {"ok": True, "agent": agent_name}


# ─── Satisfying workflow routes ─────────────────────────────────────────────

SAT_AGENT_ORDER = ["concept", "image", "video", "publish"]
SAT_JOBS_FILE = DATA_DIR / "satisfying_jobs.json"
SAT_JOBS: dict[str, dict] = _load_store(SAT_JOBS_FILE)
_reset_running_jobs(SAT_JOBS)


def _sat_agent_run(job_id: str, agent_name: str):
    os.environ["FAL_KEY"] = FAL_KEY
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from workflows.satisfying import agent_concept, agent_image as sat_image, agent_video as sat_video, agent_publish as sat_publish
    SAGENTS = {"concept": agent_concept, "image": sat_image, "video": sat_video, "publish": sat_publish}

    for a in SAT_AGENT_ORDER:
        if a not in SAT_JOBS[job_id]["agents"]:
            SAT_JOBS[job_id]["agents"][a] = {"status": "pending", "result": None, "error": None}

    agents = SAT_JOBS[job_id]["agents"]
    params = {"job_id": job_id}
    if agent_name == "image":
        params["concept_result"] = agents["concept"].get("result") or {}
    elif agent_name == "video":
        params["concept_result"] = agents["concept"].get("result") or {}
        params["image_result"] = agents["image"].get("result") or {}
    elif agent_name == "publish":
        params["concept_result"] = agents["concept"].get("result") or {}
        params["visual_result"] = agents["video"].get("result") or {}

    SAT_JOBS[job_id]["agents"][agent_name]["status"] = "running"
    SAT_JOBS[job_id]["status"] = "running"
    SAT_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(SAT_JOBS_FILE, SAT_JOBS)

    try:
        result = SAGENTS[agent_name].run(params)
        SAT_JOBS[job_id]["agents"][agent_name] = {"status": "done", "result": result, "error": None}
        all_done = all(SAT_JOBS[job_id]["agents"][a]["status"] == "done" for a in SAT_AGENT_ORDER)
        SAT_JOBS[job_id]["status"] = "done" if all_done else "idle"
    except Exception:
        err = traceback.format_exc()
        SAT_JOBS[job_id]["agents"][agent_name] = {"status": "error", "result": None, "error": err}
        SAT_JOBS[job_id]["status"] = "error"
    SAT_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(SAT_JOBS_FILE, SAT_JOBS)


@app.post("/api/satisfying/jobs")
def sat_create_job():
    job_id = f"sat_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    SAT_JOBS[job_id] = {
        "id": job_id, "status": "idle",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "agents": {name: {"status": "pending", "result": None, "error": None} for name in SAT_AGENT_ORDER},
    }
    _save_store(SAT_JOBS_FILE, SAT_JOBS)
    return {"job_id": job_id}


@app.get("/api/satisfying/jobs")
def sat_list_jobs():
    return {"jobs": sorted(SAT_JOBS.values(), key=lambda x: x["created_at"], reverse=True)}


@app.get("/api/satisfying/jobs/{job_id}")
def sat_get_job(job_id: str):
    if job_id not in SAT_JOBS:
        raise HTTPException(404, "Job not found")
    return SAT_JOBS[job_id]


@app.post("/api/satisfying/jobs/{job_id}/run/{agent_name}")
def sat_run_agent(job_id: str, agent_name: str, body: dict = Body(default={})):
    if job_id not in SAT_JOBS:
        raise HTTPException(404, "Job not found")
    if agent_name not in SAT_AGENT_ORDER:
        raise HTTPException(400, f"Unknown agent: {agent_name}")
    threading.Thread(target=_sat_agent_run, args=(job_id, agent_name), daemon=True).start()
    return {"ok": True, "agent": agent_name}


@app.get("/tiktok-developers-site-verification.txt")
def tiktok_verification():
    return HTMLResponse("tiktok-developers-site-verification=2vB95qlwlu85BjwaIZGLeMVNo7y4VsFs")


@app.get("/tiktokRxUGHl4Ay0JfWDidYsuGbGDYrsQReOzh.txt")
def tiktok_verify_file():
    return HTMLResponse("tiktok-developers-site-verification=RxUGHl4Ay0JfWDidYsuGbGDYrsQReOzh")


@app.get("/tiktok8Wyxk9Nk49EIUDBoiN4Wtmjx80vAGsFH.txt")
def tiktok_url_ownership():
    return HTMLResponse("tiktok-developers-site-verification=8Wyxk9Nk49EIUDBoiN4Wtmjx80vAGsFH")


@app.get("/api/media")
def list_media():
    """Liste tous les fichiers médias générés (images + vidéos)."""
    import os
    from pathlib import Path
    dirs = [
        Path("/home/claude-user/tiktok-voyance/output/video_jobs"),
        Path("/home/claude-user/tiktok-voyance/output/prediction_jobs"),
        Path("/home/claude-user/tiktok-voyance/output"),
    ]
    files = []
    for d in dirs:
        if not d.exists():
            continue
        for f in sorted(d.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.suffix.lower() in (".mp4", ".jpg", ".jpeg", ".png", ".gif"):
                stat = f.stat()
                url = str(f).replace("/home/claude-user/tiktok-voyance", "")
                files.append({
                    "name": f.name,
                    "url": url,
                    "size_mb": round(stat.st_size / 1024 / 1024, 1),
                    "type": "video" if f.suffix == ".mp4" else "image",
                    "mtime": stat.st_mtime,
                })
    # Dédupliquer par nom
    seen = set()
    unique = []
    for f in files:
        if f["name"] not in seen:
            seen.add(f["name"])
            unique.append(f)
    return {"files": unique[:100]}


# ─── Histoire workflow routes ─────────────────────────────────────────────────

def _hist_run_agent(job_id: str, agent_name: str):
    os.environ["FAL_KEY"] = FAL_KEY
    os.environ["KIE_KEY"] = KIE_KEY
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from workflows.histoire import agent_topic, agent_research, agent_prompt as hist_prompt, agent_visual, agent_montage, agent_publish as hist_publish
    HAGENTS = {
        "topic":    agent_topic,
        "research": agent_research,
        "prompt":   hist_prompt,
        "visual":   agent_visual,
        "montage":  agent_montage,
        "publish":  hist_publish,
    }

    job = HIST_JOBS[job_id]
    agents = job["agents"]

    params = {"job_id": job_id}
    if agent_name == "research":
        params["topic_result"] = agents["topic"].get("result") or {}
    elif agent_name == "prompt":
        params["research_result"] = agents["research"].get("result") or {}
    elif agent_name == "visual":
        params["prompt_result"] = agents["prompt"].get("result") or {}
    elif agent_name == "montage":
        params["research_result"] = agents["research"].get("result") or {}
        params["visual_result"]   = agents["visual"].get("result") or {}
    elif agent_name == "publish":
        params["research_result"] = agents["research"].get("result") or {}
        params["montage_result"]  = agents["montage"].get("result") or {}

    for a in HIST_AGENT_ORDER:
        if a not in HIST_JOBS[job_id]["agents"]:
            HIST_JOBS[job_id]["agents"][a] = {"status": "pending", "result": None, "error": None}

    HIST_JOBS[job_id]["agents"][agent_name]["status"] = "running"
    HIST_JOBS[job_id]["status"] = "running"
    HIST_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(HIST_JOBS_FILE, HIST_JOBS)

    try:
        result = HAGENTS[agent_name].run(params)
        HIST_JOBS[job_id]["agents"][agent_name] = {"status": "done", "result": result, "error": None}
        all_done = all(HIST_JOBS[job_id]["agents"][a]["status"] == "done" for a in HIST_AGENT_ORDER)
        HIST_JOBS[job_id]["status"] = "done" if all_done else "idle"
    except Exception:
        err = traceback.format_exc()
        HIST_JOBS[job_id]["agents"][agent_name] = {"status": "error", "result": None, "error": err}
        HIST_JOBS[job_id]["status"] = "error"
    HIST_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(HIST_JOBS_FILE, HIST_JOBS)


@app.post("/api/histoire/jobs")
def hist_create_job():
    job_id = f"hist_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    HIST_JOBS[job_id] = {
        "id": job_id, "status": "idle",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "agents": {
            name: {"status": "pending", "result": None, "error": None}
            for name in HIST_AGENT_ORDER
        },
    }
    _save_store(HIST_JOBS_FILE, HIST_JOBS)
    return {"job_id": job_id}


@app.get("/api/histoire/jobs")
def hist_list_jobs():
    HIST_JOBS.update(_load_store(HIST_JOBS_FILE))
    return {"jobs": sorted(HIST_JOBS.values(), key=lambda x: x["created_at"], reverse=True)}


@app.get("/api/histoire/jobs/{job_id}")
def hist_get_job(job_id: str):
    HIST_JOBS.update(_load_store(HIST_JOBS_FILE))
    if job_id not in HIST_JOBS:
        raise HTTPException(404, "Job not found")
    return HIST_JOBS[job_id]


@app.post("/api/histoire/jobs/{job_id}/run/{agent_name}")
def hist_run_agent(job_id: str, agent_name: str):
    if job_id not in HIST_JOBS:
        raise HTTPException(404, "Job not found")
    if agent_name not in HIST_AGENT_ORDER:
        raise HTTPException(400, f"Unknown agent: {agent_name}")
    threading.Thread(target=_hist_run_agent, args=(job_id, agent_name), daemon=True).start()
    return {"ok": True, "agent": agent_name}


@app.post("/api/histoire/cron")
def hist_cron():
    """Lance le pipeline histoire complet automatiquement."""
    def full_pipeline():
        os.environ["FAL_KEY"] = FAL_KEY
        os.environ["KIE_KEY"] = KIE_KEY
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from workflows.histoire import agent_topic, agent_research, agent_prompt as hist_prompt, agent_visual, agent_montage, agent_publish as hist_publish

        job_id = f"hist_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        HIST_JOBS[job_id] = {
            "id": job_id, "status": "running",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "agents": {
                name: {"status": "pending", "result": None, "error": None}
                for name in HIST_AGENT_ORDER
            },
        }
        _save_store(HIST_JOBS_FILE, HIST_JOBS)

        steps = [
            ("topic",    lambda r: {"job_id": job_id}),
            ("research", lambda r: {"job_id": job_id, "topic_result": r["topic"]}),
            ("prompt",   lambda r: {"job_id": job_id, "research_result": r["research"]}),
            ("visual",   lambda r: {"job_id": job_id, "prompt_result": r["prompt"]}),
            ("montage",  lambda r: {"job_id": job_id, "research_result": r["research"], "visual_result": r["visual"]}),
            ("publish",  lambda r: {"job_id": job_id, "research_result": r["research"], "montage_result": r["montage"]}),
        ]
        agents_map = {
            "topic":    agent_topic,
            "research": agent_research,
            "prompt":   hist_prompt,
            "visual":   agent_visual,
            "montage":  agent_montage,
            "publish":  hist_publish,
        }

        results = {}
        for agent_name, build_params in steps:
            HIST_JOBS[job_id]["agents"][agent_name]["status"] = "running"
            HIST_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
            _save_store(HIST_JOBS_FILE, HIST_JOBS)
            try:
                result = agents_map[agent_name].run(build_params(results))
                results[agent_name] = result
                HIST_JOBS[job_id]["agents"][agent_name] = {"status": "done", "result": result, "error": None}
            except Exception:
                err = traceback.format_exc()
                HIST_JOBS[job_id]["agents"][agent_name] = {"status": "error", "result": None, "error": err}
                HIST_JOBS[job_id]["status"] = "error"
                HIST_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
                _save_store(HIST_JOBS_FILE, HIST_JOBS)
                return

        HIST_JOBS[job_id]["status"] = "done"
        HIST_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
        _save_store(HIST_JOBS_FILE, HIST_JOBS)

    threading.Thread(target=full_pipeline, daemon=True).start()
    return {"ok": True, "message": "Pipeline histoire lancé"}


# ─── Histoire 2 workflow routes ───────────────────────────────────────────────

def _hist2_run_agent(job_id: str, agent_name: str):
    os.environ["FAL_KEY"] = FAL_KEY
    os.environ["KIE_KEY"] = KIE_KEY
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from workflows.histoire2 import agent_topic as hist2_topic, agent_research as hist2_research, agent_prompt as hist2_prompt, agent_visual as hist2_visual, agent_montage as hist2_montage
    HAGENTS = {
        "topic":    hist2_topic,
        "research": hist2_research,
        "prompt":   hist2_prompt,
        "visual":   hist2_visual,
        "montage":  hist2_montage,
    }

    for a in HIST2_AGENT_ORDER:
        if a not in HIST2_JOBS[job_id]["agents"]:
            HIST2_JOBS[job_id]["agents"][a] = {"status": "pending", "result": None, "error": None}

    HIST2_JOBS[job_id]["agents"][agent_name]["status"] = "running"
    HIST2_JOBS[job_id]["status"] = "running"
    HIST2_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(HIST2_JOBS_FILE, HIST2_JOBS)

    agents = HIST2_JOBS[job_id]["agents"]
    params = {"job_id": job_id}
    if agent_name == "research":
        params["topic_result"] = agents["topic"].get("result") or {}
    elif agent_name == "prompt":
        params["research_result"] = agents["research"].get("result") or {}
    elif agent_name == "visual":
        params["prompt_result"] = agents["prompt"].get("result") or {}
    elif agent_name == "montage":
        params["visual_result"]   = agents["visual"].get("result") or {}
        params["research_result"] = agents["research"].get("result") or {}

    try:
        result = HAGENTS[agent_name].run(params)
        HIST2_JOBS[job_id]["agents"][agent_name] = {"status": "done", "result": result, "error": None}
        all_done = all(HIST2_JOBS[job_id]["agents"][a]["status"] == "done" for a in HIST2_AGENT_ORDER)
        HIST2_JOBS[job_id]["status"] = "done" if all_done else "idle"
    except Exception:
        err = traceback.format_exc()
        HIST2_JOBS[job_id]["agents"][agent_name] = {"status": "error", "result": None, "error": err}
        HIST2_JOBS[job_id]["status"] = "error"
    HIST2_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(HIST2_JOBS_FILE, HIST2_JOBS)


@app.post("/api/histoire2/jobs")
def hist2_create_job():
    job_id = f"hist2_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    HIST2_JOBS[job_id] = {
        "id": job_id, "status": "idle",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "agents": {
            name: {"status": "pending", "result": None, "error": None}
            for name in HIST2_AGENT_ORDER
        },
    }
    _save_store(HIST2_JOBS_FILE, HIST2_JOBS)
    return {"job_id": job_id}


@app.get("/api/histoire2/jobs")
def hist2_list_jobs():
    HIST2_JOBS.update(_load_store(HIST2_JOBS_FILE))
    return {"jobs": sorted(HIST2_JOBS.values(), key=lambda x: x["created_at"], reverse=True)}


@app.get("/api/histoire2/jobs/{job_id}")
def hist2_get_job(job_id: str):
    HIST2_JOBS.update(_load_store(HIST2_JOBS_FILE))
    if job_id not in HIST2_JOBS:
        raise HTTPException(404, "Job not found")
    return HIST2_JOBS[job_id]


@app.patch("/api/histoire2/jobs/{job_id}/select-event")
def hist2_select_event(job_id: str, body: dict = Body(default={})):
    """Change l'événement sélectionné dans le résultat du topic sans relancer l'agent."""
    HIST2_JOBS.update(_load_store(HIST2_JOBS_FILE))
    if job_id not in HIST2_JOBS:
        raise HTTPException(404, "Job not found")
    event = body.get("event")
    if not event:
        raise HTTPException(400, "event manquant")
    topic_result = HIST2_JOBS[job_id]["agents"]["topic"].get("result") or {}
    # Recalcule titre, description, date depuis le nouvel event
    topic_result["selected_event"] = event
    topic_result["titre"]       = event.get("title", "")
    topic_result["description"] = event.get("hook", "")
    topic_result["date"]        = event.get("exact_date", f"{event.get('year','')}")
    HIST2_JOBS[job_id]["agents"]["topic"]["result"] = topic_result
    HIST2_JOBS[job_id]["updated_at"] = datetime.now().isoformat()
    _save_store(HIST2_JOBS_FILE, HIST2_JOBS)
    return {"ok": True, "selected": event.get("title")}


@app.post("/api/histoire2/jobs/{job_id}/run/{agent_name}")
def hist2_run_agent(job_id: str, agent_name: str):
    if job_id not in HIST2_JOBS:
        raise HTTPException(404, "Job not found")
    if agent_name not in HIST2_AGENT_ORDER:
        raise HTTPException(400, f"Unknown agent: {agent_name}")
    threading.Thread(target=_hist2_run_agent, args=(job_id, agent_name), daemon=True).start()
    return {"ok": True, "agent": agent_name}
