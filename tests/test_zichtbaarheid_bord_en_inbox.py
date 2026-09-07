"""Vier lekken van 7 september, en ze zijn alle vier hetzelfde lek.

Het systeem wéét het, het scherm zegt het niet:

1. **De vindplaats.** De claim-scan stuurt «"greener" (impact)» mee — de pagina dus. Wat de mens las
   was «het woord "greener" (over impact)»: het model gooide de plek niet weg maar VERBOUWDE hem tot
   een onderwerp. Erger dan een leeg veld, want het lijkt compleet.
2. **Delete liep dood.** Het formulier stuurde twee `next`-velden mee met tegengestelde bedoeling;
   `g()` leest de eerste, dus won de projectpagina die je zojuist had weggegooid.
3. **Een melding deed zich voor als besluit.** "Er staat al 1 taak op het bord" kreeg Action /
   Project / Governance aangeboden. Alle drie fout: het werk bestaat al.
4. **Een lopende kaart zei niet of er iemand werkte.** Vier heel verschillende toestanden zagen er
   identiek uit, waaronder 'onbemand' — de toestand waarin het antwoord "nooit" is.
"""
from __future__ import annotations

import pytest

from nooch_village import bevinding, governance


# ── 1. De vindplaats overleeft de herschrijving ──────────────────────────────

_RUW = ('🔴 Claim-scan: 1 nieuwe verboden claim(s) op nooch.earth '
        '— "greener" (impact) (1 taak op het bord)')


def test_de_pagina_wordt_herkend_als_vindplaats():
    assert bevinding.vindplaatsen_in(_RUW) == ['"greener" op de pagina impact']


def test_een_telling_tussen_haakjes_is_geen_pagina():
    """«(1 taak op het bord)» staat in dezelfde regel en ziet er hetzelfde uit. Zou die meetellen,
    dan krijgt de lezer "Waar: ... op de pagina 1 taak op het bord" en is de regel erger dan niets."""
    assert all("taak" not in v for v in bevinding.vindplaatsen_in(_RUW))


def test_urls_tellen_ook_mee():
    v = bevinding.vindplaatsen_in("scan faalde op https://nooch.earth/pages/impact, probeer later")
    assert v == ["https://nooch.earth/pages/impact"]


def test_de_verbouwde_plek_wordt_alsnog_expliciet_gemaakt():
    """DE KERNTEST. Het model schreef "(over impact)" — de plek staat er wel maar leest als een
    onderwerp. De expliciete regel eronder maakt er weer een vindplaats van."""
    uit = bevinding.met_vindplaats(_RUW, 'De scan vond het woord "greener" (over impact).')
    assert uit.endswith('Waar: "greener" op de pagina impact')
    assert 'De scan vond' in uit                       # de menselijke zin blijft heel


def test_zonder_vindplaats_verandert_er_niets():
    tekst = "Er is iets misgegaan bij het ophalen."
    assert bevinding.met_vindplaats("ruwe tekst zonder plek", tekst) == tekst


def test_een_al_genoemde_url_wordt_niet_herhaald():
    bron = "faalde op https://nooch.earth/impact"
    tekst = "De scan kwam niet op https://nooch.earth/impact."
    assert bevinding.met_vindplaats(bron, tekst) == tekst


def test_lege_spanning_krijgt_geen_losse_waar_regel():
    """Een afgekeurde herschrijving valt terug op de ruwe tekst. Daar een 'Waar:'-regel aan plakken
    zou een lege kaart met alleen een vindplaats opleveren."""
    assert bevinding.met_vindplaats(_RUW, "") == ""


# ── 2. Delete loopt niet meer dood ───────────────────────────────────────────

def _na(nxt, pid):
    from nooch_village.cockpit2 import _na_verwijderen
    return _na_verwijderen(nxt, pid)


