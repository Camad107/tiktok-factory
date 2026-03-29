"""Agent 1 — Contenu : tire 3 arcanes majeurs + génère narration pour ElevenLabs"""
import json
import subprocess
import random
from pathlib import Path

ARCANES_FILE = Path("/home/claude-user/tiktok-factory/data/arcanes.json")


def _load_arcanes() -> list:
    with open(ARCANES_FILE, "r") as f:
        return json.load(f)

SUJETS = ["amour", "argent", "travail", "famille", "santé", "prise de décision", "avenir proche"]

CTAS = [
    "Like pour activer cette prédiction",
    "Like pour que cette lecture t'appartienne",
    "Like ce tirage pour qu'il se réalise",
    "Like pour sceller cette prédiction",
    "Like avant que les cartes changent d'avis",
]

PROMPT = """Tu es une voyante experte en tarot, voix mystérieuse et personnelle pour TikTok francophone.

Sujet de la lecture : {sujet}
Carte 1 ({position_1}) : {nom_1} — sens {sens_1} — énergie : {energie_1} — signification : {signif_1}
Carte 2 ({position_2}) : {nom_2} — sens {sens_2} — énergie : {energie_2} — signification : {signif_2}
Carte 3 ({position_3}) : {nom_3} — sens {sens_3} — énergie : {energie_3} — signification : {signif_3}

Génère le contenu TikTok. Règles absolues :
- Parle directement à "toi" (tutoiement), jamais "vous"
- Style oral, naturel, comme une vraie lectrice qui murmure
- Pas d'emoji dans le script voix
- DURÉE TOTALE : le script_complet doit faire MAX 55 secondes lu à voix haute (environ 120 mots max)
- hook : accrocheur, max 8 mots, donne envie de rester
- narration_intro : annonce le sujet "{sujet}" clairement + engagement immédiat : utilise exactement cette phrase "{cta}" — max 25 mots, mystérieux
- Chaque narration_reveal : max 10 mots, annonce la carte sans "C'est..." ni "Glisse" — juste le nom et une émotion (ex: "Le Soleil. La lumière revient.")
- Chaque narration_detail : MAX 25 mots, direct et percutant
- narration_outro : max 15 mots, invite à commenter ou liker
- script_complet : narration_intro + [PAUSE] + narration_reveal_1 + narration_detail_1 + [PAUSE] + narration_reveal_2 + narration_detail_2 + [PAUSE] + narration_reveal_3 + narration_detail_3 + [PAUSE] + narration_outro
- Les [PAUSE] sont des marqueurs de transition entre les images — les garder EXACTEMENT comme ça dans le script

Positions : carte 1 = passé/obstacle, carte 2 = présent/action, carte 3 = futur/résultat

Format JSON strict :
{{
  "hook": "...",
  "narration_intro": "...",
  "cartes": [
    {{
      "id": 1,
      "nom": "{nom_1}",
      "sens": "{sens_1}",
      "energie": "{energie_1}",
      "position": "{position_1}",
      "narration_reveal": "...",
      "narration_detail": "..."
    }},
    {{
      "id": 2,
      "nom": "{nom_2}",
      "sens": "{sens_2}",
      "energie": "{energie_2}",
      "position": "{position_2}",
      "narration_reveal": "...",
      "narration_detail": "..."
    }},
    {{
      "id": 3,
      "nom": "{nom_3}",
      "sens": "{sens_3}",
      "energie": "{energie_3}",
      "position": "{position_3}",
      "narration_reveal": "...",
      "narration_detail": "..."
    }}
  ],
  "narration_outro": "...",
  "script_complet": "...",
  "hashtags": "#tarot #retournement #voyance #cartomancie #tarottok #spiritualite"
}}

Réponds UNIQUEMENT avec le JSON."""

POSITIONS = ["le passé", "le présent", "le futur"]


def run(params: dict = None) -> dict:
    params = params or {}
    job_id = params.get("job_id", "")

    seed = random.randint(0, 10**9)
    rng = random.Random(seed)

    arcanes = _load_arcanes()
    tirage = rng.sample(arcanes, 3)
    sujet = rng.choice(SUJETS)
    cta = rng.choice(CTAS)

    arcanes_tirés = []
    for i, arcane in enumerate(tirage):
        sens_rng = random.Random(seed + i + 100)
        sens = sens_rng.choice(["endroit", "inversé"])
        signif = arcane["endroit"] if sens == "endroit" else arcane["inverse"]
        arcanes_tirés.append({
            **arcane,
            "sens": sens,
            "signif": signif,
            "position": POSITIONS[i],
            "visuel": arcane.get("visuel", ""),
        })

    a1, a2, a3 = arcanes_tirés

    prompt = PROMPT.format(
        sujet=sujet,
        cta=cta,
        nom_1=a1["nom"], sens_1=a1["sens"], energie_1=a1["energie"], signif_1=a1["signif"], position_1=a1["position"],
        nom_2=a2["nom"], sens_2=a2["sens"], energie_2=a2["energie"], signif_2=a2["signif"], position_2=a2["position"],
        nom_3=a3["nom"], sens_3=a3["sens"], energie_3=a3["energie"], signif_3=a3["signif"], position_3=a3["position"],
    )

    result = subprocess.run(
        ["/home/claude-user/.local/bin/claude", "--print", "--output-format", "text"],
        input=prompt, capture_output=True, text=True, timeout=90
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr}")

    raw = result.stdout.strip()
    if not raw:
        raise RuntimeError(f"Claude CLI empty output. stderr: {result.stderr!r}")
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw.strip())
    if isinstance(data, list):
        data = data[0]

    data["_sujet"] = sujet
    data["_seed"] = seed
    data["_job_id"] = job_id

    # Injecter le champ visuel depuis les arcanes tirés (pas généré par Claude)
    for i, carte in enumerate(data.get("cartes", [])):
        if i < len(arcanes_tirés):
            carte["visuel"] = arcanes_tirés[i].get("visuel", "")

    return data
