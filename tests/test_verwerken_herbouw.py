"""Het verwerken-scherm: hiërarchie, geen dode rasterrij, en een scanbare uitkomstenlijst.

DRIE KLACHTEN, en ze hebben dezelfde wortel: alles stond in één `.rov-addgrid` en kreeg daarmee
dezelfde visuele lading. Het veld waar de secretaris LIVE in typt — de uitkomst-tekst — was een
eenregelige `<input>` naast een dropdown, even groot als "Rol" en "Persoon" eronder.

  1. HIËRARCHIE. Wat + de tekst worden het hoofdgebied; Rol, Persoon en (bij een project) Status
     zakken naar een stiller blok eronder. Zelfde velden, zelfde namen — alleen visueel lichter.
  2. DE DODE RASTERCEL. `rij3` was `<div class='wo-staat' hidden>…</div><div></div>`: staat de
     status verborgen, dan houdt die lege tweede cel nog steeds een hele rasterrij bezet. Het
     secundaire blok wisselt nu zélf van kolomaantal (2 → 3) in plaats van een cel te reserveren.
  3. DE TEKST TE KLEIN. `<input>` wordt `<textarea>` met echte hoogte.

En de bonus: de uitkomstenlijst gaat van `<table class='mtab'>` naar rijen met een kleurbadge
per type. Zelfde data, zelfde kolommen — andere opmaak.

Deze tests zijn eerst ROOD geschreven tegen de bestaande structuur.
"""
from __future__ import annotations

import os
import re

from nooch_village import cockpit2
from nooch_village.views import vangst

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = open(os.path.join(BASIS, "nooch_village", "static", "nooch.css"), encoding="utf-8").read()
NU = open(os.path.join(BASIS, "nooch_village", "static", "nooch-ui.css"), encoding="utf-8").read()
WEB = open(os.path.join(BASIS, "nooch_village", "web_base.py"), encoding="utf-8").read()

C = "mother_earth__nooch"


def _punt(tmp_path, uitkomsten=()):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    cockpit2.dispatch(dd, "wo_open", {"circle": [C], "next": ["/"]}, username="guest")
    cockpit2.dispatch(dd, "vangst_add",
                      {"circle": [C], "punt": ["FSC-verklaring verloopt"], "next": ["/"]},
                      username="guest")
    st = cockpit2._Stores(dd)
    it = st.werk.punten(C)[0]
    # Een uitkomst moet érgens hangen: zonder rol én zonder persoon weigert de actie. We geven
    # dus een rol mee — dezelfde eis als in het scherm, niet een omweg eromheen.
    rol = next(r.id for r in st.records.all()
               if r.id.endswith("__secretary") and not getattr(r, "archived", False))
    for u in uitkomsten:
        cockpit2.dispatch(dd, "vangst_uitkomst",
                          {"circle": [C], "iid": [it["id"]], "next": ["/"],
                           "rol": [rol], "persoon": [""], **u},
                          username="guest")
    st = cockpit2._Stores(dd)
    return dd, st, st.werk.punten(C)[0]


def _regels(css: str):
    """Selector → declaraties, MET de media-queries eruit.

    Twee dingen die deze parser eerst fout deed en die allebei een test lieten liegen:
    commentaar plakt aan de selector vast als je het niet strip, en een regel in een
    `@media`-blok overschrijft in een platte dict de basisregel — dan meet je de mobiele
    variant terwijl je de desktop bedoelt."""
    kaal = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    kaal = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", " ", kaal)
    return {re.sub(r"\s+", " ", s.strip()): b
            for sel, b in re.findall(r"([^{}]+)\{([^{}]*)\}", kaal) for s in sel.split(",")}


# ── 1 + 3. Hiërarchie, en de tekst als zwaartepunt ──────────────────────────────────────────
def test_de_uitkomst_tekst_is_een_tekstvak_met_hoogte(tmp_path):
    dd, st, it = _punt(tmp_path)
    html = vangst._uitkomst_formulier(st, C, it, "t", "/vangst")
    assert f"<input id='vut-{it['id']}'" not in html, "nog steeds een eenregelig invoerveld"
    vak = re.search(r"<textarea([^>]*)>", html).group(1)
    assert f"id='vut-{it['id']}'" in vak, vak
    # ... met een echte hoogte, en die staat in de stylesheet en niet als inline style.
    regel = _regels(CSS).get(".uk-invoer", "")
    assert "min-height" in regel, regel
    hoogte = float(re.search(r"min-height:([\d.]+)rem", regel).group(1))
    assert hoogte >= 5, hoogte


def test_de_tekst_houdt_zijn_naam_en_zijn_beginwaarde(tmp_path):
    """Alleen structuur en styling: het veld heet nog `tekst` en begint nog met de punt-titel,
    anders verandert er wél iets aan wat er wordt opgeslagen."""
    dd, st, it = _punt(tmp_path)
    html = vangst._uitkomst_formulier(st, C, it, "t", "/vangst")
    vak = html.split("<textarea")[1].split("</textarea>")[0]
    assert "name='tekst'" in vak
    assert "FSC-verklaring verloopt" in vak


def test_rol_persoon_en_status_staan_in_een_eigen_stiller_blok(tmp_path):
    dd, st, it = _punt(tmp_path)
    html = vangst._uitkomst_formulier(st, C, it, "t", "/vangst")
    sub = html.split("class='uk-sub", 1)[1].split("</div></div>")[0]
    for naam in ("name='rol'", "name='persoon'", "name='staat'"):
        assert naam in sub, naam
    # en het hoofdgebied draagt juist alleen Wat + de tekst
    hoofd = html.split("class='uk-hoofd'", 1)[1].split("class='uk-sub", 1)[0]
    assert "name='otype'" in hoofd and "<textarea" in hoofd
    assert "name='rol'" not in hoofd and "name='persoon'" not in hoofd


