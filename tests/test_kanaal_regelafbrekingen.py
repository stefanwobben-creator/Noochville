"""Een bericht met meerdere regels blijft een bericht met meerdere regels.

DE BUG. `post()` en `bewerk()` sloegen de tekst plat met

    " ".join(str(tekst or "").split())

en `str.split()` zonder argument knipt op ÉLKE witruimte — spaties, tabs én regeleindes. Wie drie
regels typte en op Send drukte, kreeg één lange alinea terug. Het renderen was niet het probleem:
`.msg-text` staat al op `white-space:pre-wrap` en `_bericht` escapet met `_e()`, dat een `\\n`
gewoon doorlaat. De tekst was al plat vóór hij werd opgeslagen.

EN HIJ WAS BEREIKBAAR MET ÉÉN TOETS. Het schrijfveld is een `<textarea>` zonder
Enter-verstuurt-handler (de enige Enter-onderschepping in `nooch.js` is de @-kiezer, en die
grijpt alleen in als zijn lijst openstaat). Enter maakte dus netjes een nieuwe regel — die bij
het opslaan verdween.

DEZELFDE REGEL STOND OP TWEE PLEKKEN, en dat is hoe de goal-kanaal-bug zich ook vermenigvuldigde:
`_eigen_bericht_poort` kopieerde daar braaf de fout van `_act_msg_post`. Daarom is dit geen
twee-regelige patch maar één helper met twee aanroepers, plus een test die verbiedt dat er een
derde kopie ontstaat.

WAT NIET VERANDERT: spaties en tabs BINNEN een regel worden nog steeds platgeslagen (anders
plakt iemand een halve tabel in een kanaal), lege tekst wordt nog steeds geweigerd, en
`TEKST_MAX` knipt er nog steeds achteraan.
"""
from __future__ import annotations

import re

from nooch_village import channels, cockpit2


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Regel Ruiter", "regel@nooch.earth")
    return dd, cockpit2._Stores(dd), ik


def _kanaal():
    return channels.circle_kanaal("mother_earth")


