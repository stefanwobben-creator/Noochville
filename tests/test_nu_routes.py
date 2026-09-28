"""Elke nieuwe route kiest bewust wél of géén designsysteem (27 september 2026).

WAT ER MISGING. `/acties` (#618) en `/tools` (#619) zijn ná fase 9 gebouwd en stonden nooit in
`_NU_ROUTES`. Gevolg: ze kregen `nooch-ui.css` niet, terwijl `/messages` ernaast dat wél kreeg —
precies het beeld "Messages ziet er goed uit, /acties ziet er oud uit". Geen cache, geen halve
deploy, geen tweede worker: een HANDMATIG BIJGEHOUDEN LIJST waar een nieuwe route niet vanzelf
in komt.

Dat is dezelfde klasse fout als het ontbrekende `Cache-Control` en het Nederlandse zinnetje: iets
wat je moet ONTHOUDEN toe te voegen, en dus een keer vergeet. De docstring van `_nu_body` zegt het
zelf al over een eerder gat: "Dat was een gat in deze lijst, geen besluit."

DEZE RATCHET SLUIT DAT. Elke route die een HTML-pagina teruggeeft staat óf in `_NU_ROUTES`, óf
hieronder met een reden. Een route in geen van beide maakt dit rood — dus wie een view toevoegt
moet kiezen, en kan het niet vergeten.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village.cockpit2 import _NU_ROUTES

BRON = (pathlib.Path(__file__).resolve().parents[1] / "nooch_village" / "cockpit2.py").read_text()

#: BEWUST BUITEN HET DESIGNSYSTEEM, met de reden erbij. Deze lijst mag alleen KORTER worden:
#: wie een van deze schermen herbouwt, haalt hem hier weg en zet hem in `_NU_ROUTES`.
BUITEN = {
    # Geen HTML-pagina maar een bestand, fragment of stream — er is geen `<body>` om te scopen.
    "/bijlage": "bestandsdownload",
    "/file": "bestandsdownload",
    "/giphy-zoek": "fragment",
    "/md-preview": "fragment",
    "/mention-search": "fragment",
    "/metric_export": "download (csv)",
    "/nav-paneel": "fragment",
    "/overleg-status": "fragment",
    "/scan-status": "fragment",
    "/context": "platte tekst voor een model",
    "/version": "diagnose-eindpunt voor deploy.sh (JSON, alleen vanaf de machine zelf)",
    # Eigen, bewust losse vormgeving: deze pagina's staan buiten de ingelogde schil.
    "/login": "eigen inline stijl, buiten de schil",
    "/logout": "redirect",
    "/wachtwoord": "eigen inline stijl, buiten de schil",
    # FASE-9-SCHULD. Deze schermen zijn nooit herbouwd; ze staan hier zodat de schuld zichtbaar
    # is en niet als vergeetachtigheid leest. Wie er toch aan werkt, neemt hem mee.
    "/bronnen": "fase-9-schuld",
    "/catalog": "fase-9-schuld",
    "/claims": "fase-9-schuld",
    "/copy-check": "fase-9-schuld",
    "/copy-prompt": "fase-9-schuld",
    "/keywords": "fase-9-schuld",
    "/kpi_new": "fase-9-schuld",
    "/long-term-trends": "fase-9-schuld",
    "/metrics2": "fase-9-schuld",
    "/noochie": "fase-9-schuld",
    "/rapport": "fase-9-schuld",
    "/skills": "fase-9-schuld",
    "/woordenschat": "fase-9-schuld",
}


def _routes() -> set[str]:
    return set(re.findall(r'path == "(/[a-z0-9_-]*)"', BRON))


# ══ De ratchet ═══════════════════════════════════════════════════════════════
def test_elke_route_heeft_een_keuze():
    """DE HELE POINTE. Een nieuwe view staat in `_NU_ROUTES` of in `BUITEN` — niet in geen van
    beide, want dat is precies hoe `/acties` en `/tools` hun vormgeving misten."""
    zwevend = _routes() - set(_NU_ROUTES) - set(BUITEN)
    assert not zwevend, (
        f"route zonder keuze: {sorted(zwevend)}. Zet hem in `_NU_ROUTES` (krijgt het "
        f"designsysteem) of in `BUITEN` in deze toets, met een reden.")


def test_de_uitzonderingen_bestaan_nog():
    """Een route die verdwijnt hoort ook hier weg te gaan; anders dekt de lijst iets af wat er
    niet meer is en verbergt hij de volgende keer een echte vergissing."""
    verdwenen = set(BUITEN) - _routes() - {"/static"}
    assert not verdwenen, f"staat in BUITEN maar bestaat niet meer: {sorted(verdwenen)}"


def test_de_schuld_mag_alleen_korter():
    """Monotone daling, zoals de inline-style-ratchet. Wie een fase-9-scherm herbouwt, verlaagt hem.

    OP DE SCHULD EN NIET OP DE HELE LIJST (28 september 2026). Deze telling stond op `len(BUITEN)`,
    en daarmee mat hij twee verschillende dingen tegelijk: de ACHTERSTAND (schermen die nooit
    herbouwd zijn) en de STRUCTURELE uitzonderingen (een fragment, een download, de loginpagina).
    Een nieuwe fragment-route — `/scan-status` was de eerste — maakte de toets dan rood zonder dat
    er iets aan schuld bij was gekomen, en de enige uitweg was het plafond ophogen. Dan meet een
    ratchet zijn eigen plafond.

    De structurele uitzonderingen worden gedekt door `test_elke_route_heeft_een_keuze` (elke route
    moet erin staan óf in `_NU_ROUTES`) en door `test_de_uitzonderingen_bestaan_nog`."""
    schuld = [r for r, reden in BUITEN.items() if reden == "fase-9-schuld"]
    assert len(schuld) <= 13, f"{len(schuld)} fase-9-schermen — de schuld is gegroeid: {schuld}"


def test_een_route_staat_nooit_in_allebei_de_lijsten():
    """"óf in `_NU_ROUTES`, óf in `BUITEN`" — en niet in allebei. Een route die in beide staat
    leest als een besluit terwijl er twee tegenstrijdige staan; bij het verplaatsen van
    `/decision-coach` bleek dat geen enkele toets dat opmerkte."""
    dubbel = sorted(set(_NU_ROUTES) & set(BUITEN))
    assert not dubbel, f"staat in _NU_ROUTES én in BUITEN: {dubbel}"


def test_de_coach_is_uit_de_schuld_gehaald():
    """Hij stond als fase-9-schuld geparkeerd terwijl hij op dezelfde schil draait als de rest
    (`_DS_LINK`, `_nav()`, `.c2-wrap`). De teller ging van 14 naar 13; de andere dertien zijn een
    eigen klus (besluit Stefan)."""
    assert "/decision-coach" in _NU_ROUTES and "/decision-coach" not in BUITEN


# ══ De twee die het misten ═══════════════════════════════════════════════════
def test_acties_en_tools_krijgen_het_designsysteem_nu_wel():
    for r in ("/acties", "/tools"):
        assert r in _NU_ROUTES, r


def test_acties_ziet_eruit_als_messages():
    """DE MELDING IN ÉÉN TOETS: "Messages ziet er goed uit, /acties ziet er oud uit"."""
    from nooch_village.cockpit2 import _nu_body
    from nooch_village.cockpit2_util import _DS_LINK
    # `_nu_body` hangt de tweede stylesheet ACHTER `_DS_LINK`; zonder die link in de romp is er
    # niets om achter te hangen en meet deze toets alleen de body-klasse.
    romp = f'<html><head>{_DS_LINK}</head><body class="navjs"></body></html>'
    a = _nu_body("/acties", romp)
    m = _nu_body("/messages", romp)
    assert 'class="nu navjs"' in a and 'class="nu navjs"' in m
    assert "nooch-ui.css" in a and "nooch-ui.css" in m


def test_een_route_buiten_de_lijst_krijgt_het_niet():
    """De andere helft: `_nu_body` voegt niets toe waar het niet hoort."""
    from nooch_village.cockpit2 import _nu_body
    from nooch_village.cockpit2_util import _DS_LINK
    romp = f'<html><head>{_DS_LINK}</head><body class="navjs"></body></html>'
    uit = _nu_body("/login", romp)
    assert "nu" not in uit.split('class="')[1].split('"')[0].split()
    assert "nooch-ui.css" not in uit


# ══ /version: waarmee de deploy zichzelf kan controleren ═════════════════════
#
# DE DEPLOY MELDDE "live op <commit>" op grond van ÉÉN health-check: één request, status < 500.
# Dat zegt dat er íéts luistert — niet dat het de zojuist uitgerolde code is. `/version` vertelt
# wat het DRAAIENDE proces in het geheugen heeft, zodat `deploy.sh` dat kan vergelijken met wat
# er op schijf ligt, vóórdat hij "geslaagd" meldt.
def _server():
    """Een draaiende handler op een vrije poort, plus zijn adres."""
    import os
    import tempfile
    import threading
    from http.server import ThreadingHTTPServer

    from nooch_village import auth as _auth
    from nooch_village import cockpit2
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    sessions = _auth.SessionStore(os.path.join(dd, "sessions.json"))
    users = _auth.UserStore(os.path.join(dd, "people.json"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "TOK", sessions, users))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _haal(httpd, pad, headers=None):
    import http.client
    c = http.client.HTTPConnection(*httpd.server_address, timeout=10)
    c.request("GET", pad, headers=headers or {})
    r = c.getresponse()
    body = r.read().decode("utf-8", "replace")
    c.close()
    return r.status, body


def test_version_vertelt_wat_er_draait():
    import json
    httpd = _server()
    try:
        status, body = _haal(httpd, "/version")
        assert status == 200
        d = json.loads(body)
        assert set(d) == {"commit", "ds", "pid"}
        from nooch_village.cockpit2_util import _DS_VERSION
        assert d["ds"] == _DS_VERSION, "de hash komt niet uit het draaiende proces"
    finally:
        httpd.shutdown()


def test_hij_is_onzichtbaar_van_buiten():
    """nginx zet `X-Forwarded-For` op alles wat van buiten komt. Staat die header er, dan is dit
    verzoek geproxied en bestaat het eindpunt niet — zonder dat nginx daar iets voor hoeft te
    doen, want een tweede plek die dit moet afdwingen is een tweede plek die het kan vergeten."""
    httpd = _server()
    try:
        assert _haal(httpd, "/version", {"X-Forwarded-For": "1.2.3.4"})[0] == 404
    finally:
        httpd.shutdown()


def test_hij_heeft_geen_sessie_nodig():
    """Anders moet het deploy-script inloggen om te controleren of de deploy klopte — en dan
    controleert het zichzelf met een inbraak."""
    from nooch_village.cockpit2 import _PUBLIC_GET
    assert "/version" in _PUBLIC_GET
    assert _PUBLIC_GET == {"/version"}, "er staat meer publiek open dan alleen dit"


def test_twaalf_requests_geven_twaalf_keer_hetzelfde():
    """DE CHECK DIE `deploy.sh` DOET. Wisselt de uitvoer, dan serveren er meerdere processen
    verschillende code — en dat is precies de hypothese die anders met de hand moet worden
    uitgesloten."""
    httpd = _server()
    try:
        antwoorden = {_haal(httpd, "/version")[1] for _ in range(12)}
        assert len(antwoorden) == 1, antwoorden
    finally:
        httpd.shutdown()


def test_het_deployscript_gebruikt_hem():
    """De toets die de twee aan elkaar knoopt: zou `/version` bestaan zonder dat de deploy hem
    raadpleegt, dan is dit een eindpunt zonder lezer."""
    sh = (pathlib.Path(__file__).resolve().parents[1] / "scripts" / "deploy.sh").read_text()
    assert "consistentie_ok" in sh
    assert "/version" in sh
    assert "consistentie_ok || return 1" in sh, "hij wordt niet in `alles_gezond` aangeroepen"
    assert 'n=12' in sh, "het aantal herhalingen staat niet vast"
