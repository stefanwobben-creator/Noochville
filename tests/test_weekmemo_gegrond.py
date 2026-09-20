"""De grondings-poort: één implementatie, twee verklaarde gedragingen.

STAP 1 VAN DE SIGNAALPIJPLIJN. `claims_modelpas` en `claim_evidence` hadden allebei hun eigen
grondings-poort — dezelfde regel (het fragment moet letterlijk in de brontekst staan), dezelfde
drempel (20 tekens), en twee verschillende normalisatoren. Gemeten op 20 september 2026 waren ze het
in 2 van 6 gevallen oneens, en geen van beide docstrings noemde de keuze. Dat is drift, geen
ontwerp: `reference, don't copy` op een regel in plaats van op een getal.

BESLUIT (Stefan, 20 september): beide gedragingen blijven, maar expliciet. `gegrond(..., streng=)`
zonder default — een default zou de keuze weer onzichtbaar maken, en dat is precies wat we opheffen.

DE HARDE EIS VAN DEZE STAP was: geen gedragsverandering per bron. Dit bestand bewijst dat met de
ZES GEVALLEN UIT DE METING, letterlijk overgenomen, en met dezelfde uitkomsten als vóór de
samenvoeging. Zou iemand later de normalisatie "opschonen", dan valt precies dit om.
"""
from __future__ import annotations

import pytest

from nooch_village.weekmemo import MIN_FRAGMENT, gegrond

# De meetgevallen van 20 september, met per geval wat elke modus hoort te zeggen.
# (naam, fragment, brontekst, los, streng)
METING = [
    ("letterlijk gelijk",
     "onze zolen verdwijnen gewoon weer in de grond",
     "Wij geloven erin: onze zolen verdwijnen gewoon weer in de grond, zonder rest.",
     True, True),
    ("komma in de bron, niet in het citaat",
     "onze zolen verdwijnen gewoon weer in de grond zonder rest",
     "Wij geloven erin: onze zolen verdwijnen, gewoon weer in de grond, zonder rest.",
     True, False),
    ("dubbele spatie in de bron",
     "our soles are fully biodegradable",
     "Note:  our soles  are fully biodegradable in soil.",
     True, True),
    ("regeleinde midden in het citaat",
     "our soles are fully biodegradable",
     "Note: our soles\nare fully biodegradable in soil.",
     True, True),
    ("hoofdletters",
     "CARBON NEUTRAL SINCE TWENTY TWENTY",
     "We are carbon neutral since twenty twenty, audited.",
     True, True),
    ("koppelteken",
     "a plastic-free upper made from hemp",
     "We use a plastic free upper made from hemp.",
     True, False),
]


@pytest.mark.parametrize("naam,fragment,bron,los,streng", METING)
def test_de_meting_van_20_september_blijft_kloppen(naam, fragment, bron, los, streng):
    """Beide modi doen precies wat ze vóór de samenvoeging deden. Dit is de test die de belofte
    'geen gedragsverandering vandaag' waarmaakt."""
    assert gegrond(fragment, bron, streng=False) is los, f"{naam}: losse modus veranderde"
    assert gegrond(fragment, bron, streng=True) is streng, f"{naam}: strenge modus veranderde"


def test_de_twee_modi_verschillen_aantoonbaar():
    """Zonder dit is niet te zien DAT er twee gedragingen zijn — en dan is `streng` een parameter
    die niets doet en bij de eerste opruiming sneuvelt."""
    verschillen = [n for n, f, b, los, streng in METING if los != streng]
    assert len(verschillen) == 2, verschillen


# ── de bronnen houden hun eigen keuze ───────────────────────────────────────

def test_claims_modelpas_staat_op_los():
    """Recall-posture: "een onterechte vlag kost een muisklik, een gemiste claim een boete"."""
    from nooch_village.claims_modelpas import _gegrond
    assert _gegrond("a plastic-free upper made from hemp",
                    "We use a plastic free upper made from hemp.") is True


def test_claim_evidence_staat_op_streng():
    """Bewijs-posture: het citaat ÍS het bewijs. Een parafrase die 'bijna' klopt, grondt niet —
    daar beroept zich later iemand op."""
    from nooch_village.skills_impl.claim_evidence import _grounded
    assert _grounded("a plastic-free upper made from hemp",
                     "We use a plastic free upper made from hemp.") is False


# ── de drempel en de randen ─────────────────────────────────────────────────

def test_te_kort_grondt_nooit():
    """Een fragment van tien tekens komt in elke pagina wel ergens voor. Beide implementaties
    hadden deze 20 al, onafhankelijk — het enige waar ze het over eens waren."""
    kort = "x" * (MIN_FRAGMENT - 1)
    bron = "iets langs met " + kort + " erin verwerkt, ruim boven de drempel"
    assert gegrond(kort, bron, streng=True) is False
    assert gegrond(kort, bron, streng=False) is False


def test_niet_in_de_bron_grondt_nooit():
    """De hele reden dat deze poort bestaat: een model dat een claim verzint mag er geen taak of
    Kroniek-record van kunnen maken."""
    verzonnen = "onze schoenen zijn gecertificeerd door het TÜV voor volledige afbreekbaarheid"
    bron = "Wij werken aan duurzamere materialen en publiceren daar binnenkort over."
    assert gegrond(verzonnen, bron, streng=True) is False
    assert gegrond(verzonnen, bron, streng=False) is False


def test_lege_invoer_valt_om_in_plaats_van_alles_door_te_laten():
    """Fail-closed op de randen: een leeg fragment is korter dan de drempel, dus nee. Zou dit
    `True` geven (want "" zit in elke tekst), dan grondde een leeg modelantwoord alles."""
    assert gegrond("", "wat tekst dan ook", streng=True) is False
    assert gegrond("", "wat tekst dan ook", streng=False) is False
    assert gegrond("een fragment van ruim voldoende lengte", "", streng=True) is False


def test_streng_heeft_geen_default():
    """De parameter is keyword-only ÉN verplicht. Een default zou de keuze weer onzichtbaar maken,
    en dat is exact de drift die deze functie opheft."""
    with pytest.raises(TypeError):
        gegrond("een fragment van ruim voldoende lengte", "een fragment van ruim voldoende lengte")
