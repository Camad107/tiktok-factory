"""Agent 1 — Choisit le sujet, pose la question, tire la carte"""
import json
import subprocess
import random
from datetime import date
from pathlib import Path

SUBJECTS = [
    {"id": "amours",    "question": "How will your love life be today?",        "question_fr": "Comment seront tes amours aujourd'hui ?"},
    {"id": "journee",   "question": "How will your day go overall?",             "question_fr": "Comment va se passer ta journée ?"},
    {"id": "carriere",  "question": "How is your career looking this week?",     "question_fr": "Comment va ta carrière cette semaine ?"},
    {"id": "energie",   "question": "What is your energy like right now?",       "question_fr": "Quelle est ton énergie en ce moment ?"},
    {"id": "decision",  "question": "Should you make that important decision?",  "question_fr": "Dois-tu prendre cette décision importante ?"},
    {"id": "relations", "question": "How are your relationships with others?",   "question_fr": "Comment vont tes relations avec les autres ?"},
    {"id": "sante",     "question": "How is your health and well-being today?",  "question_fr": "Comment va ta santé et ton bien-être ?"},
    {"id": "projet",    "question": "Will your current project succeed?",        "question_fr": "Ton projet en cours va-t-il réussir ?"},
    {"id": "finances",  "question": "How are your finances looking?",            "question_fr": "Comment vont tes finances ?"},
    {"id": "univers",   "question": "What does the universe have in store for you?", "question_fr": "Que te réserve l'univers ?"},
]

CARDS = {
    "positive": [
        {"id": "soleil",      "name": "The Sun",          "name_fr": "Le Soleil",          "meaning": "Everything will go wonderfully. Bright energy surrounds you.",        "meaning_fr": "Tout va merveilleusement bien. Une énergie lumineuse t'entoure."},
        {"id": "etoile",      "name": "The Star",         "name_fr": "L'Étoile",           "meaning": "Beautiful energy ahead. Hope and renewal are on your side.",          "meaning_fr": "Une belle énergie t'attend. L'espoir et le renouveau sont de ton côté."},
        {"id": "monde",       "name": "The World",        "name_fr": "Le Monde",           "meaning": "Success and accomplishment await you. You are aligned.",              "meaning_fr": "Le succès et l'accomplissement t'attendent. Tu es en alignement."},
        {"id": "roue",        "name": "Wheel of Fortune", "name_fr": "La Roue de Fortune", "meaning": "Luck is turning in your favor. Embrace the change.",                 "meaning_fr": "La chance tourne en ta faveur. Accueille ce changement."},
        {"id": "imperatrice", "name": "The Empress",      "name_fr": "L'Impératrice",      "meaning": "Abundance and warmth surround you. Trust the flow.",                 "meaning_fr": "L'abondance et la douceur t'entourent. Fais confiance au flot."},
    ],
    "neutral": [
        {"id": "jugement", "name": "Judgement",   "name_fr": "Le Jugement", "meaning": "A transition is underway. Results may be mixed — stay grounded.",       "meaning_fr": "Une transition est en cours. Les résultats peuvent être mitigés — reste ancré."},
        {"id": "lune",     "name": "The Moon",    "name_fr": "La Lune",     "meaning": "Uncertainty clouds the path. Trust your intuition, not appearances.",   "meaning_fr": "L'incertitude voile le chemin. Fais confiance à ton intuition."},
        {"id": "pendu",    "name": "The Hanged Man", "name_fr": "Le Pendu", "meaning": "Patience is required. A pause now leads to clarity later.",             "meaning_fr": "La patience est de mise. Une pause maintenant mène à la clarté."},
    ],
    "negative": [
        {"id": "tour",   "name": "The Tower", "name_fr": "La Tour",   "meaning": "Disruption is coming. Brace for impact — but it clears the way.", "meaning_fr": "Une perturbation arrive. Tiens bon — cela libère le chemin."},
        {"id": "diable", "name": "The Devil", "name_fr": "Le Diable", "meaning": "Tension and blockages are present. Awareness is your first step out.", "meaning_fr": "Des tensions et blocages sont présents. La prise de conscience est ta première sortie."},
    ],
}

PROMPT = """Tu es un oracle tarot. Réponds de façon concise et directe.

Aujourd'hui : {date}
Sujet : {subject}
Question posée au spectateur : "{question}"
Carte tirée : {card_name} ({card_id}) — énergie : {outcome}

Écris une courte lecture (2-3 phrases max) pour cette carte, liée au sujet et à l'énergie.
Écris aussi un court hook TikTok.

Réponds UNIQUEMENT dans ce format JSON exact :
{{
  "reading": "lecture de 2-3 phrases en français, directe et personnelle, sans emoji",
  "hook": "hook court et intrigant pour TikTok (max 8 mots, sans emoji, sans point d'interrogation)"
}}

Réponds UNIQUEMENT avec le JSON."""


def pick_subject(day_seed: int) -> dict:
    rng = random.Random(day_seed)
    return rng.choice(SUBJECTS)


def pick_card(day_seed: int) -> tuple:
    """Choisit outcome + carte de façon déterministe mais variée selon le jour."""
    rng = random.Random(day_seed + 7)  # offset pour différencier du subject seed
    # Pondération : 50% positif, 30% neutre, 20% négatif
    outcome = rng.choices(
        ["positive", "neutral", "negative"],
        weights=[50, 30, 20]
    )[0]
    card = rng.choice(CARDS[outcome])
    return outcome, card


def run(params: dict = None) -> dict:
    today = date.today()
    day_seed = today.toordinal()

    # Subject
    subject_id = (params or {}).get("subject_id")
    if subject_id:
        subject = next((s for s in SUBJECTS if s["id"] == subject_id), None) or pick_subject(day_seed)
    else:
        subject = pick_subject(day_seed)

    # Card — picked by us, not by Claude
    outcome, card = pick_card(day_seed + hash(subject["id"]) % 1000)

    prompt = PROMPT.format(
        date=today.strftime("%B %d, %Y"),
        subject=subject["id"],
        question=subject["question_fr"],
        card_name=card["name_fr"],
        card_id=card["id"],
        outcome=outcome,
    )

    result = subprocess.run(
        ["/home/claude-user/.local/bin/claude", "--print", "--output-format", "text"],
        input=prompt, capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr}")

    raw = result.stdout.strip()
    if not raw:
        raise RuntimeError(f"Claude CLI empty stdout. stderr: {result.stderr!r}")
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    parsed = json.loads(raw.strip())
    data = parsed[0] if isinstance(parsed, list) else parsed

    return {
        "subject": subject,
        "outcome": outcome,
        "card": card,
        "reading": data.get("reading", ""),
        "hook": data.get("hook", subject["question"]),
        "question": subject["question"],
        "question_fr": subject["question_fr"],
    }
