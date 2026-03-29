"""Agent 1 — Trouve l'événement historique du jour le plus viral pour TikTok"""
import json
import subprocess
from datetime import date

MONTHS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "août",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
}

PROMPT_SEARCH = """Tu es historien expert en faits historiques viraux.

MISSION : trouver des événements qui se sont produits LE {day} {month_name} (n'importe quelle année).

⚠️ RÈGLE N°1 — DATE OBLIGATOIRE : chaque événement DOIT avoir eu lieu exactement le {day} {month_name}. Pas le {day_minus1}, pas le {day_plus1}. Le jour EXACT. Si tu n'es pas certain à 100%, n'inclus pas l'événement.

⚠️ RÈGLE N°2 — NICHES AUTORISÉES uniquement :
- Guerres et interventions militaires (USA, France, URSS, OTAN, Vietnam, Irak, Libye, Afghanistan...)
- Décisions politiques controversées (frappes, coups d'état, interventions secrètes)
- Pandémies et virus avec impact mondial
- Scandales et mensonges d'état prouvés (CIA, Pentagone, NSA, Watergate...)
- Attentats majeurs connus du grand public

⚠️ RÈGLE N°3 — INTERDIT absolument : accidents, crashs aériens, catastrophes naturelles, séismes, tsunamis, incendies, naufrages.

{rejected_block}

Trouve 3 événements. Score viral 0-100 : notoriété (40pts) + potentiel débat (60pts).

Retourne UNIQUEMENT ce JSON, sans texte avant ou après :
{{
  "events": [
    {{
      "rank": 1,
      "year": 2003,
      "title": "Début de la guerre en Irak",
      "exact_date": "{day} {month_name} 2003",
      "hook": "Les USA envahissent l'Irak sans preuve d'armes de destruction massive",
      "category": "intervention_militaire",
      "viral_score": 92
    }}
  ],
  "best_event_rank": 1
}}"""

PROMPT_VERIFY = """Tu es un fact-checker historique rigoureux.

Pour chacun des événements suivants, vérifie si la date est EXACTEMENT le {day} {month_name} de l'année indiquée.
Réponds uniquement par un JSON.

Événements à vérifier :
{events_json}

Pour chaque événement, indique :
- "confirmed": true si la date est correcte OU si tu n'as pas de raison précise de la contredire. Ne rejette un événement que si tu sais avec certitude que la date est FAUSSE (ex: tu sais que c'était le 19 et non le 27).
- "reason": en 1 phrase la confirmation ou la raison précise du rejet.

Retourne UNIQUEMENT ce JSON :
[
  {{"rank": 1, "confirmed": true, "reason": "L'attentat du Park Hotel à Netanya a bien eu lieu le 27 mars 2002"}},
  {{"rank": 2, "confirmed": false, "reason": "Le bombardement de la Libye a commencé le 19 mars 2011, pas le 27"}},
  {{"rank": 3, "confirmed": true, "reason": "Le dernier V-2 sur l'Angleterre est tombé le 27 mars 1945 à Orpington"}}
]"""


def _call_claude(prompt: str, timeout: int = 120) -> str:
    result = subprocess.run(
        ["/home/claude-user/.local/bin/claude", "--print", "--output-format", "text"],
        input=prompt,
        capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr}")
    if not result.stdout.strip():
        raise RuntimeError(f"Claude CLI empty stdout. stderr: {result.stderr!r}")
    return result.stdout.strip()


def _parse_json(raw: str):
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    parsed = json.loads(raw.strip())
    return parsed[0] if (isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict) and "events" in parsed[0]) else parsed


def run(params: dict = None) -> dict:
    today = date.today()
    day = today.day
    month_name = MONTHS_FR[today.month]

    rejected_titles = []
    validated_events = []

    for attempt in range(2):
        # Bloc des événements refusés à injecter dans le prompt
        if rejected_titles:
            rejected_block = (
                "⛔ ÉVÉNEMENTS DÉJÀ REFUSÉS (date non confirmée — ne pas reproposer) :\n"
                + "\n".join(f"- {t}" for t in rejected_titles)
                + "\n\nTrouve d'autres événements différents."
            )
        else:
            rejected_block = ""

        prompt_search = PROMPT_SEARCH.format(
            day=day,
            month_name=month_name,
            day_minus1=day - 1,
            day_plus1=day + 1,
            rejected_block=rejected_block,
        )

        raw_search = _call_claude(prompt_search)
        data = _parse_json(raw_search)
        if isinstance(data, list):
            data = data[0]

        events = data.get("events", [])
        if not events:
            continue

        # Vérification des dates par Claude
        events_for_verify = [
            {"rank": e["rank"], "title": e.get("title", ""), "exact_date": e.get("exact_date", ""), "year": e.get("year", "")}
            for e in events
        ]
        prompt_verify = PROMPT_VERIFY.format(
            day=day,
            month_name=month_name,
            events_json=json.dumps(events_for_verify, ensure_ascii=False, indent=2),
        )

        raw_verify = _call_claude(prompt_verify, timeout=60)
        try:
            verif_raw = raw_verify
            if "```" in verif_raw:
                verif_raw = verif_raw.split("```")[1]
                if verif_raw.startswith("json"):
                    verif_raw = verif_raw[4:]
            verifications = json.loads(verif_raw.strip())
            if isinstance(verifications, dict):
                verifications = [verifications]
        except Exception:
            # Si la vérif échoue on garde tous les événements
            verifications = [{"rank": e["rank"], "confirmed": True, "reason": ""} for e in events]

        # Map rank → confirmed
        verif_map = {v["rank"]: v for v in verifications}

        new_confirmed = []
        new_rejected = []
        for e in events:
            v = verif_map.get(e["rank"], {})
            if v.get("confirmed", True):
                e["verify_reason"] = v.get("reason", "")
                new_confirmed.append(e)
            else:
                rejected_titles.append(e.get("title", ""))
                new_rejected.append(e.get("title", ""))

        validated_events.extend(new_confirmed)

        # Si on a au moins 1 événement confirmé, on s'arrête
        if validated_events:
            break

    # Fallback : si rien n'a passé la vérif, on prend les events bruts du dernier appel
    if not validated_events:
        validated_events = events

    # Sélection du meilleur
    best_rank = data.get("best_event_rank", 1)
    # Préfère le best_rank parmi les validés, sinon le premier validé
    best = next((e for e in validated_events if e["rank"] == best_rank), validated_events[0] if validated_events else {})

    # Force exact_date cohérente
    if best and "exact_date" not in best:
        best["exact_date"] = f"{day} {month_name} {best.get('year', '')}"

    return {
        "date_display":   f"{day} {month_name}",
        "events":         validated_events,
        "selected_event": best,
    }
