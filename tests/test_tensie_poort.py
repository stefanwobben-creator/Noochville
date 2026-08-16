"""De poort vóór elke menselijke escalatie.

De founder-inbox stond op 74 items terwijl er drie beslissingen in zaten. De rest was werk dat het
dorp bezit: projecten die zichzelf als verse tensie uitspuwden, taken voor een bemande rol die bij
de mens landden, en dezelfde kapotte bron in vier varianten.

Wat deze tests vastleggen is niet de bewoording maar de trechter:

  - een tensie die al aan een project hangt, pingt niemand;
  - het `human`-label wordt NIET geloofd (het zat 4 van de 11 keer fout) — élk item gaat eerst
    door dezelfde eigenaars-match;
  - de match moet 'geen rol past' kunnen zeggen, anders is de uitweg naar deur 1 en 2 dood;
  - een KAPOTTE bestaande capaciteit is ops, een ONTBREKENDE is een skill-deur;
  - niets verdwijnt stil: wat geen regel pakt komt er als `onbeslist` uit.
"""
from __future__ import annotations

import time

import pytest

from nooch_village import tensie_poort as tp


# ── Dubbels ─────────────────────────────────────────────────────────────────

class _Def:
    def __init__(self, purpose="", accs=(), domains=()):
        self.purpose = purpose
        self.accountabilities = list(accs)
        self.domains = list(domains)
        self.name = ""


class _Rec:
    def __init__(self, rid, purpose="", accs=()):
        self.id = rid
        self.definition = _Def(purpose, accs)
        self.archived = False
        self.type = "role"


class _Records:
    def __init__(self, recs):
        self._r = {r.id: r for r in recs}

    def get(self, rid):
        return self._r.get(rid)

    def all(self):
        return list(self._r.values())


RECS = _Records([
    _Rec("compliance", "Bewaakt dat elke publieke claim juridisch houdbaar is",
         ["claims toetsen aan EmpCo en ACM", "bewijs vastleggen in de Kroniek"]),
    _Rec("harry_hemp", "Onderzoekt materialen", ["materiaalonderzoek uitvoeren"]),
])


class _Projects:
    def __init__(self, d=None):
        self._p = dict(d or {})

    def get(self, pid):
        return self._p.get(pid)


def _n(snippet, pid="", at=None):
    return {"id": "n1", "snippet": snippet, "project_id": pid, "at": at or time.time()}


def _llm(antwoord):
    """Een reason_fn-dubbel: geeft altijd hetzelfde JSON-antwoord."""
    return lambda prompt, **kw: antwoord


# ── 1. Geborgd ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("status", ["running", "blocked", "queued", "future"])
def test_een_levend_project_pingt_niemand(status):
    """De 'Project van X vastgelopen'-klasse: het werk is belegd, dus het hoort niet als verse
    tensie terug te komen. Ook `blocked` — juist die spuwde zichzelf uit."""
    b = tp.poort(_n("Project van Harry vastgelopen", "p1"),
                 projects=_Projects({"p1": {"status": status}}), records=RECS, gebruik_llm=False)
    assert b.deur == tp.GEBORGD and "p1" in b.bewijs


def test_een_afgerond_project_is_klaar():
    b = tp.poort(_n("iets", "p1"), projects=_Projects({"p1": {"status": "done"}}),
                 records=RECS, gebruik_llm=False)
    assert b.deur == tp.AFGEHANDELD


def test_verdwenen_project_wordt_niet_stil_geborgd(caplog):
    """Een dangling project-id is geen borging maar zelf een signaal."""
    with caplog.at_level("WARNING"):
        b = tp.poort(_n("iets", "weg"), projects=_Projects(), records=RECS, gebruik_llm=False)
    assert b.deur != tp.GEBORGD
    assert "verdwenen project" in caplog.text


def test_project_dat_op_een_mens_wacht_valt_niet_stil():
    """Zou dit als 'in uitvoering' gelden, dan beweegt het nooit meer."""
    p = {"status": "blocked", "park": {"reden": "human", "items": [{"reden": "human"}]}}
    b = tp.geborgd(_n("iets", "p1"), _Projects({"p1": p}))
    assert b is None


# ── 2. Routering, met een echte 'geen rol past' ─────────────────────────────

