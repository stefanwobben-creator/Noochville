"""De laatste meter: van "wacht op een mens" naar werk op een bureau.

GEMETEN OP PROD, 29 aug 2026. De Scientist had 33 geblokkeerde projecten, alle 33 met dezelfde
park-reden: *vastgelopen op 1 item(s) — wacht op een mens of externe partij*. Samen 21 openstaande
stappen over 33 projecten — gemiddeld minder dan één per project. De oudste stonden 51 dagen stil.
Vijftien logden zelfs "✅ Checklist voltooid — klaar voor review" en stonden alsnog geblokkeerd.

De rol dééd zijn werk: 65 van de 88 einddocumenten wijken af van de seed. Wat ontbrak was de laatste
meter. Wat er wél gebeurde was een founder-ping over een TOESTAND ("vastgelopen op N mens-/extern
item(s)") in plaats van een VRAAG aan iemand die hem kan beantwoorden.

Drie eigenschappen, en dit bestand houdt ze alle drie vast:
  1. het landt via `route_werk` in een échte inbox — bestaande mechaniek, geen vierde kanaal;
  2. de ontvanger is GEGROND gekozen: mens-vervulde rol die het bezit → opdrachtgever → founder;
  3. de tekst is wélgevormd: wie vastzit, waar hij op vastzit, en wat hij concreet nodig heeft.
"""
from __future__ import annotations

import os

import pytest

from nooch_village import cockpit2, escalation_router as er
from nooch_village.human_inbox import FOUNDER_ROLE_ID


@pytest.fixture
def st(tmp_path):
    cockpit2._bootstrap(str(tmp_path))
    return cockpit2._Stores(str(tmp_path))


def _project(st, *, owner="harry_hemp", opdrachtgever="") -> dict:
    pid = st.projects.create(owner, "PHA-aanbodlandschap", "human", opdrachtgever=opdrachtgever)
    return st.projects.get(pid)


def _mens_rol(st, rid: str, monkeypatch, extra: set = frozenset()):
    """Doe alsof `rid` (en `extra`) door een mens bemand zijn — de assignments-laag zelf is elders
    getest; hier gaat het om de KEUZE."""
    bemand = {rid, *extra}
    monkeypatch.setattr("nooch_village.assignments.door_mens_bemand",
                        lambda rol, a, r: rol in bemand)


# ── 1. Het landt in een échte inbox, via bestaande mechaniek ─────────────────

def test_de_stap_landt_in_de_inbox_van_de_gekozen_mens(st, tmp_path, monkeypatch):
    rol = "mother_earth__nooch__creator_of_shoes"
    if st.records.get(rol) is None:
        pytest.skip("rol niet in de seed")
    _mens_rol(st, rol, monkeypatch)
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: {"role": rol, "kind": "human_external"})
    p = _project(st)
    uit = er.naar_mens(data_dir=str(tmp_path), project=p, from_role="harry_hemp",
                       from_naam="Scientist", waarom="het vraagt een mens of externe partij",
                       item_text="Laat de samples testen in een erkend lab (TÜV of SGS)")
    assert uit and uit["soort"] == "inbox" and uit["rol"] == rol
    open_notifs = [n for n in cockpit2._Stores(str(tmp_path)).notif.all()
                   if n.get("target_id") == rol]
    assert open_notifs, "niets in de inbox van de gekozen rol"


def test_er_komt_geen_vierde_kanaal_bij():
    """Hergebruik, geen nieuw kanaal: dit pad MOET door `route_werk`, want daar zit de regel dat een
    AI-vervulde rol de NotifStore nooit leest. Een eigen `notif.add` hier zou die regel omzeilen."""
    import inspect
    bron = inspect.getsource(er.naar_mens)
    assert "route_werk" in bron
    assert "notif.add" not in bron


# ── 2. De ontvanger is gegrond gekozen ──────────────────────────────────────