def test_delete_keert_terug_naar_het_bord_en_niet_naar_het_weggegooide_project():
    """DE KERNTEST. `next` wijst naar de projectpagina zelf; de terugweg staat in diezelfde URL."""
    nxt = "/project?pid=abc123&back=%2Fnode%3Fid%3Dnooch%26tab%3Dprojects"
    assert _na(nxt, "abc123") == "/node?id=nooch&tab=projects"


def test_zonder_back_val_je_terug_op_de_voorpagina():
    assert _na("/project?pid=abc123", "abc123") == "/"


def test_een_next_die_niet_over_dit_project_gaat_blijft_staan():
    """Alleen de doodlopende weg wordt gerepareerd. Wie ergens anders vandaan komt, gaat daarheen
    terug — anders wordt deze functie een tweede router."""
    assert _na("/inbox", "abc123") == "/inbox"


def test_een_kapotte_url_levert_geen_fout_op():
    assert _na("::::not a url::::pid=abc123", "abc123") == "/"


def test_het_formulier_stuurt_nog_maar_een_next_mee():
    """De oorzaak zat in het formulier: twee velden met dezelfde naam. Zolang die er allebei staan,
    leest de regel als een werkende terugweg terwijl er geen was."""
    from nooch_village.views import projects as pv
    bron = open(pv.__file__, encoding="utf-8").read()
    i = bron.index("terminaal = ")
    blok = bron[i:bron.index("Delete</button></form>", i)]
    assert "value='proj_delete'" in blok, "het blok dat we toetsen moet de delete-knop bevatten"
    assert blok.count("name='next'") == 0, "de delete/archive-forms horen alleen de next uit hid() te dragen"


# ── 3. Een melding is geen besluit ───────────────────────────────────────────

class _Map:
    def __init__(self, mapping): self._m = mapping
    def get(self, k): return self._m.get(k)


class _St:
    """Een rol-afzender is de voorwaarde: een @mention komt van een MENS en houdt zijn oude scherm."""
    def __init__(self, mapping, rollen=("compliance",)):
        self.projects = _Map(mapping)
        self.records = _Map({r: object() for r in rollen})


def test_een_item_dat_naar_bestaand_werk_wijst_krijgt_een_deur():
    from nooch_village.views.inbox import _al_op_het_bord
    st = _St({"p1": {"id": "p1", "scope": "Fix the word greener on the impact page"}})
    html = _al_op_het_bord(st, {"project_id": "p1", "by": "compliance"})
    assert "already has a project" in html
    assert "/project?pid=p1" in html
    assert "greener" in html                           # je ziet wélk project, niet 'een project'


def test_zonder_project_id_gebeurt_er_niets():
    from nooch_village.views.inbox import _al_op_het_bord
    assert _al_op_het_bord(_St({}), {"tekst": "iets", "by": "compliance"}) == ""


def test_een_mention_van_een_mens_houdt_het_gewone_scherm():
    """CORRECTIE OP MEZELF. Mijn eerste versie keek alleen naar `project_id`, en een @mention in een
    projectfeed draagt dat veld ook. Die is juist wél een gesprek waar een besluit bij hoort; hem de
    besluitknoppen afnemen zou het probleem omkeren in plaats van oplossen."""
    from nooch_village.views.inbox import _al_op_het_bord
    st = _St({"p1": {"id": "p1", "scope": "Bron-project"}}, rollen=())
    assert _al_op_het_bord(st, {"project_id": "p1", "by": "stefan"}) == ""


def test_zonder_afzender_verandert_er_niets():
    from nooch_village.views.inbox import _al_op_het_bord
    st = _St({"p1": {"id": "p1", "scope": "Bron-project"}})
    assert _al_op_het_bord(st, {"project_id": "p1"}) == ""


def test_een_verwijzing_naar_een_verdwenen_project_levert_geen_dode_knop():
    """Fail-soft én stil. Een dode link is erger dan geen link: die kost je een klik om te ontdekken
    dat er niets is, en precies dat maakte de inbox onbetrouwbaar."""
    from nooch_village.views.inbox import _al_op_het_bord
    assert _al_op_het_bord(_St({}), {"project_id": "weg", "by": "compliance"}) == ""


