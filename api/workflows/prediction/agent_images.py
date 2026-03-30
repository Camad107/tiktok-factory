"""Agent 3 — Génère 4 images via Fal.ai queue + superpose le texte avec Pillow"""
import os
import re
import time
import httpx
import traceback
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

FAL_KEY = os.environ.get("FAL_KEY", "")
OUTPUT_DIR = Path("/home/claude-user/tiktok-factory/output/prediction")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FONTS_DIR = Path("/home/claude-user/tiktok-factory/static/fonts")
W, H = 1080, 1920  # TikTok 9:16


def strip_emoji(text: str) -> str:
    """Supprime les emojis du texte."""
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff"
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\u2600-\u26FF\u2700-\u27BF]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text).strip()


def fetch_image_queue(prompt: str, seed: int = None) -> bytes:
    """Soumet via queue Fal.ai avec seed pour cohérence."""
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt + ", no text, no words, no letters",
        "image_size": "portrait_4_3",
        "num_inference_steps": 4,
        "num_images": 1,
    }
    if seed:
        payload["seed"] = seed

    with httpx.Client(timeout=30.0) as client:
        r = client.post("https://queue.fal.run/fal-ai/flux/schnell", headers=headers, json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"Submit error {r.status_code}: {r.text[:200]}")

        result_url = r.json().get("response_url")
        for _ in range(40):
            time.sleep(3)
            poll = client.get(result_url, headers=headers)
            if poll.status_code == 200:
                pd = poll.json()
                imgs = pd.get("images")
                if imgs:
                    img_r = client.get(imgs[0]["url"], timeout=60.0)
                    return img_r.content
                if pd.get("error"):
                    raise RuntimeError(f"Fal error: {pd['error']}")
        raise RuntimeError("Timeout image generation")


def load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONTS_DIR / "Cinzel.ttf"), size)
    except:
        return ImageFont.load_default()


def resize_to_tiktok(img_bytes: bytes) -> Image.Image:
    img = Image.open(BytesIO(img_bytes)).convert("RGBA")
    ratio = max(W / img.width, H / img.height)
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - W) // 2, (nh - H) // 2
    return img.crop((left, top, left + W, top + H))


def dark_overlay(img: Image.Image, alpha: int = 90) -> Image.Image:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, alpha))
    return Image.alpha_composite(img, overlay)


def draw_centered(draw: ImageDraw.Draw, text: str, y: int, font: ImageFont.FreeTypeFont,
                   color=(255, 255, 255, 255)):
    """Texte centré avec ombre portée."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    # Ombre
    for dx, dy in [(-2, 2), (2, 2), (0, 3)]:
        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), text, font=font, fill=color)


def draw_wrapped(draw: ImageDraw.Draw, text: str, y_center: int,
                  font: ImageFont.FreeTypeFont, max_width: int,
                  color=(240, 235, 220, 255)) -> int:
    """Texte centré avec retour à la ligne. Retourne le y final."""
    words = text.split()
    lines, current = [], ""
    for w in words:
        test = (current + " " + w).strip()
        if draw.textbbox((0, 0), test, font=font)[2] > max_width and current:
            lines.append(current)
            current = w
        else:
            current = test
    if current:
        lines.append(current)

    lh = font.size + 10
    start_y = y_center - (len(lines) * lh) // 2
    for i, line in enumerate(lines):
        draw_centered(draw, line, start_y + i * lh, font, color)
    return start_y + len(lines) * lh


def draw_text_at_x(draw: ImageDraw.Draw, text: str, cx: int, y: int,
                    font: ImageFont.FreeTypeFont, color=(255, 255, 255, 255)):
    """Texte centré sur cx (pas sur W)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = cx - tw // 2
    for dx, dy in [(-2, 2), (2, 2), (0, 3)]:
        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), text, font=font, fill=color)


def draw_ornament(draw: ImageDraw.Draw, cx: int, y: int, half_w: int = 60):
    """Petit ornement — losange central + tirets."""
    gold = (200, 175, 120, 160)
    draw.line([(cx - half_w, y), (cx - 10, y)], fill=gold, width=1)
    draw.line([(cx + 10, y), (cx + half_w, y)], fill=gold, width=1)
    # Losange
    draw.polygon([(cx, y - 5), (cx + 6, y), (cx, y + 5), (cx - 6, y)], fill=gold)


