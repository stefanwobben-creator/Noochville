"""De escalatie-router: rollen laten samenwerken in plaats van alles naar de mens te sturen.

Tot nu toe eindigde elk "ik kan niet verder" bij de founder (`_notify_founder`). Dat maakt de mens de
bottleneck voor werk dat een ándere rol gewoon bezit. Elk vastloop-pad gaat nu eerst hierlangs, met
deze beslisvolgorde:

  1. **Bezit een andere rol dit?** Match op ACCOUNTABILITY/PURPOSE, niet op skill. Een rol die het
     werk bezit maar de skill nog niet heeft, is de juiste ontvanger — daar hoort het gat te landen,
     niet bij de rol die toevallig als eerste tegen het probleem aanliep. Handoff naar een skill-loze
     rol is dus expliciet toegestaan: het item mag daar doodlopen, dat is het punt.
  2. **Niemand bezit het en het is fysiek/menselijk?** → mens-taak bij de founder.
  3. **Het is van deze rol maar hij mist de capaciteit?** → parkeren (de bestaande klep) plus een
     capaciteit-gat-record op déze rol.

Fail-closed op de match: geen zekere eigenaar → stap 2/3. Nooit een gok-handoff, want een item op het
verkeerde bureau kost een hop en levert een vals gat-record op.

Fail-soft op de LLM: geen antwoord → geen handoff, gewoon parkeren met een gat-record. Het dorp mag
langzamer worden als de LLM wegvalt, niet stiller.

**Eén keer per item.** De router vuurt op het moment van de park-beslissing en zet `routed` op het
item. Zonder die markering zou elke reactivering dezelfde LLM-call opnieuw doen op hetzelfde
vastgelopen item.

**Twee harde guards** (elk met een test):
  - *Hop-teller*: het project draagt een `handoff_trail`. Max `escalation_max_hops` hops (default 2),
    en nooit terug naar een rol die het al zag. Bij de limiet → de mens. Zo kan A→B→A niet ontstaan.
  - *Zichtbaar doodlopen*: loopt een doorverwezen item dood bij rol B, dan parkeert dat project bij B
    via dezelfde klep, mét gat-record. Nooit stil sterven.

Geen goedkeuringsstap op het routeren zelf: de slechtst mogelijke uitkomst is een zichtbaar
geparkeerd item op het verkeerde bureau — intern, omkeerbaar en begrensd door de hop-teller. De enige
poort zit op het pad van gat naar code-wijziging (Codie-backlog → mens → implementatie).
"""
from __future__ import annotations

import json
import logging
import re

from nooch_village import gap_ledger
from nooch_village.project_items import handoff

_LOG = logging.getLogger("village.router")

DEFAULT_MAX_HOPS = 2


def max_hops(settings) -> int:
    try:
        return max(0, int((settings or {}).get("escalation_max_hops", DEFAULT_MAX_HOPS)))
    except (TypeError, ValueError):
        return DEFAULT_MAX_HOPS


def trail_of(project: dict) -> list[str]:
    """Het handoff-spoor van dit project: de rollen die dit werk al zagen, oudste eerst."""
    return [r for r in (project or {}).get("handoff_trail") or [] if r]


def roster(records, *, exclude: set[str]) -> list[dict]:
    """De rollen die werk kunnen bezitten, met hun purpose en accountabilities.

    Dezelfde bron die de planner voor `projectverzoek` samenstelt (Inhabitant._plan_checklist), maar
    hier gebruikt om te bepalen WIENS accountability dit is — niet wie er toevallig een skill voor
    heeft. Cirkels vallen af: die hebben geen handen (harde regel 7)."""
    from nooch_village import org
    uit = []
    for r in (records.all() if records is not None else []):
        # Een slapende rol staat niet op de roster: werk erheen routeren zou het laten
        # verdwijnen bij iemand die niet draait. Gearchiveerd = weg, slapend = gepauzeerd; voor
        # de routering is de uitkomst dezelfde, en dat is de bedoeling.
        if (getattr(r, "archived", False) or getattr(r, "slaapt", False)
                or org.is_circle(r) or r.id in exclude):
            continue
        d = getattr(r, "definition", None)
        uit.append({"id": r.id,
                    "purpose": (getattr(d, "purpose", "") or "")[:160],
                    "accountabilities": list(getattr(d, "accountabilities", []) or [])[:4]})
    return uit


