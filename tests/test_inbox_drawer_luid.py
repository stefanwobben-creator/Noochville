"""De drawer meldt wat er misging, in plaats van stil te legen-en-verversen.

DE REGRESSIE DIE DIT AFVANGT (2 sep 2026): vijf deploys op één werkdag herstartten de cockpit.
`SessionStore` en het CSRF-token leven in het procesgeheugen, dus elke openstaande tab kreeg daarna
403 op zijn POST. De drawer keek niet naar de respons: het veld leegde zich, het paneel klapte
dicht, de lijst ververste — en er was niets toegevoegd. Geen fout op het scherm, geen 500 in het
log, geen regel in notifications.json. Vijftien uur lang zag mislukken er precies zo uit als lukken.
"""
from __future__ import annotations

import re

from nooch_village.views.inbox import _IBX_JS, render_inbox_chrome


def test_iedere_post_kijkt_naar_de_status():
    assert "r.ok" in _IBX_JS
    # en niet alleen in ibxRefresh: ook de schrijfweg
    post = _IBX_JS[_IBX_JS.index("function ibxPost"):_IBX_JS.index("function ibxRefresh")]
    assert "r.ok" in post and "throw" in post


def test_een_verlopen_sessie_zegt_wat_de_mens_moet_doen():
    """403 is het geval dat ons opbrak. 'Er ging iets mis' zou hier nutteloos zijn: de handeling is
    herladen en opnieuw inloggen, en dat hoort er letterlijk te staan."""
    assert "403" in _IBX_JS
    assert "session expired" in _IBX_JS and "reload" in _IBX_JS.lower()


def test_de_getypte_tekst_blijft_staan_als_het_mislukt():
    """Leegmaken hoort bij lukken. Wie zijn spanning kwijt is doordat de server 403 gaf, typt hem
    niet nog een keer — dan is de bug erger dan de stilte."""
    sub = _IBX_JS[_IBX_JS.index("function ibxAddSubmit"):]
    sub = sub[:sub.index("function ibxTrash")]
    # het legen zit in de then-tak, en er is een catch die dat NIET doet
    assert ".catch(" in sub
    catch = sub[sub.index(".catch("):]
    assert "t.value=''" not in catch


def test_de_meldregel_staat_in_de_drawer_en_begint_verborgen():
    html = render_inbox_chrome(csrf_token="tok", role_opts="")
    assert "id='ibx-melding'" in html
    rij = re.search(r"<div class='([^']*)' id='ibx-melding'>", html).group(1)
    assert "hide" in rij
    # geen nieuwe klasse-familie: het IS een ibx-sub, met een foutvariant
    assert "ibx-sub" in rij and "ibx-err" in rij


def test_geen_inline_style_in_de_nieuwe_melding():
    html = render_inbox_chrome(csrf_token="tok", role_opts="")
    assert "id='ibx-melding'" in html and "style=" not in html.split("ibx-melding")[0][-200:]
