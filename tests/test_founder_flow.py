"""Founder Flow — de graduele-autonomie-trainingslus.

Wat hier bewaakt wordt, is niet "de knoppen doen iets" maar de twee ontwerpregels waar de hele
lus op staat of valt:

  1. **Blind-eerst.** Op A/B (en in de auditsteekproef op C/D) staat het AI-voorstel NIET in de
     HTML. Zodra het lekt, meet de lus de echo van de AI in het menselijke oordeel en is elk
     label waardeloos. Daarom toetsen we op afwezigheid in de gerenderde pagina, niet op een
     vlaggetje in een dict.
  2. **De meting telt alleen schone labels.** Een oordeel dat ná een zichtbaar voorstel viel, mag
     de promotiepoort niet openen. De poort beslist bovendien op de Wilson-ondergrens, zodat een
     handvol toevallige treffers geen trede oplevert.
  3. **Een trede blijft precies zolang staan als het bewijs hem zou toekennen.** De demotie-poort
     is de letterlijke negatie van de promotie-poort. Eén test bevriest de valkuil die daaronder
     ligt: met een lágere drempel maar dezelfde ondergrens-toets degradeert een FOUTLOZE reeks,
     omdat de ondergrens van 21/21 goed onder een lat van 85% ligt.
"""
from __future__ import annotations

import time
import urllib.parse

import pytest

from nooch_village import cockpit2
from nooch_village import founder_flow as ff
from nooch_village import founder_taken
from nooch_village.views.founder_flow import render_founder_flow

GUEST = "guest"


@pytest.fixture
def dd(tmp_path):
    d = str(tmp_path / "poc")
    cockpit2._bootstrap(d)
    return d


def _st(dd):
    return cockpit2._Stores(dd)


def _niveaus(dd):
    import os
    return ff.NiveauStore(os.path.join(dd, ff.NIVEAU_BESTAND))


def _radar_signaal(st, content="hemp sneaker composteerbaar", rationale="materiaal"):
    return st.radar.add(role="harry_hemp", feed="Material Innovation", kind="signal",
                        content=content, rationale=rationale)


def _labels(taak, paren, *, ai_getoond=False, correctie=False, niveau="A"):
    """Bouw n labels met (mens, ai)-paren — de kortste weg naar een meetbare reeks."""
    return [{"taak": taak, "item": f"i{n}", "mens": m, "ai": a, "ai_getoond": ai_getoond,
             "correctie": correctie, "niveau": niveau, "audit": False, "door": "t",
             "seconden": 6.0, "ts": 1_000_000 + n}
            for n, (m, a) in enumerate(paren)]


# ── 1. De labels zelf ────────────────────────────────────────────────────────

def test_label_roundtrip_en_validatie(dd):
    assert ff.leg_vast(dd, taak=ff.RADAR, item="a1", mens="keep", ai="dismiss", niveau="B")
    # Onbekende taak en onbekend oordeel worden geweigerd: de meting mag nooit op typefouten tellen.
    assert ff.leg_vast(dd, taak="verzonnen", item="a2", mens="keep") is None
    assert ff.leg_vast(dd, taak=ff.RADAR, item="a3", mens="misschien") is None
    assert ff.leg_vast(dd, taak=ff.RADAR, item="", mens="keep") is None
    # Een onbekend AI-voorstel wordt stil tot "geen voorstel" — het label blijft, de meting niet.
    rij = ff.leg_vast(dd, taak=ff.RADAR, item="a4", mens="keep", ai="onzin")
    assert rij is not None and rij["ai"] is None

    rijen = ff.alle(dd)
    assert [r["item"] for r in rijen] == ["a1", "a4"]
    assert rijen[0]["mens"] == "keep" and rijen[0]["ai"] == "dismiss"


def test_label_is_append_only(dd):
    ff.leg_vast(dd, taak=ff.RADAR, item="a1", mens="keep", ai="keep")
    ff.leg_vast(dd, taak=ff.RADAR, item="a1", mens="dismiss", ai="keep", correctie=True)
    rijen = ff.alle(dd)
    assert len(rijen) == 2                                     # niets overschreven
    assert ff.laatste_per_item(rijen, ff.RADAR)["a1"]["mens"] == "dismiss"


def test_ai_regel_draagt_geen_mensoordeel(dd):
    """Een item dat de AI zelf afhandelde staat in dezelfde stroom, maar is geen menselijk label."""
    ff.leg_vast(dd, taak=ff.RADAR, item="a1", mens=None, ai="dismiss", niveau="D", door="ai")
    rij = ff.alle(dd)[0]
    assert rij["mens"] is None and rij["door"] == "ai"
    assert ff.held_out(ff.alle(dd), ff.RADAR) == []             # telt niet mee in de meting


# ── 2. Blind-eerst ───────────────────────────────────────────────────────────

def test_blind_eerst_regel():
    for niveau in ("A", "B"):
        assert ff.toont_voorstel_vooraf(niveau, audit=False) is False
        assert ff.toont_voorstel_vooraf(niveau, audit=True) is False
    for niveau in ("C", "D"):
        assert ff.toont_voorstel_vooraf(niveau, audit=False) is True
        assert ff.toont_voorstel_vooraf(niveau, audit=True) is False   # audit blijft blind


