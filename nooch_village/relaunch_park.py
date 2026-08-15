"""Parkeren op één verklaard feit: de website wordt herbouwd.

Een cluster spanningen hangt aan de HUIDIGE site — de footer inspecteren, het Plant Based
Treaty-logo lokaliseren, live claim-checks, pagina-fetches, FAQ-citaten, en het capability-item
"home geeft geen HTML". Ze los afhandelen is werk aan iets dat verdwijnt: de scan nu tegen de oude
site repareren levert een fix op voor een pagina die er straks niet meer is.

Eén feit parkeert ze dus allemaal, taken én capability-item, met één terugkeer-voorwaarde:

    reden       relaunch
    voorwaarde  komt terug als de nieuwe site live is en compliance opnieuw scant
    trigger     handmatig, één keer — niet per item een eigen datum

**Parkeren is geen oordeel.** Er komt geen founder-label aan te pas en niets wordt afgewezen: bij de
rol landt dit als gehoord-en-vastgehouden. Een label zou de Founder Flow iets onwaars leren ("de
founder wees dit af" terwijl hij zei "niet nu"), en dat onderscheid is structureel — zie
`founder_park`, dat om exact dezelfde reden buiten de labelstroom leeft.

**Parkeren mag de substantie niet weggooien.** De compliance-flags in dit cluster zijn INPUT voor de
herbouw, geen ruis. Daarom bewaart deze module de volledige tekst van elk geparkeerd item in
`data/relaunch_park.jsonl` — niet alleen een verwijzing. Een verwijzing naar een project dat
intussen is opgeruimd, levert bij de relaunch een lege lijst op, en dan is de herbouw precies het
bewijs kwijt waarvoor hij hem nodig had.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time

log = logging.getLogger("village.relaunch_park")

BESTAND = "relaunch_park.jsonl"
REDEN = "relaunch"
VOORWAARDE = "komt terug als de nieuwe site live is en compliance opnieuw scant"

# Wat "site-afhankelijk" betekent, expliciet. Bewust een lijst patronen en geen LLM-oordeel: dit
# is een bulk-parkering op een verklaard feit, en dan hoort zichtbaar te zijn wát eronder valt.
_PATRONEN = (
    ("footer-inspectie",   re.compile(r"footer", re.I)),
    ("logo op de site",    re.compile(r"\blogo\b|plant based treaty|peta approved", re.I)),
    # Let op de tweede voorwaarde. Een kale vermelding van het domein is GEEN site-afhankelijkheid:
    # "meetbaar rapporteren op nooch.earth" en "prototypes delen op Nooch.earth" zijn doelen die de
    # site als publicatieplek noemen. Die parkeren zou echt werk stilzetten op een woordvondst.
    # Gezien in de eerste prod-dry-run, vóór het live ging.
    ("live claim-check",   re.compile(r"claim-scan|site-scan|live claim", re.I)),
    ("live claim-check",   (re.compile(r"nooch\.earth|op de (?:site|website)", re.I),
                            re.compile(r"\b(?:check|scan|verify|verif|controleer|inspect|"
                                       r"lees|toets|claim)\w*", re.I))),
    ("pagina-fetch",       re.compile(r"blijft blind|gaf HTTP|scan onvolledig|"
                                      r"scrape|fetch (?:the )?(?:live )?page|pagina.{0,12}ophalen",
                                      re.I)),
    ("citaat van de site", re.compile(r"literal quote|letterlijk citaat|exacte? (?:quote|citaat)|"
                                      r"\bFAQ\b|"
                                      # 'Locate and screenshot the exact claim as it currently
                                      # appears' — lokaliseren of vastleggen van een claim ZOALS
                                      # die nu op de site staat. Ontsnapte aan de eerste ronde en
                                      # hoort onmiskenbaar in dit cluster.
                                      r"locate\b[^.]{0,60}\bclaim|screenshot|"
                                      r"as it currently (?:appears|stands)", re.I)),
)


def soort(tekst: str) -> str:
    """Onder welke noemer valt dit item, of "" als het niet site-afhankelijk is.

    Een entry is één patroon, of een PAAR dat allebei moet raken. Dat paar bestaat omdat een
    verwijzing naar de site nog geen afhankelijkheid ván de site is."""
    tekst = tekst or ""
    for naam, pat in _PATRONEN:
        if isinstance(pat, tuple):
            if all(p.search(tekst) for p in pat):
                return naam
        elif pat.search(tekst):
            return naam
    return ""


def pad(data_dir: str) -> str:
    return os.path.join(data_dir, BESTAND)


def _schrijf(data_dir: str, rijen: list[dict]) -> int:
    if not rijen:
        return 0
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(pad(data_dir), "a", encoding="utf-8") as fh:
            for r in rijen:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    except OSError as e:
        log.warning("relaunch-park niet vastgelegd: %s", e)
        return 0
    return len(rijen)


def alle(data_dir: str) -> list[dict]:
    uit = []
    try:
        with open(pad(data_dir), encoding="utf-8") as fh:
            for regel in fh:
                regel = regel.strip()
                if regel:
                    try:
                        uit.append(json.loads(regel))
                    except ValueError:
                        continue
    except FileNotFoundError:
        return []
    except OSError as e:
        log.warning("relaunch-park onleesbaar: %s", e)
    return uit


def geparkeerd(data_dir: str) -> list[dict]:
    """Wat er NU geparkeerd staat (een 'terug'-regel heft een eerdere parkering op)."""
    stand: dict[str, dict] = {}
    for r in sorted(alle(data_dir), key=lambda x: x.get("ts", 0)):
        sleutel = f"{r.get('soort_bron')}:{r.get('ref')}"
        if r.get("terug"):
            stand.pop(sleutel, None)
        else:
            stand[sleutel] = r
    return list(stand.values())


def park(data_dir: str, *, projects=None, notif=None, targets=None, door: str = "founder",
         dry_run: bool = True) -> dict:
    """Parkeer alles wat aan de huidige site hangt, in één keer.

    Projecten worden geparkeerd met reden `relaunch`; notificaties krijgen het park-oordeel en gaan
    uit de wachtrij. Van álles wordt de volledige tekst bewaard, want dat is de input voor de
    herbouw."""
    rijen, gepakt = [], {"projecten": 0, "notificaties": 0, "per_soort": {}}

    if projects is not None:
        for status in ("queued", "running", "blocked", "future", "review"):
            for p in projects.by_status(status):
                tekst = " ".join(str(p.get("scope") or "").split())
                s = soort(tekst)
                if not s:
                    continue
                gepakt["per_soort"][s] = gepakt["per_soort"].get(s, 0) + 1
                gepakt["projecten"] += 1
                rijen.append({"soort_bron": "project", "ref": p.get("id"), "soort": s,
                              "eigenaar": p.get("owner"), "tekst": tekst, "reden": REDEN,
                              "voorwaarde": VOORWAARDE, "door": door, "ts": time.time()})
                if not dry_run:
                    projects.park(p["id"], REDEN,
                                  [{"id": p["id"], "text": tekst[:200], "reden": REDEN}], door=door)

    if notif is not None and targets is not None:
        for n in notif.open_for_targets(targets):
            tekst = " ".join(str(n.get("snippet") or "").split())
            s = soort(tekst)
            if not s:
                continue
            gepakt["per_soort"][s] = gepakt["per_soort"].get(s, 0) + 1
            gepakt["notificaties"] += 1
            rijen.append({"soort_bron": "notificatie", "ref": n.get("id"), "soort": s,
                          "eigenaar": n.get("target_id"), "tekst": tekst, "reden": REDEN,
                          "voorwaarde": VOORWAARDE, "door": door, "ts": time.time()})
            if not dry_run:
                # Verwerkt + gearchiveerd met de reden als uitkomst: uit de wachtrij, maar het
                # spoor blijft. Geen 'rejected', geen founder-label — dit is geen oordeel.
                notif.set_poort(n.get("id"), {"deur": "geparkeerd", "reden": VOORWAARDE,
                                              "bewijs": REDEN, "sleutel": f"relaunch:{s}"})
                notif.mark_item_processed(
                    n.get("id"), outcome=f"geparkeerd (relaunch): {VOORWAARDE}", by="relaunch-park")
                notif.archive_item(n.get("id"))

    if not dry_run:
        _schrijf(data_dir, rijen)
        log.info("relaunch-park: %d project(en) en %d notificatie(s) geparkeerd — %s",
                 gepakt["projecten"], gepakt["notificaties"], VOORWAARDE)
    gepakt["dry_run"] = dry_run
    gepakt["items"] = rijen
    return gepakt


def heropen(data_dir: str, *, projects=None, door: str = "founder") -> dict:
    """De ene trigger: de nieuwe site is live. Alles komt in één keer terug.

    Projecten worden gedeblokkeerd; de bewaarde teksten komen terug als de herbeoordelings-lijst
    voor compliance. Append-only: er wordt een 'terug'-regel geschreven, niets herschreven."""
    staand = geparkeerd(data_dir)
    terug, rijen = [], []
    for r in staand:
        rijen.append({**{k: r.get(k) for k in ("soort_bron", "ref", "soort", "eigenaar", "tekst")},
                      "terug": True, "door": door, "ts": time.time()})
        if r.get("soort_bron") == "project" and projects is not None:
            try:
                projects.unblock(r["ref"])
            except Exception as e:                     # noqa: BLE001 — nooit stil verliezen
                log.warning("relaunch-park: kon project %s niet deblokkeren: %s", r.get("ref"), e)
        terug.append(r)
    _schrijf(data_dir, rijen)
    log.info("relaunch-park: %d item(s) teruggehaald voor herbeoordeling", len(terug))
    return {"teruggehaald": len(terug), "items": terug}