def test_een_letterlijk_genoemde_rol_kost_geen_llm_call():
    b = tp.poort(_n("[rol compliance onbemand] beoordeel deze claim"), projects=_Projects(),
                 records=RECS, reason_fn=_llm(None))
    assert b.deur == tp.GEROUTEERD and b.naar_rol == "compliance"


def test_de_match_routeert_op_eigenaarschap():
    antwoord = '{"role": "compliance", "kind": "missing_capability", "capability": ""}'
    b = tp.poort(_n("Claim-scan: 4 model-gevonden claims zonder lijstterm"),
                 projects=_Projects(), records=RECS, reason_fn=_llm(antwoord))
    assert b.deur == tp.GEROUTEERD and b.naar_rol == "compliance"


def test_de_match_kan_geen_rol_past_uitspreken():
    """De harde eis. Zonder deze uitspraak bereikt niets deur 1 of 2 en is de uitweg dood."""
    antwoord = '{"role": "NONE", "kind": "missing_capability", "capability": "iets"}'
    rol, kind, waarom = tp.match("iets heel nieuws", RECS, reason_fn=_llm(antwoord))
    assert rol == "" and kind == "missing_capability" and "expliciet geen eigenaar" in waarom


def test_een_verzonnen_rol_wordt_geweigerd():
    """Fail-closed: een item op het verkeerde bureau kost een hop en levert een vals gat-record op."""
    rol, _, _ = tp.match("iets", RECS,
                         reason_fn=_llm('{"role": "bestaat_niet", "kind": "missing_capability"}'))
    assert rol == ""


def test_zonder_llm_antwoord_gaat_het_item_door_naar_de_deuren(caplog):
    """Het dorp mag langzamer worden als de LLM wegvalt, niet stiller."""
    b = tp.poort(_n("een tensie zonder duidelijke eigenaar"), projects=_Projects(),
                 records=RECS, reason_fn=_llm(None))
    assert b.deur in (tp.DEUR_ROL, tp.DEUR_SKILL, tp.DEUR_BESLUIT, tp.ONBESLIST)


# ── 3. Mens-werk: het label wordt niet geloofd ──────────────────────────────

def test_mens_gelabeld_werk_dat_een_rol_bezit_gaat_naar_die_rol():
    """Vier van de elf `human`-items waren rolwerk. Het label telt niet; de match wel."""
    p = {"status": "blocked", "park": {"reden": "human"}}
    antwoord = '{"role": "harry_hemp", "kind": "missing_capability", "capability": ""}'
    b = tp.poort(_n("Flag if the OpenAlex query returns a noisy result count", "p1"),
                 projects=_Projects({"p1": p}), records=RECS, reason_fn=_llm(antwoord))
    assert b.deur == tp.GEROUTEERD and b.naar_rol == "harry_hemp"


def test_echt_fysiek_werk_blijft_mens_werk():
    p = {"status": "blocked", "park": {"reden": "human"}}
    antwoord = '{"role": "NONE", "kind": "human_external", "capability": ""}'
    b = tp.poort(_n("Laat de samples testen in een erkend lab (TÜV)", "p1"),
                 projects=_Projects({"p1": p}), records=RECS, reason_fn=_llm(antwoord))
    assert b.deur == tp.MENS_WERK


def test_het_human_label_alleen_maakt_nog_geen_mens_werk():
    """Zonder 'geen rol past' én 'fysiek' is een human-label niets waard."""
    p = {"status": "blocked", "park": {"reden": "human"}}
    antwoord = '{"role": "NONE", "kind": "missing_capability", "capability": "iets"}'
    b = tp.poort(_n("iets wat software zou kunnen", "p1"), projects=_Projects({"p1": p}),
                 records=RECS, reason_fn=_llm(antwoord))
    assert b.deur != tp.MENS_WERK


# ── 4. De ops-grens ─────────────────────────────────────────────────────────

def test_een_kapotte_bron_is_ops_geen_founder_besluit():
    b = tp.deur(_n("⚠️ Capaciteit ontbreekt bij een rol: Bron 'gsc/clicks' levert niet meer"))
    assert b.deur == tp.OPS and b.klasse == "bron levert niet meer"


def test_een_overgeslagen_puls_is_ops():
    assert tp.deur(_n("⚠️ Puls-uitval: rol 'harry_hemp' liet geen hartslag na")).deur == tp.OPS