def test_voorstel_staat_niet_in_de_html_op_a_en_b(dd):
    """De harde toets: op A/B mag het woord van het voorstel nergens in de pagina staan."""
    st = _st(dd)
    _radar_signaal(st, content="hemp sneaker composteerbaar")
    for niveau in ("A", "B"):
        _niveaus(dd).zet(ff.RADAR, niveau, door="t", reden="test")
        pagina = render_founder_flow(_st(dd), dd, csrf_token="tok")
        assert "hemp sneaker composteerbaar" in pagina          # het item staat er wel
        assert "The AI proposes" not in pagina                  # het voorstel niet
        assert "You decide first" in pagina


def test_voorstel_staat_wel_in_de_html_op_c(dd, monkeypatch):
    st = _st(dd)
    _radar_signaal(st, content="hemp sneaker composteerbaar")
    # Auditsteekproef uit, zodat we zeker het niet-blinde pad zien.
    monkeypatch.setattr(ff, "instellingen", lambda d, t="": dict(ff._DEFAULTS[t], audit_pct=0)
                        if t else {k: dict(v, audit_pct=0) for k, v in ff._DEFAULTS.items()})
    _niveaus(dd).zet(ff.RADAR, "C", door="t", reden="test")
    pagina = render_founder_flow(_st(dd), dd, csrf_token="tok")
    assert "The AI proposes" in pagina


def test_auditsteekproef_blijft_blind_op_d(dd, monkeypatch):
    st = _st(dd)
    _radar_signaal(st, content="hemp sneaker composteerbaar")
    # Alles in de steekproef → ook op D moet de pagina blind blijven.
    monkeypatch.setattr(ff, "in_auditsteekproef", lambda taak, item, pct: True)
    _niveaus(dd).zet(ff.RADAR, "D", door="t", reden="test")
    pagina = render_founder_flow(_st(dd), dd, csrf_token="tok")
    assert "audit sample" in pagina
    assert "The AI proposes" not in pagina


def test_onthulling_komt_pas_na_de_beslissing(dd):
    """De tegenhanger van blind-eerst: het voorstel is er wél, maar pas ná de klik.

    Zonder deze onthulling leert de founder niets van de vergelijking en is blind-eerst alleen
    maar een handicap. De 'neem het antwoord van de AI' -knop is de correctie op één klik."""
    st = _st(dd)
    rid = _radar_signaal(st, content="hemp sneaker composteerbaar")
    nxt, _ = _beslis(dd, ff.RADAR, rid, "dismiss")
    onthuld = urllib.parse.unquote(
        urllib.parse.parse_qs(nxt.split("?", 1)[1])["onthuld"][0])
    assert onthuld.startswith(f"{ff.RADAR}|{rid}|dismiss|keep|")

    pagina = render_founder_flow(_st(dd), dd, csrf_token="tok", onthuld=onthuld)
    assert "You: dismiss · AI: keep" in pagina
    assert "disagreed" in pagina
    # Op A beslist de mens en niemand anders: geen overname-knop.
    assert "take the AI&#x27;s answer instead" not in pagina

    _niveaus(dd).zet(ff.RADAR, "B", door="t", reden="test")
    op_b = render_founder_flow(_st(dd), dd, csrf_token="tok",
                               onthuld=f"{ff.RADAR}|{rid}|dismiss|keep|B")
    assert "answer instead" in op_b and "ff_beslis" in op_b


def test_onthulling_bij_eensgezindheid_en_bij_rommel(dd):
    eens = render_founder_flow(_st(dd), dd, csrf_token="tok",
                               onthuld=f"{ff.RADAR}|x|keep|keep|B")
    assert "agreed" in eens and "answer instead" not in eens
    # Zonder voorstel is er niets te vergelijken — dat wordt gezegd, niet verzwegen.
    geen = render_founder_flow(_st(dd), dd, csrf_token="tok",
                               onthuld=f"{ff.RADAR}|x|keep||B")
    assert "no proposal for this item" in geen
    # Onleesbare of gemanipuleerde parameter → geen kaart, geen crash.
    for rommel in ("", "rommel", f"{ff.RADAR}|x|verzonnen|keep|B", "verzonnen|x|keep|keep|B"):
        pagina = render_founder_flow(_st(dd), dd, csrf_token="tok", onthuld=rommel)
        assert "You:" not in pagina


def test_auditsteekproef_is_deterministisch():
    """Een item mag niet van steekproef wisselen tussen twee page-loads — anders lekt het voorstel."""
    keuzes = [ff.in_auditsteekproef(ff.RADAR, f"item{n}", 25) for n in range(200)]
    assert keuzes == [ff.in_auditsteekproef(ff.RADAR, f"item{n}", 25) for n in range(200)]
    assert 0 < sum(keuzes) < 200                                # hij selecteert écht een deel
    assert ff.in_auditsteekproef(ff.RADAR, "item1", 0) is False  # 0% = niemand


# ── 3. De meting ─────────────────────────────────────────────────────────────

