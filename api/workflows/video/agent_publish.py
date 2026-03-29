"""Agent 5 — Génère la description TikTok et publie la vidéo en inbox"""
import subprocess
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

PROMPT = """Tu es un expert marketing TikTok pour un compte tarot mystique ciblant une audience francophone.

Contenu de la vidéo tarot du jour :
Hook : {hook}
Énergie : {outcome}

Génère un titre, une courte description, des hashtags et une suggestion audio. Règles :
- Le titre ne doit PAS révéler le nom de la carte ni le résultat. Mystérieux, accrocheur, fait stopper le scroll.
- La description est 1 phrase max, qui parle directement au spectateur, crée du suspense. Pas de nom de carte. Pas de spoiler.
- Max 5 hashtags en français.
- Suggère UN son TikTok tendance qui correspond à une ambiance tarot mystique (ambiant, éthéré, mystérieux). Donne le terme de recherche exact pour le trouver sur TikTok.

Format JSON strict :
{{
  "title": "hook mystérieux et accrocheur en français (max 60 caractères, sans emoji, sans nom de carte, différent du hook ci-dessus)",
  "description": "1 phrase en français. Parle directement au spectateur. Crée du suspense. Ne révèle pas la carte. Pas de hashtags ici.",
  "hashtags": "#tarot #voyance #cartomancie #spiritualite #tarottok",
  "audio_suggestion": "terme de recherche exact pour un son TikTok tendance mystique/ambiant",
  "full_text": "title + \\n\\n + description + \\n\\n + hashtags — format exact pour TikTok : le titre sur la première ligne (visible), saut de ligne, puis le reste masqué derrière '...plus'"
}}

Réponds UNIQUEMENT avec le JSON."""


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
    if not raw:
        raise RuntimeError(f"Claude CLI empty stdout. stderr: {result.stderr!r}")
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
    video_url = video_path.replace("/home/claude-user/tiktok-factory", BASE_URL)

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