def test_een_storing_die_aanhoudt_wordt_wel_een_vraag():
    """Eén hik is ops; drie dagen is een dode bron met een investeringskeuze eronder."""
    dag = 86400
    batch = [_n(f"Bron 'gsc/x' levert niet meer", at=time.time() - i * dag) for i in range(3)]
    b = tp.deur(batch[0], batch=batch)
    assert b.deur == tp.DEUR_BESLUIT and "houdt aan" in b.reden


def test_een_ontbrekende_capaciteit_is_wel_een_skill_deur():
    """Het onderscheid dat de ops-grens draagt: kapot ≠ bestaat niet."""
    b = tp.deur(_n("🚧 Site-scan blijft blind op 4 pagina's — home gaf HTTP 403"))
    assert b.deur == tp.DEUR_SKILL


# ── 5. De besluit-deur en de bundel ─────────────────────────────────────────

def test_een_claim_goedkeuring_is_een_founder_besluit():
    b = tp.deur(_n("⤴ beslissing gevraagd: de herformulering van 'compensated' vereist goedkeuring"))
    assert b.deur == tp.DEUR_BESLUIT and b.sleutel == "besluit:compliance"


def test_veertien_claims_worden_een_regel_met_veertien_beslissingen():
    """Klasse-dedup voor de INBOX-REGEL, niet voor de beslissing. Juridisch is elke claim een eigen
    oordeel; een blanket-approve mag niet kunnen bestaan."""
    meldingen = [_n(f"⤴ beslissing gevraagd: claim '{w}' vereist goedkeuring")
                 for w in ("conscious", "compensated", "clean", "circular economy")]
    paren = [(m, tp.deur(m)) for m in meldingen]
    groepen = tp.bundel(paren)
    assert len(groepen) == 1
    g = groepen[0]
    assert g["aantal"] == 4
    assert {m["onderwerp"] for m in g["meldingen"]} == {"conscious", "compensated", "clean",
                                                        "circular economy"}


def test_niets_verdwijnt_stil():
    b = tp.deur(_n("een melding die nergens op lijkt"))
    assert b.deur == tp.ONBESLIST and "onbeslist" in b.reden


def test_rapport_telt_wat_de_poort_deed():
    """Zonder deze telling weet niemand of er iets wegviel dat er hoorde te zijn."""
    r = tp.rapport([tp.Besluit(tp.GEBORGD, "x"), tp.Besluit(tp.OPS, "y"),
                    tp.Besluit(tp.DEUR_BESLUIT, "z", sleutel="s"),
                    tp.Besluit(tp.DEUR_BESLUIT, "z", sleutel="s")])
    assert r["in"] == 4 and r["weggefilterd"] == 2
    assert r["zichtbaar_voor_mens"] == 2 and r["na_dedup"] == 1


# ── 6. De pas: wat de poort echt doet ───────────────────────────────────────

class _Notif:
    """NotifStore-dubbel met de vier methoden die de pas gebruikt."""
    def __init__(self, items):
        self._i = list(items)

    def open_for_targets(self, targets):
        return [n for n in self._i if not n.get("archived")]

    def all(self):
        return list(self._i)

    def _f(self, nid):
        return next((n for n in self._i if n.get("id") == nid), None)

    def set_poort(self, nid, verdict):
        self._f(nid)["poort"] = verdict
        return True

    def mark_item_processed(self, nid, outcome="", by=""):
        self._f(nid).update(processed=True, outcome=outcome, processed_by=by)
        return True

    def archive_item(self, nid):
        self._f(nid)["archived"] = True
        return True


class _Ledger(_Projects):
    def __init__(self, d=None):
        super().__init__(d)
        self.gemaakt = []

    def by_status(self, status):
        return [p for p in self._p.values() if p.get("status") == status]

    def create(self, owner, scope, trigger, origin=""):
        # De echte ledger valideert `trigger` tegen een vaste set; 'tensie-poort' werd geweigerd en
        # dat kwam pas op prod boven. Het dubbel toetst het nu ook.
        assert trigger in {"clock", "human", "noochie", "tension", "role"}, trigger
        pid = f"new{len(self.gemaakt)}"
        self._p[pid] = {"id": pid, "owner": owner, "scope": scope, "status": "queued"}
        self.gemaakt.append((owner, scope, trigger, origin))
        return pid


