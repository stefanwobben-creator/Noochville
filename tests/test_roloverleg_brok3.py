"""Roloverleg brok 3: wijziging altijd in beeld + 'Voorstel opslaan' weg (consent = neem aan)."""
from __future__ import annotations

from nooch_village import cockpit


def _amend_item():
    return {"id": "k1", "kind": "amend_role", "role_id": "scout", "title": "Scout uitbreiden",
            "by": "founder", "status": "open", "reason": "blijft liggen",
            "change": {"add_accountabilities": ["Bewaken van sociale kanalen"],
                       "purpose": "speuren naar kansen en signalen"}}


def _snap():
    return {"purpose": "speuren", "name": "scout",
            "accountabilities": ["Spotten van merken"], "domains": []}


def test_opslaan_knop_weg():
    page = cockpit.render_roloverleg(_amend_item(), _snap(), [], "t", roles=["scout"])
    assert "Voorstel opslaan" not in page                 # losse opslaan-knop is verdwenen


def test_neem_voorstel_aan_is_de_consent_knop():
    page = cockpit.render_roloverleg(_amend_item(), _snap(), [], "t", roles=["scout"])
    assert "Neem voorstel aan" in page
    assert 'value="rov_consent"' in page
    # de beslis-knop zit ín het bewerk-formulier (zelfde form als de velden)
    i_form = page.index('id="roveditform"')
    i_consent = page.index('value="rov_consent"')
    i_formend = page.index("</form>", i_form)
    assert i_form < i_consent < i_formend


def test_wijziging_altijd_in_beeld():
    page = cockpit.render_roloverleg(_amend_item(), _snap(), [], "t", roles=["scout"])
    # de diff staat als zichtbaar kaartje (niet meer ingeklapt onder 'Meer opties')
    assert "Wat verandert er t.o.v. nu" in page
    assert "Huidige rol" in page and "Na dit voorstel" in page
    # oude purpose doorgestreept → nieuwe purpose getoond
    assert "speuren naar kansen en signalen" in page
