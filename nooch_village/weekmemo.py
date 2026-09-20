"""De signaalpijplijn: verzamelen → filteren → synthese → bij de founder.

Dit bestand begint klein. Stap 1 van het bouwplan is één ding: de grondings-poort, die tot nu toe
twee keer met de hand was geschreven en uit elkaar was gelopen.

WAT DE POORT DOET. Een model dat een claim of een citaat teruggeeft, moet dat fragment LETTERLIJK
uit de brontekst hebben gehaald. Staat het er niet, dan vervalt de kandidaat. Zo kan een model geen
bewijs verzinnen dat daarna een taak of een Kroniek-record wordt. Het is de enige regel die
`claims_modelpas` en `claim_evidence` allebei al hadden, en de enige die geen model kost.

DE TWEE WAREN HET ONEENS, gemeten op 20 september 2026 — in 2 van 6 gevallen:

    geval                                        modelpas   evidence
    komma in de bron, niet in het citaat            True      False
    "plastic-free" tegen "plastic free"             True      False

De oorzaak was één regel elk. `claims_modelpas` streek ALLE leestekens weg
(`[^a-z0-9]+` → spatie); `claim_evidence` hield ze en vouwde alleen witruimte. Geen van beide
docstrings noemde die keuze — ze zeiden allebei "genormaliseerd letterlijk". Dat maakt het drift en
geen ontwerp: twee mensen die op twee momenten hetzelfde bedoelden en het anders schreven.

STEFANS BESLUIT (20 september): beide gedragingen blijven, maar als VERKLAARDE keuze. Eén functie,
één paar normalisatoren, en de strengheid een expliciet argument — net zoals de drempel per bron
(stap 2 van het bouwplan) bij de bron hoort en niet in de pijplijn.

    streng=True   letterlijk is letterlijk, leestekens tellen mee. Voor BEWIJS: het citaat ís het
                  bewijs, en een Kroniek-record dat grondt op een citaat dat net iets anders op de
                  pagina staat, is geen bewijs maar een parafrase.  → `claim_evidence`
    streng=False  leestekens tellen niet mee. Voor RECALL: een model dat correct citeert maar
                  herinterpungeert verliest zijn vondst niet. De posture van die bron staat er zelf
                  bij: "een onterechte vlag kost een muisklik, een gemiste claim een boete".
                  → `claims_modelpas`

WAT DIT NIET IS: een middenweg. Er is bewust geen derde modus die "meestal goed" doet. Wie een
nieuwe bron toevoegt kiest een van de twee en schrijft op waarom — dat is de hele winst van deze
stap, naast het feit dat de regel nu op één plek staat.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from nooch_village.util import JsonStore

#: Korter dan dit is te generiek om als vindplaats te dienen: een fragment van tien tekens komt in
#: elke pagina wel ergens voor, en dan grondt de poort niets meer. Beide implementaties hanteerden
#: deze 20 al, onafhankelijk van elkaar — het enige waar ze het over eens waren.
MIN_FRAGMENT = 20

_NIET_WOORD = re.compile(r"[^a-z0-9]+")
_WITRUIMTE = re.compile(r"\s+")


def norm_streng(tekst: str) -> str:
    """Witruimte gevouwen, kleine letters. Leestekens BLIJVEN staan."""
    return _WITRUIMTE.sub(" ", tekst or "").strip().casefold()


def norm_los(tekst: str) -> str:
    """Alles wat geen letter of cijfer is wordt een spatie. Leestekens verdwijnen dus."""
    return _NIET_WOORD.sub(" ", (tekst or "").lower()).strip()


def gegrond(fragment: str, brontekst: str, *, streng: bool) -> bool:
    """Staat dit fragment letterlijk in de brontekst, en is het lang genoeg om iets te betekenen?

    `streng` is verplicht en heeft met opzet geen default. Een default zou de keuze weer onzichtbaar
    maken, en dat is precies de drift die deze functie opheft — wie hem aanroept, kiest."""
    norm = norm_streng if streng else norm_los
    f = norm(fragment)
    return len(f) >= MIN_FRAGMENT and f in norm(brontekst)


# ── Stap 2: één signaalvorm, en de drempel bij de bron ──────────────────────────────────────────
#
# WAAROM ÉÉN VORM. De vijf bronnen leveren vandaag drie verschillende dingen: een claim-bevinding
# (term + pagina + stoplicht), een radar-item (feed-item met link en bron) en een Kroniek-record
# (merk + claim + status). Zolang die drie vormen los leven, moet elke lezer ze alle drie kennen —
# en dat is precies waarom de synthese in stap 4 anders vijf keer geschreven zou worden.
#
# WAT ER BEWUST NIET IN ZIT: een status, een oordeel, een ontvanger. Een signaal is een WAARNEMING.
# Wat ermee gebeurt beslist de mens die de memo leest; zet je dat hier al in het model, dan kruipt
# de beslissing terug in de pijplijn (CLAUDE.md, "AI is instrument, geen rol").


@dataclass(frozen=True)
class Signaal:
    """Eén waarneming, ongeacht welke bron hem zag.

    Bevroren met opzet: een verzamelaar levert waarnemingen en verandert er niets meer aan. Wie
    iets wil toevoegen maakt een nieuw signaal, zodat je in de memo kunt terugzien wat de bron zei
    en niet wat er onderweg van gemaakt is."""

    bron: str                       #: welke adapter hem zag — de sleutel in `BRONNEN`
    tekst: str                      #: wat er is waargenomen, in de woorden van de bron
    vindplaats: str = ""            #: waar het staat: een URL, een paginalabel, een merknaam
    gevonden_op: float = 0.0        #: wanneer de BRON het zag, niet wanneer wij het ophaalden
    herkomst: str = ""              #: het id van het onderliggende record, om op terug te vallen
    extra: dict = field(default_factory=dict)   #: wat alleen deze bron weet (stoplicht, feed, …)


#: DE DREMPEL HOORT BIJ DE BRON, NIET BIJ DE PIJPLIJN. Dit was de belangrijkste ontwerpkeuze van
#: stap 2: de drie postures hieronder zijn alle drie verdedigbaar voor hun onderwerp en ze zijn NIET
#: te middelen. Ze hier naast elkaar zetten maakt dat zichtbaar in plaats van impliciet in vijf
#: modules — en dwingt wie een bron toevoegt om te zeggen welke hij kiest.
#:
#:   recall       bij twijfel melden. Een onterechte vlag kost een muisklik, een gemiste claim
#:                een boete.
#:   precisie     bij twijfel NIET melden. Dit zijn filters: ze halen weg, en te veel weghalen is
#:                hier de dure fout.
#:   fail-closed  bij twijfel niets. Liever een gemiste melding dan een verzonnen alarm — een vals
#:                alarm ondermijnt de echte.
#:   selectie     hooguit een handvol, liever nul dan een zwakke.
DREMPELS = ("recall", "precisie", "fail-closed", "selectie")


# ── Stap 4: de synthese ─────────────────────────────────────────────────────────────────────────
#
# WAAROM ÉÉN MEMO OVER ALLE BRONNEN, en niet vijf losse. Dit was Stefans besluit, en de reden staat
# in zijn eigen woorden: *"de synthese is waar de waarde zit"*. Vijf losse memo's zijn vijf lijstjes;
# de vraag die een mens echt heeft — waar raken deze dingen elkaar — beantwoordt geen van de vijf.
# Een wetswijziging over groene claims (legal) naast een modelvondst op de eigen FAQ (claim_model)
# naast een merk dat zijn claim wél onderbouwt (bewijs) is samen één verhaal, en apart drie feiten.
#
# DAAROM MAG HIER EEN DUUR MODEL. `weekmemo_synthese` staat in `llm_keuze.HOOG_INZET`; dat is een
# bevroren lijst en een toevoeging is een besluit. Eén call per week, dus kosten zijn hier geen
# overweging — en het is de enige plek in deze pijplijn waar het model iets maakt in plaats van
# filtert.

#: Waar het ritme en het geheugen staan. Geen nieuwe store in `_Stores`: dit is een bestand naast
#: de stores, hetzelfde patroon dat `materiaal_memo.STATE` al gebruikt.
STATE = "weekmemo.json"

CALL_SITE = "weekmemo_synthese"

#: Hoeveel signalen er hooguit in de prompt gaan. Boven dit aantal is de memo geen synthese meer
#: maar een opsomming, en een model dat honderd losse feiten moet wegen doet dat slechter dan tien.
#: Wat erbuiten valt wordt geTELD, niet verzwegen — zie `_kaal`.
PROMPT_CAP = 40


class _Staat(JsonStore):
    """Ritme én geheugen in één bestand, achter het slot.

    WAAROM `JsonStore` EN GEEN LOSSE `atomic_write_json`, zoals `materiaal_memo` het doet. De
    lock-ratchet (`test_geen_ongelockte_write`) laat een uitzondering toe mét een reden, en de voor
    de hand liggende reden zou hier "single-writer: alleen de puls" zijn. Precies daarvoor
    waarschuwt die test in zijn eigen kop: `library.py` en `source_status.py` stonden er met die
    reden, en die verjaarde toen het cockpit erin ging schrijven — de ratchet bleef groen terwijl de
    schuld groeide. "Een reden die verjaart is erger dan geen reden."

    Deze staat wordt straks door de puls geschreven en mogelijk door een CLI; het slot kost hier
    niets en maakt die vraag overbodig."""

    _WRITE_METHODS = ("markeer_gedraaid", "onthoud")

    def gedraaid_in(self, periode: str) -> bool:
        return str(self._items.get("laatste_periode") or "") == str(periode)

    def markeer_gedraaid(self, periode: str, *, aantal: int = 0) -> None:
        import time
        self._items["laatste_periode"] = str(periode)
        self._items["laatste_at"] = time.time()
        self._items["laatste_aantal"] = int(aantal)
        self._save()

    def boek(self) -> dict:
        return dict(self._items.get("voorgelegd") or {})

    def onthoud(self, herkomsten) -> None:
        import time
        boek = self._items.setdefault("voorgelegd", {})
        nu = time.time()
        for h in herkomsten:
            if h:
                boek.setdefault(str(h), nu)
        self._save()


def _staat(data_dir: str) -> _Staat:
    import os
    return _Staat(os.path.join(data_dir or ".", STATE))


def al_gedraaid(data_dir: str, periode: str) -> bool:
    """Is deze week de memo al opgesteld? Het ritme leeft in het bestand en niet in het geheugen,
    want de daemon herstart en de puls draait vaker dan één keer per week."""
    return _staat(data_dir).gedraaid_in(periode)


def markeer_gedraaid(data_dir: str, periode: str, *, aantal: int = 0) -> None:
    _staat(data_dir).markeer_gedraaid(periode, aantal=aantal)


def voorgelegd(data_dir: str) -> dict:
    """{herkomst: wanneer} — wat al in een memo heeft gestaan, over ALLE bronnen heen.

    DIT IS DE ENE PLEK, en dat was de belofte bij adapter 2. `materiaal_memo` had zijn eigen boek
    omdat het de enige bron met een geheugen was; met vijf bronnen zou dat vijf boeken worden die
    hetzelfde feit bijhouden. Een verzamelaar schrijft niet — de memo onthoudt, één keer, voor
    iedereen."""
    return _staat(data_dir).boek()


def onthoud(data_dir: str, herkomsten) -> None:
    _staat(data_dir).onthoud(herkomsten)


def nieuw(data_dir: str, signalen: list) -> list:
    """De signalen die nog nooit in een memo stonden. Zonder herkomst kan er niets onthouden
    worden, en dan is 'nieuw' de veilige aanname — liever twee keer tonen dan stil overslaan."""
    boek = voorgelegd(data_dir)
    return [s for s in signalen if not s.herkomst or str(s.herkomst) not in boek]


def _regel(s) -> str:
    """Eén signaal als promptregel: wat er is waargenomen, waar, en wat de bron ervan vond."""
    kop = f"[{s.bron}] {s.tekst[:300]}"
    waar = f"\n  waar: {s.vindplaats}" if s.vindplaats else ""
    duiding = "; ".join(f"{k}: {v}" for k, v in sorted((s.extra or {}).items())
                        if v and k not in ("afgekapt", "week"))
    return kop + waar + (f"\n  bron zegt: {duiding[:300]}" if duiding else "")


def _kaal(signalen: list, periode: str) -> str:
    """De memo zonder model: een opsomming mét bronnen, gegroepeerd per bron.

    FAIL-OPEN MET DE FEITEN, en dat weegt hier zwaarder dan bij `materiaal_memo` waar dit vandaan
    komt. Daar viel één memo weg als het model niet kon; hier vallen ALLE VIJF de bronnen weg. Een
    lijst met bronnen is lelijk en bruikbaar; een lege memo is stilte over een week waarin wel
    degelijk iets gebeurde."""
    per_bron: dict = {}
    for s in signalen:
        per_bron.setdefault(s.bron, []).append(s)
    stukken = [f"🗂 Signalen week {periode} — {len(signalen)} stuks, geen synthese beschikbaar."]
    for bron in sorted(per_bron):
        stukken.append(f"\n{bron} ({len(per_bron[bron])}):")
        stukken += [f"- {_regel(s)}" for s in per_bron[bron]]
    return "\n".join(stukken)


def stel_op(signalen: list, periode: str, *, reason_fn=None) -> str:
    """De weekmemo als tekst. Nooit leeg als er signalen zijn.

    DE PROMPTREGELS ZIJN OVERGENOMEN VAN `materiaal_memo._schrijf_memo`, want die zijn daar duur
    betaald: alleen noemen wat er staat, geen verzonnen cijfers of leveranciers, en afsluiten met
    wat je NIET kon zien. Die laatste is de belangrijkste — een blinde vlek benoemen is
    informatiever dan hem verzwijgen, en bij vijf bronnen met vijf verschillende drempels is er
    altijd een blinde vlek.

    WAT HIER BIJKOMT ten opzichte van die ene memo: de bronnen hebben verschillende DREMPELS, en
    het model moet weten dat een `recall`-signaal iets anders weegt dan een `fail-closed`-signaal.
    Anders leest het een modelvondst met dezelfde stelligheid als een vastgesteld Kroniek-feit."""
    if not signalen:
        return ""
    kaal = _kaal(signalen, periode)
    in_prompt = signalen[:PROMPT_CAP]
    rest = len(signalen) - len(in_prompt)
    regels = "\n".join(_regel(s) for s in in_prompt)
    prompt = (
        "Je schrijft de WEEKMEMO voor de founder van Nooch (duurzame veganistische schoenen).\n"
        "Vijf bronnen leveren signalen aan; jij maakt er één leesstuk van.\n\n"
        "WAT DE BRONNEN ZIJN, en hoe zeker ze zijn — dit verschil moet in je tekst terug te zien "
        "zijn:\n"
        "- legal        nieuws over wetgeving. Fail-closed: staat het er, dan is het relevant.\n"
        "- bewijs       vastgestelde feiten uit ons eigen bewijsregister. Het zekerst.\n"
        "- claim_regex  termen op onze site die een toetser zou bekijken, al gefilterd op context.\n"
        "- claim_model  zinnen die een model als claim LAS. Afgesteld op ruim melden: dit is een\n"
        "               vermoeden, geen vaststelling. Schrijf er nooit over alsof het vaststaat.\n"
        "- materiaal    materiaalkandidaten, al geschift op marktrijpheid.\n\n"
        "REGELS:\n"
        "- Maximaal 350 woorden, Nederlands.\n"
        "- Groepeer in 3-5 thema's. Een thema mag signalen van VERSCHILLENDE bronnen bundelen — "
        "dat is precies waar deze memo voor bestaat.\n"
        "- Noem alleen wat in de signalen staat. Verzin geen cijfers, merken, deadlines of "
        "leveranciers; staat het er niet, dan staat het er niet.\n"
        "- Geen aanbevelingen en geen taken. Je beschrijft wat er ligt; de founder beslist.\n"
        "- Sluit af met wat je NIET kon zien in deze stroom.\n\n"
        f"PERIODE: {periode}\n"
        + (f"LET OP: {rest} signaal/signalen vielen buiten deze lijst; noem dat in je slotregel.\n"
           if rest > 0 else "")
        + f"SIGNALEN ({len(in_prompt)}):\n{regels}")
    if reason_fn is None:
        from nooch_village.llm import reason as reason_fn          # noqa: PLC0415
    try:
        from nooch_village.llm_keuze import ladder_voor
        uit = reason_fn(prompt, call_site=CALL_SITE, max_tokens=1200,
                        ladder=ladder_voor(CALL_SITE))
    except Exception:                                              # noqa: BLE001
        import logging
        logging.getLogger("village.weekmemo").warning(
            "weekmemo: model niet bereikbaar — kale opsomming met bronnen", exc_info=True)
        return kaal
    if not uit:
        return kaal
    return f"🗂 Weekmemo {periode}\n\n{str(uit).strip()}\n\n({len(signalen)} signalen)"
