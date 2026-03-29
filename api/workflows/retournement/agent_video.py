"""Agent 4 — Monte le slideshow vidéo MP4 (4 images + audio) via ffmpeg
Synchro : détection des silences [PAUSE] dans l'audio pour caler les images.
Intro : texte sujet superposé sur la première image.
"""
import json
import subprocess
from pathlib import Path

OUTPUT_DIR = Path("/home/claude-user/tiktok-voyance/output/retournement")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1080, 1920
FADE_DUR = 0.4
MIN_SLIDE_DUR = 3.0
BASE_URL = "https://factorytiktok.duckdns.org"

# Seuil de détection silence (dB) et durée minimale
SILENCE_THRESHOLD = "-35dB"
SILENCE_MIN_DUR = 1.8


def _get_audio_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
        capture_output=True, text=True,
    )
    try:
        probe = json.loads(result.stdout)
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "audio":
                return float(stream.get("duration", 0))
    except Exception:
        pass
    return 0.0


def _detect_silences(audio_path: str) -> list[float]:
    """Détecte les centres des silences dans l'audio, retourne liste de timestamps."""
    result = subprocess.run(
        [
            "ffmpeg", "-i", audio_path,
            "-af", f"silencedetect=noise={SILENCE_THRESHOLD}:d={SILENCE_MIN_DUR}",
            "-f", "null", "-"
        ],
        capture_output=True, text=True,
    )
    output = result.stderr
    starts, ends = [], []
    for line in output.splitlines():
        if "silence_start" in line:
            try:
                starts.append(float(line.split("silence_start:")[1].strip().split()[0]))
            except Exception:
                pass
        if "silence_end" in line:
            try:
                ends.append(float(line.split("silence_end:")[1].strip().split("|")[0].strip()))
            except Exception:
                pass

    # Centre de chaque silence = moment de transition
    transitions = []
    for s, e in zip(starts, ends):
        transitions.append((s + e) / 2)
    return transitions


def run(params: dict) -> dict:
    flux = params.get("flux", {})
    voice = params.get("voice", {})
    content = params.get("content", {})
    job_id = content.get("_job_id", params.get("job_id", "ret_unknown"))

    source_path = flux.get("source_path", "")
    image_A = flux.get("image_A_path", "")
    image_B = flux.get("image_B_path", "")
    image_C = flux.get("image_C_path", "")
    audio_path = voice.get("audio_path", "")

    for label, val in [("source", source_path), ("image_A", image_A), ("image_B", image_B), ("image_C", image_C), ("audio", audio_path)]:
        if not val or not Path(val).exists():
            raise RuntimeError(f"Fichier manquant pour le montage : {label} ({val})")

    audio_dur = voice.get("audio_duration", 0) or _get_audio_duration(audio_path)
    if audio_dur <= 0:
        raise RuntimeError("Durée audio invalide")

    # Sujet pour l'intro texte
    sujet = content.get("_sujet", "").upper()

    # Détecter les silences pour synchro (on attend 4 segments : source / A / B / C)
    transitions = _detect_silences(audio_path)

    # On a besoin de 3 points de transition (entre source→A, A→B, B→C)
    if len(transitions) >= 3:
        t1, t2, t3 = transitions[0], transitions[1], transitions[2]
    elif len(transitions) == 2:
        t1, t2 = transitions[0], transitions[1]
        t3 = audio_dur * 0.75
    elif len(transitions) == 1:
        t1 = transitions[0]
        t3 = audio_dur - 2.0
        t2 = (t1 + t3) / 2
    else:
        # Fallback : répartition équitable
        t1 = audio_dur * 0.25
        t2 = audio_dur * 0.50
        t3 = audio_dur * 0.75

    # Durées de chaque slide
    d0 = max(t1, MIN_SLIDE_DUR)
    d1 = max(t2 - t1, MIN_SLIDE_DUR)
    d2 = max(t3 - t2, MIN_SLIDE_DUR)
    d3 = max(audio_dur - t3, MIN_SLIDE_DUR)

    scale_filter = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"

    # Texte sujet sur la première image (intro)
    # Deux lignes : "LECTURE DU JOUR" et le sujet
    intro_filter = ""
    if sujet:
        intro_filter = (
            f",drawtext=text='LECTURE DU JOUR':fontcolor=white:fontsize=42:x=(w-text_w)/2:y=h*0.12"
            f":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
            f":borderw=2:bordercolor=black@0.8"
            f":enable='between(t,0,{d0})',"
            f"drawtext=text='{sujet}':fontcolor=#FFD700:fontsize=58:x=(w-text_w)/2:y=h*0.12+60"
            f":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
            f":borderw=2:bordercolor=black@0.8"
            f":enable='between(t,0,{d0})'"
        )

    # Offsets xfade cumulatifs
    o1 = d0 - FADE_DUR
    o2 = d0 + d1 - 2 * FADE_DUR
    o3 = d0 + d1 + d2 - 3 * FADE_DUR

    filter_complex = (
        f"[0:v]{scale_filter}{intro_filter}[v0];"
        f"[1:v]{scale_filter}[v1];"
        f"[2:v]{scale_filter}[v2];"
        f"[3:v]{scale_filter}[v3];"
        f"[v0][v1]xfade=transition=fade:duration={FADE_DUR}:offset={o1:.3f}[x01];"
        f"[x01][v2]xfade=transition=fade:duration={FADE_DUR}:offset={o2:.3f}[x12];"
        f"[x12][v3]xfade=transition=fade:duration={FADE_DUR}:offset={o3:.3f}[xout]"
    )

    out_path = OUTPUT_DIR / f"{job_id}_final.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(d0 + 1), "-i", source_path,
        "-loop", "1", "-t", str(d1 + 1), "-i", image_A,
        "-loop", "1", "-t", str(d2 + 1), "-i", image_B,
        "-loop", "1", "-t", str(d3 + 1), "-i", image_C,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[xout]",
        "-map", "4:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-shortest",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error:\n{result.stderr[-1500:]}")

    public_url = str(out_path).replace("/home/claude-user/tiktok-voyance", BASE_URL)

    return {
        "video_path": str(out_path),
        "video_url": public_url,
        "slide_duration": [d0, d1, d2, d3],
        "transitions": [t1, t2, t3],
        "audio_duration": audio_dur,
    }
