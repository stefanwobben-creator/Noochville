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

_PROMPT = """Je maakt een interne signalering leesbaar voor de mens die hem straks opent.

CONTEXT: dit is een zelfsturende organisatie. Een rol liep tegen iets aan en moet dat aan iemand
anders uitleggen. Er is geen vergadering waarin hij het even kan toelichten — jouw tekst is de hele
toelichting.

DE ROL DIE DIT OPWERPT: {rol}
ZIJN VERANTWOORDELIJKHEDEN: {accountabilities}
DE RUWE SIGNALERING: {tekst}

FEITBEHOUD GAAT VÓÓR LEESBAARHEID. Een leesbaar-maar-fout bericht is erger dan een lelijk-maar-juist
bericht. Behoud niet alleen de feiten maar ook hoe ZEKER ze zijn:

  1. De slag om de arm blijft staan. Staat er "mogelijk", schrijf dan niet "waarschijnlijk".
  2. Alternatieven blijven heel. Staat er "A of B", kies er dan niet één; noem ze allebei, of
     gebruik één woord dat ze allebei dekt.
  3. Er komt geen detail bij. Geen oorzaak, geen naam, geen getal en geen tijdstip dat de ruwe
     tekst niet had. Weet je iets niet, laat het weg — vul het niet in.
  4. Is de ruwe tekst (deels) Engels, vertaal dan letterlijk wat er staat. Vertalen is precies waar
     er iets bij verzonnen wordt: geen gladdere formulering, geen ingevulde bedoeling.
  5. Een GECITEERDE tekst blijft staan zoals hij is, ook als hij Engels is. Staat er een claim of
     zin tussen aanhalingstekens, dan is dat bewijsmateriaal: iemand heeft precies díe woorden
     ergens gezien. Vertaal je hem, dan klopt het citaat niet meer met de bron. Vertaal eromheen.

Kun je iets niet begrijpelijk maken zonder één van die vier te schenden, laat het dan staan zoals het
was. Onbegrijpelijk-maar-waar is te repareren; vloeiend-maar-onwaar niet.

Schrijf twee dingen.

1. "spanning" — in HOOGSTENS VIER ZINNEN, in deze volgorde:
     • wat er gebeurde;
     • waarom dat telt voor de lezer;
     • wat er nodig is.
   Volledige zinnen, geen afgekapte gedachte, liever korter dan langer: dit moet in één blik te
   lezen zijn. Noem geen bestandsnamen, geen id's en geen commando's.

2. "voorstel" — wat deze rol wil doen of nodig heeft, als een MENSELIJKE VRAAG en niet als een
   opdracht aan een computer. Niet "Beoordeel via het inbox-commando" maar "Kun je kijken wat er aan
   de hand is?". Eén handeling, geen lijstje opties. En stel geen vraag die een oorzaak al
   veronderstelt als de ruwe tekst die oorzaak niet noemt. Weet je het niet uit de tekst af te
   leiden, geef dan een lege string terug — verzin er geen.

DE VIJF LEZERSTESTS. Je tekst doorstaat ze alle vijf; ze staan in de policy van dit dorp:

{lezerstests}

Antwoord ALLEEN met JSON: {{"spanning": "...", "voorstel": "..."}}"""


# ── feitbehoud, deterministisch ─────────────────────────────────────────────
#
# Twee van de vier eisen zijn te MÉTEN in plaats van te vragen, en gemeten is sterker: een model dat
# zijn eigen tekst beoordeelt kijkt zijn eigen huiswerk na. De andere twee (alternatieven heel,
# letterlijk vertalen) zijn oordeel en blijven in de prompt.

# Woorden die een slag om de arm houden, en woorden die zekerder zijn. De tweede groep mag alleen
# voorkomen als de bron zelf al zo stellig was.
# Ook deze op woordgrens, en om dezelfde reden als hierboven: "onmogelijk" bevat "mogelijk" en zou
# als slag om de arm tellen terwijl het het tegendeel zegt. Dat de fout hier de ANDERE kant op valt
# (te veel hedge zien → minder afkeuren) maakt hem niet minder fout, alleen stiller.
_SLAG_OM_DE_ARM = tuple(re.compile(r"\b" + w + r"\b") for w in
                        ("mogelijk", "misschien", "wellicht", "vermoedelijk", "lijkt", "zou kunnen",
                         "mogelijkerwijs", "onduidelijk", "onzeker", "maybe", "possibly", "perhaps"))
