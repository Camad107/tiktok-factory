"""
detect_slots.py - Detecte les slots dans les fonds de Montage 2
Multi-seuil + split par coins externes pour cartes qui se chevauchent.

Usage:
  python detect_slots.py              # detecte tous les fonds
  python detect_slots.py --debug      # sauvegarde images de debug
"""

import sys
import json
import cv2
import numpy as np
from pathlib import Path

FOND_FOLDER = "Fond"
OUTPUT = "positions.json"
MIN_CARD_AREA = 5000
CARD_RATIO = 0.54  # largeur/hauteur d'une carte tarot


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
    """Affine les coins avec cv2.cornerSubPix."""
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.01)
    corners_input = corners.reshape(-1, 1, 2).astype(np.float32)
    refined = cv2.cornerSubPix(gray, corners_input, (search_radius, search_radius), (-1, -1), criteria)
    return refined.reshape(-1, 2)


def split_merged_blob(contour):
    """Split un blob de 2 cartes fusionnees en 2 quadrilateres via coins externes + ratio."""
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.03 * peri, True)
    pts = approx.reshape(-1, 2).astype(np.float32)

    if len(pts) < 4:
        return None

    # Ordonner les coins externes du blob
    corners = order_corners(pts[:4] if len(pts) == 4 else pts)
    tl, tr, br, bl = corners[0], corners[1], corners[2], corners[3]

    # Si plus de 4 points, trouver les 4 extremes
    if len(pts) > 4:
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1).flatten()
        tl = pts[np.argmin(s)]
        br = pts[np.argmax(s)]
        tr = pts[np.argmin(d)]
        bl = pts[np.argmax(d)]

    # Carte gauche : utilise le bord gauche (TL-BL) + ratio
    left_edge = bl - tl
    left_h = np.linalg.norm(left_edge)
    left_dir = left_edge / left_h
    perp_right = np.array([left_dir[1], -left_dir[0]])
    card_w_left = left_h * CARD_RATIO

    tr_left = tl + perp_right * card_w_left
    br_left = bl + perp_right * card_w_left
    card_left = np.array([tl, tr_left, br_left, bl], dtype=np.float32)

    # Carte droite : utilise le bord droit (TR-BR) + ratio
    right_edge = br - tr
    right_h = np.linalg.norm(right_edge)
    right_dir = right_edge / right_h
    perp_left = np.array([-right_dir[1], right_dir[0]])
    card_w_right = right_h * CARD_RATIO

    tl_right = tr + perp_left * card_w_right
    bl_right = br + perp_left * card_w_right
    card_right = np.array([tl_right, tr, br, bl_right], dtype=np.float32)

    return [card_left, card_right]


def detect_card_slots(img_path, expected_cards=None, debug=False):
    """Detecte les slots dans une image de fond."""
    img = cv2.imread(str(img_path))
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

    # Multi-seuil : essayer des seuils croissants jusqu'a obtenir le bon nombre
    best_contours = []
    best_threshold = 145

    for thr in [145, 170, 190, 200, 210]:
        _, thresh = cv2.threshold(blurred, thr, 255, cv2.THRESH_BINARY)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        valid = [c for c in contours if cv2.contourArea(c) > MIN_CARD_AREA]

        if expected_cards and len(valid) == expected_cards:
            best_contours = valid
            best_threshold = thr
            break

        if len(valid) >= len(best_contours):
            best_contours = valid
            best_threshold = thr

        if expected_cards and len(valid) > expected_cards:
            break

    print(f"  Image : {w}x{h}")
    print(f"  Seuil retenu : {best_threshold}, {len(best_contours)} blobs")

    # Si pas assez de blobs, splitter les gros
    if expected_cards and len(best_contours) < expected_cards:
        # Estimer la taille d'une carte
        areas = [cv2.contourArea(c) for c in best_contours]
        est_card_area = min(areas) if areas else 70000

        new_contours = []
        for cnt in best_contours:
            area = cv2.contourArea(cnt)
            if area > est_card_area * 1.4:
                print(f"    Blob fusionne (area={area:.0f}), split par coins externes...")
                cards = split_merged_blob(cnt)
                if cards:
                    for card_corners in cards:
                        # Creer un contour dummy a partir des 4 coins
                        new_contours.append(("corners", card_corners))
                    print(f"    -> Split en {len(cards)} cartes")
                else:
                    new_contours.append(("contour", cnt))
                    print(f"    -> Split echoue")
            else:
                new_contours.append(("contour", cnt))
    else:
        new_contours = [("contour", c) for c in best_contours]

    # Convertir en quadrilateres
    slots = []
    debug_img = img.copy() if debug else None

    for item_type, item in new_contours:
        if item_type == "corners":
            # Deja un quadrilatere
            corners = item
        else:
            # Contour -> minAreaRect
            rect = cv2.minAreaRect(item)
            box = cv2.boxPoints(rect)
            corners = order_corners(box)

        try:
            corners = refine_corners(gray, corners)
        except Exception:
            pass

        corners_int = np.round(corners).astype(int).tolist()
        slots.append(corners_int)

        w_top = np.linalg.norm(corners[1] - corners[0])
        h_left = np.linalg.norm(corners[3] - corners[0])
        print(f"    -> Slot: ~{w_top:.0f}x{h_left:.0f}px")

        if debug_img is not None:
            pts = np.array(corners_int, dtype=np.int32)
            cv2.polylines(debug_img, [pts], True, (0, 0, 255), 2)
            for pt in pts:
                cv2.circle(debug_img, tuple(pt), 5, (0, 255, 0), -1)

    # Trier : pile en haut (centre_y min), puis cartes par centre_x (gauche a droite)
    slots.sort(key=lambda s: sum(p[1] for p in s) / 4)
    if len(slots) > 1:
        pile = slots[0]
        cards = sorted(slots[1:], key=lambda s: sum(p[0] for p in s) / 4)
        slots = [pile] + cards

    for i, s in enumerate(slots):
        center_y = sum(p[1] for p in s) / 4
        center_x = sum(p[0] for p in s) / 4
        label = "PILE" if i == 0 else f"CARTE {i}"
        print(f"    {label}: center=({center_x:.0f},{center_y:.0f})")

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

    all_fonds = sorted([f.name for f in fond_path.iterdir() if f.suffix.lower() in extensions])

    # Grouper par sequence
    sequences = {}
    for fname in all_fonds:
        stem = Path(fname).stem
        parts = stem.split(".")
        if len(parts) == 2:
            seq_id = parts[0]
            step = int(parts[1])
            if seq_id not in sequences:
                sequences[seq_id] = []
            sequences[seq_id].append((step, fname))

    for seq_id in sequences:
        sequences[seq_id].sort(key=lambda x: x[0])

    data = {"sequences": {}}

    for seq_id, steps in sequences.items():
        print(f"\n=== Sequence {seq_id} ===")
        seq_data = {"steps": []}

        for step_num, fond_name in steps:
            img_file = fond_path / fond_name
            expected = step_num + 1
            print(f"\n--- {fond_name} (step {step_num}, attendu: {expected} slots) ---")
            slots, (w, h) = detect_card_slots(str(img_file), expected_cards=expected, debug=debug)

            step_data = {
                "fond": fond_name,
                "step": step_num,
                "image_size": [w, h],
                "slots": slots
            }

            if len(slots) > 0:
                step_data["pile_index"] = 0
                step_data["card_indices"] = list(range(1, len(slots)))

            seq_data["steps"].append(step_data)

        data["sequences"][seq_id] = seq_data

    with open(OUTPUT, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nOK - {len(data['sequences'])} sequence(s) dans {OUTPUT}")
