"""Roloverleg brok 4: Secretaris-check vóór consent — bij een 🔴 'blok' staat de knop op slot."""
from __future__ import annotations

from nooch_village import cockpit


def _item():
    return {"id": "k1", "kind": "amend_role", "role_id": "scout", "title": "Scout uitbreiden",
            "by": "founder", "status": "open", "reason": "blijft liggen",
            "change": {"add_accountabilities": ["Bewaken van sociale kanalen"]}}


def _snap():
    return {"purpose": "speuren", "name": "scout",
            "accountabilities": ["Spotten van merken"], "domains": []}


def test_blok_zet_consent_op_slot():
    issues = [{"level": "blok", "msg": "accountability bestaat al bij rol 'librarian'"}]
    page = cockpit.render_roloverleg(_item(), _snap(), issues, "t", roles=["scout"])
    assert "geen consent mogelijk" in page
    assert "disabled" in page                              # de consent-knop is uitgeschakeld
    assert "🔒 Neem voorstel aan" in page
    assert "accountability bestaat al bij rol" in page


def test_let_op_blokkeert_consent_niet():
    issues = [{"level": "let op", "msg": "begint niet met -en-vorm"}]
    page = cockpit.render_roloverleg(_item(), _snap(), issues, "t", roles=["scout"])
    assert "disabled" not in page                          # advies, geen slot
    assert "✓ Neem voorstel aan" in page
    assert "advies, consent kan" in page


def test_geen_issues_consent_kan():
    page = cockpit.render_roloverleg(_item(), _snap(), [], "t", roles=["scout"])
    assert "disabled" not in page and "✓ Neem voorstel aan" in page
    assert "consent kan" in page


def test_server_weigert_consent_bij_blok(tmp_path, monkeypatch):
    # Server-side poort: ook al is de knop disabled in de UI, een POST moet geweigerd worden
    # zolang de Secretaris een blok ziet.
    import nooch_village.roloverleg as rov
    data = tmp_path / "data"; data.mkdir()
    (data / "governance_records.json").write_text("{}", encoding="utf-8")
    agenda = rov.Agenda(str(data / "roloverleg_agenda.json"))
    iid = agenda.add(role_id="scout", kind="amend_role",
                     change={"add_accountabilities": ["Spotten van merken"]},
                     reason="test", by="scout")
    monkeypatch.setattr(rov, "secretary_check",
                        lambda item, records: [{"level": "blok", "msg": "dubbel bij andere rol"}])
    res = cockpit._dispatch_action(str(data), "rov_consent", iid, "", extra={})
    assert res["ok"] is False and "blokkeert" in res["error"].lower()
    assert agenda.get(iid)["status"] == "open"             # niet op consented gezet
