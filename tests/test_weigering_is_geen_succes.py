"""Een geweigerde actie mag nooit als geslaagd renderen.

HET GEVAL (3 sep 2026): Stefan sleepte projecten naar Done en zag "✓ moved". Er bewoog niets. De
done-handler weigerde correct — `dod_poort` blokkeerde Done zolang het einddocument nog geen
antwoord bevatte. Maar die weigering reist als melding op een 303-redirect; `fetch` volgt die, dus
de status is 200 en de client meldde succes.

VALS SUCCES IS ERGER DAN STILLE MISLUKKING. Wie niets ziet gebeuren kijkt verder; wie "✓ moved"
leest, gelooft het en gaat door.

De poort uit dat verhaal bestaat inmiddels niet meer (ingetrokken 4 sep 2026, zie
tests/test_project_dod_poort.py) — maar deze test gaat niet over die poort. Hij gaat over de vorm
van een weigering, en die vorm moet herkenbaar blijven voor elke andere weigering in de cockpit.
De strings hieronder zijn daarom voorbeelden, geen aanroepen.
"""
from __future__ import annotations

import re

from nooch_village.cockpit2 import is_weigering


def test_de_server_kent_zelf_het_verschil():
    """De client mag hier niet naar raden — de emoji is voor de mens, de markering voor de machine."""
    assert is_weigering("⛔ nog niet af: het einddocument is nog leeg")
    assert is_weigering("✗ unknown outcome")
    assert is_weigering("No access — only the Circle Lead may do this")
    assert is_weigering("Not logged in")
    assert is_weigering("CSRF token invalid")


def test_een_geslaagde_actie_is_geen_weigering():
    for ok in ("✓ afgerond", "✓ moved", "📎 bijlage geupload", "🗑 weggegooid", "", "   "):
        assert not is_weigering(ok), ok


def test_alle_weigeringsvormen_uit_de_code_worden_herkend():
    """Geteld in cockpit2: ✗ 119×, ⛔ 17×, 'No access…'/'Not …' 41×. Zou een vorm hier ontbreken,
    dan rendert die als succes — precies de bug."""
    import pathlib
    src = pathlib.Path("nooch_village/cockpit2.py").read_text(encoding="utf-8")
    meldingen = {m.group(1).strip()
                 for m in re.finditer(r'return [\w.]+, (?:f?)"([^"]{2,80})"', src)}
    weigeringen = [m for m in meldingen if m[0] in ("✗", "⛔") or m.lower().startswith(
        ("no access", "not linked", "no accountability", "not logged in", "csrf"))]
    assert len(weigeringen) > 40, len(weigeringen)
    niet_herkend = [m for m in weigeringen if not is_weigering(m)]
    assert niet_herkend == [], niet_herkend


def test_de_client_leest_de_markering_en_niet_de_emoji():
    """Zou de client op '⛔' sniffen, dan zit de betekenis in een teken dat iemand ooit vervangt."""
    js = _projects_js()
    assert "q.get('ok')!=='0'" in js                  # markering, server-side gezet
    assert "weigering(resp.url)" in js                # en op beide post-takken gebruikt
    assert js.count("weigering(resp.url)") == 2


def test_geen_confetti_op_een_weigering():
    """De weiger-check staat VÓÓR de succes-takken, anders viert het scherm een nee."""
    js = _projects_js()
    # BINNEN de wire()-tak kijken, niet over het hele bestand: de drop-tak staat verderop en
    # zou de volgorde-vraag met een andere treffer beantwoorden.
    blok = js[js.index("fetch('/action',opts)"):js.index("window.__ovlWireForms")]
    assert blok.index("weigering(resp.url)") < blok.index("confetti()")
    # de SUCCES-toast, niet de 'not saved' uit de !resp.ok-tak (die staat er al eerder)
    assert blok.index("weigering(resp.url)") < blok.index("dr){last=dr;}reopen()")


def test_de_kaart_laden_meldt_zijn_eigen_fout():
    """`openCard` had geen enkele respons-controle: een 500 of een login-redirect vulde de kaart
    met een foutpagina, zonder dat iets zich meldde."""
    js = _projects_js()
    blok = js[js.index("function openCard"):js.index("function openCard") + 400]
    assert "if(!r.ok)" in blok and "kon deze kaart niet laden" in blok


def _projects_js() -> str:
    import pathlib
    return pathlib.Path("nooch_village/views/projects.py").read_text(encoding="utf-8")


# ── hetzelfde oppervlak, tweede bestand: de inbox-drawer ──────────────────────────────────────

def _inbox_js() -> str:
    from nooch_village.views.inbox import _IBX_JS
    return _IBX_JS


def test_de_drawer_leest_dezelfde_markering():
    """De drawer kreeg bij #425 een `r.ok`-poort, en die was even blind als die van de projecten:
    hij mat het transport. Een inhoudelijke weigering ("✗ …", "No access — …") kwam als 200 binnen
    en zette de drawer op groen."""
    js = _inbox_js()
    assert "q.get('ok')!=='0'" in js
    assert "ibxWeigering(r.url)" in js


def test_de_weigering_wordt_gecontroleerd_binnen_de_ok_tak():
    """Juist DAAR zit het gat: buiten de ok-tak vangt de bestaande 403-melding het al af."""
    js = _inbox_js()
    blok = js[js.index("function ibxPost"):js.index("function ibxRefresh")]
    assert "if(r.ok){var w=ibxWeigering(r.url);" in blok
    # en hij mag niet stilletjes doorlopen naar succes
    assert blok.index("ibxWeigering(r.url)") < blok.index("ibxMelding('');return r;")


def test_de_getypte_tekst_overleeft_ook_een_inhoudelijke_weigering():
    """`ibxAddSubmit` leegt alleen in de then-tak. Door te throwen bij een weigering blijft de
    spanning staan — dezelfde regel als bij de 403."""
    js = _inbox_js()
    blok = js[js.index("function ibxPost"):js.index("function ibxRefresh")]
    assert "throw new Error('ibxPost geweigerd')" in blok
