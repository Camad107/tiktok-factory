# Montage 1 — Procédure de génération

## Ce qui a été fait

### 1. Choix du fond
Plusieurs fonds ont été générés par IA (fond 1 à 7) avec le prompt suivant comme base :
```
Portrait format 4:5, dark charcoal linen fabric texture, flat lay top-down view,
three vertical blank tarot card placeholders in a horizontal row,
each card slot proportioned exactly 47 units wide by 87 units tall,
cream parchment colored rectangles with thin golden border,
rounded corners, soft even diffused lighting, centered composition,
equal spacing between cards, photorealistic, minimal
```

**Fond retenu : `fond 5.png`** — meilleur ratio slots/cartes (écart 3.3% vs ratio cible 0.5402).

| Fond | Ratio slots | Écart |
|------|-------------|-------|
| fond 5 | 0.5579 | **3.3%** ✓ |
| fond 7 | 0.5132 | 5.0% |
| fond 6 | 0.4865 | 9.9% |

---

### 2. Détection automatique des slots (`detect_slots.py`)
Le script analyse l'image de fond par seuillage de luminosité :
- Les cartes (crème ~220 de luminosité) se détachent du fond sombre (~50)
- Les plages de colonnes claires sont détectées puis fusionnées (gap < 15px)
- Les coordonnées des 4 coins de chaque slot sont sauvegardées dans `positions.json`

**Résultat pour fond 5 :**
```
Slot 1 : x=73-333  y=487-953  (260x466px)
Slot 2 : x=380-640 y=487-953  (260x466px)
Slot 3 : x=688-948 y=487-953  (260x466px)
```

---

### 3. Compositing des cartes (`generate.py`)
Pour chaque frame, le script :
1. Charge le fond et les cartes du dossier `deck/`
2. Pioche aléatoirement N cartes (sans remise)
3. Pour chaque slot révélé :
   - Redimensionne la carte en mode **contain** (carte entière visible, sans recadrage)
   - Remplit le vide avec la **couleur du bord de la carte** (échantillonnée aux 4 coins)
   - Applique un masque à **coins arrondis** (rayon 18px)
   - Colle sur le fond
4. Sauvegarde les frames numérotées dans `output/`

**Ordre de révélation : gauche → droite** (slot 0, 1, 2)

---

## Structure des fichiers

```
Montage 1/
├── fond 5.png              ← image de fond retenue
├── positions.json          ← coordonnées des slots (auto-généré)
├── deck/                   ← cartes du deck (PNG/JPG)
│   ├── deck_01_la_tour.png
│   ├── deck_01_la_justice.png
│   └── ...
├── output/                 ← frames générées
│   ├── tirage01_00_cache.jpg
│   ├── tirage01_01_slot0_...jpg
│   ├── tirage01_02_slot1_...jpg
│   └── tirage01_03_slot2_...jpg
├── detect_slots.py         ← détection des positions
├── generate.py             ← générateur de frames
└── README.md               ← ce fichier
```

---

## Procédure complète

### Première fois (ou nouveau fond)
```bash
# 1. Mettre le fond dans le dossier
# 2. Modifier BACKGROUND dans detect_slots.py
# 3. Détecter les slots
python detect_slots.py

# 4. Mettre les cartes du deck dans deck/
# 5. Générer
python generate.py
```

### Générations suivantes
```bash
# 1 tirage aléatoire (séquence de 4 frames)
python generate.py

# N tirages d'un coup
python generate.py --count 5

# Révéler des slots précis (index 0, 1, 2)
python generate.py --cards 0 2

# Toutes les combinaisons possibles
python generate.py --mode all
```

### Changer de fond
```bash
# 1. Modifier BACKGROUND dans detect_slots.py
# 2. Relancer la détection
python detect_slots.py
# 3. Générer normalement
python generate.py
```

---

## Cartes du deck

- Format : PNG ou JPG
- Ratio attendu : **47:87** (0.5402) — ratio Rider-Waite
- Nommage libre, les cartes sont triées alphabétiquement
- Minimum : autant de cartes que de slots (3 pour ce fond)

---

## Paramètres ajustables dans `generate.py`

| Paramètre | Valeur | Rôle |
|-----------|--------|------|
| `CORNER_RADIUS` | 18px | Arrondi des coins des cartes |
| `DECK_FOLDER` | `deck` | Dossier des cartes |
| `OUTPUT_FOLDER` | `output` | Dossier de sortie |
