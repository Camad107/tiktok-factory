"""
generate.py - Genere des frames de tirage tarot

Structure attendue:
  fond 1.png          - image de fond (cartes face cachee)
  positions.json      - positions des slots (genere par detect_slots.py)
  deck/               - dossier avec les images de cartes (PNG/JPG)
  output/             - dossier de sortie (cree automatiquement)

Usage:
  python generate.py                         # tirage aleatoire, sequence complete
  python generate.py --count 5              # 5 tirages aleatoires differents
  python generate.py --cards 0 2            # revelee les slots 0 et 2 (index)
  python generate.py --mode all             # toutes les combinaisons possibles
"""

import json
import re
import random
import argparse
import cv2
import numpy as np
from pathlib import Path
from itertools import combinations
from PIL import Image, ImageDraw

POSITIONS_FILE = "positions.json"
FOND_FOLDER = "fond"
DECK_FOLDER = "deck/1"
OUTPUT_FOLDER = "output"
CARD_BACK = "deck/1/deck_01_Dos_de_carte_brut.jpg"
CORNER_RADIUS = 0  # pixels - rayon des coins arrondis (0 = coins droits)


def rounded_mask(size, radius):
    """Cree un masque avec coins arrondis."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, size[0]-1, size[1]-1], radius=radius, fill=255)
    return mask


def fit_card(card_img, slot_w, slot_h, bg_color=(255, 255, 255)):
    """Redimensionne la carte pour tenir entierement dans le slot (contain, sans recadrage).
    Remplit le vide avec bg_color (blanc par defaut)."""
    card_aspect = card_img.width / card_img.height
    slot_aspect = slot_w / slot_h

    if card_aspect > slot_aspect:
        new_w = slot_w
        new_h = int(new_w / card_aspect)
    else:
        new_h = slot_h
        new_w = int(new_h * card_aspect)

    resized = card_img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (slot_w, slot_h), (*bg_color, 255))
    offset_x = (slot_w - new_w) // 2
    offset_y = (slot_h - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))
    return canvas


def paste_card(background, card_img, slot_corners, radius=CORNER_RADIUS):
    """Colle une carte sur le slot via transformation perspective."""
    dst_pts = np.array(slot_corners, dtype=np.float32)

    # Utiliser les dimensions de la carte source directement
    card_rgba = card_img.convert("RGBA")
    card_w, card_h = card_rgba.size

    # Masque coins arrondis a la taille de la carte source
    mask = rounded_mask((card_w, card_h), radius)

    # Convertir en numpy pour OpenCV
    card_np = np.array(card_rgba)
    mask_np = np.array(mask)

    # Points source = les 4 coins de l'image de la carte
    src_pts = np.array([
        [0, 0],
        [card_w, 0],
        [card_w, card_h],
        [0, card_h]
    ], dtype=np.float32)

    # Transformation perspective
    bg_np = np.array(background.convert("RGBA"))
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    h_bg, w_bg = bg_np.shape[:2]

    warped_card = cv2.warpPerspective(card_np, M, (w_bg, h_bg),
                                       borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    warped_mask = cv2.warpPerspective(mask_np, M, (w_bg, h_bg),
                                       borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    # Composer
    mask_3ch = warped_mask[:, :, np.newaxis].astype(np.float32) / 255.0
    result = bg_np.astype(np.float32)
    card_f = warped_card.astype(np.float32)

    # Blending avec le masque
    for ch in range(3):
        result[:, :, ch] = result[:, :, ch] * (1 - mask_3ch[:, :, 0]) + card_f[:, :, ch] * mask_3ch[:, :, 0]

    result = np.clip(result, 0, 255).astype(np.uint8)
    return Image.fromarray(result).convert("RGB")


def load_deck(deck_folder):
    deck_path = Path(deck_folder)
    extensions = {".png", ".jpg", ".jpeg", ".webp"}
    cards = sorted([p for p in deck_path.iterdir()
                     if p.suffix.lower() in extensions and "dos_de_carte" not in p.stem.lower()])
    print(f"Deck charge : {len(cards)} cartes depuis '{deck_folder}/'")
    return cards


def generate_frame(background, card_paths, slots, revealed_indices, card_back_img=None):
    """
    Genere une frame.
    revealed_indices : liste des slots a reveler (0-indexed)
    card_paths : liste des chemins de cartes (une par slot)
    card_back_img : image du dos de carte pour les slots non reveles
    """
    img = background.copy()
    for idx in range(len(slots)):
        if idx in revealed_indices:
            card = Image.open(card_paths[idx])
            img = paste_card(img, card, slots[idx])
        elif card_back_img is not None:
            img = paste_card(img, card_back_img, slots[idx])
    return img


def save_frame(img, output_dir, name):
    Path(output_dir).mkdir(exist_ok=True)
    path = Path(output_dir) / name
    img.save(path, quality=95)
    print(f"  Sauvegarde : {path}")


def list_fonds():
    """Liste les fonds disponibles dans le dossier fond/."""
    fond_path = Path(FOND_FOLDER)
    extensions = {".png", ".jpg", ".jpeg", ".webp"}
    return sorted([f.name for f in fond_path.iterdir() if f.suffix.lower() in extensions])


def run(args):
    # Chargement config
    with open(POSITIONS_FILE) as f:
        config = json.load(f)

    # Liste des fonds
    if args.list_fonds:
        fonds = list_fonds()
        default_fond = config.get("default", "")
        print(f"Fonds disponibles dans '{FOND_FOLDER}/' :")
        for f in fonds:
            marker = " (defaut)" if f == default_fond else ""
            has_slots = " [slots OK]" if f in config.get("fonds", {}) else " [pas de slots]"
            print(f"  - {f}{marker}{has_slots}")
        return

    # Selection du fond
    fond_name = args.fond if args.fond else config.get("default")
    if not fond_name:
        print("ERREUR : aucun fond par defaut. Utilise --fond ou --list-fonds")
        return

    fond_file = f"{FOND_FOLDER}/{fond_name}"
    if not Path(fond_file).exists():
        print(f"ERREUR : fond '{fond_name}' introuvable dans {FOND_FOLDER}/")
        print(f"Fonds disponibles : {', '.join(list_fonds())}")
        return

    fond_config = config.get("fonds", {}).get(fond_name)
    if not fond_config:
        print(f"ERREUR : pas de slots pour '{fond_name}'. Lance : python detect_slots.py \"{fond_name}\"")
        return

    slots = fond_config["slots"]
    n_slots = len(slots)

    background = Image.open(fond_file).convert("RGB")
    card_back = Image.open(CARD_BACK)
    deck = load_deck(DECK_FOLDER)

    if len(deck) < n_slots:
        print(f"ERREUR : {len(deck)} cartes dans le deck, {n_slots} slots requis.")
        return

    output_dir = OUTPUT_FOLDER

    # --- Mode : slots specifiques ---
    if args.cards is not None:
        revealed = [int(i) for i in args.cards]
        hand = random.sample(deck, n_slots)
        frame = generate_frame(background, hand, slots, revealed, card_back)
        name = "custom_" + "_".join(str(i) for i in revealed) + ".jpg"
        save_frame(frame, output_dir, name)
        return

    # --- Mode : toutes les combinaisons ---
    if args.mode == "all":
        hand = random.sample(deck, n_slots)
        for r in range(n_slots + 1):
            for combo in combinations(range(n_slots), r):
                frame = generate_frame(background, hand, slots, list(combo), card_back)
                name = f"combo_{'_'.join(str(i) for i in combo) if combo else 'none'}.jpg"
                save_frame(frame, output_dir, name)
        # Sauvegarde aussi la frame complete
        frame = generate_frame(background, hand, slots, list(range(n_slots)), card_back)
        save_frame(frame, output_dir, "combo_all.jpg")
        return

    # --- Mode : sequence(s) aleatoire(s) ---
    # Detecte le dernier numero de tirage existant dans output/
    existing = [f.name for f in Path(output_dir).glob("tirage*") if f.is_file()]
    last_num = 0
    for fname in existing:
        m = re.match(r"tirage(\d+)", fname)
        if m:
            last_num = max(last_num, int(m.group(1)))

    count = args.count
    for t in range(count):
        tirage_num = last_num + t + 1
        hand = random.sample(deck, n_slots)
        hand_names = [p.stem for p in hand]
        print(f"\nTirage {tirage_num}: {hand_names}")

        prefix = f"tirage{tirage_num:02d}"

        # Frame 0 : toutes cachees (dos de carte)
        Path(output_dir).mkdir(exist_ok=True)
        frame0 = generate_frame(background, hand, slots, [], card_back)
        frame0.save(Path(output_dir) / f"{prefix}_00_cache.jpg", quality=95)
        print(f"  Sauvegarde : {output_dir}/{prefix}_00_cache.jpg")

        # Revelation gauche vers droite
        order = list(range(n_slots))
        revealed = []
        for step, slot_idx in enumerate(order, 1):
            revealed.append(slot_idx)
            frame = generate_frame(background, hand, slots, revealed, card_back)
            name = f"{prefix}_{step:02d}_slot{slot_idx}_{hand_names[slot_idx]}.jpg"
            save_frame(frame, output_dir, name)

    print(f"\nTermine - frames dans '{output_dir}/'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generateur de frames tarot")
    parser.add_argument("--count", type=int, default=1, help="Nombre de tirages aleatoires (defaut: 1)")
    parser.add_argument("--mode", choices=["sequence", "all"], default="sequence")
    parser.add_argument("--cards", nargs="+", help="Indices des slots a reveler (ex: --cards 0 2)")
    parser.add_argument("--fond", type=str, help="Nom du fond a utiliser (ex: --fond 'fond 6.png')")
    parser.add_argument("--list-fonds", action="store_true", help="Liste les fonds disponibles")
    args = parser.parse_args()
    run(args)