def test_eerst_een_mens_vervulde_rol_die_het_bezit(st, tmp_path, monkeypatch):
    rol = "mother_earth__nooch__website_developer"
    if st.records.get(rol) is None:
        pytest.skip("rol niet in de seed")
    _mens_rol(st, rol, monkeypatch)
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: {"role": rol, "kind": "human_external"})
    _r, _p, grond = er._mens_ontvanger(st, _project(st), "publiceer de pagina", "harry_hemp", [],
                                       None)
    assert (_r, grond) == (rol, "deze rol bezit dit werk")


def test_een_AI_ROL_is_geen_kandidaat_ook_al_bezit_hij_het(st, tmp_path, monkeypatch):
    """DE KERN VAN 'MENS-VERVULD'. Dit is de vraag ná 'geen enkele AI-rol bezit dit'. Nog een
    AI-rol voorstellen laat het werk opnieuw stranden — precies wat de hop-teller al probeerde."""
    _mens_rol(st, FOUNDER_ROLE_ID, monkeypatch)          # alleen de founder is 'mens'
    gezien = {}

    def _spion(item_text, doel, kandidaten, from_role, reason_fn, **kw):
        gezien["ids"] = {k["id"] for k in kandidaten}
        return {"role": "harry_hemp", "kind": "human_external"}   # een AI-rol voorstellen
    monkeypatch.setattr(er, "_vraag_llm", _spion)
    rol, _p, _g = er._mens_ontvanger(st, _project(st), "iets", "compliance", [], None)
    assert "harry_hemp" not in gezien["ids"], "een AI-rol stond op de kandidatenlijst"
    assert rol == FOUNDER_ROLE_ID                        # fail-closed → het vangnet


def test_zonder_zekere_rol_valt_hij_terug_op_de_opdrachtgever(st, tmp_path, monkeypatch):
    _mens_rol(st, FOUNDER_ROLE_ID, monkeypatch)
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: {"role": "NONE"})
    persoon = st.people.add("Stefan", "stefan@nooch.earth")
    pid = persoon.id if hasattr(persoon, "id") else persoon
    rol, wie, grond = er._mens_ontvanger(st, _project(st, opdrachtgever=pid), "iets",
                                         "harry_hemp", [], None)
    assert (rol, wie) == ("", pid) and grond == "jij vroeg om dit project"


def test_en_anders_de_founder(st, tmp_path, monkeypatch):
    """Het eerlijke antwoord als niets gegrond is — niet 'dan maar niet'."""
    _mens_rol(st, FOUNDER_ROLE_ID, monkeypatch)
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: None)      # geen model
    rol, wie, grond = er._mens_ontvanger(st, _project(st), "iets", "harry_hemp", [], None)
    assert rol == FOUNDER_ROLE_ID and wie == ""
    assert "geen rol bezit dit" in grond


def test_een_rol_die_dit_werk_al_zag_krijgt_het_niet_terug(st, tmp_path, monkeypatch):
    """Dezelfde guard als bij de AI-handoff: het spoor maakt A→B→A onmogelijk."""
    rol = "mother_earth__nooch__website_developer"
    if st.records.get(rol) is None:
        pytest.skip("rol niet in de seed")
    _mens_rol(st, rol, monkeypatch, extra={FOUNDER_ROLE_ID})
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: {"role": rol})
    p = _project(st)
    p["handoff_trail"] = [rol]
    gekozen, _w, _g = er._mens_ontvanger(st, p, "iets", "harry_hemp", [rol], None)
    assert gekozen != rol


# ── 3. Wélgevormd: wie, waarop, en wat er nodig is ──────────────────────────

