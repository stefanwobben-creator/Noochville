"""Taak 3 — het uitvoerbaarheids-stoplicht van de secretaris in het gate-scherm.

Groen = middel aanwezig; oranje = het bestaat in het dorp maar niet bij deze rol; rood = geen
tooling. Puur informatief: de gate blokkeert er NOOIT op.
"""
from __future__ import annotations

from nooch_village import acc_ids, cockpit2, skills_catalog
from nooch_village.gap_classifier import classify_means
from nooch_village.models import Record, RecordType, RoleDefinition


_ROLE = "mother_earth__nooch__website_developer"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _rol(st, rid="proefrol", skills=(), domains=(), accs=("iets doen",)):
    st.records.put(Record(id=rid, type=RecordType.ROLE, parent="mother_earth__nooch",
                          definition=RoleDefinition(purpose="p", accountabilities=list(accs),
                                                    skills=list(skills), domains=list(domains))))
    return st.records.get(rid)


# ── De classificatie (A/B/C) ─────────────────────────────────────────────────

def test_A_eigen_middel_dekt():
    uit, skill, _ = classify_means("de health van de site bewaken",
                                   ["site_health"], ["site_health", "plausible_stats"])
    assert uit == "A" and skill == ""


def test_B_middel_bestaat_maar_niet_bij_deze_rol():
    uit, skill, _ = classify_means("de health van de site bewaken",
                                   [], ["site_health", "plausible_stats"])
    assert uit == "B" and skill == "site_health"


def test_C_geen_enkel_middel_dekt():
    uit, skill, _ = classify_means("kantoorplanten water geven",
                                   [], ["site_health", "plausible_stats"])
    assert uit == "C" and skill == ""


def test_lege_tekst_is_C():
    assert classify_means("", ["site_health"], ["site_health"])[0] == "C"


# ── Het stoplicht (drie kleuren) ─────────────────────────────────────────────

def test_stoplicht_groen(tmp_path):
    dd, st = _st(tmp_path)
    rec = _rol(st, skills=["site_health"])
    u = skills_catalog.uitvoerbaarheid("de health van de site bewaken", rec, st.ai)
    assert u["kleur"] == "groen"


def test_stoplicht_groen_ook_via_koppeling(tmp_path):
    """De kern van de koppelingslaag: een gekoppeld middel telt mee, niet alleen DNA."""
    dd, st = _st(tmp_path)
    rec = _rol(st, accs=["de health van de site bewaken"])
    aid = acc_ids.acc_id_at(rec.definition, 0)
    assert skills_catalog.uitvoerbaarheid(rec.definition.accountabilities[0],
                                          rec, st.ai)["kleur"] == "oranje"
    st.ai.add_link(rec.id, aid, "site_health")
    assert skills_catalog.uitvoerbaarheid(rec.definition.accountabilities[0],
                                          rec, st.ai)["kleur"] == "groen"


def test_stoplicht_oranje_biedt_koppeling(tmp_path):
    dd, st = _st(tmp_path)
    rec = _rol(st)
    u = skills_catalog.uitvoerbaarheid("de health van de site bewaken", rec, st.ai)
    assert u["kleur"] == "oranje" and u["skill"] == "site_health" and u["koppelbaar"] is True


def test_stoplicht_oranje_respecteert_de_domeinpoort(tmp_path):
    """Een beslis-skill mag ook hier niet gekoppeld worden buiten de domeinhouder om."""
    dd, st = _st(tmp_path)
    zonder = _rol(st, rid="zonder_domein")
    u = skills_catalog.uitvoerbaarheid("kandidaat-woorden reviewen als keyword", zonder, st.ai)
    assert u["kleur"] == "oranje" and u["skill"] == "keyword_review"
    assert u["koppelbaar"] is False and "domeinhouder" in u["blokkade"]

    met = _rol(st, rid="met_domein", domains=["bibliotheek"])
    u2 = skills_catalog.uitvoerbaarheid("kandidaat-woorden reviewen als keyword", met, st.ai)
    assert u2["koppelbaar"] is True


def test_stoplicht_rood(tmp_path):
    dd, st = _st(tmp_path)
    u = skills_catalog.uitvoerbaarheid("kantoorplanten water geven", _rol(st), st.ai)
    assert u["kleur"] == "rood" and u["skill"] == ""


# ── In het gate-scherm ───────────────────────────────────────────────────────

def _agendapunt(st, rec):
    st.agenda.add(rec.id, "amend_role", {}, "", by="founder", title="Proefrol")
    return next(i for i in st.agenda.all() if i.get("role_id") == rec.id)


def test_gate_toont_stoplicht_en_blokkeert_niet(tmp_path):
    from nooch_village.views.roloverleg import _rov_member_block, _rov_hard
    dd, st = _st(tmp_path)
    rec = _rol(st, accs=["de health van de site bewaken", "kantoorplanten water geven"])
    item = _agendapunt(st, rec)

    html, hard = _rov_member_block(st, item, csrf="t", back="/x")
    assert "middel bestaat, niet gekoppeld" in html      # oranje
    assert "geen middel" in html                          # rood
    assert "skilllink_add" in html and "means_gap_add" in html
    # Puur informatief: het stoplicht voegt geen enkele harde blokkade toe.
    assert _rov_hard(st, item) == []