def test_een_stukke_store_breekt_het_paneel_niet():
    from nooch_village.views.inbox import _al_op_het_bord
    class Stuk:
        @property
        def records(self): raise RuntimeError("store stuk")
    try:
        uit = _al_op_het_bord(Stuk(), {"project_id": "p1", "by": "compliance"})
    except Exception:                                   # noqa: BLE001
        pytest.fail("het inbox-paneel mag nooit vallen op een stukke projectstore")
    assert uit == ""


# ── 4. De kaart zegt wat er gebeurt ──────────────────────────────────────────

class _Rec:
    def __init__(self, rid, skills=(), slaapt=False):
        self.id, self.slaapt = rid, slaapt
        self.definition = type("D", (), {"skills": list(skills)})()
        self.source = "seed"


class _Reg:
    def __init__(self, bekend=()): self._b = set(bekend)
    def get(self, s): return object() if s in self._b else None


def test_een_slapende_rol_is_onbemand_met_zijn_eigen_reden():
    rec = _Rec("r1", ["web_zoek"], slaapt=True)
    rec.slaap_reden = "afgeslankt op 5 sept"
    leeft, reden = governance.bemand(rec, registry=_Reg(["web_zoek"]))
    assert leeft is False and "afgeslankt" in reden


def test_een_rol_zonder_bekende_skill_is_onbemand():
    leeft, _ = governance.bemand(_Rec("r1", ["bestaat_niet"]), registry=_Reg(["web_zoek"]))
    assert leeft is False


def test_een_rol_met_een_actieve_skill_leeft():
    leeft, reden = governance.bemand(_Rec("r1", ["web_zoek"]), registry=_Reg(["web_zoek"]))
    assert leeft is True and reden == "actieve skill"


def test_een_class_map_entry_leeft_altijd():
    leeft, _ = governance.bemand(_Rec("r1"), class_map={"r1": object}, registry=_Reg())
    assert leeft is True


def test_zonder_registry_verklaren_we_niemand_dood():
    """FAIL-OPEN, en dit is de belangrijkste tak. Een rol ten onrechte 'onbemand' noemen op het bord
    is erger dan zwijgen: de lezer gooit dan werk weg dat wél zou lopen."""
    leeft, reden = governance.bemand(_Rec("r1", ["web_zoek"]), registry=None)
    assert leeft is True and "onbekend" in reden


def test_de_rugzakken_tellen_hier_niet_mee():
    """Bewust, en het staat in de docstring. Zou een rugzak meetellen, dan is elke rol per definitie
    bemand en komt elke slapende rol weer tot leven — het tegenovergestelde van de afslanking."""
    import inspect
    bron = inspect.getsource(governance.bemand)
    assert "rugzak" in bron.lower(), "de uitzondering hoort uitgeschreven te staan"
    # Op de CODE toetsen, niet op de docstring — die noemt `skillset.effectief` juist om uit te
    # leggen waarom hij hier NIET gebruikt wordt. Een assert die de uitleg voor de uitvoering
    # aanziet, toetst het tegenovergestelde van wat hij belooft.
    code = bron.split('"""')[-1] if bron.count('"""') >= 2 else bron
    assert "skillset" not in code, "deze poort mag de rugzak-lezende skillset niet gebruiken"
    assert "skill_links" in code                       # DNA ∪ koppelingen: dát is de juiste set


def _kaart(p, st=None):
    from nooch_village.views.projects import _kaart_status
    return _kaart_status(st, p)


def test_de_lopende_statussen_komen_uit_de_kolomdefinitie():
    """DE TEST DIE ER EERST NIET WAS, en zonder hem faalde de badge stil op productie. Ik toetste op
    `status == "active"` omdat de kolom Active heet; de statussen heten `running` en `queued`. Mijn
    test gebruikte diezelfde geraden waarde en bevestigde dus mijn aanname in plaats van de code te
    toetsen. Nu wordt de lijst AFGELEID uit `_PROJ_COLS` en toetst deze test dát."""
    from nooch_village.views.projects import _ACTIEF_STATUSSEN, _PROJ_COLS
    uit_kolom = next(s for _l, k, s in _PROJ_COLS if k == "actief")
    assert _ACTIEF_STATUSSEN == uit_kolom
    assert "running" in _ACTIEF_STATUSSEN and "queued" in _ACTIEF_STATUSSEN
    assert "active" not in _ACTIEF_STATUSSEN         # de kolom heet zo, de status niet


