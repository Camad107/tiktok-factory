"""Agent 1 — Génère l'image du pendule via Fal.ai Flux Pro"""
import os
import time
import httpx
from pathlib import Path

FAL_KEY = os.environ.get("FAL_KEY", "")
OUTPUT_DIR = Path("/home/claude-user/tiktok-voyance/output/pendule")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = (
    "a single mystical crystal pendulum hanging on a thin gold chain, "
    "pure black background, the crystal ball glows softly with an inner violet light, "
    "chain extends from top center, photorealistic, dramatic lighting, "
    "centered composition, vertical orientation, no text, no letters, no words, "
    "high detail, professional photography, dark moody atmosphere"
)


def fetch_image_flux_pro(prompt: str) -> bytes:
    """Soumet à Fal.ai Flux Pro via queue et attend le résultat."""
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt,
        "image_size": "portrait_4_3",
        "num_inference_steps": 28,
        "guidance_scale": 3.5,
        "num_images": 1,
        "safety_tolerance": "2",
    }

    with httpx.Client(timeout=60.0) as client:
        # Essai Flux Pro d'abord, fallback sur flux/dev si indisponible
        for model in ["fal-ai/flux-pro", "fal-ai/flux/dev"]:
            try:
                r = client.post(
                    f"https://queue.fal.run/{model}",
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )
                if r.status_code != 200:
                    continue

                result_url = r.json().get("response_url")
                if not result_url:
                    continue

                for _ in range(60):
                    time.sleep(3)
                    poll = client.get(result_url, headers=headers, timeout=30.0)
                    if poll.status_code == 200:
                        pd = poll.json()
                        imgs = pd.get("images")
                        if imgs:
                            img_r = client.get(imgs[0]["url"], timeout=60.0)
                            return img_r.content
                        if pd.get("error"):
                            raise RuntimeError(f"Fal error: {pd['error']}")
                raise RuntimeError(f"Timeout sur {model}")

            except RuntimeError:
                raise
            except Exception as e:
                # Essayer le modèle suivant
                last_error = e
                continue

        raise RuntimeError(f"Tous les modèles ont échoué: {last_error}")


def run(params: dict) -> dict:
    job_id = params.get("job_id", "default")

    img_bytes = fetch_image_flux_pro(PROMPT)

    out_path = OUTPUT_DIR / f"{job_id}_pendule.jpg"
    out_path.write_bytes(img_bytes)

    return {
        "image_path": str(out_path),
        "image_url": f"/output/pendule/{job_id}_pendule.jpg",
    }
