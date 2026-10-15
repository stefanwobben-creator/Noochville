"""Wiki-feiten: één primaire knop, de rest achter ⋯, "Counts for" als chip, en "+ Add fact" per vraag
(besluit Stefan, 15 oktober 2026).

- Per feit één primaire knop: "Check" (nog niet nagekeken) of "Re-check". Edit (de bestaande
  `inline_edit_knop`), Undo check en Remove (met bevestiging) staan achter ⋯; Escape sluit dat menu.
- "Counts for" is een chip naast de bron; telt het nergens, dan een gedimde chip "No question yet".
- "+ Add fact" bij elke vraag: het bestaande `pagina_feit_add` met de vraag voorgekozen. Meteen
  nakijken kan alleen MET een bron (link, bestand of first-hand); zonder bron komt het feit ongecheckt
  binnen. Een check ontstaat nooit vanzelf.
"""
from __future__ import annotations

import http.client
import pathlib
import shutil
import subprocess
import threading
import uuid
from http.server import HTTPServer

import pytest

from nooch_village import auth as _auth
from nooch_village import cockpit2, wiki, wiki_dekking as wd
from nooch_village.views.wiki import render_pagina

from tests.test_w1_antwoorden import _cel, _check, _feit, _pagina


def _feiten(dd, aid):
    return wiki.feiten(cockpit2._Stores(dd).att.get(aid))


def _voeg_toe(dd, aid, **v):
    form = {"aid": [aid], "next": ["/"], **{k: [w] for k, w in v.items()}}
    return cockpit2.dispatch(dd, "pagina_feit_add", form, username="guest")[1]


# ── + Add fact per vraag ──────────────────────────────────────────────────────

def test_toevoegen_met_link_en_vinkje_checkt_voor_die_vraag(tmp_path):
    dd, aid = _pagina(tmp_path, [])
    msg = _voeg_toe(dd, aid, tekst="Contains 30% PLA", soort="bron", url="https://lta.example/tds",
                    vraag="plastic", nakijken="1", antwoord_plastic="yes")
    assert msg.endswith("and checked")
    f = _feiten(dd, aid)[0]
    assert wiki.antwoorden(f) == [{"vraag": "plastic", "waarde": "yes"}]
    assert _cel(dd, "plastic")["status"] == wd.GECHECKT


def test_zonder_bron_komt_het_feit_altijd_ongecheckt_binnen(tmp_path):
    dd, aid = _pagina(tmp_path, [])
    msg = _voeg_toe(dd, aid, tekst="Someone said it is plastic-free", soort="bron", url="",
                    vraag="plastic", nakijken="1", antwoord_plastic="no")
    assert "not checked" in msg
    f = _feiten(dd, aid)[0]
    assert not wiki.nagekeken(f) and _cel(dd, "plastic")["status"] != wd.GECHECKT


def test_zonder_vinkje_ook_met_bron_ongecheckt(tmp_path):
    dd, aid = _pagina(tmp_path, [])
    _voeg_toe(dd, aid, tekst="ISO 14001", soort="bron", url="https://x.example", vraag="cert",
              antwoord_cert="yes")
    assert not wiki.nagekeken(_feiten(dd, aid)[0])


def test_first_hand_draagt_de_naam_uit_de_sessie(tmp_path):
    dd, aid = _pagina(tmp_path, [])
    _voeg_toe(dd, aid, tekst="I visited the plant", soort="attested", ref="iemand anders",
              vraag="plastic", nakijken="1", antwoord_plastic="no")
    f = _feiten(dd, aid)[0]
    assert f["grond"]["soort"] == "attested" and f["grond"]["ref"] == "iemand anders"
    _voeg_toe(dd, aid, tekst="Second visit", soort="attested", vraag="animal")
    g = _feiten(dd, aid)[1]
    assert g["grond"]["ref"]                                     # niet leeg: de naam uit de sessie


def test_het_formulier_staat_bij_elke_vraag_met_het_vinkje_uit(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "x")])
    h = render_pagina(cockpit2._Stores(dd), aid, csrf_token="t", username="guest")
    blok = h.split("id='vraag-plastic'", 1)[1].split("<div class='wiki-inline' id='vraag-", 1)[0]
    assert "<summary class='flink'>+ Add fact</summary>" in blok and "data-bron-poort" in blok
    assert "name='vraag' value='plastic'" in blok and "value='pagina_feit_add'" in blok
    assert "name='nakijken' value='1' disabled>" in blok
    assert "enctype='multipart/form-data'" in blok and "name='file'" in blok
    co2 = h.split("id='vraag-co2'", 1)[1]
    assert "name='grootheid' value='co2e_per_kg'" in co2 and 'name="getal"' in co2


