"""Messages als chat, niet als prikbord (voorstel, 13 oktober 2026).

Alleen markup en CSS voor dezelfde gegevens:
  - een bericht is een regel zonder rand, met een vulling bij hover of focus;
  - avatar links (ook bij je eigen berichten), naam en tijd op één regel;
  - opeenvolgende berichten van dezelfde persoon gegroepeerd (4px ertussen);
  - acties (reactie toevoegen, Edit, Remove) pas bij hover of focus, op touch achter één knop;
  - een dagscheiding, en een nieuwe dag begint een nieuwe groep;
  - het invoerveld blijft onderaan staan (sticky).
"""
from __future__ import annotations

import time

from nooch_village import cockpit2
from nooch_village.views.messages import render_messages
from tests.test_b3_lijn import _regel
from tests.test_messages_inputbalk import _dorp, _kanaal


def _ts(tekst: str) -> float:
    """Een tijdstip in de zone van de LEZER (dezelfde als de pagina, `cockpit2_util._zone`), niet
    van de machine: CI draait in UTC, en dan valt "middernacht" op een andere dag."""
    import datetime
    from nooch_village.cockpit2_util import _zone
    return datetime.datetime.strptime(tekst, "%Y-%m-%d %H:%M").replace(tzinfo=_zone(None)).timestamp()


def _post(st, k, wie, tekst, at):
    e = st.channels.post(k, tekst, author_type="human", author_id=wie)
    e["at"] = at
    st.channels._save()


def test_een_dagscheiding_en_een_nieuwe_dag_begint_een_nieuwe_groep(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal()
    middernacht = _ts("2026-10-13 00:00")
    _post(st, k, ander, "laat op de avond", middernacht - 60)
    _post(st, k, ander, "net na middernacht", middernacht + 60)    # binnen 5 minuten, andere dag
    h = render_messages(cockpit2._Stores(dd), ik=ik, kanaal=k, csrf_token="t")
    assert h.count("class='msg-dag' role='separator'") == 2
    assert "Monday 12 October 2026" in h and "Tuesday 13 October 2026" in h
    assert "msg-item--volg" not in h                                    # geen groep over de nacht heen


def test_naam_en_tijd_op_een_regel_en_iedereen_links(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal()
    _post(st, k, ik, "van mij", time.time())
    h = render_messages(cockpit2._Stores(dd), ik=ik, kanaal=k, csrf_token="t")
    assert "<b>Ik Zelf</b> <time class='muted' datetime='" in h
    assert "justify-content: flex-start" in _regel(":root .msg-item--ik")
    eigen = _regel(":root .msg-item--ik .msg-body")
    assert "background: none" in eigen and "border: 0" in eigen       # geen bubbel meer


def test_een_bericht_is_een_regel_zonder_rand_met_hover(tmp_path):
    import re
    r = _regel(":root .msg-item")
    zichtbaar = [d for d in re.findall(r"border(?:-[a-z]+)?\s*:\s*[^;]+", r)
                 if "radius" not in d and not re.search(r":\s*0\s*$", d)]
    assert zichtbaar == [], zichtbaar
    # neutraal, niet `--nu-bg-alt` ("huidige plek" in de navigatie); geen nieuw token
    assert "background: var(--nu-border-subtle)" in _regel(":root .msg-item:hover")
    assert "margin-top: 0" in _regel(":root .msg-item--volg")          # gegroepeerd: 4px (padding)


def test_acties_bij_hover_en_focus_en_op_touch_achter_een_knop(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal()
    _post(st, k, ik, "van mij", time.time())
    h = render_messages(cockpit2._Stores(dd), ik=ik, kanaal=k, csrf_token="t")
    acties = h.split("<div class='msg-acties'>", 1)[1]
    assert acties.startswith("<details class='msg-meer'><summary aria-label='Message actions'>")
    assert "value='msg_remove'" in acties                              # Remove staat in de rij
    assert "opacity: 0" in _regel(":root .msg-acties")
    assert "opacity: 1" in _regel(":root .msg-item:hover .msg-acties")
    assert "opacity: 1" in _regel(":root .msg-item:focus-within .msg-acties")
    from tests.test_b3_lijn import CSS
    touch = CSS.split("@media (hover: none) {", 1)[1].split("}\n}", 1)[0]
    assert ":root .msg-acties > :not(.msg-meer) { display: none; }" in touch
    assert ":root .msg-meer[open] ~ * { display: inline-flex;" in touch


def test_het_invoerveld_blijft_onderaan():
    r = _regel(":root .msg-balk")
    assert "position: sticky" in r and "bottom: 0" in r


def test_tekst_blijft_leesbaar_op_de_hover_vulling():
    from tests.test_contrast import _hex, _tokens, ratio
    tk = _tokens()
    for tekst in ("--nu-text", "--nu-muted", "--nu-accent-text"):
        assert ratio(_hex(tk, tekst), _hex(tk, "--nu-border-subtle")) >= 4.5, tekst


def test_edit_en_remove_zijn_stil_in_de_actierij():
    r = _regel(":root .msg-acties .flink")
    assert "border: 0" in r and "background: none" in r
    assert "background: none" in _regel(":root .msg-acties .flink:hover")


def test_de_volledige_datum_staat_in_een_time_element(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal()
    at = _ts("2026-10-13 08:40")
    _post(st, k, ander, "hallo", at)
    h = render_messages(cockpit2._Stores(dd), ik=ik, kanaal=k, csrf_token="t")
    import re
    m = re.search(r"<time class='muted' datetime='(2026-10-13T08:40[+-]\d{4})' title='[^']+'>08:40</time>", h)
    assert m, "geen time-element met datetime in de kop"
    assert "<div class='msg-dag' role='separator'><time datetime='2026-10-13'>Tuesday 13 October 2026</time></div>" in h


def test_elk_bericht_heeft_een_anker_en_zoeken_linkt_ernaar(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal()
    e = st.channels.post(k, "zoekbaar woord", author_type="human", author_id=ander)
    h = render_messages(cockpit2._Stores(dd), ik=ik, kanaal=k, csrf_token="t")
    assert f"id='m-{e['id']}'" in h
    from nooch_village.views.search import _zoek
    resultaten, _fouten = _zoek(cockpit2._Stores(dd), ["zoekbaar"])
    treffers = dict(resultaten)["Messages"]
    assert treffers and treffers[0]["url"].endswith(f"#m-{e['id']}")


def test_de_pagina_opent_bij_het_nieuwste_en_een_anker_wint():
    import pathlib
    js = (pathlib.Path(cockpit2.__file__).parent / "static" / "nooch.js").read_text(encoding="utf-8")
    f = js.split("function gesprekOnderaan()", 1)[1].split("\n  }\n", 1)[0]
    assert "window.location.hash" in f and "getElementById" in f and "return;" in f
    assert "getBoundingClientRect().bottom - window.innerHeight" in f
    assert "gesprekOnderaan();" in js.split("function gesprekOnderaan()", 1)[1]
    # het schermtoetsenbord: bij een kleiner scherm terwijl je typt weer onderaan
    assert "visualViewport" in f and "msg-tekst" in f
    # een luie afbeelding die later laadt: een ResizeObserver, die stopt zodra de lezer zelf iets doet
    assert "ResizeObserver" in f and "wheel" in f and "touchstart" in f
