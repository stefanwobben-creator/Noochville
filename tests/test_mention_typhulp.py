"""@-typhulp: de lijst die verschijnt als je `@` typt.

WAT DIT WEL IS: typen. Je kiest een naam en er komt PLATTE TEKST in het veld ("@Stefan Wobben ").
WAT DIT NIET IS: een notificatie, een link of een koppeling. Dat is een apart besluit met een
eigen autorisatievraag ("wie mag wie pingen"), en deze route draagt er niets van vooruit — hij
geeft alleen een label en een soort terug, geen id en geen e-mailadres.

DE ENE REGEL DIE HARD MOET ZIJN: geen tweede personenlijst. `mention_hits` roept `_people` en
`_roles` aan, dus wie hier verschijnt is per definitie wie de zoekpagina ook vindt. Een eigen lus
over `st.people.all()` zou de tweede interpretatie zijn die na één wijziging uit de pas loopt —
en daar toetst `test_zelfde_bron_als_de_zoekpagina` letterlijk op.

LET OP, ER IS AL EEN TWEEDE: de projectfeed heeft sinds langer zijn eigen inline autocomplete
(`mentionWire` in `_modal_html`, gevoed door `_mentionables`). Die lijst bevat óók persona-namen
en hangt wél aan notificatie-routering, dus hij is hier bewust NIET op omgezet. Zie de PR.
"""
from __future__ import annotations

import http.client
import json
import os
import threading
from http.server import HTTPServer

from nooch_village import auth as _auth
from nooch_village import cockpit2
from nooch_village.people import PeopleStore
from nooch_village.views import search
from nooch_village.views.search import _people, _roles, mention_hits

EMAIL = "ment@nooch.earth"
CSRF = "TESTTOKEN"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _labels(hits):
    return [h["label"] for h in hits]


# ── 1. Dezelfde bron als de zoekpagina ──────────────────────────────────────────────────────
def test_zelfde_bron_als_de_zoekpagina(tmp_path):
    """Geen tweede personenlijst: elke mens-treffer komt letterlijk uit `_people`."""
    dd, st = _dorp(tmp_path)
    st.people.add("Stefan Wobben", "s@nooch.earth")
    st.people.add("Sanne Vermeer", "sanne@nooch.earth")
    st = cockpit2._Stores(dd)
    uit = [h for h in mention_hits(st, "s") if h["kind"] == "person"]
    assert _labels(uit) == [h["titel"] for h in _people(st, ["s"])]


def test_de_woord_prefix_regel_geldt_ook_hier(tmp_path):
    """`_match` matcht op WOORD-prefix, niet ergens midden in een woord. Dat is geen aparte
    regel voor de typhulp — het is dezelfde functie, en deze test bewijst dat je hem erft."""
    dd, st = _dorp(tmp_path)
    st.people.add("Stefan Wobben", "s@nooch.earth")
    st = cockpit2._Stores(dd)
    assert "Stefan Wobben" in _labels(mention_hits(st, "wob"))      # tweede woord: wel
    assert "Stefan Wobben" not in _labels(mention_hits(st, "obb"))  # midden in een woord: niet


def test_een_gearchiveerde_rol_staat_er_niet_bij(tmp_path):
    """Ook geërfd: `_roles` slaat `archived` over. Een rol die niet meer bestaat hoor je niet
    te kunnen noemen."""
    dd, st = _dorp(tmp_path)
    levend = [h["titel"] for h in _roles(st, [])]
    rec = next(r for r in st.records.all() if not getattr(r, "archived", False))
    rec.archived = True
    st.records.put(rec)
    st.records.save()
    st2 = cockpit2._Stores(dd)
    namen = _labels(mention_hits(st2, "", limiet=99))
    weg = [n for n in levend if n not in [h["titel"] for h in _roles(st2, [])]]
    assert weg, "geen rol gearchiveerd — test zegt niets"
    assert not (set(weg) & set(namen))


# ── 2. Het plafond, en wat erin past ────────────────────────────────────────────────────────
def test_nooit_meer_dan_acht(tmp_path):
    dd, st = _dorp(tmp_path)
    for i in range(20):
        st.people.add(f"Mens {i}", f"m{i}@nooch.earth")
    st = cockpit2._Stores(dd)
    assert len(mention_hits(st, "")) == 8


def test_veel_mensen_duwen_de_rollen_er_niet_uit(tmp_path):
    """DE REDEN DAT ER EEN DEELPLAFOND IS. Twintig mensen die allemaal met een 'm' beginnen
    mogen niet betekenen dat er nul rollen in de lijst staan."""
    dd, st = _dorp(tmp_path)
    for i in range(20):
        st.people.add(f"Mens {i}", f"m{i}@nooch.earth")
    st = cockpit2._Stores(dd)
    soorten = [h["kind"] for h in mention_hits(st, "")]
    assert soorten.count("person") == 5
    assert len(soorten) - 5 == 3


