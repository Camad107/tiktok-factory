"""Agent 3 — Génère la voix via ElevenLabs (kie.ai)"""
import json
import subprocess
import time
import httpx
from pathlib import Path

OUTPUT_DIR = Path("/home/claude-user/tiktok-voyance/output/retournement")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

KIE_API_KEY = "1839ebc2fecc9b2ba957b4b211b390bd"
KIE_BASE = "https://api.kie.ai"

# Voix féminine mystérieuse
DEFAULT_VOICE_ID = "5l5f8iK3YPeGga21rQIX"  # Adeline - Feminine and Conversational
DEFAULT_MODEL = "elevenlabs/text-to-speech-multilingual-v2"

DEFAULT_VOICE_SETTINGS = {
    "stability": 0.55,
    "similarity_boost": 0.70,
    "style": 0.25,
    "speed": 0.82,
}


def _get_audio_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
        capture_output=True, text=True,
    )
    try:
        probe = json.loads(result.stdout)
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "audio":
                return float(stream.get("duration", 0))
    except Exception:
        pass
    return 0.0


def run(params: dict) -> dict:
    content = params.get("content", {})
    job_id = content.get("_job_id", params.get("job_id", "ret_unknown"))

    voice_id = params.get("elevenlabs_voice_id") or DEFAULT_VOICE_ID
    model_id = params.get("elevenlabs_model") or DEFAULT_MODEL

    script = content.get("script_complet", "")
    if not script:
        raise RuntimeError("Script voix manquant — lancez d'abord l'agent Contenu")

    preview = params.get("preview", False)
    if preview:
        first = script.split(".")[0].strip()
        script = first + "." if first else script[:120]

    # Convertir [PAUSE] en balise SSML break (silence 1s)
    script = script.replace("[PAUSE]", '<break time="2.2s"/>')

    suffix = "_voice_preview.mp3" if preview else "_voice.mp3"
    output_path = OUTPUT_DIR / f"{job_id}{suffix}"

    with httpx.Client(timeout=120) as client:
        # Créer la tâche TTS
        r = client.post(
            f"{KIE_BASE}/api/v1/jobs/createTask",
            headers={"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": model_id,
                "input": {
                    "text": script,
                    "voice": voice_id,
                    **DEFAULT_VOICE_SETTINGS,
                },
            },
        )
        if r.status_code != 200:
            raise RuntimeError(f"KIE TTS createTask error {r.status_code}: {r.text}")
        data = r.json()
        if data.get("code") != 200:
            raise RuntimeError(f"KIE TTS createTask failed: {data}")
        task_id = data["data"]["taskId"]

        # Poller jusqu'au résultat
        deadline = time.time() + 120
        audio_url = None
        while time.time() < deadline:
            time.sleep(4)
            r = client.get(
                f"{KIE_BASE}/api/v1/jobs/recordInfo",
                headers={"Authorization": f"Bearer {KIE_API_KEY}"},
                params={"taskId": task_id},
                timeout=30,
            )
            if r.status_code != 200:
                continue
            poll = r.json()
            if poll.get("code") != 200:
                continue
            record = poll.get("data", {})
            state = record.get("state", "")
            if state == "success":
                result_json = record.get("resultJson", "")
                result = json.loads(result_json)
                urls = result.get("resultUrls", [])
                if urls:
                    audio_url = urls[0]
                    break
                raise RuntimeError(f"TTS success but no URL: {record}")
            if state == "fail":
                raise RuntimeError(f"TTS task failed: {record.get('failMsg', record)}")

        if not audio_url:
            raise RuntimeError(f"TTS timeout après 120s (taskId: {task_id})")

        # Télécharger l'audio
        r = client.get(audio_url, timeout=60, follow_redirects=True)
        r.raise_for_status()
        output_path.write_bytes(r.content)

    duration = _get_audio_duration(str(output_path))
    public_url = str(output_path).replace(
        "/home/claude-user/tiktok-voyance", "https://factorytiktok.duckdns.org"
    )

    return {
        "audio_path": str(output_path),
        "audio_url": public_url,
        "audio_duration": duration,
        "script": script,
        "voice_id": voice_id,
        "model": model_id,
        "preview": preview,
    }
