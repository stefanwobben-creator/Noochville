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




from nooch_village import bevinding as bv
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


def test_jargon_herkent_woorden_geen_deelwoorden():
    for lang, kort in VALSTRIKKEN:
        if kort not in bv.JARGON:
            continue
        assert bv.jargon_in(f"we keken naar het {lang} van vandaag") == [], lang
        assert bv.jargon_in(f"we keken naar de {kort} van vandaag") == [kort], kort


def test_feitbehoud_herkent_woorden_geen_deelwoorden():
    bron = "mogelijk niet gestart, geen fout gemeld"
    assert bv.feitbehoud(bron, "Het is onduidelijk wat er gebeurde.")[0] is True
    assert bv.feitbehoud(bron, "We moeten zeker weten of alles werkt.")[0] is True
    assert bv.feitbehoud(bron, "Het is duidelijk kapot.")[0] is False


def test_de_systeemtaal_swaps_ook():
    """Deel 1 deed het van begin af aan goed (`\\b` rond elke bron), en dat moet zo blijven: een
    swap op deelwoord zou "hookje" of "servicedesk" verminken."""
    assert "achtergrondproces" not in st.ontjargon("de servicedesk belde")
    assert "achtergrondproces" not in st.ontjargon("een dagelijkse routine")
    assert st.ontjargon("de service startte niet") == "het achtergrondproces startte niet"


# ── de ratchet ──────────────────────────────────────────────────────────────

def _woordlijsten():
    """Elke lijst met woorden die ergens tegen een tekst wordt gehouden."""
    return {
        "bevinding.JARGON": list(bv.JARGON),
        "bevinding._SLAG_OM_DE_ARM": [r.pattern.replace(r"\b", "") for r in bv._SLAG_OM_DE_ARM],
        "bevinding._STELLIGER": [r.pattern.replace(r"\b", "") for r in bv._STELLIGER],
        "systeemtaal.SWAPS": [b for b, _ in st.SWAPS],
    }


def test_geen_enkele_woordlijst_matcht_op_een_deelwoord():
    """DE RATCHET, en hij toetst GEDRAG in plaats van broncode.

    Voor elk woord in elke lijst: plak er iets voor en achter, en controleer dat geen poort erop
    aanslaat. Een nieuwe lijst met een `in`-vergelijking valt hier vanzelf om — dat is precies hoe
    beide bugs ontstonden, en allebei faalden ze STIL: de gebruiker zag gewoon de ruwe tekst.

    Bewust gedrag en niet de tekst van de functie: een broncode-scan op `in` gaf een valse treffer op
    een variabele die toevallig `r` heette. Een poort die zijn eigen implementatie beschrijft is
    zwakker dan een poort die zijn eigen uitkomst meet."""
    voorvoegsels, achtervoegsels = ("on", "her", "in"), ("proces", "maker", "desk", "je")
    for naam, woorden in _woordlijsten().items():
        for w in woorden:
            if " " in w or not w.isalpha():
                continue                                  # samenstellingen en snake_case: geen val
            langer = [v + w for v in voorvoegsels] + [w + a for a in achtervoegsels]
            for lang in langer:
                zin = f"we bespraken het {lang} van vandaag"
                assert bv.jargon_in(zin) == [], f"{naam}: jargon_in matcht op '{lang}'"
                assert st.raakt(zin) == [], f"{naam}: systeemtaal matcht op '{lang}'"
                assert st.ontjargon(zin) == zin, f"{naam}: swap raakt '{lang}'"
                bron = "mogelijk iets, geen fout gemeld"
                assert bv.feitbehoud(bron, zin)[0] is True, f"{naam}: feitbehoud struikelt over '{lang}'"


def test_het_echte_woord_wordt_wel_herkend():
    """De andere kant van de ratchet: strenger maken mag niet betekenen dat hij niets meer ziet."""
    assert bv.jargon_in("de kern van de zaak") == ["kern"]
    assert st.raakt("de service viel om") == ["service"]
    assert bv.feitbehoud("mogelijk iets", "Het is duidelijk kapot.")[0] is False
