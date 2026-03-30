"""Agent 2 — Génère les 3 prompts Flux Kontext à partir du contenu (cartes tirées)"""

CARD_STYLE = "minimalist vintage engraving tarot style, beige parchment background, gold fine linework"

PROMPT_TEMPLATE = (
    "Edit only the {position} tarot card in this image. "
    "IMPORTANT: Keep the exact same camera angle, zoom level, framing and perspective as the input image — do not zoom in or out, do not reframe, do not crop differently. "
    "The output must look pixel-identical to the input except for the {position} card. "
    "Do not move, resize, rotate or alter the other two cards. "
    "Do not change the table surface, background, lighting, shadows, candles, crystals or any prop. "
    "Only replace the {position} card's plain back with the illustrated front face of \"{nom}\": {visuel}. "
    "The card title \"{nom}\" is printed at the bottom in serif gold letters on a dark band. "
    "Illustration style: {card_style}. "
    "The card is fully face-up, flat on the table, completely still, not mid-flip{reversed_note}."
)


def _build_prompt(position: str, nom: str, visuel: str, sens: str) -> str:
    reversed_note = ". The illustration is rotated 180 degrees (card is reversed)" if sens == "inversé" else ""
    return PROMPT_TEMPLATE.format(
        position=position,
        nom=nom,
        visuel=visuel,
        reversed_note=reversed_note,
        card_style=CARD_STYLE,
    )


def run(params: dict) -> dict:
    content = params.get("content", {})
    cartes = content.get("cartes", [])

    if len(cartes) < 3:
        raise RuntimeError("Agent content requis — 3 cartes manquantes")

    c1, c2, c3 = cartes[0], cartes[1], cartes[2]

    prompt_A = _build_prompt("left",   c1.get("nom", ""), c1.get("visuel", c1.get("nom", "")), c1.get("sens", "endroit"))
    prompt_B = _build_prompt("center", c2.get("nom", ""), c2.get("visuel", c2.get("nom", "")), c2.get("sens", "endroit"))
    prompt_C = _build_prompt("right",  c3.get("nom", ""), c3.get("visuel", c3.get("nom", "")), c3.get("sens", "endroit"))

    return {
        "card_style": CARD_STYLE,
        "prompt_A": prompt_A,
        "prompt_B": prompt_B,
        "prompt_C": prompt_C,
        "cartes": [
            {"nom": c1.get("nom"), "sens": c1.get("sens"), "position": c1.get("position")},
            {"nom": c2.get("nom"), "sens": c2.get("sens"), "position": c2.get("position")},
            {"nom": c3.get("nom"), "sens": c3.get("sens"), "position": c3.get("position")},
        ],
    }