def test_een_bestand_als_bron_via_de_echte_server(tmp_path):
    """Het formulier is multipart; de server zet het bestand bij de pagina en het feit wijst ernaar."""
    dd, aid = _pagina(tmp_path, [])
    sessies = _auth.SessionStore()
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        b = uuid.uuid4().hex
        velden = {"csrf": "T", "action": "pagina_feit_add", "aid": aid, "next": "/", "vraag": "cert",
                  "tekst": "GOTS certificate", "soort": "bron", "nakijken": "1", "antwoord_cert": "yes"}
        body = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                        for k, v in velden.items())
        body += (f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="gots.pdf"\r\n'
                 f'Content-Type: application/pdf\r\n\r\n').encode() + b"%PDF-1.4 test\r\n" + f"--{b}--\r\n".encode()
        c = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        c.request("POST", "/action", body, {"Cookie": f"nv_session={sessies.create('guest')}",
                                            "Content-Type": f"multipart/form-data; boundary={b}"})
        r = c.getresponse(); r.read()
    finally:
        httpd.shutdown()
    f = _feiten(dd, aid)[0]
    assert f["grond"]["soort"] == "document" and f["grond"]["url"].startswith("on file: ")
    assert wiki.antwoorden(f) == [{"vraag": "cert", "waarde": "yes"}]


# ── één primaire knop, de rest achter ⋯, chips ──────────────────────────────

def _blok(h, fid):
    """Alleen het feit zelf: tot het volgende feit, de volgende vraag of het "+ Add fact"-paneel."""
    b = h.split(f"id='feit-{fid}'", 1)[1]
    for grens in ("id='feit-", "id='vraag-", "<summary class='flink'>+ Add fact</summary>"):
        b = b.split(grens, 1)[0]
    return b


def test_primaire_knop_check_dan_re_check_en_de_rest_achter_het_menu(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "Contains PLA")])
    h = render_pagina(cockpit2._Stores(dd), aid, csrf_token="t", username="guest")
    b = _blok(h, "F1")
    assert "<summary class='btn sm'>Check</summary>" in b and "Re-check" not in b
    menu = b.split("<details class='acard-d' data-esc><summary class='flink' aria-label='More actions'", 1)[1]
    assert ">Edit</button>" in menu and ">Remove</button>" in menu and "Undo check" not in menu
    assert "confirm('Remove this fact?')" in menu                      # bevestiging blijft
    _check(dd, aid, "F1", plastic="yes")
    b = _blok(render_pagina(cockpit2._Stores(dd), aid, csrf_token="t", username="guest"), "F1")
    assert "<summary class='btn sm'>Re-check</summary>" in b and ">Undo check</button>" in b
    # nog steeds maar één primaire knop (btn) per feit
    assert b.count("class='btn sm'") == 1                              # alleen de primaire knop


def test_counts_for_is_een_chip_en_nergens_is_gedimd(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "Contains PLA"), _feit("F2", "Weight")])
    _check(dd, aid, "F1", plastic="yes")
    h = render_pagina(cockpit2._Stores(dd), aid, csrf_token="t", username="guest")
    assert "<span class='chip' title='Counts for Contains plastic?: yes'>Contains plastic?: yes</span>" in h
    assert ("<span class='chip muted' title='Counts for nothing: choose a question when you check "
            "it'>No question yet</span>") in _blok(h, "F2")
    assert "Counts for nothing:" not in h.replace("title='Counts for nothing:", "")


def test_een_lezer_ziet_geen_knoppen(tmp_path):
    dd, aid = _pagina(tmp_path, [_feit("F1", "x")])
    h = render_pagina(cockpit2._Stores(dd), aid, csrf_token="", username="guest")
    assert "More actions" not in h and "<summary class='flink'>+ Add fact</summary>" not in h


def test_menu_en_bronpoort_in_javascript():
    node = shutil.which("node")
    if not node:
        pytest.skip("node niet geïnstalleerd")
    t = pathlib.Path(__file__).resolve().parent / "js" / "feit_menu.test.js"
    uit = subprocess.run([node, str(t)], capture_output=True, text=True, timeout=60)
    assert uit.returncode == 0, uit.stdout + uit.stderr
