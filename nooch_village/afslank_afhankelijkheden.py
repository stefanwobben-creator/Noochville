"""Geen snit zonder afhankelijkheidscheck — in twee richtingen.

WAAROM DEZE POORT BESTAAT. De afslanking van 28 aug 2026 legde rollen slapend op grond van hun
OPBRENGST (Kroniek-records, deliverables, afgetekende projecten). Geen van de vier poorten vroeg wat
er aan zo'n rol HING. Gevolg, één voor één ontdekt in de dagen erna:

  1. `facilitator` sliep → de DAGBEL viel weg. Het dorp pulseerde drie dagen niet.
  2. `facilitator` sliep → `dag_eindigt` viel weg, en daarmee de dag-afsluitende curatie van de
     Librarian (tag-onderhoud, verband-voorstellen).

     ↳ 1 en 2 kunnen sinds 30 aug 2026 niet meer: de cadans is uit de rol gehaald (`dagcyclus.py`).
       Deze poort blijft het vangnet voor de gevallen die je niet kunt loskoppelen — maar waar je
       een koppeling kúnt wegnemen, is dat sterker dan hem tonen.
  3. `website_watcher` sliep → `pulse_completed` viel weg. Daardoor kon de afrondingsregel niet
     verschijnen en bleven `last_pulse.json` en `pulse_history.jsonl` op 27 augustus staan.
  4. `website_watcher` sliep → de hele GROEI-PULS viel weg: Field Note, Plausible-metrics,
     dode-bron-detectie, doel-gap-signalering, keyword-voorstellen.
  5. `serpapi_trends` werd ingetrokken → de CODE van website_watcher roept hem nog aan, en meldt
     bij elk ontwaken 'dode capability'.

Vier van de vijf zijn dezelfde fout in richting A, de vijfde is richting B. Een poort die alleen
naar opbrengst kijkt, ziet geen van beide.

DRIE RICHTINGEN:

  A. Een ROL slapen of archiveren → wat consumeren ANDEREN van hem? Events die hij publiceert en
     waar een ander op reageert, een eigen ritme (`tick`), en skills die alleen hij houdt.
  B. Een SKILL of grant intrekken → welke CODE roept hem nog aan?
  C. Een ROL slapen of archiveren → wat ligt er nog OP ZIJN BORD? Open projecten verdwijnen niet
     met de rol; ze blijven staan op een bureau waar niemand meer zit.

RICHTING C KWAM LATER, en hij kostte een handmatige opruiming. A en B kijken naar de CODE — wat
publiceert deze rol, wie roept die skill aan — en dat is precies wat je met statische analyse ziet.
Wat er op zijn bord ligt staat niet in de code maar in de DATA, en die vraag stelde niemand. Gevolg
op prod: 5 open projecten op rollen die ná het aanmaken slapend werden gelegd, gevonden toen er al
weken overheen waren.

Een poort die alleen leest wat hij makkelijk kan zien, bewaakt de rest niet.

Statische analyse over de broncode: geen draaiend dorp nodig, en daarom bruikbaar in een dry-run.
Bewust RUIM: liever een afhankelijkheid te veel tonen dan er één missen — dit is een waarschuwing
voor een mens, geen automatische blokkade. Wat er staat, moet je gelezen hebben; wat je dan besluit,
is aan jou.
"""
from __future__ import annotations

import functools
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent

_PUBLICEERT = re.compile(r'Event\(\s*"([a-z_]+)"')
_CONSUMEERT = re.compile(r'(?:react|subscribe)\(\s*"([a-z_]+)"')
_KLASSE = re.compile(r"^class (\w+)", re.M)


@functools.lru_cache(maxsize=1)
def _bronnen() -> dict:
    """Alle modules als tekst, één keer gelezen."""
    uit = {}
    for f in sorted(ROOT.rglob("*.py")):
        try:
            uit[str(f.relative_to(ROOT))] = f.read_text(encoding="utf-8")
        except Exception:                                # noqa: BLE001
            continue
    return uit


def _klasse_van(rol_id: str):
    """De CLASS_MAP-klasse van een rol, of None. Alleen die rollen dragen eigen gedrag."""
    try:
        from nooch_village.village import CLASS_MAP
        return CLASS_MAP.get(rol_id)
    except Exception:                                    # noqa: BLE001
        return None


def _blok_van_klasse(klas) -> str:
    try:
        import inspect
        return inspect.getsource(klas)
    except Exception:                                    # noqa: BLE001
        return ""


def _consumenten(event: str, *, behalve_klasse: str = "") -> list[str]:
    """Welke klassen reageren op dit event? (naam van de klasse waarin de aanroep staat)"""
    uit = []
    for naam, tekst in _bronnen().items():
        for m in re.finditer(rf'(?:react|subscribe)\(\s*"{re.escape(event)}"', tekst):
            kop = _KLASSE.findall(tekst[:m.start()])
            wie = kop[-1] if kop else naam
            if wie != behalve_klasse and wie not in uit:
                uit.append(wie)
    return uit


