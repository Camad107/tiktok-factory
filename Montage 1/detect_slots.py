"""
detect_slots.py - Detecte les 4 coins des cartes vertes (chroma-key)
dans les fonds via detection couleur HSV + affinement des coins.

Usage:
  python detect_slots.py              # detecte tous les fonds dans fond/
  python detect_slots.py "fond 9.png" # detecte un fond specifique
  python detect_slots.py --debug      # sauvegarde une image de debug
"""

import sys
import json
import cv2
import numpy as np
from pathlib import Path

FOND_FOLDER = "fond"
OUTPUT = "positions.json"
MIN_CARD_AREA = 10000
EXPAND_PX = 15


def order_corners(pts):
    """Ordonne les 4 coins : top-left, top-right, bottom-right, bottom-left."""
    pts = pts.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).flatten()

    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(s)]   # top-left
    ordered[2] = pts[np.argmax(s)]   # bottom-right
    ordered[1] = pts[np.argmin(d)]   # top-right
    ordered[3] = pts[np.argmax(d)]   # bottom-left
    return ordered


def refine_corners(gray, corners, search_radius=15):
    """Affine les coins avec cv2.cornerSubPix pour une precision sub-pixel."""
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.01)
    corners_input = corners.reshape(-1, 1, 2).astype(np.float32)
    refined = cv2.cornerSubPix(gray, corners_input, (search_radius, search_radius), (-1, -1), criteria)
    return refined.reshape(-1, 2)


def detect_card_slots(img_path, debug=False):
    img = cv2.imread(str(img_path))
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Detection par couleur verte (chroma-key)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([35, 80, 80])
    upper = np.array([85, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    print(f"  Image : {w}x{h}")

    # Filtrer par surface et ratio
    candidates = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < MIN_CARD_AREA:
            continue
        rect = cv2.minAreaRect(cnt)
        box_w, box_h = rect[1]
        if box_w == 0 or box_h == 0:
            continue
        ratio = min(box_w, box_h) / max(box_w, box_h)
        if 0.35 < ratio < 0.80:
            candidates.append(cnt)
            print(f"    Candidat: area={area:.0f} ratio={ratio:.3f}")

    slots = []
    debug_img = img.copy() if debug else None

    for cnt in candidates:
        # Approximation polygonale avec tolerance progressive
        peri = cv2.arcLength(cnt, True)
        approx = None
        for eps in [0.015, 0.02, 0.025, 0.03, 0.04]:
            a = cv2.approxPolyDP(cnt, eps * peri, True)
            if len(a) == 4:
                approx = a
                break

        if approx is not None and len(approx) == 4:
            corners = order_corners(approx.reshape(4, 2))
        else:
            rect = cv2.minAreaRect(cnt)
            box = cv2.boxPoints(rect)
            corners = order_corners(box)

        # Affinement sub-pixel des coins
        try:
            corners = refine_corners(gray, corners)
        except cv2.error:
            pass

        # Expansion optionnelle
        if EXPAND_PX > 0:
            center = corners.mean(axis=0)
            expanded = np.zeros_like(corners)
            for j in range(4):
                direction = corners[j] - center
                direction = direction / np.linalg.norm(direction)
                expanded[j] = corners[j] + direction * EXPAND_PX
            corners = expanded

        corners_int = np.round(corners).astype(int).tolist()
        slots.append(corners_int)

        w_top = np.linalg.norm(corners[1] - corners[0])
        h_left = np.linalg.norm(corners[3] - corners[0])
        print(f"    -> Slot: coins={corners_int}  ~{w_top:.0f}x{h_left:.0f}px")

        if debug_img is not None:
            pts = np.array(corners_int, dtype=np.int32)
            cv2.polylines(debug_img, [pts], True, (0, 0, 255), 2)
            for j, pt in enumerate(pts):
                cv2.circle(debug_img, tuple(pt), 5, (0, 255, 0), -1)

    # Trier de gauche a droite
    slots.sort(key=lambda s: s[0][0])

    for i, s in enumerate(slots):
        print(f"    Slot {i+1}: {s}")

    if debug_img is not None:
        debug_name = "debug_" + Path(img_path).name
        debug_path = str(Path("output") / debug_name)
        Path("output").mkdir(exist_ok=True)
        cv2.imwrite(debug_path, debug_img)
        print(f"  Debug: {debug_path}")

    return slots, (w, h)


if __name__ == "__main__":
    fond_path = Path(FOND_FOLDER)
    extensions = {".png", ".jpg", ".jpeg", ".webp"}

    debug = "--debug" in sys.argv
    args_clean = [a for a in sys.argv[1:] if a != "--debug"]

    # Charger positions existantes ou creer
    if Path(OUTPUT).exists():
        with open(OUTPUT) as f:
            data = json.load(f)
        if "fonds" not in data:
            data = {"default": None, "fonds": {}}
    else:
        data = {"default": None, "fonds": {}}

    # Determiner quels fonds scanner
    if args_clean:
        targets = [args_clean[0]]
    else:
        targets = sorted([f.name for f in fond_path.iterdir() if f.suffix.lower() in extensions])

    for fond_name in targets:
        img_file = fond_path / fond_name
        if not img_file.exists():
            print(f"ERREUR : {img_file} introuvable")
            continue

        print(f"\n--- {fond_name} ---")
        slots, (w, h) = detect_card_slots(str(img_file), debug=debug)

        data["fonds"][fond_name] = {
            "image_size": [w, h],
            "slots": slots
        }

        if data["default"] is None:
            data["default"] = fond_name

    with open(OUTPUT, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nOK - {len(data['fonds'])} fond(s) dans {OUTPUT}")
