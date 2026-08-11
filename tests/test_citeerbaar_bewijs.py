"""Citeerbaar bewijs: de critic toetst tegen wat de skills écht teruggaven.

De missie-critic verklaarde "Compliance Score: 88/100" ongegrond terwijl `claims_check` letterlijk
`score: 88` teruggaf. Twee stille grenzen samen sneden precies dat bewijs weg:

  1. `deliverables[:8]` — en de store stapelde duplicaten, dus die acht waren zeven keer hetzelfde;
  2. `str(d)[:600]` — en `d` was alleen de samenvattingstekst, niet de skill-uitvoer.

Gemeten op productie: `88` stond niet in het critic-venster, `Safe to Use` ook niet. Van de vier
gevlagde beweringen waren er drie echt en één verzonnen ("Annex I 2a").

Drie eigenschappen die hier bewaakt worden:
  1. een veld uit de skill-uitvoer is los aanhaalbaar, mét zijn herkomst;
  2. begrenzen mag, stil begrenzen niet;
  3. ontdubbelen wist geen bewijs-historie — de Kroniek verwijst via `result_ref` naar een
     deliverable-id, dus vervangen betekent markeren, niet weggooien.
"""
from __future__ import annotations

import logging

from nooch_village.citeerbaar import bewijsblok, velden_van
from nooch_village.deliverable_store import DeliverableStore
from nooch_village import missie_critic as mc

# De echte uitvoer van claims_check bij c0641e032729, ingekort.
CLAIMS_CHECK = {"ok": True, "score": 88, "rood": 1, "versie": "2026-07-18.2",
                "bevindingen": [{"term": "planet-safe / planet-friendly", "stoplicht": "red",
                                 "categorie": "Generiek", "hardness": "hard"}]}


# ── 1. Een veld is los aanhaalbaar ──────────────────────────────────────────

def test_het_cijfer_dat_de_critic_niet_zag_is_nu_citeerbaar():
    velden = velden_van("claims_check", CLAIMS_CHECK)
    plat = {veld: w for _s, veld, w in velden}
    assert plat["score"] == "88"
    assert plat["bevindingen[0].stoplicht"] == "red"
    assert plat["bevindingen[0].categorie"] == "Generiek"
    assert all(s == "claims_check" for s, _v, _w in velden)      # herkomst reist mee


def test_run_administratie_telt_niet_als_citeerbaar_feit():
    """Een weeknummer of versiestring is geen bevinding: anders vult het bewijsvenster zich met
    boekhouding in plaats van met feiten."""
    plat = {veld for _s, veld, _w in velden_van("claims_check", CLAIMS_CHECK)}
    assert "versie" not in plat and "ok" not in plat


def test_een_domeinveld_is_geen_run_administratie():
    """Deze laag leende eerst `inhabitant._META_KEYS`, en dat was reference-don't-copy verkeerd
    toegepast: dat zijn twee verschillende vragen. `_classify_result` vraagt "draagt dit resultaat
    inhoud?" en mag `term` negeren; hier is `term` juist DE bevinding.

    Gemeten gevolg: `bevindingen[0].term = planet-safe / planet-friendly / planet-loving` viel uit
    het bewijsvenster terwijl het rapport die lijst wél citeerde — precies het gat dat deze module
    moest dichten, opnieuw gemaakt door zijn eigen filter."""
    plat = {veld: w for _s, veld, w in velden_van("claims_check", CLAIMS_CHECK)}
    assert plat["bevindingen[0].term"] == "planet-safe / planet-friendly"
    for domein in ("term", "query", "bron", "locale", "corpus", "reden", "reason", "waarom"):
        uit = velden_van("x", {domein: "een echte waarde"})
        assert uit and uit[0][1] == domein, f"{domein} hoort citeerbaar te zijn"


def test_een_lange_waarde_wordt_gemarkeerd_afgekapt():
    velden = velden_van("x", {"tekst": "a" * 500})
    assert velden[0][2].endswith("…") and len(velden[0][2]) < 500


# ── 2. Begrenzen mag, stil begrenzen niet ───────────────────────────────────

def _recs(n):
    return [{"id": f"r{i}", "skill": "claims_check", "summary": f"s{i}"} for i in range(n)]