def test_queued_zegt_dat_het_in_de_rij_staat():
    """Het onderscheid tussen 'ermee bezig' en 'wacht op de puls' hoefde niet verzonnen: het staat
    al in de status. Ik schreef eerst dat daar een hartslag voor nodig was, en keek ernaast."""
    p = {"status": "queued", "owner": "",
         "checklists": [{"items": [{"id": "1", "text": "x", "skill": "web_zoek"}]}]}
    assert "queued" in _kaart(p)


def test_alleen_een_lopende_kaart_krijgt_een_status():
    p = {"status": "future", "owner": "r1",
         "checklists": [{"items": [{"id": "1", "text": "x"}]}]}
    assert _kaart(p) == ""


def test_een_kaart_zonder_open_items_zegt_niets_extras():
    p = {"status": "running", "owner": "r1",
         "checklists": [{"items": [{"id": "1", "text": "x", "done": True}]}]}
    assert _kaart(p) == ""


def test_vastgelopen_wint_van_looptdoor():
    p = {"status": "running", "owner": "",
         "checklists": [{"items": [{"id": "1", "text": "x", "skill": "web_zoek", "fails": 3}]}]}
    uit = _kaart(p)
    assert "stuck (3×)" in uit


def test_alleen_menswerk_zegt_dat_jij_aan_zet_bent():
    p = {"status": "running", "owner": "",
         "checklists": [{"items": [{"id": "1", "text": "bel de leverancier"}]}]}
    assert "your turn" in _kaart(p)


def test_een_verdwenen_eigenaar_rol_zegt_geen_eigenaar():
    """GEVONDEN DOOR TE RENDEREN, niet door te lezen. Een project waarvan de eigenaar-rol niet meer
    in governance staat kreeg 'running' — de ergste leugen die dit vakje kan vertellen: daar gebeurt
    gegarandeerd nooit meer iets."""
    class Leeg:
        records = _Map({})
    p = {"status": "running", "owner": "verdwenen_rol",
         "checklists": [{"items": [{"id": "1", "text": "x", "skill": "web_zoek"}]}]}
    uit = _kaart(p, Leeg())
    assert "no owner" in uit and "running" not in uit


def test_een_individueel_initiatief_heeft_geen_rol_en_dus_geen_verwijt():
    """`ii:<cirkel>` is geen rol maar een persoonlijk initiatief. Die 'onbemand' noemen zou elke
    eigen actie op het bord rood kleuren."""
    from nooch_village.views.projects import _II_PREFIX
    class Leeg:
        records = _Map({})
    p = {"status": "running", "owner": f"{_II_PREFIX}nooch",
         "checklists": [{"items": [{"id": "1", "text": "x", "skill": "web_zoek"}]}]}
    assert "running" in _kaart(p, Leeg())


def test_een_lopend_project_met_skill_zegt_running():
    p = {"status": "running", "owner": "",
         "checklists": [{"items": [{"id": "1", "text": "x", "skill": "web_zoek"}]}]}
    assert "running" in _kaart(p)


def test_de_badge_valt_nooit_om():
    """Versiering op een kaart mag het bord niet slopen. Een `st` die bij elke aanroep ontploft is
    de scherpste vorm van die test."""
    class Stuk:
        @property
        def records(self): raise RuntimeError("stuk")
    p = {"status": "running", "owner": "r1",
         "checklists": [{"items": [{"id": "1", "text": "x", "skill": "web_zoek"}]}]}
    assert _kaart(p, Stuk()) == ""


