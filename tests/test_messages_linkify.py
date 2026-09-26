"""Een adres in een chatbericht wordt vanzelf klikbaar (26 september 2026).

Een bericht werd gerenderd als kale, ge-escapete tekst: plak je een adres, dan staat het er als
tekst. In een chat typt niemand `[tekst](url)` — dat is wiki-syntax — dus daar hoort een adres
gewoon te werken.

SCOPE: alleen het bericht-renderpad. `_md` rendert ook de wiki, de reacties en de projectfeed, en
daar bestaat de markdown-syntax al als bewuste keuze.
"""
from __future__ import annotations

import re

from nooch_village.views.messages import _TLDS, linkify
from nooch_village.web_base import _e


def _l(tekst: str) -> str:
    """Zoals de view het doet: eerst escapen, dan linken."""
    return linkify(_e(tekst))


def _hrefs(html: str) -> list[str]:
    return re.findall(r"href='([^']*)'", html)


# ── Wat een link wordt ───────────────────────────────────────────────────────
def test_een_volledig_adres():
    assert _hrefs(_l("kijk op https://nooch.earth maar")) == ["https://nooch.earth"]


def test_ook_zonder_s():
    assert _hrefs(_l("zie http://example.com")) == ["http://example.com"]


def test_www_krijgt_een_schema():
    """Zet je `www.nooch.earth` in een `href`, dan leest de browser dat als een RELATIEF pad en
    land je op `village.nooch.earth/messages/www.nooch.earth`."""
    assert _hrefs(_l("ga naar www.nooch.earth")) == ["https://www.nooch.earth"]


def test_een_kaal_domein_ook():
    assert _hrefs(_l("zie nooch.earth voor meer")) == ["https://nooch.earth"]


def test_een_pad_en_querystring_gaan_mee():
    h = _hrefs(_l("https://x.nl/a/b?c=1"))
    assert h == ["https://x.nl/a/b?c=1"]


def test_een_ampersand_blijft_een_entiteit():
    """Op dit punt staat er al `&amp;`, en dat hoort zo: in een `href`-attribuut is dat de
    correcte schrijfwijze van één ampersand. Zou hij hier terug-ontsnapt worden, dan is het
    attribuut stuk."""
    h = _hrefs(_l("https://x.nl/a?b=1&c=2"))
    assert h == ["https://x.nl/a?b=1&amp;c=2"]


def test_meerdere_adressen_in_een_bericht():
    assert _hrefs(_l("eerst nooch.earth en dan https://x.nl")) == [
        "https://nooch.earth", "https://x.nl"]


def test_hoofdletters_maken_niet_uit():
    assert _hrefs(_l("HTTPS://X.NL")) == ["HTTPS://X.NL"]


def test_elke_tld_uit_de_lijst_werkt():
    for tld in _TLDS:
        assert _hrefs(_l(f"zie proef.{tld} hier")) == [f"https://proef.{tld}"], tld


# ── Wat GEEN link wordt ──────────────────────────────────────────────────────
def test_een_emailadres_niet():
    """`stefan@nooch.earth` mag geen link naar nooch.earth worden — dat is het domein van iemands
    adres, niet een adres dat hij deelde."""
    assert "<a " not in _l("mail stefan@nooch.earth")


def test_een_bestandsnaam_niet():
    """DE REDEN VOOR DE CURATED TLD-LIJST. Met `[a-z]{2,}` worden deze allemaal links."""
    for tekst in ("bestand.txt", "script.js", "index.html", "notities.md", "data.json"):
        assert "<a " not in _l(f"open {tekst} even"), tekst


def test_een_nederlandse_afkorting_niet():
    for tekst in ("o.a.", "i.v.m.", "d.w.z."):
        assert "<a " not in _l(f"dit {tekst} dat"), tekst


def test_een_versienummer_niet():
    assert "<a " not in _l("versie 1.2 en 3.14")


def test_een_onbekende_extensie_niet():
    """FAIL-CLOSED, hetzelfde principe als `_md`, dat een url zonder http(s)-schema bewust niet
    linkt: wat we niet zeker herkennen blijft tekst."""
    assert "<a " not in _l("zie iets.verzonnenextensie")


def test_javascript_wordt_geen_link():
    uit = _l("javascript:alert(1)")
    assert "<a " not in uit and "javascript:" not in _hrefs(uit)


def test_een_los_woord_met_punt_niet():
    assert "<a " not in _l("Klaar. Volgende.")