def build_image1(img_bytes: bytes, content: dict) -> str:
    """Image 1 : 3 cartes face cachée — incite à choisir, sans noms de symboles."""
    img = resize_to_tiktok(img_bytes)
    img = dark_overlay(img, 80)
    draw = ImageDraw.Draw(img)

    hook = strip_emoji(content.get("hook", "Choisissez votre carte"))
    cta = "Choisis un symbole"

    # Safe zones TikTok — 320px haut (profil+titre), 420px bas (boutons)
    TOP_SAFE = 320
    BOT_SAFE = H - 420

    # Hook en haut
    font_hook = load_font(54)
    draw_wrapped(draw, hook.upper(), TOP_SAFE, font_hook, W - 160, color=(255, 248, 230, 255))

    # Ornement sous le hook
    draw_ornament(draw, W // 2, TOP_SAFE + 110, half_w=120)

    # Ornement au-dessus du CTA
    draw_ornament(draw, W // 2, BOT_SAFE - 70, half_w=120)

    # CTA en bas
    font_cta = load_font(62)
    draw_wrapped(draw, cta, BOT_SAFE - 20, font_cta, W - 160, color=(200, 180, 140, 230))

    path = OUTPUT_DIR / f"{content.get('_job_id', 'job')}_1_choix.jpg"
    img.convert("RGB").save(str(path), "JPEG", quality=92)
    return str(path)


def draw_card_frame(draw: ImageDraw.Draw, x0: int, y0: int, x1: int, y1: int,
                    corner: int = 28):
    """Cadre de carte élégant avec coins ornés."""
    gold = (200, 175, 120, 200)
    gold_dim = (160, 140, 90, 130)
    r = corner

    # Bordure principale — rectangle arrondi simulé avec lignes
    # Côtés
    draw.line([(x0 + r, y0), (x1 - r, y0)], fill=gold, width=2)
    draw.line([(x0 + r, y1), (x1 - r, y1)], fill=gold, width=2)
    draw.line([(x0, y0 + r), (x0, y1 - r)], fill=gold, width=2)
    draw.line([(x1, y0 + r), (x1, y1 - r)], fill=gold, width=2)

    # Coins coupés en diagonale
    draw.line([(x0, y0 + r), (x0 + r, y0)], fill=gold, width=2)
    draw.line([(x1 - r, y0), (x1, y0 + r)], fill=gold, width=2)
    draw.line([(x0, y1 - r), (x0 + r, y1)], fill=gold, width=2)
    draw.line([(x1 - r, y1), (x1, y1 - r)], fill=gold, width=2)

    # Ornements aux coins — petits carrés tournés
    for cx, cy in [(x0 + r, y0 + r), (x1 - r, y0 + r),
                   (x0 + r, y1 - r), (x1 - r, y1 - r)]:
        s = 6
        draw.polygon([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)],
                     fill=gold_dim)

    # Double bordure intérieure fine
    pad = 12
    draw.rectangle([x0 + pad, y0 + pad, x1 - pad, y1 - pad],
                   outline=(160, 140, 90, 80), width=1)


def draw_separator(draw: ImageDraw.Draw, y: int, x0: int = 140, x1: int = None):
    """Séparateur orné avec losange central."""
    if x1 is None:
        x1 = W - 140
    cx = W // 2
    gold = (200, 175, 120, 150)
    draw.line([(x0, y), (cx - 18, y)], fill=gold, width=1)
    draw.line([(cx + 18, y), (x1, y)], fill=gold, width=1)
    draw.polygon([(cx, y - 7), (cx + 9, y), (cx, y + 7), (cx - 9, y)], fill=gold)
    # Petits points flanquants
    for dx in [-28, 28]:
        draw.ellipse([(cx + dx - 2, y - 2), (cx + dx + 2, y + 2)],
                     fill=(180, 155, 100, 120))


def build_symbol_image(img_bytes: bytes, symbol: dict, img_num: int, job_id: str) -> str:
    """Images 2-4 : carte retournée avec cadre graphique."""
    img = resize_to_tiktok(img_bytes)
    img = dark_overlay(img, 85)
    draw = ImageDraw.Draw(img)

    name = strip_emoji(symbol.get("name", ""))
    title = strip_emoji(symbol.get("prediction_title", ""))
    prediction = strip_emoji(symbol.get("prediction", ""))
    energy = strip_emoji(symbol.get("energy", ""))

    # Safe zones TikTok — 320px haut, 420px bas
    TOP_SAFE = 320
    BOT_SAFE = H - 420

    # Cadre dans la zone safe
    draw_card_frame(draw, 70, TOP_SAFE - 30, W - 70, BOT_SAFE + 30, corner=32)

    # Nom du symbole en haut
    font_name = load_font(50)
    draw_centered(draw, name.upper(), TOP_SAFE + 10, font_name, color=(210, 190, 150, 240))

    # Séparateur orné
    draw_separator(draw, TOP_SAFE + 100, x0=140, x1=W - 140)

    # Titre prédiction — centré dans la zone disponible
    font_title = load_font(66)
    mid = (TOP_SAFE + BOT_SAFE) // 2 - 60
    draw_wrapped(draw, title.upper(), mid, font_title, W - 200, color=(255, 250, 225, 255))

    # Séparateur fin
    draw_separator(draw, mid + 130, x0=200, x1=W - 200)

    # Texte prédiction
    font_pred = load_font(40)
    draw_wrapped(draw, prediction, mid + 230, font_pred, W - 200, color=(230, 225, 210, 235))

    # Séparateur bas
    draw_separator(draw, BOT_SAFE - 90, x0=140, x1=W - 140)

    # Énergie en bas
    font_energy = load_font(36)
    draw_centered(draw, energy.upper(), BOT_SAFE - 50, font_energy, color=(190, 165, 115, 210))

    path = OUTPUT_DIR / f"{job_id}_{img_num}_{symbol.get('id', img_num)}.jpg"
    img.convert("RGB").save(str(path), "JPEG", quality=92)
    return str(path)


def run(params: dict) -> dict:
    content = params.get("content", {})
    prompts = params.get("image_prompts", {})
    job_id = params.get("job_id", "default")
    content["_job_id"] = job_id

    seed = prompts.get("seed")
    symbols = content.get("symbols", [])
    prompt_keys = ["image1_prompt", "image2_prompt", "image3_prompt", "image4_prompt"]
    results = {}

    for i, key in enumerate(prompt_keys):
        prompt = prompts.get(key, "wooden table with dark linen cloth, tarot cards, soft candlelight")
        try:
            img_bytes = fetch_image_queue(prompt, seed=seed)
            if i == 0:
                results["image1"] = build_image1(img_bytes, content)
            else:
                sym = symbols[i - 1] if i - 1 < len(symbols) else {}
                results[f"image{i + 1}"] = build_symbol_image(img_bytes, sym, i + 1, job_id)
        except Exception:
            raise RuntimeError(f"Image {i+1} failed:\n{traceback.format_exc()}")

    return {"images": results}
