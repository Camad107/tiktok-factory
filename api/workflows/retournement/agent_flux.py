"""Agent — Génération images via Flux Kontext (kie.ai) en chaîne"""
import time
import random
import httpx
from pathlib import Path

KIE_API_KEY = "1839ebc2fecc9b2ba957b4b211b390bd"
KIE_BASE = "https://api.kie.ai"
KIE_UPLOAD_BASE = "https://kieai.redpandaai.co"
OUTPUT_DIR = Path("/home/claude-user/tiktok-voyance/output/retournement")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://factorytiktok.duckdns.org"


def _upload_image(client: httpx.Client, image_path: str) -> str:
    """Upload une image locale sur kieai.redpandaai.co et retourne l'URL publique."""
    with open(image_path, "rb") as f:
        r = client.post(
            f"{KIE_UPLOAD_BASE}/api/file-stream-upload",
            headers={"Authorization": f"Bearer {KIE_API_KEY}"},
            files={"file": (Path(image_path).name, f, "image/jpeg")},
            data={"uploadPath": "retournement"},
            timeout=60,
        )
    if r.status_code != 200:
        raise RuntimeError(f"Kie upload error {r.status_code}: {r.text}")
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"Kie upload failed: {data}")
    return data["data"]["downloadUrl"]


def _create_task(client: httpx.Client, image_path: str, prompt: str) -> str:
    """Upload l'image puis soumet une tâche Flux Kontext."""
    image_url = _upload_image(client, image_path)

    r = client.post(
        f"{KIE_BASE}/api/v1/flux/kontext/generate",
        headers={"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"},
        json={
            "prompt": prompt,
            "inputImage": image_url,
            "aspectRatio": "9:16",
            "outputFormat": "jpeg",
            "model": "flux-kontext-pro",
            "promptUpsampling": False,
            "enableTranslation": False,
            "safetyTolerance": 2,
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Flux Kontext createTask error {r.status_code}: {r.text}")
    data = r.json()
    if data.get("code") != 200:
        raise RuntimeError(f"Flux Kontext createTask failed: {data}")
    task_id = data.get("data", {}).get("taskId")
    if not task_id:
        raise RuntimeError(f"No taskId in response: {data}")
    return task_id


def _poll_task(client: httpx.Client, task_id: str, max_wait: int = 600) -> str:
    """Attend la complétion et retourne l'URL de l'image générée."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        time.sleep(5)
        r = client.get(
            f"{KIE_BASE}/api/v1/flux/kontext/record-info",
            headers={"Authorization": f"Bearer {KIE_API_KEY}"},
            params={"taskId": task_id},
            timeout=30,
        )
        if r.status_code != 200:
            continue
        data = r.json()
        if data.get("code") != 200:
            continue
        record = data.get("data", {})

        # successFlag=1 = terminé avec succès
        if record.get("successFlag") == 1:
            url = record.get("response", {}).get("resultImageUrl")
            if url:
                return url
            raise RuntimeError(f"Flux Kontext success but no resultImageUrl: {record}")

        if record.get("errorCode") or record.get("errorMessage"):
            raise RuntimeError(f"Flux Kontext task failed: {record.get('errorMessage', record)}")

    raise RuntimeError(f"Timeout polling task {task_id} after {max_wait}s")


def _download_image(client: httpx.Client, url: str, dest_path: Path) -> str:
    """Télécharge et sauvegarde l'image localement."""
    r = client.get(url, timeout=60, follow_redirects=True)
    r.raise_for_status()
    dest_path.write_bytes(r.content)
    return str(dest_path)


def _call_flux(client: httpx.Client, input_path: str, prompt: str, output_path: Path) -> str:
    """Lance une tâche Flux Kontext, attend le résultat, télécharge et retourne le chemin local."""
    task_id = _create_task(client, input_path, prompt)
    image_url = _poll_task(client, task_id)
    return _download_image(client, image_url, output_path)


def run(params: dict) -> dict:
    content = params.get("content", {})
    sources_dir = params.get("sources_dir", "/home/claude-user/tiktok-voyance/output/retournement_sources")
    job_id = content.get("_job_id", params.get("job_id", "ret_unknown"))

    # Choisir une photo source aléatoire
    sources_path = Path(sources_dir)
    sources = list(sources_path.glob("*.jpg")) + list(sources_path.glob("*.jpeg")) + list(sources_path.glob("*.png"))
    if not sources:
        raise RuntimeError(f"Aucune photo source dans {sources_dir} — uploadez des photos dans les Réglages")

    seed = content.get("_seed", 0)
    source_path = str(random.Random(seed).choice(sources))

    prompts_data = params.get("prompts", {})
    prompt_A = prompts_data.get("prompt_A", "")
    prompt_B = prompts_data.get("prompt_B", "")
    prompt_C = prompts_data.get("prompt_C", "")

    if not prompt_A or not prompt_B or not prompt_C:
        cartes = content.get("cartes", [])
        if len(cartes) < 3:
            raise RuntimeError("Contenu invalide — 3 cartes requises et agent prompts manquant")
        nom_1 = cartes[0].get("nom", "une carte de tarot")
        nom_2 = cartes[1].get("nom", "une carte de tarot")
        nom_3 = cartes[2].get("nom", "une carte de tarot")
        prompt_A = f"Flip only the left card to reveal '{nom_1}'. Keep everything else exactly the same."
        prompt_B = f"Flip only the center card to reveal '{nom_2}'. Keep everything else exactly the same."
        prompt_C = f"Flip only the right card to reveal '{nom_3}'. Keep everything else exactly the same."

    # step = "A" | "B" | "C" | "all" (défaut)
    step = params.get("step", "all").upper()

    path_A = OUTPUT_DIR / f"{job_id}_A.jpg"
    path_B = OUTPUT_DIR / f"{job_id}_B.jpg"
    path_C = OUTPUT_DIR / f"{job_id}_C.jpg"

    def to_url(p: str) -> str:
        return p.replace("/home/claude-user/tiktok-voyance", BASE_URL)

    existing = params.get("flux", {})

    with httpx.Client() as client:
        if step in ("A", "all"):
            local_A = _call_flux(client, source_path, prompt_A, path_A)
        else:
            local_A = existing.get("image_A_path") or str(path_A)

        if step in ("B", "all"):
            if not Path(local_A).exists():
                raise RuntimeError(f"Image A introuvable ({local_A}) — générez d'abord l'image A")
            local_B = _call_flux(client, local_A, prompt_B, path_B)
        else:
            local_B = existing.get("image_B_path") or str(path_B)

        if step in ("C", "all"):
            if not Path(local_B).exists():
                raise RuntimeError(f"Image B introuvable ({local_B}) — générez d'abord l'image B")
            local_C = _call_flux(client, local_B, prompt_C, path_C)
        else:
            local_C = existing.get("image_C_path") or str(path_C)

    result = {
        "source_path": source_path,
        "source_url": to_url(source_path),
        "step": step,
    }
    if path_A.exists():
        result["image_A_path"] = local_A
        result["image_A_url"] = to_url(local_A)
    if path_B.exists():
        result["image_B_path"] = local_B
        result["image_B_url"] = to_url(local_B)
    if path_C.exists():
        result["image_C_path"] = local_C
        result["image_C_url"] = to_url(local_C)
    return result