# ── Leestekens horen bij de zin, niet bij het adres ──────────────────────────
def test_een_punt_aan_het_eind_blijft_buiten_de_link():
    uit = _l("ga naar www.nooch.earth.")
    assert _hrefs(uit) == ["https://www.nooch.earth"]
    assert uit.endswith("</a>.")


def test_uitroepteken_komma_en_vraagteken_ook():
    for teken in ("!", ",", "?", ":", ";"):
        uit = _l(f"zie nooch.earth{teken} ja")
        assert _hrefs(uit) == ["https://nooch.earth"], teken
        assert f"</a>{teken}" in uit


def test_een_aanhalingsteken_ook():
    """Na `_e()` is dat `&#x27;` respectievelijk `&quot;` — entiteiten, geen losse tekens. Knip je
    het `;` eerst weg, dan houd je een kapotte entiteit over."""
    for teken in ("'", '"'):
        uit = _l(f"zie {teken}nooch.earth{teken}")
        assert _hrefs(uit) == ["https://nooch.earth"], teken
        assert "&#x27" not in _hrefs(uit)[0] and "&quot" not in _hrefs(uit)[0]


def test_een_sluithaakje_zonder_openhaakje_gaat_eraf():
    uit = _l("(zie https://x.nl)")
    assert _hrefs(uit) == ["https://x.nl"]


def test_maar_een_haakje_in_de_url_blijft_staan():
    """Een url als `…/Schoen_(kleding)` eindigt écht op een `)`, en die blind afknippen breekt
    hem. Alleen wegknippen wat niet zélf geopend is."""
    url = "https://nl.wikipedia.org/wiki/Schoen_(kleding)"
    assert _hrefs(_l(url)) == [url]


# ── De XSS-discipline ────────────────────────────────────────────────────────
def test_escapen_gebeurt_voor_het_linken():
    """DE VOLGORDE IS DE VEILIGHEID, dezelfde als in `_md`. Andersom zou een bericht met
    `<script>` erin door de linkifier heen gaan en daarna pas ontsmet worden — of erger, niet
    meer."""
    uit = _l("<script>alert(1)</script> en x.com")
    assert "<script>" not in uit and "&lt;script&gt;" in uit
    assert _hrefs(uit) == ["https://x.com"]


def test_de_linkifier_escapet_zelf_niets():
    """Ze krijgt uitvoer van `_e()` en voegt er tags aan toe. Zou ze zelf ook escapen, dan wordt
    `&amp;` tot `&amp;amp;` — dubbel escapen is net zo goed een bug."""
    assert linkify("&amp; blijft &amp;") == "&amp; blijft &amp;"


def test_een_aanhalingsteken_in_de_url_breekt_het_attribuut_niet():
    """Een attribuutwaarde wordt begrensd op het RUWE aanhalingsteken; `&#x27;` is een entiteit en
    sluit hem dus niet af. Deze toets legt vast dat er geen kaal teken in de href komt."""
    uit = _l("https://x.nl/it's")
    for h in _hrefs(uit):
        assert "'" not in h


def test_elke_link_opent_veilig_in_een_nieuw_tabblad():
    uit = _l("zie nooch.earth en https://x.nl")
    assert uit.count("target='_blank'") == 2
    assert uit.count("rel='noopener'") == 2


# ── Het renderpad ────────────────────────────────────────────────────────────
def test_beide_weergaven_van_een_bericht_linkifyen():
    """Bij je EIGEN bericht wordt de tekst vervangen door het inline bewerkveld. Zou het daar
    ontbreken, dan is een link in andermans bericht wel klikbaar en in je eigen niet."""
    import inspect
    from nooch_village.views import messages
    src = inspect.getsource(messages)
    assert src.count("linkify(_e(") == 2, "een van de twee weergaven linkt niet"


def test_de_bewerk_textarea_blijft_kaal():
    """Daar bewerk je de BRON; een `<a>` hoort daar niet in."""
    import inspect
    from nooch_village.views import messages
    veld = inspect.getsource(messages._bewerk_veld)
    ta = veld.split("<textarea")[1].split("</textarea>")[0]
    assert "linkify" not in ta


def test_md_is_niet_aangeraakt():
    """SCOPE. `_md` rendert ook de wiki, de reacties en de projectfeed; daar bestaat
    `[tekst](url)` al als bewuste syntax en een automatische linkifier zou die keuze overrulen."""
    from nooch_village.cockpit2_util import _md
    assert "<a " not in _md("zie nooch.earth"), "_md linkt nu ook automatisch"
    assert "<a " in _md("zie [Nooch](https://nooch.earth)"), "de bestaande syntax is stuk"
