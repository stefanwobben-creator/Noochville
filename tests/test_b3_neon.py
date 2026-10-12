"""B3 fase d (13 oktober 2026): neon is voor de ENE hoofdactie per scherm, en voor signalen.

Besluiten (Stefan, 12 oktober):
  1. Hoofdactie per scherm: `/projects` "+ add project", `/wiki` "New page", `/messages` Send;
     `/open-questions` en de rolpagina geen. Hooguit één neon actie zichtbaar per scherm.
  2. Signalen tellen niet mee (`.c2-navct`, `.msg-nieuw`, de lopende meeting), mits de teller bij 0
     verdwijnt en het element klein is. De selectors staan hieronder in een VASTE lijst.
  3. Een gekozen modus ("by role", filter "All") is zwart met witte tekst; de huidige plek (de
     boom, het actieve nav-item) is --nu-bg-alt met een neon balkje.

DE NEON-GUARD. Elke regel die een vlak neon vult staat hieronder met een reden; een NIEUWE faalt
deze toets, en een die geen neon meer vult moet eraf. Zelfde vorm als de 2px-lijst in
`test_b3_lijn.py`.
"""
from __future__ import annotations

import http.client
import pathlib
import re
import threading
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2, org

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"
CSS = (ROOT / "static" / "nooch.css").read_text(encoding="utf-8")

#: selector → waarom hij een neon vlak mag dragen.
NEON_VULLING = {
    ":root .btn.ok": "de hoofdactie (hooguit één per scherm, zie de schermtoets hieronder)",
    ":root .c2-navct": "signaal: teller in de navigatie (wordt nergens gerenderd, zie hieronder)",
    ":root .msg-kanaal.on .msg-nieuw": "signaal: ongelezen-teller in het open kanaal, weg bij 0",
    ":root .c2-subnav a.c2-overleg--live": "signaal: de lopende meeting, alleen zolang hij loopt",
}


def _blokken(css: str):
    """(selector, declaraties) voor elke regel, ook binnen @media; commentaar weg."""
    kaal = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    kaal = re.sub(r"@media[^{]*\{", " ", kaal)
    for sel, decl in re.findall(r"([^{}]+)\{([^{}]*)\}", kaal):
        yield " ".join(sel.split()), decl


def _neon_vlakken() -> set[str]:
    uit = set()
    for sel, decl in _blokken(CSS):
        if re.search(r"background(?:-color)?\s*:\s*(?:var\(--nu-neon\)|#00ff00\b)", decl, re.I):
            uit.update(s.strip() for s in sel.split(","))
    return uit


def _regel(selector: str) -> str:
    return " ".join(d for s, d in _blokken(CSS) if selector in [x.strip() for x in s.split(",")])


# ── de vaste lijst ──────────────────────────────────────────────────────────

def test_geen_nieuw_neon_vlak():
    nieuw = sorted(_neon_vlakken() - set(NEON_VULLING))
    assert nieuw == [], "een neon vlak buiten de hoofdactie en de signalen: " + ", ".join(nieuw)


def test_de_neon_lijst_veroudert_niet():
    oud = sorted(set(NEON_VULLING) - _neon_vlakken())
    assert oud == [], "haal deze van NEON_VULLING: " + ", ".join(oud)


# ── signalen: klein, en weg bij 0 ───────────────────────────────────────────

def test_de_ongelezen_teller_is_klein_en_verdwijnt_bij_nul():
    assert "font-size: var(--type-12)" in _regel(":root .msg-nieuw")
    code = (ROOT / "views" / "messages.py").read_text(encoding="utf-8")
    assert re.search(r"stip = f\"<span class='msg-nieuw'>.*\" if n else \"\"", code)


def test_de_lopende_meeting_is_alleen_neon_als_hij_loopt():
    code = (ROOT / "cockpit2_util.py").read_text(encoding="utf-8")
    assert "(\" c2-overleg--live\" if live else \"\")" in code


def test_de_nav_teller_wordt_nergens_gerenderd():
    """`.c2-navct` staat in de lijst omdat het besluit hem noemt. Rendert iemand hem ooit, dan moet
    die render ook bij 0 wegvallen — deze toets wijst je daar dan op."""
    for f in [*ROOT.rglob("*.py"), ROOT / "static" / "nooch.js"]:
        assert "c2-navct" not in f.read_text(encoding="utf-8"), f.name


# ── gekozen modus en huidige plek ───────────────────────────────────────────

@pytest.mark.parametrize("selector", [":root .vswitch a.on", ".cat-f.on", ".seg>a.on"])
def test_de_gekozen_modus_is_zwart_met_witte_tekst(selector):
    r = _regel(selector).replace(" ", "")
    assert "background:var(--nu-text)" in r and "color:var(--nu-surface)" in r, selector


