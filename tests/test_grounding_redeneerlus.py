"""Grounding: de grondwet en de Kroniek in de redeneerlus.

Het probleem dat dit oplost: de productie- en oordeelsprompts kregen een kennisblok dat inzichten
tot *titel plus verdict* strippte, de Kroniek helemaal niet noemde, en de missie nergens. Daardoor
kon een rol (a) opnieuw onderzoeken wat al bevestigd was, (b) een kennisgat als bevinding
presenteren, en (c) een inzicht als vaststaand feit behandelen omdat de falsifier eraf was.

De twee guards die de opdracht vraagt staan onderaan:
  - een onderwerp dat al BEVESTIGD in de Kroniek staat, duikt op in de prompt;
  - een inzicht draagt zijn falsifier mee.

En over alles heen: fail-soft. Geen embeddings, geen Kroniek, geen store → het oude lexicale
gedrag, nooit slechter. Dat is geen nettigheid: dit blok zit in het hete pad van élk projectwerk.
"""
from __future__ import annotations

import json
import os

import pytest

from nooch_village import kennis_context as kc
from nooch_village.evidence_ledger import EvidenceLedger
from nooch_village.kennisbank import KennisbankStore
from nooch_village.mission import ANCHOR_PURPOSE


@pytest.fixture
def dd(tmp_path):
    return str(tmp_path)


def _kroniek(dd, rijen):
    led = EvidenceLedger(os.path.join(dd, "evidence_ledger.jsonl"))
    for r in rijen:
        led.record(**r)
    return led


def _inzicht(dd, **kw):
    st = KennisbankStore(os.path.join(dd, "kennisbank.json"))
    return st.add(kw.pop("title"), **kw)


def _project(dd, **kw):
    from nooch_village.projects import ProjectLedger
    led = ProjectLedger(os.path.join(dd, "projects.json"))
    return led.create(kw.pop("owner", "harry_hemp"), kw.pop("scope"), "human", **kw)


# ── GUARD 1: bevestigd in de Kroniek → zichtbaar in de prompt ────────────────

def test_bevestigd_onderwerp_duikt_op_in_de_prompt(dd):
    """DE guard. Staat er bevestigd bewijs over mycelium in de Kroniek, dan moet een rol die aan
    een mycelium-project begint dat in zijn prompt zien — anders onderzoekt hij het opnieuw."""
    _kroniek(dd, [
        dict(role_id="harry_hemp", skill="openalex_evidence", query="mycelium leather durability",
             source="openalex", status="bevestigd", result_ref="12 werken, 340 citaties"),
    ])
    kennis = kc.kennis_voor(dd, "Onderzoek de duurzaamheid van mycelium leather voor schoenen")
    assert kennis["kroniek"]["bevestigd"], "bevestigd bewijs niet teruggevonden"
    blok = kc.kennis_blok(kennis)
    assert "DE KRONIEK" in blok
    assert "[BEVESTIGD]" in blok
    assert "mycelium leather durability" in blok
    assert "12 werken, 340 citaties" in blok          # het bewijs zelf, niet alleen de vraag
    assert "onderzoek dit niet opnieuw" in blok       # en de instructie die eruit volgt


def test_leeg_record_wordt_als_kennisgat_benoemd_niet_als_bevinding(dd):
    """'Leeg' is een eersteklas uitkomst: onderzocht, niets gevonden. Als de prompt dat niet zegt,
    presenteert het model het gat als een bevinding."""
    _kroniek(dd, [dict(role_id="harry_hemp", skill="epo_patents", query="mycelium coating patent",
                       source="epo", status="leeg")])
    blok = kc.kennis_blok(kc.kennis_voor(dd, "Zoek patenten voor mycelium coating"))
    assert "[LEEG]" in blok
    assert "kennisgat, geen bevinding" in blok


def test_foute_bron_wordt_niet_als_kennis_gepresenteerd(dd):
    _kroniek(dd, [dict(role_id="harry_hemp", skill="epo_patents", query="mycelium coating patent",
                       source="epo", status="fout")])
    blok = kc.kennis_blok(kc.kennis_voor(dd, "Zoek patenten voor mycelium coating"))
    assert "[FOUT]" in blok and "hierover weten we niets" in blok