def _vraag_llm(item_text: str, project_goal: str, kandidaten: list[dict], from_role: str,
               reason_fn) -> dict | None:
    """Eén call per vastgelopen item: wie bezit dit, en is het überhaupt software-werk?

    Beide vragen in één call, want het is dezelfde overweging en de router mag maar één keer per
    item vuren. Geeft None als er geen bruikbaar antwoord is (dan geldt fail-closed)."""
    if reason_fn is None:
        from nooch_village.llm import reason as reason_fn          # noqa: PLC0415
    lijst = "\n".join(
        f"- {k['id']}: purpose={k['purpose'] or '(none)'} | accountabilities="
        f"{', '.join(k['accountabilities']) or '(none)'}" for k in kandidaten)
    prompt = (
        "You route stuck work in a self-managing organisation (Holacracy). A role got stuck on a "
        "sub-task it cannot carry out.\n\n"
        f"STUCK TASK: {item_text}\n"
        f"PROJECT GOAL: {project_goal}\n"
        f"CURRENT ROLE (cannot do it): {from_role}\n\n"
        "OTHER ROLES (id, purpose, accountabilities):\n" + (lijst or "(none)") + "\n\n"
        "Answer two questions.\n"
        "1. role — Which role's ACCOUNTABILITY or PURPOSE covers this task? Judge ownership, NOT "
        "tooling: a role that owns this work but lacks the tool is still the right owner. Only name "
        "a role if the ownership is CLEAR; if no role clearly owns it, answer \"NONE\". Never guess.\n"
        "2. kind — \"human_external\" if no software could ever do this because it needs a person or "
        "an outside party in the physical world (visiting, filming, phoning, signing, shipping); "
        "\"missing_capability\" if software could do it but no role has the tool yet.\n"
        "3. capability — a SHORT reusable label for the tool that is missing (e.g. \"patent search "
        "API\", \"invoice OCR\"), max 6 words. Empty string if kind is human_external.\n\n"
        "Answer ONLY with JSON: {\"role\": \"<role id or NONE>\", "
        "\"kind\": \"missing_capability|human_external\", \"capability\": \"...\"}")
    try:
        raw = reason_fn(prompt, json_mode=True, max_tokens=200, call_site="escalation_route")
    except Exception as e:                       # noqa: BLE001 — LLM weg = geen handoff, geen crash
        _LOG.warning("router: LLM-call faalde (%s) — geen handoff, wel parkeren", e)
        return None
    if not raw:
        return None
    m = re.search(r"\{.*\}", str(raw), re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def kies_ontvanger(data: dict | None, kandidaten: list[dict], trail: list[str],
                   from_role: str) -> str | None:
    """De gekozen rol-id, of None. Fail-closed op elke twijfel.

    Weigert: geen antwoord, 'NONE', een onbekende id (LLM verzon een rol), zichzelf, en elke rol die
    dit werk al zag — dat laatste is de guard die A→B→A onmogelijk maakt."""
    if not data:
        return None
    kandidaat = str(data.get("role") or "").strip()
    if not kandidaat or kandidaat.upper() == "NONE":
        return None
    geldig = {k["id"] for k in kandidaten}
    if kandidaat not in geldig:
        _LOG.info("router: LLM noemde onbekende/uitgesloten rol %r — fail-closed, geen handoff",
                  kandidaat)
        return None
    if kandidaat == from_role or kandidaat in trail:
        _LOG.info("router: %r zag dit werk al (spoor %s) — geen terugverwijzing", kandidaat, trail)
        return None
    return kandidaat


def route_item(*, ledger, records, data_dir, project, clid, item, from_role, from_naam="",
               settings=None, reason_fn=None, notify=None) -> dict:
    """Routeer ÉÉN vastgelopen item. Geeft {actie, naar_rol, reason, capability, gap, trail}.

    actie ∈ handoff | human | park:
      handoff — doorgegeven aan een andere rol (item hier overgeslagen, telt niet meer mee);
      human   — niemand bezit het, of de hop-limiet is bereikt → zichtbaar bij de mens;
      park    — van deze rol, maar de capaciteit ontbreekt → blijft hier staan (de klep parkeert).
    In alle drie de gevallen ontstaat er een gat-record zodra er capaciteit ontbreekt."""
    pid = project["id"]
    item_id = item.get("id", "")
    item_text = (item.get("text") or "").strip()
    trail = trail_of(project)
    hops = max_hops(settings)
    scope = project.get("scope")
    doel = (" · ".join(f"{k}: {v}" for k, v in scope.items())
            if isinstance(scope, dict) else str(scope or ""))

    # Guard 1 — hop-teller. Op de limiet routeren we niet meer: dan gaat het naar de mens, ook al zou
    # er nog een kandidaat zijn. Werk dat twee bureaus verder nog niet landt, is een mens-beslissing.
    limiet_bereikt = len(trail) >= hops
    kandidaten = roster(records, exclude={from_role, *trail})
    data = None if (limiet_bereikt or not kandidaten) else _vraag_llm(
        item_text, doel, kandidaten, from_role, reason_fn)
    naar = kies_ontvanger(data, kandidaten, trail, from_role)

    kind = str((data or {}).get("kind") or item.get("kind") or "").strip().lower()
    if kind not in (gap_ledger.MISSING_CAPABILITY, gap_ledger.HUMAN_EXTERNAL):
        kind = gap_ledger.MISSING_CAPABILITY     # onbekend → bouwbaar-tenzij-bewezen-anders
    capability = str((data or {}).get("capability") or "").strip()

    # Markeer vóór elke uitkomst: de router vuurt één keer per item, ook als er hierna iets misgaat.
    _markeer_routed(ledger, pid, clid, item_id)

    if naar:
        nieuw_spoor = [*trail, from_role]
        res = handoff(ledger, naar, item_text, done_criterium=item.get("reason") or "",
                      records=records, van_pid=pid)
        if res.get("ok"):
            _zet_trail(ledger, res["pid"], nieuw_spoor)
            ledger.set_item_skipped(pid, clid, item_id, True,
                                    f"overgedragen aan {naar} (project {res['pid']}) — "
                                    f"accountability ligt daar")
            ledger.link(pid, res["pid"])
            ledger.add_feed_entry(
                pid, f"📤 Doorgegeven aan {naar}: {item_text[:120]}. Die rol bezit deze "
                     f"accountability; ik niet. Spoor: {' → '.join(nieuw_spoor)}.",
                kind="system", author_type="role", author_id=from_role)
            _LOG.info("📤 router: '%s' → %s (spoor %s)", item_text[:60], naar, nieuw_spoor)
            return {"actie": "handoff", "naar_rol": naar, "reason": kind, "capability": capability,
                    "gap": None, "trail": nieuw_spoor, "pid": res["pid"]}
        _LOG.warning("router: handoff naar %s mislukte (%s) — valt terug op parkeren",
                     naar, res.get("error"))

    # Geen ontvanger: dit is een gat. Vastleggen wat er ontbreekt, op de rol die het opliep.
    gap = gap_ledger.record(data_dir, role=from_role, item_text=item_text, project_id=pid,
                            reason=kind, capability=capability, hop_trail=trail, item_id=item_id)
    mens = kind == gap_ledger.HUMAN_EXTERNAL or limiet_bereikt
    geland = None
    if mens:
        waarom = ("de hop-limiet is bereikt — twee rollen konden dit niet oppakken"
                  if limiet_bereikt else "geen enkele rol bezit dit; het vraagt een mens of "
                                         "externe partij")
        geland = naar_mens(data_dir=data_dir, project=project, item_text=item_text,
                           from_role=from_role, from_naam=from_naam or from_role, waarom=waarom,
                           reason_fn=reason_fn)
        if geland is None and notify is not None:
            notify(pid, f"🙋 {from_role}: '{item_text[:90]}' — {waarom}.")
    return {"actie": "human" if mens else "park", "naar_rol": None, "reason": kind,
            "capability": capability, "gap": gap, "trail": trail, "geland": geland}


# ── De laatste meter: van "wacht op een mens" naar werk op een bureau ────────────────────────────
#
# GEMETEN OP PROD, 29 aug 2026. De Scientist had 33 geblokkeerde projecten, ALLE 33 met dezelfde
# park-reden: "vastgelopen op 1 item(s) — wacht op een mens of externe partij". Samen 21 openstaande
# stappen over 33 projecten — gemiddeld minder dan één per project. De oudste stonden 51 dagen stil.
# Vijftien logden zelfs "✅ Checklist voltooid — klaar voor review" en stonden alsnog geblokkeerd.
#
# De rol dééd zijn werk: 65 van de 88 einddocumenten wijken af van de seed. Wat ontbrak was de
# laatste meter — één stap die hij niet kon doen, en geen route die die stap bij een mens legde.
# Wat er wél gebeurde was een ping naar de founder met "vastgelopen op N mens-/extern item(s)": een
# melding over een toestand, niet een vraag aan iemand die hem kan beantwoorden.
#
# Drie dingen zijn hier anders:
#   1. het landt via `route_werk` in een ÉCHTE inbox — bestaande mechaniek, geen vierde kanaal;
#   2. de ontvanger wordt GEGROND gekozen (mens-vervulde rol die het bezit → opdrachtgever →
#      founder), niet standaard de founder;
#   3. de tekst is wélgevormd: wie vastzit, waar hij op vastzit, en wat hij concreet nodig heeft.

def _kort(tekst: str, n: int) -> str:
    """Afkappen op een WOORDGRENS. `[:60]` maakte van 'that caused the failure' → 'that cau', en een
    half woord in een herkomst-regel leest als een defect in plaats van als een titel."""
    tekst = " ".join(str(tekst or "").split())
    if len(tekst) <= n:
        return tekst
    kort = tekst[:n].rsplit(" ", 1)[0]
    return (kort or tekst[:n]) + "…"


def mens_kandidaten(records, assign, *, exclude: set) -> list[dict]:
    """De roster, maar alleen de rollen waar een MENS op zit.

    Waarom een aparte verzameling en niet de gewone roster: dit is de vraag ná "geen enkele AI-rol
    bezit dit". Een tweede AI-rol voorstellen zou het werk opnieuw laten stranden, en precies dat
    heeft de hop-teller al een keer geprobeerd. Hier telt alleen wie het écht kan oppakken."""
    from nooch_village.assignments import door_mens_bemand
    uit = []
    for k in roster(records, exclude=exclude):
        try:
            if door_mens_bemand(k["id"], assign, records):
                uit.append(k)
        except Exception:                            # noqa: BLE001 — onbekend = geen kandidaat
            continue
    return uit


def _mens_ontvanger(st, project: dict, item_text: str, from_role: str, trail: list[str],
                    reason_fn) -> tuple[str, str, str]:
    """(rol_id, persoon_id, grond) — wie krijgt dit, en waaróm die.

    De volgorde is van meest naar minst gegrond:
      1. een MENS-VERVULDE ROL wiens accountability of purpose deze stap dekt. Fail-closed via
         `kies_ontvanger`: bij twijfel, een verzonnen rol of een rol die dit werk al zag → geen keuze.
      2. de OPDRACHTGEVER van het project — wie erom vroeg, hoort te horen dat het klem zit. Een
         zwakkere grond dan 1 (hij vroeg het, hij kan het niet per se) maar wel een echt feit.
      3. de FOUNDER — het bestaande vangnet, en de eerlijke uitkomst als niets anders gegrond is.

    Fail-OPEN op het model: geen antwoord betekent stap 2 of 3, nooit 'dan maar niet'. Werk dat
    nergens landt is precies wat we hier weghalen."""
    kandidaten = mens_kandidaten(st.records, st.assign, exclude={from_role, *trail})
    if kandidaten:
        scope = project.get("scope")
        doel = (" · ".join(f"{k}: {v}" for k, v in scope.items())
                if isinstance(scope, dict) else str(scope or ""))
        keuze = kies_ontvanger(_vraag_llm(item_text, doel, kandidaten, from_role, reason_fn),
                               kandidaten, trail, from_role)
        if keuze:
            return keuze, "", "deze rol bezit dit werk"
    opdrachtgever = str(project.get("opdrachtgever") or "").strip()
    if opdrachtgever and st.people.get(opdrachtgever) is not None:
        return "", opdrachtgever, "jij vroeg om dit project"
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    return FOUNDER_ROLE_ID, "", "geen rol bezit dit, en het project heeft geen opdrachtgever"


def naar_mens(*, data_dir: str, project: dict, item_text: str, from_role: str, from_naam: str,
              waarom: str, reason_fn=None) -> dict | None:
    """Leg één vastgelopen stap wélgevormd op het bureau van een mens. None = niet gelukt.

    Bij None hoort de aanroeper terug te vallen op zijn oude melding: liever een vage ping dan
    stilte. Dat is de hele fail-open-regel hier — dit pad mag nooit werk laten verdampen."""
    try:
        from nooch_village.cockpit2 import _Stores, route_werk      # lui: zware module, geen cyclus
        st = _Stores(data_dir)
        pid = project.get("id", "")
        rol, persoon, grond = _mens_ontvanger(st, project, item_text, from_role,
                                              trail_of(project), reason_fn)
        scope = project.get("scope")
        titel = (scope.get("titel") or scope.get("scope") or "" if isinstance(scope, dict)
                 else str(scope or ""))
        # WAT HIJ CONCREET NODIG HEEFT staat vooraan, want dat is wat de lezer moet doen.
        # WIE + WAAROP volgt als herkomst — de kaart toont die als tweede regel.
        tekst = f"{from_naam} heeft dit nodig: {item_text}".strip()
        herkomst = (f"↳ {from_naam} loopt vast in '{_kort(titel, 60)}' — {waarom} "
                    f"({grond})").strip()
        soort, ref = route_werk(st, tekst=tekst, rol=rol, persoon=persoon, herkomst=herkomst,
                                door=from_role, opdrachtgever="", bron_project=pid)
        _LOG.info("🙋 laatste meter: '%s' → %s (%s)", item_text[:60], ref, grond)
        return {"soort": soort, "ref": ref, "rol": rol, "persoon": persoon, "grond": grond}
    except Exception as e:                           # noqa: BLE001 — nooit de puls breken
        _LOG.warning("laatste meter mislukt (%s) — terugval op de oude melding", e)
        return None


def _markeer_routed(ledger, pid: str, clid: str, item_id: str) -> None:
    """Zet `routed` op het item — de garantie dat de router één keer per item vuurt."""
    try:
        ledger.mark_item_routed(pid, clid, item_id)
    except Exception:                            # noqa: BLE001 — markeren mag nooit fataal zijn
        pass


def _zet_trail(ledger, pid: str, trail: list[str]) -> None:
    """Hang het spoor aan het ONTVANGENDE project: zo reist de hop-teller mee naar de volgende rol,
    ook al krijgt die een vers uitvoerplan met nieuwe item-id's."""
    try:
        ledger.set_handoff_trail(pid, trail)
    except Exception:                            # noqa: BLE001
        pass


def escaleer(*, ledger, records, data_dir, project, clid, items, from_role, from_naam="",
             settings=None, reason_fn=None, notify=None) -> dict:
    """Routeer alle vastgelopen items van één park-beslissing.

    Geeft {handoffs, gaps, resterend, mens}: `resterend` zijn de items die hier blijven staan — die
    parkeren via de bestaande klep, zodat een doodgelopen doorverwijzing zichtbaar stilvalt bij de
    rol waar hij eindigde in plaats van stil te sterven."""
    uit = {"handoffs": [], "gaps": [], "resterend": [], "mens": 0, "geland": []}
    for item in items:
        if item.get("routed"):                   # al eerder gerouteerd → niet nog een LLM-call
            uit["resterend"].append(item)
            continue
        try:
            res = route_item(ledger=ledger, records=records, data_dir=data_dir, project=project,
                             clid=clid, item=item, from_role=from_role, from_naam=from_naam,
                             settings=settings, reason_fn=reason_fn, notify=notify)
        except Exception as e:                   # noqa: BLE001 — routeren mag de puls nooit breken
            _LOG.warning("router: item %s overgeslagen (%s)", item.get("id"), e)
            uit["resterend"].append(item)
            continue
        if res["actie"] == "handoff":
            uit["handoffs"].append(res)
        else:
            uit["resterend"].append(item)
            if res.get("gap"):
                uit["gaps"].append(res["gap"])
            if res["actie"] == "human":
                uit["mens"] += 1
                if res.get("geland"):
                    uit["geland"].append(res["geland"])
    return uit
