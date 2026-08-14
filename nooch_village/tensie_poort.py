"""De poort vóór elke menselijke escalatie: wat mag de founder überhaupt zien?

De founder-inbox liep vol met werk dat het dorp zelf hoort af te handelen: projecten die zichzelf
als verse tensie uitspuwen, taken voor een rol die bij de mens landden, en dezelfde kapotte bron in
vier varianten. Het probleem was niet de bewoording maar de trechter — er stond niets tussen "een
rol kan niet verder" en "de mens ziet het". Mooiere tensie-zinnen op dezelfde trechter is verf op
roest.

Vier checks, in deze volgorde. De eerste die pakt wint, en elke uitkomst draagt een reden.

  1. GEBORGD    hangt dit al aan een levend project? → wacht op uitvoering, geen ping.
  2. ROUTERING  bezit een rol dit op PURPOSE/ACCOUNTABILITY? → toewijzen, dorp-intern.
  3. MENS-WERK  pas als geen rol past én het fysiek/extern is → mens-todo (aparte lijst).
  4. DE DEUREN  nieuwe rol, nieuwe skill, of een besluit dat de grondwet aan de founder houdt.

**Het human-label wordt niet geloofd.** Van de elf items die als park-reden `human` binnenkwamen,
waren er vier gewoon rolwerk ("flag if the result count is noisy"). Daarom loopt ÉLK item door de
routering, ook een als-mens-gelabeld item; alleen wat de match als NONE bestempelt én fysiek is
blijft mens-werk. Zo schoont één stap de systeem-missers en de verkeerde labels tegelijk.

**Routering gebruikt de LLM-match van `escalation_router`, niet een lagere woord-drempel.** Een
lagere drempel is de gok-handoff die een item op het verkeerde bureau legt. De match kan expliciet
"NONE" zeggen; zonder die uitspraak zou niets ooit deur 1 of 2 halen en was de uitweg naar een
nieuwe rol of skill dood.

**Kapotte capaciteit is ops, geen founder-besluit.** "Nieuwe skill" betekent: een capaciteit die
niet bestaat en gebouwd moet worden. Een bron die stukging en een rol die zijn puls oversloeg zijn
storingen — die gaan naar de systeem-health-monitor. Ze bereiken de founder pas als ze AANHOUDEN
(op meerdere dagen terugkomen), en dan als deur 3 met een investeringsvraag, niet als ruis.

**De poort logt wat hij wegfilterde en waarom.** Een stil filter dat per ongeluk een echt
deur-3-item wegvangt is dezelfde declaratie-wijkt-af-van-handhaving-kwaal als de luna-trede zonder
prijs. Elke uitkomst draagt `deur`, `reden` en `bewijs`; waar de regels het niet zeker weten komt
er `ONBESLIST` uit, geen gok.
"""
from __future__ import annotations

import datetime
import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger("village.tensie_poort")

# ── De uitkomsten ───────────────────────────────────────────────────────────
GEBORGD      = "geborgd"        # hangt aan een levend project → wacht op uitvoering
AFGEHANDELD  = "afgehandeld"    # het project is al klaar
GEROUTEERD   = "gerouteerd"     # een rol bezit dit → dorp-intern
MENS_WERK    = "mens_werk"      # fysiek/extern én geen rol → mens-todo
OPS          = "ops"            # kapotte bestaande capaciteit → systeem-health, niet de inbox
DEUR_ROL     = "deur_rol"       # geen rol dekt dit werk → rol aanmaken
DEUR_SKILL   = "deur_skill"     # capaciteit bestaat niet → skill bouwen
DEUR_BESLUIT = "deur_besluit"   # voorbehouden domein → besluit voor de founder
ONBESLIST    = "onbeslist"      # geen regel pakte dit — expliciet, nooit stil

DEUREN = (DEUR_ROL, DEUR_SKILL, DEUR_BESLUIT)
STIL   = (GEBORGD, AFGEHANDELD, GEROUTEERD, OPS)

# Hoeveel verschillende DAGEN een storing moet terugkomen voor hij een founder-vraag wordt.
# Eén dag is een hik; drie dagen is een bron die dood is en waar een keuze onder ligt.
OPS_VOLHARDING_DAGEN = 3


@dataclass
class Besluit:
    deur: str
    reden: str                       # het log, geen debug-extra
    bewijs: str = ""
    naar_rol: str = ""
    sleutel: str = ""                # dedup: gelijke sleutel = één beslissing
    klasse: str = ""                 # de soort melding, voor de dedup op klasse-niveau
    meta: dict = field(default_factory=dict)