def test_last_good_levert_het_gezaghebbende_record(dd):
    """`last_good` was dode code. Hij is nu de bron van de bewijsregel: bij meerdere bevestigde
    records voor dezelfde vraag telt de MEEST RECENTE, niet de eerste die je tegenkomt."""
    _kroniek(dd, [
        dict(role_id="r", skill="openalex_evidence", query="hemp fibre strength", source="openalex",
             status="bevestigd", result_ref="OUD: 3 werken", ts=1000),
        dict(role_id="r", skill="openalex_evidence", query="hemp fibre strength", source="openalex",
             status="bevestigd", result_ref="NIEUW: 40 werken", ts=2000),
    ])
    blok = kc.kennis_blok(kc.kennis_voor(dd, "Wat weten we over hemp fibre strength?"))
    assert "NIEUW: 40 werken" in blok
    assert "OUD: 3 werken" not in blok


# ── GUARD 2: een inzicht draagt zijn falsifier mee ───────────────────────────

def test_inzicht_draagt_zijn_falsifier_en_caveat_mee(dd):
    """DE tweede guard. Zonder falsifier is een inzicht een mening met een id: de lezer kan niet
    zien waaraan hij zou merken dat het niet meer klopt, en behandelt het als vaststaand."""
    _inzicht(dd, title="Plasticvrij zijn is onze werkelijke edge",
             why="Mensen wachten maanden op een pre-order en kopen toch",
             falsifier="Een concurrent komt met een overtuigender plasticvrij-verhaal en snellere levering",
             caveat="Geldt zolang levertijd geen dealbreaker wordt",
             reframe="Niet 'duurzaam' maar 'aantoonbaar fossielvrij'")
    kennis = kc.kennis_voor(dd, "Hoe positioneren we plasticvrij als edge?")
    assert kennis["inzichten"], "inzicht niet teruggevonden"
    ins = kennis["inzichten"][0]
    assert ins["falsifier"].startswith("Een concurrent")
    assert ins["caveat"].startswith("Geldt zolang")

    blok = kc.kennis_blok(kennis)
    assert "WEERLEGD ALS: Een concurrent" in blok
    assert "LET OP: Geldt zolang" in blok


def test_inzicht_zonder_falsifier_krijgt_geen_lege_regel(dd):
    """Een lege 'WEERLEGD ALS:'-regel is erger dan geen regel — hij suggereert een toets die er
    niet is."""
    _inzicht(dd, title="Barefoot schoenen versterken de voetspieren", why="onderzoek", falsifier="")
    blok = kc.kennis_blok(kc.kennis_voor(dd, "Wat weten we over barefoot schoenen?"))
    assert "Barefoot schoenen versterken" in blok
    assert "WEERLEGD ALS:" not in blok


# ── De grondwet ─────────────────────────────────────────────────────────────

def test_grondwet_staat_altijd_bovenaan(dd):
    for kennis in ({}, kc.kennis_voor(dd, "wat dan ook")):
        blok = kc.kennis_blok(kennis)
        assert blok.startswith("GRONDWET (waaraan dit werk moet voldoen):")
        assert ANCHOR_PURPOSE in blok


def test_grondwet_komt_uit_mission_niet_uit_een_kopie():
    """Reference, don't copy: de missietekst leeft op één plek. Zou hij hier overgetypt zijn, dan
    drijft de prompt af zodra de missie verandert."""
    src = open("nooch_village/kennis_context.py", encoding="utf-8").read()
    assert "from nooch_village.mission import ANCHOR_PURPOSE" in src
    assert "most sustainable shoe brand" not in src        # geen tweede exemplaar van de tekst


# ── Pre-flight ──────────────────────────────────────────────────────────────

def test_weten_we_dit_al_draait_automatisch(dd):
    """De skill was opt-in en gebeurde daardoor zelden. Nu draait hij bij élke raadpleging."""
    _inzicht(dd, title="Mycelium leer is nog niet schaalbaar", why="pilots blijven klein")
    kennis = kc.kennis_voor(dd, "Is mycelium leer schaalbaar voor onze productie?")
    assert kennis["preflight"], "pre-flight is niet gedraaid"
    assert kennis["preflight"]["bekend"] is True
    assert "WETEN WE DIT AL? JA" in kc.kennis_blok(kennis)


def test_preflight_zegt_nee_bij_onontgonnen_terrein(dd):
    kennis = kc.kennis_voor(dd, "Wat weten we over titanium veterogen uit IJsland?")
    assert kennis["preflight"].get("bekend") is False
    assert "WETEN WE DIT AL? NEE" in kc.kennis_blok(kennis)


# ── Eerdere projecten ───────────────────────────────────────────────────────

def test_eerdere_projecten_komen_mee_met_hun_antwoord(dd):
    _project(dd, owner="harry_hemp", scope="Mycelium leer verkennen als bovenmateriaal",
             dod_outcome="Nog niet schaalbaar onder 500 paar")
    blok = kc.kennis_blok(kc.kennis_voor(dd, "Kunnen we mycelium leer gebruiken als bovenmateriaal?"))
    assert "EERDERE PROJECTEN HIEROVER" in blok
    assert "Nog niet schaalbaar" in blok


