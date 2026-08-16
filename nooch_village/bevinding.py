"""De bevinding: wat een rol tegenkwam en wat hij voorstelt, in gewone taal.

Dit vervangt de toelichting die een mens in een werkoverleg zou geven. Er is geen werkoverleg meer
tussen het ontstaan van een spanning en de rol die hem leest, dus moet de tekst het in één blik
doen. Wat er nu binnenkomt haalt dat niet: afgekapte zinnen ("…'Decide whether to permanently
exclude this overl"), interne verpakking ("Project van X vastgelopen op 1 mens-/extern item(s)"), en
jargon dat alleen binnen het dorp betekenis heeft.

Eén call per nieuwe spanning, en die mag duur zijn: hij draait één keer, op het moment van ontstaan,
en alles daarna leest mee. Beter één keer goed opschrijven dan tien keer half lezen.

Twee delen, allebei verplicht:

    spanning   wat er aan de hand is — volledig, zonder jargon, begrijpelijk voor een veertienjarige
    voorstel   wat de opwerpende rol wil doen of nodig heeft — concreet genoeg om ja op te zeggen

**Zonder voorstel is het geen bevinding maar een melding.** Een verzoek- of besluit-kaart zonder
concreet voorstel is niet verzendbaar: hij degradeert naar "moet herschreven" in plaats van als
lege kaart bij iemand te landen die dan zelf mag raden wat er gevraagd wordt.

De poorten hieronder zijn deterministisch. Een model dat zijn eigen tekst beoordeelt is een model
dat zijn eigen huiswerk nakijkt; de afkap-toets, de jargon-toets en de voorstel-toets zijn
vergelijkingen op de tekst.
"""
from __future__ import annotations

import json
import logging
import re

log = logging.getLogger("village.bevinding")

CALL_SITE = "bevinding_herschrijf"

# Woorden die alleen binnen het dorp of binnen software betekenis hebben. De lezerstest uit
# COPYCHECK-001 ("zou een veertienjarige dit hardop kunnen voorlezen en menen?") toegepast op onze
# eigen interne taal — want de founder is hier de lezer, en hij hoeft onze machinerie niet te kennen.
JARGON = (
    "payload", "checklist-item", "hop-limiet", "capability", "deliverable", "done-when",
    "done_when", "required_payload", "no_data", "fail-closed", "dry-run", "ledger", "store",
    "queued", "blocked", "notificatie", "escalatie", "poort", "dispatch", "record-id",
    "project_id", "skill-run", "match", "roster", "kern", "snippet",
)

# Een zin die middenin ophoudt. Geen leesteken aan het eind, of een aanhalingsteken dat nooit sluit.
_EIND = re.compile(r"[.!?…]\s*$")
_MIN_SPANNING = 40
_MIN_VOORSTEL = 15

_PROMPT = """Je herschrijft een interne signalering tot iets wat een mens in één blik begrijpt.

CONTEXT: dit is een zelfsturende organisatie. Een rol liep tegen iets aan en moet dat aan iemand
anders uitleggen. Er is geen vergadering waarin hij het even kan toelichten — jouw tekst is de hele
toelichting.

DE ROL DIE DIT OPWERPT: {rol}
ZIJN VERANTWOORDELIJKHEDEN: {accountabilities}
DE RUWE SIGNALERING: {tekst}

Schrijf twee dingen.

1. "spanning" — wat er aan de hand is, in HOOGSTENS VIER ZINNEN. Volledige zinnen, geen afgekapte
   gedachte, en liever korter dan langer: dit moet in één blik te lezen zijn. Schrijf zo dat
   een veertienjarige het hardop kan voorlezen en snapt: geen vakjargon, geen Engelse technische
   termen, geen interne systeemwoorden. Als de ruwe tekst een verwijzing bevat die je niet kunt
   uitleggen, laat hem dan weg in plaats van hem over te nemen. Noem geen bestandsnamen of id's.

2. "voorstel" — wat deze rol wil doen of nodig heeft, concreet genoeg dat iemand er ja op kan
   zeggen. Eén handeling, geen lijstje opties. Weet je het niet uit de tekst af te leiden, geef dan
   een lege string terug — verzin er geen.

Antwoord ALLEEN met JSON: {{"spanning": "...", "voorstel": "..."}}"""


def _accountabilities(records, rol: str) -> str:
    rec = records.get(rol) if records is not None else None
    accs = list(getattr(getattr(rec, "definition", None), "accountabilities", None) or [])
    return "; ".join(a[:90] for a in accs[:5]) or "(niet vastgelegd)"