def test_koppelknop_uit_de_gate_legt_een_echte_link(tmp_path):
    dd, st = _st(tmp_path)
    rec = _rol(st, accs=["de health van de site bewaken"])
    aid = acc_ids.acc_id_at(rec.definition, 0)
    _, msg = cockpit2.dispatch(dd, "skilllink_add",
                               {"role": [rec.id], "acc_id": [aid], "skill": ["site_health"],
                                "next": ["/x"]}, username="guest")
    assert "gekoppeld" in msg
    st2 = cockpit2._Stores(dd)
    assert [t.skill for t in st2.ai.links_for_role(rec.id)] == ["site_health"]
    # …en het stoplicht springt daarmee op groen.
    assert skills_catalog.uitvoerbaarheid("de health van de site bewaken",
                                          st2.records.get(rec.id), st2.ai)["kleur"] == "groen"


def test_meld_als_means_gap_landt_in_de_inbox(tmp_path):
    from nooch_village.human_inbox import HumanInbox
    dd, st = _st(tmp_path)
    rec = _rol(st)
    _, msg = cockpit2.dispatch(dd, "means_gap_add",
                               {"role": [rec.id], "acc": ["kantoorplanten water geven"],
                                "next": ["/x"]}, username="guest")
    assert "means-gap" in msg
    hi = HumanInbox(f"{dd}/human_inbox.json")
    gaps = [i for i in hi.pending() if i["type"] == "means_gap"]
    assert len(gaps) == 1 and "kantoorplanten" in gaps[0]["context"]["description"]
    # …en verschijnt in blok 3 van de catalogus.
    assert any("kantoorplanten" in r["beschrijving"] for r in skills_catalog.gewenst(hi))


# ── Waarschuwing: deze ronde maakt koppelingen wees ──────────────────────────

def _amend_item(st, rec, *, add=(), remove=()):
    st.agenda.add(rec.id, "amend_role",
                  {"kind": "amend_role", "role_id": rec.id,
                   "add_accountabilities": list(add),
                   "remove_accountabilities": list(remove)},
                  "", by="founder", title="Proefrol")
    return next(i for i in st.agenda.all() if i.get("role_id") == rec.id)


def test_gate_waarschuwt_bij_verweesde_koppelingen(tmp_path):
    from nooch_village.views.roloverleg import _rov_signals
    dd, st = _st(tmp_path)
    rec = _rol(st, accs=["site monitoren", "bezoekersdata duiden"])
    aid = acc_ids.acc_id_at(rec.definition, 0)
    st.ai.add_link(rec.id, aid, "site_health")

    item = _amend_item(st, rec, remove=["site monitoren"])
    msgs = " ".join(s["msg"] for s in _rov_signals(st, item))
    assert "1 koppeling(en) wees" in msgs and "site_health" in msgs


def test_gate_waarschuwt_niet_bij_herformulering(tmp_path):
    """Eén remove + één add = dezelfde belofte, nieuwe woorden: het id reist mee."""
    from nooch_village.views.roloverleg import _rov_signals
    dd, st = _st(tmp_path)
    rec = _rol(st, accs=["site monitoren", "bezoekersdata duiden"])
    st.ai.add_link(rec.id, acc_ids.acc_id_at(rec.definition, 0), "site_health")

    item = _amend_item(st, rec, add=["de gezondheid van de site bewaken"],
                       remove=["site monitoren"])
    msgs = " ".join(s["msg"] for s in _rov_signals(st, item))
    assert "koppeling(en) wees" not in msgs


def test_gate_waarschuwt_niet_zonder_koppelingen(tmp_path):
    from nooch_village.views.roloverleg import _rov_signals
    dd, st = _st(tmp_path)
    rec = _rol(st, accs=["site monitoren", "bezoekersdata duiden"])
    item = _amend_item(st, rec, remove=["site monitoren"])
    assert "koppeling(en) wees" not in " ".join(s["msg"] for s in _rov_signals(st, item))


def test_gate_waarschuwing_telt_ook_autonome_ai_taken(tmp_path):
    """Een verweesde AI-taak is net zo stil kapot als een verweesd middel."""
    from nooch_village.views.roloverleg import _rov_signals
    dd, st = _st(tmp_path)
    rec = _rol(st, accs=["site monitoren", "bezoekersdata duiden"])
    codie = st.personas.add("Codie", skills=["schrijft de code"])
    st.ai.add(rec.id, acc_ids.acc_id_at(rec.definition, 0), codie.id, "schrijft de code")

    item = _amend_item(st, rec, remove=["site monitoren"])
    msgs = " ".join(s["msg"] for s in _rov_signals(st, item))
    assert "1 koppeling(en) wees" in msgs and "Codie" in msgs
