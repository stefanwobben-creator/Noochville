"""weten_we_dit_al — geheugen-eerst voor élke bewoner (founder, 19 jul).

Eén leesgreep naar het collectieve geheugen vóór dure actie, met een expliciet antwoord
op de naamsvraag: `bekend: true/false` — weten we dit al? Bij JA komen de directe
treffers mee uit de kennisbank (gemunte inzichten), de kaarten-bibliotheek
(signals/atomen), De Kroniek (bevestigd/leeg/fout, laatste stand per bron) en de
projecten (inclusief hun antwoord, dod_outcome). Bij NEE komt wat het dorp WEL al weet
over het aangrenzende onderwerp mee als `context` — zodat een bewoner nooit met lege
handen begint (founder, 19 jul: "bij N meegeven wat we wél al weten").

Twee matchlagen, deterministisch en zonder LLM:
- STERK (≥2 vraagwoorden raken; bij een éénwoordsvraag: dat woord) → direct antwoord;
- ZWAK (één woord raakt) → context, per laag gelabeld.
Kale treffers met bron en datum zijn hier waardevoller dan een gladde samenvatting —
dit is de plek waar het dorp zijn waarheidslat heeft liggen (geest van kroniek_interpret).

Zuiver lezen ("alle rollen voeden, lezen is vrij"). De skill beschrijft zijn eigen
gebruik als Kroniek-record (evidence_records): bevestigd = het geheugen had een direct
antwoord, leeg = onontgonnen terrein (het kennisgat is de bevinding). Zo ziet Lara na
een maand wie het geheugen benut en waar de terugkerende gaten zitten.
"""
from __future__ import annotations

import os
import re

from nooch_village.skills import Skill

_MIN_WOORD = 4          # matchwoorden: alleen betekenisdragers, geen lidwoorden
_MIN_ACRONIEM = 2       # …behalve een afkorting in HOOFDLETTERS (PHA, MOQ, EVA, TPU): die is betekenis
_PER_BAK = 8            # max treffers per geheugenlaag — genoeg om te weten dat het er is

# Functiewoorden van ≥4 tekens die anders als 'betekenis' meetellen — substring-matchen is bewust
# (schoenen ⊂ schoenenindustrie), dus deze ruis moet er expliciet uit. Nederlands én Engels: de
# inhoudslaag is sinds 06-09-2026 Engels, en "What do we already know about MOQ for EVA soles"
# telde what/already/know/about als betekenis en liet MOQ/EVA vallen (skill-review 12-09-2026).
_STOP = {"voor", "over", "naar", "deze", "onze", "zijn", "wordt", "worden", "heeft",
         "hebben", "maar", "niet", "alle", "andere", "tussen", "door", "weten", "welke",
         "over", "ook", "zonder", "moet", "moeten", "gaat", "gaan", "veel", "meer",
         # Engels
         "what", "about", "from", "already", "know", "known", "check", "anything", "does",
         "with", "that", "this", "have", "there", "which", "when", "where", "their", "them",
         "they", "would", "could", "should", "than", "then", "into", "also", "some", "such",
         "been", "were", "will", "your", "ours", "more", "most", "very", "just", "only",
         "whether", "please", "find", "look", "search", "village", "know", "still"}


def _woorden(vraag: str) -> list[str]:
    """De betekenisdragers van een vraag: woorden van ≥4 tekens buiten de stoplijst, plus korte
    afkortingen die in de vraag in HOOFDLETTERS staan (PHA, MOQ, EVA). Een materiaalvraag bestaat
    vaak alleen uit zulke afkortingen ('PHA PLA TPU') en gaf voorheen "geen betekenisvol woord"."""
    uit = []
    for w in re.findall(r"[\w-]+", vraag or ""):
        low = w.lower()
        if low in _STOP:
            continue
        if len(low) >= _MIN_WOORD or (len(low) >= _MIN_ACRONIEM and w.isupper() and w.isalpha()):
            uit.append(low)
    return uit


def _score(tekst: str, woorden: list[str]) -> int:
    t = (tekst or "").lower()
    return sum(1 for w in woorden if w in t)


