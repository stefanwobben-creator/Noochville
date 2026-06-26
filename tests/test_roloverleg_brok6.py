"""Roloverleg brok 6: chat-kladblok met AI (vervangt AI-per-veld / AI-herziening)."""
from __future__ import annotations

import nooch_village.roloverleg as rov
from nooch_village import cockpit


def _item():
    return {"id": "k1", "kind": "amend_role", "role_id": "scout", "title": "Scout uitbreiden",
            "by": "founder", "status": "open", "reason": "blijft liggen",
            "change": {"add_accountabilities": ["Bewaken van sociale kanalen"]},
            "kladblok": [{"who": "jij", "text": "klopt deze formulering?"},
                         {"who": "ai", "text": "Begin met een werkwoord op -en."}]}


def _snap():
    return {"purpose": "speuren", "name": "scout",
            "accountabilities": ["Spotten van merken"], "domains": []}


def test_kladblok_panel_en_historie():
    page = cockpit.render_roloverleg(_item(), _snap(), [], "t", roles=["scout"])
    assert "Kladblok — chat met de AI" in page
    assert 'value="rov_kladblok"' in page and "kladblok_msg" in page
    # de bestaande conversatie staat in beeld
    assert "klopt deze formulering?" in page and "Begin met een werkwoord" in page
    # de oude AI-herziening (rov_react) is weg
    assert 'value="rov_react"' not in page


def test_add_kladblok_bewaart_bericht(tmp_path):
    ag = rov.Agenda(str(tmp_path / "a.json"))
    iid = ag.add(role_id="scout", kind="amend_role", change={"purpose": "x"}, reason="r", by="scout")
    assert ag.add_kladblok(iid, "jij", "een vraag") is True
    assert ag.add_kladblok(iid, "jij", "   ") is False          # lege tekst telt niet
    assert ag.get(iid)["kladblok"][0]["text"] == "een vraag"
    # herladen vanaf schijf
    assert rov.Agenda(str(tmp_path / "a.json")).get(iid)["kladblok"][0]["who"] == "jij"


def test_kladblok_actie_failsoft_zonder_llm(tmp_path, monkeypatch):
    data = tmp_path / "data"; data.mkdir()
    (data / "governance_records.json").write_text("{}", encoding="utf-8")
    ag = rov.Agenda(str(data / "roloverleg_agenda.json"))
    iid = ag.add(role_id="scout", kind="amend_role", change={"purpose": "x"}, reason="r", by="scout")
    # geen AI beschikbaar → bericht blijft bewaard, ai=False
    monkeypatch.setattr(cockpit, "_kladblok_ai_reply", lambda *a, **k: None)
    res = cockpit._dispatch_action(str(data), "rov_kladblok", iid, "", extra={"kladblok_msg": "hoi"})
    assert res["ok"] is True and res["ai"] is False
    saved = rov.Agenda(str(data / "roloverleg_agenda.json")).get(iid)["kladblok"]
    assert saved[-1]["text"] == "hoi" and saved[-1]["who"] == "jij"


def test_kladblok_leeg_bericht_weigert(tmp_path):
    data = tmp_path / "data"; data.mkdir()
    (data / "governance_records.json").write_text("{}", encoding="utf-8")
    ag = rov.Agenda(str(data / "roloverleg_agenda.json"))
    iid = ag.add(role_id="scout", kind="amend_role", change={"purpose": "x"}, reason="r", by="scout")
    res = cockpit._dispatch_action(str(data), "rov_kladblok", iid, "", extra={"kladblok_msg": "  "})
    assert res["ok"] is False
