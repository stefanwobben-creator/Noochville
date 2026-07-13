"""@mention van een AI-persona op de project-wall triggert een eenmalig antwoord van die persona.

Match-regels als de bestaande mention-parsing (rolnaam of persona-naam). De aanleidende comment staat
bovenaan de reply-context. Geen loop (persona-comment triggert nooit), cap op mention_reply_limit,
fail-closed (geen LLM-antwoord → geen post). Mens-notificatie-gedrag blijft ongewijzigd.
De echte LLM wordt gestubd via nooch_village.llm.reason.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2


@pytest.fixture(autouse=True)
def _sync_mention_reply(monkeypatch):
    # De reply-logica (cap / no-loop / fail-closed / prompt) test synchroon; async heeft z'n eigen test.
    monkeypatch.setattr(cockpit2, "_MENTION_REPLY_ASYNC", False)


def _setup(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rid = "mother_earth__nooch__website_developer"
    codie = st.personas.add("Codie")
    st.assign.assign(rid, "persona", codie.id)
    pid = st.projects.create(rid, "Checkout flow", "human")
    return dd, rid, pid, codie


# 1. Mention op een persona → één persona-comment, met de aanleidende vraag in de prompt-context
def test_mention_persona_laat_persona_antwoorden(tmp_path, monkeypatch):
    dd, rid, pid, codie = _setup(tmp_path)
    caps = []
    monkeypatch.setattr("nooch_village.llm.reason",
                        lambda prompt, **k: caps.append(prompt) or "Ik denk mee: meet eerst de conversie.")
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"],
                                        "text": ["@Codie wat vind jij?"], "next": ["/"]}, username="guest")
    log = cockpit2._Stores(dd).projects.get(pid)["log"]
    assert log[-1]["author"] == {"type": "persona", "id": codie.id}
    assert "Ik denk mee" in log[-1]["text"]
    # de aanleidende comment staat expliciet bovenaan de context
    assert caps and "De mens vraagt jou: @Codie wat vind jij?" in caps[-1]


# 2. Mention op een mens → alleen notificatie (ongewijzigd), geen AI-antwoord
def test_mention_mens_alleen_notificatie(tmp_path, monkeypatch):
    dd, rid, pid, codie = _setup(tmp_path)
    person = cockpit2._Stores(dd).people.all()[0]
    called = []
    monkeypatch.setattr("nooch_village.llm.reason", lambda p, **k: called.append(p) or "x")
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"],
                                        "text": [f"@{person.name} kijk even"], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    assert any(n["target_type"] == "person" for n in st.notif.all())     # notificatie zoals altijd
    assert not called                                                    # geen LLM aangeroepen
    assert all(e.get("author", {}).get("type") != "persona" for e in st.projects.get(pid)["log"])


# 3. Een persona-comment met een @mention → geen trigger (geen loop)
def test_persona_comment_met_mention_triggert_niet(tmp_path, monkeypatch):
    dd, rid, pid, codie = _setup(tmp_path)
    called = []
    monkeypatch.setattr("nooch_village.llm.reason", lambda p, **k: called.append(p) or "x")
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": [f"persona:{codie.id}"],
                                        "text": ["@Codie @Website Developer wat denken jullie?"],
                                        "next": ["/"]}, username="guest")
    assert not called                                                    # geen reply-machinerie
    assert len(cockpit2._Stores(dd).projects.get(pid)["log"]) == 1       # alleen de eigen comment


# 4. Drie mentions in één comment → cap op 2 replies
def test_cap_max_twee_replies(tmp_path, monkeypatch):
    dd, rid, pid, codie = _setup(tmp_path)
    st = cockpit2._Stores(dd)
    st.personas.add("Alfa")
    st.personas.add("Beta")
    monkeypatch.setattr("nooch_village.llm.reason", lambda p, **k: "reply")
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"],
                                        "text": ["@Codie @Alfa @Beta allen graag meedenken"],
                                        "next": ["/"]}, username="guest")
    log = cockpit2._Stores(dd).projects.get(pid)["log"]
    persona_replies = [e for e in log if e.get("author", {}).get("type") == "persona"]
    assert len(persona_replies) == 2                                     # 3 genoemd, cap 2


# 5. Geen LLM-antwoord → geen post (fail-closed)
def test_geen_llm_antwoord_geen_post(tmp_path, monkeypatch):
    dd, rid, pid, codie = _setup(tmp_path)
    monkeypatch.setattr("nooch_village.llm.reason", lambda p, **k: None)  # LLM geeft niets terug
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"],
                                        "text": ["@Codie help"], "next": ["/"]}, username="guest")
    log = cockpit2._Stores(dd).projects.get(pid)["log"]
    assert all(e.get("author", {}).get("type") != "persona" for e in log)
    assert len(log) == 1                                                 # alleen de mens-comment


# 6. Async (prod-default): de POST blokkeert niet op de LLM; het antwoord landt via de thread.
def test_async_reply_landt_na_join(tmp_path, monkeypatch):
    dd, rid, pid, codie = _setup(tmp_path)
    monkeypatch.setattr(cockpit2, "_MENTION_REPLY_ASYNC", True)          # overschrijf de sync-fixture
    monkeypatch.setattr("nooch_village.llm.reason", lambda p, **k: "async antwoord")
    import threading
    t = cockpit2._run_mention_reply(cockpit2._Stores(dd), pid, "@Codie hoi")
    assert isinstance(t, threading.Thread)                              # async → joinbare thread, geen int
    t.join(timeout=5)
    log = cockpit2._Stores(dd).projects.get(pid)["log"]
    assert any(e.get("author", {}).get("type") == "persona" and "async antwoord" in e["text"] for e in log)
