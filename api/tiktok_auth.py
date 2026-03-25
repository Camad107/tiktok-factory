"""TikTok OAuth 2.0 — gestion tokens"""
import json
import os
import httpx
from pathlib import Path

CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("TIKTOK_REDIRECT_URI", "https://factorytiktok.duckdns.org/oauth/callback")
SCOPES = "video.upload,video.publish"

TOKEN_FILE = Path(__file__).parent / "tiktok_token.json"


def get_auth_url() -> str:
    return (
        f"https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={CLIENT_KEY}"
        f"&scope={SCOPES}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state=tiktok_voyance"
    )


def exchange_code(code: str) -> dict:
    """Échange le code OAuth contre access_token + refresh_token."""
    with httpx.Client(timeout=30) as client:
        r = client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={
                "client_key": CLIENT_KEY,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        data = r.json()
        save_token(data)
        return data


def refresh_access_token(refresh_token: str) -> dict:
    with httpx.Client(timeout=30) as client:
        r = client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={
                "client_key": CLIENT_KEY,
                "client_secret": CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        data = r.json()
        save_token(data)
        return data


def save_token(data: dict):
    TOKEN_FILE.write_text(json.dumps(data, indent=2))


def load_token() -> dict | None:
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())
    return None


def get_valid_token() -> str | None:
    """Retourne un access_token valide, rafraîchit si nécessaire."""
    token = load_token()
    if not token:
        return None
    # Tente un refresh pour s'assurer que le token est frais
    refresh = token.get("refresh_token")
    if not refresh:
        return token.get("access_token")
    try:
        new_token = refresh_access_token(refresh)
        return new_token.get("access_token")
    except Exception:
        return token.get("access_token")
