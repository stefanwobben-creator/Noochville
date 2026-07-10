"""App-shell-fundament: de swap-primitive is well-formed, de cleanup-registry zit in de <head> (vóór
content-scripts), de modal delegeert nu i.p.v. per-kaart te binden, en wo_close ververst via de shell.

Plus het afdwingbare cleanup-contract (guard): een shell-genoot content-view mag geen setInterval of
document/window-listener buiten de registry om opzetten — anders lekt/stapelt het over een swap heen.
"""
from __future__ import annotations

import glob
import os
import re

from nooch_village.views.shell import _shell_chrome
from nooch_village.views.projects import _modal_html
from nooch_village.web_base import _SHELL_REGISTRY, _page

_VIEWS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nooch_village", "views")
# Chrome-bestanden: hun listeners/timers zijn bewust persistent (ze worden NIET geswapt) → vrijgesteld.
_CHROME = {"shell.py", "callbar.py", "noochie.py", "__init__.py"}
# Ratchet voor document/window-listeners in content-views. projects.py: de modal-machinerie (popstate +
# keydown) staat BUITEN .c2-main en persisteert → geen swap-teardown nodig. Monotoon dalend naar 0.
_LISTENER_WHITELIST = {"projects.py": 2}
_LISTENER_RE = re.compile(r"(?:document|window)\.addEventListener\(")


def _content_views():
    for full in sorted(glob.glob(os.path.join(_VIEWS, "*.py"))):
        if os.path.basename(full) not in _CHROME:
            yield full


# ── de swap-primitive + registry ────────────────────────────────────────────
def test_registry_stub_in_page_head():
    html = _page("t", "<div class='c2-main'></div>")
    head = html.split("</head>", 1)[0]
    assert "window.registerSwapCleanup" in head and "__swapCleanups" in head   # beschikbaar vóór content
    assert "__swapCleanups" in _SHELL_REGISTRY


def test_shell_chrome_wellformed():
    js = _shell_chrome()
    assert "window.shellSwap" in js and "runCleanups" in js and "reinit" in js
    assert "replaceWith" in js and "document.title" in js                       # .c2-main + title
    assert "scrollTo(0,0)" in js and "focus" in js                             # scroll top + focus bij nieuwe nav
    assert "e.state&&e.state.shell" in js                                       # popstate alleen op shell-entries
    assert "__shellOpenCard" in js and "closest('#ovl')" in js                  # delegatie, in-modal overslaan
    assert "style=" not in js                                                   # geen inline styles


def test_modal_delegeert_en_wo_close_via_shell():
    m = _modal_html("[]")
    assert "window.__shellOpenCard=openCard" in m                              # modal exposeert openCard
    assert "querySelectorAll('.pcard[data-href],a.js-modal[data-href]')" not in m   # geen per-kaart-binding meer
    assert "window.shellSwap(location.href" in m                               # dirty-close ververst via de shell
    assert "location.reload()" in m                                            # ... met reload als fallback


# ── afdwingbaar cleanup-contract ─────────────────────────────────────────────
def test_setinterval_registreert_cleanup():
    """Elke content-view met een setInterval MOET registerSwapCleanup gebruiken (anders lekt de timer
    over een swap heen — de aardbol-bug)."""
    for full in _content_views():
        src = open(full, encoding="utf-8").read()
        if "setInterval(" in src:
            assert "registerSwapCleanup" in src, (
                f"{os.path.basename(full)}: setInterval zonder registerSwapCleanup — registreer een "
                f"teardown, anders draait de timer door na een .c2-main-swap.")


def test_geen_ongeregistreerde_document_listeners_in_content():
    """Ratchet: document/window-listeners in content-views horen in de chrome (views/shell.py) of moeten
    geregistreerd zijn. De whitelist (modal-machinerie buiten .c2-main) daalt monotoon naar 0."""
    for full in _content_views():
        rel = os.path.basename(full)
        count = len(_LISTENER_RE.findall(open(full, encoding="utf-8").read()))
        ceiling = _LISTENER_WHITELIST.get(rel, 0)
        assert count <= ceiling, (
            f"{rel}: {count} document/window-listener(s), plafond {ceiling}. Zet 'm in de shell-chrome "
            f"(views/shell.py) of registreer teardown via registerSwapCleanup; anders overleeft hij een swap.")
        assert count >= ceiling, (
            f"{rel}: {count} < plafond {ceiling} — opgeruimd, verlaag de whitelist (ratchet naar 0).")