def test_held_out_negeert_besmette_labels():
    schoon = _labels(ff.RADAR, [("keep", "keep")] * 3)
    besmet = _labels(ff.RADAR, [("keep", "keep")] * 3, ai_getoond=True)
    gecorrigeerd = _labels(ff.RADAR, [("keep", "keep")] * 3, correctie=True)
    zonder_ai = [{**r, "ai": None} for r in _labels(ff.RADAR, [("keep", "keep")] * 3)]
    alles = schoon + besmet + gecorrigeerd + zonder_ai
    assert len(ff.held_out(alles, ff.RADAR)) == 3


def test_overeenstemming_en_wilson_ondergrens():
    labels = _labels(ff.RADAR, [("keep", "keep")] * 27 + [("keep", "dismiss")] * 3)
    meting = ff.overeenstemming(labels, ff.RADAR, venster=60)
    assert meting["n"] == 30 and meting["akkoord"] == 27
    assert meting["ratio"] == pytest.approx(0.9)
    # De ondergrens ligt merkbaar onder het punt — dát is de reden om erop te poorten.
    assert meting["lo"] < meting["ratio"] < meting["hi"]
    assert 0.70 < meting["lo"] < 0.85


def test_venster_houdt_alleen_de_recentste_labels():
    labels = (_labels(ff.RADAR, [("keep", "dismiss")] * 40)          # oud en fout
              + [{**r, "ts": r["ts"] + 10_000} for r in _labels(ff.RADAR, [("keep", "keep")] * 40)])
    assert ff.overeenstemming(labels, ff.RADAR, venster=40)["ratio"] == pytest.approx(1.0)


def test_promotie_poort_eist_genoeg_voorbeelden_en_de_lat():
    cfg = dict(ff._DEFAULTS[ff.RADAR])
    # Te weinig voorbeelden, ook al is alles goed.
    kan, reden = ff.promoveerbaar(_labels(ff.RADAR, [("keep", "keep")] * 5), ff.RADAR, "A", cfg)
    assert not kan and "blind examples" in reden
    # Genoeg voorbeelden, maar de ondergrens haalt de lat niet (punt 90%, ondergrens ~74%).
    labels = _labels(ff.RADAR, [("keep", "keep")] * 27 + [("keep", "dismiss")] * 3)
    kan, reden = ff.promoveerbaar(labels, ff.RADAR, "A", cfg)
    assert not kan and "below the bar" in reden
    # Ruim boven de lat over een grotere reeks → wel.
    kan, reden = ff.promoveerbaar(_labels(ff.RADAR, [("keep", "keep")] * 40), ff.RADAR, "A", cfg)
    assert kan and "lower bound" in reden
    # D is het eindpunt.
    assert ff.promoveerbaar(_labels(ff.RADAR, [("keep", "keep")] * 40), ff.RADAR, "D", cfg)[0] is False


def test_besmette_labels_openen_de_poort_niet():
    """Honderd instemmingen ná een zichtbaar voorstel zijn geen bewijs — de poort blijft dicht."""
    cfg = dict(ff._DEFAULTS[ff.RADAR])
    labels = _labels(ff.RADAR, [("keep", "keep")] * 100, ai_getoond=True)
    kan, reden = ff.promoveerbaar(labels, ff.RADAR, "A", cfg)
    assert not kan and "0/30 blind examples" in reden


def test_drift_wordt_zichtbaar_op_c_en_d():
    cfg = dict(ff._DEFAULTS[ff.RADAR])
    slecht = _labels(ff.RADAR, [("keep", "dismiss")] * 20)
    assert ff.drift(slecht, ff.RADAR, "A", cfg) == ""            # op A zegt drift niets
    assert "drift" in ff.drift(slecht, ff.RADAR, "C", cfg)
    assert "drift" in ff.drift(slecht, ff.RADAR, "D", cfg)
    goed = _labels(ff.RADAR, [("keep", "keep")] * 40)
    assert ff.drift(goed, ff.RADAR, "D", cfg) == ""


# ── 3b. Automatische demotie — de spiegel van de promotiepoort ───────────────

def test_demotiepoort_is_de_letterlijke_negatie_van_de_promotiepoort():
    """Een trede blijft precies zolang staan als het bewijs hem zou toekennen. Dezelfde lat,
    dezelfde min_n, dezelfde ondergrens — anders krijg je twee onverenigbare oordelen over één
    reeks labels."""
    cfg = dict(ff._DEFAULTS[ff.RADAR])
    for paren in ([("keep", "keep")] * 40,                       # ruim boven
                  [("keep", "keep")] * 27 + [("keep", "dismiss")] * 3,   # 90%, ondergrens eronder
                  [("keep", "dismiss")] * 30):                   # ver eronder
        labels = _labels(ff.RADAR, paren)
        promoveert = ff.promoveerbaar(labels, ff.RADAR, "C", cfg)[0]
        demoveert = ff.demoveerbaar(labels, ff.RADAR, "D", cfg)[0]
        assert promoveert != demoveert, paren[:1]


def test_foutloze_reeks_degradeert_nooit():
    """De val in de directe formulering ('ondergrens onder de lat' bij een lagere drempel): de
    Wilson-ondergrens van 21/21 goed is 84,5% en dus onder een lat van 85%. Een taak zou dan
    terugvallen op perfect werk, puur omdat de steekproef klein is. Deze test bevriest dat dit
    niet kan gebeuren — bij géén enkele steekproefgrootte."""
    cfg = dict(ff._DEFAULTS[ff.RADAR])
    for n in range(1, 80):
        labels = _labels(ff.RADAR, [("keep", "keep")] * n)
        moet, reden = ff.demoveerbaar(labels, ff.RADAR, "D", cfg)
        assert not moet, f"{n}/{n} goed degradeerde: {reden}"


