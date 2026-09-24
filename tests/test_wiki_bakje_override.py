"""Het noodluik: een bakje rechtstreeks aanwijzen als geen domein past (24 september 2026).

WANNEER DIT MAG. Een gewone indeling loopt via een DOMEIN — het artefact draagt er een, of zijn
rol doet dat. Dat is de route die je wilt, want een domein is door governance toegewezen en het
beweegt mee als de classificatie ooit verandert. Deze route slaat dat over.

DE REGEL ERACHTER, en die is belangrijker dan de uitzondering zelf:

    EEN DOMEIN MAAK JE ALS DE PRAKTIJK EROM VRAAGT, NIET VOORAF OM EEN INDELING SLUITEND TE
    KRIJGEN.

Hetzelfde principe als waarom `domeinen.ROL_BAKJE` kort blijft. Groeit de override-tabel, dan is
dat een signaal dat er iets ontbreekt in governance — geen aanleiding om er hier regels bij te
schrijven.

HET GEVAAR ZIT IN `meta`. De feiten van een pagina wonen in datzelfde woordenboek, en
`update(meta=…)` VERVANGT het. Wie hier een vers `{"domein": …}` doorgeeft, gooit de feiten van
die pagina weg — stil, en pas zichtbaar als iemand ze mist.
"""
from __future__ import annotations

from nooch_village import cockpit2, domeinen, wiki_domein


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    return dd, st, st.records.all()[0].id


def _met(st, aid, bakje, reden="x" * 60):
    bewaard = dict(wiki_domein.OVERRIDES)
    wiki_domein.OVERRIDES.clear()
    wiki_domein.OVERRIDES[aid] = (bakje, reden)
    return bewaard


def _terug(bewaard):
    wiki_domein.OVERRIDES.clear()
    wiki_domein.OVERRIDES.update(bewaard)


def test_de_override_zet_het_bakje(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Company information")
    bewaard = _met(st, a.id, "compliance-legal")
    try:
        wiki_domein.pas_overrides_toe(st, apply=True)
        na = st.att.get(a.id)
        assert na.meta.get("domein") == "compliance-legal"
        assert domeinen.bakje_van(na, st.records.all())[0] == "compliance-legal"
    finally:
        _terug(bewaard)


def test_de_feiten_van_de_pagina_overleven(tmp_path):
    """DE VAL. `update(meta=…)` vervangt het hele woordenboek, en de feiten wonen daarin."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="X", meta={"feiten": [{"tekst": "een feit"}]})
    bewaard = _met(st, a.id, "compliance-legal")
    try:
        wiki_domein.pas_overrides_toe(st, apply=True)
        na = st.att.get(a.id)
        assert na.meta.get("domein") == "compliance-legal"
        assert na.meta.get("feiten") == [{"tekst": "een feit"}], "de feiten zijn weg"
    finally:
        _terug(bewaard)


def test_de_dry_run_schrijft_niets(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="X")
    bewaard = _met(st, a.id, "compliance-legal")
    try:
        acties = wiki_domein.pas_overrides_toe(st, apply=False)
        assert acties[0][1] == "zou zetten"
        assert not (st.att.get(a.id).meta or {}).get("domein")
    finally:
        _terug(bewaard)


def test_hij_is_idempotent(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="X")
    bewaard = _met(st, a.id, "compliance-legal")
    try:
        wiki_domein.pas_overrides_toe(st, apply=True)
        opnieuw = wiki_domein.pas_overrides_toe(st, apply=True)
        assert opnieuw[0][1] == "staat al goed"
    finally:
        _terug(bewaard)


def test_een_onbekend_bakje_wordt_geweigerd(tmp_path):
    """Fail-closed: anders staat er een override en valt de pagina alsnog in Overig, terwijl het
    rapport zegt dat hij geplaatst is."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="X")
    bewaard = _met(st, a.id, "bestaat-niet")
    try:
        acties = wiki_domein.pas_overrides_toe(st, apply=True)
        assert acties[0][1] == "geweigerd"
        assert not (st.att.get(a.id).meta or {}).get("domein")
    finally:
        _terug(bewaard)


def test_elke_override_draagt_zijn_reden_en_wijst_naar_een_bestaand_bakje():
    geldig = dict(domeinen.BAKJES)
    for aid, (bakje, reden) in wiki_domein.OVERRIDES.items():
        assert bakje in geldig, f"{aid} wijst naar onbekend bakje {bakje!r}"
        assert len(reden) > 60, f"{aid} heeft geen bruikbare reden"


def test_de_tabel_blijft_klein():
    """Geen plafond maar een signaal: groeit deze tabel, dan ontbreekt er iets in governance —
    en dan hoort daar een domein te komen, niet hier een regel bij. Zelfde gedachte als het kort
    houden van `domeinen.ROL_BAKJE`."""
    assert len(wiki_domein.OVERRIDES) <= 3, (
        f"{len(wiki_domein.OVERRIDES)} overrides. Dit is de uitzonderingsroute; bij meer dan een "
        f"handvol is de vraag welk domein er ontbreekt, niet welke regel erbij moet.")
