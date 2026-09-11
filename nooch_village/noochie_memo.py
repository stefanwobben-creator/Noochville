"""Eén memo van Noochie aan de founder, op afroep.

Aanleiding (11 september 2026). Stefan: "ik denk dat Noochie nog dingen naar de verkeerde inbox
stuurt want ik zie niks van haar." Gemeten: het was niet de verkeerde inbox maar géén inbox.
`Noochie._on_dag_eindigt` schrijft elke dag een bulletin naar `data/output/` en publiceert
`bulletin_geschreven`; daar luistert precies één ding naar, `village._observe`, een logger. Ze doet
het werk, het bewijs ligt op schijf, en niemand krijgt het te horen.

Dit is de toets van de pijp, bewust klein: één memo, op afroep, aan de founder gericht, via dezelfde
`_notify_founder`-route die elf andere plekken al gebruiken. Pas als die aankomt gaat de wekelijkse
klok eraan hangen (scope 42) — anders weet je bij een lege inbox niet of de inhoud of de bezorging
het probleem was.

Drie keuzes die niet toevallig zijn:

- **Rauwe invoer, geen eerdere LLM-tekst.** De Field Notes en het bulletin zijn zelf al
  LLM-output; die opnieuw laten samenvatten geeft een memo die geïnformeerd klinkt en niets zegt.
  Hier gaan tellingen en titels in: projecten per status, de claims-werklijst, de events van de
  afgelopen dagen, de draaistaat.
- **Sonnet 5 via `HOOG_INZET`.** Mens-facing, zelfde reden als `skill_bulletin`. Kosten zijn hier
  bewust geen overweging; het is één call.
- **Fail-closed op de LLM.** Geen antwoord = geen memo, en dat zegt het commando met zoveel
  woorden. Er wordt nooit een sjabloon bezorgd alsof Noochie hem schreef.

De memo is in het Nederlands: rapportage aan de mens volgt de taal van de mens (CLAUDE.md, "Taal
van een output"), en dit is precies dat.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import Counter

log = logging.getLogger("village.noochie_memo")

CALL_SITE = "noochie_memo"
AFZENDER = "noochie"
#: Het type dat het inbox-item bij het ontstaan meekrijgt. Daardoor slaat `NotifStore.add` de
#: herschrijf-poort over: die zou de memo (niet-mens-schrijver → herschrijf=True) door een goedkoop
#: model laten herformuleren tot een spanning. De inbox kent dit type niet als beslis-kaart en
#: toont hem daarom als gewone tekst — precies wat een memo moet zijn.
TYPE = "memo"

#: Hoeveel dagen aan events de memo meekrijgt, en hoeveel titels per lijst. Klein gehouden:
#: de memo moet kunnen kiezen, niet alles herhalen.
DAGEN = 7
MAX_TITELS = 8


# ── 1. Verzamelen: rauwe feiten, geen oordelen ───────────────────────────────

def _projecten(st) -> dict:
    """Per status een telling, plus de titels van wat loopt en wat vastzit."""
    try:
        alle = [p for p in st.projects.all() if not p.get("archived")]
    except Exception as exc:                          # noqa: BLE001
        log.warning("noochie_memo: projecten onleesbaar: %s", exc)
        return {"fout": str(exc)}
    per_status = Counter(p.get("status") or "?" for p in alle)
    # De kaarttitel is `scope`, niet `title`: `_scope_text` is de ene plek die dat afleidt (het bord
    # gebruikt hem ook). Mijn eerste versie las `title`/`titel`, en de rooktest op de echte data
    # gaf zestien lege titels — Noochie had zestien naamloze projecten gekregen.
    from nooch_village.views.projects import _scope_text

    def titels(status):
        uit = []
        for p in alle:
            if p.get("status") != status:
                continue
            rij = {"titel": _scope_text(p)[:90], "eigenaar": p.get("owner") or ""}
            if status == "blocked" and p.get("blocked_on") not in (None, "", "—"):
                rij["wacht_op"] = str(p.get("blocked_on"))[:80]
            uit.append(rij)
        return uit[:MAX_TITELS]

    return {"per_status": dict(per_status), "lopend": titels("running"),
            "vastgelopen": titels("blocked"), "totaal": len(alle)}


def _claims(data_dir: str) -> dict:
    """De werklijst uit de claims-database: hoeveel staat open, per oordeel."""
    try:
        from nooch_village import claims_db
        db = claims_db.load(data_dir=data_dir)
    except Exception as exc:                          # noqa: BLE001
        log.warning("noochie_memo: claims-database onleesbaar: %s", exc)
        return {"fout": str(exc)}
    wl = db.get("werklijst") or []
    open_ = [i for i in wl if i.get("status") == "open"]
    return {
        "werklijst": len(wl),
        "open": len(open_),
        "per_oordeel_open": dict(Counter(i.get("oordeel") or "?" for i in open_)),
        "voorbeelden_open": [(i.get("claim") or "")[:80] for i in open_[:5]],
        "handhaving": ((db.get("meta") or {}).get("regelgeving") or {}).get("empco", ""),
    }


def _events(data_dir: str, dagen: int = DAGEN) -> dict:
    """De events uit `system_log.jsonl` van de afgelopen dagen, geteld per naam.

    Het log heeft geen tijdstempel per regel (village._observe schrijft alleen naam + data), dus we
    nemen de STAART van het bestand. Dat is een benadering en de memo krijgt dat te horen."""
    pad = os.path.join(data_dir, "system_log.jsonl")
    namen: Counter = Counter()
    regels = 0
    try:
        with open(pad, encoding="utf-8") as f:
            staart = f.readlines()[-2000:]
        for regel in staart:
            try:
                e = json.loads(regel)
            except ValueError:
                continue
            namen[e.get("event") or "?"] += 1
            regels += 1
    except FileNotFoundError:
        return {"regels": 0, "per_event": {}, "opmerking": "geen system_log gevonden"}
    except Exception as exc:                          # noqa: BLE001
        return {"fout": str(exc)}
    return {"regels": regels, "per_event": dict(namen.most_common(15)),
            "opmerking": f"de laatste {regels} regels van het log; geen tijdstempel per regel"}


def _draaistaat(data_dir: str) -> dict:
    """Wat het gereedschap heeft gedaan. Leeg vlak na de deploy van scope 40, en dat mag de memo
    gewoon zeggen."""
    try:
        from nooch_village import draaistaat
        s = draaistaat.Draaistaat(draaistaat.pad_voor(data_dir)).samenvatting()
    except Exception as exc:                          # noqa: BLE001
        return {"fout": str(exc)}
    return {"skills_gedraaid": len(s),
            "zonder_opbrengst": sorted(k for k, v in s.items() if not v.get("laatste_opbrengst")),
            "met_opbrengst": sorted(k for k, v in s.items() if v.get("laatste_opbrengst"))}


def _backlog(st, circle: str) -> list[str]:
    """Open spanningen in de werkoverleg-backlog van een cirkel."""
    try:
        return [(b.get("title") or "")[:90] for b in st.werk.backlog(circle)][:MAX_TITELS]
    except Exception as exc:                          # noqa: BLE001
        log.debug("noochie_memo: backlog onleesbaar: %s", exc)
        return []


def verzamel(st, data_dir: str, circle: str = "mother_earth__nooch") -> dict:
    """Alle rauwe invoer voor één memo. Elke bron faalt los: een kapotte store levert een `fout`-
    veld op, niet een lege memo."""
    return {
        "datum": time.strftime("%Y-%m-%d"),
        "projecten": _projecten(st),
        "claims": _claims(data_dir),
        "events": _events(data_dir),
        "gereedschap": _draaistaat(data_dir),
        "werkoverleg_backlog": _backlog(st, circle),
    }


# ── 2. Schrijven ─────────────────────────────────────────────────────────────

def prompt_voor(feiten: dict) -> str:
    return (
        "Je bent Noochie, de AI-rol van Nooch (nooch.earth, plantaardige made-to-order sneakers, "
        "missie: het duurzaamste schoenenmerk ter wereld zijn). Je schrijft één memo aan Stefan, "
        "founder en bestuurder. Dit is de eerste keer dat je hem rechtstreeks bereikt.\n\n"
        "Hieronder staan RAUWE feiten uit het dorp: tellingen, titels, een werklijst. Geen "
        "conclusies. Jouw werk is kiezen wat ertoe doet en dat kort en concreet zeggen.\n\n"
        "Regels:\n"
        "- Nederlands, informeel, direct. Geen inleiding, geen 'hopelijk gaat alles goed'.\n"
        "- Maximaal 250 woorden.\n"
        "- Eén kop 'Wat ik zie' met hooguit vier punten: het belangrijkste eerst, met het getal "
        "erbij dat het onderbouwt.\n"
        "- Eén kop 'Wat ik zou doen' met hooguit drie voorstellen. Per voorstel één zin wat, één "
        "zin waarom, en wat het jou kost.\n"
        "- Eén kop 'Wat ik niet weet': wat je uit deze feiten NIET kunt afleiden en wel zou "
        "willen weten. Verzin niets; een lege bron benoem je als leeg.\n"
        "- Geen opsomming van alle feiten. Als iets er niet toe doet, laat je het weg.\n\n"
        f"FEITEN (JSON):\n{json.dumps(feiten, ensure_ascii=False, indent=1)}\n"
    )


def _ladder():
    """De hoog-inzet-ladder voor deze call-site; fail-soft naar de dorpsladder."""
    try:
        from nooch_village.llm_keuze import ladder_voor
        return ladder_voor(CALL_SITE)
    except Exception:                                 # noqa: BLE001
        return None


def schrijf(feiten: dict) -> str | None:
    """Laat Noochie de memo schrijven. None als er geen LLM-antwoord is: fail-closed, geen sjabloon."""
    try:
        from nooch_village.llm import reason
    except Exception as exc:                          # noqa: BLE001
        log.warning("noochie_memo: llm niet beschikbaar: %s", exc)
        return None
    tekst = reason(prompt_voor(feiten), ladder=_ladder(), max_tokens=1200, call_site=CALL_SITE)
    tekst = (tekst or "").strip()
    return tekst or None


# ── 3. Bezorgen ──────────────────────────────────────────────────────────────

def lever(data_dir: str, tekst: str) -> bool:
    """Zet de memo in de cockpit-inbox van de founder, via de bestaande heads-up-route.

    Bewust dezelfde functie als de elf andere founder-meldingen: één bezorgroute, één plek waar
    `FOUNDER_ROLE_ID` telt. De store bewaart de volle tekst en leidt zelf de preview af."""
    try:
        from nooch_village.human_inbox import _notify_founder
        inbox_pad = os.path.join(data_dir, "human_inbox.json")
        _notify_founder(inbox_pad, by=AFZENDER, snippet=tekst, extra={"type": TYPE})
        return True
    except Exception as exc:                          # noqa: BLE001
        log.warning("noochie_memo: bezorgen mislukt: %s", exc)
        return False


# ── Het geheel ───────────────────────────────────────────────────────────────

def memo(st, data_dir: str, *, apply: bool = True) -> dict:
    """Verzamel, schrijf, bezorg. Geeft een rapport terug dat zegt wat er wél en niet gebeurde.

    `apply=False` schrijft de memo wel maar bezorgt niet: je leest hem in de terminal en beslist
    dan. Dat is de dry-run-conventie van het dorp (`wiki_zaad`, `wiki_broncheck`)."""
    feiten = verzamel(st, data_dir)
    tekst = schrijf(feiten)
    if tekst is None:
        return {"ok": False, "reden": "geen LLM-antwoord: memo niet geschreven en niet bezorgd",
                "feiten": feiten, "tekst": None, "bezorgd": False}
    bezorgd = lever(data_dir, tekst) if apply else False
    return {"ok": True, "tekst": tekst, "bezorgd": bezorgd, "feiten": feiten,
            "reden": "" if (bezorgd or not apply) else "geschreven maar niet bezorgd"}
