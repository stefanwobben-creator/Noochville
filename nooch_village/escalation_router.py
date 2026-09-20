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

# TWEE GESPREKKEN, TWEE BREINEN. Dezelfde prompt, maar niet dezelfde afweging.
#
# `ROUTE_SITE` is het eerste gesprek: bezit een ANDERE AI-ROL dit werk? Dat is triage — een grove
# keuze uit een bak, met een goedkope fout: verkeerd gerouteerd werk komt terug via de hop-teller,
# en de rol die het krijgt parkeert het gewoon opnieuw. Die hoort op de goedkope trede (GOEDKOOP),
# en daar staat hij.
#
# `MENS_SITE` is het tweede gesprek: welke MENS doet dit werk? Dat is geen bak kiezen maar een
# oordeel, en de fout is duur — het spoor zorgt dat een verkeerde ontvanger vandaag een betere
# morgen buitensluit (`vastgelopen_route.al_geland`).
#
# BEWEZEN, niet aangenomen (29 aug 2026, prod): drie identieke droge loops over dezelfde 17
# stappen gaven drie verschillende verdelingen — 5, dan 2, dan 4 van de 17 kregen een rol. Op negen
# stappen die vrijwel hetzelfde werk zijn (de live FAQ-pagina ophalen en er een zin uit halen)
# koos hetzelfde model vier keer wél een rol en vijf keer NONE. Er was geen quota-probleem: alle
# 17 kregen antwoord van mistral-small. Het model kán deze vraag daar niet reproduceerbaar
# beantwoorden, en een routering die per run anders uitvalt is een muntworp.
#
# Deze splitsing verandert vandaag niets aan de uitkomst: de premium-kop is onbetaald, dus de
# `met_dorpsstaart`-staart levert nog steeds mistral. Hij werkt zodra het krediet er is.
ROUTE_SITE = "escalation_route"
MENS_SITE = "escalation_mens"


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
               reason_fn, *, call_site: str = ROUTE_SITE, ladder: str | None = None) -> dict | None:
    """Eén call per vastgelopen item: wie bezit dit, en is het überhaupt software-werk?

    Beide vragen in één call, want het is dezelfde overweging en de router mag maar één keer per
    item vuren. Geeft None als er geen bruikbaar antwoord is (dan geldt fail-closed).

    `call_site` en `ladder` verschillen per GESPREK — zie de twee constanten hierboven. Dezelfde
    prompt, een andere afweging, dus een ander brein."""
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
        raw = reason_fn(prompt, json_mode=True, max_tokens=200, call_site=call_site,
                        ladder=ladder)
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


def match(tekst: str, records, *, doel: str = "", van_rol: str = "",
          reason_fn=None, call_site: str = ROUTE_SITE, ladder=None) -> tuple[str, str, str]:
    """Wie bezit dit werk? → (rol_id, kind, waarom). Leeg rol_id = geen rol past.

    Dezelfde drie stappen als `route_item` — roster, `_vraag_llm`, `kies_ontvanger` — maar zonder
    project, ledger of aflevering: alleen het oordeel. `kind` is 'human_external' of
    'missing_capability'; dat is wat de lezer daarna nodig heeft om te bepalen of hij het zelf doet.

    De match MOET 'geen rol past' kunnen zeggen: zonder die uitspraak kan niemand ooit vaststellen
    dat er een gat in de structuur zit, en zou elk item bij de eerste de beste rol landen.

    Stond tot 20 september 2026 in `tensie_poort`, waar hij de founder-inbox trieerde. Die poort is
    met de inbox verdwenen; dit oordeel niet — `zelf_verwerking.verwerk` is nu de lezer, en hij
    hoort thuis bij de roster en de prompt die hij hergebruikt."""
    kandidaten = roster(records, exclude={van_rol} if van_rol else set())
    data = _vraag_llm(tekst, doel or "(onbekend)", kandidaten, van_rol or "(onbekend)", reason_fn,
                      call_site=call_site, ladder=ladder)
    if data is None:
        # LLM weg = geen handoff. Het dorp mag langzamer worden, niet stiller: de lezer krijgt een
        # lege rol mét reden terug en deelt wat hij vond, in plaats van stil te vallen.
        return "", "", "geen LLM-antwoord — fail-closed, geen handoff"
    kind = str(data.get("kind") or "")
    rol = kies_ontvanger(data, kandidaten, [], van_rol or "")
    if not rol:
        return "", kind, f"de match zegt expliciet geen eigenaar (kind={kind or '?'})"
    return rol, kind, f"purpose/accountability-eigenaarschap volgens de match (kind={kind or '?'})"


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


