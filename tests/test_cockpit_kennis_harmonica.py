"""Cockpit UX brok 3: de harmonica voor de kennislaag — links de lijst, rechts het kaartje,
↑/↓ doorlopen, een niet-officieel krabbelveld."""
from __future__ import annotations

from nooch_village import cockpit


def _ins(n):
    return [{"id": f"c{i}", "claim": f"claim {i}", "kind": ("bevinding" if i % 2 else None),
             "strength": "ondersteund"} for i in range(n)]


def test_harmonica_lijst_en_filters():
    page = cockpit.render_kennis(_ins(4), "", "", "t", filt="alle")
    assert "harmonica" in page
    # alle vier in de linkerlijst
    assert "claim 0" in page and "claim 3" in page
    # filters aanwezig met tellingen
    assert "alle (4)" in page and "onbeslist (2)" in page
    # toetsenbordnavigatie ingebakken
    assert "ArrowDown" in page and "keydown" in page


def test_harmonica_filter_onbeslist():
    # filter onbeslist toont alleen kaartjes zonder soort (c0, c2)
    page = cockpit.render_kennis(_ins(4), "", "", "t", filt="onbeslist")
    assert "claim 0" in page and "claim 2" in page
    assert ">claim 1<" not in page          # c1 (bevinding) valt buiten het filter


def test_harmonica_rechterpaneel_en_selectie():
    detail = "<div class='tension'>HET GEKOZEN KAARTJE</div>"
    page = cockpit.render_kennis(_ins(3), detail, "c1", "t", filt="alle")
    assert "HET GEKOZEN KAARTJE" in page    # rechterpaneel toont het detail
    assert "kh-item sel" in page            # gekozen kaartje is gemarkeerd


def test_harmonica_leeg_rechts():
    page = cockpit.render_kennis(_ins(2), "", "", "t")
    assert "Kies links een kaartje" in page


def test_card_detail_scratchveld():
    card = {"id": "c1", "claim": "x", "grounds": "g", "status": "open", "grounding_count": 0,
            "kind": "bevinding", "strength": "ondersteund", "supports": [], "contradicts": []}
    out = cockpit._card_detail(card, [], "t", [], back="/kennis?id=c1", scratch="mijn krabbel")
    assert "note_scratch" in out and "mijn krabbel" in out
    assert "Notitie" in out


def test_scratch_opslaan_en_lezen(tmp_path):
    dd = str(tmp_path)
    cockpit._scratch_save(dd, "c1", "idee A")
    assert cockpit._scratch_load(dd)["c1"] == "idee A"
    # leeg maken verwijdert de sleutel
    cockpit._scratch_save(dd, "c1", "   ")
    assert "c1" not in cockpit._scratch_load(dd)
