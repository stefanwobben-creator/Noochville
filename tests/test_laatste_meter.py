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
  2. de ontvanger is de FOUNDER, altijd;
  3. de tekst is wélgevormd: wie vastzit, waar hij op vastzit, en wat hij concreet nodig heeft.

EIGENSCHAP 2 IS OP 20 SEPTEMBER 2026 OMGEDRAAID. Hier stond: "de ontvanger is GEGROND gekozen:
mens-vervulde rol die het bezit → opdrachtgever → founder". Die eerste stap was een model dat een
collega werk gaf, uitgevoerd in dezelfde codepad, zonder dat iemand het vooraf zag — met vijf mensen
op veertien mens-bemande rollen geen theoretisch risico. Besluit van Stefan: *"niet de ladder, altijd
naar mij direct. Ik wil eerst alles zelf zien voordat het verder gaat."*

Het model mag nog steeds iets VINDEN; die zin reist mee als voorstel in de herkomst-regel. Het
gedrag van die grens staat in `test_bestemming_is_altijd_de_founder`, de brede vorm-bewaking in
`test_geen_model_routering`.
"""
from __future__ import annotations

import os

import pytest

from nooch_village import cockpit2, escalation_router as er, signaal
from nooch_village.human_inbox import FOUNDER_ROLE_ID


@pytest.fixture
def st(tmp_path):
    cockpit2._bootstrap(str(tmp_path))
    return cockpit2._Stores(str(tmp_path))


def _dm_aan(st, persoon_id):
    """De DM-teksten die deze persoon kreeg. Sinds B2 (20 sept 2026) landt werk als DM bij de mens
    in plaats van als item in een wachtrij; de routering — wie het krijgt — is ongewijzigd."""
    return [e.get("text") or "" for k in st.channels.kanalen_van(persoon_id)
            for e in st.channels.trail(k)]

def _project(st, *, owner="harry_hemp", opdrachtgever="") -> dict:
    pid = st.projects.create(owner, "PHA-aanbodlandschap", "human", opdrachtgever=opdrachtgever)
    return st.projects.get(pid)


def _mens_rol(st, rid: str, monkeypatch, extra: set = frozenset()):
    """Doe alsof `rid` (en `extra`) door een mens vervuld zijn — de assignments-laag zelf is elders
    getest; hier gaat het om de KEUZE.

    Patcht `mens_vervullers` en niet meer `door_mens_bemand`: sinds `route_werk` naar de VERVULLER
    kijkt in plaats van naar de rol is "wie vervult dit" de vraag, niet "is het vervuld". Dat is
    ook een betere fixture — hij zegt nu wie het draagt."""
    bemand = {rid, *extra}
    persoon = st.people.add("Testmens", "test@nooch.earth")
    monkeypatch.setattr(cockpit2, "mens_vervullers",
                        lambda _st, rol: [persoon.id] if rol in bemand else [])
    return persoon


# ── 1. Het landt in een échte inbox, via bestaande mechaniek ─────────────────

def test_de_stap_landt_in_de_inbox_van_de_founder(st, tmp_path, monkeypatch):
    """Het model krijgt hier alle ruimte: het wijst met stelligheid een bestaande rol aan. Vroeger
    landde het werk dan bij díé rol; nu bij de founder, met de rolnaam als voorstel erachter."""
    rol = "mother_earth__nooch__creator_of_shoes"
    if st.records.get(rol) is None:
        pytest.skip("rol niet in de seed")
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: {"role": rol, "kind": "human_external"})
    p = _project(st)
    uit = er.naar_mens(data_dir=str(tmp_path), project=p, from_role="harry_hemp",
                       from_naam="Scientist", waarom="het vraagt een mens of externe partij",
                       item_text="Laat de samples testen in een erkend lab (TÜV of SGS)")
    st2 = cockpit2._Stores(str(tmp_path))
    founder = signaal.terugval(st2)
    assert uit and uit["soort"] == "inbox"
    assert uit["persoon"] == founder and uit["rol"] == ""
    bij_mens = _dm_aan(st2, founder)
    assert bij_mens, "niets bij de founder aangekomen"
    # `rol` was een apart veld op het inbox-item; een DM draagt alleen tekst. De rol-context moet
    # dus IN de tekst staan — en dat is beter, want zo ziet de lezer hem zonder uitklappen.
    assert any("Scientist" in t for t in bij_mens), "de rol-context is weg"
    # En het oordeel van het model is niet weggegooid: het staat er als VOORSTEL.
    assert uit["suggestie"].startswith("voorstel:")


def test_er_komt_geen_vierde_kanaal_bij():
    """Hergebruik, geen nieuw kanaal: dit pad MOET door `route_werk`, want daar zit de regel dat een
    AI-vervulde rol de NotifStore nooit leest. Een eigen `notif.add` hier zou die regel omzeilen."""
    import inspect
    bron = inspect.getsource(er.naar_mens)
    assert "route_werk" in bron
    assert "notif.add" not in bron


# ── 2. De ontvanger is de founder, altijd ───────────────────────────────────
#
# WAT HIER WEG IS (20 september 2026): vijf tests over de oude keuze-ladder. Ze toetsten allemaal
# een regel die niet meer bestaat, en het is de moeite waard te noteren wát ze vasthielden:
#
#   `..._eerst_een_mens_vervulde_rol_die_het_bezit`     het model koos de ontvanger → nu een voorstel
#   `..._een_AI_ROL_is_geen_kandidaat`                  een AI-rol stond niet op de kandidatenlijst,
#                                                       want werk daar strandde. De suggestie MAG hem
#                                                       nu noemen — een voorstel strandt niet, en de
#                                                       lezer ziet zelf dat er geen mens op zit.
#   `..._zonder_zekere_rol_valt_hij_terug_op_de_opdrachtgever`
#                                                       DIT IS EEN ECHT VERLIES: wie om een project
#                                                       vroeg, hoorde het als het klem kwam te zitten.
#                                                       Dat spoor is weg; alles komt bij de founder,
#                                                       en die geeft het door. Bewust, niet vergeten.
#   `..._en_anders_de_founder`                          het vangnet is nu de hoofdweg
#   `..._een_rol_die_dit_werk_al_zag_krijgt_het_niet_terug`
#                                                       de A→B→A-guard. Die kan niet meer misgaan:
#                                                       er wordt niet meer doorverwezen, dus er is
#                                                       geen tweede hop om te bewaken.
#
# Wat ervoor in de plaats komt staat hierboven (`..._landt_in_de_inbox_van_de_founder`) en, op
# functieniveau, in `test_bestemming_is_altijd_de_founder`.

# ── 3. Wélgevormd: wie, waarop, en wat er nodig is ──────────────────────────

def test_de_melding_noemt_de_rol_de_plek_en_de_vraag(st, tmp_path, monkeypatch):
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: None)
    er.naar_mens(data_dir=str(tmp_path), project=_project(st), from_role="harry_hemp",
                 from_naam="Scientist", waarom="het vraagt een mens of externe partij",
                 item_text="Laat de samples testen in een erkend lab (TÜV of SGS)")
    st2 = cockpit2._Stores(str(tmp_path))
    tekst = _dm_aan(st2, signaal.terugval(st2))[-1]
    assert "Scientist" in tekst                              # WIE
    assert "erkend lab" in tekst                             # WAT hij nodig heeft
    assert "mens-/extern item(s)" not in tekst               # niet de oude, vage vorm
    # WAAR hij op vastzit en waarom het hier ligt stonden in het aparte `herkomst`-veld. Een DM
    # heeft dat veld niet; wat blijft is dat de lezer WIE en WAT in één regel ziet.


def test_het_bron_project_reist_mee_zodat_de_lus_terugloopt(st, tmp_path, monkeypatch):
    """Zonder het project is de melding een dood briefje: de lezer kan wel iets doen, maar niet
    zien wát er stilstaat of het weer in beweging zetten."""
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: None)
    p = _project(st)
    er.naar_mens(data_dir=str(tmp_path), project=p, from_role="harry_hemp", from_naam="Scientist",
                 waarom="x", item_text="iets")
    st2 = cockpit2._Stores(str(tmp_path))
    mens = st2.people.get(signaal.terugval(st2))
    # Het bron-project reist mee als `herkomst` op het bericht — het enige veld dat B2 bewaarde,
    # juist omdat de lezer anders niet kan zien wát er stilstaat.
    entries = [e for k in st2.channels.kanalen_van(mens.id) for e in st2.channels.trail(k)]
    assert entries and (entries[-1].get("herkomst") or {}).get("project") == p["id"]


# ── Fail-open: dit pad mag nooit werk laten verdampen ───────────────────────

def test_bij_een_storing_valt_hij_terug_op_de_oude_melding(st, tmp_path, monkeypatch):
    """Liever een vage ping dan stilte. Dat is de hele fail-open-regel hier."""
    monkeypatch.setattr(er, "_mens_ontvanger",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stuk")))
    assert er.naar_mens(data_dir=str(tmp_path), project=_project(st), from_role="r",
                        from_naam="R", waarom="x", item_text="y") is None




# ── Wat de scherm-check opleverde (29 aug 2026) ─────────────────────────────

# WAT HIER WEG IS (B2, 20 september 2026): `test_de_kaart_claimt_geen_overleg_dat_er_niet_was`.
# Die toetste de tekst van de actie-kaart in `views/inbox._TYPE_LIJF`. Dat scherm bestaat
# niet meer; een DM draagt de zin die de afzender typte en verzint er geen herkomst bij.



def test_de_projecttitel_wordt_op_een_woordgrens_afgekapt():
    """'…failure that cau' leest als een defect, niet als een titel."""
    from nooch_village.escalation_router import _kort
    lang = "Diagnose and repair the silent hook/service failure that caused the miss"
    kort = _kort(lang, 60)
    assert kort.endswith("…") and not kort.endswith("cau…")
    assert " " not in kort[-2:]                       # geen losse spatie vóór de ellips
    assert _kort("kort genoeg", 60) == "kort genoeg"  # past het, dan geen ellips


# ── Twee gesprekken, twee breinen (29 aug 2026) ─────────────────────────────

def test_de_twee_router_vragen_draaien_nu_op_hetzelfde_brein():
    """Deze test heette `..._niet_op_hetzelfde_brein`, en de reden waarom staat hieronder — want hij
    klopte, en het is de VERANDERING die hem omdraaide, niet een nieuw inzicht.

    Gesprek 1 ("bezit een andere AI-rol dit?") was altijd triage: een grove keuze met een goedkope
    fout, want verkeerd gerouteerd werk komt terug via de hop-teller. Gesprek 2 ("welke MENS doet
    dit?") was een OORDEEL waarvan de fout bleef plakken: het spoor (`vastgelopen_route.al_geland`)
    zorgde dat een verkeerde ontvanger vandaag een betere morgen buitensloot. Gemeten op prod gaven
    drie identieke droge loops over dezelfde 17 stappen drie verschillende verdelingen — het
    goedkope model kón die vraag niet reproduceerbaar beantwoorden.

    Sinds 20 september 2026 KIEST gesprek 2 niets meer. De bestemming is altijd de founder en het
    antwoord is een voorstelzin in de herkomst-regel. Daarmee is het dezelfde soort vraag geworden
    als gesprek 1: een grove keuze met een goedkope fout. Dus dezelfde ladder.

    Het MEETPUNT blijft gescheiden (`MENS_SITE` ≠ `ROUTE_SITE`): het zijn nog steeds twee vragen, en
    ze apart kunnen tellen is precies hoe de meting hierboven ooit boven water kwam."""
    from nooch_village import llm_keuze as lk
    assert er.ROUTE_SITE in lk.GOEDKOOP and er.MENS_SITE in lk.GOEDKOOP
    assert er.MENS_SITE not in lk.HOOG_INZET
    assert lk.ladder_voor(er.MENS_SITE) == lk.ladder_voor(er.ROUTE_SITE)
    assert er.MENS_SITE != er.ROUTE_SITE, "twee vragen, twee meetpunten"


def test_de_mens_vraag_blijft_apart_gemeten(st, tmp_path, monkeypatch):
    """De ladder is goedkoop geworden, het MEETPUNT niet verdwenen. Zonder eigen `call_site` valt
    deze vraag samen met de routeer-calls in `llm_usage.jsonl` en is de volgende meting onmogelijk —
    precies de val waar `wizard_plan` in zat, maar dan andersom."""
    gezien = {}

    def _vang(prompt, **kw):
        gezien.update(kw)
        return '{"role": "NONE"}'
    monkeypatch.setattr(er, "roster", lambda records, exclude: [{"id": FOUNDER_ROLE_ID,
                                                                 "purpose": "p",
                                                                 "accountabilities": []}])
    er._mens_ontvanger(st, _project(st), "iets", "harry_hemp", [], _vang)
    assert gezien["call_site"] == er.MENS_SITE
    assert gezien["ladder"] is None, "geen eigen kop meer — de dorpsladder volstaat"


def test_het_eerste_gesprek_blijft_goedkoop(st, tmp_path, monkeypatch):
    """Triage hoort niet duurder te worden omdat de tweede vraag dat wel is."""
    gezien = {}

    def _vang(prompt, **kw):
        gezien.update(kw)
        return '{"role": "NONE", "kind": "missing_capability"}'
    er._vraag_llm("iets", "doel", [{"id": "x", "purpose": "", "accountabilities": []}],
                  "harry_hemp", _vang)
    assert gezien["call_site"] == er.ROUTE_SITE and gezien["ladder"] is None


# WAT HIER WEG IS (20 september 2026): `test_vandaag_verandert_er_niets_aan_de_uitkomst`. Die was
# eerlijk over de premium-kop op `MENS_SITE` — onbetaald, dus `met_dorpsstaart` leverde in de
# praktijk toch de dorpstredes, en de fix zou pas werken zodra het krediet er was. Die kop is er nu
# af: de vraag verdient hem niet meer. Er valt dus niets meer te melden over wanneer hij aanslaat.