def test_de_melding_noemt_de_rol_de_plek_en_de_vraag(st, tmp_path, monkeypatch):
    _mens_rol(st, FOUNDER_ROLE_ID, monkeypatch)
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: None)
    er.naar_mens(data_dir=str(tmp_path), project=_project(st), from_role="harry_hemp",
                 from_naam="Scientist", waarom="het vraagt een mens of externe partij",
                 item_text="Laat de samples testen in een erkend lab (TÜV of SGS)")
    n = [x for x in cockpit2._Stores(str(tmp_path)).notif.all()
         if x.get("target_id") == FOUNDER_ROLE_ID][-1]
    tekst, herkomst = n.get("snippet") or "", n.get("herkomst") or ""
    assert "Scientist" in tekst                              # WIE
    assert "erkend lab" in tekst                             # WAT hij nodig heeft
    assert "PHA-aanbodlandschap" in herkomst                 # WAAR hij op vastzit
    assert "geen rol bezit dit" in herkomst                  # en waarom het hier ligt
    assert "mens-/extern item(s)" not in tekst               # niet de oude, vage vorm


def test_het_bron_project_reist_mee_zodat_de_lus_terugloopt(st, tmp_path, monkeypatch):
    """Zonder het project is de melding een dood briefje: de lezer kan wel iets doen, maar niet
    zien wát er stilstaat of het weer in beweging zetten."""
    _mens_rol(st, FOUNDER_ROLE_ID, monkeypatch)
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: None)
    p = _project(st)
    er.naar_mens(data_dir=str(tmp_path), project=p, from_role="harry_hemp", from_naam="Scientist",
                 waarom="x", item_text="iets")
    n = [x for x in cockpit2._Stores(str(tmp_path)).notif.all()
         if x.get("target_id") == FOUNDER_ROLE_ID][-1]
    assert n.get("bron_project") == p["id"] or n.get("project_id") == p["id"]


# ── Fail-open: dit pad mag nooit werk laten verdampen ───────────────────────