def test_demotie_eist_hetzelfde_bewijs_als_promotie():
    cfg = dict(ff._DEFAULTS[ff.RADAR])
    min_n = int(cfg["min_n"])
    # Te weinig blinde audit-oordelen → geen intrekking, ook niet als alles fout is.
    weinig = _labels(ff.RADAR, [("keep", "dismiss")] * (min_n - 1))
    moet, reden = ff.demoveerbaar(weinig, ff.RADAR, "D", cfg)
    assert not moet and "not enough to withdraw the level" in reden
    # Genoeg en onder de lat → terug.
    slecht = _labels(ff.RADAR, [("keep", "dismiss")] * min_n)
    moet, reden = ff.demoveerbaar(slecht, ff.RADAR, "D", cfg)
    assert moet and "would no longer be granted" in reden
    # Op A/B valt er geen autonomie in te trekken: de poort doet daar niets.
    for niveau in ("A", "B"):
        assert ff.demoveerbaar(slecht, ff.RADAR, niveau, cfg)[0] is False


def test_waarschuwing_gaat_eerder_af_dan_de_poort():
    """De waarschuwing dekt het gat dat de bewijs-eis openlaat: hij mag al aan op de halve
    drempel, want hij verandert niets — hij laat de founder zelf ingrijpen."""
    cfg = dict(ff._DEFAULTS[ff.RADAR])
    half = ff.drift_drempel(cfg)
    slecht = _labels(ff.RADAR, [("keep", "dismiss")] * half)
    assert ff.demoveerbaar(slecht, ff.RADAR, "D", cfg)[0] is False    # poort nog dicht
    melding = ff.drift(slecht, ff.RADAR, "D", cfg)                    # waarschuwing wel aan
    assert "drift" in melding and "one click" in melding
    # Te weinig, of gewoon goed → stil.
    assert ff.drift(_labels(ff.RADAR, [("keep", "dismiss")] * 3), ff.RADAR, "D", cfg) == ""
    assert ff.drift(_labels(ff.RADAR, [("keep", "keep")] * 40), ff.RADAR, "D", cfg) == ""


def test_besmette_labels_veroorzaken_geen_demotie():
    """Een correctie ná een zichtbaar voorstel is geen drift-bewijs — anders zou elke correctie
    op C (waar het voorstel juist zichtbaar hoort te zijn) het niveau omlaag trekken."""
    cfg = dict(ff._DEFAULTS[ff.RADAR])
    besmet = _labels(ff.RADAR, [("keep", "dismiss")] * 40, ai_getoond=True)
    assert ff.demoveerbaar(besmet, ff.RADAR, "D", cfg)[0] is False


def test_demotie_verlaagt_een_trede_en_legt_de_reden_vast(dd):
    niveaus = _niveaus(dd)
    niveaus.zet(ff.RADAR, "D", door="founder", reden="meting groen")
    for n in range(30):
        ff.leg_vast(dd, taak=ff.RADAR, item=f"m{n}", mens="keep", ai="dismiss", niveau="D")
    melding = ff.pas_demotie_toe(niveaus, ff.alle(dd), ff.RADAR, ff.instellingen(dd, ff.RADAR))
    assert "stepped back to level C" in melding
    assert _niveaus(dd).niveau(ff.RADAR) == "C"
    laatste = _niveaus(dd).historie(ff.RADAR)[-1]
    assert laatste["door"] == "auto" and laatste["reden"].startswith("auto-demotion")


def test_demotie_valt_niet_door_op_stil_bewijs(dd):
    """Na een terugval telt alleen NIEUW bewijs. Zonder die grens trapt één slechte reeks de
    taak in opeenvolgende klikken van D helemaal naar beneden."""
    niveaus = _niveaus(dd)
    niveaus.zet(ff.RADAR, "D", door="founder", reden="meting groen")
    for n in range(30):
        ff.leg_vast(dd, taak=ff.RADAR, item=f"m{n}", mens="keep", ai="dismiss", niveau="D")
    assert ff.pas_demotie_toe(niveaus, ff.alle(dd), ff.RADAR, ff.instellingen(dd, ff.RADAR))
    assert niveaus.niveau(ff.RADAR) == "C"
    # Tweede aanroep op exact dezelfde labels: die zijn allemaal van vóór de wissel.
    assert ff.pas_demotie_toe(niveaus, ff.alle(dd), ff.RADAR, ff.instellingen(dd, ff.RADAR)) == ""
    assert niveaus.niveau(ff.RADAR) == "C"