# ── 1. Geborgd ──────────────────────────────────────────────────────────────

LEVEND = frozenset({"queued", "running", "blocked", "future", "review", "todo", "active"})
KLAAR  = frozenset({"done", "cancelled", "archived"})


def _park_redenen(project: dict) -> set[str]:
    park = (project or {}).get("park") or {}
    redenen = {str(park.get("reden") or "")} if park.get("reden") else set()
    for it in park.get("items") or []:
        if it.get("reden"):
            redenen.add(str(it["reden"]))
    return {r for r in redenen if r}


def geborgd(notif: dict, projects) -> Besluit | None:
    """Hangt deze tensie al aan een project? Dan is het werk belegd."""
    pid = str(notif.get("project_id") or "")
    if not pid:
        return None
    p = projects.get(pid)
    if p is None:
        log.warning("poort: notificatie verwijst naar verdwenen project %s — niet geborgd", pid)
        return None
    status = str(p.get("status") or "").lower()
    if status in KLAAR:
        return Besluit(AFGEHANDELD, f"project {pid} is '{status}'", bewijs=pid, sleutel=f"p:{pid}")
    if status in LEVEND:
        # Wacht het project op een MENS, dan is het niet 'in uitvoering' — het zou hier stil vallen
        # en nooit meer bewegen. Doorlaten naar de routering, die het label opnieuw toetst.
        if "human" in _park_redenen(p):
            return None
        return Besluit(GEBORGD, f"project {pid} staat op '{status}' — wacht op uitvoering",
                       bewijs=pid, sleutel=f"p:{pid}")
    return None


# ── 2. Routering via de LLM-match van escalation_router ─────────────────────

_ROL_MARKERS = (
    re.compile(r"\[rol ([a-z0-9_]+) onbemand\]", re.I),
    re.compile(r"🙋\s*([a-z0-9_]+)\s*:", re.I),
)


def _genoemde_rol(tekst: str, records) -> str:
    """Een rol die de tensie letterlijk noemt is geen gok maar een gegeven — geen LLM-call nodig."""
    for pat in _ROL_MARKERS:
        m = pat.search(tekst or "")
        if m:
            kort = m.group(1)
            if records.get(kort) is not None:
                return kort
            for rec in records.all():
                if rec.id.split("__")[-1] == kort:
                    return rec.id
    return ""


def match(tekst: str, records, *, doel: str = "", van_rol: str = "",
          reason_fn=None) -> tuple[str, str, str]:
    """Wie bezit dit werk? → (rol_id, kind, waarom). Leeg rol_id = geen rol past.

    Hergebruikt `escalation_router`: dezelfde roster (purpose + accountabilities, cirkels eruit),
    dezelfde prompt die ownership boven tooling stelt, dezelfde fail-closed keuze. `kind` is
    'human_external' of 'missing_capability' — dat is wat de mens-check hierna nodig heeft.

    De match MOET 'geen rol past' kunnen zeggen: zonder die uitspraak bereikt niets deur 1 of 2 en
    is de uitweg naar een nieuwe rol of skill dood."""
    from nooch_village import escalation_router as er

    kandidaten = er.roster(records, exclude={van_rol} if van_rol else set())
    data = er._vraag_llm(tekst, doel or "(onbekend)", kandidaten, van_rol or "(onbekend)", reason_fn)
    if data is None:
        # LLM weg = geen handoff. Het dorp mag langzamer worden, niet stiller: dit item gaat door
        # naar de deuren en wordt daar zichtbaar, niet stilletjes weggefilterd.
        return "", "", "geen LLM-antwoord — fail-closed, geen handoff"
    kind = str(data.get("kind") or "")
    rol = er.kies_ontvanger(data, kandidaten, [], van_rol or "")
    if not rol:
        return "", kind, f"de match zegt expliciet geen eigenaar (kind={kind or '?'})"
    return rol, kind, f"purpose/accountability-eigenaarschap volgens de match (kind={kind or '?'})"


# ── 3. Mens-werk (alleen als geen rol past) ─────────────────────────────────

def _onderwerp(tekst: str) -> str:
    m = re.search(r"[\"'“‘]([^\"'”’]{4,60})", tekst or "")
    if m:
        return m.group(1).strip().lower()[:40]
    return " ".join((tekst or "").split()[:6]).lower()[:40]


# ── 4. De deuren, en de ops-grens ───────────────────────────────────────────