# ── 1. Regelovergangen blijven ──────────────────────────────────────────────────────────────
def test_een_bericht_van_drie_regels_blijft_drie_regels(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = _kanaal()
    st.channels.post(k, "eerste regel\ntweede regel\nderde regel", author_id=ik.id)
    assert cockpit2._Stores(dd).channels.trail(k)[0]["text"] == \
        "eerste regel\ntweede regel\nderde regel"


def test_een_witregel_tussen_twee_alinea_s_blijft_staan(tmp_path):
    """Een lege regel is een alinea-grens, geen witruimte die je mag opruimen."""
    dd, st, ik = _dorp(tmp_path)
    k = _kanaal()
    st.channels.post(k, "alinea een\n\nalinea twee", author_id=ik.id)
    assert cockpit2._Stores(dd).channels.trail(k)[0]["text"] == "alinea een\n\nalinea twee"


def test_bewerken_behoudt_ze_ook(tmp_path):
    """De tweede aanroeper. Zonder deze test dekt de fix maar de helft — en dat is precies hoe
    de goal-kanaal-bug een maand lang half gerepareerd bleef."""
    dd, st, ik = _dorp(tmp_path)
    k = _kanaal()
    st.channels.post(k, "eerst", author_id=ik.id)
    eid = cockpit2._Stores(dd).channels.trail(k)[0]["id"]
    st2 = cockpit2._Stores(dd)
    assert st2.channels.bewerk(k, eid, "regel een\nregel twee", door=ik.id)
    assert cockpit2._Stores(dd).channels.trail(k)[0]["text"] == "regel een\nregel twee"


def test_het_werkt_ook_in_een_projectkanaal(tmp_path):
    """Een projectkanaal is `project["log"]` via de ledger. Die doet alleen `.strip()`, dus zodra
    de store niet meer platslaat komt het daar ook goed — maar dat is een aanname tot het getoetst
    is, en de store is de enige plek waar het misging."""
    dd, st, ik = _dorp(tmp_path)
    pid = st.projects.create("mother_earth", "Een project", "human")
    k = channels.project_kanaal(pid)
    st.channels.post(k, "regel een\nregel twee", author_id=ik.id)
    assert cockpit2._Stores(dd).channels.trail(k)[-1]["text"] == "regel een\nregel twee"


# ── 2. Wat wél wordt platgeslagen ───────────────────────────────────────────────────────────
def test_spaties_en_tabs_binnen_een_regel_worden_nog_steeds_platgeslagen(tmp_path):
    """MUTATIE-CONTROLE: "behoud alles" zou ook slagen op de tests hierboven. Wie een halve tabel
    plakt, hoort geen kolommen in een kanaalbericht te krijgen."""
    dd, st, ik = _dorp(tmp_path)
    k = _kanaal()
    st.channels.post(k, "veel    spaties\ten\teen\ttab\ntweede   regel", author_id=ik.id)
    assert cockpit2._Stores(dd).channels.trail(k)[0]["text"] == \
        "veel spaties en een tab\ntweede regel"


def test_witruimte_aan_de_randen_gaat_eraf(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = _kanaal()
    st.channels.post(k, "\n\n  midden  \n\n", author_id=ik.id)
    assert cockpit2._Stores(dd).channels.trail(k)[0]["text"] == "midden"


def test_windows_regeleindes_worden_gewone_regeleindes(tmp_path):
    """Een browser stuurt `\\r\\n`. Eén losse `\\r` in de opslag is een tekst die overal anders
    afbreekt dan hij eruitziet."""
    dd, st, ik = _dorp(tmp_path)
    k = _kanaal()
    st.channels.post(k, "regel een\r\nregel twee\rregel drie", author_id=ik.id)
    tekst = cockpit2._Stores(dd).channels.trail(k)[0]["text"]
    assert "\r" not in tekst
    assert tekst == "regel een\nregel twee\nregel drie"


# ── 3. Wat fail-closed blijft ───────────────────────────────────────────────────────────────
def test_een_leeg_bericht_bestaat_nog_steeds_niet(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = _kanaal()
    for leeg in ("", "   ", "\n\n\n", " \n \t \n "):
        assert st.channels.post(k, leeg, author_id=ik.id) is None, repr(leeg)
    assert cockpit2._Stores(dd).channels.trail(k) == []


def test_een_bewerking_naar_leeg_doet_nog_steeds_niets(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = _kanaal()
    st.channels.post(k, "blijft staan", author_id=ik.id)
    eid = cockpit2._Stores(dd).channels.trail(k)[0]["id"]
    st2 = cockpit2._Stores(dd)
    assert st2.channels.bewerk(k, eid, "\n \n", door=ik.id) is False
    assert cockpit2._Stores(dd).channels.trail(k)[0]["text"] == "blijft staan"


def test_de_lengtegrens_geldt_nog(tmp_path):
    dd, st, ik = _dorp(tmp_path)
    k = _kanaal()
    st.channels.post(k, "a\n" * 2000, author_id=ik.id)
    assert len(cockpit2._Stores(dd).channels.trail(k)[0]["text"]) == channels.TEKST_MAX


# ── 4. Eén regel, niet twee ─────────────────────────────────────────────────────────────────
def _methode_bron(naam: str) -> str:
    bron = open(channels.__file__, encoding="utf-8").read()
    m = re.search(rf"\n    def {naam}\(.*?(?=\n    def |\nclass |\Z)", bron, re.S)
    assert m, f"{naam} niet gevonden"
    zonder = re.sub(r'""".*?"""', " ", m.group(0), flags=re.S)
    return re.sub(r"#[^\n]*", " ", zonder)


def test_geen_enkele_schrijfmethode_slaat_zelf_tekst_plat():
    """`reference, don't copy`. De platslag-regel stond letterlijk twee keer in dit bestand.

    OP DE TWEE METHODES EN NIET OP HET HELE BESTAND. De eerste versie telde `" ".join(` over
    `channels.py` en eiste er één — maar er zijn er nog drie die over een kanaalNAAM gaan, en
    dáár is platslaan juist goed (een naam IS één regel). Die test mat dus iets anders dan hij
    beweerde."""
    assert callable(getattr(channels, "_normaliseer_tekst", None))
    for naam in ("post", "bewerk"):
        bron = _methode_bron(naam)
        assert "_normaliseer_tekst(" in bron, f"{naam} gebruikt de helper niet"
        assert '" ".join(' not in bron, f"{naam} slaat de tekst nog zelf plat"


def test_ook_de_kanaalnaam_wordt_maar_op_een_plek_genormaliseerd():
    """Bijvangst uit dezelfde beurt: `maak_topic` en `hernoem_topic` hadden allebei hun eigen
    kopie van de naam-regel. Dezelfde soort duplicatie, één streek verderop."""
    assert callable(getattr(channels, "_normaliseer_naam", None))
    for naam in ("maak_topic", "hernoem_topic"):
        bron = _methode_bron(naam)
        assert "_normaliseer_naam(" in bron, f"{naam} gebruikt de helper niet"
        assert '" ".join(' not in bron, f"{naam} slaat de naam nog zelf plat"
    assert channels._normaliseer_naam("  Batch   4\nmet een regel  ") == "Batch 4 met een regel"


# ── 5. Op het scherm ────────────────────────────────────────────────────────────────────────
def test_de_regelovergang_komt_ook_op_het_scherm(tmp_path):
    """`.msg-text` stond al op `white-space:pre-wrap` en `_e()` laat een `\\n` door — het
    renderen was nooit het probleem. Deze test zorgt dat dat zo blijft."""
    import os
    from nooch_village.views.messages import render_messages
    dd, st, ik = _dorp(tmp_path)
    k = _kanaal()
    st.channels.post(k, "regel een\nregel twee", author_id=ik.id)
    html = render_messages(cockpit2._Stores(dd), ik=ik.id, kanaal=k, csrf_token="t")
    assert "regel een\nregel twee" in html
    basis = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(basis, "nooch_village", "static", "nooch.css"), encoding="utf-8").read()
    assert re.search(r"\.msg-text\{[^}]*white-space:pre-wrap", css)