def test_demotie_stopt_bij_b(dd):
    """Onder B valt er niets in te trekken — daar stelt de AI alleen voor. A is een keuze."""
    niveaus = _niveaus(dd)
    niveaus.zet(ff.RADAR, "C", door="founder", reden="test")
    for n in range(30):
        ff.leg_vast(dd, taak=ff.RADAR, item=f"m{n}", mens="keep", ai="dismiss", niveau="C")
    assert ff.pas_demotie_toe(niveaus, ff.alle(dd), ff.RADAR, ff.instellingen(dd, ff.RADAR))
    assert niveaus.niveau(ff.RADAR) == "B"
    for n in range(30, 70):
        ff.leg_vast(dd, taak=ff.RADAR, item=f"m{n}", mens="keep", ai="dismiss", niveau="B")
    assert ff.pas_demotie_toe(niveaus, ff.alle(dd), ff.RADAR, ff.instellingen(dd, ff.RADAR)) == ""
    assert niveaus.niveau(ff.RADAR) == "B"


def test_demotie_raakt_alleen_de_eigen_taak(dd):
    niveaus = _niveaus(dd)
    for taak in (ff.RADAR, ff.CLAIM):
        niveaus.zet(taak, "D", door="founder", reden="test")
    for n in range(30):
        ff.leg_vast(dd, taak=ff.RADAR, item=f"m{n}", mens="keep", ai="dismiss", niveau="D")
    ff.pas_demotie_toe(niveaus, ff.alle(dd), ff.RADAR, ff.instellingen(dd, ff.RADAR))
    assert _niveaus(dd).niveau(ff.RADAR) == "C"
    assert _niveaus(dd).niveau(ff.CLAIM) == "D"


# ── 4. De niveaus klimmen los van elkaar ─────────────────────────────────────

def test_niveaus_klimmen_per_taak(dd):
    store = _niveaus(dd)
    assert store.alles() == {t: "A" for t in ff.TAKEN}
    assert store.zet(ff.RADAR, "B", door="founder", reden="meting groen")
    assert _niveaus(dd).niveau(ff.RADAR) == "B"
    assert _niveaus(dd).niveau(ff.CLAIM) == "A"                  # onafhankelijk
    assert _niveaus(dd).historie(ff.RADAR)[-1]["van"] == "A"
    assert store.zet(ff.RADAR, "B") is False                     # geen no-op-regel in de historie
    assert store.zet(ff.RADAR, "Z") is False


def test_er_zijn_precies_drie_taken():
    assert ff.TAKEN == ("radar_triage", "claim_oordeel", "content_goedkeuring")
    assert set(ff.OORDELEN) == set(ff.TAKEN)


# ── 5. De dispatch-takken ────────────────────────────────────────────────────

def _beslis(dd, taak, item, oordeel, **extra):
    form = {"taak": [taak], "item": [item], "oordeel": [oordeel], "next": ["/founder?ritme=dag"],
            "getoond": [str(time.time() - 8)]}
    form.update({k: [v] for k, v in extra.items()})
    return cockpit2.dispatch(dd, "ff_beslis", form, username=GUEST)


def test_beslissing_voert_uit_en_legt_vast(dd):
    st = _st(dd)
    rid = _radar_signaal(st, content="hemp sneaker composteerbaar")
    nxt, msg = _beslis(dd, ff.RADAR, rid, "dismiss")
    assert "dismissed" in msg
    assert _st(dd).radar.get(rid)["status"] == "afgewezen"       # het bestaande pad is echt gelopen
    rij = ff.alle(dd)[0]
    assert rij["mens"] == "dismiss" and rij["ai"] == "keep"      # voorstel door de server berekend
    assert rij["ai_getoond"] is False and rij["niveau"] == "A"
    assert 0 < rij["seconden"] < 60                             # founder-minuten gemeten
    assert "onthuld=" in nxt                                    # blind → onthulling volgt


def test_voorstel_komt_van_de_server_niet_uit_het_formulier(dd):
    """Een meegestuurd 'ai'-veld wordt genegeerd; anders kan de client de meting zetten."""
    st = _st(dd)
    rid = _radar_signaal(st, content="willekeurig nieuws zonder thema")
    _beslis(dd, ff.RADAR, rid, "dismiss", ai="dismiss")
    assert ff.alle(dd)[0]["ai"] == "dismiss"                    # toevallig gelijk...
    st2 = _st(dd)
    rid2 = _radar_signaal(st2, content="hemp sneaker composteerbaar plasticvrij")
    _beslis(dd, ff.RADAR, rid2, "dismiss", ai="dismiss")
    assert ff.alle(dd)[1]["ai"] == "keep"                       # ...maar hier wint de server


def test_onbekende_taak_of_oordeel_wordt_geweigerd(dd):
    _, msg = _beslis(dd, "verzonnen", "x", "keep")
    assert msg.startswith("✗")
    _, msg = _beslis(dd, ff.RADAR, "x", "misschien")
    assert msg.startswith("✗")
    assert ff.alle(dd) == []


def test_item_buiten_de_wachtrij_wordt_geweigerd(dd):
    _, msg = _beslis(dd, ff.RADAR, "bestaat-niet", "keep")
    assert "no longer in the queue" in msg


