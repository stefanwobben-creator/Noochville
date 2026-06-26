"""Roloverleg brok 1: of/of-dropdown (nieuwe rol als eerste optie) + huidige rol in beeld."""
from __future__ import annotations

from nooch_village import cockpit


def test_dropdown_of_of_nieuwe_rol_eerste_optie():
    ov = cockpit.render_roloverleg_overview(
        [], [], ["scout", "librarian"], "t",
        role_snaps={"scout": {"purpose": "speuren", "accountabilities": ["Spotten van merken"]}})
    # placeholder dwingt een keuze af, en '➕ Nieuwe rol/cirkel' staat vóór de bestaande rollen
    assert "kies: nieuwe of bestaande rol" in ov
    i_new = ov.index("Nieuwe rol/cirkel")
    i_scout = ov.index(">scout<")
    assert i_new < i_scout                      # nieuwe rol staat eerst (of/of)


def test_huidige_rol_snapshot_in_beeld():
    ov = cockpit.render_roloverleg_overview(
        [], [], ["scout"], "t",
        role_snaps={"scout": {"purpose": "speuren naar kansen",
                              "accountabilities": ["Spotten van nieuwe merken"]}})
    # de referentie-panelen + de snapshot-data zitten in de pagina (JS vult ze bij keuze)
    assert "Huidige rol (referentie)" in ov
    assert "speuren naar kansen" in ov and "Spotten van nieuwe merken" in ov
    # of/of-toggle aanwezig
    assert "rovToggle" in ov and "rovcur" in ov


def test_geen_snapshots_blijft_werken():
    # zonder role_snaps mag het niet breken (read-only / lege governance)
    ov = cockpit.render_roloverleg_overview([], [], ["scout"], "t")
    assert "ROVSNAP" in ov and 'value="rov_add"' in ov
