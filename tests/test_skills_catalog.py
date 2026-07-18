"""Taak 2 — de skills-catalogus (/skills): wat kan al, waarvoor moet tooling komen.

Puur leeswerk op echte data: registry, records, koppelingen, human inbox.
"""
from __future__ import annotations

from nooch_village import acc_ids, cockpit2, skills_catalog
from nooch_village.human_inbox import HumanInbox
from nooch_village.views.skills import render_skills


_ROLE = "mother_earth__nooch__website_developer"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _koppel(dd, st, skill="site_health"):
    aid = acc_ids.acc_id_at(st.records.get(_ROLE).definition, 0)
    cockpit2.dispatch(dd, "skilllink_add", {"role": [_ROLE], "acc_id": [aid], "skill": [skill],
                                            "next": ["/x"]}, username="guest")
    return aid


# ── Blok 1: uitvoerbaar ──────────────────────────────────────────────────────

def test_uitvoerbaar_bevat_echte_registry_skills(tmp_path):
    dd, st = _st(tmp_path)
    rows = skills_catalog.uitvoerbaar(st.records.all(), st.ai)
    namen = {r["skill"] for r in rows}
    assert "site_health" in namen and "keyword_review" in namen
    sh = next(r for r in rows if r["skill"] == "site_health")
    assert sh["label"] and sh["label"] != "site_health"      # mensentaal, geen kale id
    assert sh["domein"] is None and sh["zwaar"] is False


def test_domein_en_zwaar_markering(tmp_path):
    dd, st = _st(tmp_path)
    rows = {r["skill"]: r for r in skills_catalog.uitvoerbaar(st.records.all(), st.ai)}
    kr = rows["keyword_review"]
    assert kr["domein"] == "bibliotheek" and kr["zwaar"] is True
    assert kr["suggestie_tegenhanger"] == "keyword_nominatie"


def test_gebruikers_toont_dna_en_koppeling(tmp_path):
    dd, st = _st(tmp_path)
    _koppel(dd, st)
    st2 = cockpit2._Stores(dd)
    door = skills_catalog.gebruikers(st2.records.all(), st2.ai)
    routes = [(g["role"], g["route"]) for g in door.get("site_health", [])]
    assert (_ROLE, "koppeling") in routes
    # De belofte staat erbij: het middel dient een accountability, niet een rol.
    koppeling = next(g for g in door["site_health"] if g["route"] == "koppeling")
    assert koppeling["acc"]


def test_sleutels_worden_alleen_bij_naam_genoemd(tmp_path):
    dd, st = _st(tmp_path)
    rows = skills_catalog.uitvoerbaar(st.records.all(), st.ai)
    for r in rows:
        for k in r["sleutels"]["verplicht"] + r["sleutels"]["optioneel"]:
            assert k.isupper() or "_" in k       # een env-naam, nooit een waarde


# ── Blok 2: genoemd maar niet gedekt ─────────────────────────────────────────

def test_skill_zonder_implementatie_verschijnt(tmp_path):
    dd, st = _st(tmp_path)
    rec = st.records.get(_ROLE)
    rec.definition.skills = ["bestaat_niet_skill"]
    st.records.put(rec)
    st2 = cockpit2._Stores(dd)
    blok = skills_catalog.niet_gedekt(st2.records.all(), st2.ai)
    assert [r["skill"] for r in blok["zonder_implementatie"]] == ["bestaat_niet_skill"]


def test_referenced_capabilities_leest_use_skill_uit_broncode():
    class Basis:
        def draai(self):
            self.use_skill("site_health", {})

    class Kind(Basis):
        def meer(self):
            self.use_skill("plausible_stats", {})

    caps = skills_catalog.referenced_capabilities(Kind)
    assert caps == {"site_health", "plausible_stats"}       # ook uit de basisklasse


def test_dode_audit_faalt_zacht_zonder_class_map(tmp_path):
    dd, st = _st(tmp_path)
    blok = skills_catalog.niet_gedekt(st.records.all(), st.ai)
    assert isinstance(blok["dood"], list)     # geen crash, ook als geen rol een klasse heeft


# ── Blok 3: gewenst ──────────────────────────────────────────────────────────

def test_gewenst_leest_means_gaps(tmp_path):
    dd, st = _st(tmp_path)
    hi = HumanInbox(str(tmp_path / "hi.json"))
    hi.add_means_gap("gap_meten", "pairs_sold is niet meetbaar in de puls",
                     role_id="analyst", sensed_by="analyst")
    rows = skills_catalog.gewenst(hi)
    assert len(rows) == 1
    assert rows[0]["gap_key"] == "gap_meten" and rows[0]["role"] == "analyst"
    assert "pairs_sold" in rows[0]["beschrijving"]


def test_gewenst_faalt_zacht_zonder_inbox():
    assert skills_catalog.gewenst(None) == []


# ── De pagina ────────────────────────────────────────────────────────────────

def test_pagina_rendert_met_echte_data(tmp_path):
    dd, st = _st(tmp_path)
    _koppel(dd, st)
    hi = HumanInbox(str(tmp_path / "hi.json"))
    hi.add_means_gap("gap_meten", "pairs_sold is niet meetbaar", role_id="analyst")

    page = render_skills(cockpit2._Stores(dd), hi)
    assert "Skills — wat kan het dorp al?" in page
    assert "Uitvoerbaar" in page and "Genoemd maar niet gedekt" in page and "Gewenst" in page
    assert "site_health" in page                    # blok 1 + gebruikersregel
    assert "domein: bibliotheek" in page            # domeinmarkering op keyword_review
    assert "pairs_sold" in page                     # blok 3
    assert "<!doctype" in page.lower()


def test_pagina_gebruikt_geen_inline_styles(tmp_path):
    dd, st = _st(tmp_path)
    page = render_skills(cockpit2._Stores(dd), None)
    # Alles buiten de gedeelde _page/_DS_LINK-basis moet uit bestaande klassen komen.
    from nooch_village.views import skills as skills_view
    src = open(skills_view.__file__, encoding="utf-8").read()
    assert "style=" not in src
