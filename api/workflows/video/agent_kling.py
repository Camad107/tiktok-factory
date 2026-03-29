"""Agent Vidéo — Génère une vidéo avec Kling O3 (first frame → last frame)"""
import os
import time
import httpx
from pathlib import Path

FAL_KEY = os.environ.get("FAL_KEY", "")
OUTPUT_DIR = Path("/home/claude-user/tiktok-factory/output/video_jobs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run(params: dict) -> dict:
    first_frame_url = params["first_frame_url"]
    last_frame_url = params["last_frame_url"]
    prompt = params.get("prompt", "hands slowly shuffling and revealing a tarot card on a wooden table, smooth cinematic motion")
    duration = params.get("duration", 5)
    job_id = params.get("job_id", "video")

    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt,
        "image_url": first_frame_url,
        "end_image_url": last_frame_url,
        "duration": duration,
        "aspect_ratio": "9:16",
    }

    with httpx.Client(timeout=30.0) as client:
        r = client.post("https://queue.fal.run/fal-ai/kling-video/o3/standard/image-to-video",
                        headers=headers, json=payload)
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
                    # Download
                    vid_r = client.get(video_url, timeout=120.0)
                    out_path = OUTPUT_DIR / f"{job_id}.mp4"
                    out_path.write_bytes(vid_r.content)
                    return {
                        "video_url": video_url,
                        "video_path": str(out_path),
                        "duration": duration,
                    }
                if pd.get("error"):
                    raise RuntimeError(f"Kling error: {pd['error']}")
        raise RuntimeError("Timeout vidéo Kling")
