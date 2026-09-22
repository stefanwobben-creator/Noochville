"""Twee naveegjes uit de werkoverleg-ronde: een breedte-cap en een dubbele knoppenrij.

A · HET WERKOVERLEG WAS SMALLER DAN DE REST. `_wo_schil` wrapte `.c2-main` in `.wo-breed`
    (`max-width:1160px`). Op een breed scherm gaf dat een lege strook rechts die geen ander
    nu-scherm heeft — en het valt het hardst op bij de Projects-stap, waar vier kolommen naast
    elkaar juist ruimte willen. De cap kwam mee toen de losse "nog niet geopend"-pagina werd
    opgeheven; hij stond daar als inline `style='max-width:1160px'` en is toen klasse geworden
    in plaats van weggehaald.

B · DE TWEE OVERLEG-KNOPPEN STONDEN TWEE KEER. `_overview_html` bouwde een eigen `.c2-meet`-rij
    met precies dezelfde live-status-check (`_rov_items`, `st.werk.is_open`) die de zijbalk al
    doet via `overleg_items()`. Twee renders van dezelfde knop met dezelfde bron: de ene kan
    wél live tonen en de andere niet, en dan zie je twee knoppen die elkaar tegenspreken.
    Zelfde opruiming als eerder in dit bestand met de dubbele organisatieboom.

Beide tests zijn eerst ROOD geschreven tegen de bestaande code, daarna is de fix gekomen.
"""
from __future__ import annotations

import os
import re

from nooch_village import cockpit2

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = open(os.path.join(BASIS, "nooch_village", "static", "nooch.css"), encoding="utf-8").read()
WO = open(os.path.join(BASIS, "nooch_village", "views", "werkoverleg.py"), encoding="utf-8").read()
OV = open(os.path.join(BASIS, "nooch_village", "views", "overview.py"), encoding="utf-8").read()

C = "mother_earth__nooch"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _main_content(html: str) -> str:
    """Alleen de HOOFDKOLOM: alles vanaf `.c2-main` tot het einde van de wrap. De zijbalk staat
    ervóór, dus wat hier in zit is wat er IN het scherm staat en niet in de navigatie."""
    return html.split("class='c2-main'", 1)[1] if "class='c2-main'" in html else ""


# ── A. De breedte-cap ───────────────────────────────────────────────────────────────────────
def test_het_werkoverleg_pakt_dezelfde_breedte_als_elk_ander_scherm(tmp_path):
    dd = _dd(tmp_path)
    html = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, csrf_token="t")
    assert "wo-breed" not in html
    assert "class='c2-main'" in html


def _zonder_uitleg(bron: str, soort: str) -> str:
    """Commentaar eruit. Anders telt deze test de UITLEG mee waarin staat dat de klasse weg is —
    en die uitleg hoort er juist te staan. (Zelfde val als eerder deze week; nu meteen goed.)"""
    if soort == ".py":
        return "\n".join(r.split("#")[0] for r in bron.splitlines())
    return re.sub(r"/\*.*?\*/", " ", bron, flags=re.S)


def test_de_cap_staat_ook_niet_meer_in_de_stylesheet():
    """Een klasse die nergens meer gerenderd wordt hoort niet in de stylesheet te blijven staan —
    dan komt hij bij de volgende stijlronde weer mee als iets dat bestaat."""
    assert "wo-breed" not in _zonder_uitleg(CSS, ".css")
    assert "wo-breed" not in _zonder_uitleg(WO, ".py")


def test_geen_enkel_ander_scherm_gebruikte_de_cap():
    """De reden dat hij zonder meer weg kon: één renderer, één stylesheet-regel, verder niets."""
    treffers = []
    for map_, _sub, bestanden in os.walk(os.path.join(BASIS, "nooch_village")):
        for b in bestanden:
            soort = os.path.splitext(b)[1]
            if soort in (".py", ".css", ".js"):
                pad = os.path.join(map_, b)
                bron = open(pad, encoding="utf-8").read()
                if "wo-breed" in _zonder_uitleg(bron, soort):
                    treffers.append(os.path.relpath(pad, BASIS))
    assert treffers == [], treffers