# Een BESTAANDE capaciteit die stuk is. Geen founder-besluit maar een storing.
_OPS_KLASSEN = (
    ("bron levert niet meer", re.compile(r"levert niet meer|capaciteit ontbreekt.*bron|"
                                         r"bron .* niet meer", re.I)),
    ("rol sloeg zijn puls over", re.compile(r"puls-uitval|geen hartslag", re.I)),
)

# Een capaciteit die NIET bestaat en gebouwd moet worden.
_SKILL_RE = re.compile(r"blijft blind|gaf HTTP|scan onvolledig|niet op te halen|"
                       r"geen skill|ontbrekende capaciteit", re.I)

_BESLUIT_DOMEIN = {
    # 'herformulering' hoort erbij: een publieke claim herschrijven IS compliance-werk, ook als het
    # woord 'claim' toevallig niet in de zin staat. Zonder dit viel zo'n item op ONBESLIST — wel
    # zichtbaar (niet stil), maar op de verkeerde stapel.
    "compliance": re.compile(r"claim|compliance|juridisch|EmpCo|ACM|greenwash|richtlijn|"
                             r"herformulering|reformulat", re.I),
    "merk":       re.compile(r"merk|brand|tone of voice|positionering", re.I),
    "strategie":  re.compile(r"strategie|strategy|koers|doelstelling", re.I),
    "geld":       re.compile(r"budget|kosten|prijs|betaal|investering|€", re.I),
    "governance": re.compile(r"governance|nieuwe rol|rol aanmaken|skill toekennen|mandaat", re.I),
}
_VRAAGT_BESLUIT = re.compile(r"beslissing gevraagd|goedkeuring|escalatie|approval|"
                             r"vereist .*(goedkeuring|akkoord)|herformulering", re.I)


def ops_klasse(tekst: str) -> str:
    for naam, pat in _OPS_KLASSEN:
        if pat.search(tekst or ""):
            return naam
    return ""


def _dag(ts) -> str:
    try:
        return datetime.datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


def volhardend(klasse: str, batch: list[dict], *, dagen: int = OPS_VOLHARDING_DAGEN) -> bool:
    """Kwam deze storing op minstens `dagen` verschillende dagen terug?

    Zo blijft één hik ops en wordt een dode bron een vraag. De telling komt uit de batch zelf: geen
    extra store die zijn eigen waarheid gaat bijhouden naast de notificaties."""
    return len({_dag(n.get("at")) for n in batch
                if ops_klasse(str(n.get("snippet") or "")) == klasse} - {""}) >= dagen


def deur(notif: dict, *, batch: list[dict] | None = None, kind: str = "",
         waarom: str = "") -> Besluit:
    tekst = str(notif.get("snippet") or "")
    batch = batch or [notif]

    klasse = ops_klasse(tekst)
    if klasse:
        if volhardend(klasse, batch):
            return Besluit(DEUR_BESLUIT,
                           f"storing '{klasse}' houdt aan (≥{OPS_VOLHARDING_DAGEN} dagen) — "
                           f"er ligt een investeringskeuze onder",
                           bewijs=tekst[:80], sleutel=f"besluit:ops:{klasse}", klasse=klasse)
        return Besluit(OPS, f"kapotte bestaande capaciteit ('{klasse}') — systeem-health, "
                            f"geen founder-besluit",
                       bewijs=tekst[:80], sleutel=f"ops:{klasse}", klasse=klasse)

    m = _SKILL_RE.search(tekst)
    if m:
        return Besluit(DEUR_SKILL, f"capaciteit bestaat niet ({m.group(0)!r})", bewijs=tekst[:80],
                       sleutel="skill:pagina niet op te halen", klasse="pagina niet op te halen")

    # De match heeft al geoordeeld dat software dit KAN maar geen rol de capaciteit heeft. Dat is
    # de skill-deur, letterlijk. Dat oordeel hier weggooien en terugvallen op tekstpatronen was een
    # gat: het signaal was er al en belandde als 'onbeslist' op de verkeerde stapel.
    if kind == "missing_capability" and not _VRAAGT_BESLUIT.search(tekst):
        return Besluit(DEUR_SKILL, f"geen rol bezit dit en software zou het kunnen ({waarom})",
                       bewijs=tekst[:80], sleutel=f"skill:{_onderwerp(tekst)}",
                       klasse="capaciteit ontbreekt")

    if _VRAAGT_BESLUIT.search(tekst):
        for naam, pat in _BESLUIT_DOMEIN.items():
            if pat.search(tekst):
                return Besluit(DEUR_BESLUIT, f"voorbehouden domein '{naam}' + expliciete vraag",
                               bewijs=tekst[:80], sleutel=f"besluit:{naam}", klasse=f"{naam}-besluit")
        return Besluit(ONBESLIST, "vraagt een besluit maar raakt geen voorbehouden domein",
                       bewijs=tekst[:80], sleutel=f"?:{_onderwerp(tekst)}")

    if waarom.startswith("geen LLM-antwoord"):
        # Andere oorzaak, andere fix: dit is geen onclassificeerbaar item maar een uitgevallen
        # match. Ze op één hoop gooien verbergt een storing achter 'onbekend'.
        return Besluit(ONBESLIST, "de eigenaars-match was niet beschikbaar — niet geclassificeerd",
                       bewijs=tekst[:80], sleutel=f"?:llm-uit:{_onderwerp(tekst)}")
    return Besluit(ONBESLIST, "geen regel pakte dit — expliciet onbeslist, niet stil weggefilterd",
                   bewijs=tekst[:80], sleutel=f"?:{_onderwerp(tekst)}")


