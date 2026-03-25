"""Agent 5 — Génère la description TikTok et publie la vidéo en inbox"""
import subprocess
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

PROMPT = """You are a TikTok marketing expert for a mystical tarot account targeting English-speaking US audiences.

Today's tarot video content:
Hook: {hook}
Outcome energy: {outcome}

Generate a TikTok title, short description, hashtags, and an audio recommendation. Rules:
- The title must NOT reveal the card name or the reading result. Mysterious, engaging, makes people stop scrolling.
- The description is 1-2 sentences max, speaking directly to the viewer, creating suspense. No card name. No spoiler.
- Max 5 hashtags.
- Suggest ONE real trending TikTok audio/song that fits a mystical tarot vibe and is currently popular in the USA (ambient, ethereal, mysterious, or a popular song with a moody feel). Give the exact search term to find it on TikTok.

Strict JSON format:
{{
  "title": "mysterious engaging hook (max 60 chars, no emoji, no card name, different from the hook above)",
  "description": "1-2 sentences. Speak directly to the viewer. Build suspense. Do NOT reveal the card or outcome. Do NOT include hashtags here.",
  "hashtags": "#tarot #tarotreading #pickacard #spiritualtiktok #tarottok",
  "audio_suggestion": "exact TikTok search term for a trending mystical/moody audio",
  "full_text": "description + two line breaks + hashtags (assembled, ready to post)"
}}

Reply ONLY with the JSON."""


def run(params: dict) -> dict:
    question_result = params.get("question_result", {})
    montage_result = params.get("montage_result", {})

    hook = question_result.get("hook", "")
    card = question_result.get("card", {})
    card_name = card.get("name", "")
    reading = question_result.get("reading", "")
    outcome = question_result.get("outcome", "neutral")

    prompt = PROMPT.format(
        hook=hook,
        outcome=outcome,
    )

    result = subprocess.run(
        ["/home/claude-user/.local/bin/claude", "--print", "--output-format", "text"],
        input=prompt,
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr}")

    raw = result.stdout.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    parsed = json.loads(raw.strip())
    data = parsed[0] if isinstance(parsed, list) else parsed

    video_path = montage_result.get("final_path", "")
    title = data.get("title", "Tarot du jour")
    full_text = data.get("full_text", data.get("description", title))

    try:
        publish_result = _send_to_inbox(video_path, title, full_text)
    except Exception as e:
        publish_result = {"status": "error", "message": str(e)}

    return {
        "title": data.get("title"),
        "description": data.get("description"),
        "hashtags": data.get("hashtags"),
        "audio_suggestion": data.get("audio_suggestion"),
        "full_text": data.get("full_text"),
        "publish": publish_result,
    }


def _send_to_inbox(video_path: str, title: str, full_text: str = "") -> dict:
    from tiktok_auth import get_valid_token
    import httpx

    token = get_valid_token()
    if not token:
        return {"status": "no_token", "message": "Token TikTok manquant — reconnectez-vous"}

    BASE_URL = "https://factorytiktok.duckdns.org"
    video_url = video_path.replace("/home/claude-user/tiktok-voyance", BASE_URL)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    clean_title = title.strip()[:90] or "Tarot du jour"
    description = (full_text or title).strip()[:2200]

    payload = {
        "post_info": {
            "title": f"{clean_title}\n\n{description}"[:150],
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        },
    }

    with httpx.Client(timeout=60) as client:
        r = client.post(
            "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
            headers=headers,
            json=payload,
        )
        if r.status_code != 200:
            raise RuntimeError(f"TikTok error {r.status_code}: {r.text}")

        resp_data = r.json().get("data", {})
        return {
            "status": "sent_to_inbox",
            "publish_id": resp_data.get("publish_id"),
            "message": "Vidéo envoyée dans ton inbox TikTok — ouvre l'app pour publier",
        }
