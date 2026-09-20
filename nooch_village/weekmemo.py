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
