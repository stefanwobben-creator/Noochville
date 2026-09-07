"""Roloverleg brok 6: chat-kladblok met AI (vervangt AI-per-veld / AI-herziening)."""
from __future__ import annotations

import nooch_village.roloverleg as rov



def _item():
    return {"id": "k1", "kind": "amend_role", "role_id": "scout", "title": "Scout uitbreiden",
            "by": "founder", "status": "open", "reason": "blijft liggen",
            "change": {"add_accountabilities": ["Bewaken van sociale kanalen"]},
            "kladblok": [{"who": "jij", "text": "klopt deze formulering?"},
                         {"who": "ai", "text": "Begin met een werkwoord op -en."}]}


def _snap():
    return {"purpose": "speuren", "name": "scout",
            "accountabilities": ["Spotten van merken"], "domains": []}




def test_add_kladblok_bewaart_bericht(tmp_path):
    ag = rov.Agenda(str(tmp_path / "a.json"))
    iid = ag.add(role_id="scout", kind="amend_role", change={"purpose": "x"}, reason="r", by="scout")
    assert ag.add_kladblok(iid, "jij", "een vraag") is True
    assert ag.add_kladblok(iid, "jij", "   ") is False          # lege tekst telt niet
    assert ag.get(iid)["kladblok"][0]["text"] == "een vraag"
    # herladen vanaf schijf
    assert rov.Agenda(str(tmp_path / "a.json")).get(iid)["kladblok"][0]["who"] == "jij"




