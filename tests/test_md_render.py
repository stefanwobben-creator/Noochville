"""De lichte markdown-renderer _md: per patroon (vet/cursief/doorhalen/kop/link) + HTML-veiligheid.

Vet/lijst bestonden al; cursief, doorhalen, kop en link zijn nieuw. Een link krijgt alleen een
http(s)-schema; alles anders blijft platte (ge-escapte) tekst — fail-closed tegen javascript:-XSS.
"""
from __future__ import annotations

from nooch_village.cockpit2_util import _md


def test_vet_blijft_werken():
    assert "<strong>hoi</strong>" in _md("**hoi**") and "**" not in _md("**hoi**")


def test_cursief():
    out = _md("een *schuin* woord")
    assert "<em>schuin</em>" in out and "*schuin*" not in out


def test_doorhalen():
    out = _md("~~weg~~ hiermee")
    assert "<del>weg</del>" in out and "~~" not in out


def test_kop():
    out = _md("## Kop hier\ngewone regel")
    assert "<h4>Kop hier</h4>" in out and "## " not in out
    assert "gewone regel" in out                              # de regel eronder blijft normaal


def test_link_http_wordt_gelinkt():
    out = _md("zie [Nooch](https://nooch.earth) online")
    assert "<a href='https://nooch.earth' target='_blank' rel='noopener'>Nooch</a>" in out
    assert "[Nooch]" not in out


def test_link_niet_http_geen_link_failclosed():
    # javascript: en interne paden worden NOOIT een link (XSS-veilig); de tekst blijft staan
    js = _md("[klik](javascript:alert(1))")
    assert "<a " not in js and "javascript:alert(1)" in js     # letterlijk, geen href
    intern = _md("[pad](/intern/route)")
    assert "<a " not in intern and "/intern/route" in intern


def test_link_label_ge_escaped():
    out = _md("[<script>x</script>](https://ok.nl)")
    assert "<a href='https://ok.nl'" in out                    # wel gelinkt (http)
    assert "&lt;script&gt;x&lt;/script&gt;" in out and "<script>" not in out   # label veilig


def test_escaping_blijft_intact_met_opmaak():
    out = _md("*a* & <b>")
    assert "<em>a</em>" in out and "&amp;" in out and "&lt;b&gt;" in out and "<b>" not in out


def test_lijst_blijft_werken():
    out = _md("- een\n- twee")
    assert "<ul class='fbul'>" in out and out.count("<li>") == 2


def test_combinatie_kop_met_inline_opmaak():
    out = _md("## Titel met **vet**")
    assert "<h4>Titel met <strong>vet</strong></h4>" in out