# ── De poort ────────────────────────────────────────────────────────────────

def poort(notif: dict, *, projects, records, batch: list[dict] | None = None,
          reason_fn=None, gebruik_llm: bool = True) -> Besluit:
    """De volledige poort voor één tensie. Geeft altijd een Besluit — nooit None, nooit stil."""
    tekst = str(notif.get("snippet") or "")

    b = geborgd(notif, projects)
    if b is not None:
        return b

    # Routering. Een letterlijk genoemde rol is geen gok; anders de LLM-match.
    rol = _genoemde_rol(tekst, records)
    kind, waarom = "", "de tensie noemt de rol letterlijk"
    if not rol and gebruik_llm:
        try:
            rol, kind, waarom = match(tekst, records, reason_fn=reason_fn)
        except Exception as e:                        # noqa: BLE001 — fail-soft, luid
            log.warning("poort: routering faalde (%s) — item gaat door naar de deuren", e)
            rol, kind, waarom = "", "", f"routering faalde: {e}"
    if rol:
        return Besluit(GEROUTEERD, waarom, bewijs=rol, naar_rol=rol,
                       sleutel=f"rol:{rol}:{_onderwerp(tekst)}")

    # Mens-werk — pas NA de routering, en alleen op het oordeel van de match. Het park-label
    # `human` telt hier bewust niet mee: dat zat in 4 van de 11 gevallen fout.
    if kind == "human_external":
        return Besluit(MENS_WERK, f"geen rol bezit dit en het is fysiek/extern ({waarom})",
                       bewijs=tekst[:80], sleutel=f"mens:{_onderwerp(tekst)}")

    return deur(notif, batch=batch, kind=kind, waarom=waarom)


def rapport(besluiten: list[Besluit]) -> dict:
    """Wat de poort deed, geteld. Het verplichte tegenwicht tegen een stil filter: zonder deze
    telling weet niemand of er iets is weggevallen dat er hoorde te zijn."""
    per_deur: dict[str, int] = {}
    for b in besluiten:
        per_deur[b.deur] = per_deur.get(b.deur, 0) + 1
    zichtbaar = [b for b in besluiten if b.deur in DEUREN or b.deur == ONBESLIST]
    return {"in": len(besluiten), "per_deur": per_deur,
            "zichtbaar_voor_mens": len(zichtbaar),
            "na_dedup": len({b.sleutel for b in zichtbaar}),
            "weggefilterd": sum(per_deur.get(k, 0) for k in STIL),
            "mens_todo": per_deur.get(MENS_WERK, 0)}


def bundel(paren: list[tuple[dict, Besluit]]) -> list[dict]:
    """Groepeer wat de founder ziet op dedup-sleutel: één inbox-regel per klasse, met ALLE
    onderliggende meldingen erin.

    Klasse-dedup voor de regel, niet voor de beslissing. Bij compliance-claims is dat juridisch
    het hele punt: veertien claims onder één regel, maar elke claim houdt zijn eigen melding en
    zijn eigen oordeel. Een blanket-approve mag niet kunnen bestaan."""
    uit: dict[str, dict] = {}
    for n, b in paren:
        if b.deur not in DEUREN and b.deur != ONBESLIST:
            continue
        g = uit.setdefault(b.sleutel, {"deur": b.deur, "sleutel": b.sleutel, "klasse": b.klasse,
                                       "reden": b.reden, "meldingen": []})
        g["meldingen"].append({"id": n.get("id"), "tekst": str(n.get("snippet") or ""),
                               "project_id": n.get("project_id") or "", "at": n.get("at"),
                               "onderwerp": _onderwerp(str(n.get("snippet") or ""))})
    for g in uit.values():
        g["aantal"] = len(g["meldingen"])
    return sorted(uit.values(), key=lambda g: (-g["aantal"], g["sleutel"]))


