"""Agent 4 — Génère la description TikTok via Claude + envoie en inbox"""
import subprocess
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

PROMPT = """You are a TikTok marketing expert for an oracle/tarot account targeting English-speaking audiences.

Today's oracle content:
Hook: {hook}
Symbols: {symbols}
CTA: {cta}
Theme: {theme}

Generate two distinct texts for TikTok. Strict JSON format:
{{
  "title": "short punchy title (max 60 chars, no emoji, different from the hook)",
  "description": "engaging description of 3-5 sentences in English. Speak directly to the viewer. Mention the theme '{theme}' and invite them to pick a card. Create intrigue. End with the CTA. No hashtags here.",
  "hashtags": "#pickacard #tarot #tarotreading #spiritualtiktok #tarottok",
  "full_text": "description + two line breaks + hashtags (assembled, ready to post)"
}}

Reply ONLY with the JSON."""


def run(params: dict) -> dict:
    content = params.get("content", {})
    hook = content.get("hook", "")
    cta = content.get("cta", "")
    symbols = " / ".join([s.get("name", "") for s in content.get("symbols", [])])
    theme = content.get("_theme", "")

    prompt = PROMPT.format(hook=hook, symbols=symbols, cta=cta, theme=theme)

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

    # Envoyer en inbox TikTok
    images = params.get("images", {})
    image_paths = [v for k, v in sorted(images.items()) if v]
    title = data.get("title", "Today's Oracle")
    full_text = data.get("full_text", data.get("description", title))

    publish_result = _send_to_inbox(image_paths, title, full_text)

    return {
        "title": data.get("title"),
        "description": data.get("description"),
        "hashtags": data.get("hashtags"),
        "full_text": data.get("full_text"),
        "publish": publish_result,
    }


def _send_to_inbox(image_paths: list, title: str, full_text: str = "") -> dict:
    from tiktok_auth import get_valid_token
    import httpx

    token = get_valid_token()
    if not token:
        return {"status": "no_token", "message": "Token TikTok manquant — reconnectez-vous"}

    BASE_URL = "https://factorytiktok.duckdns.org"
    photo_urls = [p.replace("/home/claude-user/tiktok-voyance", BASE_URL) for p in image_paths]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    clean_title = title.strip()[:90] or "Oracle du jour"
    description = (full_text or title).strip()[:2200]

    payload = {
        "media_type": "PHOTO",
        "post_mode": "MEDIA_UPLOAD",
        "post_info": {
            "title": clean_title,
            "description": description,
            "disable_comment": False,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "photo_images": photo_urls,
            "photo_cover_index": 0,
        },
    }

    with httpx.Client(timeout=60) as client:
        r = client.post(
            "https://open.tiktokapis.com/v2/post/publish/content/init/",
            headers=headers,
            json=payload,
        )
        if r.status_code != 200:
            raise RuntimeError(f"TikTok error {r.status_code}: {r.text}")

        data = r.json().get("data", {})
        return {
            "status": "sent_to_inbox",
            "publish_id": data.get("publish_id"),
            "message": "Post envoyé dans ton inbox TikTok — ouvre l'app pour publier",
        }