def test_onbemand_heeft_zijn_eigen_zwaarste_opmaak():
    """Kleur draagt de ernst, maar het teken draagt de betekenis — anders leest een kaart verkeerd
    voor wie geen kleurverschil ziet."""
    import os
    from nooch_village import views
    css = open(os.path.join(os.path.dirname(views.__file__), "..", "static", "nooch.css"),
               encoding="utf-8").read()
    assert ".pstatus.is-onbemand{background:var(--coral)" in css
    from nooch_village.views.projects import _STATUS_UIT
    tekens = [v[0] for v in _STATUS_UIT.values()]
    assert len(set(tekens)) == len(tekens), "elke status heeft een eigen teken, niet alleen een kleur"


# ── 5. Vloeiend, niet luid ───────────────────────────────────────────────────
#
# "Die interactie dat AI willen helpen om taken uit te voeren voelt nu nog wat statisch." Elk vinkje
# en elk skill-aanbod gooide de hele pagina weg en bouwde hem opnieuw op. Deze tests bewaken niet
# hoe het VOELT (dat kan een test niet) maar de drie regels die de beweging eerlijk houden.

def _js():
    from nooch_village.views.checklists import _ck_sleep_js
    return _ck_sleep_js("tok", "/project?pid=p1&back=%2F")


def test_de_weigering_wordt_uit_de_url_gelezen_en_niet_uit_de_status():
    """DE BLINDE VLEK DIE `ibxPost` AL BESCHRIJFT. Een inhoudelijke weigering reist als melding op
    een 303; fetch volgt die en `r.ok` is dan gewoon waar. Wie op `r.ok` afgaat, zet het scherm op
    groen terwijl de server nee zei."""
    js = _js()
    assert "ckWeigering" in js
    assert "q.get('ok')==='0'" in js.replace(" ", "")


def test_de_nieuwe_stand_komt_van_de_server_en_wordt_niet_geraden():
    """Niets optimistisch bijwerken: we halen de lijst opnieuw op bij de bestaande
    `?fragment=1`-route in plaats van te gokken wat er zou moeten staan."""
    js = _js()
    assert "fragment=1" in js
    assert "location.reload()" in js       # onverwachte vorm → eerlijk herladen, niet half


def test_bij_elke_fout_gaat_het_formulier_alsnog_op_de_oude_manier():
    """Stil falen is hier het ergst: dan lijkt je klik gelukt. Elke fout valt terug op de gewone
    formulierpost, zodat de mens de melding krijgt die de server altijd al gaf."""
    js = _js()
    assert "catch(function()" in js.replace(" ", "") or ".catch(function()" in js
    assert "f.submit()" in js


def test_alleen_de_herhaalde_handelingen_gaan_ter_plekke():
    """Verwijderen en doorgeven blijven een hele paginabeurt: dat zijn eindpunten, geen ritme."""
    js = _js()
    assert "check_toggle" in js and "check_accept" in js and "check_rename" in js
    assert "check_remove" not in js and "check_handoff" not in js


def test_zonder_javascript_werkt_alles_gewoon():
    """We hangen aan `submit`, niet aan `click`, en we vervangen de knoppen niet. Valt de JS uit,
    dan post het formulier zoals het altijd al deed."""
    js = _js()
    assert "addEventListener('submit'" in js
    assert "preventDefault" in js


def _css() -> str:
    import os
    from nooch_village import views
    pad = os.path.join(os.path.dirname(views.__file__), "..", "static", "nooch.css")
    return open(pad, encoding="utf-8").read()


def _regel(css: str, selector: str) -> str:
    """De declaraties van de regel waar `selector` in staat, op één regel.

    Inspringing en regeleindes gaan eruit, losse spaties NIET: in een shorthand als
    `animation:ck-wacht 1.1s ease-in-out .5s infinite` zijn die spaties de scheiding tussen
    duur en vertraging, en juist die vertraging is hier het onderwerp.
    """
    _kop, _, rest = css.partition(selector)
    assert rest, f"selector {selector} staat niet in de css"
    return " ".join(rest.partition("{")[2].partition("}")[0].split())