# ── De pas: de poort echt uitvoeren ─────────────────────────────────────────

def _bestaand_project(projects, rol: str, tekst: str) -> str:
    """Heeft deze rol dit werk al op zijn bord? Dedup op de eerste 60 tekens van de scope.

    Zonder dit levert elke pas dezelfde tien projecten opnieuw af — precies de lus die we
    wegnemen, dan een laag dieper."""
    kern = " ".join((tekst or "").split())[:60].lower()
    try:
        lopend = [p for st in ("queued", "running", "blocked", "future")
                  for p in projects.by_status(st)]
    except Exception:                                  # noqa: BLE001 — geen by_status = geen dedup
        return ""
    for p in lopend:
        if p.get("owner") == rol and " ".join(str(p.get("scope") or "").split())[:60].lower() == kern:
            return str(p.get("id") or "")
    return ""


def draai(*, notif, projects, records, targets, reason_fn=None, dry_run: bool = True,
          gebruik_llm: bool = True) -> dict:
    """Draai de poort over de open founder-notificaties en handel af wat het dorp zelf bezit.

    Wat er gebeurt per uitkomst:

      geborgd / afgehandeld / ops  → verwerkt + gearchiveerd, met de reden als uitkomst (het spoor
                                     blijft, de wachtrij niet);
      gerouteerd                   → als PROJECT op het bord van die rol (een AI-rol leest zijn
                                     inbox nooit — #271), daarna verwerkt + gearchiveerd;
      mens_werk / deuren / onbeslist → blijft open, met het oordeel op het item zodat de weergave
                                     kan groeperen zonder de poort opnieuw te draaien.

    `dry_run=True` (default) muteert niets: meten mag nooit per ongeluk opruimen."""
    open_items = [n for n in notif.open_for_targets(targets)]
    uit = {"gezien": len(open_items), "per_deur": {}, "projecten": [], "gearchiveerd": 0,
           "blijft_open": 0, "dry_run": dry_run}
    paren = []
    for n in open_items:
        b = poort(n, projects=projects, records=records, batch=open_items,
                  reason_fn=reason_fn, gebruik_llm=gebruik_llm)
        paren.append((n, b))
        uit["per_deur"][b.deur] = uit["per_deur"].get(b.deur, 0) + 1
        log.info("poort [%s] %s | %s", b.deur, str(n.get("snippet"))[:60], b.reden)
        if dry_run:
            continue

        notif.set_poort(n.get("id"), {"deur": b.deur, "reden": b.reden, "bewijs": b.bewijs,
                                      "naar_rol": b.naar_rol, "sleutel": b.sleutel,
                                      "klasse": b.klasse})
        if b.deur == GEROUTEERD:
            tekst = str(n.get("snippet") or "")
            pid = _bestaand_project(projects, b.naar_rol, tekst)
            if not pid:
                try:
                    pid = projects.create(b.naar_rol, tekst, "tensie-poort")
                    uit["projecten"].append({"rol": b.naar_rol, "project": pid})
                except Exception as e:                 # noqa: BLE001 — nooit stil verliezen
                    log.warning("poort: kon werk niet afleveren bij %s (%s) — item blijft open",
                                b.naar_rol, e)
                    uit["blijft_open"] += 1
                    continue
            notif.mark_item_processed(n.get("id"), outcome=f"gerouteerd naar {b.naar_rol} "
                                                           f"(project {pid}) — {b.reden}",
                                      by="tensie-poort")
            notif.archive_item(n.get("id"))
            uit["gearchiveerd"] += 1
        elif b.deur in STIL:
            notif.mark_item_processed(n.get("id"), outcome=f"{b.deur}: {b.reden}", by="tensie-poort")
            notif.archive_item(n.get("id"))
            uit["gearchiveerd"] += 1
        else:
            uit["blijft_open"] += 1

    uit["rapport"] = rapport([b for _, b in paren])
    uit["bundels"] = bundel(paren)
    return uit