def test_alle_deliverables_tellen_mee_niet_de_eerste_acht():
    """DE fix. Met ontdubbeling zijn het er 2 tot 6 per project, dus 'alle' is goedkoop — maar de
    regel moet ook staan als een groot project ooit veel unieke deliverables heeft."""
    blok = bewijsblok(_recs(12), lambda rid: {"nummer": rid})
    assert all(f"= r{i}" in blok for i in range(12))


def test_afkappen_gebeurt_op_tekens_en_zegt_dat_het_afkapte(caplog):
    """Geen stille cap — zelfde regel als bij het thinking-budget, het afgekapte critic-antwoord en
    de premium-cap-verlaging. Wie het bewijs leest moet weten dat hij een fractie ziet."""
    with caplog.at_level(logging.WARNING):
        blok = bewijsblok(_recs(60), lambda rid: {"veld": "x" * 200}, max_chars=800)
    assert "bewijs is onvolledig" in blok                          # de LLM leest het mee
    assert "CITEERBAAR_CAP" in caplog.text                         # en de mens ziet het in het log


def test_zonder_sidecar_blijft_de_samenvatting_over():
    blok = bewijsblok(_recs(2), lambda rid: None)
    assert "samenvatting = s0" in blok


def test_een_kapotte_sidecar_breekt_het_bewijs_niet():
    def _stuk(rid):
        raise OSError("schijf weg")
    assert "samenvatting = s0" in bewijsblok(_recs(1), _stuk)


# ── 3. De critic gebruikt het, en valt nooit stil terug op minder ───────────

def test_de_critic_krijgt_het_citeerbare_bewijs():
    gezien = {}

    class _Vangt:
        def run(self, payload, context=None):
            gezien.update(payload)
            return {"ok": True, "oordeel": "houdt stand", "ongegrond": []}

    recs = [{"id": "r1", "skill": "claims_check", "summary": "📎 …"}]
    mc._gegrond("doc", recs, {}, skill=_Vangt(), content_for=lambda rid: CLAIMS_CHECK)
    assert "claims_check | score = 88" in gezien["bewijs"]


def test_zonder_content_for_valt_hij_terug_op_alles_niet_op_acht():
    """De terugval mag nooit stiekem minder bewijs geven dan de aanroeper denkt: geen [:8], geen
    [:600] — dat waren precies de twee grenzen die dit probleem maakten."""
    recs = [{"id": f"r{i}", "skill": "s", "summary": f"bevinding-{i}"} for i in range(12)]
    bewijs = mc._bewijs(recs)
    assert all(f"bevinding-{i}" in bewijs for i in range(12))


# ── 4. Ontdubbelen zonder de audit-trail te wissen ──────────────────────────

def _store(tmp_path):
    return DeliverableStore(str(tmp_path / "deliverables.json"))


def test_een_herdraai_vervangt_zijn_voorganger(tmp_path):
    """Productiebug, niet herdraai-rommel: elke retry stapelde. Op prod stonden er 30 bij één
    project waarvan 5 uniek — de synthese zag er zes en betaalde zeven keer voor hetzelfde."""
    st = _store(tmp_path)
    for n in (1, 2, 3):
        st.add(project_id="p", role="r", skill="claims_check", checklist_item="i1",
               title="Toets de claim", content={"score": n}, summary=f"run {n}")
    geldend = st.for_project("p")
    assert len(geldend) == 1
    assert st.content_for(geldend[0]["id"]) == {"score": 3}        # de laatste wint


def test_de_vervangen_records_blijven_bestaan_voor_de_kroniek(tmp_path):
    """De Kroniek verwijst via `result_ref` naar een deliverable-id. Weggooien zou die verwijzing
    kapotmaken; markeren houdt de audit-trail heel."""
    st = _store(tmp_path)
    eerste = st.add(project_id="p", role="r", skill="s", checklist_item="i1", title="t",
                    content={"a": 1}, summary="een")
    tweede = st.add(project_id="p", role="r", skill="s", checklist_item="i1", title="t",
                    content={"a": 2}, summary="twee")
    assert len(st.for_project("p", inclusief_vervangen=True)) == 2
    assert st.content_for(eerste["id"]) == {"a": 1}                # sidecar staat er nog
    assert st._items[eerste["id"]]["vervangen_door"] == tweede["id"]