def test_wie_geen_beweging_wil_krijgt_ze_niet():
    """Geen extraatje maar de voorwaarde om te mogen bewegen: alles wat beweegt is versiering op
    informatie die ook stil klopt."""
    css = _css()
    blok = css.split("@media (prefers-reduced-motion: reduce)")[1].split("}\n")[0] \
        if "prefers-reduced-motion" in css else ""
    assert blok, "er is geen reduced-motion-blok"
    assert "animation:none" in css.replace(" ", "")


# ── 5b. Zichtbaarheid van de systeemstatus ───────────────────────────────────
#
# "Subtiel, maar wel vloeiend, en van belang: visibility of system status." Dimmen alleen is voor een
# snel antwoord genoeg en voor een traag antwoord te weinig: dan zit de rij er grijs bij en lijkt de
# klik niet aangekomen. Deze drie tests bewaken de grens tussen die twee gevallen.

def test_een_snel_antwoord_toont_helemaal_geen_wachtteken():
    """De vertraging IS het ontwerp. Een indicator die oplicht en meteen weer weg is, is drukte;
    binnen een halve seconde voelt een antwoord als direct en hoort er niets te verschijnen."""
    decl = _regel(_css(), ".ck-item.bezig,.ibx-row.gk.bezig")
    assert "animation:ck-wacht" in decl
    tijden = [d for d in decl.split("animation:")[1].split(";")[0].split()
              if d.endswith("s") and d[0].isdigit() or d.startswith(".")]
    # In de shorthand is de eerste tijdwaarde de duur en de tweede de vertraging.
    assert len(tijden) >= 2, f"geen animation-delay in: {decl}"
    assert float(tijden[1].rstrip("s")) >= .4, "te snel zichtbaar: dan knippert het bij elke klik"


def test_een_traag_antwoord_blijft_niet_stil():
    """Voorbij die grens is stilte de leugen: dan lijkt je klik niet aangekomen. De rij ademt dan,
    zonder spinner die de aandacht opeist."""
    css = _css()
    assert "@keyframes ck-wacht" in css
    assert "infinite" in _regel(css, ".ck-item.bezig,.ibx-row.gk.bezig")


def test_bezig_heeft_een_vorm_voor_beide_lijsten():
    """Reference, don't copy — ook in css. Twee keer dezelfde opacity uitschrijven is het feit op
    twee plekken dat uiteendrijft zodra iemand er één aanpast."""
    css = _css()
    gedeeld = _regel(css, ".ck-item.bezig,.ibx-row.gk.bezig")
    assert "opacity:.45" in gedeeld and "pointer-events:none" in gedeeld
    # De inbox heeft geen eigen bezig-regel meer naast de gedeelde. Een regel die met díe selector
    # BEGINT (na een regeleinde) zou de tweede plek zijn waar dezelfde vorm staat.
    assert "\n.ibx-row.gk.bezig{" not in css


def test_het_dimmen_blijft_ook_zonder_beweging():
    """Het ademen is versiering, het dimmen is de status zelf: die blijft ook bij reduced motion."""
    css = _css()
    blok = css.split("@media (prefers-reduced-motion: reduce)")[1].split("\n}")[0].replace(" ", "")
    assert ".ck-item.bezig,.ibx-row.gk.bezig{animation:none}" in blok
    assert "opacity" not in blok, "reduced motion mag het dimmen niet meenemen"


def test_het_draai_teken_maakt_geen_nieuwe_klassefamilie():
    """De prefix-ratchet telt alles vóór het eerste koppelteken als familie, dus `pstatus-ic` maakte
    er stilletjes een nieuwe aan. Vandaar een klasse zonder streepje."""
    from nooch_village.views.projects import _kaart_status
    p = {"status": "running", "owner": "",
         "checklists": [{"items": [{"id": "1", "text": "x", "skill": "web_zoek"}]}]}
    uit = _kaart_status(None, p)
    assert "class='draait'" in uit and "-ic" not in uit
