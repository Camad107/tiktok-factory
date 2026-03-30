"""Agent 5 — Génère la description TikTok et publie la vidéo en inbox"""
import subprocess
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

PROMPT = """Tu es un expert marketing TikTok pour un compte tarot/voyance ciblant une audience francophone.

Sujet de la lecture : {sujet}
Hook : {hook}
Cartes tirées : {cartes}

Génère le texte du post TikTok. TOUT en français. Format JSON strict :
{{
  "title": "titre accrocheur mystérieux, max 60 caractères, sans emoji, donne envie de regarder",
  "description": "1 phrase qui invite à liker ou commenter, avec 1 emoji max",
  "hashtags": "#tarot #voyance #cartomancie #tarottok #spiritualite #retournement #arcanes",
  "full_text": "description + \\n\\n + hashtags"
}}

Réponds UNIQUEMENT avec le JSON."""


def run(params: dict) -> dict:
    content = params.get("content", {})
    video = params.get("video", {})

    sujet = content.get("_sujet", "")
    hook = content.get("hook", "")
    cartes = " / ".join([c.get("nom", "") for c in content.get("cartes", [])])

    prompt = PROMPT.format(sujet=sujet, hook=hook, cartes=cartes)

    result = subprocess.run(
        ["/home/claude-user/.local/bin/claude", "--print", "--output-format", "text"],
        input=prompt, capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr}")

    raw = result.stdout.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw.strip())
    if isinstance(data, list):
        data = data[0]

    video_path = video.get("video_path", "")
    video_url = video.get("video_url", "")
    title = data.get("title", "Tarot du jour")
    full_text = data.get("full_text", data.get("description", title))

    try:
        publish_result = _send_to_inbox(video_path, video_url, title, full_text)
    except Exception as e:
        publish_result = {"status": "error", "message": str(e)}

    return {
        "title": data.get("title"),
        "description": data.get("description"),
        "hashtags": data.get("hashtags"),
        "full_text": data.get("full_text"),
        "publish": publish_result,
    }


def _send_to_inbox(video_path: str, video_url: str, title: str, full_text: str) -> dict:
    from tiktok_auth import get_valid_token
    import httpx

    token = get_valid_token()
    if not token:
        return {"status": "no_token", "message": "Token TikTok manquant — reconnectez-vous"}

    if not video_url:
        return {"status": "error", "message": "URL vidéo manquante"}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    payload = {
        "post_info": {
            "title": f"{title.strip()[:90]}\n\n{full_text.strip()[:2200]}"[:150],
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
