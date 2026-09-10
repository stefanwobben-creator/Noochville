"""De periodieke compliance-skills hangen aan het claims-domein, niet aan een rol-id.

Gemeten op 10 september 2026 op de live site: `/skills` meldde "Nobody wields this means yet" voor
zowel `claims_site_scan` als `regulation_watch`. De vorige houder was gearchiveerd, en een
gearchiveerde rol krijgt geen inwoner, dus draaide er niemand meer. De wekelijkse site-scan liep op
8 september voor het laatst en was op 15 september aan de beurt — twaalf dagen vóór de
EmpCo-handhaving van 27 september.

Deze grant is bewust tijdelijk: zodra de geplande-taak-mechaniek er is horen beide skills daar
thuis. Daarom toetst dit bestand ook expliciet dat een INTREKKING blijft staan, want anders zet de
seed bij de eerstvolgende start stil terug wat je net hebt weggehaald.
"""
from __future__ import annotations

from nooch_village import afslanken, claims_db, cockpit2, org
from nooch_village.seeds import migrate_records

PERIODIEK = ("claims_site_scan", "regulation_watch")
ROL = "mother_earth__nooch__website_developer"      # bestaande rol in de fixture
ANDERE = "mother_earth__nooch__marketing_lead"


def _stores(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def _geef_domein(st, role_id: str):
    rec = st.records.get(role_id)
    rec.definition.domains = [claims_db.DOMEIN]
    st.records.put(rec)
    return rec


def _skills(st, role_id: str) -> list:
    return list(st.records.get(role_id).definition.skills)


def test_houder_van_het_claims_domein_krijgt_beide_skills(tmp_path):
    st = _stores(tmp_path)
    _geef_domein(st, ROL)
    migrate_records(st.records)
    for s in PERIODIEK:
        assert s in _skills(st, ROL), s


def test_de_grant_is_idempotent(tmp_path):
    st = _stores(tmp_path)
    _geef_domein(st, ROL)
    migrate_records(st.records)
    versie_na_1 = st.records.get(ROL).version
    migrate_records(st.records)
    assert _skills(st, ROL).count("claims_site_scan") == 1
    assert st.records.get(ROL).version == versie_na_1, "tweede run mag niets meer schrijven"


def test_een_gearchiveerde_rol_wordt_niet_gewekt(tmp_path):
    """De kern: het oude record bestaat nog, maar mag deze skills nooit terugkrijgen."""
    st = _stores(tmp_path)
    rec = _geef_domein(st, ROL)
    rec.archived = True
    st.records.put(rec)
    migrate_records(st.records)
    for s in PERIODIEK:
        assert s not in _skills(st, ROL), s


def test_zonder_houder_gebeurt_er_niets(tmp_path):
    """Geen levende rol met het domein: geen crash, geen grant, geen willekeurige rol."""
    st = _stores(tmp_path)
    assert org.role_for_domain(st.records.all(), claims_db.DOMEIN) is None
    migrate_records(st.records)
    for rec in st.records.all():
        for s in PERIODIEK:
            assert s not in (rec.definition.skills or []), f"{s} belandde bij {rec.id}"


def test_een_ingetrokken_skill_komt_niet_terug(tmp_path):
    """Straks verhuizen deze twee naar de geplande taak. Een intrekking moet dan blijven staan,
    anders zet de eerstvolgende start hem stil terug — precies wat er met bulletin_schrijven
    gebeurde."""
    st = _stores(tmp_path)
    _geef_domein(st, ROL)
    migrate_records(st.records)
    assert "claims_site_scan" in _skills(st, ROL)

    afslanken.skill_intrekken(st.records, "claims_site_scan", reden="verhuisd naar de geplande taak",
                              data_dir=st.dd)
    assert "claims_site_scan" not in _skills(st, ROL)

    migrate_records(st.records)
    assert "claims_site_scan" not in _skills(st, ROL), "de seed overrulede een bewust besluit"
    assert "regulation_watch" in _skills(st, ROL), "de andere skill hoort ongemoeid te blijven"


def test_de_grant_verhuist_mee_met_het_domein(tmp_path):
    """Verhuist het domein naar een andere rol, dan volgt het gereedschap. Dat is het hele punt:
    geen rol-id in de code."""
    st = _stores(tmp_path)
    _geef_domein(st, ANDERE)
    migrate_records(st.records)
    for s in PERIODIEK:
        assert s in _skills(st, ANDERE), s
        assert s not in _skills(st, ROL), f"{s} hoort niet bij een rol zonder het domein"
