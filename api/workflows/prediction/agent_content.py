"""Agent 1 — Generates content: 3 symbols + short predictions"""
import json
import subprocess
import random
from datetime import date

SYMBOL_POOL = [
    {"symbol": "🌙", "name": "La Lune",        "prompt_style": "crescent moon"},
    {"symbol": "☀️", "name": "Le Soleil",          "prompt_style": "radiant sun"},
    {"symbol": "⭐", "name": "L'Étoile",         "prompt_style": "five-pointed star"},
    {"symbol": "🔮", "name": "L'Oracle",       "prompt_style": "crystal ball"},
    {"symbol": "🌊", "name": "L'Océan",        "prompt_style": "ocean wave"},
    {"symbol": "🔥", "name": "La Flamme",        "prompt_style": "flame"},
    {"symbol": "🌸", "name": "La Fleur",      "prompt_style": "cherry blossom"},
    {"symbol": "🦋", "name": "Le Papillon",    "prompt_style": "butterfly"},
    {"symbol": "⚡", "name": "L'Éclair",    "prompt_style": "lightning bolt"},
    {"symbol": "🌿", "name": "La Feuille",         "prompt_style": "green leaf"},
    {"symbol": "💎", "name": "Le Cristal",      "prompt_style": "diamond crystal"},
    {"symbol": "🗝️", "name": "La Clé",          "prompt_style": "old key"},
    {"symbol": "🌀", "name": "Le Vortex",       "prompt_style": "spiral vortex"},
    {"symbol": "🏔️", "name": "La Montagne",    "prompt_style": "mountain peak"},
    {"symbol": "✨", "name": "Le Ciel Étoilé",    "prompt_style": "starry night sky"},
]

THEMES = [
    "nouveaux débuts et recommencements",
    "relations et connexions humaines",
    "ambition et percées professionnelles",
    "lâcher prise et acceptation",
    "intuition et écoute intérieure",
    "abondance et gratitude",
    "transformation et changement",
    "courage et dépassement de soi",
    "amour et tendresse",
    "clarté et vérité",
    "repos et recharge",
    "créativité et expression personnelle",
    "protection et sécurité",
    "liberté et nouveaux horizons",
]

BANNED_WORDS = [
    "lumière", "chemin", "force intérieure", "univers", "vibration",
    "énergie positive", "belle journée", "chaque pas", "avancer",
    "briller", "s'épanouir", "rayonner", "amour universel"
]

PROMPT = """Tu es un oracle TikTok. Style: sobre, poétique, personnel — s'adressant directement à quelqu'un en le tutoyant (tu, toi, ton, ta, tes).
Aujourd'hui: {date} ({day})
Thème du jour: {theme}
Phase du cycle: jour {cycle_day}/14

RÈGLES IMPORTANTES:
- Chaque prédiction doit être unique et spécifique à son symbole
- Évite absolument ces mots surexploités: {banned_words}
- Les prédictions doivent être concrètes et toucher quelque chose de réel dans la vie quotidienne
- Utilise TOUJOURS le tutoiement (tu, toi, ton, ta, tes) — jamais le vouvoiement
- Le hook doit refléter le thème d'aujourd'hui sans le nommer explicitement
- TOUT le texte DOIT être en français

Les 3 symboles tirés aujourd'hui: {sym1_name} ({sym1}), {sym2_name} ({sym2}), {sym3_name} ({sym3})

Crée un post "Choisissez votre carte". Format JSON strict:
{{
  "hook": "accroche courte et intrigante, sans emoji (max 7 mots)",
  "symbols": [
    {{
      "id": 1,
      "symbol": "{sym1}",
      "name": "{sym1_name}",
      "prompt_style": "{sym1_style}",
      "prediction_title": "titre sobre, sans emoji (max 3 mots)",
      "prediction": "message précis et touchant lié au thème '{theme}', sans emoji (max 18 mots)",
      "energy": "un seul mot captures l'essence de ce symbole aujourd'hui, sans emoji"
    }},
    {{
      "id": 2,
      "symbol": "{sym2}",
      "name": "{sym2_name}",
      "prompt_style": "{sym2_style}",
      "prediction_title": "titre sobre, sans emoji (max 3 mots)",
      "prediction": "message précis et touchant lié au thème '{theme}', sans emoji (max 18 mots)",
      "energy": "un seul mot captures l'essence de ce symbole aujourd'hui, sans emoji"
    }},
    {{
      "id": 3,
      "symbol": "{sym3}",
      "name": "{sym3_name}",
      "prompt_style": "{sym3_style}",
      "prediction_title": "titre sobre, sans emoji (max 3 mots)",
      "prediction": "message précis et touchant lié au thème '{theme}', sans emoji (max 18 mots)",
      "energy": "un seul mot captures l'essence de ce symbole aujourd'hui, sans emoji"
    }}
  ],
  "cta": "invitation courte à commenter son symbole, sans emoji (max 7 mots)"
}}

IMPORTANT: pas d'emoji dans hook, prediction_title, prediction, energy, cta. Réponds UNIQUEMENT avec le JSON."""


def pick_symbols_for_day(day_seed: int) -> list:
    rng = random.Random(day_seed)
    return rng.sample(SYMBOL_POOL, 3)


def get_theme_for_day(day_num: int) -> str:
    return THEMES[day_num % len(THEMES)]


def run(params: dict = None) -> dict:
    today = date.today()
    day_seed = today.toordinal()
    cycle_day = (day_seed % 14) + 1
    theme = get_theme_for_day(day_seed)
    symbols = pick_symbols_for_day(day_seed)

    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    day = days[today.weekday()]

    prompt = PROMPT.format(
        date=today.strftime("%B %d, %Y"),
        day=day,
        theme=theme,
        cycle_day=cycle_day,
        banned_words=", ".join(BANNED_WORDS),
        sym1=symbols[0]["symbol"], sym1_name=symbols[0]["name"], sym1_style=symbols[0]["prompt_style"],
        sym2=symbols[1]["symbol"], sym2_name=symbols[1]["name"], sym2_style=symbols[1]["prompt_style"],
        sym3=symbols[2]["symbol"], sym3_name=symbols[2]["name"], sym3_style=symbols[2]["prompt_style"],
    )

    result = subprocess.run(
        ["/home/claude-user/.local/bin/claude", "--print", "--output-format", "text"],
        input=prompt,
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr}")

    raw = result.stdout.strip()
    if not raw:
        raise RuntimeError(f"Claude CLI returned empty stdout. stderr: {result.stderr!r}")
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    if not raw:
        raise RuntimeError(f"Claude CLI response empty after stripping code block. stdout was: {result.stdout!r}")
    parsed = json.loads(raw)
    data = parsed[0] if isinstance(parsed, list) else parsed
    data["_theme"] = theme
    return data