def test_correctie_is_een_klik_en_telt_niet_mee(dd):
    st = _st(dd)
    rid = _radar_signaal(st, content="hemp sneaker composteerbaar")
    _beslis(dd, ff.RADAR, rid, "dismiss")
    _, msg = _beslis(dd, ff.RADAR, rid, "keep", correctie="1")
    assert "kept" in msg
    assert _st(dd).radar.get(rid)["status"] == "goedgekeurd"     # de correctie draait het echt om
    rijen = ff.alle(dd)
    assert len(rijen) == 2 and rijen[1]["correctie"] is True
    assert rijen[1]["ai"] == "keep"                             # voorstel uit de log, niet uit de form
    assert len(ff.held_out(rijen, ff.RADAR)) == 1               # alleen het blinde label meet mee


def test_promotie_is_fail_closed(dd):
    """De knop zichtbaar krijgen is geen bewijs; de poort rekent bij de klik opnieuw."""
    _, msg = cockpit2.dispatch(dd, "ff_promote", {"taak": [ff.RADAR], "next": ["/founder"]},
                               username=GUEST)
    assert "promotion blocked" in msg
    assert _niveaus(dd).niveau(ff.RADAR) == "A"

    for n in range(40):
        ff.leg_vast(dd, taak=ff.RADAR, item=f"m{n}", mens="keep", ai="keep", niveau="A")
    _, msg = cockpit2.dispatch(dd, "ff_promote", {"taak": [ff.RADAR], "next": ["/founder"]},
                               username=GUEST)
    assert "level B" in msg and _niveaus(dd).niveau(ff.RADAR) == "B"
    assert _niveaus(dd).niveau(ff.CLAIM) == "A"                  # klimt niet mee


def test_demotie_kan_altijd(dd):
    _niveaus(dd).zet(ff.RADAR, "C", door="t", reden="test")
    _, msg = cockpit2.dispatch(dd, "ff_demote", {"taak": [ff.RADAR], "next": ["/founder"]},
                               username=GUEST)
    assert "level B" in msg and _niveaus(dd).niveau(ff.RADAR) == "B"


def test_audit_beslissing_trekt_de_trede_vanzelf_terug(dd, monkeypatch):
    """De hele lus: een blind audit-oordeel dat de meting onder de lat duwt, degradeert de taak
    zonder dat de founder iets extra's hoeft te doen. Promotie vraagt een handtekening, terugval
    niet — anders draait een afwijkend model door tot iemand toevallig kijkt."""
    st = _st(dd)
    _niveaus(dd).zet(ff.RADAR, "D", door="founder", reden="meting groen")
    # 29 eerdere blinde audit-oordelen die het niet eens waren: één onder de bewijs-eis van 30.
    for n in range(29):
        ff.leg_vast(dd, taak=ff.RADAR, item=f"m{n}", mens="keep", ai="dismiss",
                    niveau="D", audit=True)
    assert _niveaus(dd).niveau(ff.RADAR) == "D"                  # nog geen conclusie

    monkeypatch.setattr(ff, "in_auditsteekproef", lambda taak, item, pct: True)
    rid = _radar_signaal(st, content="beursbericht over kantoorpanden")   # voorstel: dismiss
    _, msg = _beslis(dd, ff.RADAR, rid, "keep")                  # de 30e afwijking
    assert "stepped back to level C" in msg
    assert _niveaus(dd).niveau(ff.RADAR) == "C"


def test_goede_audit_beslissing_laat_de_trede_staan(dd, monkeypatch):
    st = _st(dd)
    _niveaus(dd).zet(ff.RADAR, "D", door="founder", reden="meting groen")
    for n in range(20):
        ff.leg_vast(dd, taak=ff.RADAR, item=f"m{n}", mens="keep", ai="keep",
                    niveau="D", audit=True)
    monkeypatch.setattr(ff, "in_auditsteekproef", lambda taak, item, pct: True)
    rid = _radar_signaal(st, content="composteerbare hemp sneaker")       # voorstel: keep
    _, msg = _beslis(dd, ff.RADAR, rid, "keep")
    assert "stepped back" not in msg
    assert _niveaus(dd).niveau(ff.RADAR) == "D"


def test_terugval_staat_op_het_scherm(dd):
    _niveaus(dd).zet(ff.RADAR, "C", door="founder", reden="meting groen")
    pagina = render_founder_flow(_st(dd), dd, csrf_token="tok")
    assert "Automatic step-back is armed" in pagina              # de poort is zichtbaar...
    assert "0/30 needed" in pagina                               # ...inclusief waar hij op wacht
    assert "Last change: A → C by founder" in pagina
    # Op A is er geen autonomie om in te trekken, dus ook geen belofte erover.
    assert pagina.count("Automatic step-back is armed") == 1


def test_ai_werkt_de_wachtrij_alleen_af_vanaf_c(dd):
    st = _st(dd)
    _radar_signaal(st, content="hemp sneaker composteerbaar")
    _, msg = cockpit2.dispatch(dd, "ff_run", {"taak": [ff.RADAR], "next": ["/founder"]},
                               username=GUEST)
    assert "only works through the queue from level C" in msg
    assert ff.alle(dd) == []


# ── 6. Automatische verwerking op C/D ────────────────────────────────────────

