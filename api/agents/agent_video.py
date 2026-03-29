"""Agent 5 — Assemble la vidéo finale avec ffmpeg"""
import os
import subprocess
import json
import asyncio
from pathlib import Path

OUTPUT_DIR = Path("/home/claude-user/tiktok-factory/output/videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR = Path("/home/claude-user/tiktok-factory/static/assets")


def get_audio_duration(audio_path: str) -> float:
    """Retourne la durée d'un fichier audio en secondes."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", audio_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return 3.0
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        duration = stream.get("duration")
        if duration:
            return float(duration)
    return 3.0


def build_video(job_id: str, images: dict, audio_segments: dict, content: dict) -> str:
    """Assemble la vidéo TikTok complète."""

    # Format TikTok : 1080x1920 (9:16 vertical)
    WIDTH, HEIGHT = 1080, 1920

    # Durées des segments audio
    durations = {}
    for seg_id, audio_path in audio_segments.items():
        durations[seg_id] = get_audio_duration(audio_path)

    # Construction du filtre ffmpeg complexe
    # Structure : intro (cover) → carte 1 → carte 2 → carte 3 → outro

    inputs = []
    filter_parts = []
    audio_parts = []

    # Images disponibles
    img_cover = images.get("cover")
    img_cards = {f"card{i}": images.get(f"card{i}") for i in range(1, 4)}

    # Séquence vidéo
    sequence = [
        ("intro", img_cover, durations.get("intro", 4.0)),
        ("card1", img_cards.get("card1"), durations.get("card1", 6.0)),
        ("card2", img_cards.get("card2"), durations.get("card2", 6.0)),
        ("card3", img_cards.get("card3"), durations.get("card3", 6.0)),
        ("outro", img_cover, durations.get("outro", 3.0)),
    ]

    # Build ffmpeg command with filter_complex
    cmd = ["ffmpeg", "-y"]

    # Add image inputs
    img_idx = 0
    img_map = {}
    for seg_id, img_path, duration in sequence:
        if img_path and Path(img_path).exists():
            cmd += ["-loop", "1", "-t", str(duration), "-i", img_path]
            img_map[seg_id] = img_idx
            img_idx += 1

    # Add audio inputs
    audio_idx = img_idx
    audio_map = {}
    for seg_id, _, _ in sequence:
        audio_path = audio_segments.get(seg_id)
        if audio_path and Path(audio_path).exists():
            cmd += ["-i", audio_path]
            audio_map[seg_id] = audio_idx
            audio_idx += 1

    # Filter complex: scale each image to TikTok format, add fade effects
    filter_complex_parts = []
    video_labels = []
    audio_labels = []

    for i, (seg_id, img_path, duration) in enumerate(sequence):
        if seg_id in img_map:
            v_idx = img_map[seg_id]
            label = f"v{i}"
            # Scale + pad to 1080x1920, add fade in/out
            filter_complex_parts.append(
                f"[{v_idx}:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={WIDTH}:{HEIGHT},"
                f"fade=t=in:st=0:d=0.5,"
                f"fade=t=out:st={duration-0.5}:d=0.5[{label}]"
            )
            video_labels.append(f"[{label}]")

        if seg_id in audio_map:
            audio_labels.append(f"[{audio_map[seg_id]}:a]")

    # Concatenate video
    if video_labels:
        concat_v = "".join(video_labels)
        n = len(video_labels)
        filter_complex_parts.append(f"{concat_v}concat=n={n}:v=1:a=0[outv]")

    # Concatenate audio
    if audio_labels:
        concat_a = "".join(audio_labels)
        n = len(audio_labels)
        filter_complex_parts.append(f"{concat_a}concat=n={n}:v=0:a=1[outa]")

    filter_complex = ";".join(filter_complex_parts)
    cmd += ["-filter_complex", filter_complex]

    if video_labels:
        cmd += ["-map", "[outv]"]
    if audio_labels:
        cmd += ["-map", "[outa]"]

    output_path = str(OUTPUT_DIR / f"{job_id}_final.mp4")
    cmd += [
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr[-500:]}")

    return output_path


def run(params: dict) -> dict:
    job_id = params.get("job_id", "default")
    images = params.get("images", {}).get("images", {})
    audio_segments = params.get("audio_segments", {}).get("audio_segments", {})
    content = params.get("content", {})

    video_path = build_video(job_id, images, audio_segments, content)
    return {"video_path": video_path}
