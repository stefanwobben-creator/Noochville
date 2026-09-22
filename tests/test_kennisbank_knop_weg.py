"""De kennisbank-uploadknoppen: een duidelijke 'niet beschikbaar' in plaats van een crash.

WAT ER STUK WAS. De kennisbank-schermen (`/kennisbank`, `/kennisbank/staging`), de atomiser
(`kennisbank_intake` met `kb_intake`/`atomiseer`) en de stores `notes` en `staging` zijn in #516
verwijderd. Drie multipart-acties in `do_POST` bleven achter en riepen die namen gewoon aan:

    kb_intake_pdf     → NameError: name 'kb_intake' is not defined
    kb_atoom_ref_pdf  → AttributeError: '_Stores' object has no attribute 'notes'
    kb_bron_add       → NameError: name 'atomiseer' is not defined

Dat is geen nette 500: de handler valt uit `do_POST` en de verbinding wordt verbroken zónder
antwoord (curl gaf status 000 — reproductie op 22 september 2026 met een PDF mét tekstlaag).

WAT DEZE TESTS VASTZETTEN. Niet dat de knop werkt — de functionaliteit bestaat niet meer en komt
niet terug met een import. Wel dat de drie acties een LEESBAAR antwoord geven, dat de Oracle-kaart
op de rol-pagina zichtbaar uitgeschakeld is in plaats van naar een kale 404 te linken, en dat er
geen view meer naar `/kennisbank` wijst.
"""
from __future__ import annotations

import http.client
import os
import threading
from http.server import HTTPServer

from nooch_village import auth as _auth
from nooch_village import cockpit2
from nooch_village.people import PeopleStore
from nooch_village.views import overview

EMAIL = "kb@nooch.earth"
CSRF = "TESTTOKEN"


def _server(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    ps = PeopleStore(os.path.join(dd, "people.json"))
    p = ps.add("KB Tester", EMAIL)
    ps.set_password(p.id, _auth.hash_password("geheim1234"), must_change=False)
    sessions = _auth.SessionStore()
    tok = sessions.create(EMAIL)
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, CSRF, sessions=sessions))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return dd, httpd, httpd.server_address[1], tok


def _multipart(velden: dict, bestand: tuple | None = None):
    """Een echte multipart-body — de tak die crashte zat achter de multipart-parser, dus een
    urlencoded POST zou er nooit komen."""
    grens = "----kbgrens"
    delen = []
    for k, v in velden.items():
        delen.append(f"--{grens}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n")
    body = "".join(delen).encode()
    if bestand:
        naam, inhoud, soort = bestand
        body += (f"--{grens}\r\nContent-Disposition: form-data; name=\"file\"; "
                 f"filename=\"{naam}\"\r\nContent-Type: {soort}\r\n\r\n").encode() + inhoud + b"\r\n"
    body += f"--{grens}--\r\n".encode()
    return body, f"multipart/form-data; boundary={grens}"


def _pdf_met_tekstlaag() -> bytes:
    """Zonder tekstlaag viel `kb_intake_pdf` al vóór de kapotte regel uit (van_pdf → None), dus
    een leeg PDF-je bewijst niets. Deze heeft een echte content-stream."""
    zin = ("Nooch maakt schoenen zonder leer en zonder plastic. De zool is van natuurlijk "
           "rubber. De bovenkant is van hennep. Productie gebeurt on demand. ") * 4
    regels = [zin[i:i + 90] for i in range(0, len(zin), 90)]
    stroom = ("BT /F1 10 Tf 40 780 Td 12 TL\n"
              + "\n".join(f"({r.replace('(', '').replace(')', '')}) Tj T*" for r in regels)
              + "\nET").encode("latin-1")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stroom) + stroom + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def _post(port, tok, actie, pdf):
    body, ctype = _multipart({"csrf": CSRF, "action": actie, "atom_id": "NOTE-X"},
                             ("bron.pdf", pdf, "application/pdf"))
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("POST", "/action", body=body,
                 headers={"Content-Type": ctype, "Content-Length": str(len(body)),
                          "Cookie": f"nv_session={tok}"})
    r = conn.getresponse()
    r.read()
    loc = r.getheader("Location") or ""
    conn.close()
    return r.status, loc


