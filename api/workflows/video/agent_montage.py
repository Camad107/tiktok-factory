"""Agent 4 — Monte la vidéo finale avec FFmpeg + transitions xfade"""
import subprocess
import tempfile
from pathlib import Path

OUTPUT_DIR = Path("/home/claude-user/tiktok-voyance/output/video_jobs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1024, 1536
INTRO_DUR = 3      # secondes
REVEAL_DUR = 7     # secondes
FADE_DUR = 0.5     # durée de la transition en secondes


def run(params: dict) -> dict:
    job_id = params.get("job_id", "video")
    overlay_result = params.get("overlay_result", {})
    video_result = params.get("video_result", {})

    intro_path = overlay_result.get("intro_path", "")
    reveal_path = overlay_result.get("reveal_path", "")
    clip_path = video_result.get("video_path", "")

    if not intro_path or not reveal_path or not clip_path:
        raise RuntimeError("Fichiers manquants pour le montage")

    intro_vid = OUTPUT_DIR / f"{job_id}_intro.mp4"
    reveal_vid = OUTPUT_DIR / f"{job_id}_reveal.mp4"
    clip_reenc = OUTPUT_DIR / f"{job_id}_clip_reenc.mp4"
    out_path = OUTPUT_DIR / f"{job_id}_final.mp4"

    # Intro : déjà une vidéo MP4 si généré par agent_overlay, sinon image → vidéo
    if Path(intro_path).suffix != ".mp4":
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", intro_path,
            "-c:v", "libx264", "-t", str(INTRO_DUR), "-pix_fmt", "yuv420p", "-r", "25",
            "-vf", f"scale={W}:{H}", str(intro_vid)
        ], check=True, capture_output=True)
    else:
        # Déjà le bon fichier, pas besoin de re-encoder
        intro_vid = Path(intro_path)

    # Reveal image → vidéo
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", reveal_path,
        "-c:v", "libx264", "-t", str(REVEAL_DUR), "-pix_fmt", "yuv420p", "-r", "25",
        "-vf", f"scale={W}:{H}", str(reveal_vid)
    ], check=True, capture_output=True)

    # Clip Kling → re-encodé au même format
    subprocess.run([
        "ffmpeg", "-y", "-i", clip_path,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2",
        str(clip_reenc)
    ], check=True, capture_output=True)

    # Récupérer la durée réelle du clip
    result = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(clip_reenc)
    ], capture_output=True, text=True)
    import json
    probe = json.loads(result.stdout)
    clip_dur = float(next(s for s in probe["streams"] if s["codec_type"] == "video")["duration"])

    # Transitions xfade :
    # intro → clip  : fade à INTRO_DUR - FADE_DUR
    # clip → reveal : fade à INTRO_DUR + clip_dur - 2*FADE_DUR (offset cumulatif)
    offset1 = INTRO_DUR - FADE_DUR
    offset2 = INTRO_DUR + clip_dur - 2 * FADE_DUR

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(intro_vid),
        "-i", str(clip_reenc),
        "-i", str(reveal_vid),
        "-filter_complex",
        f"[0][1]xfade=transition=fade:duration={FADE_DUR}:offset={offset1}[v01];"
        f"[v01][2]xfade=transition=fade:duration={FADE_DUR}:offset={offset2}[vout]",
        "-map", "[vout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(out_path)
    ], check=True, capture_output=True)

    # Cleanup (ne pas supprimer intro_vid si c'est le fichier source original)
    for f in [reveal_vid, clip_reenc]:
        try:
            f.unlink()
        except:
            pass

    public_url = str(out_path).replace("/home/claude-user/tiktok-voyance", "https://factorytiktok.duckdns.org")
    return {
        "final_path": str(out_path),
        "final_url": public_url,
    }