def _mens_ontvanger(st, project: dict, item_text: str, from_role: str, trail: list[str],
                    reason_fn) -> tuple[str, str, str, str]:
    """(rol_id, persoon_id, grond, suggestie) — de bestemming is ALTIJD de founder.

    HIER KOOS EEN MODEL DE ONTVANGER, en dat is op 20 september 2026 vervallen (CLAUDE.md, "AI is
    instrument, geen rol"). De oude volgorde was: een mens-vervulde rol die het model aanwees, dan
    de opdrachtgever, dan de founder. Stap 1 was een organisatorisch besluit — werk op het bord van
    een collega — genomen door een model, uitgevoerd in dezelfde codepad, zonder dat iemand het
    vooraf zag. Met vijf mensen op veertien mens-bemande rollen was dat geen theoretisch risico.

    WAT ERVOOR IN DE PLAATS KOMT is geen andere keuze maar GEEN keuze: vastgelopen werk komt eerst
    bij de founder, altijd, en hij bepaalt waar het heen gaat. Dat is een besluit van Stefan zelf
    ("ik wil eerst alles zelf zien voordat het verder gaat") en bewust NIET de ladder
    vervuller → Circle Lead → founder die `signaal.ontvangers` hanteert: die verdeelt, en hier
    wordt niet verdeeld.

    HET MODEL MAG NOG STEEDS IETS VINDEN, maar alleen als TEKST. `match()` geeft een rol mét de
    grond waarop hij matcht; die zin reist mee in het bericht als voorstel. De lezer accepteert hem
    door in de DM `@rol` te antwoorden — dan is het toewijzen een menselijke handeling, met spoor.
    Valt het model weg of is het krediet op, dan gaat het bericht gewoon zonder voorstelregel: de
    ONTVANGER verandert daar niet meer door. Dat was de stille fout van de oude versie — geen
    antwoord betekende een andere bestemming."""
    from nooch_village import signaal

    scope = project.get("scope")
    doel = (" · ".join(f"{k}: {v}" for k, v in scope.items())
            if isinstance(scope, dict) else str(scope or ""))
    try:                                             # fail-soft: geen keuze-laag → dorpsladder
        from nooch_village.llm_keuze import llm_voorkeur
        ladder = llm_voorkeur(st, from_role, MENS_SITE)
    except Exception:                                # noqa: BLE001
        ladder = None
    suggestie = ""
    try:
        # DE LADDER EN HET MEETPUNT BLIJVEN STAAN, en dat is bewust geen vanzelfsprekendheid meer.
        # `MENS_SITE` staat in `llm_keuze.HOOG_INZET` omdat dit "een OORDEEL was waarvan de fout
        # blijft plakken": een verkeerde ontvanger vandaag sloot via het spoor een betere morgen
        # uit. Die grond is vervallen — het is nu een voorstel dat een mens leest en weggooit. Of
        # deze vraag nog een duur model verdient is daarmee een OPEN KOSTENVRAAG, en die verandert
        # niemand stilzwijgend hier; tot dat besluit meet hij door op dezelfde plek.
        rol, _kind, waarom = match(item_text, st.records, doel=doel, van_rol=from_role,
                                   reason_fn=reason_fn, call_site=MENS_SITE, ladder=ladder)
        if rol:
            rec = st.records.get(rol)
            naam = (getattr(getattr(rec, "definition", None), "name", "") or rol)
            suggestie = f"voorstel: dit lijkt van {naam} — {waarom}"
    except Exception as e:                               # noqa: BLE001 — een voorstel mag nooit blokkeren
        _LOG.warning("rolvoorstel niet gelukt (%s) — het bericht gaat zonder voorstel", e)

    founder = signaal.terugval(st)
    if founder:
        return "", founder, "alles wat vastloopt komt eerst bij jou", suggestie
    # Geen founder-persoon te vinden: dan de founder-ROL, zodat het niet alsnog verdampt.
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    return FOUNDER_ROLE_ID, "", "alles wat vastloopt komt eerst bij jou", suggestie


def naar_mens(*, data_dir: str, project: dict, item_text: str, from_role: str, from_naam: str,
              waarom: str, reason_fn=None) -> dict | None:
    """Leg één vastgelopen stap wélgevormd op het bureau van een mens. None = niet gelukt.

    Bij None hoort de aanroeper terug te vallen op zijn oude melding: liever een vage ping dan
    stilte. Dat is de hele fail-open-regel hier — dit pad mag nooit werk laten verdampen."""
    try:
        from nooch_village.cockpit2 import _Stores, route_werk      # lui: zware module, geen cyclus
        st = _Stores(data_dir)
        pid = project.get("id", "")
        rol, persoon, grond, suggestie = _mens_ontvanger(st, project, item_text, from_role,
                                                         trail_of(project), reason_fn)
        scope = project.get("scope")
        titel = (scope.get("titel") or scope.get("scope") or "" if isinstance(scope, dict)
                 else str(scope or ""))
        # WAT HIJ CONCREET NODIG HEEFT staat vooraan, want dat is wat de lezer moet doen.
        # WIE + WAAROP volgt als herkomst — de kaart toont die als tweede regel.
        tekst = f"{from_naam} heeft dit nodig: {item_text}".strip()
        herkomst = (f"↳ {from_naam} loopt vast in '{_kort(titel, 60)}' — {waarom} "
                    f"({grond})").strip()
        # HET VOORSTEL STAAT ACHTER DE HERKOMST, niet ervoor. Wat de lezer moet DOEN komt eerst,
        # waar het vandaan komt daarna, en wat een model ervan vindt als laatste — in die volgorde,
        # zodat een voorstel nooit leest als een gegeven.
        if suggestie:
            herkomst = f"{herkomst} · {suggestie}"
        soort, ref = route_werk(st, tekst=tekst, rol=rol, persoon=persoon, herkomst=herkomst,
                                door=from_role, opdrachtgever="", bron_project=pid)
        _LOG.info("🙋 laatste meter: '%s' → %s (%s)", item_text[:60], ref, grond)
        return {"soort": soort, "ref": ref, "rol": rol, "persoon": persoon, "grond": grond,
                "suggestie": suggestie}
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