# OP WOORDGRENS, en dat is geen detail. De eerste versie zocht op losse tekst, en verwierp toen een
# perfecte herschrijving omdat er "ONduidelijk" in stond — het woord dat de slag om de arm juist
# vasthoudt, gelezen als het tegendeel. De poort die feitbehoud bewaakt kan zelf een feit verdraaien.
# Gevonden door de meting, niet door de test die ik erbij schreef.
#
# "dus" en het kale "zeker" staan er bewust niet bij. "dus" is een gevolgtrekking, geen
# zekerheidsclaim. En "zeker" is in het Nederlands te veelzijdig: "we moeten zeker weten of alles
# werkt" is een WENS om te controleren, precies het tegenovergestelde van een stellige bewering — en
# de meting verwierp daarop een correcte herschrijving. Tweede valse afwijzing van dezelfde soort.
_STELLIGER = tuple(re.compile(r"\b" + w + r"\b") for w in
                   ("waarschijnlijk", "duidelijk", "ongetwijfeld", "uiteraard",
                    "blijkbaar", "kennelijk", "vast en zeker"))
# ELK getal, ook een losse cijfer. "De dagpuls draaide 3 dagen niet" is precies de vorm waarin een
# model een specifiek detail bijverzint dat de bron niet had, en die glipte door een grens van twee
# cijfers heen. Vals afkeuren kost een lelijke maar ware tekst; dat is de goedkope kant.
_GETAL = re.compile(r"\d+")


# ── de grond-check ──────────────────────────────────────────────────────────
#
# GEGENERALISEERD UIT DE GETAL-CHECK, en de aanleiding stond op prod. Een compliance-bericht zei
# letterlijk "(vermoeden, geen wet)"; de herschrijving maakte daar "de EU-richtlijn 2024/825 (EmpCo)"
# van. De richtlijn bestáát — het model had gelijk — en juist dat maakt het gevaarlijk: alles klopt,
# alleen stond het niet in de bron. Correct-maar-ongegrond zie je bij nalezen niet.
#
# De getal-check ving hem, maar bij toeval: had het model "de EU-richtlijn EmpCo" geschreven zonder
# cijfers, dan was hij erdoor. Een poort die zijn vangst aan cijfers dankt, dekt niet wat hij lijkt
# te dekken.
#
# WAT TELT ALS SPECIFIEK: gegevens die naar iets buiten de tekst wijzen en die je kunt opzoeken.
# Acroniemen (EU, ISO, EmpCo), formele identifiers (2024/825, EN-1234), getallen. NIET elk woord met
# een hoofdletter: een naam als "Harry Hemp" of een zin die met een hoofdletter begint is geen
# opzoekbaar gegeven, en die zou een legitieme herformulering laten sneuvelen.
#
# STRENG MAG. Een valse afwijzing kost een lelijke maar ware tekst; een gemiste smokkel kost een
# feit. Fail-open naar het origineel maakt de goedkope kant ook echt goedkoop.
_SPECIFIEK = (
    re.compile(r"\b[A-Z]{2,}\b"),                    # acroniem: EU, ISO, MOQ, GSC
    re.compile(r"\b[A-Z][a-z]+[A-Z][A-Za-z]*\b"),    # binnenkapitaal: EmpCo, GreenClaims
    re.compile(r"\b[A-Za-z]{2,}[-/]?\d+(?:/\d+)?\b"),  # identifier: ISO14001, EN-1234
    # De NAAM die aan zo'n acroniem vastzit: "EU Green Deal", "ISO Standard". Gevonden in de meting:
    # de bron zei "EU Green", de herschrijving maakte er "EU Green Deal-regelgeving" van. "Deal" is
    # een gewoon woord met een hoofdletter en viel dus buiten de andere patronen — maar vastgeplakt
    # aan een acroniem is het wél een opzoekbare aanduiding. Zo blijft de regel "geen enkel
    # hoofdletterwoord" overeind: alleen wat aan een formele bron vastzit telt mee.
    re.compile(r"\b[A-Z]{2,}(?:[ -][A-Z][a-z]+){1,3}\b"),
)


def _plat(x: str) -> str:
    """Koppeltekens en schuine strepen als spatie: "EU-richtlijn" en "EU richtlijn" zijn hetzelfde
    gegeven, en een poort die daarover struikelt keurt taal af in plaats van inhoud."""
    return re.sub(r"\s+", " ", re.sub(r"[-/]", " ", x or "")).strip()


