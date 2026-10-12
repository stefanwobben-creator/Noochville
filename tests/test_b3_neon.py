"""B3 fase d (13 oktober 2026): neon is voor de ENE hoofdactie per scherm, en voor signalen.

Besluiten (Stefan, 12 oktober):
  1. Hoofdactie per scherm: `/projects` "+ add project", `/wiki` "New page", `/messages` Send;
     `/open-questions` en de rolpagina geen. Hooguit één neon actie zichtbaar per scherm.
  2. Signalen tellen niet mee (`.c2-navct`, `.msg-nieuw`, de lopende meeting), mits de teller bij 0
     verdwijnt en het element klein is. De selectors staan hieronder in een VASTE lijst.
  3. Een gekozen modus ("by role", filter "All") is zwart met witte tekst; de huidige plek (de
     boom, het actieve nav-item) is --nu-bg-alt met een neon balkje.
  4. (13 oktober) Een GEOPENDE popover of dialoog is een eigen context met hooguit één neon actie.
     "Save" in de Defer-popover blijft dus neon. Op een wikipagina zijn de herhaalde acties per
     feit ("I checked this", "Check again with an answer") secundair; de knop ín de popover die
     zo'n opener opent, blijft de ene neon actie van die popover.

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
    """Telt `.btn.ok`-elementen per CONTEXT.

    Context 0 is het scherm in rust: wat je ziet zonder iets open te klikken. Elke dichte
    `<details>` en elk element met `hidden` is een eigen context (een popover, een dialoog, de
    bewerkbalk): wat erin staat zie je pas als je hem opent. De `<summary>` van een details hoort bij
    de context eromheen — die zie je wél. Een `<details open>` verbergt niets."""

    def __init__(self):
        super().__init__()
        self.stapel: list[dict] = []
        self.per_context: dict[int, list[str]] = {}
        self._volgnr = 0
        self._open: tuple[int, list[str]] | None = None   # (context, tekst) van de knop die loopt

    def _context(self, tag: str) -> int:
        """De binnenste verbergende ouder; de summary van een details telt bij de context erbuiten."""
        for i in range(len(self.stapel) - 1, -1, -1):
            f = self.stapel[i]
            if f["verbergt"]:
                in_summary = (tag == "summary" and i == len(self.stapel) - 1) or (
                    i + 1 < len(self.stapel) and self.stapel[i + 1]["tag"] == "summary")
                if f["tag"] == "details" and in_summary:
                    continue
                return f["nr"]
        return 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        kl = (a.get("class") or "").split()
        if "btn" in kl and "ok" in kl:
            ctx = self._context(tag)
            self.per_context.setdefault(ctx, []).append(tag)
            self._open = (ctx, [])
        if tag in ("input", "br", "img", "meta", "link", "hr"):
            return
        verbergt = (tag == "details" and "open" not in a) or "hidden" in a
        self._volgnr += 1
        self.stapel.append({"tag": tag, "verbergt": verbergt, "nr": self._volgnr})

    def handle_endtag(self, tag):
        for i in range(len(self.stapel) - 1, -1, -1):
            if self.stapel[i]["tag"] == tag:
                del self.stapel[i:]
                break
        if self._open is not None and tag in ("a", "button", "summary"):
            ctx, tekst = self._open
            self.per_context[ctx][-1] += ":" + "".join(tekst).strip()
            self._open = None

    def handle_data(self, data):
        if self._open is not None:
            self._open[1].append(data)


def _contexten(html: str) -> dict[int, list[str]]:
    p = _NeonActies()
    p.feed(html)
    return p.per_context


def _acties(html: str) -> list[str]:
    """De neon acties op het scherm in rust."""
    return _contexten(html).get(0, [])


def _te_veel(html: str) -> dict[int, list[str]]:
    """Elke context (het scherm, of een geopende popover/dialoog) met meer dan één neon actie."""
    return {k: v for k, v in _contexten(html).items() if len(v) > 1}


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


# ── wikipagina: herhaalde acties per feit zijn secundair (B3 PR 3, eerste commit) ──────────────

def _wikipagina(tmp_path, bom: bool):
    """Een pagina met drie feiten met een bron. `bom=True`: een materiaalpagina van /bom, waar
    nakijken een popover met vragen is ("I checked this" / "Check again with an answer");
    anders de losse "I checked this"-knop."""
    from nooch_village import wiki
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = "mother_earth__nooch__creator_of_shoes"
    feiten = [wiki.maak_feit(f"Feit {i}", soort="bron", url=f"https://example.org/{i}") for i in range(3)]
    feiten[2]["gezien"] = {"door": "Stefan", "op": "2026-10-06"}        # al nagekeken → "Check again"
    a = st.att.add(rol, "note", title="Full Green", body="## Conclusion\n\nSome text.",
                   meta={"feiten": feiten})
    if bom:
        st.bom_materialen.zet("Insole", "Full Green")
    from nooch_village.views.wiki import render_pagina
    return render_pagina(cockpit2._Stores(dd), a.id, csrf_token="T", username="guest")


@pytest.mark.parametrize("bom", [False, True], ids=["los-feit", "bom-materiaal"])
def test_een_wikipagina_toont_hooguit_een_neon_actie(tmp_path, bom):
    html = _wikipagina(tmp_path, bom)
    assert "Feit 0" in html and ("I checked this" in html or "Check again" in html)
    assert len(_acties(html)) <= 1, _acties(html)


@pytest.mark.parametrize("bom", [False, True], ids=["los-feit", "bom-materiaal"])
def test_elke_popover_op_een_wikipagina_heeft_hooguit_een_neon_actie(tmp_path, bom):
    html = _wikipagina(tmp_path, bom)
    assert _te_veel(html) == {}
    if bom:                                   # de knop ín de nakijk-popover blijft de neon actie
        assert any(v == ["button:Check"] for k, v in _contexten(html).items() if k)


def test_elke_context_op_de_hoofdschermen_heeft_hooguit_een_neon_actie(dorp):
    dd, rol = dorp
    for pad in ("/projects", "/wiki", "/open-questions", f"/node?id={rol}"):
        _status, html = _get(dd, pad)
        assert _te_veel(html) == {}, pad