def test_verwerk_automatisch_slaat_de_auditsteekproef_over(dd, monkeypatch):
    st = _st(dd)
    ids = [_radar_signaal(st, content=f"hemp composteerbaar signaal {n}") for n in range(6)]
    # De helft in de steekproef: die moet blind bij de mens blijven liggen.
    monkeypatch.setattr(ff, "in_auditsteekproef",
                        lambda taak, item, pct: item in ids[:3])
    cfg = dict(ff._DEFAULTS[ff.RADAR])
    verslag = founder_taken.verwerk_automatisch(_st(dd), dd, ff.RADAR, "D", cfg)
    assert verslag["verwerkt"] == 3 and verslag["audit"] == 3
    st2 = _st(dd)
    assert all(st2.radar.get(i)["status"] == "wacht" for i in ids[:3])       # audit onaangeroerd
    assert all(st2.radar.get(i)["status"] == "goedgekeurd" for i in ids[3:])
    rijen = ff.alle(dd)
    assert len(rijen) == 3 and all(r["mens"] is None and r["door"] == "ai" for r in rijen)


def test_verwerk_automatisch_doet_niets_op_a_en_b(dd):
    st = _st(dd)
    rid = _radar_signaal(st, content="hemp sneaker composteerbaar")
    for niveau in ("A", "B"):
        verslag = founder_taken.verwerk_automatisch(_st(dd), dd, ff.RADAR, niveau,
                                                    dict(ff._DEFAULTS[ff.RADAR]))
        assert verslag["verwerkt"] == 0
    assert _st(dd).radar.get(rid)["status"] == "wacht"


def test_verwerkte_items_verdwijnen_uit_de_wachtrij(dd, monkeypatch):
    st = _st(dd)
    _radar_signaal(st, content="hemp sneaker composteerbaar")
    monkeypatch.setattr(ff, "in_auditsteekproef", lambda taak, item, pct: False)
    founder_taken.verwerk_automatisch(_st(dd), dd, ff.RADAR, "D", dict(ff._DEFAULTS[ff.RADAR]))
    assert founder_taken.wachtrij(_st(dd), dd, ff.RADAR) == []


# ── 7. De wachtrijen en hun voorstellen ──────────────────────────────────────

def test_radar_voorstel_gebruikt_het_bestaande_strategie_filter(dd):
    st = _st(dd)
    raak = _radar_signaal(st, content="composteerbare hemp sneaker", rationale="materiaal")
    mis = _radar_signaal(st, content="beursbericht over kantoorpanden", rationale="")
    rijen = {i["item"]: i for i in founder_taken.wachtrij(_st(dd), dd, ff.RADAR)}
    assert rijen[raak]["ai"] == "keep" and "strategy theme" in rijen[raak]["ai_waarom"]
    assert rijen[mis]["ai"] == "dismiss"


def test_claim_wachtrij_bevat_wat_de_scan_niet_kon_afdoen():
    """Op productie stond de hele werklijst in een auto-status en was de wachtrij dus leeg: de
    flow wachtte op 'open' terwijl de wekelijkse scan dat woord al lang niet meer gebruikte.
    'Niet auto-verifieerbaar' is juist hét geval waarin een mens moet oordelen."""
    from nooch_village import claims_db
    assert founder_taken._wacht_op_mens("open")
    assert founder_taken._wacht_op_mens(claims_db.NIET_VERIFIEERBAAR)
    assert founder_taken._wacht_op_mens(claims_db.AUTO_REGRESSIE)
    assert not founder_taken._wacht_op_mens(claims_db.AUTO_OPGELOST)
    assert not founder_taken._wacht_op_mens("in behandeling")
    assert not founder_taken._wacht_op_mens("live")


def test_claim_wachtrij_leest_de_auto_statussen_uit_de_overlay(dd):
    from nooch_village import claims_db
    eerst = {r["item"] for r in founder_taken.wachtrij(_st(dd), dd, ff.CLAIM)}
    assert "claim:1" in eerst
    # De scan zet #1 op 'niet auto-verifieerbaar' → moet in de wachtrij BLIJVEN.
    claims_db.overlay_set_status(dd, 1, claims_db.NIET_VERIFIEERBAAR, machine=True)
    # ...en #2 op auto-opgelost → moet eruit.
    claims_db.overlay_set_status(dd, 2, claims_db.AUTO_OPGELOST, machine=True)
    daarna = {r["item"] for r in founder_taken.wachtrij(_st(dd), dd, ff.CLAIM)}
    assert "claim:1" in daarna and "claim:2" not in daarna


def test_claim_voorstel_volgt_het_stoplicht_van_de_database(dd):
    rijen = founder_taken.wachtrij(_st(dd), dd, ff.CLAIM)
    assert rijen, "de werklijst van de claims-database is de wachtrij"
    for r in rijen:
        assert r["item"].startswith("claim:")
        assert r["ai"] in (None,) + ff.OORDELEN[ff.CLAIM]
    # red → fix copy, orange → bank evidence: geen nieuwe weging, alleen de routing die volgt.
    assert founder_taken._STOPLICHT_ROUTE["red"] == "fix"
    assert founder_taken._STOPLICHT_ROUTE["orange"] == "bewijs"
    assert founder_taken._STOPLICHT_ROUTE["escaleren"] == "scientist"