def _items(*snips):
    return [{"id": f"n{i}", "snippet": s, "project_id": "", "at": time.time()}
            for i, s in enumerate(snips)]


def test_dry_run_muteert_niets():
    """Meten mag nooit per ongeluk opruimen — daarom is dry_run de default."""
    nf = _Notif(_items("[rol compliance onbemand] doe iets"))
    led = _Ledger()
    r = tp.draai(notif=nf, projects=led, records=RECS, targets=[("role", "x")])
    assert r["dry_run"] is True and r["gearchiveerd"] == 0
    assert led.gemaakt == [] and not nf._i[0].get("archived")


def test_gerouteerd_werk_landt_als_project_niet_als_bericht():
    """Een AI-rol leest zijn inbox nooit (#271). Routeren zonder project is een dead letter."""
    nf = _Notif(_items("[rol compliance onbemand] beoordeel claim X"))
    led = _Ledger()
    r = tp.draai(notif=nf, projects=led, records=RECS, targets=[("role", "x")], dry_run=False)
    assert led.gemaakt and led.gemaakt[0][0] == "compliance"
    assert nf._i[0]["archived"] and "gerouteerd naar compliance" in nf._i[0]["outcome"]
    assert r["projecten"]


def test_dezelfde_tensie_levert_geen_tweede_project():
    """Zonder dedup levert elke pas dezelfde projecten opnieuw af — de lus, een laag dieper."""
    nf = _Notif(_items("[rol compliance onbemand] beoordeel claim X"))
    led = _Ledger()
    tp.draai(notif=nf, projects=led, records=RECS, targets=[("role", "x")], dry_run=False)
    nf2 = _Notif(_items("[rol compliance onbemand] beoordeel claim X"))
    tp.draai(notif=nf2, projects=led, records=RECS, targets=[("role", "x")], dry_run=False)
    assert len(led.gemaakt) == 1


def test_een_deur_item_blijft_open_met_zijn_oordeel():
    """Wat de founder moet zien blijft staan — mét het oordeel erop, zodat de weergave kan
    groeperen zonder de poort (en dus een LLM-call) opnieuw te draaien."""
    nf = _Notif(_items("⤴ beslissing gevraagd: claim 'clean' vereist goedkeuring"))
    r = tp.draai(notif=nf, projects=_Ledger(), records=RECS, targets=[("role", "x")],
                 dry_run=False, gebruik_llm=False)
    assert not nf._i[0].get("archived")
    assert nf._i[0]["poort"]["deur"] == tp.DEUR_BESLUIT
    assert r["blijft_open"] == 1


def test_een_mislukte_aflevering_archiveert_niet(caplog):
    """Nooit stil verliezen: kan het werk niet op het bord, dan blijft het item staan."""
    class _Stuk(_Ledger):
        def create(self, *a, **kw):
            raise RuntimeError("bord stuk")

    nf = _Notif(_items("[rol compliance onbemand] beoordeel claim X"))
    with caplog.at_level("WARNING"):
        r = tp.draai(notif=nf, projects=_Stuk(), records=RECS, targets=[("role", "x")],
                     dry_run=False)
    assert not nf._i[0].get("archived") and r["blijft_open"] == 1
    assert "kon werk niet afleveren" in caplog.text


# ── 7. De opruiming van stap 0 ──────────────────────────────────────────────

def test_opruiming_trekt_alleen_grafstenen_in():
    """Twee guards: alleen van vóór de fix, en alleen als de rol NU aantoonbaar bemand is — dat
    laatste is precies de bewering die de bug verkeerd deed."""
    from nooch_village import notif_opruiming as no

    class _Ass:
        def fillers_of(self, rid, record=None):
            return [{"type": "persona", "id": "p1"}] if rid == "compliance" else []

    oud = no.FIX_TS - 86400
    nieuw = no.FIX_TS + 86400
    items = [
        {"id": "a", "snippet": "[rol compliance onbemand] doe iets", "at": oud},
        {"id": "b", "snippet": "[rol harry_hemp onbemand] doe iets", "at": oud},   # echt onbemand
        {"id": "c", "snippet": "[rol compliance onbemand] doe iets", "at": nieuw}, # regressie
        {"id": "d", "snippet": "gewone melding", "at": oud},
    ]
    gevonden = no.stale_onbemand(_Notif(items), RECS, _Ass())
    assert [n["id"] for n in gevonden] == ["a"]


