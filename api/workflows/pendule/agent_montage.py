"""Agent 3 — Montage final : loop Kling + ralentissement + freeze + texte OUI/NON"""
import subprocess
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path("/home/claude-user/tiktok-factory/output/pendule")
FONTS_DIR = Path("/home/claude-user/tiktok-factory/static/fonts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1080, 1920

# Timings (en secondes dans la vidéo source Kling)
FREEZE_TIME_OUI = 0.5   # pendule à droite
FREEZE_TIME_NON = 2.0   # pendule à gauche

# Durées des segments finaux
LOOP_DURATION = 7.0     # secondes de loop normale
SLOWMO_DURATION = 2.0   # secondes de ralentissement (0.3x speed)
FREEZE_DURATION = 2.0   # secondes de freeze
TEXT_FADE_DURATION = 1.5  # secondes pour l'apparition du texte

TOTAL_DURATION = LOOP_DURATION + SLOWMO_DURATION + FREEZE_DURATION


def load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONTS_DIR / "Cinzel.ttf"), size)
    except Exception:
        return ImageFont.load_default()


def extract_freeze_frame(video_path: str, t: float, out_path: Path):
    """Extrait une frame précise de la vidéo."""
    subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(t),
        "-i", video_path,
        "-vframes", "1",
        "-vf", f"scale={W}:{H}",
        str(out_path),
    ], check=True, capture_output=True)


def make_freeze_clip(frame_path: Path, duration: float, out_path: Path):
    """Crée un clip vidéo à partir d'un freeze frame."""
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(frame_path),
        "-t", str(duration),
        "-vf", f"scale={W}:{H},fps=30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ], check=True, capture_output=True)


def make_text_overlay_frames(freeze_frame_path: Path, answer: str, frames_dir: Path, n_frames: int = 45):
    """Génère des frames avec le texte qui apparaît en fondu (45 frames = 1.5s à 30fps)."""
    frames_dir.mkdir(parents=True, exist_ok=True)
    base = Image.open(freeze_frame_path).convert("RGBA")
    base = base.resize((W, H), Image.LANCZOS)

    font = load_font(200)
    font_sub = load_font(60)

    is_oui = answer.upper() == "OUI"
    color = (80, 220, 100) if is_oui else (220, 70, 70)
    label = "OUI" if is_oui else "NON"

    for i in range(n_frames):
        alpha = int(255 * (i / (n_frames - 1)))  # 0 → 255
        frame = base.copy()
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Texte principal centré verticalement bas
        y_label = H - 500

        # Halo
        halo_alpha = alpha // 3
        for dx, dy in [(-6, 6), (6, 6), (0, 8), (-6, -6), (6, -6)]:
            draw.text(
                (W // 2 + dx - _text_width(draw, label, font) // 2, y_label + dy),
                label, font=font, fill=color + (halo_alpha,)
            )

        # Texte principal
        tw = _text_width(draw, label, font)
        draw.text((W // 2 - tw // 2, y_label), label, font=font, fill=color + (alpha,))

        # Sous-texte
        sub = "Le pendule a parlé" if is_oui else "Le pendule a tranché"
        stw = _text_width(draw, sub, font_sub)
        draw.text(
            (W // 2 - stw // 2, y_label + 220),
            sub, font=font_sub, fill=(220, 220, 220, alpha)
        )

        frame = Image.alpha_composite(frame, overlay)
        frame.convert("RGB").save(str(frames_dir / f"frame_{i:04d}.png"), "PNG")


def _text_width(draw: ImageDraw.Draw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def encode_frames_clip(frames_dir: Path, out_path: Path, fps: int = 30):
    subprocess.run([
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%04d.png"),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}",
        str(out_path),
    ], check=True, capture_output=True)


def concat_clips(clip_paths: list, out_path: Path, tmp_list: Path):
    """Concatène plusieurs clips MP4 avec FFmpeg concat demuxer."""
    tmp_list.write_text("\n".join(f"file '{p}'" for p in clip_paths))
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(tmp_list),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={W}:{H}",
        str(out_path),
    ], check=True, capture_output=True)


def run(params: dict) -> dict:
    job_id = params.get("job_id", "default")
    kling_path = params.get("kling_path") or str(OUTPUT_DIR / f"{job_id}_kling.mp4")
    tmp = OUTPUT_DIR / f"tmp_{job_id}"
    tmp.mkdir(exist_ok=True)

    results = {}

    try:
        for answer in ["oui", "non"]:
            freeze_t = FREEZE_TIME_OUI if answer == "oui" else FREEZE_TIME_NON
            is_oui = answer == "oui"

            # 1. Clip loop normale (LOOP_DURATION secondes, début de la vidéo Kling)
            loop_clip = tmp / f"{answer}_loop.mp4"
            subprocess.run([
                "ffmpeg", "-y",
                "-i", kling_path,
                "-t", str(LOOP_DURATION),
                "-vf", f"scale={W}:{H}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p",
                str(loop_clip),
            ], check=True, capture_output=True)

            # 2. Clip ralentissement (setpts=3.5*PTS = 0.28x speed)
            slowmo_clip = tmp / f"{answer}_slowmo.mp4"
            # On prend 0.57s de la vidéo source autour du freeze_t → ça donne ~2s à 0.28x
            src_slowmo_start = max(0, freeze_t - 0.3)
            subprocess.run([
                "ffmpeg", "-y",
                "-ss", str(src_slowmo_start),
                "-i", kling_path,
                "-t", "0.6",
                "-vf", f"setpts=3.5*PTS,scale={W}:{H}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p",
                str(slowmo_clip),
            ], check=True, capture_output=True)

            # 3. Freeze frame
            freeze_frame = tmp / f"{answer}_freeze.jpg"
            extract_freeze_frame(kling_path, freeze_t, freeze_frame)

            freeze_clip = tmp / f"{answer}_freeze_clip.mp4"
            make_freeze_clip(freeze_frame, FREEZE_DURATION, freeze_clip)

            # 4. Clip texte en fondu (sur le freeze frame)
            text_frames_dir = tmp / f"{answer}_text_frames"
            text_clip = tmp / f"{answer}_text.mp4"
            make_text_overlay_frames(freeze_frame, answer.upper(), text_frames_dir, n_frames=45)
            encode_frames_clip(text_frames_dir, text_clip)

            # 5. Concat tout
            out_path = OUTPUT_DIR / f"{job_id}_{answer}.mp4"
            concat_list = tmp / f"{answer}_concat.txt"
            concat_clips(
                [str(loop_clip), str(slowmo_clip), str(freeze_clip), str(text_clip)],
                out_path,
                concat_list,
            )

            results[answer] = {
                "video_path": str(out_path),
                "video_url": f"/output/pendule/{job_id}_{answer}.mp4",
            }

    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)

    return {
        "videos": results,
        "total_duration_s": round(TOTAL_DURATION + TEXT_FADE_DURATION, 1),
    }
