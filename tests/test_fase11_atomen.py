"""Fase 11, laag 1 en 2 — de atomen en de moleculen die erop staan.

DE VOLGORDE IS DE REGEL (CLAUDE.md, "Atomair opbouwen"): eerst de atomen, dan de moleculen die ze
combineren, dan het patroon. Wat deze tests bewaken is niet hoe iets eruitziet maar of die
gelaagdheid ook echt gelaagd is — want dat is wat er stukgaat. Een scherm dat "even" zijn eigen
balkje tekent ziet er hetzelfde uit en is een tweede implementatie.

Drie concrete dingen, en alle drie zijn een keer misgegaan in dit project:

1. **Eén balkje, niet drie.** De voortgangsbalk stond op drie plekken (projectkaart, doelkop,
   checklist) en was drie keer anders gebouwd: twee geneste divs met `style='width:42%'`, en één
   `<progress>`. Nu is het één atoom, en juist omdat het een `<progress>` is heeft het geen inline
   breedte nodig — dat ruimt tegelijk drie stuks inline-style-schuld op.
2. **Eén vormtaal voor status.** Gevuld = bezet, gestippeld = vacant. Dezelfde twee vormen als op
   het bord en in de checklist; een derde vorm erbij zou betekenen dat de lezer per scherm opnieuw
   moet leren wat een cirkeltje betekent.
3. **Een vorm is geen status zonder woord.** In zwart-wit, of voor wie die tinten niet
   onderscheidt, zijn twee cirkeltjes twee cirkeltjes. Het woord staat in een `.sr`-span.
"""
from __future__ import annotations

import pathlib
import re
import tempfile

import pytest

from nooch_village import cockpit2

REPO = pathlib.Path(__file__).resolve().parents[1]
CSS = (REPO / "nooch_village" / "static" / "nooch.css").read_text()
NU = (REPO / "nooch_village" / "static" / "nooch-ui.css").read_text()
VIEWS = REPO / "nooch_village" / "views"

ROL = "mother_earth__nooch__creator_of_shoes"


@pytest.fixture()
def dorp():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


# ── laag 1: de atomen ────────────────────────────────────────────────────────────────────────

def test_het_voortgangs_atoom_bestaat_in_beide_lagen():
    """De basis (buiten `.nu`) én de systeemtaal (binnen `.nu`). Alleen de tweede zou betekenen dat
    het balkje verdwijnt op elk scherm dat nog niet meedoet — en de zijbalk staat op álle schermen."""
    assert "progress.nu-progress{" in CSS.replace(" ", "")
    assert re.search(r"\.nu\s+progress\.nu-progress\s*\{", NU)


def test_het_rol_icoon_hergebruikt_de_bestaande_statusvormen():
    """Geen nieuwe vorm en geen nieuwe kleur: `--icoon` is een kaderloze variant van het atoom dat
    er al stond, en hij leunt op dezelfde twee modifiers."""
    assert ".nu-status--icoon" in CSS and ".nu-status--icoon" in NU
    for mod in ("nu-status--ok", "nu-status--open"):
        assert mod in NU, f"{mod} hoort in het systeem te blijven"


def test_er_is_een_tekst_equivalent_voor_een_vorm():
    """`.sr` is geen opmaak maar de andere helft van "vorm + woord"."""
    assert re.search(r"\.sr\{[^}]*clip-path", CSS.replace(" ", "").replace("\n", ""))


#: Views die een voortgangsbalk tonen en dus het atoom horen te gebruiken. Geen projectbrede
#: sweep: `views/metrics.py` heeft een eigen `bar-t`/`bar-f`-familie voor staafdiagrammen (een
#: ander ding dan een voortgangsbalk) en `views/overview.py` zet met `style='width:28px'` een
#: avatar op maat. Die twee zijn schuld voor wie ze tóch aanraakt, niet voor deze fase — zelfde
#: ratchet-afspraak als bij de inline-styles: monotone daling, geen losse opruimronde.
_BALK_VIEWS = ("projects.py", "checklists.py")


def test_de_balk_views_tekenen_geen_eigen_breedte_meer():
    """DE RATCHET VAN DEZE LAAG. Een `style='width:…%'` is per definitie een balkje dat zijn eigen
    breedte tekent — precies de tweede implementatie die het atoom vervangt."""
    overtredingen = []
    for naam in _BALK_VIEWS:
        # DE CODE, NIET DE UITLEG. Het comment bij `_progress_badge` noemt `style='width:60%'`
        # juist als wat er wég is; een assertie over de hele bron zou de uitleg verbieden in
        # plaats van het gedrag (zelfde vorm als `test_notify_rol_is_niet_meer_hardwired`).
        for nr, regel in enumerate((VIEWS / naam).read_text().splitlines(), 1):
            if regel.lstrip().startswith("#"):
                continue
            if "style='width:" in regel:
                overtredingen.append(f"{naam}:{nr}")
    assert overtredingen == [], (
        "gebruik `<progress class='nu-progress' value='…' max='100'>` — één atoom, geen inline "
        f"breedte: {overtredingen}")


