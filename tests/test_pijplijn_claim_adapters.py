"""Adapters 4 en 5: de twee claim-bronnen, en waarom ze niet konden verzamelen.

DE ANDERE DRIE ADAPTERS LEZEN UIT OPGESLAGEN DATA (de radar, de Kroniek). Deze twee werken op
PAGINATEKST, en die bestaat alleen tijdens een site-scan. Tot 20 september 2026 gingen hun
bevindingen rechtstreeks van de scan naar `claims_board.zet_op_bord` → een project op een rol, en
daarna waren ze weg: de weekmarker droeg alleen TELLINGEN (`nieuw`, `gescand`, `gedekt`).

Haal je `zet_op_bord` uit de puls (stap 3), dan verdampen die signalen tussen de scan en de memo.
Daarom bewaart `markeer_week` ze nu — in de marker die hij al had, want die is er volgens zijn eigen
docstring voor "wat hij vond, zonder een tweede opslagplek". Geen nieuwe store.

DE TWEE ZIJN ELKAARS SPIEGELBEELD, en dat is de hele aanleiding van deze operatie:

    claims_modelpas   VOEGT TOE wat de regex miste (recall)   → `claim_model`
    claims_context    HAALT WEG wat geen claim is (precisie)  → `claim_regex`

Ze liepen op gescheiden paden: de recall-pas draaide in de dagpuls en maakte projecten aan, de
contextlaag draaide alleen op het scherm. Het ONGEFILTERDE pad was dus het pad dat autonoom werk
aanmaakte. Hier komen ze voor het eerst achter elkaar te staan.
"""
from __future__ import annotations

import time

import pytest

from nooch_village import claims_context as cc, claims_modelpas as mp
from nooch_village.skills_impl.claims_site_scan import (BEVINDINGEN_CAP, laatste_run, markeer_week)


def _regex_bev(term="carbon neutral", pagina="FAQ"):
    return {"term": term, "gevonden": [f"we are {term} since 2020"], "stoplicht": "red",
            "pagina": pagina, "url": f"https://nooch.earth/{pagina.lower()}",
            # De zinnen eromheen, zoals de scan ze meegeeft: zonder context kan de contextlaag
            # niet oordelen of de term wordt GEDAAN of alleen BESPROKEN.
            "contexten": [f"We are {term} since 2020, audited by SGS."]}


def _model_bev(zin="onze zolen verdwijnen gewoon weer in de grond"):
    return {"term": zin[:120], "gevonden": [zin], "stoplicht": "orange",
            "pagina": "FAQ", "url": "https://nooch.earth/faq", "herkomst": mp.HERKOMST}


def _geen_filter(prompt, **kw):
    """Een contextlaag die niets wegweegt — dan blijft elke regex-bevinding staan."""
    return '{"oordelen": []}'


# ── de marker draagt de bevindingen nu ──────────────────────────────────────

def test_de_marker_bewaart_de_bevindingen(tmp_path):
    d = str(tmp_path)
    markeer_week(d, "2026-W38", {"bevindingen": [_regex_bev(), _model_bev()], "nieuw": 2})
    m = laatste_run(d)
    assert len(m["bevindingen"]) == 2 and m["bevindingen_totaal"] == 2
    assert m["last_week"] == "2026-W38"


def test_de_cap_kapt_af_maar_liegt_niet_over_het_aantal(tmp_path):
    """EEN AFGEKAPTE WEEK MOET ZICHTBAAR AFGEKAPT ZIJN. Zonder `bevindingen_totaal` leest de memo
    veertig als "dit was alles", en dan is een uitschieter — precies het geval waarvoor de cap
    bestaat — onzichtbaar geworden."""
    d = str(tmp_path)
    veel = [_regex_bev(term=f"term {i}") for i in range(BEVINDINGEN_CAP + 15)]
    markeer_week(d, "2026-W38", {"bevindingen": veel})
    m = laatste_run(d)
    assert len(m["bevindingen"]) == BEVINDINGEN_CAP
    assert m["bevindingen_totaal"] == BEVINDINGEN_CAP + 15


def test_de_marker_bewaart_geen_paginatekst(tmp_path):
    """De marker is geen kopie van de site. Genoeg om de bevinding te lezen én terug te vinden,
    en niet meer — anders groeit hij mee met elke pagina die de scan aanraakt."""
    d = str(tmp_path)
    lang = "x" * 5000
    markeer_week(d, "2026-W38", {"bevindingen": [{**_regex_bev(), "tekst": lang,
                                                  "gevonden": [lang, lang, lang]}]})
    b = laatste_run(d)["bevindingen"][0]
    assert "tekst" not in b
    assert len(b["gevonden"]) <= 2 and all(len(g) <= 300 for g in b["gevonden"])


