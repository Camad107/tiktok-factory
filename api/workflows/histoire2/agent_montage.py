"""Agent 5 — Monte la vidéo finale : overlay date + titre sur la vidéo Runway 10s"""
import subprocess
import json
from pathlib import Path
from PIL import ImageFont

OUTPUT_DIR = Path("/home/claude-user/tiktok-factory/output/histoire2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FONTS = {
    "cinzel":   "/home/claude-user/tiktok-factory/static/fonts/Cinzel-Bold.ttf",
    "liberation": "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "bebas":    "/home/claude-user/tiktok-factory/static/fonts/BebasNeue.ttf",
    "oswald":   "/home/claude-user/tiktok-factory/static/fonts/Oswald-Bold.ttf",
    "fallback": "/usr/share/fonts/truetype/lato/Lato-Black.ttf",
}

SAFE_TOP_RATIO = 0.17
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
        return size * len(text)


def _split_line(text: str, font_key: str, size: int, max_w: int) -> list[str]:
    """Découpe le texte en autant de lignes que nécessaire pour rentrer dans max_w."""
    if _text_width(text, font_key, size) <= max_w:
        return [text]
    words = text.split()
    if len(words) <= 1:
        return [text]
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        if _text_width(test, font_key, size) <= max_w:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines if lines else [text]


def _escape(text: str) -> str:
    return (text
        .replace("\\", "\\\\")
        .replace("'",  "\u2019")
        .replace(":",  "\\:")
        .replace(",",  "\\,")
    )


def _dt(text: str, font_key: str, size: int, y: int, color: str, sx: int = 3, sy: int = 3, align: str = "center", margin: int = 0, start: float = 0, fade: float = 0.5, end: float = None) -> str:
    f = _font(font_key)
    if align == "left":
        x_expr = str(margin)
    else:
        x_expr = "(w-text_w)/2"
    if end is not None:
        fade_out = fade
        fade_out_start = end - fade_out
        alpha = f":alpha='if(lt(t\\,{start})\\,0\\,if(gt(t\\,{end})\\,0\\,if(gt(t\\,{fade_out_start})\\,({end}-t)/{fade_out}\\,min(1\\,(t-{start})/{fade}))))'"
    else:
        alpha = f":alpha='if(lt(t\\,{start})\\,0\\,min(1\\,(t-{start})/{fade}))'"
    return (
        f"drawtext=fontfile='{f}':text='{text}':"
        f"fontcolor={color}:fontsize={size}:"
        f"x={x_expr}:y={y}:"
        f"shadowcolor=black@0.9:shadowx={sx}:shadowy={sy}"
        f"{alpha}"
    )


def run(params: dict) -> dict:
    job_id = params.get("job_id", "hist2")
    visual_result = params.get("visual_result", {})
    research_result = params.get("research_result", {})

    video_path = visual_result.get("video_path", "")
    if not video_path or not Path(video_path).exists():
        raise RuntimeError("video_path manquant — lance d'abord l'agent Visuel")

    # Probe dimensions
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", video_path],
        capture_output=True, text=True
    )
    probe_data = json.loads(probe.stdout)
    vid_stream = next((s for s in probe_data["streams"] if s["codec_type"] == "video"), {})
    vid_w = int(vid_stream.get("width", 608))
    vid_h = int(vid_stream.get("height", 1080))

    # Données
    raw_date = research_result.get("date", "").upper()
    raw_titre = research_result.get("overlay_titre", "").upper()

    # Marge latérale = 6% de chaque côté
    max_w = int(vid_w * 0.88)

    # Taille date
    size_date = max(32, vid_h // 28)

    # Taille titre : on part de grand et on réduit jusqu'à ce que ça tienne en 3 lignes max
    size_titre = 72
    while size_titre > 28:
        test_lines = _split_line(raw_titre, "oswald", size_titre, max_w)
        if len(test_lines) <= 3:
            break
        size_titre -= 4

    date_lines = _split_line(raw_date, "liberation", size_date, max_w)
    titre_lines = _split_line(raw_titre, "oswald", size_titre, max_w)

    line_gap = int(vid_h * 0.015)

    # Hauteur du bloc titre
    titre_block_h = len(titre_lines) * size_titre + (len(titre_lines) - 1) * line_gap

    # Ancre : le titre se termine à SAFE_BOT_RATIO * vid_h
    bot_anchor = int(vid_h * SAFE_BOT_RATIO)
    titre_y_start = bot_anchor - titre_block_h

    # Date en haut (safe zone)
    y_date = int(vid_h * SAFE_TOP_RATIO)

    filters = []

    margin_left = int(vid_w * 0.06)

    # Durée totale après slowdown : ~12s
    total_dur = 12.0

    # DATE (Liberation Serif Bold, blanc cassé, haut, fade-in dès 0s, fade-out à la fin)
    for i, line in enumerate(date_lines):
        y = y_date + i * (size_date + line_gap)
        filters.append(_dt(_escape(line), "liberation", size_date, y,
                           color="0xF0E8D8", sx=2, sy=2, align="left", margin=margin_left,
                           start=0.0, fade=0.5, end=total_dur))

    # TITRES OVERLAY (Oswald Bold, blanc, bas, séquentiels)
    extra_titres = [
        "30 MORTS, 140 BLESSÉS : DES SURVIVANTS DE LA SHOAH TUÉS",
        "48H APRÈS, OFFENSIVE ISRAÉLIENNE EN CISJORDANIE, RAMALLAH ASSIÉGÉE",
    ]
    all_titres = [raw_titre] + extra_titres

    # Trouver la taille unique qui fait rentrer TOUS les titres en 3 lignes max
    common_size = size_titre
    while common_size > 28:
        all_fit = all(len(_split_line(t, "oswald", common_size, max_w)) <= 3 for t in all_titres)
        if all_fit:
            break
        common_size -= 4

    titre_start = 1.0
    available = total_dur - titre_start
    dur_per_titre = available / len(all_titres)

    for t_idx, titre_text in enumerate(all_titres):
        t_start = titre_start + t_idx * dur_per_titre
        t_end = t_start + dur_per_titre
        t_lines = _split_line(titre_text, "oswald", common_size, max_w)
        t_block_h = len(t_lines) * common_size + (len(t_lines) - 1) * line_gap
        t_y_start = bot_anchor - t_block_h
        for i, line in enumerate(t_lines):
            y = t_y_start + i * (common_size + line_gap)
            filters.append(_dt(_escape(line), "oswald", common_size, y,
                               color="white", sx=4, sy=4, align="left", margin=margin_left,
                               start=t_start, fade=0.4, end=t_end))

    vf = "setpts=PTS/0.83," + ",".join(filters)
    out_path = OUTPUT_DIR / f"{job_id}_final.mp4"

    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf,
        "-an",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-movflags", "+faststart",
        str(out_path)
    ], check=True, capture_output=True)

    raw_video_url = video_path.replace("/home/claude-user/tiktok-factory", "")
    final_url = str(out_path).replace("/home/claude-user/tiktok-factory", "")
    return {
        "final_path": str(out_path),
        "final_url": final_url,
        "raw_video_url": raw_video_url,
        "overlay_date": raw_date,
        "overlay_titre": raw_titre,
    }
