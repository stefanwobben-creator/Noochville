""""My actions" toont ook wat anderen op JOUW projecten hebben opgeschreven (28 september 2026).

HET GAT. `render_acties` putte uit `st.acties.voor(ik)`, en dat is puur `person == ik`. Hang jij als
projecteigenaar een volgende stap bij iemand anders, dan zie jij hem nergens terug — behalve door de
projectpagina te openen en te weten dat je moest kijken. De omgekeerde koppeling bestond al
(`ActieStore.bij_project`, tot nu toe alleen gebruikt door de vastgelopen-route); wat ontbrak was de
vraag "welke projecten zijn van mij".

ÉÉN DEFINITIE VAN EIGENAARSCHAP, en dat is de helft van deze stap die je later pas mist. Die vraag
werd al beantwoord door `_projectopties` (de keuzelijst achter "+ link to a project"), ingebakken in
die functie. Nu staat hij in `_mijn_projecten` en putten allebei eruit. Twee formuleringen van
hetzelfde lopen uiteen zodra er één verandert, en dan toont dit blok acties van een project dat je
in de keuzelijst niet eens kunt kiezen.
"""
from __future__ import annotations

import inspect

from nooch_village import cockpit2
from nooch_village.views import acties as V

ROL = "mother_earth__nooch__compliance"
ANDERE_ROL = "mother_earth__nooch__creator_of_shoes"


def _dorp(tmp_path):
    """Ik vervul ROL, Beer vervult een andere rol. Elk een lopend project."""
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    for rol in (ROL, ANDERE_ROL):
        for f in list(st.assign.fillers_of(rol, st.records.get(rol))):
            st.assign.unassign(rol, f.type, f.id)
    ik = st.people.add("Aap Een", "aap@test.nl")
    beer = st.people.add("Beer Twee", "beer@test.nl")
    st.assign.assign(ROL, "person", ik.id)
    st.assign.assign(ANDERE_ROL, "person", beer.id)
    mijn = st.projects.create(ROL, "Mijn lopende project", "human", status="running")
    hun = st.projects.create(ANDERE_ROL, "Project van Beer", "human", status="running")
    return dd, st, ik, beer, mijn, hun


def _teksten(st, ik) -> list[str]:
    return [a.get("tekst") for a, _p in V._van_mijn_projecten(st, ik.id)]


# ══ 1. Wat er in het blok hoort ══════════════════════════════════════════════
def test_de_actie_van_een_ander_op_mijn_project_komt_erbij(tmp_path):
    """DE HELE POINTE. Beer schrijft een volgende stap op mijn project; ik zie hem op mijn lijst."""
    dd, st, ik, beer, mijn, hun = _dorp(tmp_path)
    st.acties.add(beer.id, "Selco bellen over de zolen", project=mijn)
    assert _teksten(st, ik) == ["Selco bellen over de zolen"]
    h = V.render_acties(st, ik.id, "TOK")
    assert "From your projects" in h and "Selco bellen over de zolen" in h
    assert "Beer Twee" in h, "zonder naam weet je niet wie het opschreef"


def test_op_het_project_van_een_ander_niet(tmp_path):
    """Het is "mijn projecten", niet "alles wat ik mag lezen" — dat laatste is het hele bord."""
    dd, st, ik, beer, mijn, hun = _dorp(tmp_path)
    st.acties.add(beer.id, "Iets op zijn eigen project", project=hun)
    assert _teksten(st, ik) == []
    assert "From your projects" not in V.render_acties(st, ik.id, "TOK")


def test_mijn_eigen_actie_staat_er_niet_dubbel(tmp_path):
    """Hij staat al bovenaan, in je eigen lijst, mét vinkje. Twee keer dezelfde regel op één
    scherm laat je zoeken naar het verschil dat er niet is."""
    dd, st, ik, beer, mijn, hun = _dorp(tmp_path)
    st.acties.add(ik.id, "Van mij en van mijn project", project=mijn)
    assert _teksten(st, ik) == []
    assert V.render_acties(st, ik.id, "TOK").count("Van mij en van mijn project") == 1


def test_wat_een_ander_afvinkt_verdwijnt_hier(tmp_path):
    """Wat JIJ afvinkt blijft staan — doorstrepen is de beloning. Wat een ánder afvinkt is geen
    nieuws maar geschiedenis, en het zou dit blok laten volstromen."""
    dd, st, ik, beer, mijn, hun = _dorp(tmp_path)
    a = st.acties.add(beer.id, "Al gedaan door Beer", project=mijn)
    st.acties.zet(a["id"], beer.id, done=True)
    assert _teksten(st, ik) == []


def test_een_los_briefje_van_een_ander_blijft_van_hem(tmp_path):
    """Zonder project is een actie privé — `zichtbaar_voor` zegt dat al, en dit blok kan er niet
    omheen omdat het per PROJECT zoekt."""
    dd, st, ik, beer, mijn, hun = _dorp(tmp_path)
    st.acties.add(beer.id, "Beers eigen briefje")
    assert _teksten(st, ik) == []


def test_leeg_is_echt_leeg(tmp_path):
    """Een kop boven een lege ruimte is meubilair, en op de meeste dagen zou dat de stand zijn."""
    dd, st, ik, beer, mijn, hun = _dorp(tmp_path)
    assert "From your projects" not in V.render_acties(st, ik.id, "TOK")


