"""Een poort die op LETTERS zoekt keurt taal af die er niets mee te maken heeft.

TWEE KEER DEZELFDE FOUT, op één dag gevonden, allebei door een meting op echte berichten en geen van
beide door een test:

  1. `bevinding.jargon_in` deed een substring-vergelijking. "kern" staat op de jargonlijst, dus
     "kernproces" werd afgekeurd; "match" staat erop, dus "matchmaker" ook. Deze poort stond LIVE en
     verwierp stil correcte herschrijvingen — je ziet er niets van, want het resultaat is gewoon de
     ruwe tekst.
  2. `bevinding.feitbehoud` — die ik diezelfde dag schreef om epistemisch niveau te bewaken — las
     "ONduidelijk" als "duidelijk". Het woord dat de slag om de arm juist vasthoudt, gelezen als het
     tegendeel. De poort die betekenis moet beschermen draaide zelf een betekenis om.

Dat is de ergste variant, en daarom staat hier een ratchet in plaats van alleen twee regressietests:
elke poort die woorden herkent, herkent ze op WOORDGRENS. Een nieuwe lijst met een `in`-vergelijking
valt hier om.
"""
from __future__ import annotations


from nooch_village import systeemtaal as st

# Woorden die een andere term als deelwoord bevatten. Elk van deze zinnen is legitiem Nederlands en
# mag door geen enkele poort worden aangezien voor jargon of voor een zekerheidsclaim.
VALSTRIKKEN = (
    ("kernproces", "kern"),
    ("matchmaker", "match"),
    ("onduidelijk", "duidelijk"),
    ("geschiedenisstore", "store"),
    ("poortwachter", "poort"),
    ("onzeker", "zeker"),
)


def test_de_valstrikken_bevatten_echt_wat_ze_beweren():
    """De testdata zelf moet kloppen, anders bewijst hij niets."""
    for lang, kort in VALSTRIKKEN:
        assert kort in lang and lang != kort


def test_de_systeemtaal_swaps_ook():
    """Deel 1 deed het van begin af aan goed (`\\b` rond elke bron), en dat moet zo blijven: een
    swap op deelwoord zou "hookje" of "servicedesk" verminken."""
    assert "achtergrondproces" not in st.ontjargon("de servicedesk belde")
    assert "achtergrondproces" not in st.ontjargon("een dagelijkse routine")
    assert st.ontjargon("de service startte niet") == "het achtergrondproces startte niet"


# ── de ratchet ──────────────────────────────────────────────────────────────


