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
_PER_BAK = 8            # max treffers per geheugenlaag — genoeg om te weten dat het er is

# Nederlandse functiewoorden van ≥4 tekens die anders als 'betekenis' meetellen — substring-
# matchen is bewust (schoenen ⊂ schoenenindustrie), dus deze ruis moet er expliciet uit.
_STOP = {"voor", "over", "naar", "deze", "onze", "zijn", "wordt", "worden", "heeft",
         "hebben", "maar", "niet", "alle", "andere", "tussen", "door", "weten", "welke",
         "over", "ook", "zonder", "moet", "moeten", "gaat", "gaan", "veel", "meer"}


def _woorden(vraag: str) -> list[str]:
    return [w for w in re.findall(r"[\w-]+", (vraag or "").lower())
            if len(w) >= _MIN_WOORD and w not in _STOP]


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
    description = ("Geheugen-eerst: weten we dit al (ja/nee)? Doorzoekt kennisbank, "
                   "kaarten-bibliotheek, De Kroniek en projecten. Bij nee komt wat het dorp "
                   "wél al weet over het onderwerp mee als context. Deterministisch, geen LLM.")
    input_schema = "vraag: str (verplicht — waar wil je van weten of het dorp het al weet)"
    required_payload = ("vraag",)
    output_schema = ("ok: bool, bekend: bool, vraag: str, inzichten: list, kaarten: list, "
                     "kroniek: {bevestigd, leeg, fout}, projecten: list, context: list, "
                     "treffers: int, samenvatting: str | error")

    def _dd(self, context) -> str:
        return getattr(context, "data_dir", ".") or "."

    def run(self, payload: dict, context=None) -> dict:
        vraag = ((payload or {}).get("vraag") or "").strip()
        woorden = _woorden(vraag)
        if not woorden:
            return {"ok": False, "error": "geef een vraag met minstens één betekenisvol woord"}
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
        if bekend:
            samenvatting = (f"Ja — {len(uit_inz)} inzicht(en), {len(uit_kaart)} kaart(en), "
                            f"{n_kroniek} Kroniek-regel(s) ({len(kroniek['bevestigd'])} bevestigd, "
                            f"{len(kroniek['leeg'])} leeg, {len(kroniek['fout'])} fout) en "
                            f"{len(uit_proj)} project(en) raken deze vraag direct.")
        elif uit_context:
            samenvatting = (f"Nee — geen direct antwoord. Wel {len(uit_context)} aangrenzende "
                            f"treffer(s) als context: begin dáár, niet bij nul.")
        else:
            samenvatting = "Nee — niets gevonden; dit is onontgonnen terrein voor het dorp."
        return {"ok": True, "bekend": bekend, "vraag": vraag,
                "inzichten": uit_inz, "kaarten": uit_kaart, "kroniek": kroniek,
                "projecten": uit_proj, "context": uit_context,
                "treffers": treffers, "samenvatting": samenvatting}

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