def rol_afhankelijkheden(rol_id: str, records=None, projects=None) -> dict:
    """RICHTING A. Wat verliest het dorp als deze rol stilvalt?

    Geeft {klasse, events: [{event, consumenten}], eigen_ritme, alleen_houder}. Een lege uitkomst
    betekent: deze rol draagt niets waar een ander op wacht — dan is slapen vrij."""
    klas = _klasse_van(rol_id)
    uit = {"rol": rol_id, "klasse": getattr(klas, "__name__", ""), "events": [],
           "eigen_ritme": False, "alleen_houder": [],
           # RICHTING C staat BUITEN de klasse-check hieronder: een generieke inwoner draagt geen
           # mechanisme, maar zijn bord kan wel vol liggen. Dat was precies het gemiste geval.
           "open_projecten": open_projecten(rol_id, projects)}
    if klas is None:
        return uit                                       # generieke Inwoner: draagt geen mechanisme
    src = _blok_van_klasse(klas)
    uit["eigen_ritme"] = bool(re.search(r"def tick\(", src))
    for ev in sorted(set(_PUBLICEERT.findall(src))):
        if ev.startswith("_"):
            continue
        wie = _consumenten(ev, behalve_klasse=uit["klasse"])
        if wie:
            uit["events"].append({"event": ev, "consumenten": wie})
    if records is not None:
        uit["alleen_houder"] = _alleen_houder(rol_id, records)
    return uit


def open_projecten(rol_id: str, projects=None) -> list[dict]:
    """RICHTING C. Open projecten op het bord van deze rol.

    `projects` is een ProjectLedger of een lijst dicts; zonder store geen uitspraak (leeg) — een
    poort die niets kan zien hoort niets te beweren."""
    if projects is None:
        return []
    try:
        rijen = projects.all() if hasattr(projects, "all") else list(projects)
    except Exception:                                    # noqa: BLE001
        return []
    uit = []
    for p in rijen:
        if not isinstance(p, dict) or p.get("archived"):
            continue
        if str(p.get("status") or "").lower() in ("done", "afgerond", "klaar"):
            continue
        if str(p.get("owner") or "") == rol_id:
            uit.append({"pid": p.get("id"), "status": p.get("status"),
                        "titel": str(p.get("scope") or p.get("label") or "")[:70]})
    return uit


def _alleen_houder(rol_id: str, records) -> list[str]:
    """Skills die ALLEEN deze rol heeft: slaapt hij, dan is die capaciteit het dorp uit."""
    try:
        from nooch_village import org
        rec = records.get(rol_id)
        mijn = set(getattr(getattr(rec, "definition", None), "skills", None) or [])
        if not mijn:
            return []
        anderen = set()
        for r in records.all():
            if r.id == rol_id or org.is_circle(r) or getattr(r, "archived", False) \
                    or getattr(r, "slaapt", False):
                continue
            anderen |= set(getattr(getattr(r, "definition", None), "skills", None) or [])
        return sorted(mijn - anderen)
    except Exception:                                    # noqa: BLE001
        return []


def skill_afhankelijkheden(skill: str) -> dict:
    """RICHTING B. Welke CODE roept deze skill nog aan?

    Zoekt de skill-naam als string in de broncode, buiten zijn eigen implementatie en registratie.
    Ruim: een treffer in commentaar telt mee. Liever één te veel tonen dan de aanroep missen die
    straks 'dode capability' logt."""
    uit = {"skill": skill, "aanroepers": []}
    naald = f'"{skill}"'
    naald2 = f"'{skill}'"
    for naam, tekst in _bronnen().items():
        if naam.startswith("skills_impl/") and skill in naam:
            continue                                     # zijn eigen implementatie
        for i, regel in enumerate(tekst.splitlines(), 1):
            if naald in regel or naald2 in regel:
                if "registry.register" in regel or "register(" in regel:
                    continue                             # de registratie zelf is geen aanroeper
                uit["aanroepers"].append({"bestand": naam, "regel": i,
                                          "code": regel.strip()[:110]})
    return uit


def rapport(rollen: list, skills: list, records=None, projects=None) -> str:
    """Het menselijke overzicht dat vóór de snit op het scherm hoort."""
    regels = []
    for rid in rollen:
        d = rol_afhankelijkheden(rid, records, projects)
        if not (d["events"] or d["eigen_ritme"] or d["alleen_houder"] or d["open_projecten"]):
            regels.append(f"  {rid}: draagt geen mechanisme dat een ander consumeert.")
            continue
        regels.append(f"  ⚠ {rid} ({d['klasse'] or 'generieke inwoner'}) draagt:")
        if d["eigen_ritme"]:
            regels.append("      · een EIGEN RITME (tick) — dat stopt met de rol")
        for e in d["events"]:
            regels.append(f"      · publiceert '{e['event']}' → gelezen door "
                          f"{', '.join(e['consumenten'])}")
        if d["alleen_houder"]:
            regels.append(f"      · is de ENIGE houder van: {', '.join(d['alleen_houder'])}")
        for pj in d["open_projecten"]:
            regels.append(f"      · OPEN PROJECT ({pj['status']}): {pj['titel']}")
    for sk in skills:
        d = skill_afhankelijkheden(sk)
        if not d["aanroepers"]:
            regels.append(f"  {sk}: geen code roept hem nog aan.")
            continue
        regels.append(f"  ⚠ {sk} wordt nog aangeroepen door:")
        for a in d["aanroepers"][:6]:
            regels.append(f"      · {a['bestand']}:{a['regel']}  {a['code']}")
        if len(d["aanroepers"]) > 6:
            regels.append(f"      · … en {len(d['aanroepers']) - 6} meer")
    return "\n".join(regels)