def test_verschillende_items_vervangen_elkaar_niet(tmp_path):
    st = _store(tmp_path)
    st.add(project_id="p", role="r", skill="s", checklist_item="i1", title="t",
           content={"a": 1}, summary="een")
    st.add(project_id="p", role="r", skill="s", checklist_item="i2", title="t",
           content={"a": 2}, summary="twee")
    assert len(st.for_project("p")) == 2


def test_zonder_checklist_item_vervangt_er_niets(tmp_path):
    """Losse deliverables (zonder item-adres) horen niet elkaars voorganger te zijn — dan zou een
    tweede vrije levering de eerste stilzwijgend wissen."""
    st = _store(tmp_path)
    st.add(project_id="p", role="r", skill="s", checklist_item="", title="t",
           content={"a": 1}, summary="een")
    st.add(project_id="p", role="r", skill="s", checklist_item="", title="t",
           content={"a": 2}, summary="twee")
    assert len(st.for_project("p")) == 2


# ── 5. B: de promptregel verbiedt verzinnen, niet concreetheid ──────────────

def test_de_synthese_regel_noemt_beide_helften():
    """De valkuil van deze fix is dat het rapport vaag wordt. Grondering moet het PRECIEZER maken:
    heb je het specifieke niet, zeg dan wat je wél hebt met bron — niet 'mogelijk zorgen'."""
    src = open("nooch_village/inhabitant.py", encoding="utf-8").read()
    assert "een score, een status" in src and "wetsartikel of bepaling" in src
    assert "Terugvallen op 'er zijn mogelijk zorgen' is FOUT" in src
    assert "Verbied jezelf het verzinnen" in src
    assert "CITEERBARE FEITEN" in src


def test_migratie_ontdubbelt_bestaande_stapels_zonder_te_wissen(tmp_path):
    """De ontdubbeling geldt anders alleen voor NIEUWE runs, en houdt elk project dat nooit meer
    herdraait zijn stapel — op prod stond er één met 30 records waarvan 5 uniek."""
    st = DeliverableStore(str(tmp_path / "d.json"))
    ids = []
    for n in range(4):                                   # bouw de oude situatie na: geen markering
        r = st.add(project_id="p", role="r", skill="s", checklist_item="i1", title="t",
                   content={"n": n}, summary=f"run {n}")
        ids.append(r["id"])
    for r in st._items.values():
        r.pop("vervangen_door", None)
    st._save()
    assert len(st.for_project("p")) == 4                 # zonder migratie: de hele stapel

    assert st.migrate_vervangen() == 3
    assert st.migrate_vervangen() == 0                   # idempotent
    geldend = st.for_project("p")
    assert len(geldend) == 1 and geldend[0]["id"] == ids[-1]
    assert len(st.for_project("p", inclusief_vervangen=True)) == 4
    assert all(st.content_for(i) is not None for i in ids)   # geen sidecar gewist


# ── 6. De critic beoordeelt het rapport, niet zijn eigen venster ────────────

def test_het_rapport_wordt_niet_stil_op_6000_tekens_afgekapt():
    """`[:6000]` liet een rapport van 8872 tekens halverwege een zin binnenkomen, en de critic
    vlagde dat als gebrek: "de conclusie is afgekapt ('Wat we zek...') waardoor het eindoordeel
    niet toetsbaar is". Hij beoordeelde zijn eigen venster."""
    doc = "x" * 8872
    assert mc._te_toetsen(doc) == doc


def test_moet_het_toch_afgekapt_dan_staat_dat_in_de_prompt(caplog):
    with caplog.at_level(logging.WARNING):
        uit = mc._te_toetsen("y" * (mc.MAX_RAPPORT_CHARS + 500))
    assert "afkapping is van de TOETS, niet van het rapport" in uit
    assert "CRITIC_RAPPORT_CAP" in caplog.text


def test_de_ongegrond_lijst_is_alleen_voor_ongegronde_beweringen():
    """De critic zette er ook vorm-gebreken en nuances in ("dit klopt met de onderbouwing, maar…"),
    waardoor de grond-as zakte op iets dat geen grondingsprobleem is."""
    assert "ALLEEN voor beweringen die de onderbouwing niet dekt" in mc._KADER
    assert "zet die in 'revisie'" in mc._KADER.replace("\n", " ")


