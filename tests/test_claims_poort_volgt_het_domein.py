"""De claims-poort leidt zijn rol af uit het domein, niet uit een naam.

Acht dispatch-takken in `cockpit2` riepen los `_role_gate("compliance", …)` aan. Toen die rol naar
een andere cirkel verhuisde en het oude record werd gearchiveerd, hingen die acht poorten aan een
naam die niemand meer draagt. Ze werkten alleen nog doordat `resolve_circle_id` via het
ARCHIEF-record bij de oude cirkel uitkwam waar Stefan Circle Lead is — verdwijnt die cirkel, dan
weigeren ze iedereen, zonder dat iets zegt waarom.

Twee dingen die dit bestand vastlegt en die ik tijdens het bouwen zelf fout had:

- de guest-regel (auth uit = mag alles) blijft ONGEWIJZIGD gelden. Mijn eerste versie weigerde
  vóór `_role_gate` en brak daarmee stil de enige modus waarin het dorp zonder login draait;
- de resolver mag niet klappen op de vorm van `records`. Een exception in de resolver legt de hele
  claims-keten plat, en dat is duurder dan een lege uitkomst die de aanroeper afhandelt.
"""
from __future__ import annotations

import json
from types import SimpleNamespace as NS

from nooch_village import claims_board, claims_db, cockpit2
from nooch_village.projects import ProjectLedger

DOMEIN_ROL = "mother_earth__nooch__compliance"
ANDERE = "mother_earth__nooch__marketing_lead"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def _verhuis_domein(st, naar: str):
    oud = st.records.get(DOMEIN_ROL)
    oud.definition.domains = []
    st.records.put(oud)
    nieuw = st.records.get(naar)
    nieuw.definition.domains = [claims_db.DOMEIN]
    st.records.put(nieuw)


def _vervuller(st, rol: str, mail: str = "curator@nooch.earth") -> str:
    """Een persoon mét e-mail die deze rol vervult. De fixture-mensen hebben geen adres, en
    `_role_gate` herkent een gebruiker op e-mail."""
    p = st.people.by_email(mail) or st.people.add("Curator", mail)
    st.assign.assign(rol, "person", p.id)
    return mail


# ── de poort ─────────────────────────────────────────────────────────────────────────────────

def test_de_vervuller_van_de_domein_houder_mag_cureren(tmp_path):
    st = _st(tmp_path)
    mail = _vervuller(st, DOMEIN_ROL)
    assert cockpit2._claims_gate(cockpit2._Stores(st.dd), mail) is None


def test_de_poort_verhuist_mee_met_het_domein(tmp_path):
    """Het hele punt: geen rol-id in de poort. Dezelfde persoon, dezelfde poort, ander domein-huis."""
    st = _st(tmp_path)
    mail = _vervuller(st, ANDERE)
    st = cockpit2._Stores(st.dd)
    assert cockpit2._claims_gate(st, mail) is not None      # bezit het domein (nog) niet

    _verhuis_domein(st, ANDERE)
    st = cockpit2._Stores(st.dd)
    assert cockpit2._claims_rol(st) == ANDERE
    assert cockpit2._claims_gate(st, mail) is None          # het domein verhuisde, de poort ook


def test_zonder_domein_houder_zegt_de_poort_de_echte_reden(tmp_path):
    """Niet "alleen de rolvervuller of Circle Lead mag dit" — dat stuurt je de verkeerde kant op."""
    st = _st(tmp_path)
    rec = st.records.get(DOMEIN_ROL)
    rec.definition.domains = []
    st.records.put(rec)
    st = cockpit2._Stores(st.dd)
    melding = cockpit2._claims_gate(st, "buitenstaander@nooch.earth")
    assert melding and claims_db.DOMEIN in melding
    assert cockpit2.is_weigering(melding)


def test_gearchiveerde_houder_telt_niet(tmp_path):
    """`records.get()` geeft een archief-record gewoon terug; 'bestaat' is geen poort."""
    st = _st(tmp_path)
    rec = st.records.get(DOMEIN_ROL)
    rec.archived = True
    st.records.put(rec)
    st = cockpit2._Stores(st.dd)
    assert st.records.get(DOMEIN_ROL) is not None            # het record is er nog
    assert cockpit2._claims_rol(st) == ""


def test_guest_mag_alles_ook_zonder_domein_houder(tmp_path):
    """Auth uit = guest = mag alles. Een nieuwe poort mag die regel niet als bijvangst omduwen."""
    st = _st(tmp_path)
    rec = st.records.get(DOMEIN_ROL)
    rec.definition.domains = []
    st.records.put(rec)
    st = cockpit2._Stores(st.dd)
    assert cockpit2._claims_gate(st, "guest") is None
    assert cockpit2._claims_gate_open(st, "guest") is True


def test_knop_en_mutatie_gebruiken_dezelfde_poort(tmp_path):
    st = _st(tmp_path)
    for wie in (_vervuller(st, DOMEIN_ROL), "buitenstaander@nooch.earth", "guest"):
        assert cockpit2._claims_gate_open(st, wie) is (cockpit2._claims_gate(st, wie) is None)


# ── de resolver ──────────────────────────────────────────────────────────────────────────────

def test_resolver_klapt_niet_op_een_vreemde_records_vorm():
    """Een dubbel zonder `all()` mag geen exception geven: onbekend is "", niet 'stuk'."""
    class Raar:
        def get(self, _):
            return None

    assert claims_board.claims_rol(Raar()) == ""
    assert claims_board.claims_rol(None) == ""
    assert claims_board.claims_rol([]) == ""


def test_resolver_leest_zowel_een_store_als_een_lijst():
    eigenaar = NS(id="x", parent="c", archived=False, definition=NS(domains=[claims_db.DOMEIN]))
    assert claims_board.claims_rol([eigenaar]) == "x"
    assert claims_board.claims_rol(NS(all=lambda: [eigenaar])) == "x"


# ── het bord ─────────────────────────────────────────────────────────────────────────────────

def test_bord_meldt_wat_het_oversloeg_zonder_eigenaar(tmp_path):
    """Overslaan mag; stil overslaan niet."""
    dd = tmp_path / "leeg"
    dd.mkdir()
    bev = {"gevonden": ["volstrekt gifvrij"], "term": "gifvrij", "stoplicht": "red",
           "categorie": "Generiek", "alternatief": "iets concreets", "pagina": "home",
           "url": "https://nooch.earth/"}
    st = cockpit2._Stores(str(dd))
    verslag = claims_board.zet_op_bord(st, claims_db.load(), [bev], "bron", lambda _c: "compliance")
    assert verslag["aangemaakt"] == []
    assert verslag["zonder_eigenaar"], "de uitkomst moet zeggen wat er is overgeslagen"
    assert ProjectLedger(str(dd / "projects.json")).all() == []


def test_bord_belegt_het_werk_bij_de_domein_houder(tmp_path):
    st = _st(tmp_path)
    payload = json.dumps({"bevindingen": [
        {"gevonden": ["volstrekt gifvrij"], "term": "gifvrij", "stoplicht": "red",
         "categorie": "Generiek", "alternatief": "iets concreets", "pagina": "home"}]})
    cockpit2.dispatch(st.dd, "claims_to_board",
                      {"bevindingen": [payload], "bron": ["https://nooch.earth/"],
                       "next": ["/claims"]}, "guest")
    taken = ProjectLedger(str(st.dd + "/projects.json")).all()
    assert taken and all(t["owner"] == DOMEIN_ROL for t in taken)