def test_opruiming_laat_een_regressie_zichtbaar_en_meldt_hem(caplog):
    """Een item van ná de fix met dezelfde tekst is geen grafsteen maar een regressie."""
    from nooch_village import notif_opruiming as no

    class _Ass:
        def fillers_of(self, rid, record=None):
            return [{"type": "persona", "id": "p1"}]

    items = [{"id": "c", "snippet": "[rol compliance onbemand] x", "at": no.FIX_TS + 10}]
    with caplog.at_level("WARNING"):
        assert no.stale_onbemand(_Notif(items), RECS, _Ass()) == []
    assert "regressie" in caplog.text


def test_opruiming_is_idempotent():
    from nooch_village import notif_opruiming as no

    class _Ass:
        def fillers_of(self, rid, record=None):
            return [{"type": "persona", "id": "p1"}]

    nf = _Notif([{"id": "a", "snippet": "[rol compliance onbemand] x", "at": no.FIX_TS - 10}])
    assert no.archiveer_stale_onbemand(nf, RECS, _Ass())["gearchiveerd"] == 1
    assert no.archiveer_stale_onbemand(nf, RECS, _Ass())["gearchiveerd"] == 0
    assert "gefixte bug" in nf._i[0]["outcome"]


def test_het_oordeel_van_de_match_bepaalt_de_skill_deur():
    """De match zegt 'geen rol, maar software zou het kunnen'. Dat IS de skill-deur; dat oordeel
    weggooien en terugvallen op tekstpatronen legde het item op de onbeslist-stapel."""
    antwoord = '{"role": "NONE", "kind": "missing_capability", "capability": "page fetch"}'
    b = tp.poort(_n("Scrape/fetch the live FAQ page content"), projects=_Projects(),
                 records=RECS, reason_fn=_llm(antwoord))
    assert b.deur == tp.DEUR_SKILL


def test_een_uitgevallen_match_leest_anders_dan_onclassificeerbaar():
    """Andere oorzaak, andere fix — ze op één hoop gooien verbergt een storing achter 'onbekend'."""
    b = tp.poort(_n("iets"), projects=_Projects(), records=RECS, reason_fn=_llm(None))
    assert b.deur == tp.ONBESLIST and "niet beschikbaar" in b.reden


# ── 8. Herbeoordelen: het sjabloon en het bewijs-gat ────────────────────────

def test_het_sjabloon_wordt_weggehaald_voor_de_match():
    """"Deze taak vereist een mens of externe partij" domineerde de tekst en duwde elke match naar
    human_external, terwijl het werk eronder gewoon van een rol is."""
    t = ("⏸️ Project van Harry Hemp vastgelopen op 1 mens-/extern item(s): Deze taak vereist een "
         "mens of externe partij: 'Decide whether to permanently exclude this overlap'")
    assert tp.kern(t) == "Decide whether to permanently exclude this overlap"


def test_een_methode_keuze_gaat_naar_de_rol_die_hem_bezit():
    """De harry_hemp/OpenAlex-overlap is een onderzoeksmethode-keuze, geen founder-besluit."""
    antwoord = '{"role": "harry_hemp", "kind": "missing_capability", "capability": ""}'
    b = tp.poort(_n("⏸️ Project van X vastgelopen op 1 mens-/extern item(s): Deze taak vereist een "
                    "mens of externe partij: 'Decide whether to exclude this overlap'"),
                 projects=_Projects(), records=RECS, reason_fn=_llm(antwoord))
    assert b.deur == tp.GEROUTEERD and b.naar_rol == "harry_hemp"


@pytest.mark.parametrize("tekst", [
    "⤴ beslissing gevraagd: De claim mist harde bewijzen voor de nieuwe versie",
    "⤴ beslissing gevraagd: De FAQ-pagina claimt 'clean' zonder definitie of validatie",
    "⤴ beslissing gevraagd: de claim is niet onderbouwd en vraagt aanvullende bewijsvoering",
])
def test_een_claim_zonder_bewijs_is_een_bewijs_gat_geen_besluit(tekst):
    """Het antwoord ligt al bij de bewijslaag: geen onderbouwing = niet claimbaar. De founder
    beslist waar bewijs dubbelzinnig is, niet waar het ontbreekt."""
    b = tp.deur(_n(tekst))
    assert b.deur == tp.BEWIJS_WACHT and b.klasse == "bewijs-wachtspoor"


