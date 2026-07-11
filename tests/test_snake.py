"""'De Veter' snake-easter-egg: eigen store (higher-only), score onder de sessie-gebruiker (nooit een
meegestuurde naam), routes achter de sessie-auth. Testdata in de tmp-map, niet repo-root data/."""
from __future__ import annotations

from nooch_village import cockpit2, snake
from nooch_village.snake import SnakeScores


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_store_higher_only_en_persistent(tmp_path):
    p = str(tmp_path / "snake_scores.json")             # eigen testdata in tmp, niet repo-root data/
    s = SnakeScores(p)
    assert s.record("p1", 23, "2026-07-05") == 23
    assert s.record("p1", 10, "2026-07-05") == 23       # lager → genegeerd
    assert s.best("p1") == 23
    assert s.record("p1", 40, "2026-07-06") == 40       # hoger → geschreven
    assert SnakeScores(p).best("p1") == 40              # persistent op schijf


def test_score_lager_dan_record_wordt_genegeerd(tmp_path):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd)
    st.people.add("Lotte", "lotte@nooch.earth")
    pid = st.people.by_email("lotte@nooch.earth").id
    snake.handle_score(st, "lotte@nooch.earth", 30)
    snake.handle_score(cockpit2._Stores(dd), "lotte@nooch.earth", 5)   # lager → genegeerd
    assert snake._store(cockpit2._Stores(dd)).best(pid) == 30


def test_score_valt_onder_sessie_gebruiker_niet_meegestuurde_naam(tmp_path):
    dd = _dd(tmp_path); st = cockpit2._Stores(dd)
    st.people.add("Lotte", "lotte@nooch.earth"); st.people.add("Stefan", "stefan@nooch.earth")
    lotte = st.people.by_email("lotte@nooch.earth").id
    stef = st.people.by_email("stefan@nooch.earth").id
    # handle_score neemt ALLEEN (username, score) — geen naam-param; de score valt onder de sessie-gebruiker
    snake.handle_score(st, "lotte@nooch.earth", 42)
    store = snake._store(cockpit2._Stores(dd))
    assert store.best(lotte) == 42 and store.best(stef) == 0          # alleen lotte, niet stefan


def test_niet_ingelogd_geen_toegang_tot_beide_routes(tmp_path):
    dd = _dd(tmp_path)
    # /snake is niet publiek → do_GET redirect een uitgelogde gebruiker naar /login
    assert "/snake" not in cockpit2._PUBLIC_GET
    # score-schrijven zonder herkende sessie (guest/None) doet niets
    snake.handle_score(cockpit2._Stores(dd), "guest", 999)
    snake.handle_score(cockpit2._Stores(dd), None, 999)
    assert snake._store(cockpit2._Stores(dd)).all() == {}
    # de /snake-pagina lekt geen persoonlijk record voor een niet-herkende gebruiker
    h = snake.render_snake_page(cockpit2._Stores(dd), None)
    assert '"me": ""' in h and "<canvas id='c'" in h


# ── v2: rename 'De Veter' → 'Snaker' + overlay/close-gedrag ──────────────────────

def test_render_heet_snaker_maar_behoudt_veter_thematiek(tmp_path):
    h = snake.render_snake_page(cockpit2._Stores(_dd(tmp_path)), None)
    assert "<title>Snaker</title>" in h and "🥾 Snaker" in h
    assert "<h2>🥾 De Veter</h2>" not in h              # spelnaam is niet meer 'De Veter'
    assert "De veter zit in de knoop" in h and "Veteranen" in h   # thematiek-copy blijft


def test_snake_sluit_via_postmessage_naar_parent(tmp_path):
    h = snake.render_snake_page(cockpit2._Stores(_dd(tmp_path)), None)
    assert "id='egg-sluit'" in h                        # × is in JS gewired, geen inline onclick
    assert "onclick='history.back()'" not in h
    assert "snake-close" in h and "postMessage" in h    # embedded → parent laten sluiten
    assert "'Escape'" in h                              # Escape sluit ook


def test_konami_trigger_opent_overlay_niet_navigatie():
    from nooch_village.web_base import _KONAMI_TRIGGER, _CSS
    assert "openSnake()" in _KONAMI_TRIGGER and "snake-overlay" in _KONAMI_TRIGGER
    assert "overlay-open" in _KONAMI_TRIGGER
    assert "location.href='/snake'" not in _KONAMI_TRIGGER   # geen full-page navigatie meer
    # de bar wordt verborgen zolang een overlay open is (generiek, geen snake-specifieke hack)
    assert "body.overlay-open .cb-frame{display:none}" in _CSS
    assert ".snake-overlay{" in _CSS and ".snake-frame{" in _CSS


def test_snake_route_wordt_chrome_loos_geserveerd():
    import inspect
    src = inspect.getsource(cockpit2)
    # /snake mag de dorp-brede call bar/rail niet in de iframe-doc geïnjecteerd krijgen
    assert "render_snake_page(st, username, effective_csrf), chrome=False" in src
