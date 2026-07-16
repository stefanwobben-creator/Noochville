"""Belofte-graaf: eerste-principes-reconstructie, bewezen domein-agnostisch.

De kern (weeg_belofte) mag NIETS van schoen/materiaal weten. De laatste test draait
dezelfde functie over drie domeinen (schoen, papieren paperclip, studie-dienst) en eist
identiek gedrag. Als dat breekt, is de abstractie lek."""
from nooch_village.belofte_graaf import (
    Oordeel, Sterkte, Constituent, weeg_belofte, ground_constituenten,
)
from nooch_village.compositie import ontleed_bom, ontleed_voorwaarden, _alternatieven

# fragment van de echte Nooch-BOM (tab-gescheiden, met legenda-kolom en 'Or'-alternatieven)
_BOM = (
    "Legenda\t\tPart\tMaterial\tComment\n"
    "Done\t\tOutsole\tPliant\t\n"
    "Please fill inn\t\tVamp\tHyphaLite\t< Or hemp fabric, Or organic cotton fabric\n"
    "\t\tLining\tHyphalite Lining\t< Or organic cotton\n"
    "\t\tOutsole stitch\tCotton thread\t< Might be linen thread, please check.\n"
    "\t\tGlue / cement\tWaterbased Latex based Glue\t\n"
    "\t\tLaces\tOrganic cotton laces\t\n"
)


def test_bom_ontleed_kop_en_alternatieven():
    cs = ontleed_bom(_BOM)
    namen = [c.naam for c in cs]
    assert "Part" not in namen                       # koprij overgeslagen
    assert "Outsole" in namen and "Glue / cement" in namen
    vamp = next(c for c in cs if c.naam == "Vamp")
    assert vamp.realisatie == "HyphaLite"
    assert vamp.alternatieven == ("hemp fabric", "organic cotton fabric")
    # een vrije check-opmerking is géén alternatief
    stitch = next(c for c in cs if c.naam == "Outsole stitch")
    assert stitch.alternatieven == ()
    assert all(c.bron == "BOM" for c in cs)


def test_weakest_link_breekt_op_een_constituent():
    oordelen = {"Outsole": Oordeel.HOUDT, "Vamp": Oordeel.HOUDT,
                "Glue / cement": Oordeel.HOUDT_NIET}
    w = weeg_belofte(oordelen)
    assert w.sterkte == Sterkte.GEBROKEN and not w.houdbaar
    assert w.gebroken_op == ("Glue / cement",)
    assert w.bottleneck == ("Glue / cement",)


def test_onbekend_maakt_onbewezen_niet_gebroken():
    w = weeg_belofte({"a": Oordeel.HOUDT, "b": Oordeel.ONBEKEND})
    assert w.sterkte == Sterkte.ONBEWEZEN and not w.houdbaar
    assert w.onbekend_op == ("b",) and w.gebroken_op == ()


def test_alles_houdt_is_verdedigbaar():
    w = weeg_belofte({"a": Oordeel.HOUDT, "b": Oordeel.HOUDT})
    assert w.sterkte == Sterkte.VERDEDIGBAAR and w.houdbaar and w.bottleneck == ()


def test_leeg():
    assert weeg_belofte({}).sterkte == Sterkte.LEEG


def test_breuk_wint_van_onbekend():
    # zowel een breuk als een gat → gebroken (de breuk is definitief), gat blijft zichtbaar
    w = weeg_belofte({"a": Oordeel.HOUDT_NIET, "b": Oordeel.ONBEKEND})
    assert w.sterkte == Sterkte.GEBROKEN
    assert w.gebroken_op == ("a",) and w.onbekend_op == ("b",)


def test_zelfde_model_geldt_voor_dienst_en_paperclip():
    # papieren paperclip: functionele constituenten, geen materiaal-BOM
    paperclip = {"klemkracht": Oordeel.HOUDT, "papiervezel-sterkte": Oordeel.HOUDT_NIET,
                 "herbruikbaarheid": Oordeel.HOUDT}
    wp = weeg_belofte(paperclip)
    assert wp.sterkte == Sterkte.GEBROKEN and wp.gebroken_op == ("papiervezel-sterkte",)

    # studie-dienst voor 65-jarigen: voorwaarden i.p.v. onderdelen, zelfde vorm
    cs = ontleed_voorwaarden([
        ("inschrijftoegang", "open inschrijving"),
        ("cognitieve aansluiting", "aangepast tempo"),
        ("tech-toegankelijkheid", "begeleide onboarding"),
        ("erkenning diploma", ""),
    ])
    assert cs[0].bron == "dienstontwerp" and cs[0].realisatie == "open inschrijving"
    dienst = {cs[0].naam: Oordeel.HOUDT, cs[1].naam: Oordeel.HOUDT,
              cs[2].naam: Oordeel.HOUDT, cs[3].naam: Oordeel.ONBEKEND}
    wd = weeg_belofte(dienst)
    assert wd.sterkte == Sterkte.ONBEWEZEN and wd.onbekend_op == ("erkenning diploma",)


def test_ground_fail_closed():
    cs = [Constituent("x"), Constituent("y")]

    def kapot(_c):
        raise RuntimeError("llm down")

    assert ground_constituenten(cs, kapot) == {"x": Oordeel.ONBEKEND, "y": Oordeel.ONBEKEND}

    def half(c):
        return (Oordeel.HOUDT, "ok") if c.naam == "x" else ("ja", "")  # 'ja' is geen Oordeel

    assert ground_constituenten(cs, half) == {"x": Oordeel.HOUDT, "y": Oordeel.ONBEKEND}


def test_alternatieven_helper():
    assert _alternatieven("< Or hemp fabric, Or organic cotton fabric") == (
        "hemp fabric", "organic cotton fabric")
    assert _alternatieven("< Might be linen thread, please check.") == ()
    assert _alternatieven("") == ()