# ── adapter 4: de modelvondsten ─────────────────────────────────────────────

def test_modelpas_levert_alleen_de_modelvondsten(tmp_path):
    """Wat de regex vond is geen vondst van deze bron: die heeft zijn eigen weg. Hier staat wat de
    recall-pas TOEVOEGDE — precies het deel dat tot vandaag ongefilterd een project werd."""
    d = str(tmp_path)
    markeer_week(d, "2026-W38", {"bevindingen": [_regex_bev(), _model_bev()]})
    uit = mp.verzamel(d)
    assert len(uit) == 1
    assert uit[0].bron == "claim_model"
    assert "zolen verdwijnen" in uit[0].tekst
    assert uit[0].vindplaats == "https://nooch.earth/faq"
    assert uit[0].extra["week"] == "2026-W38"


def test_modelpas_meldt_dat_de_week_is_afgekapt(tmp_path):
    d = str(tmp_path)
    markeer_week(d, "2026-W38",
                 {"bevindingen": [_model_bev(f"claim nummer {i} over afbreekbaarheid")
                                  for i in range(BEVINDINGEN_CAP + 5)]})
    uit = mp.verzamel(d)
    assert len(uit) == BEVINDINGEN_CAP
    assert all(s.extra["afgekapt"] for s in uit)


def test_modelpas_respecteert_sinds(tmp_path):
    d = str(tmp_path)
    markeer_week(d, "2026-W38", {"bevindingen": [_model_bev()]})
    assert mp.verzamel(d, sinds=time.time() + 3600) == []
    assert len(mp.verzamel(d, sinds=0)) == 1


def test_zonder_scan_geen_signalen(tmp_path):
    """Fail-soft: een dorp waar de scan nooit draaide heeft geen marker. Dat is geen fout."""
    assert mp.verzamel(str(tmp_path)) == []
    assert cc.verzamel(str(tmp_path), reason_fn=_geen_filter) == []


# ── adapter 5: de regex-bevindingen, door de contextlaag ────────────────────

def test_context_levert_alleen_de_regex_bevindingen(tmp_path):
    d = str(tmp_path)
    markeer_week(d, "2026-W38", {"bevindingen": [_regex_bev(), _model_bev()]})
    uit = cc.verzamel(d, reason_fn=_geen_filter)
    assert len(uit) == 1
    assert uit[0].bron == "claim_regex"
    assert "carbon neutral" in uit[0].tekst


def test_context_weegt_weg_wat_geen_claim_is(tmp_path):
    """DE KERN VAN DEZE ADAPTER. Een tekst die de term juist ONTMASKERT is geen claim. Tot vandaag
    draaide dit filter alleen op het scherm, terwijl het pad dat projecten aanmaakte ongefilterd
    was — dat is de reden dat deze pijplijn bestaat."""
    d = str(tmp_path)
    markeer_week(d, "2026-W38", {"bevindingen": [_regex_bev(term="carbon neutral"),
                                                 _regex_bev(term="climate positive")]})

    def _weeg_een_weg(prompt, **kw):
        # `nr` is de INDEX in de kandidatenlijst, niet de term — zelfde contract als `_schift`.
        # Een oordeel dat niet naar een kandidaat verwijst, hoort nergens bij.
        return '{"oordelen": [{"nr": 0, "oordeel": "geen-claim", "reden": "ontmaskering"}]}'

    uit = cc.verzamel(d, reason_fn=_weeg_een_weg)
    termen = [s.herkomst for s in uit]
    assert "carbon neutral" not in termen, termen
    assert "climate positive" in termen
    assert uit[0].extra["weggewogen"] == 1


def test_context_zonder_regex_bevindingen_vraagt_het_model_niet(tmp_path):
    """Alleen modelvondsten in de week: er is niets te filteren, en een lege modelaanroep kost
    krediet zonder iets op te leveren."""
    d = str(tmp_path)
    markeer_week(d, "2026-W38", {"bevindingen": [_model_bev()]})

    def _nooit(prompt, **kw):
        raise AssertionError("het model werd aangeroepen zonder regex-bevindingen")

    assert cc.verzamel(d, reason_fn=_nooit) == []


# ── de drempels ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("module,verwacht", [(mp, "recall"), (cc, "precisie")])
def test_de_drempels_staan_op_de_bron(module, verwacht):
    """De twee zijn elkaars spiegelbeeld, en hun drempels horen dus tegengesteld te zijn. Zou een
    van beide schuiven, dan wordt de een een slechtere vinder of de ander een slechter filter."""
    from nooch_village.weekmemo import DREMPELS
    assert module.DREMPEL == verwacht and module.DREMPEL in DREMPELS
