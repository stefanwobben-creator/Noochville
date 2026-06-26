"""Roloverleg brok 2: accountabilities als losse velden met ✗ + toevoegregel (behandel-scherm)."""
from __future__ import annotations

from nooch_village import cockpit


def _amend_item():
    return {"id": "k1", "kind": "amend_role", "role_id": "scout", "title": "Scout uitbreiden",
            "by": "founder", "status": "open", "reason": "blijft liggen",
            "change": {"add_accountabilities": ["Bewaken van sociale kanalen"]}}


def _snap():
    return {"purpose": "speuren", "name": "scout",
            "accountabilities": ["Spotten van merken"], "domains": []}


def test_accountabilities_zijn_losse_velden_met_kruisje():
    page = cockpit.render_roloverleg(_amend_item(), _snap(), [], "t", roles=["scout"])
    # losse invoervelden i.p.v. één textarea-regel
    assert 'class="tg-in acc-field"' in page
    # bestaande + voorgestelde accountability staan elk in een eigen veld (value=...)
    assert 'value="Spotten van merken"' in page
    assert 'value="Bewaken van sociale kanalen"' in page
    # een ✗-knop om te verwijderen en een toevoeg-knop
    assert "acc-x" in page and "rovAccAdd" in page
    # synct naar het verborgen ed_accs zodat de handler ongewijzigd blijft
    assert 'id="rovedit-accs-hidden"' in page and 'name="ed_accs"' in page


def test_nieuwe_accountability_krijgt_groene_rand():
    page = cockpit.render_roloverleg(_amend_item(), _snap(), [], "t", roles=["scout"])
    # de toegevoegde (voorgestelde) accountability is visueel gemarkeerd (groen)
    i = page.index("Bewaken van sociale kanalen")
    chunk = page[max(0, i - 200):i]
    assert "green-tint" in chunk or "var(--green)" in chunk
