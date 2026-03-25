"""Agent 3 — Anime l'image avec Kling 2.5 Turbo"""
import os
import time
import httpx
from pathlib import Path

FAL_KEY = os.environ.get("FAL_KEY", "")
OUTPUT_DIR = Path("/home/claude-user/tiktok-voyance/output/satisfying")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run(params: dict) -> dict:
    job_id = params.get("job_id", "sat")
    concept_result = params.get("concept_result", {})
    image_result = params.get("image_result", {})

    motion_prompt = concept_result.get("video_motion_prompt", "slow satisfying movement, smooth loop")
    image_url = image_result.get("image_url", "")

    if not image_url:
        raise RuntimeError("image_url manquant — lance d'abord l'agent Image")

    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": motion_prompt,
        "image_url": image_url,
        "duration": 5,
    }

    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            "https://queue.fal.run/fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
            headers=headers, json=payload
        )
        if r.status_code != 200:
            raise RuntimeError(f"Kling submit error {r.status_code}: {r.text[:300]}")
        result_url = r.json().get("response_url")

        for _ in range(60):
            time.sleep(5)
            poll = client.get(result_url, headers=headers)
            if poll.status_code == 200:
                pd = poll.json()
                videos = pd.get("video") or pd.get("videos")
                if videos:
                    video_url = videos["url"] if isinstance(videos, dict) else videos[0]["url"]
                    vid_r = client.get(video_url, timeout=120.0)
                    out_path = OUTPUT_DIR / f"{job_id}_video.mp4"
                    out_path.write_bytes(vid_r.content)
                    public_url = str(out_path).replace("/home/claude-user/tiktok-voyance", "https://factorytiktok.duckdns.org")
                    return {"video_path": str(out_path), "video_url": public_url}
                if pd.get("error"):
                    raise RuntimeError(f"Kling error: {pd['error']}")
        raise RuntimeError("Timeout vidéo Kling")
