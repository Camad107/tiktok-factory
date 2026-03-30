"""
generate.py - Genere les frames de tirage tarot (Montage 2 - pile)

Structure :
  Fond/1.0.png ... 1.3.png    - fonds sequentiels (pile → pile+1 → pile+2 → pile+3)
  positions.json               - positions des slots (genere par detect_slots.py)
  ../deck/1/                   - cartes du deck
  output/                      - frames generees

Usage:
  python generate.py                    # 1 tirage aleatoire
  python generate.py --count 5          # 5 tirages
  python generate.py --seq 1            # sequence specifique
"""

import json
import re
import random
import argparse
import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw

POSITIONS_FILE = "positions.json"
FOND_FOLDER = "Fond"
DECK_FOLDER = "../deck/1"
OUTPUT_FOLDER = "output"
CARD_BACK = "../deck/1/deck_01_Dos_de_carte_brut.jpg"
CORNER_RADIUS = 20


def rounded_mask(size, radius):
    """Cree un masque avec coins arrondis."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return mask


def paste_card(background, card_img, slot_corners, radius=CORNER_RADIUS):
    """Colle une carte sur le slot via transformation perspective."""
    dst_pts = np.array(slot_corners, dtype=np.float32)
    card_rgba = card_img.convert("RGBA")
    card_w, card_h = card_rgba.size

    mask = rounded_mask((card_w, card_h), radius)
    card_np = np.array(card_rgba)
    mask_np = np.array(mask)

    src_pts = np.array([
        [0, 0], [card_w, 0], [card_w, card_h], [0, card_h]
    ], dtype=np.float32)

    bg_np = np.array(background.convert("RGBA"))
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    h_bg, w_bg = bg_np.shape[:2]

    warped_card = cv2.warpPerspective(card_np, M, (w_bg, h_bg),
                                       borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    warped_mask = cv2.warpPerspective(mask_np, M, (w_bg, h_bg),
                                       borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    mask_3ch = warped_mask[:, :, np.newaxis].astype(np.float32) / 255.0
    result = bg_np.astype(np.float32)
    card_f = warped_card.astype(np.float32)

    for ch in range(3):
        result[:, :, ch] = result[:, :, ch] * (1 - mask_3ch[:, :, 0]) + card_f[:, :, ch] * mask_3ch[:, :, 0]

    result = np.clip(result, 0, 255).astype(np.uint8)
    return Image.fromarray(result).convert("RGB")


def load_deck(deck_folder):
    deck_path = Path(deck_folder)
    extensions = {".png", ".jpg", ".jpeg", ".webp"}
    cards = sorted([p for p in deck_path.iterdir()
                     if p.suffix.lower() in extensions and "dos_de_carte" not in p.stem.lower()])
    print(f"Deck : {len(cards)} cartes depuis '{deck_folder}/'")
    return cards


def run(args):
    with open(POSITIONS_FILE) as f:
        config = json.load(f)

    sequences = config.get("sequences", {})

    # Selection de la sequence
    seq_id = args.seq if args.seq else list(sequences.keys())[0]
    if seq_id not in sequences:
        print(f"ERREUR: sequence '{seq_id}' introuvable. Disponibles: {list(sequences.keys())}")
        return

    seq = sequences[seq_id]
    steps = seq["steps"]

    # Nombre de cartes revelees = nombre de steps - 1 (step 0 = pile seule)
    n_cards = len(steps) - 1
    print(f"Sequence {seq_id}: {len(steps)} steps, {n_cards} cartes a reveler")

    deck = load_deck(DECK_FOLDER)
    card_back = Image.open(CARD_BACK)

    if len(deck) < n_cards:
        print(f"ERREUR: {len(deck)} cartes dans le deck, {n_cards} requises.")
        return

    output_dir = OUTPUT_FOLDER

    # Auto-increment du numero de tirage
    Path(output_dir).mkdir(exist_ok=True)
    existing = [f.name for f in Path(output_dir).glob("tirage*") if f.is_file()]
    last_num = 0
    for fname in existing:
        m = re.match(r"tirage(\d+)", fname)
        if m:
            last_num = max(last_num, int(m.group(1)))

    count = args.count
    for t in range(count):
        tirage_num = last_num + t + 1
        hand = random.sample(deck, n_cards)
        hand_names = [p.stem for p in hand]
        print(f"\nTirage {tirage_num}: {hand_names}")

        prefix = f"tirage{tirage_num:02d}"

        for step_idx, step_data in enumerate(steps):
            fond_name = step_data["fond"]
            fond_path = f"{FOND_FOLDER}/{fond_name}"
            background = Image.open(fond_path).convert("RGB")

            slots = step_data["slots"]
            pile_idx = step_data.get("pile_index", 0)
            card_indices = step_data.get("card_indices", [])

            img = background.copy()

            # Coller le dos de carte sur la pile
            if pile_idx < len(slots):
                img = paste_card(img, card_back, slots[pile_idx])

            # Coller les cartes revelees (gauche a droite = arriere vers avant)
            # A ce step, on revele step_idx cartes (step 0 = 0 cartes, step 1 = 1 carte, etc.)
            n_revealed = step_data["step"]
            for i, slot_idx in enumerate(card_indices[:n_revealed]):
                if i < len(hand) and slot_idx < len(slots):
                    card = Image.open(hand[i])
                    img = paste_card(img, card, slots[slot_idx])

            # Nom du fichier
            if step_idx == 0:
                name = f"{prefix}_{step_idx:02d}_pile.jpg"
            else:
                name = f"{prefix}_{step_idx:02d}_carte{step_idx}_{hand_names[step_idx-1]}.jpg"

            path = Path(output_dir) / name
            img.save(path, quality=95)
            print(f"  {path}")

    print(f"\nTermine - frames dans '{output_dir}/'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generateur de frames tarot - Montage 2 (pile)")
    parser.add_argument("--count", type=int, default=1, help="Nombre de tirages (defaut: 1)")
    parser.add_argument("--seq", type=str, help="ID de la sequence (defaut: premiere)")
    args = parser.parse_args()
    run(args)
