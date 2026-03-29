"""Agent 5 — Publie la vidéo histoire dans l'inbox TikTok"""


def run(params: dict) -> dict:
    research_result = params.get("research_result", {})
    prompt_result = params.get("prompt_result", {})
    montage_result = params.get("montage_result", {})

    description = research_result.get("description_tiktok", "")
    hashtags = research_result.get("hashtags", "#histoire #fyp")
    verified_title = research_result.get("verified_title", "Histoire du jour")
    year = research_result.get("year", "")
    video_path = montage_result.get("final_path", "")

    title = f"{verified_title} ({year})" if year else verified_title
    full_text = f"{description}\n\n{hashtags}" if description else f"{title}\n\n{hashtags}"

    try:
        publish_result = _send_to_inbox(video_path, title, full_text)
    except Exception as e:
        publish_result = {"status": "error", "message": str(e)}

    return {
        "title": title,
        "description": full_text,
        "hashtags": hashtags,
        "publish": publish_result,
    }


def _send_to_inbox(video_path: str, title: str, full_text: str) -> dict:
    from tiktok_auth import get_valid_token
    import httpx
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    token = get_valid_token()
    if not token:
        return {"status": "no_token", "message": "Token TikTok manquant — reconnectez-vous"}

    BASE_URL = "https://factorytiktok.duckdns.org"
    video_url = video_path.replace("/home/claude-user/tiktok-voyance", BASE_URL)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    payload = {
        "post_info": {
            "title": title.strip()[:150],
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
            "message": "Vidéo envoyée dans ton inbox TikTok",
        }
