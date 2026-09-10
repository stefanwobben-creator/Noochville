"""Het domein wijst de rol aan, niet andersom.

De compliance-rol verhuisde van de noochville-subcirkel naar de Nooch-cirkel en kreeg daarbij een
nieuw record-id. Overal in de code stond nog het oude id `"compliance"` als letterlijke waarde. Twee
gevolgen, allebei stil:

- de Claims-checker verdween van de Tools-tab van de rol (de mapping was op id gesleuteld);
- de wiki-zaaier zou zijn 20 claimpagina's op het GEARCHIVEERDE record hebben gezet, want zijn
  poort was `records.get(id) is None` en een archief-record bestaat nog gewoon.

Het tweede is het gemeenste: geen foutmelding, wel 20 pagina's, op een plek die niemand opent.

Wat een domein bezit is een governance-feit (G1 bewaakt dat het bij één rol ligt) en het verhuist
mee met de rol. Daarom leidt de code de eigenaar af uit het domein, en telt gearchiveerd niet mee.
"""
from __future__ import annotations

from nooch_village import claims_db, cockpit2, org, wiki_seed

CLAIMS = claims_db.DOMEIN
ROL = "mother_earth__nooch__website_developer"      # bestaande rol in de fixture
ANDERE = "mother_earth__nooch__marketing_lead"


def _stores(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def _geef_domein(st, role_id: str, domein: str = CLAIMS):
    rec = st.records.get(role_id)
    rec.definition.domains = [domein]
    st.records.put(rec)
    return rec


def _archiveer(st, role_id: str):
    rec = st.records.get(role_id)
    rec.archived = True
    st.records.put(rec)
    return rec


# ── de opzoeking zelf ────────────────────────────────────────────────────────────────────────

def test_domein_wijst_de_levende_rol_aan(tmp_path):
    st = _stores(tmp_path)
    _geef_domein(st, ROL)
    gevonden = org.role_for_domain(st.records.all(), CLAIMS)
    assert gevonden is not None and gevonden.id == ROL


def test_hoofdletters_en_spaties_doen_er_niet_toe(tmp_path):
    st = _stores(tmp_path)
    _geef_domein(st, ROL, "  Claims ")
    gevonden = org.role_for_domain(st.records.all(), CLAIMS)
    assert gevonden is not None and gevonden.id == ROL


def test_gearchiveerde_rol_bezit_geen_domein_meer(tmp_path):
    """De kern: het record bestaat nog, dus 'bestaat' is geen poort."""
    st = _stores(tmp_path)
    _geef_domein(st, ROL)
    _archiveer(st, ROL)
    assert st.records.get(ROL) is not None                 # het record is er nog
    assert org.role_for_domain(st.records.all(), CLAIMS) is None


def test_levende_rol_wint_van_gearchiveerde_naamgenoot(tmp_path):
    st = _stores(tmp_path)
    _geef_domein(st, ROL)
    _archiveer(st, ROL)
    _geef_domein(st, ANDERE)
    gevonden = org.role_for_domain(st.records.all(), CLAIMS)
    assert gevonden is not None and gevonden.id == ANDERE


def test_onbekend_of_leeg_domein_geeft_niets(tmp_path):
    st = _stores(tmp_path)
    assert org.role_for_domain(st.records.all(), "bestaat-niet") is None
    assert org.role_for_domain(st.records.all(), "") is None


# ── de Tools-tab ─────────────────────────────────────────────────────────────────────────────

def test_tools_kaart_volgt_het_domein(tmp_path):
    st = _stores(tmp_path)
    _geef_domein(st, ANDERE)
    page = cockpit2.render_node(st, ANDERE, "tools", csrf_token="t")
    assert "Claims checker" in page and "/claims" in page
    assert "Claim pages" in page
    assert f"/node?id={ANDERE}&amp;tab=notes" in page      # wijst naar de eigen wiki-pagina's


def test_rol_zonder_claims_domein_krijgt_geen_claims_tools(tmp_path):
    st = _stores(tmp_path)
    page = cockpit2.render_node(st, ANDERE, "tools", csrf_token="t")
    assert "Claims checker" not in page and "Claim pages" not in page


def test_id_gesleutelde_tools_blijven_werken(tmp_path):
    """De domein-laag komt naast de id-laag, niet ervoor in de plaats."""
    st = _stores(tmp_path)
    page = cockpit2.render_node(st, ROL, "tools", csrf_token="t")
    assert "Backlog Builder" in page


# ── de zaaier ────────────────────────────────────────────────────────────────────────────────

_PAGINA = [{"titel": "“100% Vegan” — homepage", "body": "Oordeel: oranje.", "feiten": []}]


def test_zaaien_op_een_gearchiveerde_rol_schrijft_niets(tmp_path):
    st = _stores(tmp_path)
    _archiveer(st, ROL)
    rapport = wiki_seed.zaai(st.att, st.records, paginas=_PAGINA, eigenaar=ROL,
                             soort="claim", apply=True)
    assert rapport[0]["actie"] == "overgeslagen"
    assert "gearchiveerd" in rapport[0]["reden"]
    assert cockpit2._Stores(st.dd).att.by_kind("note") == []


def test_zaaien_op_een_levende_rol_werkt_nog(tmp_path):
    st = _stores(tmp_path)
    rapport = wiki_seed.zaai(st.att, st.records, paginas=_PAGINA, eigenaar=ROL,
                             soort="claim", apply=True)
    assert rapport[0]["actie"] == "aangemaakt"
    assert len(cockpit2._Stores(st.dd).att.by_kind("note")) == 1