# ── B. De dubbele knoppenrij ────────────────────────────────────────────────────────────────
def test_de_overlegknoppen_staan_niet_in_de_hoofdkolom(tmp_path):
    """DIT IS DE TEST DIE HET PUNT VASTLEGT. Tegen de oude code faalt hij op allebei de namen."""
    dd = _dd(tmp_path)
    html = cockpit2.render_node(cockpit2._Stores(dd), C, "overview", csrf_token="t")
    main = _main_content(html)
    assert "Governance meeting" not in main
    assert "Tactical meeting" not in main
    assert "c2-meet" not in main


def test_ze_staan_wel_in_de_zijbalk(tmp_path):
    """Mutatie-controle: de test hierboven zou ook slagen als de knoppen HELEMAAL weg waren.

    OVER DE ECHTE HTTP-WEG, en dat is hier geen luxe: de zijbalk-knoppen zijn een PLAATSHOUDER
    (`_SIDE_OVERLEG`) die `_send` per verzoek invult met de cirkel waar je staat. `render_node`
    alleen levert dus het commentaar-blokje en niet de knoppen — een test op die render zou
    "weg" en "nog niet ingevuld" niet uit elkaar houden."""
    import http.client
    import threading
    from http.server import HTTPServer
    from nooch_village import auth as _auth
    from nooch_village.people import PeopleStore

    dd = _dd(tmp_path)
    ps = PeopleStore(os.path.join(dd, "people.json"))
    p = ps.add("Naveeg Tester", "naveeg@nooch.earth")
    ps.set_password(p.id, _auth.hash_password("geheim1234"), must_change=False)
    sessions = _auth.SessionStore()
    tok = sessions.create("naveeg@nooch.earth")
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessions))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        conn.request("GET", f"/node?id={C}&tab=overview",
                     headers={"Cookie": f"nv_session={tok}"})
        html = conn.getresponse().read().decode("utf-8", "replace")
        conn.close()
    finally:
        httpd.shutdown()
    zijbalk = html.split("class='c2-main'", 1)[0]
    assert "/werkoverleg?circle=" in zijbalk and "/roloverleg2?circle=" in zijbalk
    assert "c2-overleg" in zijbalk
    # ... en in de hoofdkolom staan ze niet, óók niet langs deze weg.
    assert "Governance meeting" not in _main_content(html)


def test_de_eigen_status_check_is_uit_overview_weg():
    """`_rov_items` en `st.werk.is_open` zaten in `render_node` om een knop groen te maken die
    de zijbalk al kleurt. Blijft die check staan, dan is er nog steeds een tweede plek die kan
    gaan afwijken — ook zonder knop eromheen.

    DE EERSTE VERSIE KEEK NAAR `_overview_html`, en dáár heeft die check nooit gestaan: hij zat
    in `render_node`. De test was dus al groen vóór de fix en bleef groen toen ik de check er
    met de hand weer in zette. Een mutatie-controle liet dat zien; nu op de goede functie, en
    over het HELE bestand zodat hij ook een verhuizing naar een andere plek opmerkt."""
    kaal = "\n".join(r.split("#")[0] for r in OV.splitlines())
    assert "_rov_items" not in kaal
    assert "werk.is_open" not in kaal


def test_een_rol_had_die_knoppen_sowieso_nooit(tmp_path):
    """Een rol heeft geen overleg. Dat was al zo en blijft zo — de zijbalk toont ze alleen bij
    een cirkel."""
    dd = _dd(tmp_path)
    rol = next(r for r in cockpit2._Stores(dd).records.all()
               if r.id.endswith("__secretary") and not getattr(r, "archived", False))
    html = cockpit2.render_node(cockpit2._Stores(dd), rol.id, "overview", csrf_token="t")
    assert "Governance meeting" not in _main_content(html)
