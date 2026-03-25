"""Agent 2 — Génère l'image Flux Pro Ultra puis la vidéo Kling 2.5 Turbo"""
import os
import time
import httpx
from pathlib import Path

FAL_KEY = os.environ.get("FAL_KEY", "")
OUTPUT_DIR = Path("/home/claude-user/tiktok-voyance/output/satisfying")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_image(prompt: str) -> bytes:
    """Génère une image photoréaliste via Flux Pro Ultra."""
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt + ", no text, no watermark, no people",
        "image_size": "portrait_4_3",
        "output_format": "jpeg",
        "safety_tolerance": "2",
    }

    with httpx.Client(timeout=30.0) as client:
        r = client.post("https://queue.fal.run/fal-ai/flux-pro/v1.1-ultra", headers=headers, json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"Flux submit error {r.status_code}: {r.text[:200]}")

        result_url = r.json().get("response_url")
        for _ in range(40):
            time.sleep(3)
            poll = client.get(result_url, headers=headers)
            if poll.status_code == 200:
                pd = poll.json()
                imgs = pd.get("images")
                if imgs:
                    img_r = client.get(imgs[0]["url"], timeout=60.0)
                    return img_r.content
                if pd.get("error"):
                    raise RuntimeError(f"Flux error: {pd['error']}")
        raise RuntimeError("Timeout image generation")


def upload_image(img_bytes: bytes, job_id: str) -> str:
    """Sauvegarde l'image et retourne son URL publique."""
    path = OUTPUT_DIR / f"{job_id}_frame.jpg"
    path.write_bytes(img_bytes)
    return str(path).replace("/home/claude-user/tiktok-voyance", "https://factorytiktok.duckdns.org")


def generate_video(image_url: str, motion_prompt: str, job_id: str) -> str:
    """Anime l'image avec Kling 2.5 Turbo."""
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
                    return str(out_path)
                if pd.get("error"):
                    raise RuntimeError(f"Kling error: {pd['error']}")
        raise RuntimeError("Timeout vidéo Kling")


def run(params: dict) -> dict:
    job_id = params.get("job_id", "sat")
    concept_result = params.get("concept_result", {})

    image_prompt = concept_result.get("image_prompt", "colorful kinetic sand macro photography")
    motion_prompt = concept_result.get("video_motion_prompt", "slow satisfying movement, smooth loop")

    # Génère l'image
    img_bytes = generate_image(image_prompt)
    image_url = upload_image(img_bytes, job_id)

    # Anime avec Kling
    video_path = generate_video(image_url, motion_prompt, job_id)
    video_url = video_path.replace("/home/claude-user/tiktok-voyance", "https://factorytiktok.duckdns.org")

    return {
        "image_url": image_url,
        "video_path": video_path,
        "video_url": video_url,
    }
