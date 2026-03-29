"""Agent 3 — Superpose le texte sur first frame et last frame avec Pillow"""
import re
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import httpx

CTA_PHRASES = [
    "LIKE POUR QUE L'UNIVERS T'ENTENDE",
    "LIKE ET LAISSE L'UNIVERS AGIR",
    "LIKE POUR ACTIVER CETTE ENERGIE",
    "LIKE SI C'EST UN SIGNE POUR TOI",
    "LIKE SI TU LE SENS",
    "LIKE POUR QUE CA SE REALISE",
    "LIKE SI CE MESSAGE EST POUR TOI",
    "LIKE POUR ATTIRER CETTE ENERGIE",
]

OUTPUT_DIR = Path("/home/claude-user/tiktok-factory/output/video_jobs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FONTS_DIR = Path("/home/claude-user/tiktok-factory/static/fonts")
W, H = 1024, 1536

OUTCOME_COLORS = {
    "positive": (80, 220, 140, 255),   # vert doux
    "neutral":  (220, 180, 80, 255),   # or
    "negative": (220, 90, 90, 255),    # rouge doux
}

OUTCOME_LABELS = {
    "positive": "✦ Favorable",
    "neutral":  "✦ Énergie Mixte",
    "negative": "✦ Difficile",
}


def strip_emoji(text: str) -> str:
    return re.compile(
        "[\U00010000-\U0010ffff\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF]+",
        flags=re.UNICODE
    ).sub('', text).strip()


def load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONTS_DIR / "Cinzel.ttf"), size)
    except:
        return ImageFont.load_default()


def load_image_from_url_or_path(src: str) -> Image.Image:
    if src.startswith("http"):
        r = httpx.get(src, timeout=30)
        return Image.open(BytesIO(r.content)).convert("RGBA")
    return Image.open(src).convert("RGBA")


def resize_to_tiktok(img: Image.Image) -> Image.Image:
    ratio = max(W / img.width, H / img.height)
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - W) // 2, (nh - H) // 2
    return img.crop((left, top, left + W, top + H))


def dark_overlay(img: Image.Image, alpha: int = 100) -> Image.Image:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, alpha))
    return Image.alpha_composite(img, overlay)


def draw_centered(draw, text, y, font, color=(255, 255, 255, 255)):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    for dx, dy in [(-2, 2), (2, 2), (0, 3)]:
        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), text, font=font, fill=color)


def draw_wrapped(draw, text, y_center, font, max_width, color=(255, 255, 255, 255)):
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
    lh = font.size + 12
    start_y = y_center - (len(lines) * lh) // 2
    for i, line in enumerate(lines):
        draw_centered(draw, line, start_y + i * lh, font, color)
    return start_y + len(lines) * lh


def draw_separator(draw, y, x0=140, x1=None):
    if x1 is None:
        x1 = W - 140
    cx = W // 2
    gold = (200, 175, 120, 150)
    draw.line([(x0, y), (cx - 18, y)], fill=gold, width=1)
    draw.line([(cx + 18, y), (x1, y)], fill=gold, width=1)
    draw.polygon([(cx, y-7), (cx+9, y), (cx, y+7), (cx-9, y)], fill=gold)