def test_bij_een_storing_valt_hij_terug_op_de_oude_melding(st, tmp_path, monkeypatch):
    """Liever een vage ping dan stilte. Dat is de hele fail-open-regel hier."""
    monkeypatch.setattr(er, "_mens_ontvanger",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stuk")))
    assert er.naar_mens(data_dir=str(tmp_path), project=_project(st), from_role="r",
                        from_naam="R", waarom="x", item_text="y") is None


def test_de_klep_pingt_de_founder_niet_dubbel():
    """Twee meldingen over één gebeurtenis: dan overschreeuwt de vage de concrete."""
    src = open("nooch_village/inhabitant.py", encoding="utf-8").read()
    assert "if mens and not payload and not faal and not geland:" in src
    assert "open_items, geland = self._route_stuck_items(" in src


# ── Wat de scherm-check opleverde (29 aug 2026) ─────────────────────────────

def test_de_kaart_claimt_geen_overleg_dat_er_niet_was():
    """OP HET SCHERM GEVONDEN, niet in een test. De actie-kaart zei "Actie uit het werkoverleg /
    Afgesproken in het overleg" terwijl de herkomst-regel er direct boven zei dat een rol was
    vastgelopen. Twee tegengestelde zinnen op één scherm — precies wat deze kaarten wegnemen.

    De herkomst leeft in het `herkomst`-veld en staat er al; hem in de kaart nóg eens in andere
    woorden vertellen is `reference, don't copy` met tekst in plaats van een getal."""
    from nooch_village.views.inbox import _TYPE_LIJF
    titel, uitleg = _TYPE_LIJF["actie"]
    for verzonnen in ("werkoverleg", "overleg", "afgesproken", "Afgesproken"):
        assert verzonnen not in titel and verzonnen not in uitleg, verzonnen


def test_de_projecttitel_wordt_op_een_woordgrens_afgekapt():
    """'…failure that cau' leest als een defect, niet als een titel."""
    from nooch_village.escalation_router import _kort
    lang = "Diagnose and repair the silent hook/service failure that caused the miss"
    kort = _kort(lang, 60)
    assert kort.endswith("…") and not kort.endswith("cau…")
    assert " " not in kort[-2:]                       # geen losse spatie vóór de ellips
    assert _kort("kort genoeg", 60) == "kort genoeg"  # past het, dan geen ellips


# ── Twee gesprekken, twee breinen (29 aug 2026) ─────────────────────────────

def test_de_twee_router_vragen_draaien_niet_op_hetzelfde_brein():
    """Dezelfde prompt, een andere afweging.

    Gesprek 1 ("bezit een andere AI-rol dit?") is TRIAGE: een grove keuze met een goedkope fout,
    want verkeerd gerouteerd werk komt terug via de hop-teller. Gesprek 2 ("welke MENS doet dit?")
    is een OORDEEL waarvan de fout blijft plakken — het spoor (`vastgelopen_route.al_geland`) zorgt
    dat een verkeerde ontvanger vandaag een betere morgen buitensluit.

    Gemeten op prod: drie identieke droge loops over dezelfde 17 stappen gaven drie verschillende
    verdelingen (5, 2, 4 van de 17 kregen een rol), en op negen vrijwel identieke stappen koos
    hetzelfde model vier keer wél en vijf keer NONE. Alle 17 kregen antwoord — er was geen
    quota-probleem. Het goedkope model kán deze vraag niet reproduceerbaar beantwoorden."""
    from nooch_village import llm_keuze as lk
    assert er.ROUTE_SITE in lk.GOEDKOOP
    assert er.MENS_SITE in lk.HOOG_INZET and er.MENS_SITE not in lk.GOEDKOOP
    assert lk.ladder_voor(er.MENS_SITE) != lk.ladder_voor(er.ROUTE_SITE)
    assert lk.ladder_voor(er.MENS_SITE).split(",")[0].startswith("anthropic:claude-sonnet")


def test_de_mens_vraag_geeft_zijn_ladder_ook_echt_door(st, tmp_path, monkeypatch):
    """De HOOG_INZET-lijst alleen is niet genoeg: `reason()` kijkt daar niet zelf in. Precies de val
    waar `wizard_plan` in zat — in de lijst, maar zonder ladder, dus stil op de dorpsladder."""
    _mens_rol(st, FOUNDER_ROLE_ID, monkeypatch)
    gezien = {}

    def _vang(prompt, **kw):
        gezien.update(kw)
        return '{"role": "NONE"}'
    monkeypatch.setattr(er, "roster", lambda records, exclude: [{"id": FOUNDER_ROLE_ID,
                                                                 "purpose": "p",
                                                                 "accountabilities": []}])
    er._mens_ontvanger(st, _project(st), "iets", "harry_hemp", [], _vang)
    assert gezien["call_site"] == er.MENS_SITE
    assert (gezien["ladder"] or "").split(",")[0].startswith("anthropic:claude-sonnet")


def test_het_eerste_gesprek_blijft_goedkoop(st, tmp_path, monkeypatch):
    """Triage hoort niet duurder te worden omdat de tweede vraag dat wel is."""
    gezien = {}

    def _vang(prompt, **kw):
        gezien.update(kw)
        return '{"role": "NONE", "kind": "missing_capability"}'
    er._vraag_llm("iets", "doel", [{"id": "x", "purpose": "", "accountabilities": []}],
                  "harry_hemp", _vang)
    assert gezien["call_site"] == er.ROUTE_SITE and gezien["ladder"] is None


def test_vandaag_verandert_er_niets_aan_de_uitkomst():
    """Eerlijk over wat deze fix nú doet: de premium-kop is onbetaald, dus `met_dorpsstaart` levert
    nog steeds de dorpstredes. De verandering werkt zodra het krediet er is — niet eerder."""
    from nooch_village import llm, llm_keuze as lk
    tredes = lk.ladder_voor(er.MENS_SITE).split(",")
    assert tredes[1:] == llm.dorpsladder().split(","), "de goedkope staart is weggevallen"
