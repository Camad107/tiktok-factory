"""Agent 1 — Trouve l'événement géopolitique/guerre/scandale/attentat du jour le plus viral"""
import json
import subprocess
from datetime import date

MONTHS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "août",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
}

PROMPT_SEARCH = """Tu es un historien expert en géopolitique et en faits historiques viraux.

MISSION : trouver des événements qui se sont produits LE {day} {month_name} (n'importe quelle année).

⚠️ RÈGLE N°1 — DATE OBLIGATOIRE : chaque événement DOIT avoir eu lieu exactement le {day} {month_name}. Pas le {day_minus1}, pas le {day_plus1}. Le jour EXACT. Si tu n'es pas certain à 100%, n'inclus pas l'événement.

⚠️ RÈGLE N°2 — NICHES AUTORISÉES par ordre de priorité STRICT :
1. Scandales d'État prouvés impliquant USA, Israël, France ou Russie (CIA, Mossad, KGB, NSA, Watergate, Iraqgate, Cablegate, opérations secrètes...)
2. Décisions politiques controversées impliquant USA, Israël, France ou Russie (frappes, invasions, coups d'état soutenus, sanctions, ultimatums, traités secrets)
3. Attentats et actes terroristes majeurs impliquant ou ciblant USA, Israël, France ou Russie
4. Guerres et interventions militaires impliquant USA, Israël, France ou Russie
5. Attentats, guerres ou scandales majeurs (tous pays, si rien de pertinent dans 1-4)
6. Pandémies et crises sanitaires mondiales

⚠️ RÈGLE N°3 — INTERDIT absolument : accidents, crashs aériens, catastrophes naturelles, séismes, tsunamis, incendies, naufrages, faits divers.

⚠️ RÈGLE N°4 — SCORING 0-100 :
- notoriété grand public (30pts)
- potentiel débat/indignation (30pts)
- implication USA/Israël/France/Russie (20pts)
- révélation d'un mensonge ou manipulation d'État (20pts)

{rejected_block}

Trouve 3 événements distincts, en respectant STRICTEMENT l'ordre de priorité ci-dessus.

Retourne UNIQUEMENT ce JSON, sans texte avant ou après :
{{
  "events": [
    {{
      "rank": 1,
      "year": 2003,
      "title": "Début de l'invasion de l'Irak par les USA",
      "exact_date": "{day} {month_name} 2003",
      "hook": "Les USA envahissent l'Irak sans preuve d'armes de destruction massive : 200 000 soldats, mensonge d'État mondial",
      "category": "intervention_militaire",
      "countries": ["USA", "Irak", "Royaume-Uni"],
      "viral_score": 95
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
- "confirmed": true si la date est correcte OU si tu n'as pas de raison précise de la contredire. Ne rejette un événement que si tu sais avec certitude que la date est FAUSSE.
- "reason": en 1 phrase la confirmation ou la raison précise du rejet.

Retourne UNIQUEMENT ce JSON :
[
  {{"rank": 1, "confirmed": true, "reason": "L'invasion de l'Irak a bien commencé le 20 mars 2003"}},
  {{"rank": 2, "confirmed": false, "reason": "Cet événement s'est produit le 15 janvier et non la date indiquée"}},
  {{"rank": 3, "confirmed": true, "reason": "Confirmé par les archives historiques"}}
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
    data = {}
    used_prompt_search = ""
    used_prompt_verify = ""

    for attempt in range(2):
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
        used_prompt_search = prompt_search

        raw_search = _call_claude(prompt_search)
        data = _parse_json(raw_search)
        if isinstance(data, list):
            data = data[0]

        events = data.get("events", [])
        if not events:
            continue

        events_for_verify = [
            {"rank": e["rank"], "title": e.get("title", ""), "exact_date": e.get("exact_date", ""), "year": e.get("year", "")}
            for e in events
        ]
        prompt_verify = PROMPT_VERIFY.format(
            day=day,
            month_name=month_name,
            events_json=json.dumps(events_for_verify, ensure_ascii=False, indent=2),
        )
        used_prompt_verify = prompt_verify

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
            verifications = [{"rank": e["rank"], "confirmed": True, "reason": ""} for e in events]

        verif_map = {v["rank"]: v for v in verifications}

        all_events_this_round = []
        for e in events:
            v = verif_map.get(e["rank"], {})
            confirmed = v.get("confirmed", True)
            e["confirmed"] = confirmed
            e["verify_reason"] = v.get("reason", "")
            all_events_this_round.append(e)
            if confirmed:
                validated_events.append(e)
            else:
                rejected_titles.append(e.get("title", ""))

        # Garde tous les events de ce round pour l'affichage (confirmés + refusés)
        all_events = all_events_this_round

        if validated_events:
            break

    if not validated_events:
        validated_events = events
        all_events = events

    best_rank = data.get("best_event_rank", 1)
    best = next((e for e in validated_events if e["rank"] == best_rank), validated_events[0] if validated_events else {})

    if best and "exact_date" not in best:
        best["exact_date"] = f"{day} {month_name} {best.get('year', '')}"

    return {
        "date_display":    f"{day} {month_name}",
        "events":          all_events,
        "selected_event":  best,
        "titre":           best.get("title", ""),
        "description":     best.get("hook", ""),
        "date":            best.get("exact_date", f"{day} {month_name} {best.get('year', '')}"),
        "prompt_search":   used_prompt_search,
        "prompt_verify":   used_prompt_verify,
    }