# ── 1. De drie acties geven antwoord in plaats van de verbinding te verbreken ────────────────
def test_de_drie_kennisbank_acties_geven_een_leesbaar_antwoord(tmp_path):
    """Dit is de regressietest op de crash zelf. Vóór de fix gooide elk van de drie een
    NameError/AttributeError uit `do_POST` en kreeg de client GEEN response (http.client:
    RemoteDisconnected/BadStatusLine). Nu: 303 naar een bestaande pagina."""
    _, httpd, port, tok = _server(tmp_path)
    pdf = _pdf_met_tekstlaag()
    try:
        for actie in ("kb_intake_pdf", "kb_atoom_ref_pdf", "kb_bron_add"):
            status, loc = _post(port, tok, actie, pdf)
            assert status == 303, f"{actie} gaf {status}"
            assert "/kennisbank" not in loc, f"{actie} stuurt nog naar een dood scherm: {loc}"
    finally:
        httpd.shutdown()


def test_het_antwoord_zegt_waarom_en_niet_alleen_dat_er_niets_gebeurde(tmp_path):
    """Een stille redirect naar '/' is ook geen crash, maar laat de mens raden. De melding
    moet zeggen dát het weg is."""
    _, httpd, port, tok = _server(tmp_path)
    try:
        _, loc = _post(port, tok, "kb_intake_pdf", _pdf_met_tekstlaag())
        assert "unavailable" in loc.lower()
        assert "knowledge-base" in loc.lower() or "knowledge base" in loc.lower()
    finally:
        httpd.shutdown()


def test_de_pdf_wordt_niet_meer_weggeschreven(tmp_path):
    """`kb_atoom_ref_pdf` bewaarde de PDF in data/kbref/ vóórdat hij op de kapotte regel stuk
    liep — dus elke mislukte klik liet een bestand achter dat nergens meer aan hing. Geen
    schrijfactie meer nu de tak weg is."""
    dd, httpd, port, tok = _server(tmp_path)
    try:
        _post(port, tok, "kb_atoom_ref_pdf", _pdf_met_tekstlaag())
        assert not os.path.isdir(os.path.join(dd, "kbref"))
    finally:
        httpd.shutdown()


# ── 2. De zichtbare knop: uitgeschakeld mét reden, geen dode link ────────────────────────────
class _Rec:
    def __init__(self, rid):
        self.id = rid
        self.definition = type("D", (), {"domains": []})()


def test_de_oracle_kaart_is_geen_link_meer_maar_toont_waarom():
    html = overview._role_tools_html(_Rec("librarian"))
    assert "Oracle" in html                       # de kaart is er nog: het vermogen is weg, niet verstopt
    assert "href='/kennisbank'" not in html       # maar niet meer klikbaar naar een 404
    assert "not available" in html


def test_een_tool_met_een_scherm_blijft_gewoon_een_link():
    """Mutatie-controle: de test hierboven zou ook slagen als _tool_kaart álles uitschakelde."""
    html = overview._role_tools_html(_Rec("librarian"))
    assert "<a class='card' href='/woordenschat'>" in html


# ── 3. Geen enkele view wijst nog naar het verdwenen scherm ──────────────────────────────────
def _zonder_uitleg(pad: str) -> str:
    """Comments en docstrings eruit: anders telt de guard zijn eigen uitleg mee."""
    import ast
    bron = open(pad, encoding="utf-8").read()
    boom = ast.parse(bron)
    doc = set()
    for n in ast.walk(boom):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            d = ast.get_docstring(n, clean=False)
            if d:
                doc.add(d)
    regels = [r for r in bron.splitlines() if not r.strip().startswith("#")]
    tekst = "\n".join(regels)
    for d in doc:
        tekst = tekst.replace(d, "")
    return tekst


def test_geen_view_linkt_nog_naar_kennisbank():
    basis = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "nooch_village")
    gevonden = []
    for map_, _, bestanden in os.walk(basis):
        for b in bestanden:
            if not b.endswith(".py"):
                continue
            pad = os.path.join(map_, b)
            if "/kennisbank" in _zonder_uitleg(pad):
                gevonden.append(os.path.relpath(pad, basis))
    assert gevonden == [], f"dode link naar /kennisbank in: {gevonden}"