def build_intro_frame(first_frame_src: str, question: str, hook: str, job_id: str) -> str:
    """Frame d'intro : vidéo — question apparaît vite, puis CTA, les deux restent."""
    import subprocess

    img = load_image_from_url_or_path(first_frame_src)
    img = resize_to_tiktok(img)

    TOP_SAFE = 320
    BOT_SAFE = H - 420
    cta = random.choice(CTA_PHRASES)

    def make_frame(with_question: bool, with_cta: bool, path: Path):
        frame = dark_overlay(img.copy(), 130)
        draw = ImageDraw.Draw(frame)
        if with_question:
            font_q = load_font(68)
            q_clean = strip_emoji(question)
            draw_wrapped(draw, q_clean, (TOP_SAFE + BOT_SAFE) // 2, font_q, W - 120, color=(255, 255, 255, 245))
        if with_cta:
            draw_separator(draw, BOT_SAFE - 90)
            font_cta = load_font(36)
            draw_centered(draw, cta, BOT_SAFE - 55, font_cta, color=(200, 175, 120, 230))
        frame.convert("RGB").save(str(path), "JPEG", quality=92)

    # 3 états : fond seul / question seule / question + CTA
    p_bg  = OUTPUT_DIR / f"{job_id}_i0.jpg"
    p_q   = OUTPUT_DIR / f"{job_id}_i1.jpg"
    p_all = OUTPUT_DIR / f"{job_id}_i2.jpg"

    make_frame(False, False, p_bg)
    make_frame(True,  False, p_q)
    make_frame(True,  True,  p_all)

    # Convertir chaque image en clip court, puis xfade
    out_path = OUTPUT_DIR / f"{job_id}_intro.mp4"
    v_bg  = OUTPUT_DIR / f"{job_id}_v0.mp4"
    v_q   = OUTPUT_DIR / f"{job_id}_v1.mp4"
    v_all = OUTPUT_DIR / f"{job_id}_v2.mp4"

    for src, dst, dur in [(p_bg, v_bg, 0.9), (p_q, v_q, 1.0), (p_all, v_all, 1.5)]:
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", str(dur), "-r", "25", "-i", str(src),
            "-vf", f"scale={W}:{H}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst)
        ], check=True, capture_output=True)

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(v_bg), "-i", str(v_q), "-i", str(v_all),
        "-filter_complex",
        "[0][1]xfade=transition=fade:duration=0.4:offset=0.5[va];"
        "[va][2]xfade=transition=fade:duration=0.4:offset=1.1[vout]",
        "-map", "[vout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out_path)
    ], check=True, capture_output=True)

    for p in [p_bg, p_q, p_all, v_bg, v_q, v_all]:
        p.unlink(missing_ok=True)

    for p in [p_bg, p_q, p_all]:
        p.unlink(missing_ok=True)

    return str(out_path)


def build_reveal_frame(last_frame_src: str, card: dict, reading: str, outcome: str, job_id: str) -> str:
    """Frame de révélation : carte + lecture sur le last frame."""
    img = load_image_from_url_or_path(last_frame_src)
    img = resize_to_tiktok(img)
    img = dark_overlay(img, 130)
    draw = ImageDraw.Draw(img)

    TOP_SAFE = 320
    BOT_SAFE = H - 420
    outcome_color = OUTCOME_COLORS.get(outcome, (220, 200, 120, 255))
    outcome_label = OUTCOME_LABELS.get(outcome, "")

    # Nom de la carte
    font_name = load_font(52)
    draw_centered(draw, strip_emoji(card.get("name_fr") or card.get("name", "")).upper(), TOP_SAFE + 10, font_name, color=(210, 190, 150, 240))

    draw_separator(draw, TOP_SAFE + 100)

    # Label outcome centré
    font_outcome = load_font(42)
    draw_centered(draw, strip_emoji(outcome_label).upper(), TOP_SAFE + 140, font_outcome, color=outcome_color)

    draw_separator(draw, TOP_SAFE + 210)

    # Lecture
    font_reading = load_font(38)
    draw_wrapped(draw, strip_emoji(reading), (TOP_SAFE + BOT_SAFE) // 2 + 40, font_reading, W - 180, color=(230, 225, 210, 235))

    draw_separator(draw, BOT_SAFE - 80)

    # Meaning court
    font_meaning = load_font(32)
    meaning = strip_emoji(card.get("meaning_fr") or card.get("meaning", ""))
    draw_wrapped(draw, meaning, BOT_SAFE - 30, font_meaning, W - 200, color=(180, 165, 120, 200))

    path = OUTPUT_DIR / f"{job_id}_reveal.jpg"
    img.convert("RGB").save(str(path), "JPEG", quality=92)
    return str(path)


def run(params: dict) -> dict:
    job_id = params.get("job_id", "video")
    question_result = params.get("question_result", {})
    first_frame_url = params.get("first_frame_url", "")
    last_frames = params.get("last_frames", {})

    card = question_result.get("card", {})
    card_id = card.get("id", "lune")
    outcome = question_result.get("outcome", "neutral")
    reading = question_result.get("reading", "")
    hook = question_result.get("hook", "")
    question = question_result.get("question_fr") or question_result.get("question", "")

    last_frame_src = last_frames.get(card_id, "")
    if not last_frame_src:
        raise RuntimeError(f"Dernier frame manquant pour la carte '{card_id}'")

    intro_path = build_intro_frame(first_frame_url, question, hook, job_id)
    reveal_path = build_reveal_frame(last_frame_src, card, reading, outcome, job_id)

    return {
        "intro_path": intro_path,
        "reveal_path": reveal_path,
        "intro_url": intro_path.replace("/home/claude-user/tiktok-factory", "https://factorytiktok.duckdns.org"),
        "reveal_url": reveal_path.replace("/home/claude-user/tiktok-factory", "https://factorytiktok.duckdns.org"),
    }
