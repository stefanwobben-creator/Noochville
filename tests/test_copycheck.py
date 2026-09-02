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


def test_de_backstop_schreeuwt_als_hij_afgaat(tmp_path, caplog):
    """EEN STILLE BACKSTOP VERBERGT DE OMZEILING DIE HIJ ZOU MOETEN VANGEN.

    De cap-comment zei "zodat niemand stil tekst verliest", en toen verloor de backstop stil tekst:
    mijn schrijfroute omzeilde de weigering, liep hier binnen, en er bleef een half codeblok in
    COPYCHECK-001 achter. Niemand merkte het tot iemand de OPGESLAGEN tekst las.

    Hij blijft afkappen — een halve opslag is beter dan een crash midden in een schrijfactie — maar
    hij laat het weten, mét de plek en de verloren staart, zodat de route te vinden is."""
    import logging

    from nooch_village.attachments import AttachmentStore, body_cap
    store = AttachmentStore(str(tmp_path / "a.json"))
    with caplog.at_level(logging.WARNING):
        a = store.add("rol", "policy", body="x" * (body_cap("policy") + 500))
    assert len(a.body) == body_cap("policy")
    gilt = [r for r in caplog.records if "AFKAPPING" in r.message]
    assert gilt, "de backstop kapte stil af"
    assert "_body_te_lang" in gilt[0].message, "de melding wijst niet naar de route die had moeten weigeren"


def test_binnen_de_cap_geen_geschreeuw(tmp_path, caplog):
    """Een alarm dat altijd afgaat is geen alarm."""
    import logging

    from nooch_village.attachments import AttachmentStore
    store = AttachmentStore(str(tmp_path / "b.json"))
    with caplog.at_level(logging.WARNING):
        store.add("rol", "policy", body="x" * 100)
    assert not [r for r in caplog.records if "AFKAPPING" in r.message]


# ── De grond van de checker ────────────────────────────────────────────────

def test_de_checker_heeft_zijn_eigen_expliciete_set():
    """DE GROND MAG NIET STIL VERANDEREN. De generator componeert via `copy_stack`: erfenis plus
    inclusies, met lagen die iemand in de UI aan of uit kan zetten. Dat is juist voor SCHRIJVEN.
    Maar een checker die gisteren op vier policies toetste en vandaag op drie, zonder dat iemand dat
    besloot, geeft een groen scherm dat niets betekent.

    Twee tools, twee gronden. De brand- en design-policies vallen bewust buiten: die gaan over het
    visuele medium, niet over tekst."""
    assert cc.COPY_POLICIES == ("COPYCHECK-001", "POSITIONSTAT-001", "TONEOFVOICE-001",
                                "STANCE-001")
    for merk in ("BRANDPOSITIO-001", "DESIGNSYSTEM-001"):
        assert merk not in cc.COPY_POLICIES


def test_de_grond_hangt_niet_aan_de_generator():
    """Geen zijeffect-koppeling: de checker leest zijn eigen constante, niet wat de generator
    toevallig aan heeft staan."""
    import inspect
    import re as _re
    # De CODE, niet het commentaar: dat legt juist uit waaróm we hem niet gebruiken, en die uitleg
    # moet mogen blijven staan.
    bron = inspect.getsource(cc)
    kaal = _re.sub(r"#[^\n]*", "", bron)
    assert "copy_stack" not in kaal.split('"""')[-1]
    assert "componeer(" not in kaal
    assert "from nooch_village.copy_stack" not in kaal


class _Att:
    def __init__(self, bodies):
        self._b = bodies

    def get(self, pid):
        import types
        return types.SimpleNamespace(body=self._b[pid]) if pid in self._b else None


def test_alleen_policies_met_een_blok_dragen_regels():
    """Een policy zonder blok levert niets — geen valse zekerheid. Levert extractie geen checkbare
    tekstregel op, dan blijft hij leeg, en dat is een eerlijke uitkomst en geen gat."""
    att = _Att({"COPYCHECK-001": BODY, "POSITIONSTAT-001": "alleen prosa, geen blok"})
    ids = [pid for pid, _ in cc.regels_uit(att)]
    assert ids == ["COPYCHECK-001"]


def test_elke_bevinding_noemt_zijn_bronpolicy():
    """Bij vier gronden moet je kunnen zien wélke regel je overtreedt — anders is 'het mag niet'
    een bewering zonder adres."""
    tweede = BODY.replace("verboden: friend", "verboden: eco-warrior").replace(
        "Never write: friend,", "Never write: eco-warrior,")
    att = _Att({"COPYCHECK-001": BODY, "TONEOFVOICE-001": tweede})
    hits = cc.check_alles("Hey friend, you eco-warrior!", att)
    bronnen = {h["policy"] for h in hits}
    assert bronnen == {"COPYCHECK-001", "TONEOFVOICE-001"}, bronnen


def test_de_checker_dedupliceert_niet_over_policies():
    """DRIFT IS HEDEN, EN DE CHECKER VERBERGT HEM NIET. `biodegradable` staat in twee copy-policies;
    beide flaggen. Dedupliceren zou dat verstoppen — dan lijkt het één regel terwijl het er twee zijn,
    en dan merkt niemand dat ze uit elkaar kunnen lopen. De opschoning is een policy-vraag, niet iets
    wat de checker cosmetisch oplost."""
    tweede = BODY.replace("bron_vereist: biodegradable", "bron_vereist: biodegradable")
    att = _Att({"COPYCHECK-001": BODY, "POSITIONSTAT-001": tweede})
    hits = cc.check_alles("Our soles are biodegradable.", att)
    bronnen = sorted(h["policy"] for h in hits if "biodegradable" in h["regel"])
    assert bronnen == ["COPYCHECK-001", "POSITIONSTAT-001"], bronnen


def test_laag_1_blijft_letterlijk():
    """LAAG 1 FUZZY MAKEN ERODEERT DE SCHEIDING. De policy verbiedt "lasts longer than leather";
    echte copy schrijft "they last longer than leather". Laag 1 flagt dat NIET, en dat is de grens —
    een vergelijkende claim heeft oneindig veel bewoordingen en hoort bij het oordeel van laag 2.

    Zou laag 1 gaan stemmen, dan is de term in het blok niet meer letterlijk in de prosa terug te
    vinden, en verdwijnt de grond waarop hij mag bestaan."""
    blok = {"verboden": ["lasts longer than leather"], "bron_vereist": [], "limieten": {}}
    assert cc.check("They last longer than leather.", blok) == []
    assert cc.check("It lasts longer than leather.", blok)


def test_een_term_mag_zelf_een_komma_bevatten():
    """GEVONDEN IN DE DROGE RUN OP TONEOFVOICE-001. `At Nooch, we believe` brak in tweeën, en
    `At Nooch` alleen flagt élke zin die zo begint — veel te breed, en niet meer wat de policy zegt.

    Een scheidingsteken dat ook in de data voorkomt heeft een ontsnapping nodig; anders verandert de
    betekenis stilletjes bij het LEZEN, zonder dat iemand iets fout schreef."""
    body = ('prosa: At Nooch, we believe en Our mission is to\n\n'
            '```check\nverboden: "At Nooch, we believe", Our mission is to\n```\n')
    blok = cc.parse_blok(body)
    assert blok["verboden"] == ["At Nooch, we believe", "Our mission is to"]
    assert cc.koppeltest(body) == []
    assert cc.check("At Nooch we make shoes.", blok) == [], "te breed: 'At Nooch' alleen"
    assert cc.check("At Nooch, we believe in plants.", blok)
