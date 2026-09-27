"""De projectkeuze op /acties staat gegroepeerd per eigenaar (27 september 2026).

HET PROBLEEM WAS NIET DE FILTER. Die klopt: van 168 projecten blijven er 46 over (leesbaar +
lopend + onder je eigen rollen). Maar gemeten op productie hangen 35 van die 46 aan ÉÉN rol —
Strategic Lead & Founder Steward. Een platte lijst van 46 waarvan 35 uit dezelfde hoek komen
leest als "alles", ook al is er scherp gefilterd.

`<optgroup>` maakt van één brij vier stapels. Native HTML, geen JavaScript — en dat is hier geen
toevalligheid maar de architectuur van dit scherm: typen + Enter werkt omdat de browser het zelf
doet. Een zoek-dropdown zou het eerste script introduceren; dit kost er nul.

GEMETEN OP PROD, met Stefans eigen rollen:

     3  Financial Controller
     4  Nooch — eigen initiatief
    35  Strategic Lead & Founder Steward
     4  Website Developer
"""
from __future__ import annotations

import re

from nooch_village import cockpit2
from nooch_village.views.acties import _projectopties, render_acties

ROL = "mother_earth__nooch__compliance"
ANDERE = "mother_earth__nooch__creator_of_shoes"
CIRKEL = "mother_earth__nooch"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    for rol in (ROL, ANDERE):
        for f in list(st.assign.fillers_of(rol, st.records.get(rol))):
            st.assign.unassign(rol, f.type, f.id)
    a = st.people.add("Aap Een", "aap@test.nl")
    st.assign.assign(ROL, "person", a.id)
    return dd, st, a


def _groepen(html: str) -> dict:
    """{groepskop: [optietekst, ...]}, in de volgorde van de select."""
    uit = {}
    for m in re.finditer(r"<optgroup label='([^']*)'>(.*?)</optgroup>", html, re.S):
        uit[m.group(1)] = re.findall(r"<option[^>]*>([^<]+)</option>", m.group(2))
    return uit


# ══ De groepering ════════════════════════════════════════════════════════════
def test_de_lijst_is_gegroepeerd_per_eigenaar(tmp_path):
    dd, st, a = _dorp(tmp_path)
    st.assign.assign(ANDERE, "person", a.id)
    st.projects.create(ROL, "Van compliance mycelium", "human", status="running")
    st.projects.create(ANDERE, "Van de schoenmaker", "human", status="running")
    g = _groepen(_projectopties(st, a.id, ""))
    assert len(g) == 2, g
    plat = {p for rij in g.values() for p in rij}
    assert "Van compliance mycelium" in plat and "Van de schoenmaker" in plat
    for kop, rij in g.items():
        assert len(rij) == 1, (kop, rij)


def test_de_kop_is_de_naam_van_de_rol_niet_het_id(tmp_path):
    dd, st, a = _dorp(tmp_path)
    st.projects.create(ROL, "Iets mycelium", "human", status="running")
    koppen = list(_groepen(_projectopties(st, a.id, "")))
    assert koppen == ["Compliance"], koppen


def test_een_eigen_initiatief_krijgt_een_leesbare_kop(tmp_path):
    """`ii:<cirkel>` heeft geen eigen record; hij hoort bij de cirkel uit zijn prefix."""
    dd, st, a = _dorp(tmp_path)
    from nooch_village.cockpit2 import _II_PREFIX
    st.projects.create(f"{_II_PREFIX}{CIRKEL}", "Mijn eigen ding", "human", status="running")
    koppen = list(_groepen(_projectopties(st, a.id, "")))
    assert koppen and "eigen initiatief" in koppen[0], koppen
    assert _II_PREFIX not in koppen[0], "het kale id staat in de kop"


def test_de_groepen_staan_op_alfabet(tmp_path):
    dd, st, a = _dorp(tmp_path)
    st.assign.assign(ANDERE, "person", a.id)
    st.projects.create(ROL, "A", "human", status="running")
    st.projects.create(ANDERE, "B", "human", status="running")
    koppen = list(_groepen(_projectopties(st, a.id, "")))
    assert koppen == sorted(koppen, key=str.lower), koppen


def test_binnen_een_groep_ook(tmp_path):
    dd, st, a = _dorp(tmp_path)
    for naam in ("Zebra mycelium", "Appel mycelium", "Midden mycelium"):
        st.projects.create(ROL, naam, "human", status="running")
    rij = list(_groepen(_projectopties(st, a.id, "")).values())[0]
    assert rij == sorted(rij, key=str.lower), rij


# ══ Wat niet verandert ═══════════════════════════════════════════════════════
def test_geen_project_staat_buiten_alle_groepen(tmp_path):
    """"De 'geen project…' optie blijft buiten alle groepen, bovenaan zoals nu." """
    dd, st, a = _dorp(tmp_path)
    st.projects.create(ROL, "Iets mycelium", "human", status="running")
    h = _projectopties(st, a.id, "")
    assert h.index("no project") < h.index("<optgroup"), "hij is in een groep beland"
    assert "no project" not in "".join(v for rij in _groepen(h).values() for v in rij)


def test_de_huidige_selectie_blijft_altijd_inbegrepen(tmp_path):
    """BESTAAND GEDRAG. Anders wist een select die je opent om te ONTkoppelen stilzwijgend de
    koppeling die er stond — de browser stuurt immers de geselecteerde optie mee."""
    dd, st, a = _dorp(tmp_path)
    pid = st.projects.create(ANDERE, "Niet van mijn rol", "human", status="running")
    h = _projectopties(st, a.id, pid)
    plat = [v for rij in _groepen(h).values() for v in rij]
    assert "Niet van mijn rol" in plat
    assert "selected" in h
    # En hij staat in de groep van ZIJN eigenaar, niet losjes erbuiten.
    assert any("Niet van mijn rol" in rij for rij in _groepen(h).values())


def test_de_filter_zelf_is_niet_aangeraakt(tmp_path):
    """Lopend + eigen rollen + leesbaar; alleen de presentatie verandert."""
    dd, st, a = _dorp(tmp_path)
    st.projects.create(ROL, "Loopt mycelium", "human", status="running")
    st.projects.create(ROL, "Toekomst mycelium", "human", status="future")
    st.projects.create(ANDERE, "Andermans mycelium", "human", status="running")
    plat = [v for rij in _groepen(_projectopties(st, a.id, "")).values() for v in rij]
    assert plat == ["Loopt mycelium"], plat


def test_een_lege_lijst_geeft_geen_lege_groep(tmp_path):
    dd, st, a = _dorp(tmp_path)
    h = _projectopties(st, a.id, "")
    assert "<optgroup" not in h
    assert "no project" in h


def test_het_blijft_zonder_javascript(tmp_path):
    """`<optgroup>` is native HTML. Zou hier een script voor nodig zijn, dan is dit scherm zijn
    belangrijkste eigenschap kwijt."""
    dd, st, a = _dorp(tmp_path)
    st.projects.create(ROL, "Iets mycelium", "human", status="running")
    it = st.acties.add(a.id, "Een actie")
    h = render_acties(st, ik=a.id, csrf_token="t")
    kern = h[h.index("<div class='card'"):]
    assert "<optgroup" in kern
    assert "addEventListener" not in kern and "data-qadd" not in kern
    assert it
