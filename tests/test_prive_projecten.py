"""Privé-projecten ("Only for this circle") per leespad, met ECHTE inlogsessies (11 oktober 2026).

Tot nu toe vroegen alleen Messages, My actions en de bijlagen de privé-regel (`mag_project_lezen`).
Het zoeken (Projects, Steps, Messages), het bord en /project?id= toonden een privé-project aan
iedereen die was ingelogd. Nu vraagt elk leespad dezelfde regel (`messages.project_lezer`): een lid
van de cirkel van de eigenaar-rol ziet het, een niet-lid niet (en /project geeft een 404). Een
gewoon project blijft voor iedereen zichtbaar, en guest (auth uit) mag alles.
"""
from __future__ import annotations

import http.client
import re
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2

CIRKEL = "mother_earth__nooch"
ROL = "mother_earth__nooch__financial_controller"          # een rol in die cirkel
LID, BUITEN = "lid@nooch.earth", "buiten@nooch.earth"
TITEL, STAP, BERICHT, OPEN = "Zebraproject", "Kwagga stap", "Okapibericht", "Giraffeproject"


@pytest.fixture
def dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.assign.assign(ROL, "person", st.people.add("Lid Persoon", LID).id)
    st.people.add("Buiten Persoon", BUITEN)
    pid = st.projects.create(ROL, TITEL, "human")
    cl = st.projects.checklist_add(pid, "Plan")
    st.projects.check_add(pid, cl["id"], STAP)
    st.projects.add_comment(pid, BERICHT)
    st.projects.edit(pid, private=True, allow_done=True)
    open_pid = st.projects.create(ROL, OPEN, "human")      # een gewoon project ernaast
    return dd, pid, open_pid


def _server(dd, sessies):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _get(poort, pad, sessie=None):
    c = http.client.HTTPConnection("127.0.0.1", poort, timeout=10)
    c.request("GET", pad, headers={"Cookie": f"nv_session={sessie}"} if sessie else {})
    r = c.getresponse()
    return r.status, r.read().decode()


def _paden(pid):
    q = urllib.parse.quote
    return {
        "zoeken-dropdown: project": (f"/search?q={q(TITEL)}&frag=1", TITEL),
        "zoeken-dropdown: stap": (f"/search?q={q(STAP)}&frag=1", STAP),
        "zoeken-dropdown: bericht": (f"/search?q={q(BERICHT)}&frag=1", BERICHT),
        "zoeken-pagina: project": (f"/search?q={q(TITEL)}", TITEL),
        "zoeken-pagina: stap": (f"/search?q={q(STAP)}", STAP),
        "zoeken-pagina: bericht": (f"/search?q={q(BERICHT)}", BERICHT),
        "bord /projects": ("/projects", TITEL),
        "bord op de cirkel": (f"/node?id={CIRKEL}&tab=projects", TITEL),
    }


@pytest.mark.parametrize("wie, ziet", [(LID, True), (BUITEN, False)])
def test_elk_leespad_volgt_de_privé_regel(dorp, wie, ziet):
    dd, pid, open_pid = dorp
    sessies = _auth.SessionStore()
    httpd = _server(dd, sessies)
    poort, s = httpd.server_address[1], sessies.create(wie)
    try:
        for naam, (pad, merk) in _paden(pid).items():
            status, body = _get(poort, pad, s)
            assert status == 200, naam
            if pad.startswith("/search"):
                # Alleen de TREFFERS: de zoekpagina zet de zoekterm zelf ook in het veld en de titel.
                body = " ".join(re.findall(r"<a class='gs-hit'.*?</a>", body, re.S))
            assert (merk in body) is ziet, f"{naam}: {wie} {'ziet' if ziet else 'ziet niet'} verwacht"
        status, body = _get(poort, f"/project?id={pid}", s)
        assert (status == 200 and TITEL in body) if ziet else (status == 404 and TITEL not in body)
        # het gewone project ernaast blijft voor iedereen zichtbaar, op het bord en via /project
        assert OPEN in _get(poort, "/projects", s)[1]
        assert _get(poort, f"/project?id={open_pid}", s)[0] == 200
    finally:
        httpd.shutdown()


@pytest.mark.parametrize("wie, ziet", [(LID, True), (BUITEN, False)])
def test_het_bord_van_een_lopend_overleg_en_de_persoonslens(dorp, wie, ziet):
    dd, pid, _ = dorp
    st = cockpit2._Stores(dd)
    st.werk.open(CIRKEL)
    lid_id = st.people.by_email(LID).id
    sessies = _auth.SessionStore()
    httpd = _server(dd, sessies)
    poort, s = httpd.server_address[1], sessies.create(wie)
    try:
        for pad in (f"/wo-bord-status?circle={CIRKEL}", f"/werkoverleg?circle={CIRKEL}&step=projecten",
                    f"/person?id={lid_id}&tab=projecten"):
            status, body = _get(poort, pad, s)
            assert status == 200, pad
            assert (TITEL in body) is ziet, pad
    finally:
        httpd.shutdown()


def test_guest_ziet_alles(dorp):
    dd, pid, _ = dorp
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T"))   # auth uit
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        poort = httpd.server_address[1]
        assert TITEL in _get(poort, "/projects")[1]
        assert _get(poort, f"/project?id={pid}")[0] == 200
        assert "gs-hit" in _get(poort, f"/search?q={urllib.parse.quote(STAP)}&frag=1")[1]
    finally:
        httpd.shutdown()


def test_zonder_kijker_blijven_privé_projecten_weg_uit_het_zoeken(dorp):
    """Een interne aanroep zonder gebruiker (de daemon, een test): fail-closed."""
    from nooch_village.views.search import render_search_fragment
    dd, _pid, _ = dorp
    st = cockpit2._Stores(dd)
    assert TITEL not in render_search_fragment(st, TITEL)
    assert OPEN in render_search_fragment(st, OPEN)