def test_het_secundaire_blok_is_visueel_lichter():
    """"Ondergeschikt" is geen smaak maar een meetbare keuze: kleiner lettertype dan het
    hoofdveld, en een eigen rustige achtergrond."""
    per = _regels(CSS)
    groot = float(re.search(r"font-size:([\d.]+)rem", per[".uk-invoer"]).group(1))
    klein = float(re.search(r"font-size:([\d.]+)rem", per[".uk-sub input"]).group(1))
    assert klein < groot, (klein, groot)
    assert "background" in per[".uk-sub"]


# ── 2. Geen dode rastercel ──────────────────────────────────────────────────────────────────
def test_de_lege_rastercel_is_weg(tmp_path):
    """`rij3` reserveerde een tweede cel die altijd leeg was. Verborgen status = een hele
    rasterrij met niets erin."""
    dd, st, it = _punt(tmp_path)
    html = vangst._uitkomst_formulier(st, C, it, "t", "/vangst")
    assert "<div></div>" not in html


def test_het_blok_wisselt_zelf_van_kolomaantal(tmp_path):
    """Niet terugvallen op een vaste twee-koloms grid: zodra Status verschijnt gaat het blok
    naar drie kolommen, en de handler die dat doet is dezelfde `onchange` die het label al
    wisselde — een inline attribuut, want een <script> in een fragment draait niet."""
    dd, st, it = _punt(tmp_path)
    html = vangst._uitkomst_formulier(st, C, it, "t", "/vangst")
    handler = html.split("onchange=\"")[1].split('"')[0]
    assert "uk-sub--status" in handler, handler
    per = _regels(CSS)
    kol = re.search(r"grid-template-columns:([^;]+)", per[".uk-sub"]).group(1)
    kol3 = re.search(r"grid-template-columns:([^;]+)", per[".uk-sub--status"]).group(1)
    assert kol.count("1fr") == 2 and kol3.count("1fr") == 3, (kol, kol3)


def test_de_status_begint_verborgen_en_hoort_bij_een_project(tmp_path):
    """Ongewijzigd gedrag: alleen een project heeft een wachtstand om naartoe te schrijven."""
    dd, st, it = _punt(tmp_path)
    html = vangst._uitkomst_formulier(st, C, it, "t", "/vangst")
    blok = html.split("data-staat-voor")[1].split(">")[0]
    assert "hidden" in html.split("data-staat-voor")[1].split(">")[0] or "hidden" in blok
    assert "'project'" in html.split("onchange=\"")[1].split('"')[0]


# ── Bonus: de uitkomstenlijst ───────────────────────────────────────────────────────────────
def test_de_lijst_is_geen_tabel_meer(tmp_path):
    dd, st, it = _punt(tmp_path, [{"otype": ["actie"], "tekst": ["Leverancier bellen"]}])
    html = vangst._uitkomsten_tabel(st, C, it, "t", "/vangst")
    assert "mtab" not in html and "<table" not in html
    assert "uk-rij" in html and "uk-badge" in html


def test_elke_soort_heeft_zijn_eigen_badge(tmp_path):
    dd, st, it = _punt(tmp_path, [
        {"otype": ["actie"], "tekst": ["Bellen"]},
        {"otype": ["project"], "tekst": ["Alternatief zoeken"]},
        {"otype": ["governance"], "tekst": ["Rol aanpassen"]},
    ])
    html = vangst._uitkomsten_tabel(st, C, it, "t", "/vangst")
    for soort in ("actie", "project", "governance"):
        assert f"uk-badge--{soort}" in html, soort
    for label in ("Actie", "Project", "Punt voor roloverleg"):
        assert label in html, label


def test_dezelfde_gegevens_staan_er_nog(tmp_path):
    """Andere opmaak, dezelfde kolommen: wat precies, rol, persoon, herkomst, en de twee acties."""
    dd, st, it = _punt(tmp_path, [{"otype": ["actie"], "tekst": ["Leverancier bellen"]}])
    html = vangst._uitkomsten_tabel(st, C, it, "t", "/vangst")
    assert "Leverancier bellen" in html
    assert "vangst_uitkomst_edit" in html and "vangst_uitkomst_weg" in html


def test_de_badgekleuren_komen_uit_tokens():
    """Zelfde aanpak als de kanban-kolommen: de waarden staan één keer, bij de andere tokens in
    web_base, en beide lagen verwijzen ernaar. Geen losse hex in een badge-regel."""
    assert "--uk-project:" in WEB and "--ukt-project:" in WEB
    per_css, per_nu = _regels(CSS), _regels(NU)
    for soort, klasse in (("actie", "actie"), ("project", "project"), ("gov", "governance")):
        regel = per_css.get(f".uk-badge--{klasse}", "")
        assert f"var(--uk-{soort})" in regel and f"var(--ukt-{soort})" in regel, (soort, regel)
        assert not re.search(r"#[0-9a-fA-F]{3,6}", regel), (soort, regel)
    # ... en de nu-laag doet het óók, net als bij de kanban-fix
    assert any(k.startswith(".nu .uk-badge") for k in per_nu), "nu-laag dekt de badges niet"


def test_het_project_deelt_zijn_tint_met_de_kanban_kolom():
    """`reference, don't copy` op kleur: een project-badge en de Active-kolom zijn hetzelfde
    soort ding, dus ze horen dezelfde waarde te gebruiken en niet twee keer dezelfde hex."""
    tok = re.search(r"--uk-project:([^;]+)", WEB).group(1).strip()
    assert tok == "var(--col-actief)", tok