def test_project_vindt_zichzelf_niet_terug(dd):
    """Zonder exclude_pid vindt elk project zichzelf als 'eerder project' — dan is er altijd een
    treffer en zegt de sectie niets."""
    pid = _project(dd, scope="Mycelium leer verkennen als bovenmateriaal")
    kennis = kc.kennis_voor(dd, "Mycelium leer verkennen als bovenmateriaal", exclude_pid=pid)
    assert kennis["projecten"] == []


# ── Fail-soft: nooit slechter dan het oude gedrag ───────────────────────────

def test_geen_kroniek_geen_stores_blokkeert_niets(dd):
    """Een lege data_dir: geen enkele store bestaat. Het blok moet nog steeds renderen (grondwet)
    en mag niet klappen."""
    kennis = kc.kennis_voor(dd, "wat weten we over mycelium")
    assert kennis["kroniek"] == {"bevestigd": [], "leeg": [], "fout": []}
    assert kennis["projecten"] == [] and kennis["inzichten"] == []
    assert kc.kennis_blok(kennis).startswith("GRONDWET")


def test_kapotte_kroniek_valt_zacht(dd, monkeypatch):
    open(os.path.join(dd, "evidence_ledger.jsonl"), "w").write("{niet eens json\n")
    kennis = kc.kennis_voor(dd, "mycelium")
    assert kennis["kroniek"]["bevestigd"] == []          # geen crash, gewoon leeg


def test_zonder_embeddings_valt_de_rangschikking_terug_op_lexicaal(dd, monkeypatch):
    """De harde fail-soft-eis: geen embeddings → het oude woordoverlap-gedrag, niet minder."""
    _inzicht(dd, title="Barefoot schoenen versterken de voetspieren", why="onderzoek")
    monkeypatch.setattr("nooch_village.kennis_embeddings.rank_semantisch",
                        lambda *a, **k: None)           # geen sleutel/index → None
    kennis = kc.kennis_voor(dd, "Wat weten we over barefoot schoenen?")
    assert [i["tekst"] for i in kennis["inzichten"]] == ["Barefoot schoenen versterken de voetspieren"]


def test_semantische_route_wordt_gebruikt_als_hij_kan(dd, monkeypatch):
    """En andersom: is er wél een semantische ranglijst, dan wint die van de woordoverlap — dat is
    het punt van de vervanging ('paddenstoelvezel' moet 'mycelium' vinden)."""
    gebruikt = {}

    def _nep(zoektekst, items, index_path, tekst_fn, **kw):
        gebruikt["ja"] = True
        return list(items)[:1]

    monkeypatch.setattr("nooch_village.kennis_embeddings.rank_semantisch", _nep)
    _inzicht(dd, title="Mycelium is een paddenstoelvezel", why="materiaal")
    kennis = kc.kennis_voor(dd, "paddenstoelvezel als bovenmateriaal")
    assert gebruikt.get("ja"), "de semantische route is niet geprobeerd"
    assert kennis["inzichten"]


# ── De injectiepunten ───────────────────────────────────────────────────────

def test_alle_drie_de_prompts_injecteren_het_blok():
    """work_one, de einddocument-synthese en het voorstel halen alle drie het grondingsblok op.
    Zonder deze test kan een van de drie stilletjes terugvallen op een kale prompt."""
    worker = open("nooch_village/project_worker.py", encoding="utf-8").read()
    assert "kennis_blok" in worker and "kennis.strip()" in worker

    inh = open("nooch_village/inhabitant.py", encoding="utf-8").read()
    i = inh.index("def synthesize_einddocument")
    body = inh[i:i + 6000]
    assert "kennis_blok(kennis_voor(" in body
    assert '(grond + "\\n\\n" if grond else "")' in body

    voorstel = open("nooch_village/skills_impl/voorstel.py", encoding="utf-8").read()
    assert "kennis_blok(kennis_voor(" in voorstel
    assert '(grond + "\\n\\n" if grond else "")' in voorstel


def test_einddocument_zonder_data_dir_blijft_werken():
    """De cockpit-actie en de puls geven data_dir mee; een oude caller die dat niet doet mag geen
    fout krijgen — dan zou een deploy halverwege het einddocument breken."""
    import inspect

    from nooch_village.inhabitant import synthesize_einddocument
    sig = inspect.signature(synthesize_einddocument)
    assert sig.parameters["data_dir"].default == ""
