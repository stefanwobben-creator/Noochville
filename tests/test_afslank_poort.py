"""Geen snit zonder afhankelijkheidscheck — in twee richtingen.

DE VIJF GEVALLEN DIE DEZE POORT HAD GEVANGEN. De afslanking van 28 aug 2026 sneed op OPBRENGST
(Kroniek-records, deliverables, afgetekende projecten) en vroeg nergens wat er aan een rol HING.
Wat er daarna één voor één omviel:

  1. `facilitator` sliep → de DAGBEL viel weg; het dorp pulseerde drie dagen niet.
  2. `facilitator` sliep → `dag_eindigt` viel weg, en daarmee de dag-afsluitende curatie van de
     Librarian (tag-onderhoud, verband-voorstellen).

     ↳ 1 en 2 zijn sinds 30 aug 2026 ONMOGELIJK: de cadans is uit de rol gehaald en woont in
       `dagcyclus.py`. De test daarvoor bewijst nu de afwezigheid van de koppeling, niet de
       zichtbaarheid ervan — wegnemen is sterker dan waarschuwen.
  3. `website_watcher` sliep → `pulse_completed` viel weg; de afrondingsregel kon niet verschijnen
     en `last_pulse`/`pulse_history` bleven op 27 augustus staan.
  4. `website_watcher` sliep → de GROEI-PULS viel weg (Field Note, Plausible-metrics,
     dode-bron-detectie, doel-gap-signaal, keyword-voorstellen) — zichtbaar aan de events die hij
     publiceert en die anderen lezen.
  5. `serpapi_trends` werd ingetrokken → de CODE van website_watcher roept hem nog aan, en meldt
     bij elk ontwaken 'dode capability'.

Vier keer richting A (rol → wat consumeren anderen), één keer richting B (skill → welke code roept
nog aan). Alle vijf staan hieronder als meting.
"""
from __future__ import annotations

import pytest

from nooch_village import afslank_afhankelijkheden as aa
from nooch_village import afslanken as af


# ── Richting A: een rol slapen ─────────────────────────────────────────────

def test_geval_1_en_2_kunnen_niet_meer_gebeuren():
    """DE POORT WAS HET VANGNET, NIET DE OPLOSSING.

    Geval 1 en 2 gingen allebei over dezelfde koppeling: de dagbel en `dag_eindigt` werden
    gepubliceerd vanuit `Facilitator`, dus een governance-besluit over die ROL zette de hartslag van
    het hele DORP uit. Deze poort zou dat voortaan tonen vóór de snit — maar tonen is zwakker dan
    wegnemen, en een waarschuwing die je mag wegklikken houdt een systeem niet overeind.

    De cadans is daarom verhuisd naar `dagcyclus.py`: infrastructuur, geen rol. De facilitator draagt
    hem niet meer, en dus is er niets meer te waarschuwen. Dat deze test omdraaide van 'let op' naar
    'kan niet meer' is de winst; zie tests/test_hartslag_los.py voor de ratchet die het zo houdt."""
    d = aa.rol_afhankelijkheden("facilitator")
    ev = {e["event"] for e in d["events"]}
    assert not (ev & {"dag_begint", "dag_eindigt", "maand_begint", "kwartaal_begint"})
    assert d["eigen_ritme"] is False, "de facilitator heeft geen eigen ritme meer nodig"


def test_geval_3_website_watcher_draagt_pulse_completed():
    d = aa.rol_afhankelijkheden("website_watcher")
    ev = {e["event"]: e["consumenten"] for e in d["events"]}
    assert "pulse_completed" in ev
    assert "Village" in ev["pulse_completed"], "de afrondingsregel hangt hieraan"


def test_geval_4_website_watcher_draagt_de_groeipuls():
    """De groei-puls zelf is geen event, maar wat hij oplevert wél: ontdekking en dode bronnen."""
    d = aa.rol_afhankelijkheden("website_watcher")
    ev = {e["event"] for e in d["events"]}
    assert {"project_discovery_ready", "source_died"} <= ev


# ── Richting B: een skill intrekken ────────────────────────────────────────

def test_geval_5_serpapi_trends_wordt_nog_aangeroepen():
    d = aa.skill_afhankelijkheden("serpapi_trends")
    plekken = {a["bestand"] for a in d["aanroepers"]}
    assert "roles.py" in plekken, "de use_skill-aanroep in de rol wordt niet gezien"
    assert any("use_skill" in a["code"] for a in d["aanroepers"])


# ── Wat de poort NIET moet doen ────────────────────────────────────────────

def test_een_rol_zonder_mechanisme_is_vrij():
    """Een generieke Inwoner draagt niets; die mag zonder waarschuwing slapen. Een poort die overal
    afgaat wordt genegeerd — dezelfde wet als bij de rode ratchet."""
    d = aa.rol_afhankelijkheden("mother_earth__nooch__marketing_lead")
    assert not d["events"] and not d["eigen_ritme"] and not d["klasse"]
    assert "draagt geen mechanisme" in aa.rapport(["mother_earth__nooch__marketing_lead"], [])


def test_een_ongebruikte_skill_is_vrij():
    d = aa.skill_afhankelijkheden("een_skill_die_niet_bestaat_xyz")
    assert d["aanroepers"] == []


# ── De poort blokkeert, en laat zich bewust openen ─────────────────────────