# ══ 2. Zichtbaarheid ═════════════════════════════════════════════════════════
def test_een_prive_project_dat_ik_niet_mag_lezen_telt_niet_mee(tmp_path):
    """DE BUITENGRENS. `_mijn_projecten` vraagt `mag_project_lezen`, dus een privé project van een
    cirkel waar ik niet in zit levert hier niets op — ook al loopt het."""
    dd, st, ik, beer, mijn, hun = _dorp(tmp_path)
    st.projects.edit(hun, private=True)
    st.acties.add(beer.id, "Achter gesloten deuren", project=hun)
    assert _teksten(st, ik) == []


def test_de_actie_zelf_wordt_ook_nog_getoetst(tmp_path):
    """TWEE NETTEN, en dat is geen dubbeling: `_mijn_projecten` zegt of het PROJECT van jou is,
    `zichtbaar_voor` of je de ACTIE mag zien. Dat tweede is de vraag die elk ander scherm ook
    stelt; hem hier overslaan zou de eerste plek zijn waar dit scherm zijn eigen regel verzint."""
    bron = inspect.getsource(V._van_mijn_projecten)
    assert "zichtbaar_voor" in bron
    assert "person" in bron, "de eigen-actie-filter is weg"


# ══ 3. Lezen, niet bedienen ══════════════════════════════════════════════════
def test_er_staat_geen_knop_die_de_server_weigert(tmp_path):
    """`ActieStore.zet`, `koppel` en `verwijder` eisen alle drie dat je de EIGENAAR bent. Een vakje
    dat je kunt aanklikken en waar de server "nothing changed" op zegt, belooft iets wat niet kan —
    dezelfde regel als bij de feiten-knop op een policy."""
    dd, st, ik, beer, mijn, hun = _dorp(tmp_path)
    st.acties.add(beer.id, "Selco bellen", project=mijn)
    blok = V.render_acties(st, ik.id, "TOK").split("From your projects")[1]
    for actie in ("actie_zet", "actie_weg", "actie_koppel"):
        assert f"value='{actie}'" not in blok, f"{actie} staat in het blok"
    assert "<form" not in blok, "er staat een formulier in een blok dat alleen leest"


def test_de_server_zou_hem_inderdaad_weigeren(tmp_path):
    """DE KETEN TOT HET EIND, en niet alleen de vorm: als dit WEL zou mogen, is de knop hierboven
    onterecht weggelaten."""
    dd, st, ik, beer, mijn, hun = _dorp(tmp_path)
    a = st.acties.add(beer.id, "Selco bellen", project=mijn)
    assert st.acties.zet(a["id"], ik.id, done=True) is False
    assert st.acties.verwijder(a["id"], ik.id) is False


def test_het_blok_hergebruikt_het_bestaande_molecuul(tmp_path):
    """Geen eigen lijstvorm: dezelfde `.ck-item`-rij als erboven, met het bolletje als `<span>`.
    Zonder dat bolletje springt de tekst naar links en leest het als een andere soort lijst."""
    dd, st, ik, beer, mijn, hun = _dorp(tmp_path)
    st.acties.add(beer.id, "Selco bellen", project=mijn)
    blok = V.render_acties(st, ik.id, "TOK").split("From your projects")[1]
    assert "class='ck-item'" in blok and "<span class='ck-box'></span>" in blok
    assert "class='cl-filter pill'" in blok, "het projectlabeltje hoort erbij"


def test_het_bolletje_zonder_knop_is_geen_handje():
    """`.ck-box` draagt `cursor:pointer` — terecht op een knop, misleidend op een `<span>`.
    Uitbreiding van dezelfde klasse, geen nieuwe familie (zie de UI-regel in CLAUDE.md)."""
    import pathlib
    css = (pathlib.Path(__file__).resolve().parents[1]
           / "nooch_village" / "static" / "nooch.css").read_text(encoding="utf-8")
    assert "span.ck-box{cursor:default;opacity:.5}" in css


# ══ 4. Eén definitie van "mijn projecten" ════════════════════════════════════
def test_de_keuzelijst_en_het_blok_putten_uit_dezelfde_bron():
    """`reference, don't copy`, harde regel. Zou `_projectopties` zijn eigen eigenaarschapsvraag
    houden, dan kan dit blok acties tonen van een project dat je in die lijst niet kunt kiezen."""
    bron = inspect.getsource(V._projectopties)
    assert "_mijn_projecten(" in bron
    for eigen in ("roles_of", "_LOPEND", "_II_PREFIX"):
        assert eigen not in bron, f"{eigen} staat weer in _projectopties zelf"
    assert "_mijn_projecten(" in inspect.getsource(V._van_mijn_projecten)


def test_de_keuzelijst_toont_nog_steeds_dezelfde_projecten(tmp_path):
    """De verhuizing mag niets aan het gedrag veranderen — dat is waar de toetsen van #623 op
    staan. Deze doet de tegenproef op de twee kanten tegelijk."""
    dd, st, ik, beer, mijn, hun = _dorp(tmp_path)
    opties = V._projectopties(st, ik.id, "")
    assert "Mijn lopende project" in opties and "Project van Beer" not in opties
    assert [p.get("id") for p in V._mijn_projecten(st, ik.id)] == [mijn]
