"""Agent 3 — Génère le prompt Runway à partir des données visuelles de research"""
import json
import subprocess


PROMPT_TEMPLATE = """Tu es un directeur de la photographie (DP) hollywoodien spécialisé en vidéo cinématique pour TikTok.

Événement : {verified_title} ({year})
Élément visuel clé : {comm_visual_key}
Ambiance visuelle : {comm_visual_mood}

Ta mission : créer un prompt Runway Gen-4 parfait pour une vidéo loop de 5 secondes en 9:16.

STRUCTURE OBLIGATOIRE du prompt :
1. [Type de plan + mouvement caméra] : "Slow dolly in on:", "Wide static shot:", "Low angle tracking shot:"
2. [Scène concrète basée sur l'élément visuel clé] avec détails d'époque et de contexte
3. [Éléments atmosphériques animés] : fumée, cendres, brouillard, débris, pluie, poussière — ils donnent vie à la loop
4. [Éclairage précis] : backlit, rim lighting, motivated light, low-key shadows, golden hour, cold clinical
5. [Palette de couleurs] cohérente avec l'ambiance : {comm_visual_mood}
6. Terminer par : "Cinematic, anamorphic lens, photorealistic, film grain, no text, no readable faces, vertical 9:16"

RÈGLES STRICTES :
- 50 à 80 mots MAX
- Un seul plan, une seule scène, un seul mouvement de caméra
- Mouvement LENT pour loop seamless (slow dolly, gentle pan, subtle tilt)
- Pas de visages identifiables
- En anglais

EXEMPLES :
Pandémie → "Wide static shot: empty hospital emergency corridor at night, flickering fluorescent lights casting cold blue shadows on sealed biohazard doors, discarded latex gloves on the floor, fog drifting at floor level. Cold motivated light, deep shadows, desaturated blue-grey. Cinematic, anamorphic lens, photorealistic, film grain, no text, no readable faces, vertical 9:16"

Guerre → "Low angle tracking shot: ruined city street at dusk, collapsed facades casting jagged shadows, dust and ash particles floating in shafts of amber backlight, single overturned child's bicycle in foreground. Backlit, high contrast, warm amber through cold grey ruins. Cinematic, anamorphic lens, photorealistic, film grain, no text, no readable faces, vertical 9:16"

Scandale → "Gentle dolly through dimly lit government archive room, floor-to-ceiling filing cabinets with classified stamps, single desk lamp casting hard cone of yellow light on open dossier, dust particles floating in beam, deep shadows. Noir low-key lighting, warm amber on cold dark. Cinematic, anamorphic lens, photorealistic, film grain, no text, no readable faces, vertical 9:16"

Retourne UNIQUEMENT ce JSON :
{{
  "runway_prompt": "Le prompt complet 50-80 mots en anglais",
  "visual_rationale": "En 1 phrase pourquoi cette scène est le meilleur choix visuel"
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

    prompt = PROMPT_TEMPLATE.format(
        verified_title=research_result.get("verified_title", ""),
        year=research_result.get("year", ""),
        comm_visual_key=research_result.get("comm_visual_key", ""),
        comm_visual_mood=research_result.get("comm_visual_mood", ""),
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
    }