# ── 7. Een herschrijving leest zijn eigen proza niet ────────────────────────

class _DocStore:
    def __init__(self, tier=None, ts=0.0, doc=""):
        self._meta = {"tier": tier, "ts": ts} if tier else {}
        self._doc = doc

    def meta(self, pid):
        return dict(self._meta)


def _vv(store, recs=(), doc="tekst", log=logging.getLogger("t")):
    from nooch_village.inhabitant import _vorige_versie
    return _vorige_versie(store, "p", doc, list(recs), log)


def test_de_synthese_krijgt_zijn_eigen_vorige_draft_niet_te_zien():
    """Het witwas-mechanisme: op c0641e032729 stond 'Term | planet-safe / planet-friendly /
    planet-loving' in het rapport terwijl de huidige claims_check-uitvoer dat veld niet meer heeft.
    Die lijst kwam uit een oudere skill-versie en overleefde drie herschrijvingen via de vorige
    draft — elke keer door zichzelf bevestigd."""
    uit = _vv(_DocStore(tier="anthropic:claude-sonnet-5"), doc="OUD PROZA MET EEN VERZINSEL")
    assert "OUD PROZA" not in uit
    assert "BEWUST niet te zien" in uit


def test_in_plaats_daarvan_komt_er_een_compacte_melding_van_nieuw_bewijs():
    recs = [{"skill": "claims_check", "title": "Toets de claim", "created_at": 200},
            {"skill": "claim_evidence", "title": "Zoek onderbouwing", "created_at": 50}]
    uit = _vv(_DocStore(tier="x", ts=100), recs=recs)
    assert "1 deliverable(s)" in uit
    assert "claims_check: Toets de claim" in uit
    assert "claim_evidence" not in uit                      # ouder dan de vorige versie


def test_zonder_nieuw_bewijs_zegt_hij_dat_ook():
    assert "geen nieuw bewijs bijgekomen" in _vv(_DocStore(tier="x", ts=100), recs=[])


def test_een_mens_geredigeerde_versie_gaat_wel_mee():
    """Het gevaar is ZELF-witwassen, niet tekst op zich. Een mens-edit is invoer, net als de
    #task-comments — die stilzwijgend weggooien zou erger zijn dan wat we repareren. Herkenning via
    de herkomst-sidecar: geen tier = geen model verantwoordelijk."""
    uit = _vv(_DocStore(tier=None), doc="DE MENS SCHREEF DIT ZELF")
    assert "DE MENS SCHREEF DIT ZELF" in uit
    assert "dit is invoer, geen eigen tekst" in uit


def test_zonder_document_geen_gedoe():
    assert "nog geen eerdere versie" in _vv(_DocStore(tier="x"), doc="")


def test_onleesbare_herkomst_houdt_de_draft_buiten_de_prompt(caplog):
    """Fail-closed op de kant die telt: weten we niet wie het schreef, dan gaan we ervan uit dat het
    model het was. Andersom zou een verzinsel er stilzwijgend weer in glippen."""
    class _Stuk:
        def meta(self, pid):
            raise OSError("sidecar weg")
    with caplog.at_level(logging.WARNING):
        uit = _vv(_Stuk(), doc="OUD PROZA")
    assert "OUD PROZA" not in uit and "NIET meegestuurd" in caplog.text


# ── 8. Een stoplicht is een signaal, geen vrijwaring ────────────────────────

def test_de_schrijver_leest_een_groen_stoplicht_niet_als_goedkeuring():
    """De 7c1e576-klasse: 'vegan | stoplicht = green' werd '100% Vegan: Status Groen (Safe to Use)'
    en 'kan zonder wijziging blijven staan'. Een term-scan die niets vlagt is geen juridisch
    oordeel, en voor compliance is die categoriefout gevaarlijker dan een gemist signaal."""
    src = open("nooch_village/inhabitant.py", encoding="utf-8").read()
    assert "een SIGNAAL, geen" in src and "juridisch of veiligheidsoordeel" in src
    assert "veilig te gebruiken" in src and "mag zonder wijziging blijven staan" in src
