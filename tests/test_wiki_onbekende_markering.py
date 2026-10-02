"""Een `{{X}}` die geen bekende markering is, zegt dat hij onbekend is (2 oktober 2026).

Op prod stond `{{PLIANT}}` op de NFW-pagina: platte tekst, geen link, en niets dat het zei. Links zijn
`[[…]]`; `{{…}}` is alleen voor de afgeleide blokken (`wiki.AFGELEID`). De chip wijst, maar
verandert niets: de bron komt er exact zo uit terug als hij erin ging.
"""
from __future__ import annotations

import pytest

from nooch_village import wiki
from nooch_village.cockpit2_util import _md_naar_bron
from nooch_village.views.wiki import _body_html


def _html(bron):
    return _body_html(bron, [], blokken=True)


def test_een_onbekende_markering_krijgt_de_vraag():
    h = _html("{{PLIANT}}")
    assert "<span class='chip muted'" in h and "did you mean [[PLIANT]]?" in h


@pytest.mark.parametrize("bron", [
    "{{PLIANT}}", "a {{x}} b", "{{PLIANT}}\n[[PLIANT]]", "| a |\n|---|\n| {{y}} |",
])
def test_de_bron_komt_exact_terug(bron):
    """De vraag staat in `data-chrome`: hij gaat nooit mee de opslag in."""
    assert _md_naar_bron(_html(bron)) == bron


@pytest.mark.parametrize("bron", ["a `{{x}}` b", "```\n{{x}}\n```"])
def test_in_code_is_het_een_voorbeeld(bron):
    assert "did you mean" not in _html(bron)
    assert _md_naar_bron(_html(bron)) == bron


def test_een_bekende_markering_blijft_wat_hij_is():
    for naam in wiki.AFGELEID:
        assert "did you mean" not in _html(f"tekst {{{{{naam}}}}} midden")
        assert "did you mean" not in _html(f"{{{{{naam}}}}}")


def test_de_link_in_de_vraag_wordt_zelf_geen_link():
    """De substitutie staat ná die van `[[…]]`; anders werd de vraag een (kapotte) verwijzing."""
    h = _html("{{PLIANT}}")
    assert "data-ref='PLIANT'" not in h
