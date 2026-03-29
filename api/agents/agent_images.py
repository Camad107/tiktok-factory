"""Agent 3 — Génère les images via Fal.ai queue (contourne la limite concurrent)"""
import os
import time
import httpx
import traceback
from pathlib import Path

FAL_KEY = os.environ.get("FAL_KEY", "")
OUTPUT_DIR = Path("/home/claude-user/tiktok-factory/output/images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_image(prompt: str, filename: str) -> str:
    """Soumet via queue Fal.ai, poll jusqu'au résultat."""
    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "image_size": "portrait_4_3",
        "num_inference_steps": 4,
        "num_images": 1,
    }

    with httpx.Client(timeout=30.0) as client:
        # Soumettre en queue
        r = client.post(
            "https://queue.fal.run/fal-ai/flux/schnell",
            headers=headers,
            json=payload,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Submit error {r.status_code}: {r.text[:200]}")

        data = r.json()
        result_url = data.get("response_url")
        if not result_url:
            raise RuntimeError(f"No response_url: {data}")

        # Poll jusqu'au résultat (max 120s)
        for _ in range(40):
            time.sleep(3)
            poll = client.get(result_url, headers=headers)
            if poll.status_code != 200:
                continue
            pd = poll.json()
            images = pd.get("images")
            if images:
                image_url = images[0]["url"]
                img_resp = client.get(image_url, timeout=60.0)
                filepath = OUTPUT_DIR / filename
                filepath.write_bytes(img_resp.content)
                return str(filepath)
            # Si erreur explicite
            if pd.get("error"):
                raise RuntimeError(f"Fal.ai error: {pd['error']}")

        raise RuntimeError("Timeout: image non générée après 120s")


def run(params: dict) -> dict:
    prompts = params.get("image_prompts", {})
    job_id = params.get("job_id", "default")

    tasks = []
    if prompts.get("cover_prompt"):
        tasks.append(("cover", prompts["cover_prompt"], f"{job_id}_cover.jpg"))
    for cp in prompts.get("card_prompts", []):
        tasks.append((f"card{cp['number']}", cp["prompt"], f"{job_id}_card{cp['number']}.jpg"))

    output = {}
    for key, prompt, filename in tasks:
        try:
            output[key] = generate_image(prompt, filename)
        except Exception:
            raise RuntimeError(f"Image '{key}' failed:\n{traceback.format_exc()}")

    return {"images": output}
