"""Het dorp afslanken — slapen leggen wat niets opleverde, opruimen wat nooit bestond.

Bron van waarheid is `data/output/waarde_audit_<datum>.md`, niet een lijst in de code en niet een
herinnering. Dit bestand LEEST dat verslag en voert uit wat erin staat; verandert de audit, dan
verandert deze operatie mee.

**Slapen is niet verwijderen.** Een slapende rol houdt zijn purpose, accountabilities, domeinen,
versie en historie. Wat stopt is de uitvoering: geen thread (`Reconciler`), geen oordeel over zijn
spanningen (`spanning_ontstaat`), en geen nieuw werk via de routering (`escalation_router.roster`).
Eén commando zet hem terug:

    python -m nooch_village.village afslanken wek <rol_id>

**Fail-closed op drie punten**, en die zijn niet onderhandelbaar:

1. **Grondwettelijke rollen blijven onaangeraakt.** Een Circle Lead, Circle Rep, Secretary of
   Facilitator draagt governance; die slaap leggen is de organisatie zelf uitzetten. De audit
   markeert ze al als `structureel`; hier worden ze bovendien op id geweigerd, zodat een verkeerd
   verslag ze nog steeds niet kan raken.
2. **Een skill die een WAKKERE rol houdt, wordt niet aangeraakt.** De audit beoordeelt een skill op
   "zit er een deliverable in een afgetekend project" — en dat is bij compliance en de librarian
   massaal niet zo, terwijl die rollen wél wakker blijven. Die skills wegnemen zou een wakkere rol
   zijn handen afnemen op grond van een meting over iets anders (het ontbreken van handtekeningen).
   Ze worden overgeslagen en gerapporteerd, niet stilzwijgend meegenomen.
3. **`vlag voor Stefan` wordt nooit uitgevoerd.** Dat is per definitie het geval dat de data niet
   kon beslissen.

**Dry-run is de default.** Er wordt niets geschreven zonder `--apply`, en de dry-run toont per regel
het bewijs waarop het besluit rust.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time

log = logging.getLogger("village.afslanken")

BESTAND = "afslanken.jsonl"

SLAPEN, OPRUIMEN, WAKKER, VLAG = "slapen", "opruimen", "wakker houden", "vlag voor Stefan"
STRUCTUREEL = "structureel"

# ── het verslag lezen ───────────────────────────────────────────────────────

_ID_RE = re.compile(r"^- \*\*(.+?)\*\* \(`(.+?)`\)")


def lees_audit(pad: str) -> dict:
    """{"rollen": [{naam, id, advies, bewijs}], "skills": [{naam, advies, bewijs}]}.

    Puur lezen: geen store, geen netwerk. Een verslag dat niet te lezen is levert lege lijsten op —
    en dan doet de operatie niets, wat het juiste gedrag is (fail-closed)."""
    try:
        regels = open(pad, encoding="utf-8").read().splitlines()
    except OSError as e:
        log.warning("audit-verslag niet leesbaar (%s) — er wordt niets voorgesteld", e)
        return {"rollen": [], "skills": [], "pad": pad}

    ids: dict = {}
    for r in regels:
        m = _ID_RE.match(r)
        if m:
            ids.setdefault(m.group(1), m.group(2))

    sectie = None
    uit: dict = {"rollen": [], "skills": [], "pad": pad}
    for r in regels:
        if r.startswith("## Rollen"):
            sectie = "rollen"; continue
        if r.startswith("## Skills"):
            sectie = "skills"; continue
        if r.startswith("## ") and sectie:
            sectie = None
        if not sectie or not r.startswith("| ") or "---" in r:
            continue
        c = [x.strip() for x in r.strip("|").split("|")]
        if len(c) < 6 or c[0] in ("rol", "skill"):
            continue
        naam = c[0].strip("`")
        # Kolommen: naam | bracht voort | Nooch-uitkomst? | kosten | laatst | advies.
        # `bewijs` is de "bracht voort"-kolom: dát is waarop een slaap-besluit rust. Een slaap-
        # besluit rust namelijk op een AFWEZIGHEID (geen uitkomst), en een afwezigheid heeft geen
        # eigen id — het anker is de auditregel zelf plus wat de rol wél produceerde.
        uit[sectie].append({"naam": naam, "id": ids.get(naam, ""), "advies": c[-1],
                            "bewijs": c[1], "uitkomst": c[2], "kosten": c[3], "laatst": c[4]})
    return uit


# ── de poorten ──────────────────────────────────────────────────────────────

def is_grondwettelijk(rol_id: str) -> bool:
    """Dezelfde definitie als de audit gebruikt — één plek, geen tweede lijst."""
    from nooch_village.waarde_audit import is_structureel
    return is_structureel(rol_id)


def wakkere_rollen(audit: dict, records) -> set[str]:
    ids = set()
    for r in audit["rollen"]:
        if r["advies"] == WAKKER and r["id"]:
            ids.add(r["id"])
    return ids


def skills_van_wakkere_rollen(audit: dict, records) -> dict:
    """{skill: [wakkere rol-ids]} — de skills die we NIET mogen aanraken, met wie erop leunt."""
    uit: dict = {}
    wakker = wakkere_rollen(audit, records)
    for rid in wakker:
        rec = records.get(rid) if records is not None else None
        for s in (getattr(getattr(rec, "definition", None), "skills", None) or []):
            uit.setdefault(str(s), []).append(rid)
    return uit


# ── het plan ────────────────────────────────────────────────────────────────

def plan(audit: dict, records, *, kill_skills: tuple = (), uit_governance: tuple = ()) -> dict:
    """Wat er zou gebeuren. Schrijft niets.

    `kill_skills` en `uit_governance` zijn EXPLICIETE menselijke besluiten die boven de audit gaan
    (de founder mag een skill killen die de audit alleen wilde laten slapen). Ze lopen wél langs
    dezelfde poorten: ook een menselijk besluit raakt geen grondwettelijke rol."""
    beschermd = skills_van_wakkere_rollen(audit, records)
    slapen, opruimen, overgeslagen, geweigerd = [], [], [], []

    for r in audit["rollen"]:
        rid = r["id"]
        if not rid:
            geweigerd.append({**r, "waarom": "geen rol-id in het verslag te vinden"})
            continue
        rec = records.get(rid) if records is not None else None
        if rec is None:
            geweigerd.append({**r, "waarom": "staat niet (meer) in de records"})
            continue
        if is_grondwettelijk(rid):
            overgeslagen.append({**r, "waarom": "grondwettelijke rol — governance-drager"})
            continue
        if r["advies"] == VLAG:
            overgeslagen.append({**r, "waarom": "de data kon dit niet beslissen — dit is aan Stefan"})
            continue
        if getattr(rec, "slaapt", False):
            overgeslagen.append({**r, "waarom": "slaapt al"})
            continue
        if r["advies"] == SLAPEN:
            slapen.append({**r, "soort": "rol"})
        elif r["advies"] == OPRUIMEN:
            opruimen.append({**r, "soort": "rol"})

    for s in audit["skills"]:
        naam = s["naam"]
        expliciet = naam in kill_skills or naam in uit_governance
        if s["advies"] not in (SLAPEN, OPRUIMEN) and not expliciet:
            continue
        houders = beschermd.get(naam) or []
        if houders and not expliciet:
            overgeslagen.append({**s, "waarom": ("een WAKKERE rol houdt deze skill: "
                                                 + ", ".join(sorted(houders)))})
            continue
        # SLAPEN IS GEEN INTREKKEN. Voor een rol bestaat een omkeerbare slaap; voor een skill niet —
        # de enige knop is hem uit het DNA halen, en dat is een zwaardere ingreep dan de audit
        # vroeg. Stilzwijgend escaleren van 'slapen' naar 'weg' is precies de fout die deze hele
        # operatie moest vermijden, dus dit gaat naar de mens.
        if s["advies"] == SLAPEN and not expliciet:
            overgeslagen.append({**s, "waarom": ("de audit zegt slapen, maar voor een skill bestaat "
                                                 "geen omkeerbare slaap — intrekken zou een "
                                                 "zwaardere ingreep zijn dan gevraagd")})
            continue
        opruimen.append({**s, "soort": "skill", "houders": houders,
                         "expliciet": expliciet, "advies": OPRUIMEN})

    return {"slapen": slapen, "opruimen": opruimen, "overgeslagen": overgeslagen,
            "geweigerd": geweigerd, "audit_pad": audit.get("pad", "")}


# ── uitvoeren ───────────────────────────────────────────────────────────────

def _log_regel(data_dir: str, rij: dict) -> None:
    """Append-only spoor: wat er is gedaan, waarop het rustte, en hoe je het terugdraait."""
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, BESTAND), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({**rij, "ts": time.time()}, ensure_ascii=False) + "\n")
    except OSError as e:                                  # noqa: BLE001
        log.warning("afslank-spoor niet weggeschreven: %s", e)


def slaap_leggen(records, rol_id: str, *, reden: str, data_dir: str = "") -> bool:
    """Zet één rol op slapend. Idempotent, en het record blijft compleet."""
    rec = records.get(rol_id)
    if rec is None or is_grondwettelijk(rol_id):
        return False
    if getattr(rec, "slaapt", False):
        return False
    rec.slaapt = True
    rec.slaap_reden = reden
    rec.slaap_sinds = time.time()
    records.put(rec)
    if data_dir:
        _log_regel(data_dir, {"actie": "slaap", "id": rol_id, "reden": reden,
                              "terug": f"village afslanken wek {rol_id}"})
    return True


def wekken(records, rol_id: str, *, data_dir: str = "") -> bool:
    """De terugweg. Eén veld terug, en de Reconciler bouwt de rol bij de volgende start gewoon weer
    op — daarom is slapen omkeerbaar en archiveren niet."""
    rec = records.get(rol_id)
    if rec is None or not getattr(rec, "slaapt", False):
        return False
    rec.slaapt = False
    rec.slaap_reden = None
    rec.slaap_sinds = None
    records.put(rec)
    if data_dir:
        _log_regel(data_dir, {"actie": "wek", "id": rol_id})
    return True


def skill_herstellen(records, skill: str, rol_id: str, *, data_dir: str = "") -> bool:
    """De terugweg voor een ingetrokken skill: markering weg én de skill terug in het DNA."""
    rec = records.get(rol_id)
    if rec is None or skill not in (rec.ingetrokken_skills or []):
        return False
    rec.ingetrokken_skills = [s for s in rec.ingetrokken_skills if s != skill]
    if skill not in rec.definition.skills:
        rec.definition.skills = list(rec.definition.skills) + [skill]
    rec.version = int(getattr(rec, "version", 1)) + 1
    records.put(rec)
    if data_dir:
        _log_regel(data_dir, {"actie": "skill_herstel", "skill": skill, "id": rol_id})
    return True


def rol_opruimen(records, rol_id: str, *, reden: str, data_dir: str = "") -> bool:
    """Een rol die nooit iets voortbracht: archiveren. Ook dit is een record-mutatie, geen delete —
    de historie blijft, hij verdwijnt alleen uit de levende organisatie."""
    rec = records.get(rol_id)
    if rec is None or is_grondwettelijk(rol_id) or getattr(rec, "archived", False):
        return False
    rec.archived = True
    records.put(rec)
    if data_dir:
        _log_regel(data_dir, {"actie": "archiveer_rol", "id": rol_id, "reden": reden,
                              "terug": "zet archived terug op false in governance_records.json"})
    return True


def skill_intrekken(records, skill: str, *, reden: str, data_dir: str = "") -> list[str]:
    """Haal een skill uit het DNA van elke rol die hem houdt. Geeft de geraakte rol-ids terug.

    Dit is de enige manier waarop declaratie en code weer kloppen als een skill niet bestaat: de
    rol beweert iets te kunnen wat er niet is, en dat is geen kleinigheid — `dormant_capabilities`
    waarschuwt er bij elke start over."""
    geraakt = []
    for rec in list(records.all()):
        skills = list(getattr(rec.definition, "skills", None) or [])
        if skill not in skills:
            continue
        rec.definition.skills = [s for s in skills if s != skill]
        # Vastleggen DÁT het is ingetrokken, niet alleen dat het weg is. De seeding voegt
        # "idempotent" skills terug toe; zonder deze markering staat de skill er na de eerstvolgende
        # herstart gewoon weer, en dan heeft een start-routine een governance-besluit overruled.
        if skill not in (rec.ingetrokken_skills or []):
            rec.ingetrokken_skills = list(rec.ingetrokken_skills or []) + [skill]
        rec.version = int(getattr(rec, "version", 1)) + 1     # DNA-wijziging = versie omhoog
        records.put(rec)
        geraakt.append(rec.id)
    if geraakt and data_dir:
        _log_regel(data_dir, {"actie": "skill_intrekken", "skill": skill, "reden": reden,
                              "rollen": geraakt,
                              "terug": f"voeg '{skill}' terug toe aan de skills van: "
                                       f"{', '.join(geraakt)}"})
    return geraakt


def voer_uit(plan_: dict, records, *, data_dir: str) -> dict:
    """Voer het plan uit. Alleen aanroepen ná een dry-run en een menselijk akkoord."""
    gedaan = {"slaap": [], "archiveer_rol": [], "skill_intrekken": []}
    for r in plan_["slapen"]:
        reden = f"waarde-audit: {r['advies']} — {r['bewijs'][:120]}"
        if slaap_leggen(records, r["id"], reden=reden, data_dir=data_dir):
            gedaan["slaap"].append(r["id"])
    for r in plan_["opruimen"]:
        reden = f"waarde-audit: opruimen — {r['bewijs'][:120]}"
        if r["soort"] == "rol":
            if rol_opruimen(records, r["id"], reden=reden, data_dir=data_dir):
                gedaan["archiveer_rol"].append(r["id"])
        else:
            geraakt = skill_intrekken(records, r["naam"], reden=reden, data_dir=data_dir)
            if geraakt:
                gedaan["skill_intrekken"].append({"skill": r["naam"], "rollen": geraakt})
    records.save()
    return gedaan


# ── het rapport ─────────────────────────────────────────────────────────────

def rapport_tekst(plan_: dict, *, apply: bool) -> str:
    kop = "TOEGEPAST" if apply else "DRY-RUN — er is niets geschreven"
    uit = [f"# Afslanken — {kop}", "",
           f"Bron: `{plan_['audit_pad']}`", ""]

    uit += [f"## Slapen ({len(plan_['slapen'])} rollen)", ""]
    if plan_["slapen"]:
        uit += ["Omkeerbaar: het record blijft compleet, alleen de uitvoering stopt.", "",
                "| rol | waarop dit rust | kosten | laatst |", "|---|---|---|---|"]
        uit += [f"| {r['naam']} (`{r['id']}`) | {r['bewijs']} | {r['kosten']} | {r['laatst']} |"
                for r in plan_["slapen"]]
    else:
        uit += ["Niets."]
    uit.append("")

    rollen = [r for r in plan_["opruimen"] if r["soort"] == "rol"]
    skills = [r for r in plan_["opruimen"] if r["soort"] == "skill"]
    uit += [f"## Opruimen ({len(rollen)} rollen, {len(skills)} skills)", ""]
    if rollen:
        uit += ["**Rollen** — gearchiveerd, niet verwijderd: de historie blijft staan.", "",
                "| rol | waarop dit rust | laatst |", "|---|---|---|"]
        uit += [f"| {r['naam']} (`{r['id']}`) | {r['bewijs']} | {r['laatst']} |" for r in rollen]
        uit.append("")
    if skills:
        uit += ["**Skills** — uit het DNA van elke rol die hem hield (versie omhoog).", "",
                "| skill | waarop dit rust | besluit |", "|---|---|---|"]
        uit += [f"| `{r['naam']}` | {r['bewijs']} | "
                f"{'expliciet besluit van de founder' if r.get('expliciet') else 'volgt de audit'}"
                f"{' · wordt gehouden door: ' + ', '.join(r['houders']) if r.get('houders') else ''} |"
                for r in skills]
        uit.append("")

    uit += [f"## Overgeslagen ({len(plan_['overgeslagen'])})", "",
            "Deze zijn bewust NIET aangeraakt:", ""]
    uit += [f"- **{o['naam']}** — {o['waarom']}" for o in plan_["overgeslagen"]] or ["- niets"]
    uit.append("")

    if plan_["geweigerd"]:
        uit += [f"## Geweigerd ({len(plan_['geweigerd'])})", "",
                "Het verslag noemt ze, maar ze zijn niet te koppelen aan een record:", ""]
        uit += [f"- **{g['naam']}** — {g['waarom']}" for g in plan_["geweigerd"]]
        uit.append("")

    uit += ["## Terugdraaien", "",
            "```bash",
            "python -m nooch_village.village afslanken wek <rol_id>    # één rol weer wakker",
            "```",
            "Een gearchiveerde rol of een ingetrokken skill draai je terug via het spoor in "
            "`data/afslanken.jsonl`: elke regel draagt zijn eigen `terug`-instructie.", ""]
    return "\n".join(uit)
