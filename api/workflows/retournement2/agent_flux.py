"""Agent — Compositing local opencv/PIL (remplace Flux Kontext)
Génère 4 images : source (tout caché), A (1 révélée), B (2 révélées), C (3 révélées)
"""
import cv2
import json
import random
import unicodedata
import re
import numpy as np
from pathlib import Path
from PIL import Image

MONTAGE_DIR = Path("/home/claude-user/tiktok-factory/Montage 1")
FOND_DIR    = MONTAGE_DIR / "Fond"
DECK_DIR    = MONTAGE_DIR / "deck" / "1"
POSITIONS_FILE = MONTAGE_DIR / "positions.json"
OUTPUT_DIR  = Path("/home/claude-user/tiktok-factory/output/retournement2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BASE_URL = "https://factorytiktok.duckdns.org"
W, H = 1080, 1920

ALIASES = {
    "le_bateleur": "le_magicien",
}


def _normalize(s):
    s = unicodedata.normalize("NFD", s)
    s = s.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "_", s.lower()).strip("_")


def _find_card_path(nom):
    target = _normalize(nom)
    target = ALIASES.get(target, target)
    for f in DECK_DIR.glob("*.jpg"):
        if "dos_de_carte" in f.name.lower():
            continue
        if target in _normalize(f.stem):
            return f
    words = [w for w in target.split("_") if len(w) > 2]
    best, best_score = None, 0
    for f in DECK_DIR.glob("*.jpg"):
        if "dos_de_carte" in f.name.lower():
            continue
        stem = _normalize(f.stem)
        score = sum(1 for w in words if w in stem)
        if score > best_score:
            best, best_score = f, score
    return best


def _dos_path():
    return DECK_DIR / "deck_01_Dos_de_carte_brut.jpg"


def _paste_card_cv2(bg_pil, card_path, slot_corners):
    bg = np.array(bg_pil.convert("RGB"))
    card_bgr = cv2.imread(str(card_path))
    ch, cw = card_bgr.shape[:2]

    src_pts = np.float32([[0, 0], [cw, 0], [cw, ch], [0, ch]])
    dst_pts = np.float32(slot_corners)

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    bh, bw = bg.shape[:2]

    card_rgb = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2RGB)
    warped = cv2.warpPerspective(card_rgb, M, (bw, bh))

    mask_src = np.ones((ch, cw), dtype=np.uint8) * 255
    mask_warped = cv2.warpPerspective(mask_src, M, (bw, bh))
    mask_3ch = cv2.merge([mask_warped, mask_warped, mask_warped])

    result = np.where(mask_3ch > 0, warped, bg)
    return Image.fromarray(result.astype(np.uint8))


def _resize_tiktok(img):
    ratio = max(W / img.width, H / img.height)
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    l, t = (nw - W) // 2, (nh - H) // 2
    return img.crop((l, t, l + W, t + H))


def _to_url(path):
    return str(path).replace("/home/claude-user/tiktok-factory", BASE_URL)


def run(params):
    content = params.get("content", {})
    job_id  = content.get("_job_id", params.get("job_id", "ret2_unknown"))
    seed    = content.get("_seed", 0)
    cartes  = content.get("cartes", [])
    if len(cartes) < 3:
        raise RuntimeError("3 cartes requises")

    positions = json.loads(POSITIONS_FILE.read_text())
    fonds = list(positions["fonds"].keys())
    fond_name = random.Random(seed).choice(fonds)
    fond_path = FOND_DIR / fond_name
    slots = positions["fonds"][fond_name]["slots"]

    card_paths = []
    for c in cartes[:3]:
        p = _find_card_path(c.get("nom", ""))
        if p is None:
            raise RuntimeError(f"Carte introuvable dans le deck : {c.get('nom')}")
        card_paths.append(p)
    dos = _dos_path()

    def make_frame(revealed_count):
        bg = Image.open(fond_path).convert("RGB")
        for i, slot in enumerate(slots[:3]):
            card = card_paths[i] if i < revealed_count else dos
            bg = _paste_card_cv2(bg, card, slot)
        return _resize_tiktok(bg)

    frames = {
        "source": make_frame(0),
        "A":      make_frame(1),
        "B":      make_frame(2),
        "C":      make_frame(3),
    }

    paths = {}
    for key, img in frames.items():
        p = OUTPUT_DIR / f"{job_id}_{key}.jpg"
        img.save(str(p), "JPEG", quality=92)
        paths[key] = p

    return {
        "source_path":  str(paths["source"]),
        "source_url":   _to_url(paths["source"]),
        "image_A_path": str(paths["A"]),
        "image_A_url":  _to_url(paths["A"]),
        "image_B_path": str(paths["B"]),
        "image_B_url":  _to_url(paths["B"]),
        "image_C_path": str(paths["C"]),
        "image_C_url":  _to_url(paths["C"]),
        "fond": fond_name,
    }