def test_de_drie_balken_gebruiken_hetzelfde_atoom():
    """Projectkaart, doelkop en checklist: drie plekken, één klasse. Stond hier drie keer anders."""
    proj = (VIEWS / "projects.py").read_text()
    ck = (VIEWS / "checklists.py").read_text()
    assert proj.count("class='nu-progress") >= 2          # kaart + doelkop
    assert "class='nu-progress" in ck
    assert "<div class='pbar'>" not in proj               # de oude, zelfgetekende variant


# ── laag 1a in de boom, laag 1b op de kaart ──────────────────────────────────────────────────

def test_de_organisatieboom_toont_bezet_en_vacant(dorp):
    """1a. Een rol met een vervuller krijgt de gevulde cirkel, een lege rol de gestippelde — en
    allebei met het woord ernaast."""
    from nooch_village.views.overview import _tree_html
    dd, st = dorp
    mens = st.people.add("Lotte Vermeer", "lotte@nooch.earth")
    st.assign.assign(ROL, "person", mens.id)
    html = _tree_html(st, "")
    assert "nu-status--icoon" in html
    assert "nu-status--ok" in html and "nu-status--open" in html      # beide standen komen voor
    assert "<span class='sr'>filled: " in html and "<span class='sr'>vacant: " in html


def test_een_cirkel_draagt_geen_bezet_merkteken(dorp):
    """Een cirkel is geen stoel waar iemand in zit. Een bezet/vacant-icoon erop beantwoordt een
    vraag die niemand stelt — en zou de boom vol zetten met betekenisloze vormen."""
    from nooch_village.views.overview import _tree_html
    dd, st = dorp
    html = _tree_html(st, "")
    cirkelrij = re.search(r"<summary>(.*?)</summary>", html)
    assert cirkelrij and "nu-status" not in cirkelrij.group(1)


def test_de_kaartvoorkant_leest_van_onderwerp_naar_stand(dorp):
    """1b. Titel eerst, dan de etiketten, dan de voortgang, dan wie/wanneer. De titel stond hier
    ónder het doel-etiket: de kaart begon met een categorie in plaats van met zijn onderwerp."""
    from nooch_village.views.projects import _proj_card
    dd, st = dorp
    pid = st.projects.create(ROL, "Mycelium samples aanvragen", "human", status="running")
    html = _proj_card(st, st.projects.get(pid), "TOK", "/projects")
    assert html.index("ptitle") < html.index("pmeta"), "de titel staat bovenaan"
    assert "pchips" not in html or html.index("ptitle") < html.index("pchips")


def test_de_kaart_toont_geen_lege_deadline(dorp):
    """Wat er niet is, staat er niet. Een lege deadline-chip is een etiket zonder inhoud."""
    from nooch_village.views.projects import _kaart_chips
    dd, st = dorp
    pid = st.projects.create(ROL, "Zonder deadline", "human", status="running")
    assert _kaart_chips(st, st.projects.get(pid)) == ""


# ── laag 2b: de checklist-rij beweegt mee ────────────────────────────────────────────────────

def test_de_checklist_koppelt_vakje_en_balk(dorp):
    """2b. Het vakje weet bij welke lijst het hoort en de balk weet zijn noemer — anders kan de
    stand niet meebewegen zonder de pagina opnieuw te vragen."""
    from nooch_village.views.checklists import _checklists_html
    dd, st = dorp
    pid = st.projects.create(ROL, "Met lijst", "human", status="running")
    cl = st.projects.checklist_add(pid, "Plan")
    for tekst in ("eerste stap", "tweede stap"):
        st.projects.check_add(pid, cl["id"], tekst)
    html = _checklists_html(st.projects.get(pid), "TOK", pid, "/projects", True, st)
    assert "data-ck-bar=" in html and "data-ck-tot=" in html
    assert "data-ck-item=" in html and "data-ck-done=" in html
    assert "nu-progress" in html                                    # hetzelfde atoom


def test_de_opslag_blijft_de_post_en_niet_het_scriptje(dorp):
    """DE GRENS VAN 2B. Het scriptje raakt alleen wat je ziet; de waarheid blijft de POST die er
    altijd al was. Zonder deze regel zou een tweede opslagpad ontstaan dat stil uit de pas loopt."""
    from nooch_village.views.checklists import _CK_LIVE_JS
    for verboden in ("fetch(", "XMLHttpRequest", "navigator.sendBeacon"):
        assert verboden not in _CK_LIVE_JS
    assert "check_toggle" not in _CK_LIVE_JS                        # het post niets zelf
