"""Agent 4 — Génère la vidéo 10s via Runway (kie.ai)"""
import os
import time
import httpx
from pathlib import Path

KIE_KEY = os.environ.get("KIE_KEY", "")
OUTPUT_DIR = Path("/home/claude-user/tiktok-voyance/output/histoire2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

KIE_BASE = "https://api.kie.ai/api/v1/runway"


def generate_video(runway_prompt: str, job_id: str) -> tuple[str, str]:
    if not KIE_KEY:
        raise RuntimeError("KIE_KEY manquant — ajoute KIE_KEY dans le .env")

    headers = {
        "Authorization": f"Bearer {KIE_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": runway_prompt,
        "duration": 10,
        "quality": "720p",
        "aspectRatio": "9:16",
        "waterMark": "",
    }

    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{KIE_BASE}/generate", headers=headers, json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"Runway submit error {r.status_code}: {r.text[:300]}")
        result = r.json()
        if result.get("code") != 200:
            raise RuntimeError(f"Runway API error: {result.get('msg', 'Unknown')}")
        task_id = result["data"]["taskId"]

    # Poll toutes les 15s, max 15 minutes (60 attempts) — 10s prend plus longtemps
    poll_headers = {"Authorization": f"Bearer {KIE_KEY}"}
    for attempt in range(60):
        time.sleep(15)
        with httpx.Client(timeout=30.0) as client:
            poll = client.get(
                f"{KIE_BASE}/record-detail?taskId={task_id}",
                headers=poll_headers,
            )
            if poll.status_code != 200:
                continue
            pd = poll.json()
            if pd.get("code") != 200:
                continue
            task_data = pd["data"]
            state = task_data.get("state")

            if state == "success":
                video_url = task_data["videoInfo"]["videoUrl"]
                with httpx.Client(timeout=120.0) as dl:
                    vid_r = dl.get(video_url)
                out_path = OUTPUT_DIR / f"{job_id}_raw.mp4"
                out_path.write_bytes(vid_r.content)
                public_url = str(out_path).replace(
                    "/home/claude-user/tiktok-voyance", ""
                )
                return str(out_path), public_url

            elif state == "fail":
                raise RuntimeError(f"Runway generation failed: {task_data.get('failMsg', 'unknown')}")

    raise RuntimeError("Timeout — génération Runway > 15 minutes")


def run(params: dict) -> dict:
    job_id = params.get("job_id", "hist2")
    prompt_result = params.get("prompt_result", {})

    runway_prompt = prompt_result.get("runway_prompt", "")
    if not runway_prompt:
        raise RuntimeError("Prompt manquant — lance d'abord l'agent Prompt")

    video_path, video_url = generate_video(runway_prompt, job_id)

    return {
        "video_path":         video_path,
        "video_url":          video_url,
        "runway_prompt_used": runway_prompt,
        "duration":           10,
    }