def _ongegronde_specifieken(bron: str, tekst: str) -> list[str]:
    """Specifieke gegevens in de herschrijving die niet in de bron staan.

    Op WOORDGRENS en hoofdletter-ongevoelig: "EU" mag uit "EU-richtlijn" komen, maar niet uit
    "Europa". Zelfde regel als bij de jargon- en zekerheidspoort, en om dezelfde reden."""
    uit, gezien = [], set()
    for r in _SPECIFIEK:
        for tok in r.findall(tekst or ""):
            k = tok.casefold()
            if k in gezien:
                continue
            gezien.add(k)
            if not re.search(r"\b" + re.escape(_plat(tok)) + r"\b", _plat(bron), re.I):
                uit.append(tok)
    return uit


def feitbehoud(bron: str, tekst: str) -> tuple[bool, str]:
    """Is de herschrijving niet ZEKERDER of SPECIFIEKER dan de bron? Geeft (ok, reden).

    DRIE ONAFHANKELIJKE DEELCHECKS, en dat is met opzet: de smokkel van vandaag hield zich keurig aan
    de zekerheidsregel ("mogelijk" bleef staan) en glipte langs een andere as. Eén goede check is
    zwakker dan drie die elkaar niet overlappen.

      slag om de arm   `mogelijk` wordt geen `waarschijnlijk`      (hieronder)
      grond            geen specifiek gegeven dat de bron niet had (`_ongegronde_specifieken`)
      alternatieven    `A of B` wordt niet stil één ervan          (in de prompt — oordeel)

    De aanleiding staat in het ijkpunt van de spec. De ruwe tekst zei "mogelijk niet-uitvoering
    (hook of service)"; de eerste leesbare versie maakte daar "waarschijnlijk draait zijn service
    niet meer" van. Twee mogelijkheden werden er één, en "mogelijk" werd "waarschijnlijk" — feitbehoud
    dat faalt in het klein, geschreven door een mens met aandacht. Een goedkoop model doet het vaker.

    Fail-open: zonder bron valt er niets te vergelijken, en dan keurt deze poort niets af."""
    b, t = (bron or "").lower(), (tekst or "").lower()
    if not b.strip() or not t.strip():
        return True, ""
    erbij = next((r.pattern for r in _STELLIGER if r.search(t)), "")
    if (erbij and not any(r.search(b) for r in _STELLIGER)
            and any(r.search(b) for r in _SLAG_OM_DE_ARM)):
        woord = erbij.replace(r"\b", "")
        return False, f"stelliger dan de bron: '{woord}' terwijl er een slag om de arm stond"
    # Getallen: elk getal in de uitkomst moet in de bron te vinden zijn. Een datum mag anders
    # geschreven worden ("2026-08-29" → "29 augustus"), want de cijfers zitten dan nog in de bron.
    bron_cijfers = "".join(_GETAL.findall(b))
    for g in _GETAL.findall(t):
        if g not in bron_cijfers:
            return False, f"getal '{g}' staat niet in de ruwe tekst"
    ongegrond = _ongegronde_specifieken(bron or "", tekst or "")
    if ongegrond:
        return False, (f"specifiek gegeven zonder grond in de ruwe tekst: "
                       f"{', '.join(repr(x) for x in ongegrond[:3])}")
    return True, ""


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
    """OP WOORDGRENS. Dit deed een substring-vergelijking, en verwierp daarmee een prima
    herschrijving omdat er "kernproces" stond — "kern" staat in de lijst. Zelfde soort fout als in
    `feitbehoud`, en allebei gevonden door de meting en niet door een test: "match" zit in
    "matchmaker", "store" in "geschiedenisstore", "kern" in "kernproces". Een poort die op letters
    zoekt in plaats van op woorden keurt taal af die er niets mee te maken heeft."""
    laag = (tekst or "").lower()
    return [w for w in JARGON if re.search(r"\b" + re.escape(w) + r"\b", laag)]


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
    # Feitbehoud gaat vóór politoer: liever de ruwe tekst laten staan dan een gladde versie die
    # zekerder of specifieker is dan wat er stond. Afkeuren = terugvallen op het origineel.
    bron = str((bevinding or {}).get("ruw") or "")
    for deel in (spanning, voorstel):
        ok, reden = feitbehoud(bron, deel)
        if not ok:
            return False, reden
    if voorstel_verplicht:
        if len(voorstel) < _MIN_VOORSTEL:
            return False, ("geen concreet voorstel — zonder 'wat wil je doen' is dit een melding, "
                           "geen verzoek")
        if afgekapt(voorstel):
            return False, "het voorstel houdt middenin op"
    return True, ""


