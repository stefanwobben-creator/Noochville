"""Fase 9: Nooch UI v1 op de negentien herbouwde schermen.

Wat hier vastligt is niet "het ziet er goed uit" — dat is een screenshot-vraag. Het zijn de drie
dingen die stil kapot kunnen gaan:

1. de twee systemen raken elkaar niet (geen botsende tokens, geen globale `:root`);
2. een scherm doet mee of niet, en dat is één lijst — geen vlag die over negentien views uitwaaiert;
3. status is VORM plus WOORD, nooit kleur alleen.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village.cockpit2 import _NU_ROUTES
from nooch_village.cockpit2_util import _NU_CSS, _NU_LINK, _EXTRA_CSS
from nooch_village.web_base import _status

NU_RUW = pathlib.Path("nooch_village/static/nooch-ui.css").read_text(encoding="utf-8")
#: Zonder commentaar. De kop van dat bestand LEGT UIT waarom er geen tweede `:root` is en noemt de
#: botsende tokennamen — een test die de tekst meeleest verbiedt precies de uitleg die er hoort te
#: staan. Zelfde les als bij `Noochie._reflect` eerder dit traject.
NU = re.sub(r"/\*.*?\*/", "", NU_RUW, flags=re.S)


# ── 1. de twee systemen raken elkaar niet ────────────────────────────────────
def test_het_nieuwe_systeem_heeft_geen_globale_root():
    """Een tweede globale `:root` zou vier tokennamen overschrijven. `--border` is de dodelijke:
    oud een KLEUR, nieuw een shorthand, en hij staat 147x als `border:1px solid var(--border)`."""
    assert ":root" not in NU
    assert NU.count(".nu {") == 1 or NU.count(".nu{") == 1


def test_elke_nieuwe_token_draagt_de_eigen_naamruimte():
    # Alleen DECLARATIES (na `{` of `;`). Zonder die grens vangt de regex ook
    # klassennamen als `.nu-status--ok::before` en meldt die als losse token.
    tokens = set(re.findall(r"[;{]\s*(--[a-z0-9-]+)\s*:", NU))
    vreemd = {t for t in tokens if not t.startswith("--nu-")}
    assert not vreemd, f"tokens buiten de --nu--naamruimte: {sorted(vreemd)}"


def test_geen_enkele_regel_valt_buiten_de_nu_scope():
    """Één regel zonder `.nu` ervoor raakt élk scherm, ook de geparkeerde."""
    # `@media`-wrappers eerst weg: die zijn geen selector, en de regels ERIN moeten wel gescoped
    # zijn. Zonder die stap meldt de test de media-query zelf als overtreding.
    kaal = re.sub(r"@media[^{]*\{", "", NU)
    regels = [r.split("{")[0].strip() for r in kaal.split("}") if "{" in r]
    buiten = [r for r in regels if r and not r.startswith(".nu")]
    assert not buiten, f"regels buiten de scope: {buiten}"


def test_de_oude_stylesheet_is_niet_aangeraakt():
    """De klassensets blijven gescheiden: nooch.css kent het nieuwe systeem niet."""
    assert "--nu-" not in _EXTRA_CSS and ".nu " not in _EXTRA_CSS


# ── 2. de scope is één lijst ─────────────────────────────────────────────────
def test_de_negentien_schermen_staan_erin():
    for pad in ("/", "/projects", "/messages", "/wiki", "/pagina", "/node", "/person",
                "/project", "/admin", "/search", "/inbox", "/goals", "/werkoverleg",
                "/roloverleg2", "/vangst"):
        assert pad in _NU_ROUTES, pad


def test_de_geparkeerde_schermen_staan_er_bewust_niet_in():
    """/claims en /metrics2 zijn geparkeerd voor een eventuele tiende fase; de rest is in
    fase 1-8 nooit qua UI aangeraakt.

    `/site-audit` stond hier tot 20 september 2026 ook in. Fase 10 heeft hem alsnog opgenomen: hij
    WAS in fase 7 aangeraakt (taalresten) en viel dus ten onrechte buiten de scope. Bewust hier
    weggehaald en niet stilzwijgend — dat is precies het soort wijziging dat een jaar later
    onverklaarbaar is."""
    for pad in ("/claims", "/metrics2", "/catalog", "/skills", "/copy-check", "/decision-coach",
                "/keywords", "/rapport", "/login"):
        assert pad not in _NU_ROUTES, pad


def test_de_scope_wordt_op_een_plek_gezet():
    """Route-gestuurd in `_send`, niet als vlag door negentien render-functies."""
    src = pathlib.Path("nooch_village/cockpit2.py").read_text(encoding="utf-8")
    assert src.count("_NU_ROUTES") == 2                 # de definitie + de ene check
    assert '<body class="nu">' in src


def test_het_stylesheet_hangt_aan_de_scope():
    assert "nooch-ui.css" in _NU_LINK and "Archivo" in _NU_LINK


# ── 3. status is vorm plus woord ─────────────────────────────────────────────
def test_elke_status_draagt_een_woord():
    for s in ("running", "blocked", "done", "future", "proposed", "draft"):
        html = _status(s)
        assert ">" in html and html.split(">")[-2].strip("</span"), s


def test_de_vorm_zit_in_de_css_en_niet_in_de_kleur():
    """`::before` met een eigen vorm per status. Zou de betekenis in de achtergrond zitten, dan is
    het onleesbaar in zwart-wit en voor wie kleur niet goed ziet."""
    for variant, vorm in (("ok", "border-radius: 50%"), ("open", "border-radius: 50%"),
                          ("wait", "clip-path"), ("off", "clip-path")):
        blok = NU.split(f".nu-status--{variant}::before")[1].split("}")[0]
        assert vorm in blok, (variant, vorm)


def test_een_onbekende_status_verzint_niets():
    """Fail-closed: geen gokje op een vorm die iets anders belooft dan er is."""
    html = _status("rommel")
    assert "nu-status--open" in html and "rommel" in html


def test_status_blijft_leesbaar_buiten_een_nu_scherm():
    """Op een geparkeerd scherm doen de klassen niets; de tekst moet er dan gewoon staan."""
    assert "Waiting" in _status("blocked")
