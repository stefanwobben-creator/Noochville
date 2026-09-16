"""De regrant-loop in `seeds.py`: periodieke skills volgen hun DOMEIN, niet een rol-id.

TWEE PAREN LOPEN ER NU DOORHEEN, en ze zitten om dezelfde reden aan een domein vast:

  claims_site_scan + regulation_watch      → het claims-domein (10 september)
  materiaal_kwartaal + materiaal_shortlist → het materiaal-domein (16 september)

Het materiaal-paar hing aan `harry_hemp` en aan niets anders. Die rol staat op de nominatie om
opgeruimd te worden, en dan verdwijnen twee werkende skills mee met een rol — niet als besluit,
maar als bijvangst. `materiaal_memo.ontvanger` adresseerde de memo's al op het eigenaar-domein;
sinds deze scope volgt de grant dezelfde verklaring als de bezorging.

WAT DIT BESTAND ECHT BEWAAKT is de derde fout, die pas bij het bouwen van het tweede paar boven
water kwam: `claims_db.DOMEIN` stond op "claims", en geen enkele rol hield dat ooit — de akte
schreef `claims-database`. `role_for_domain` gaf dus altijd None, `_zorg_skill(records, None, …)`
doet niets en zegt niets, en de PoC-fixture zaaide dezelfde verzonnen naam zodat elke test groen
stond. Een grant die nergens landt ziet er in de logs identiek uit aan een grant die al gedaan was.
Daarom eist dit bestand dat elk domein in de loop een houder HEEFT, en dat de loop luid is als niet.
"""
from __future__ import annotations

import logging

from nooch_village import claims_db, cockpit2, materiaal_memo, org
from nooch_village.seeds import migrate_records

MATERIAAL = ("materiaal_kwartaal", "materiaal_shortlist")
CLAIMS = ("claims_site_scan", "regulation_watch")


def _stores(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def _skills(st, role_id: str) -> list:
    return list(st.records.get(role_id).definition.skills)


# ── het materiaal-paar ────────────────────────────────────────────────────────

def test_de_houder_van_het_materiaal_domein_krijgt_beide_memos(tmp_path):
    st = _stores(tmp_path)
    houder = org.role_for_domain(st.records.all(), materiaal_memo.eigenaar_domein(st.dd))
    assert houder is not None, "de fixture kent geen houder van het materiaal-domein"
    migrate_records(st.records)
    for s in MATERIAAL:
        assert s in _skills(st, houder.id), s


def test_de_grant_gebruikt_hetzelfde_domein_als_de_bezorging(tmp_path):
    """De hele winst van deze scope. Zou de grant een eigen domeinnaam (of erger: een rol-id)
    dragen, dan kan "wie hem draait" en "wie de memo leest" alleen per toeval dezelfde rol zijn."""
    st = _stores(tmp_path)
    migrate_records(st.records)
    domein = materiaal_memo.eigenaar_domein(st.dd)
    houder = org.role_for_domain(st.records.all(), domein)
    assert materiaal_memo.ontvanger(st, st.dd, "materiaal")["rol"] == houder.id


def test_de_grant_is_idempotent(tmp_path):
    st = _stores(tmp_path)
    migrate_records(st.records)
    houder = org.role_for_domain(st.records.all(), materiaal_memo.eigenaar_domein(st.dd))
    versie = st.records.get(houder.id).version
    migrate_records(st.records)
    assert _skills(st, houder.id).count("materiaal_kwartaal") == 1
    assert st.records.get(houder.id).version == versie, "tweede run mag niets meer schrijven"


def test_de_grant_verhuist_mee_met_het_domein(tmp_path):
    """Waar dit allemaal om begonnen is: `harry_hemp` mag opgeruimd worden zonder dat de twee
    memo-skills stil met hem meegaan."""
    st = _stores(tmp_path)
    domein = materiaal_memo.eigenaar_domein(st.dd)
    oud = org.role_for_domain(st.records.all(), domein)
    nieuw_id = "mother_earth__nooch__website_developer"

    oud.definition.domains = [d for d in oud.definition.domains
                              if str(d).strip().lower() != domein.strip().lower()]
    st.records.put(oud)
    rec = st.records.get(nieuw_id)
    rec.definition.domains = list(rec.definition.domains or []) + [domein]
    st.records.put(rec)

    migrate_records(st.records)
    for s in MATERIAAL:
        assert s in _skills(st, nieuw_id), s
        assert s not in _skills(st, oud.id), f"{s} hoort niet bij een rol zonder het domein"


def test_een_gearchiveerde_houder_wordt_niet_gewekt(tmp_path):
    st = _stores(tmp_path)
    houder = org.role_for_domain(st.records.all(), materiaal_memo.eigenaar_domein(st.dd))
    houder.archived = True
    st.records.put(houder)
    migrate_records(st.records)
    for s in MATERIAAL:
        assert s not in _skills(st, houder.id), s


# ── de stille-no-op-klasse ────────────────────────────────────────────────────

def test_elk_domein_in_de_loop_heeft_een_houder_in_de_fixture(tmp_path):
    """DE guard onder deze scope. `claims_db.DOMEIN` wees zes dagen naar een naam die niemand
    hield; de fixture zaaide dezelfde naam, dus alle claims-tests stonden groen terwijl de lookup
    op productie None gaf. Een domeinconstante die de fixture niet kan vinden, is een dode lookup."""
    st = _stores(tmp_path)
    recs = st.records.all()
    zonder = [d for d in (claims_db.DOMEIN, materiaal_memo.eigenaar_domein(st.dd))
              if org.role_for_domain(recs, d) is None]
    assert zonder == [], f"domein zonder houder in de fixture: {zonder}"


def test_de_fixture_draagt_de_domeinnamen_uit_de_governance_akte(tmp_path):
    """Niet de naam die de code verzon. `role_proposals.build_compliance_domain_proposal` schreef
    `claims-database`; het levende record houdt dat plus `claim-verification`."""
    st = _stores(tmp_path)
    rec = st.records.get("mother_earth__nooch__compliance")
    assert {str(d).lower() for d in rec.definition.domains} == set(claims_db.DOMEINEN)


def test_een_domein_zonder_houder_is_luid_en_niet_stil(tmp_path, caplog):
    """`_zorg_skill(records, None, …)` doet niets en zwijgt. Dat is precies waarom de drift zo lang
    kon blijven staan: geen grant en een geslaagde grant zien er in de logs identiek uit."""
    st = _stores(tmp_path)
    for rec in st.records.all():
        doms = list(getattr(rec.definition, "domains", None) or [])
        if any(str(d).strip().lower() in {claims_db.DOMEIN.lower()} for d in doms):
            rec.definition.domains = [d for d in doms
                                      if str(d).strip().lower() != claims_db.DOMEIN.lower()]
            st.records.put(rec)

    with caplog.at_level(logging.WARNING, logger="village.seeds"):
        migrate_records(st.records)
    assert any(claims_db.DOMEIN in r.getMessage() for r in caplog.records), caplog.text
    for rec in st.records.all():
        for s in CLAIMS:
            assert s not in (rec.definition.skills or []), f"{s} belandde bij {rec.id}"