def test_claim_oordeel_zet_het_werklijst_item_op_in_behandeling(dd):
    rij = founder_taken.wachtrij(_st(dd), dd, ff.CLAIM)[0]
    _, msg = _beslis(dd, ff.CLAIM, rij["item"], "scientist")
    assert "Scientist" in msg
    assert rij["item"] not in {r["item"] for r in founder_taken.wachtrij(_st(dd), dd, ff.CLAIM)}


def test_content_wachtrij_bevat_field_notes_met_grondings_oordeel(dd, tmp_path):
    import json
    import os
    out = os.path.join(dd, "output")
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "field_note_2026-08-03.md"), "w").write(
        "# Field Note\n\nVandaag 42 bezoekers op de site.\n")
    json.dump({"visitors": 42}, open(os.path.join(out, "pulse_raw_2026-08-03.json"), "w"))
    open(os.path.join(out, "field_note_2026-08-04.md"), "w").write(
        "# Field Note\n\nVandaag 999 bezoekers op de site.\n")
    json.dump({"visitors": 7}, open(os.path.join(out, "pulse_raw_2026-08-04.json"), "w"))

    rijen = {i["item"]: i for i in founder_taken.wachtrij(_st(dd), dd, ff.CONTENT)}
    assert rijen["fieldnote:2026-08-03"]["ai"] == "publiceer"
    assert rijen["fieldnote:2026-08-04"]["ai"] == "corrigeer"    # 999 staat nergens in de data
    assert "ongegrond" in rijen["fieldnote:2026-08-04"]["ai_waarom"]


def test_content_goedkeuring_is_de_vastlegging_zelf(dd):
    import os
    out = os.path.join(dd, "output")
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "field_note_2026-08-03.md"), "w").write("# Field Note\n\nRustige dag.\n")
    _, msg = _beslis(dd, ff.CONTENT, "fieldnote:2026-08-03", "publiceer")
    assert "approved" in msg
    assert ff.alle(dd)[0]["item"] == "fieldnote:2026-08-03"


# ── 8. De succesmetriek ──────────────────────────────────────────────────────

def test_weekcijfers_tellen_minuten_en_ai_aandeel(dd):
    week = 7 * 86400
    nu = time.time()
    rijen = [
        {"taak": ff.RADAR, "item": "a", "mens": "keep", "ai": "keep", "seconden": 120.0,
         "ai_getoond": False, "correctie": False, "ts": nu - week},
        {"taak": ff.RADAR, "item": "b", "mens": "keep", "ai": "keep", "seconden": 60.0,
         "ai_getoond": False, "correctie": False, "ts": nu - week},
        {"taak": ff.RADAR, "item": "c", "mens": "keep", "ai": "keep", "seconden": 30.0,
         "ai_getoond": False, "correctie": False, "ts": nu},
        {"taak": ff.RADAR, "item": "d", "mens": None, "ai": "keep", "ts": nu},
        {"taak": ff.RADAR, "item": "e", "mens": None, "ai": "keep", "ts": nu},
    ]
    cijfers = ff.weekcijfers(rijen, ff.RADAR)
    assert len(cijfers) == 2
    assert cijfers[0]["minuten"] == 3.0 and cijfers[0]["ai_aandeel"] == 0.0
    assert cijfers[1]["minuten"] == 0.5 and cijfers[1]["ai_aandeel"] == pytest.approx(2 / 3)
    assert ff.trend(cijfers) == "dalend"                        # dít is de succesmetriek


def test_seconden_worden_geplafonneerd(dd):
    """Eén vergeten tabblad mag de founder-minuten van een week niet onleesbaar maken."""
    rij = ff.leg_vast(dd, taak=ff.RADAR, item="a", mens="keep", ai="keep", seconden=99_999)
    assert rij["seconden"] == 300.0


def test_succesmetriek_staat_op_het_scherm(dd):
    pagina = render_founder_flow(_st(dd), dd, csrf_token="tok")
    assert "Founder minutes per week" in pagina
    assert "agreement" in pagina or "no blind examples yet" in pagina
    assert "Level A" in pagina


# ── 9. De lat is per taak in te stellen ──────────────────────────────────────

def test_lat_is_per_taak_configureerbaar(dd, tmp_path):
    import json
    import os
    cfgdir = os.path.join(dd, "..", "config")
    os.makedirs(cfgdir, exist_ok=True)
    with open(os.path.join(cfgdir, ff.CONFIG_BESTAND), "w") as f:
        json.dump({ff.RADAR: {"lat": 0.5, "min_n": 4}, ff.CLAIM: {"lat": 0.99}}, f)
    assert ff.instellingen(dd, ff.RADAR)["lat"] == 0.5
    assert ff.instellingen(dd, ff.RADAR)["min_n"] == 4
    assert ff.instellingen(dd, ff.CLAIM)["lat"] == 0.99
    assert ff.instellingen(dd, ff.CONTENT)["lat"] == ff._DEFAULTS[ff.CONTENT]["lat"]


def test_kapotte_config_verlaagt_de_lat_niet(dd):
    import os
    cfgdir = os.path.join(dd, "..", "config")
    os.makedirs(cfgdir, exist_ok=True)
    open(os.path.join(cfgdir, ff.CONFIG_BESTAND), "w").write("{ dit is geen json")
    assert ff.instellingen(dd, ff.RADAR)["lat"] == ff._DEFAULTS[ff.RADAR]["lat"]