# ── de twee tredes ──────────────────────────────────────────────────────────
#
# MISTRAL IS DE BASIS, de sterke trede is de KLIM. Gemeten op vier echte ijkpunten (systeem-pad,
# rol-pad, vrij Engels, verpakte tekst): mistral haalde alle vier de feitbehoud-punten, gemini-flash
# viel af op punt 3 — het voegde "essentieel" en "onbekende gevolgen" toe, karakterisering die de
# bron niet had. Vlotter lezen weegt niet op tegen epistemische inflatie.
#
# De sterke trede stond eerst vooraan, met de dorpsstaart eronder. Dat betekende in de praktijk:
# anthropic zonder krediet → doorvallen naar gemini-flash-LITE, de goedkoopste trede van allemaal en
# precies degene die we niet willen. Vandaar deze volgorde: eerst de trede die het aantoonbaar haalt,
# en de sterke trede alleen waar hij verschil maakt.
_BASIS = "mistral:mistral-small-latest"


def basis_ladder() -> str:
    """De trede die élke herschrijving draait. Met de dorpsstaart eronder, zodat een storing bij één
    leverancier geen lege bevinding oplevert — een spanning zonder tekst bereikt niemand."""
    try:
        from nooch_village.llm import met_dorpsstaart
        return met_dorpsstaart(_BASIS)
    except Exception:                                              # noqa: BLE001
        return _BASIS


def klim_ladder() -> str:
    """De sterke trede, ALLEEN voor een afgekeurde herschrijving. Geen tweede poging voor de sport:
    hij draait waar de goedkope trede aantoonbaar tekortschoot, en dat is precies de plek waar een
    beter oordeel iets oplevert. Is er geen krediet, dan levert hij niets en blijft de ruwe tekst
    staan — dezelfde uitkomst als zonder klim, alleen een call duurder."""
    from nooch_village.llm_keuze import hoog_inzet_ladder
    return hoog_inzet_ladder()


def herschrijf(tekst: str, *, rol: str, records=None, reason_fn=None,
               ladder: str = "", data_dir: str = "", klim: bool = True) -> dict:
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
        ladder = basis_ladder()

    # GROND-EERST, MODEL-LAATST. De deterministische systeemjargon-swap draait vóór de call: gratis,
    # gegarandeerd, en onafhankelijk van welke trede er draait. Wat overblijft (structuur,
    # leesbaarheid, een menselijke vraag in plaats van een commando) is oordeel, en dat is het model.
    # `uit["ruw"]` blijft de ECHTE ruwe tekst: dat veld is herkomst, en herkomst hoor je niet op te
    # poetsen. Loopt de swap de tekst leeg (een bericht dat alleen een commando was), dan gaat de
    # ruwe tekst alsnog naar het model — fail-open naar het origineel, nooit naar niets.
    from nooch_village.systeemtaal import ontjargon
    leesbaar = ontjargon(ruw) or ruw
    from nooch_village.helderheid import reader_tests
    lezerstests, _uit_policy = reader_tests(data_dir)
    prompt = _PROMPT.format(rol=rol or "onbekend", tekst=leesbaar[:1200],
                            accountabilities=_accountabilities(records, rol),
                            lezerstests=lezerstests)
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
    if ok or not klim:
        if not ok:
            log.info("bevinding geweigerd (%s) op: %s", reden, ruw[:70])
        return uit
    # DE KLIM. De goedkope trede schoot aantoonbaar tekort — niet vermoedelijk, maar volgens een
    # deterministische poort. Dát is het moment waarop een sterker model iets toevoegt, en het is
    # ook de enige plek waar we hem betalen. Levert de klim niets (geen krediet, opnieuw afgekeurd),
    # dan blijft de afwijzing van de basis staan en toont het scherm de ruwe tekst.
    sterk = klim_ladder()
    if not sterk or sterk == ladder:
        return uit
    log.info("bevinding: klim naar %s na afkeuring (%s)", sterk, reden)
    hoger = herschrijf(tekst, rol=rol, records=records, reason_fn=reason_fn, ladder=sterk,
                       data_dir=data_dir, klim=False)
    return hoger if hoger.get("ok") else uit
