"""Agent 4 — Monte la vidéo finale avec FFmpeg : overlays typographiques, safe zones TikTok"""
import subprocess
import json
from pathlib import Path
from PIL import ImageFont

OUTPUT_DIR = Path("/home/claude-user/tiktok-factory/output/histoire")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FONTS = {
    "cinzel":   "/home/claude-user/tiktok-factory/static/fonts/Cinzel.ttf",
    "bebas":    "/home/claude-user/tiktok-factory/static/fonts/BebasNeue.ttf",
    "oswald":   "/home/claude-user/tiktok-factory/static/fonts/Oswald-Bold.ttf",
    "fallback": "/usr/share/fonts/truetype/lato/Lato-Black.ttf",
}

# Safe zones TikTok
SAFE_TOP_RATIO = 0.13
SAFE_BOT_RATIO = 0.80


def _font(key: str) -> str:
    path = FONTS.get(key, FONTS["fallback"])
    return path if Path(path).exists() else FONTS["fallback"]


def _text_width(text: str, font_key: str, size: int) -> int:
    try:
        font = ImageFont.truetype(_font(font_key), size)
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0]
    except Exception:
        return size * len(text)  # estimation grossière si PIL échoue


def _split_line(text: str, font_key: str, size: int, max_w: int) -> list[str]:
    """
    Retourne 1 ou 2 lignes selon si le texte rentre.
    Coupe sur le mot le plus proche du milieu si nécessaire.
    """
    if _text_width(text, font_key, size) <= max_w:
        return [text]

    words = text.split()
    if len(words) <= 1:
        return [text]  # 1 seul mot, on ne peut pas couper

    # Cherche la coupure qui équilibre le mieux les deux lignes
    best_cut = len(words) // 2
    best_diff = float("inf")
    for i in range(1, len(words)):
        line1 = " ".join(words[:i])
        line2 = " ".join(words[i:])
        w1 = _text_width(line1, font_key, size)
        w2 = _text_width(line2, font_key, size)
        diff = abs(w1 - w2)
        if max(w1, w2) <= max_w and diff < best_diff:
            best_diff = diff
            best_cut = i

    return [" ".join(words[:best_cut]), " ".join(words[best_cut:])]


def _escape(text: str) -> str:
    return (text
        .replace("\\", "\\\\")
        .replace("'",  "\u2019")
        .replace(":",  "\\:")
        .replace(",",  "\\,")
    )


def _dt(text: str, font_key: str, size: int, y: int, color: str, sx: int = 3, sy: int = 3) -> str:
    f = _font(font_key)
    return (
        f"drawtext=fontfile='{f}':text='{text}':"
        f"fontcolor={color}:fontsize={size}:"
        f"x=(w-text_w)/2:y={y}:"
        f"shadowcolor=black@0.9:shadowx={sx}:shadowy={sy}"
    )


def run(params: dict) -> dict:
    job_id = params.get("job_id", "hist")
    visual_result = params.get("visual_result", {})

    video_path = visual_result.get("video_path", "")
    if not video_path or not Path(video_path).exists():
        raise RuntimeError("video_path manquant — lance d'abord l'agent Visuel")

    # Probe dimensions réelles
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_path],
        capture_output=True, text=True
    )
    probe_data = json.loads(probe.stdout)
    vid_stream = next((s for s in probe_data["streams"] if s["codec_type"] == "video"), {})
    vid_w = int(vid_stream.get("width",  608))
    vid_h = int(vid_stream.get("height", 1080))

    research_result = params.get("research_result", {})
    raw_date  = research_result.get("comm_date",  "").upper()
    raw_title = research_result.get("comm_title", "").upper()
    raw_stat  = research_result.get("comm_stat",  "").upper()

    # ── Tailles cibles (basées sur la hauteur vidéo, cohérentes entre elles)
    # Règle : titre = référence, date = 40% du titre, stat = 70% du titre
    size_title_target = max(80, vid_h // 10)   # ~108px sur 1080p
    size_date_target  = max(36, vid_h // 25)   # ~43px  sur 1080p
    size_stat_target  = max(60, vid_h // 14)   # ~77px  sur 1080p

    # Marge latérale = 6% de chaque côté
    max_w = int(vid_w * 0.88)

    # ── Découpe en lignes si nécessaire (taille FIXE, pas de réduction)
    title_lines = _split_line(raw_title, "bebas",  size_title_target, max_w)
    stat_lines  = _split_line(raw_stat,  "oswald", size_stat_target,  max_w)
    date_lines  = _split_line(raw_date,  "cinzel", size_date_target,  max_w)

    line_gap = int(vid_h * 0.015)   # espacement entre lignes d'un même bloc
    block_gap = int(vid_h * 0.025)  # espacement entre titre et stat

    # ── Hauteur totale du bloc bas (titre + stat)
    title_block_h = len(title_lines) * size_title_target + (len(title_lines) - 1) * line_gap
    stat_block_h  = len(stat_lines)  * size_stat_target  + (len(stat_lines)  - 1) * line_gap
    total_bot_h   = title_block_h + block_gap + stat_block_h

    # Ancre basse : le bloc se termine à SAFE_BOT_RATIO * vid_h
    bot_anchor = int(vid_h * SAFE_BOT_RATIO)
    title_y_start = bot_anchor - total_bot_h

    # ── Positions Y
    y_date = int(vid_h * SAFE_TOP_RATIO)

    # ── Construction des filtres
    filters = []

    # DATE (1 ou 2 lignes, Cinzel, blanc cassé)
    for i, line in enumerate(date_lines):
        y = y_date + i * (size_date_target + line_gap)
        filters.append(_dt(_escape(line), "cinzel", size_date_target, y,
                           color="0xF0E8D8", sx=2, sy=2))

    # TITRE (1 ou 2 lignes, Bebas Neue, blanc)
    for i, line in enumerate(title_lines):
        y = title_y_start + i * (size_title_target + line_gap)
        filters.append(_dt(_escape(line), "bebas", size_title_target, y,
                           color="white", sx=4, sy=4))

    # STAT (1 ou 2 lignes, Oswald, rouge)
    stat_y_start = title_y_start + title_block_h + block_gap
    for i, line in enumerate(stat_lines):
        y = stat_y_start + i * (size_stat_target + line_gap)
        filters.append(_dt(_escape(line), "oswald", size_stat_target, y,
                           color="0xFF4444", sx=3, sy=3))

    vf = ",".join(filters)
    out_path = OUTPUT_DIR / f"{job_id}_final.mp4"

    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-movflags", "+faststart",
        str(out_path)
    ], check=True, capture_output=True)

    public_url = str(out_path).replace(
        "/home/claude-user/tiktok-factory", "https://factorytiktok.duckdns.org"
    )
    return {
        "final_path": str(out_path),
        "final_url": public_url,
    }