def _top(rows: list[tuple[int, dict]]) -> list[dict]:
    rows.sort(key=lambda r: -r[0])
    return [r[1] for r in rows[:_PER_BAK]]


class WetenWeDitAlSkill(Skill):
    name = "weten_we_dit_al"
    cost = "free"                  # lokale I/O, deterministisch, geen externe call en geen LLM
    side_effect_free = True        # leest vier stores, schrijft niets (het Kroniek-record
    #                                beschrijft hij alleen; de inhabitant schrijft het)
    description = ("Memory first: do we already know this (yes/no)? Searches the knowledge base, "
                   "the card library, the Chronicle and the projects for the words of the question. "
                   "On no, what the village does know about the adjacent topic comes along as context. "
                   "Deterministic, no model.")
    input_schema = ("vraag: str (required — the question or topic, in a few content words; "
                    "acronyms in capitals such as PHA or MOQ count as words)")
    required_payload = ("vraag",)
    output_schema = ("ok: bool, bekend: bool, text/samenvatting: str, inzichten: list, kaarten: list, "
                     "kroniek: {bevestigd|leeg|fout: list} (only non-empty buckets), projecten: list, "
                     "context: list, treffers: int | no_data+reason (nothing known, no context) | error")

    def _dd(self, context) -> str:
        return getattr(context, "data_dir", ".") or "."

    def run(self, payload: dict, context=None) -> dict:
        vraag = ((payload or {}).get("vraag") or "").strip()
        woorden = _woorden(vraag)
        if not woorden:
            return {"ok": False, "error": "geef een vraag ('vraag' is verplicht) met minstens één "
                                          "betekenisvol woord"}
        drempel = 2 if len(woorden) >= 2 else 1        # sterk = meerdere vraagwoorden raken
        dd = self._dd(context)
        context_bak: list[tuple[int, dict]] = []       # zwakke treffers, per laag gelabeld

        def verdeel(s: int, laag: str, item: dict, sterk: list) -> None:
            if s >= drempel:
                sterk.append((s, item))
            elif s:
                context_bak.append((s, {"laag": laag, **item}))

        # 1. Kennisbank — gemunte inzichten (laag 2)
        inzichten: list[tuple[int, dict]] = []
        try:
            from nooch_village.kennisbank import KennisbankStore
            for i in KennisbankStore(os.path.join(dd, "kennisbank.json")).all():
                s = _score(" ".join(str(i.get(k) or "") for k in ("title", "why", "subject")), woorden)
                verdeel(s, "inzicht", {"id": i.get("id"), "titel": (i.get("title") or "")[:200],
                                       "versie": i.get("version"), "subject": i.get("subject")},
                        inzichten)
        except Exception:
            pass                                       # fail-soft per laag: een kapotte store ≠ geen antwoord

        # 2. Kaarten-bibliotheek — signals/atomen (laag 1)
        kaarten: list[tuple[int, dict]] = []
        try:
            from nooch_village.kennisbank import load_atoms
            for aid, a in load_atoms(dd).items():
                s = _score(" ".join([str(a.get("claim") or ""), " ".join(a.get("tags") or [])]), woorden)
                verdeel(s, "kaart", {"id": aid, "claim": (a.get("claim") or "")[:200],
                                     "bron": a.get("source"), "reference": a.get("reference"),
                                     "herkomst": a.get("provenance")}, kaarten)
        except Exception:
            pass

        # 3. De Kroniek — laatste stand per (skill, query, bron), zoals interpret()
        kroniek = {"bevestigd": [], "leeg": [], "fout": []}
        n_kroniek = 0
        try:
            from nooch_village.evidence_ledger import EvidenceLedger
            led = getattr(context, "evidence_ledger", None) or \
                EvidenceLedger(os.path.join(dd, "evidence_ledger.jsonl"))
            laatste: dict = {}
            for r in led.all_records():
                if not _score(str(r.get("query") or ""), woorden):
                    continue
                key = (r.get("skill"), r.get("query"), r.get("source"))
                if key not in laatste or r.get("ts", 0) >= laatste[key].get("ts", 0):
                    laatste[key] = r
            for r in laatste.values():
                s = _score(str(r.get("query") or ""), woorden)
                item = {"skill": r.get("skill"), "query": (r.get("query") or "")[:150],
                        "bron": r.get("source"), "status": r.get("status"), "ts": r.get("ts")}
                if s >= drempel:
                    kroniek.setdefault(r.get("status"), kroniek["leeg"]).append(item)
                    n_kroniek += 1
                else:
                    context_bak.append((s, {"laag": "kroniek", **item}))
        except Exception:
            pass

        # 4. Projecten — inclusief het antwoord op de projectvraag (dod_outcome)
        projecten: list[tuple[int, dict]] = []
        try:
            from nooch_village.projects import ProjectLedger
            for p in ProjectLedger(os.path.join(dd, "projects.json")).all():
                s = _score(" ".join(str(p.get(k) or "") for k in ("scope", "description", "dod_outcome")),
                           woorden)
                verdeel(s, "project", {"id": p.get("id"), "scope": str(p.get("scope") or "")[:150],
                                       "status": p.get("status"), "archived": bool(p.get("archived")),
                                       "antwoord": (p.get("dod_outcome") or "")[:300] or None,
                                       "owner": p.get("owner")}, projecten)
        except Exception:
            pass

        uit_inz, uit_kaart, uit_proj = _top(inzichten), _top(kaarten), _top(projecten)
        treffers = len(uit_inz) + len(uit_kaart) + len(uit_proj) + n_kroniek
        bekend = treffers > 0
        uit_context = _top(context_bak) if not bekend else _top(context_bak)[:_PER_BAK]
        n_bev, n_leeg, n_fout = (len(kroniek["bevestigd"]), len(kroniek["leeg"]), len(kroniek["fout"]))
        # Alleen de gevulde Kroniek-bakken: drie lege lijsten lazen op de wall als inhoud ("usable
        # (8)") en wonnen van de echte treffers — en van een eerlijk "nee" (skill-review 12-09-2026).
        kroniek = {k: v for k, v in kroniek.items() if v}
        if bekend:
            samenvatting = (f"Yes — {len(uit_inz)} insight(s), {len(uit_kaart)} card(s), "
                            f"{n_kroniek} Chronicle record(s) ({n_bev} confirmed, {n_leeg} empty, "
                            f"{n_fout} failed) and {len(uit_proj)} project(s) touch this question "
                            f"directly.")
        elif uit_context:
            samenvatting = (f"No — no direct answer. {len(uit_context)} adjacent hit(s) come along as "
                            f"context: start there, not from zero.")
        else:
            samenvatting = "No — nothing found; this is uncharted territory for the village."
        uit = {"ok": True, "bekend": bekend, "vraag": vraag, "text": samenvatting,
               "inzichten": uit_inz, "kaarten": uit_kaart, "kroniek": kroniek,
               "projecten": uit_proj, "context": uit_context,
               "treffers": treffers, "samenvatting": samenvatting}
        if not bekend and not uit_context:
            # Niets bekend en niets aangrenzends: een eerlijk "nee" is een gemelde nul (📭), geen
            # succes met de vraag als enige inhoud. `ok` blijft True: de pre-flight en de radar
            # lezen `bekend` en `treffers` ongewijzigd.
            uit.update({"no_data": True, "reason": samenvatting})
        return uit

    def evidence_records(self, result: dict, *, role_id: str) -> list:
        """Elke geheugen-greep is zelf een Kroniek-feit: bevestigd = direct antwoord aanwezig,
        leeg = onontgonnen terrein (het kennisgat is de bevinding; context telt bewust niet
        als 'bekend' — anders verdwijnen gaten achter aangrenzend materiaal)."""
        if not isinstance(result, dict) or not result.get("ok"):
            return []
        return [{"role_id": role_id, "skill": self.name,
                 "query": (result.get("vraag") or "")[:200], "source": "geheugen",
                 "status": "bevestigd" if result.get("bekend") else "leeg",
                 "result_ref": ""}]
