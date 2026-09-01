"""De deterministische helft van de copy-checker, plus de koppeltest die het blok mag bestaan.

DE CHECKER HERSCHRIJFT NIETS. Nina schreef de tekst; wij wijzen aan waar iets wringt en stellen iets
voor. Zij beslist. Spiegelbeeld van de leesbaarheidslaag — daar herschrijven we machinewerk vóór een
mens, hier laten we mensenwerk staan.

HET BLOK IS EEN TWEEDE PLEK waar dezelfde regels staan, en onze eigen conventie zegt dat een tweede
plek afdrijft tenzij iets klaagt. De koppeltest is dat iets: elke term moet in de PROSA van diezelfde
policy staan, en elke numerieke limiet draagt het prosa-fragment dat hem uitspreekt.
"""
from __future__ import annotations

from nooch_village import copycheck as cc

BODY = """Every text passes these before it goes out.

  **Hard limits**
  Never write: friend, join the movement, duurzame keuze.

  - Zero emoji.
  - Maximum one exclamation mark per text. Target zero.

  **Claims**
  Never say biodegradable without a source.

```check
verboden: friend, join the movement, duurzame keuze
bron_vereist: biodegradable
max_emoji: 0 | Zero emoji
max_uitroepteken: 1 | Maximum one exclamation mark per text
```
"""


# ── het blok ────────────────────────────────────────────────────────────────

def test_het_blok_wordt_gelezen():
    blok = cc.parse_blok(BODY)
    assert blok["verboden"] == ["friend", "join the movement", "duurzame keuze"]
    assert blok["bron_vereist"] == ["biodegradable"]
    assert blok["limieten"]["emoji"] == (0, "Zero emoji")


def test_zonder_blok_geen_regels():
    """Een policy zonder blok levert geen checks — en dus ook geen valse zekerheid."""
    assert cc.parse_blok("gewone prosa zonder blok") == {}
    assert cc.check("wat dan ook", {}) == []


# ── de koppeltest ───────────────────────────────────────────────────────────

def test_blok_en_prosa_zeggen_hetzelfde():
    assert cc.koppeltest(BODY) == []


def test_een_term_die_de_prosa_niet_noemt_laat_de_test_falen():
    """DE HELE REDEN DAT HET BLOK MAG BESTAAN. Zonder deze test is het een tweede waarheid die
    stilletjes iets anders gaat zeggen dan de tekst die de eigenaar leest en onderhoudt."""
    stiekem = BODY.replace("verboden: friend", "verboden: eco-warrior, friend")
    klachten = cc.koppeltest(stiekem)
    assert any("eco-warrior" in k for k in klachten), klachten


def test_een_limiet_zonder_prosa_anker_faalt():
    """Een limiet die je nergens kunt terugvinden is een regel zonder grond."""
    kaal = BODY.replace("max_emoji: 0 | Zero emoji", "max_emoji: 0")
    assert any("prosa-anker" in k for k in cc.koppeltest(kaal))


def test_een_getal_dat_de_prosa_niet_noemt_faalt():
    """NUMERIEKE LIMIETEN HOREN OOK IN DE PROSA. Een blok dat "max 2" zegt terwijl de tekst over één
    gaat, is precies de divergentie waar deze test voor bestaat."""
    scheef = BODY.replace("max_uitroepteken: 1 |", "max_uitroepteken: 2 |")
    assert any("noemt dat getal niet" in k for k in cc.koppeltest(scheef))


def test_een_anker_dat_niet_in_de_prosa_staat_faalt():
    verzonnen = BODY.replace("| Zero emoji", "| Absolutely no emoji whatsoever")
    assert any("anker" in k for k in cc.koppeltest(verzonnen))


# ── de check ────────────────────────────────────────────────────────────────

def test_een_verboden_woord_wordt_geflagd_met_citaat():
    """COPYCHECK-001 eist het letterlijk: "Quote the failing sentence, do not summarise." Een
    bevinding zonder citaat dwingt de lezer zelf te gaan zoeken."""
    tekst = "Hey friend, welcome to Nooch. We make shoes from plants."
    hits = cc.check(tekst, cc.parse_blok(BODY), policy_id="COPYCHECK-001")
    assert len(hits) == 1
    assert hits[0]["citaat"] == "Hey friend, welcome to Nooch."
    assert "friend" in hits[0]["regel"] and hits[0]["policy"] == "COPYCHECK-001"


def test_een_schone_tekst_levert_niets():
    """De andere kant: een checker die altijd iets vindt, wordt genegeerd."""
    tekst = "We make shoes from plants. The sole returns to the soil when you are done with it."
    assert cc.check(tekst, cc.parse_blok(BODY)) == []


def test_een_claim_zonder_bron_wordt_aangewezen():
    hits = cc.check("Our soles are biodegradable.", cc.parse_blok(BODY))
    assert hits and "bron nodig" in hits[0]["regel"]


def test_een_percentage_zonder_bron_wordt_aangewezen():
    hits = cc.check("We cut emissions by 40% last year.", cc.parse_blok(BODY))
    assert any("percentage zonder bron" in h["regel"] for h in hits)
    schoon = cc.check("We cut emissions by 40% according to the TRAID source.", cc.parse_blok(BODY))
    assert not [h for h in schoon if "percentage" in h["regel"]]


def test_een_limiet_telt_en_zegt_hoeveel_eraf_moet():
    hits = cc.check("Wow! Amazing! Great!", cc.parse_blok(BODY))
    uitroep = [h for h in hits if "uitroepteken" in h["regel"]][0]
    assert "3 gevonden" in uitroep["regel"] and "2 weg" in uitroep["suggestie"]


def test_de_checker_verandert_de_tekst_niet():
    """Aanwijzen, niet herschrijven. De bevinding draagt een SUGGESTIE; de tekst blijft van Nina."""
    tekst = "Hey friend!"
    hits = cc.check(tekst, cc.parse_blok(BODY))
    assert all("suggestie" in h for h in hits)
    assert tekst == "Hey friend!"


def test_een_policy_met_blok_past_binnen_de_cap():
    """STILLE AFKAPPING VAN MIJN EIGEN HAND. COPYCHECK-001 telt 3765 tekens prosa; de policy-cap
    stond op 4000. Het structuurblok (445 tekens) paste niet, en de store deed wat hij belooft:
    afkappen. Er stond een half codeblok in de policy, met een niet-gesloten fence — en `parse_blok`
    vond dus niets, dus de checker had stilletjes NUL regels.

    Sinds een policy zijn eigen machine-leesbare regels draagt naast de prosa, is hij geen briefje
    meer maar een document met twee lezers. 4000 was de maat van het oude ding."""
    from nooch_village.attachments import body_cap
    assert body_cap("policy") >= 3765 + 445 * 3, "geen ruimte voor prosa plus blok"
    assert body_cap("policy") < body_cap("note")


def test_de_schrijfroute_weigert_liever_dan_af_te_kappen():
    """De store kapt af als BACKSTOP; de route hoort te weigeren. Mijn eigen script omzeilde die
    route en liep dus recht in de backstop — de guard bestond al, ik gebruikte hem niet."""
    from nooch_village.cockpit2 import _body_te_lang
    from nooch_village.attachments import body_cap
    assert _body_te_lang("x" * (body_cap("policy") + 1), "policy").startswith("✗")
    assert _body_te_lang("x" * 100, "policy") == ""