def test_weinig_rollen_laat_de_mensen_de_rest_vullen(tmp_path):
    """En andersom: het deelplafond is een bodem voor rollen, geen dak voor mensen. Zijn er
    geen rollen om mee te vullen, dan blijft de lijst niet op vijf steken."""
    dd, st = _dorp(tmp_path)
    for i in range(20):
        st.people.add(f"Zeldzaam {i}", f"z{i}@nooch.earth")
    st = cockpit2._Stores(dd)
    hits = mention_hits(st, "zeldzaam")
    assert len(hits) == 8 and all(h["kind"] == "person" for h in hits)


def test_mensen_staan_bovenaan(tmp_path):
    dd, st = _dorp(tmp_path)
    st.people.add("Compliance Mens", "c@nooch.earth")
    st = cockpit2._Stores(dd)
    hits = mention_hits(st, "")
    assert hits[0]["kind"] == "person"


def test_net_een_apenstaartje_getypt_geeft_de_eerste_treffers(tmp_path):
    """Lege `q` = je hebt net `@` getypt. Een lege dropdown ziet eruit als kapot."""
    dd, st = _dorp(tmp_path)
    assert mention_hits(st, "")


# ── 3. Wat er NIET uit komt ─────────────────────────────────────────────────────────────────
def test_alleen_label_en_soort(tmp_path):
    """Puur typhulp. `_people` draagt een `id` en een `url`, en die horen hier niet mee te
    liften: wat je invoegt is platte tekst, dus meer dan een naam is niet nodig. Een veld dat
    'vast alvast' wordt meegestuurd is precies hoe een koppeling ongemerkt ontstaat."""
    dd, st = _dorp(tmp_path)
    st.people.add("Stefan Wobben", "s@nooch.earth")
    st = cockpit2._Stores(dd)
    for h in mention_hits(st, ""):
        assert set(h) == {"label", "kind"}, h


# ── 4. De route ─────────────────────────────────────────────────────────────────────────────
def _server(dd):
    sessions = _auth.SessionStore()
    ps = PeopleStore(os.path.join(dd, "people.json"))
    p = ps.add("Stefan Wobben", EMAIL)
    ps.set_password(p.id, _auth.hash_password("geheim1234"), must_change=False)
    tok = sessions.create(EMAIL)
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, CSRF, sessions=sessions))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1], tok


def _get(port, pad, cookie=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", pad, headers=({"Cookie": f"nv_session={cookie}"} if cookie else {}))
    r = conn.getresponse()
    body = r.read().decode("utf-8", "replace")
    ctype = r.getheader("Content-Type") or ""
    conn.close()
    return r.status, ctype, body


def test_de_route_geeft_json(tmp_path):
    dd, _ = _dorp(tmp_path)
    httpd, port, tok = _server(dd)
    try:
        status, ctype, body = _get(port, "/mention-search?q=stef", cookie=tok)
        assert status == 200 and ctype.startswith("application/json")
        hits = json.loads(body)["hits"]
        assert "Stefan Wobben" in _labels(hits)
    finally:
        httpd.shutdown()


def test_de_route_zit_achter_de_login(tmp_path):
    """Namen van mensen en rollen zijn niet publiek. Dezelfde poort als /search, want het is
    letterlijk dezelfde inhoud — maar 'hetzelfde' is hier iets om te toetsen, niet om aan te nemen."""
    dd, _ = _dorp(tmp_path)
    httpd, port, _tok = _server(dd)
    try:
        status, _, _ = _get(port, "/mention-search?q=stef")
        assert status in (302, 303, 403), status
    finally:
        httpd.shutdown()


def test_zonder_q_faalt_de_route_niet(tmp_path):
    dd, _ = _dorp(tmp_path)
    httpd, port, tok = _server(dd)
    try:
        status, _, body = _get(port, "/mention-search", cookie=tok)
        assert status == 200 and isinstance(json.loads(body)["hits"], list)
    finally:
        httpd.shutdown()


# ── 5. Het veld draagt het attribuut, en het component leest het ────────────────────────────
def test_het_messages_schrijfveld_draagt_data_mention(tmp_path):
    from nooch_village.views.messages import render_messages
    from nooch_village import channels
    dd, st = _dorp(tmp_path)
    ik = st.people.add("Stefan Wobben", EMAIL)
    st = cockpit2._Stores(dd)
    k = channels.circle_kanaal("mother_earth")
    html = render_messages(st, ik=ik.id, kanaal=k, csrf_token=CSRF)
    assert "data-mention" in html
    # ... en wel op het SCHRIJFVELD, niet ergens anders op de pagina.
    stuk = html.split("id='msg-tekst'")[1].split(">")[0]
    assert "data-mention" in stuk


def test_het_component_is_bedraad():
    """Een component dat niet in `NV.wire` staat, draait nergens. Dat was hier geen theorie:
    een los gedefinieerde functie is precies hoe een scherm 'niets doet' zonder één foutmelding."""
    js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "nooch_village", "static", "nooch.js"), encoding="utf-8").read()
    wire = js.split("NV.wire = function")[1].split("};")[0]
    assert "mentions(root)" in wire
    assert "[data-mention]" in js
