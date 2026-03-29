"""Agent 2 — Génère l'image via Flux Pro Ultra"""
import os
import time
import httpx
from pathlib import Path

FAL_KEY = os.environ.get("FAL_KEY", "")
OUTPUT_DIR = Path("/home/claude-user/tiktok-factory/output/satisfying")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run(params: dict) -> dict:
    job_id = params.get("job_id", "sat")
    concept_result = params.get("concept_result", {})
    image_prompt = concept_result.get("image_prompt", "colorful kinetic sand macro photography")

    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": image_prompt + ", no text, no watermark, no people",
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
                    path = OUTPUT_DIR / f"{job_id}_frame.jpg"
                    path.write_bytes(img_r.content)
                    image_url = str(path).replace("/home/claude-user/tiktok-factory", "https://factorytiktok.duckdns.org")
                    return {"image_path": str(path), "image_url": image_url}
                if pd.get("error"):
                    raise RuntimeError(f"Flux error: {pd['error']}")
        raise RuntimeError("Timeout image generation")
