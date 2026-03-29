"""Agent 4 — Génère la description TikTok via Claude + envoie en inbox"""
import subprocess
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

PROMPT = """Tu es un expert marketing TikTok pour un compte oracle/voyance ciblant une audience francophone.

Contenu oracle du jour :
Hook : {hook}
Symboles : {symbols}
CTA : {cta}
Thème : {theme}

Génère le texte du post TikTok. TOUT doit être en français. Format JSON strict :
{{
  "title": "hook accrocheur qui invite à choisir une carte, style : 'Choisis une carte' ou 'L'une d'elle te connaît' ou 'Laquelle te parle ?' — max 60 caractères, sans emoji",
  "description": "une seule phrase d'engagement qui invite à liker pour que ça se réalise, sans emoji, sans hashtags — ex: 'Like si tu veux que ça se réalise pour toi 🤍'",
  "hashtags": "#choisistacarte #tarot #voyance #spiritualite #oracle",
  "full_text": "description + \\n\\n + hashtags"
}}

Réponds UNIQUEMENT avec le JSON."""


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
