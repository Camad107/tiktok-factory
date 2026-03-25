"""Agent 2 — Génère la vidéo Kling (first frame → last frame selon la carte)"""
import os
import time
import httpx
import subprocess
from pathlib import Path

FAL_KEY = os.environ.get("FAL_KEY", "")
OUTPUT_DIR = Path("/home/claude-user/tiktok-voyance/output/video_jobs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://factorytiktok.duckdns.org"
W, H = 1024, 1536  # Format natif des images


def run(params: dict) -> dict:
    job_id = params.get("job_id", "video")
    question_result = params.get("question_result", {})
    card = question_result.get("card", {})
    card_id = card.get("id", "lune")

    # Get first frame URL (global setting)
    first_frame_url = params.get("first_frame_url", "")
    if not first_frame_url:
        raise RuntimeError("Premier frame manquant — configure-le dans les réglages")

    # Get last frame URL for this card
    last_frame_url = params.get("last_frames", {}).get(card_id, "")
    if not last_frame_url:
        raise RuntimeError(f"Dernier frame manquant pour la carte '{card_id}' — uploade-la dans les réglages")

    outcome = question_result.get("outcome", "neutral")
    prompt = (
        f"overhead top-down cinematic shot, static camera, no zoom, no camera movement, "
        f"a real human feminine hand with natural skin texture, visible knuckles, natural nails, lifelike and photorealistic, enters the frame, "
        f"picks up the tarot card and performs a complete full flip revealing the {card.get('name','tarot card')} entirely face up, "
        f"the card must be fully turned over in one smooth complete motion showing the entire front face of the card, "
        f"then the hand gracefully slides out of the frame leaving only the card fully face up on the table, "
        f"smooth fluid motion, warm atmospheric lighting, elegant and mysterious, fixed top-down angle throughout, "
        f"hyperrealistic hand, natural human skin, not CGI, not illustrated"
    )

    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt,
        "image_url": first_frame_url,
        "end_image_url": last_frame_url,
        "duration": 5,
    }

    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            "https://queue.fal.run/fal-ai/kling-video/o3/standard/image-to-video",
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
                    out_path = OUTPUT_DIR / f"{job_id}_clip.mp4"
                    out_path.write_bytes(vid_r.content)
                    return {
                        "video_url": video_url,
                        "video_path": str(out_path),
                        "card_id": card_id,
                        "outcome": outcome,
                    }
                if pd.get("error"):
                    raise RuntimeError(f"Kling error: {pd['error']}")
        raise RuntimeError("Timeout vidéo Kling")
