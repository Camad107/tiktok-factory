"""Agent 1 — Génère l'intro, le thème global et les 3 cartes tarot du jour"""
import os
import json
import subprocess
from datetime import date

PROMPT_TEMPLATE = """Tu es un oracle mystique spécialisé dans le tarot TikTok.
Aujourd'hui c'est le {date}.

Génère un contenu "Pick a Card" pour TikTok sur le thème de la voyance/tarot.
Format de réponse JSON strictement :
{{
  "intro_text": "texte d'accroche mystérieux pour TikTok (2-3 phrases max, style hypnotique)",
  "theme_global": "thème du tirage du jour (ex: amour, carrière, changements...)",
  "cards": [
    {{
      "number": 1,
      "label": "Carte 1 — [nom mystérieux]",
      "tarot_card": "nom de la carte tarot (ex: La Lune, Le Soleil, La Tour...)",
      "prediction": "prédiction de 3-4 phrases pour ceux qui choisissent cette carte, style mystique et positif",
      "energy": "mot clé énergétique (ex: Renaissance, Abondance, Clarté...)"
    }},
    {{
      "number": 2,
      "label": "Carte 2 — [nom mystérieux]",
      "tarot_card": "nom de la carte tarot",
      "prediction": "prédiction de 3-4 phrases",
      "energy": "mot clé énergétique"
    }},
    {{
      "number": 3,
      "label": "Carte 3 — [nom mystérieux]",
      "tarot_card": "nom de la carte tarot",
      "prediction": "prédiction de 3-4 phrases",
      "energy": "mot clé énergétique"
    }}
  ],
  "outro_text": "phrase finale mystérieuse invitant à commenter quelle carte ils choisissent"
}}

Réponds UNIQUEMENT avec le JSON, aucun autre texte."""


def run(params: dict = None) -> dict:
    today = date.today().strftime("%d %B %Y")
    prompt = PROMPT_TEMPLATE.format(date=today)

    result = subprocess.run(
        ["/home/claude-user/.local/bin/claude", "--print", "--output-format", "text"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr}")

    raw = result.stdout.strip()
    # Nettoyer les balises markdown si présentes
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)
    return data