def test_de_huidige_plek_is_bg_alt_met_een_neon_balkje():
    for selector in (":root .tree .here", ":root .c2-subnav [aria-current]"):
        r = _regel(selector)
        assert "background: var(--nu-bg-alt)" in r, selector
        assert "var(--nu-neon)" in r and "border-left" in r, selector
    assert "border-left: 3px solid var(--nu-neon)" in _regel(":root .tree .here")


# ── per scherm: hooguit één neon actie ──────────────────────────────────────

class _NeonActies(HTMLParser):
    """Telt `.btn.ok`-elementen die je ziet zonder iets open te klikken: niet binnen een DICHTE
    `<details>`, behalve de `<summary>` zelf (die zie je wél)."""

    def __init__(self):
        super().__init__()
        self.stapel: list[tuple[str, bool]] = []         # (tag, verbergt-zijn-inhoud)
        self.acties: list[str] = []
        self._tekst: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        kl = (a.get("class") or "").split()
        verborgen = any(v for _t, v in self.stapel)
        if tag == "summary" and self.stapel and self.stapel[-1][0] == "details":
            verborgen = any(v for _t, v in self.stapel[:-1])
        if "btn" in kl and "ok" in kl and not verborgen:
            self.acties.append(tag)
            self._tekst = []
        if tag in ("input", "br", "img", "meta", "link", "hr"):
            return
        self.stapel.append((tag, tag == "details" and "open" not in a))

    def handle_endtag(self, tag):
        for i in range(len(self.stapel) - 1, -1, -1):
            if self.stapel[i][0] == tag:
                del self.stapel[i:]
                break
        if self._tekst is not None and tag in ("a", "button", "summary"):
            self.acties[-1] += ":" + "".join(self._tekst).strip()
            self._tekst = None

    def handle_data(self, data):
        if self._tekst is not None:
            self._tekst.append(data)


def _acties(html: str) -> list[str]:
    p = _NeonActies()
    p.feed(html)
    return p.acties


@pytest.fixture
def dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = next(r for r in st.records.all() if not org.is_circle(r) and not r.archived)
    st.projects.create(rol.id, "Een kaart op het bord", "human")
    st.people.add("Iemand", "iemand@nooch.earth")
    return dd, rol.id


def _get(dd, pad, sessies=None, token=None):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=20)
        c.request("GET", pad, headers={"Cookie": f"nv_session={token}"} if token else {})
        r = c.getresponse()
        return r.status, r.read().decode("utf-8")
    finally:
        httpd.shutdown()


def test_projects_heeft_een_neon_actie_add_project(dorp):
    dd, _rol = dorp
    status, html = _get(dd, "/projects")
    assert status == 200
    assert _acties(html) == ["a:＋ add project"]


def test_wiki_heeft_een_neon_actie_new_page(dorp):
    dd, _rol = dorp
    status, html = _get(dd, "/wiki")
    assert status == 200
    assert _acties(html) == ["summary:+ New page"]


def test_open_questions_en_de_rolpagina_hebben_geen_neon_actie(dorp):
    dd, rol = dorp
    for pad in ("/open-questions", f"/node?id={rol}"):
        status, html = _get(dd, pad)
        assert status == 200, pad
        assert _acties(html) == [], pad


def test_messages_heeft_een_neon_actie_send(dorp):
    dd, _rol = dorp
    sessies = _auth.SessionStore()
    token = sessies.create("iemand@nooch.earth")
    status, html = _get(dd, "/messages", sessies, token)
    assert status == 200
    m = re.search(r"href='(/messages\?k=[^'&]+)'", html)
    assert m, "geen kanaal om te openen"
    status, html = _get(dd, m.group(1), sessies, token)
    assert status == 200
    assert _acties(html) == ["button:Send"]


def test_de_uitstel_popover_toont_in_rust_geen_neon():
    """De bootstrap heeft geen open vragen, dus de schermtoets hierboven ziet op /open-questions
    alleen het kader. Deze toets pakt de rij-actie zelf: "Save" zit in een dichte popover en telt
    pas als je hem openklikt — dan is hij de enige neon op het scherm."""
    import types
    from nooch_village.views.open_vragen import uitstel_form
    html = uitstel_form("T", types.SimpleNamespace(id="ATT-1", anchor="rol"), "leverancier", "k", "/open-questions")
    assert "btn ok" in html                                       # het formulier heeft zijn knop
    assert _acties(html) == []
    assert _acties(html.replace("<details class='acard-d'>", "<details class='acard-d' open>")) == ["button:Save"]