def afgekapt(tekst: str) -> bool:
    """Houdt deze tekst middenin op? Een afgekapte zin is geen bevinding maar een fragment."""
    t = (tekst or "").strip()
    if not t:
        return True
    if not _EIND.search(t):
        return True
    # ALLEEN dubbele aanhalingstekens tellen. De enkele is in gewone tekst meestal een apostrof
    # ("Nooch's", "'t"), en die pariteit-check wees een correcte bevinding af omdat er één keer
    # een term werd aangehaald. Een valse afwijzing kost een leesbare kaart; dat weegt zwaarder
    # dan het zeldzame geval van een echt ongesloten enkel citaat.
    return t.count('"') % 2 == 1 or (t.count("“") != t.count("”"))


def jargon_in(tekst: str) -> list[str]:
    laag = (tekst or "").lower()
    return [w for w in JARGON if w in laag]


def keur(bevinding: dict, *, voorstel_verplicht: bool = True) -> tuple[bool, str]:
    """De kwaliteitspoort. Geeft (ok, reden). Deterministisch — een model dat zijn eigen tekst
    beoordeelt kijkt zijn eigen huiswerk na."""
    spanning = str((bevinding or {}).get("spanning") or "").strip()
    voorstel = str((bevinding or {}).get("voorstel") or "").strip()
    if len(spanning) < _MIN_SPANNING:
        return False, f"de spanning is te kort om iets uit te leggen ({len(spanning)} tekens)"
    if afgekapt(spanning):
        return False, "de spanning houdt middenin op — afgekapte zin of ongesloten aanhalingsteken"
    gevonden = jargon_in(spanning) or jargon_in(voorstel)
    if gevonden:
        return False, f"jargon dat de lezer niet hoeft te kennen: {', '.join(gevonden[:4])}"
    if voorstel_verplicht:
        if len(voorstel) < _MIN_VOORSTEL:
            return False, ("geen concreet voorstel — zonder 'wat wil je doen' is dit een melding, "
                           "geen verzoek")
        if afgekapt(voorstel):
            return False, "het voorstel houdt middenin op"
    return True, ""


def herschrijf(tekst: str, *, rol: str, records=None, reason_fn=None,
               ladder: str = "") -> dict:
    """Eén call per nieuwe spanning. Geeft {spanning, voorstel, ok, reden, ruw}.

    `ok=False` betekent: dit is niet verzendbaar en degradeert naar 'moet herschreven'. Nooit een
    halve kaart: liever zichtbaar onaf dan onzichtbaar onbegrijpelijk."""
    from nooch_village import tensie_poort as tp

    ruw = tp.kern(tekst)                      # eerst de verpakking eraf
    uit = {"spanning": "", "voorstel": "", "ok": False, "reden": "", "ruw": ruw}
    if not ruw:
        uit["reden"] = "lege signalering"
        return uit

    if reason_fn is None:
        from nooch_village.llm import reason as reason_fn         # noqa: PLC0415
    if not ladder:
        try:
            from nooch_village.llm_keuze import hoog_inzet_ladder
            ladder = hoog_inzet_ladder()
        except Exception:                                          # noqa: BLE001
            ladder = ""

    prompt = _PROMPT.format(rol=rol or "onbekend", tekst=ruw[:1200],
                            accountabilities=_accountabilities(records, rol))
    try:
        # 700 tokens kapte lange antwoorden af, en de afkap-poort weigerde ze dan terecht — maar
        # de oorzaak lag bij mij, niet bij het model. Ruimer, plus een lengte-instructie in de
        # prompt zodat het antwoord kort blijft in plaats van alleen te passen.
        rauw = reason_fn(prompt, json_mode=True, max_tokens=1400, call_site=CALL_SITE,
                         **({"ladder": ladder} if ladder else {}))
    except Exception as e:                                         # noqa: BLE001
        log.warning("bevinding: herschrijven faalde (%s) — ruwe tekst blijft staan", e)
        uit["reden"] = f"herschrijven faalde: {e}"
        return uit
    if not rauw:
        uit["reden"] = "geen antwoord van het model"
        return uit
    m = re.search(r"\{.*\}", str(rauw), re.DOTALL)
    try:
        data = json.loads(m.group(0)) if m else {}
    except ValueError:
        data = {}
    uit["spanning"] = str(data.get("spanning") or "").strip()
    uit["voorstel"] = str(data.get("voorstel") or "").strip()
    ok, reden = keur(uit)
    uit["ok"], uit["reden"] = ok, reden
    if not ok:
        log.info("bevinding geweigerd (%s) op: %s", reden, ruw[:70])
    return uit
