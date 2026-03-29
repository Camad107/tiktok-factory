"""Agent 2 — Fact-check + données de communication (visuel, ambiance, script)"""
import json
import subprocess


PROMPT_TEMPLATE = """Tu es un journaliste d'investigation spécialisé dans les faits historiques viraux.

Événement : {title} ({year})
Date EXACTE de l'événement : {exact_date}
Hook : {hook}
Catégorie : {category}

RÈGLE ABSOLUE : Tous tes faits et ta comm_date DOIVENT se référer à cet événement précis du {exact_date}. N'invente pas une date approchante. Si tu mentionnes une date, c'est {exact_date}.

─── PARTIE 1 : FACT-CHECK ───
3 faits précis et vérifiés, avec chiffres ou détails concrets. Angle : choc, indignation, ou mystère.

─── PARTIE 2 : SCRIPT TIKTOK ───
- tiktok_hook : 4 mots MAX, choc immédiat, sans verbe introductif. Ex: "583 morts. Un accent." / "La CIA savait tout."
- tiktok_body : 2-3 phrases style AFP, faits bruts, pas d'opinion.
- tiktok_punchline : 1 phrase qui déclenche un commentaire. Ex: "Et personne n'a jamais été jugé."

─── PARTIE 3 : DONNÉES DE COMMUNICATION ───
- comm_date : La date exacte. DOIT être {exact_date} en majuscules. Ex: "27 MARS 1999"
- comm_stat : Le chiffre le plus fort. 1 nombre + 1 mot. Ex: "583 MORTS" / "50 MILLIONS MORTS". Pas d'unités financières.
- comm_visual_key : L'élément visuel LE PLUS FORT. 1 phrase courte et concrète. Ex: "Des chars dans une rue de ville dévastée" / "Une centrale nucléaire avec un panache de fumée".
- comm_visual_mood : L'ambiance visuelle. 3-4 mots clés. Ex: "Froid, clinique, bleu désaturé" / "Chaud, fumée, cendres orangées".
- description_tiktok : Description TikTok en 2 blocs séparés par "\n\n". Bloc 1 : 1 phrase d'accroche courte et percutante (visible avant "voir plus"). Bloc 2 : 3-4 phrases avec des faits précis, chiffres, détails concrets — ce que les gens découvrent en cliquant "voir plus". Avec emojis. Ex: "L'avion invisible des USA abattu par un missile de 1961. 🛩️\n\nLe 27 mars 1999, le F-117 — 1,45 milliard de dollars — est descendu par un SA-3 soviétique vieux de 40 ans. Le colonel serbe Dani avait trouvé sa fréquence radar dans des publications américaines non-classifiées. Les débris ont été transmis à la Russie et la Chine. Le pilote Dale Zelko a survécu 8h en territoire ennemi."
- hashtags : 5 hashtags maximum, les plus pertinents pour la viralité. Ex: "#histoire #guerre #usa #serbie #fyp"

Retourne UNIQUEMENT un JSON :
{{
  "year": {year},
  "facts": [
    "Fait choc 1 avec chiffres précis",
    "Fait indignant ou mystérieux 2",
    "Détail concret méconnu 3"
  ],
  "tiktok_hook": "4 mots max.",
  "tiktok_body": "2-3 phrases AFP.",
  "tiktok_punchline": "1 phrase débat.",
  "comm_date": "{exact_date}",
  "comm_stat": "82 404 CAS",
  "comm_visual_key": "Description concrète de l'élément visuel iconique",
  "comm_visual_mood": "3-4 mots clés d'ambiance",
  "description_tiktok": "Phrase d'accroche courte.\n\nDétails précis avec faits et chiffres sur plusieurs phrases.",
  "hashtags": "#histoire #guerre #usa #serbie #fyp"
}}"""


def _parse(raw: str) -> dict:
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    parsed = json.loads(raw.strip())
    return parsed[0] if isinstance(parsed, list) else parsed


def run(params: dict) -> dict:
    topic_result = params.get("topic_result", {})
    selected = topic_result.get("selected_event", {})

    if not selected:
        raise RuntimeError("Aucun événement sélectionné — lance d'abord l'agent Topic")

    prompt = PROMPT_TEMPLATE.format(
        title=selected.get("title", ""),
        year=selected.get("year", ""),
        exact_date=selected.get("exact_date", f"{selected.get('year', '')}"),
        hook=selected.get("hook", ""),
        category=selected.get("category", ""),
    )

    result = subprocess.run(
        ["/home/claude-user/.local/bin/claude", "--print", "--output-format", "text"],
        input=prompt, capture_output=True, text=True, timeout=90
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr}")
    if not result.stdout.strip():
        raise RuntimeError(f"Claude CLI empty stdout. stderr: {result.stderr!r}")

    data = _parse(result.stdout.strip())

    topic_title = selected.get("title", "")
    exact_date  = selected.get("exact_date", "")

    return {
        "verified_title":   topic_title,
        "year":             data.get("year", selected.get("year", "")),
        "facts":            data.get("facts", []),
        "tiktok_hook":      data.get("tiktok_hook", ""),
        "tiktok_body":      data.get("tiktok_body", ""),
        "tiktok_punchline": data.get("tiktok_punchline", ""),
        "comm_date":        exact_date.upper() if exact_date else data.get("comm_date", ""),
        "comm_title":       topic_title,
        "comm_stat":        data.get("comm_stat", ""),
        "comm_visual_key":  data.get("comm_visual_key", ""),
        "comm_visual_mood": data.get("comm_visual_mood", ""),
        "description_tiktok": data.get("description_tiktok", ""),
        "hashtags":         data.get("hashtags", "#histoire #catastrophe #fyp"),
    }
