"""Achteraf-formaliseren van de seed/migratie-toevoegingen via de echte governance-poort.

Deterministisch: Gate.check + Secretary._adopt direct, geen threads. Bewijst dat het add_role-
voorstel voor de Concurrent-scout door G0-G4 komt en het record getrouw herbouwt (4 skills,
source=sensed), en dat de Librarian-KE-grant via amend_role idempotent landt."""
from __future__ import annotations
from unittest.mock import patch

from nooch_village.event_bus import EventBus
from nooch_village.governance import Records, Gate, Secretary
from nooch_village.seeds import seed_records, migrate_records
from nooch_village.role_proposals import (
    build_concurrent_scout_proposal, build_grant_skill_proposal,
    build_grant_accountability_proposal)


def _records(tmp_path):
    r = Records(str(tmp_path / "gov.json"))
    seed_records(r)
    migrate_records(r)        # brengt de huidige staat (incl. geseede scout + librarian)
    return r


def test_scout_addrole_passeert_de_poort_en_herbouwt_record(tmp_path):
    r = _records(tmp_path)
    p = build_concurrent_scout_proposal()
    # G4 kan een LLM willen; geen verdachte termen → poort is deterministisch zonder LLM,
    # maar we mocken reason→None voor de zekerheid (fail-closed pad).
    with patch("nooch_village.llm.reason", return_value=None):
        passed, gate, reason = Gate().check(p, r, None)
    assert passed, f"verwacht door de poort, geblokkeerd op {gate}: {reason}"

    Secretary(r, EventBus(name="t"))._adopt(p)
    scout = r.get("concurrent_scout")
    assert scout.source == "sensed"
    assert set(scout.definition.skills) == {
        "competitor_news", "competitor_discover", "linkbuilding_targets", "keywords_everywhere"}
    assert "concurrent_scout" in r.root().members


def test_librarian_ke_grant_passeert_en_is_idempotent(tmp_path):
    r = _records(tmp_path)
    p = build_grant_skill_proposal("librarian", "keywords_everywhere", "formaliseren")
    with patch("nooch_village.llm.reason", return_value=None):
        passed, gate, reason = Gate().check(p, r, None)
    assert passed, f"geblokkeerd op {gate}: {reason}"
    Secretary(r, EventBus(name="t"))._adopt(p)
    lib = r.get("librarian")
    assert "keywords_everywhere" in lib.definition.skills
    # idempotent: geen dubbele entry
    assert lib.definition.skills.count("keywords_everywhere") == 1


def test_website_watcher_locale_accountability_via_governance(tmp_path):
    r = _records(tmp_path)
    p = build_grant_accountability_proposal("website_watcher", "bezoekersdata per locale duiden")
    with patch("nooch_village.llm.reason", return_value=None):
        passed, gate, reason = Gate().check(p, r, None)
    assert passed, f"geblokkeerd op {gate}: {reason}"
    Secretary(r, EventBus(name="t"))._adopt(p)
    ww = r.get("website_watcher")
    assert "bezoekersdata per locale duiden" in ww.definition.accountabilities