def test_een_echte_compliance_vraag_blijft_wel_een_besluit():
    """De grens: mét bewijs en een inhoudelijke vraag hoort het wél bij de founder."""
    b = tp.deur(_n("⤴ beslissing gevraagd: is de geherformuleerde claim compliant met EmpCo?"))
    assert b.deur == tp.DEUR_BESLUIT


def test_het_bewijs_wachtspoor_bereikt_de_founder_niet():
    assert tp.BEWIJS_WACHT in tp.STIL


def test_mens_oordeel_zonder_fysieke_handeling_wordt_niet_gevolgd():
    """De router omschrijft human_external als 'kan geen software, er moet een mens de fysieke
    wereld in'. 'Decide whether to exclude this overlap' is een methode-keuze. Zegt de match tóch
    mens, zonder één fysieke handeling in de tekst, dan geloven we dat oordeel niet."""
    antwoord = '{"role": "NONE", "kind": "human_external", "capability": ""}'
    b = tp.poort(_n("Decide whether to permanently exclude this overlap", "p1"),
                 projects=_Projects({"p1": {"status": "blocked", "owner": "harry_hemp",
                                            "park": {"reden": "human"}}}),
                 records=RECS, reason_fn=_llm(antwoord))
    assert b.deur != tp.MENS_WERK
    assert b.naar_rol == "harry_hemp"          # terug naar de eigenaar, niet naar de founder


def test_echt_fysiek_werk_blijft_wel_mens_werk_na_de_check():
    antwoord = '{"role": "NONE", "kind": "human_external", "capability": ""}'
    b = tp.poort(_n("Laat de samples testen in een erkend lab (TÜV)", "p1"),
                 projects=_Projects({"p1": {"status": "blocked", "owner": "harry_hemp",
                                            "park": {"reden": "human"}}}),
                 records=RECS, reason_fn=_llm(antwoord))
    assert b.deur == tp.MENS_WERK


def test_een_vastgelopen_item_blijft_van_de_eigenaar():
    """Een item wordt geen founder-besluit omdat het vastliep. Zonder andere eigenaar en zonder
    fysieke handeling gaat het terug naar wie het project bezit."""
    antwoord = '{"role": "NONE", "kind": "missing_capability", "capability": "iets"}'
    b = tp.poort(_n("iets wat software zou kunnen", "p1"),
                 projects=_Projects({"p1": {"status": "running", "owner": "compliance",
                                            "park": {"reden": "human"}}}),
                 records=RECS, reason_fn=_llm(antwoord))
    assert b.deur == tp.GEROUTEERD and b.naar_rol == "compliance"


# ── 9. De veilige helft: triëren zonder werk te verplaatsen ─────────────────

def test_vasthouden_levert_geen_werk_af_maar_haalt_het_wel_weg():
    """Triage uit de inbox is laag risico; werk naar een ander bord schuiven niet. Zonder
    `lever_af` gebeurt alleen het eerste — met het oordeel op het item, zodat de aflevering later
    alsnog kan."""
    nf = _Notif(_items("[rol compliance onbemand] beoordeel claim X"))
    led = _Ledger()
    r = tp.draai(notif=nf, projects=led, records=RECS, targets=[("role", "x")],
                 dry_run=False, lever_af=False)
    assert led.gemaakt == []                                   # niets naar een ander bord
    assert nf._i[0]["archived"]                                # wel uit de founder-inbox
    assert "vastgehouden" in nf._i[0]["outcome"]
    assert r["vastgehouden"] and r["vastgehouden"][0]["rol"] == "compliance"


def test_met_lever_af_wordt_het_wel_afgeleverd():
    nf = _Notif(_items("[rol compliance onbemand] beoordeel claim X"))
    led = _Ledger()
    tp.draai(notif=nf, projects=led, records=RECS, targets=[("role", "x")],
             dry_run=False, lever_af=True)
    assert led.gemaakt and led.gemaakt[0][0] == "compliance"
