"""TikTok Content Posting API — photo carousel via URL pull"""
import httpx
from tiktok_auth import get_valid_token

BASE_URL = "https://factorytiktok.duckdns.org"


def path_to_url(path: str) -> str:
    """Convertit un chemin local en URL publique."""
    # /home/claude-user/tiktok-factory/output/... → https://factorytiktok.duckdns.org/output/...
    relative = path.replace("/home/claude-user/tiktok-factory", "")
    return f"{BASE_URL}{relative}"


def post_photo_carousel(image_paths: list[str], caption: str = "") -> dict:
    """Publie un carrousel de photos sur TikTok via PULL_FROM_URL."""
    token = get_valid_token()
    if not token:
        raise RuntimeError("Pas de token TikTok — reconnectez-vous via OAuth")

    photo_urls = [path_to_url(p) for p in image_paths]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    payload = {
        "media_type": "PHOTO",
        "post_mode": "DIRECT_POST",
        "post_info": {
            "title": caption[:90] if caption else "Oracle du jour",
            "privacy_level": "SELF_ONLY",
            "disable_comment": False,
            "auto_add_music": True,
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
            raise RuntimeError(f"Init error {r.status_code}: {r.text}")

        data = r.json().get("data", {})
        publish_id = data.get("publish_id")

    return {"publish_id": publish_id, "status": "published", "photo_urls": photo_urls}


def get_post_status(publish_id: str) -> dict:
    token = get_valid_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=30) as client:
        r = client.post(
            "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
            headers=headers,
            json={"publish_id": publish_id},
        )
        return r.json()
