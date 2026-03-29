"""Agent 2 — Reçoit titre, description, date et enrichit pour TikTok"""
import json
import subprocess


PROMPT_TEMPLATE = """Tu es un journaliste d'investigation spécialisé dans les faits historiques viraux pour TikTok.

Événement : {titre}
Date exacte : {date}
Description : {description}

─── PARTIE 1 : FACT-CHECK ───
3 faits précis et vérifiés, avec chiffres ou détails concrets. Angle : choc, indignation, ou révélation.

─── PARTIE 2 : SCRIPT TIKTOK (voix off — INTERDIT ABSOLU : emojis, symboles, caractères spéciaux) ───
- tiktok_hook : 8 mots MAX, choc immédiat, peut être une phrase courte avec verbe. Ex: "Un massacre en entraîne un autre." / "La CIA savait tout." / "30 morts. Une seule nuit."
- tiktok_body : 2-3 phrases style AFP, faits bruts, pas d'opinion, lettres et chiffres uniquement.
- tiktok_punchline : 1 phrase qui déclenche un commentaire, lettres et chiffres uniquement. Ex: "Et personne n'a jamais été jugé."

─── PARTIE 3 : OVERLAY VIDÉO ───
- overlay_titre : Titre à superposer sur la vidéo. 10 mots maximum, minuscules, contient les infos essentielles (qui attaque, qui est attaqué, contexte clé). Pas de majuscules, pas de parenthèses. Ex: "L'OTAN bombarde la Serbie sans autorisation" / "Israël envahit la Cisjordanie après l'attentat" / "La CIA finance les rebelles en secret"

─── PARTIE 4 : DESCRIPTION TIKTOK ───
- description_tiktok : Description TikTok structurée en 3 blocs séparés par "\\n\\n" :
  Bloc 1 : 1 phrase d'accroche courte avec emoji (visible avant "voir plus").
  Bloc 2 : 3-4 phrases avec faits précis, chiffres, détails concrets. Avec emojis.
  Bloc 3 : les 3 faits vérifiés de la Partie 1, format liste avec "▸ " devant chaque fait, sans emojis.
- hashtags : 5 hashtags maximum, les plus pertinents pour la viralité.

Retourne UNIQUEMENT un JSON :
{{
  "facts": [
    "Fait choc 1 avec chiffres précis",
    "Fait indignant ou mystérieux 2",
    "Détail concret méconnu 3"
  ],
  "tiktok_hook": "8 mots max, phrase choc.",
  "tiktok_body": "2-3 phrases AFP.",
  "tiktok_punchline": "1 phrase débat.",
  "overlay_titre": "L'OTAN bombarde la Serbie sans autorisation",
  "description_tiktok": "Phrase d'accroche courte. 🔥\\n\\nDétails précis avec faits et chiffres sur plusieurs phrases.\\n\\n▸ Fait 1 précis\\n▸ Fait 2 indignant\\n▸ Fait 3 méconnu",
  "hashtags": "#histoire #attentat #israel #fyp"
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

    titre       = (topic_result.get("titre")
                   or topic_result.get("titre1")
                   or (topic_result.get("selected_event") or {}).get("title")
                   or "")
    description = (topic_result.get("description")
                   or (topic_result.get("selected_event") or {}).get("hook")
                   or "")
    date        = (topic_result.get("date")
                   or (topic_result.get("selected_event") or {}).get("exact_date")
                   or "")

    if not titre:
        raise RuntimeError("Données topic manquantes — lance d'abord l'agent Topic")

    prompt = PROMPT_TEMPLATE.format(
        titre=titre,
        date=date,
        description=description,
        date_upper=date.upper(),
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

    return {
        "titre":              titre,
        "date":               date,
        "description":        description,
        "facts":              data.get("facts", []),
        "tiktok_hook":        data.get("tiktok_hook", ""),
        "tiktok_body":        data.get("tiktok_body", ""),
        "tiktok_punchline":   data.get("tiktok_punchline", ""),
        "overlay_titre":      data.get("overlay_titre", ""),
        "description_tiktok": data.get("description_tiktok", ""),
        "hashtags":           data.get("hashtags", "#histoire #fyp"),
        "prompt_used":        prompt,
    }
