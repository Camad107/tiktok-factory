"""Agent 4 — Génère la voix via Fal.ai (ElevenLabs multilingual) — mode synchrone"""
import os
import httpx
import traceback
from pathlib import Path

FAL_KEY = os.environ.get("FAL_KEY", "")
OUTPUT_DIR = Path("/home/claude-user/tiktok-factory/output/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FAL_VOICE = os.environ.get("FAL_VOICE_VOYANCE", "Charlotte")


def build_full_script(content: dict) -> list[dict]:
    segments = []
    segments.append({"id": "intro", "text": content.get("intro_text", "")})
    for card in content.get("cards", []):
        text = f"{card['label']}. {card['tarot_card']}. Énergie : {card['energy']}. {card['prediction']}"
        segments.append({"id": f"card{card['number']}", "text": text})
    segments.append({"id": "outro", "text": content.get("outro_text", "")})
    return segments


def generate_segment(text: str, filename: str, voice=None, speed=None) -> str:
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            "https://fal.run/fal-ai/elevenlabs/tts/multilingual-v2",
            headers={
                "Authorization": f"Key {FAL_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "voice": voice or FAL_VOICE,
                "language_code": "fr",
                "stability": 0.55,
                "similarity_boost": 0.80,
                "style": 0.45,
                "speed": speed if speed is not None else 0.90,
            }
        )

        if response.status_code != 200:
            raise RuntimeError(f"TTS error {response.status_code}: {response.text[:200]}")

        data = response.json()
        audio_url = data.get("audio", {}).get("url")
        if not audio_url:
            raise RuntimeError(f"No audio URL. Response: {data}")

        audio_resp = client.get(audio_url)
        filepath = OUTPUT_DIR / filename
        filepath.write_bytes(audio_resp.content)
        return str(filepath)


def run(params: dict) -> dict:
    content = params.get("content", {})
    job_id = params.get("job_id", "default")
    # Overrides optionnels depuis l'UI
    voice_override = params.get("voice")
    speed_override = params.get("speed")

    segments = build_full_script(content)
    output = {}

    for seg in segments:
        if not seg["text"].strip():
            continue
        filename = f"{job_id}_{seg['id']}.mp3"
        try:
            path = generate_segment(
                seg["text"], filename,
                voice=voice_override,
                speed=speed_override,
            )
            output[seg["id"]] = path
        except Exception as e:
            raise RuntimeError(f"Voice segment '{seg['id']}' failed: {traceback.format_exc()}")

    return {"audio_segments": output}
