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
        {"id": "soleil",   "name": "The Sun",            "name_fr": "Le Soleil",          "meaning": "Everything will go wonderfully. Bright energy surrounds you."},
        {"id": "etoile",   "name": "The Star",           "name_fr": "L'Étoile",           "meaning": "Beautiful energy ahead. Hope and renewal are on your side."},
        {"id": "monde",    "name": "The World",          "name_fr": "Le Monde",           "meaning": "Success and accomplishment await you. You are aligned."},
        {"id": "roue",     "name": "Wheel of Fortune",   "name_fr": "La Roue de Fortune", "meaning": "Luck is turning in your favor. Embrace the change."},
        {"id": "imperatrice", "name": "The Empress",     "name_fr": "L'Impératrice",      "meaning": "Abundance and warmth surround you. Trust the flow."},
    ],
    "neutral": [
        {"id": "jugement", "name": "Judgement",          "name_fr": "Le Jugement",        "meaning": "A transition is underway. Results may be mixed — stay grounded."},
        {"id": "lune",     "name": "The Moon",           "name_fr": "La Lune",            "meaning": "Uncertainty clouds the path. Trust your intuition, not appearances."},
        {"id": "pendu",    "name": "The Hanged Man",     "name_fr": "Le Pendu",           "meaning": "Patience is required. A pause now leads to clarity later."},
    ],
    "negative": [
        {"id": "tour",     "name": "The Tower",          "name_fr": "La Tour",            "meaning": "Disruption is coming. Brace for impact — but it clears the way."},
        {"id": "diable",   "name": "The Devil",          "name_fr": "Le Diable",          "meaning": "Tension and blockages are present. Awareness is your first step out."},
    ],
}

PROMPT = """You are a tarot oracle. Answer concisely and directly.

Today: {date}
Subject: {subject}
Question asked to the viewer: "{question}"
Card drawn: {card_name} ({card_id}) — outcome: {outcome}

Write a short reading (2-3 sentences max) for this card, tied to the subject and outcome.
Also write a short TikTok hook.

Reply ONLY in this exact JSON format:
{{
  "reading": "2-3 sentence reading in English, direct and personal, no emoji",
  "hook": "short intriguing hook for TikTok (max 8 words, no emoji, no question mark)"
}}

Reply ONLY with the JSON."""


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
        question=subject["question"],
        card_name=card["name"],
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
