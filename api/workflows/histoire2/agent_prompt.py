"""Agent 3 — Génère le prompt Runway 10s cinématique à partir des données research"""
import json
import subprocess


PROMPT_TEMPLATE = """Tu es un directeur de la photographie (DP) hollywoodien spécialisé en vidéo cinématique pour TikTok.

Événement : {titre}
Date : {date}
Description : {description}
Facts clés : {facts}

Ta mission : créer un prompt Runway Gen-4 pour un MINI-FILM de 10 secondes en 9:16.
Ce n'est PAS une loop — c'est une scène narrative avec un début et une progression visuelle.

STRUCTURE OBLIGATOIRE :
1. [Mouvement caméra actif] : commence par un verbe d'action caméra. Ex: "Camera pushes slowly forward through...", "Handheld camera tracks alongside...", "Low angle dolly moves through..."
2. [Scène d'ouverture concrète] : décris précisément ce qui est visible à la première seconde — lieu, époque, atmosphère
3. [Action ou révélation progressive] : ce qui se passe ou se révèle pendant les 10 secondes — mouvement, lumière, détail qui émerge
4. [Éléments atmosphériques] : fumée, poussière, débris, pluie, cendres, brouillard — donnent vie et réalisme
5. [Éclairage cinématique précis] : backlit, rim light, motivated light, golden hour, cold clinical, harsh shadows
6. [Palette et grain] : cohérents avec l'événement — guerre/chaud/ambre, scandale/froid/bleu, attentat/chaos/désaturé
7. Terminer OBLIGATOIREMENT par : "Photorealistic, 35mm film grain, anamorphic lens, no text, no readable faces, vertical 9:16"

RÈGLES STRICTES :
- 80 à 120 mots MAX
- Un seul plan continu, une seule scène
- Commence TOUJOURS par le mouvement caméra (verbe actif)
- Pas de visages identifiables
- Handheld autorisé pour chaos/attentats/guerre
- En anglais uniquement
- Orienté PHOTOREALISME et CINEMA — pas cartoon, pas stylisé

TYPES DE MOUVEMENTS SELON L'ÉVÉNEMENT :
- Attentat/explosion : "Handheld camera jolts forward through..." (chaos, urgence)
- Guerre/invasion : "Low angle tracking shot follows..." (puissance, tension)
- Scandale/complot : "Slow dolly pushes into..." (suspense, révélation)
- Décision politique : "Camera slowly pulls back from..." (isolement, poids)
- Pandémie : "Wide static shot holds on..." (vide, silence)

EXEMPLES :
Attentat → "Handheld camera pushes through smoke-filled hotel banquet hall, overturned tables and shattered glass catching emergency light, debris scattered across white tablecloths, distant sirens bleeding through broken windows. Dust and ash particles float in shafts of red emergency lighting. Chaotic handheld motion, high contrast, desaturated warm tones bleeding into cold blue. Photorealistic, 35mm film grain, anamorphic lens, no text, no readable faces, vertical 9:16"

Invasion militaire → "Low angle tracking shot moves alongside convoy of tanks rolling through empty city boulevard at dawn, exhaust and dust clouds billowing in amber backlight, power lines swaying above, abandoned vehicles lining the curb. Backlit harsh sunrise, long shadows, warm amber haze through grey concrete. Photorealistic, 35mm film grain, anamorphic lens, no text, no readable faces, vertical 9:16"

Scandale d'État → "Camera slowly dollies forward through dimly lit government operations room at night, monitors casting cold blue light on empty chairs, classified documents spread across a central table, single overhead lamp flickering. Tense low-key lighting, cold blue on deep shadow, institutional grey walls. Photorealistic, 35mm film grain, anamorphic lens, no text, no readable faces, vertical 9:16"

Retourne UNIQUEMENT ce JSON :
{{
  "runway_prompt": "Le prompt complet 80-120 mots en anglais",
  "visual_rationale": "En 1 phrase pourquoi cette scène et ce mouvement caméra sont le meilleur choix pour cet événement",
  "camera_movement": "Le type de mouvement caméra choisi",
  "mood": "L'ambiance visuelle en 3 mots"
}}"""


def _parse(raw: str) -> dict:
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    parsed = json.loads(raw.strip())
    return parsed[0] if isinstance(parsed, list) else parsed


def run(params: dict) -> dict:
    research_result = params.get("research_result", {})

    if not research_result:
        raise RuntimeError("Données research manquantes — lance d'abord l'agent Research")

    facts_str = "\n".join(f"- {f}" for f in research_result.get("facts", []))

    prompt = PROMPT_TEMPLATE.format(
        titre=research_result.get("titre", ""),
        date=research_result.get("date", ""),
        description=research_result.get("description", ""),
        facts=facts_str,
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
        "runway_prompt":    data.get("runway_prompt", ""),
        "visual_rationale": data.get("visual_rationale", ""),
        "camera_movement":  data.get("camera_movement", ""),
        "mood":             data.get("mood", ""),
        "prompt_used":      prompt,
    }