def _plan(rollen=(), skills=()):
    """Een plan in de vorm die `plan()` oplevert — genoeg velden om het rapport te renderen."""
    return {"slapen": [{"id": r, "naam": r, "bewijs": "-", "kosten": "-", "laatst": "-",
                        "advies": "slapen"} for r in rollen],
            "opruimen": [{"soort": "skill", "naam": s, "bewijs": "-", "id": s} for s in skills],
            "overgeslagen": [], "geweigerd": [], "audit_pad": "x"}


def test_een_snit_met_afhankelijkheden_wordt_geweigerd():
    """Stond op `facilitator` + `dag_eindigt`; die koppeling bestaat niet meer (zie hierboven).
    `website_watcher` draagt nog wél echt werk waar anderen op wachten, dus daar heeft de poort
    zijn tanden."""
    with pytest.raises(af.AfhankelijkheidNietBevestigd) as e:
        af.voer_uit(_plan(rollen=["website_watcher"]), None, data_dir="", bevestigd=False)
    assert "pulse_completed" in str(e.value)


def test_bevestigen_mag_wel_want_het_kan_de_juiste_keuze_zijn():
    """De machine weet het niet beter. Een rol slapen die iets draagt kán goed zijn — het moet
    alleen een BESLISSING zijn en geen bijvangst."""
    from types import SimpleNamespace
    recs = SimpleNamespace(get=lambda i: None, all=lambda: [], save=lambda: None)
    gedaan = af.voer_uit(_plan(), recs, data_dir="", bevestigd=True)
    assert gedaan == {"slaap": [], "archiveer_rol": [], "skill_intrekken": []}


def test_een_leeg_plan_hoeft_niets_te_bevestigen():
    assert af.afhankelijkheden_van(_plan())["leeg"] is True


def test_het_rapport_toont_de_afhankelijkheden():
    plan = _plan(rollen=["website_watcher"], skills=["serpapi_trends"])
    plan["_afhankelijkheden"] = af.afhankelijkheden_van(plan)["tekst"]
    tekst = af.rapport_tekst(plan, apply=False)
    assert "Wat er aan deze snit hangt" in tekst
    assert "pulse_completed" in tekst and "serpapi_trends" in tekst


# ── Richting C: wat ligt er op zijn bord ────────────────────────────────────

def test_open_projecten_van_een_rol_tellen_mee(tmp_path):
    """RICHTING C, EN HIJ KOSTTE EEN HANDMATIGE OPRUIMING. A en B kijken naar de CODE — wat
    publiceert deze rol, wie roept die skill aan — en dat is precies wat statische analyse ziet.
    Wat er op zijn bord ligt staat niet in de code maar in de DATA, en die vraag stelde niemand.
    Gevolg op prod: 5 open projecten op rollen die ná het aanmaken slapend werden gelegd."""
    from nooch_village.projects import ProjectLedger
    pj = ProjectLedger(str(tmp_path / "p.json"))
    pj.create("slaper", "Iets dat nog loopt", "human")
    d = aa.rol_afhankelijkheden("slaper", None, pj)
    assert [x["titel"] for x in d["open_projecten"]] == ["Iets dat nog loopt"]


def test_een_afgerond_of_gearchiveerd_project_telt_niet_mee(tmp_path):
    from nooch_village.projects import ProjectLedger
    pj = ProjectLedger(str(tmp_path / "p.json"))
    klaar = pj.create("slaper", "Al klaar", "human")
    pj.complete(klaar, "klaar")
    weg = pj.create("slaper", "Gearchiveerd", "human")
    pj.archive(weg)
    assert aa.rol_afhankelijkheden("slaper", None, pj)["open_projecten"] == []


def test_zonder_projectstore_beweert_de_poort_niets(tmp_path):
    """Een poort die niets kan zien hoort niets te beweren — geen valse groene vinkje."""
    assert aa.rol_afhankelijkheden("slaper", None, None)["open_projecten"] == []


def test_een_generieke_inwoner_met_een_vol_bord_wordt_ook_gezien(tmp_path):
    """HET GEMISTE GEVAL. Richting A stopt bij "geen CLASS_MAP-entry = draagt geen mechanisme", en
    dat klopt voor code — maar zijn BORD kan wel vol liggen. Daarom staat richting C buiten die
    check."""
    from nooch_village.projects import ProjectLedger
    pj = ProjectLedger(str(tmp_path / "p.json"))
    pj.create("een_rol_zonder_klasse", "Werk dat blijft liggen", "human")
    d = aa.rol_afhankelijkheden("een_rol_zonder_klasse", None, pj)
    assert d["klasse"] == "" and d["open_projecten"], d


def test_de_snit_wordt_geweigerd_om_een_vol_bord(tmp_path):
    """De poort heeft tanden: open projecten blokkeren de snit tot je ze bevestigt."""
    from nooch_village.projects import ProjectLedger
    pj = ProjectLedger(str(tmp_path / "p.json"))
    pj.create("website_watcher", "Werk dat blijft liggen", "human")
    with pytest.raises(af.AfhankelijkheidNietBevestigd) as e:
        af.voer_uit(_plan(rollen=["website_watcher"]), None, data_dir="", bevestigd=False,
                    projects=pj)
    assert "OPEN PROJECT" in str(e.value)


def test_het_rapport_noemt_het_project_bij_naam(tmp_path):
    """Een waarschuwing die niet zegt WÁT er blijft liggen, laat je alsnog gokken."""
    from nooch_village.projects import ProjectLedger
    pj = ProjectLedger(str(tmp_path / "p.json"))
    pj.create("website_watcher", "Carbon footprint jaarlijks meten", "human")
    tekst = aa.rapport(["website_watcher"], [], None, pj)
    assert "OPEN PROJECT" in tekst and "Carbon footprint" in tekst
