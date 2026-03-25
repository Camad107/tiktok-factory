"""Agent 2 — Génère les prompts pour les images des cartes tarot"""
import os
import json
import subprocess

PROMPT_TEMPLATE = """Tu es un expert en génération d'images IA style tarot mystique.

Thème global du tirage : {theme_global}
Cartes :
{cards_info}

Pour chaque carte, génère un prompt en anglais pour Flux/Stable Diffusion qui crée une image de carte tarot.
Style visuel : mystique, sombre et lumineux, or et violet, ambiance bougies, ultra détaillé, style illustration tarot vintage moderne.

Format JSON strictement :
{{
  "cover_prompt": "prompt pour l'image de couverture du TikTok (fond mystérieux avec 3 cartes face cachée, atmosphère tarot)",
  "card_prompts": [
    {{
      "number": 1,
      "prompt": "prompt détaillé en anglais pour la carte 1 révélée (inclure: tarot card illustration, {card1_name}, golden ornate border, mystical symbols, candlelight atmosphere, dark purple and gold, hyper detailed, tarot art style)"
    }},
    {{
      "number": 2,
      "prompt": "prompt détaillé pour carte 2"
    }},
    {{
      "number": 3,
      "prompt": "prompt détaillé pour carte 3"
    }}
  ]
}}

Réponds UNIQUEMENT avec le JSON."""


def run(params: dict) -> dict:
    content = params.get("content", {})
    theme = content.get("theme_global", "voyance")
    cards = content.get("cards", [])

    cards_info = "\n".join([
        f"- Carte {c['number']}: {c['tarot_card']} ({c['energy']})"
        for c in cards
    ])
    card1_name = cards[0]["tarot_card"] if cards else "The Moon"

    prompt = PROMPT_TEMPLATE.format(
        theme_global=theme,
        cards_info=cards_info,
        card1_name=card1_name
    )

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
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)
