"""Agent 2 — Crée la vidéo loopable du pendule (Pillow + FFmpeg)"""
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT_DIR = Path("/home/claude-user/tiktok-factory/output/pendule")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1080, 1920
BG_COLOR = (0, 0, 0)  # Noir pur, identique au fond de l'image source

# Paramètres animation
FPS = 30
N_CYCLES = 5            # 5 cycles → loop parfaite de 12s
T_PERIOD = 2.4          # secondes par cycle complet
ANGLE_MAX = 28.0        # degrés d'oscillation max
FRAMES_PER_CYCLE = int(FPS * T_PERIOD)   # 72 frames exactement
N_FRAMES = FRAMES_PER_CYCLE * N_CYCLES   # 360 frames = 12s (frame 0 = frame 360)

# Taille du pendule dans la vidéo (centré, occupe toute la hauteur utile)
PEND_DISPLAY_W = 700
PEND_DISPLAY_H = 1600


def prepare_pendulum(image_path: str):
    """Charge l'image source et la recadre pour l'animation.
    Retourne (pendulum_rgba, pad) où pad est le padding latéral ajouté."""
    img = Image.open(image_path).convert("RGBA")

    # Scale pour remplir PEND_DISPLAY_W × PEND_DISPLAY_H
    ratio = max(PEND_DISPLAY_W / img.width, PEND_DISPLAY_H / img.height)
    nw = int(img.width * ratio)
    nh = int(img.height * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)

    # Crop : garder le haut (point d'attache chaîne) et centrer horizontalement
    left = (nw - PEND_DISPLAY_W) // 2
    img = img.crop((left, 0, left + PEND_DISPLAY_W, PEND_DISPLAY_H))

    # Padding latéral en noir pour absorber la rotation (sin(28°) × 1600 ≈ 750px)
    PAD = 400
    padded = Image.new("RGBA", (PEND_DISPLAY_W + 2 * PAD, PEND_DISPLAY_H), BG_COLOR + (255,))
    padded.paste(img, (PAD, 0))
    return padded, PAD


def get_angle(frame_idx: int) -> float:
    """Oscillation sinusoïdale. frame 0 = frame N_FRAMES (loop parfaite)."""
    t = frame_idx / FPS
    return ANGLE_MAX * math.sin(2 * math.pi * t / T_PERIOD)


def render_frame(bg: Image.Image, pendulum: Image.Image, frame_idx: int) -> Image.Image:
    """Génère une frame — fond uni + pendule tourné, aucun texte."""
    frame = bg.copy()
    angle = get_angle(frame_idx)

    # Rotation autour du pivot haut-centre (point d'attache de la chaîne)
    pivot_x = pendulum.width // 2
    rotated = pendulum.rotate(
        -angle,
        center=(pivot_x, 0),
        expand=False,
        resample=Image.BICUBIC,
        fillcolor=BG_COLOR + (255,),  # remplir les zones vides avec le même noir
    )

    # Coller au centre horizontalement, en haut verticalement
    paste_x = (W - pendulum.width) // 2
    paste_y = 60
    frame.paste(rotated, (paste_x, paste_y), rotated)

    return frame


def generate_frames(bg: Image.Image, pendulum: Image.Image, frames_dir: Path):
    frames_dir.mkdir(parents=True, exist_ok=True)
    for i in range(N_FRAMES):
        frame = render_frame(bg, pendulum, i)
        frame.convert("RGB").save(str(frames_dir / f"frame_{i:04d}.png"), "PNG")
        if i % 30 == 0:
            print(f"  frame {i}/{N_FRAMES}")


def encode_video(frames_dir: Path, output_path: Path):
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", str(frames_dir / "frame_%04d.png"),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={W}:{H}",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def run(params: dict) -> dict:
    job_id = params.get("job_id", "default")
    image_path = params.get("image_path") or (
        params.get("image", {}) or {}
    ).get("image_path")

    if not image_path:
        raise ValueError("image_path manquant dans les params")

    frames_dir = OUTPUT_DIR / f"frames_{job_id}"
    output_path = OUTPUT_DIR / f"{job_id}_loop.mp4"
    duration = round(N_FRAMES / FPS, 1)

    try:
        bg = Image.new("RGBA", (W, H), BG_COLOR + (255,))
        pendulum, _ = prepare_pendulum(image_path)
        generate_frames(bg, pendulum, frames_dir)
        encode_video(frames_dir, output_path)
    finally:
        if frames_dir.exists():
            shutil.rmtree(frames_dir, ignore_errors=True)

    return {
        "video_path": str(output_path),
        "video_url": f"/output/pendule/{job_id}_loop.mp4",
        "duration_s": duration,
        "fps": FPS,
        "frames": N_FRAMES,
        "cycles": N_CYCLES,
    }
