"""Het scherm dat de founder echt opent.

De kaart bestond in de CLI en in een muted regel boven de lijst, maar de WEB-MODAL toonde nog de
rauwe dump: "Project van X vastgelopen op 1 mens-/extern item(s): Deze taak vereist een mens of
externe partij: '…'" met een generieke Ja/Nee eronder. "Klaar in de CLI" is niet "de founder kan
het lezen" — daarom staat de kaart nu in `_spanning_pane`, het paneel dat de modal in een iframe
toont.
"""
from __future__ import annotations

from nooch_village.views.inbox import _kaart_html, _spanning_pane


class _Def:
    def __init__(self, naam, accs=()):
        self.name = naam
        self.accountabilities = list(accs)
        self.purpose = ""
        self.domains = []


class _Rec:
    def __init__(self, rid, naam, accs=()):
        self.id = rid
        self.definition = _Def(naam, accs)
        self.archived = False


class _Records:
    def __init__(self, recs):
        self._r = {r.id: r for r in recs}

    def get(self, rid):
        return self._r.get(rid)

    def all(self):
        return list(self._r.values())


class _Projects:
    def __init__(self, d=None):
        self._p = dict(d or {})

    def get(self, pid):
        return self._p.get(pid)


class _Notif:
    def verwerkingen_of(self, n):
        return []


class _St:
    records = _Records([
        _Rec("compliance", "Compliance",
             ["Verifying sustainability claims against evidence and EmpCo guidelines"]),
        _Rec("mother_earth__nooch__strategic_lead_founder_steward", "Founder",
             ["Guarding mission, values and long-term principles"]),
    ])
    projects = _Projects({"p1": {"owner": "compliance"}})
    notif = _Notif()


VASTGELOPEN = ("⏸️ Project van Harry Hemp vastgelopen op 1 mens-/extern item(s): Deze taak vereist "
               "een mens of externe partij: 'Decide whether to exclude this overlap'")
BESLUIT = ("⤴ beslissing gevraagd: mag de geherformuleerde claim 'compensated' live volgens "
           "EmpCo 2024/825?")


def test_de_modal_toont_de_kaart_niet_de_vastgelopen_preambule():
    n = {"id": "n1", "by": "compliance", "project_id": "p1", "snippet": BESLUIT,
         "poort": {"deur": "deur_besluit", "klasse": "compliance-besluit"}}
    html = _kaart_html(_St(), n)
    assert "Compliance werpt dit op" in html
    assert "vanuit accountability" in html
    assert "Wat ik van jou nodig heb" in html
    assert "vastgelopen" not in html
    assert "vereist een mens of externe partij" not in html


def test_de_sjabloon_verpakking_staat_niet_meer_in_de_spanning():
    """De kern, niet de verpakking — anders leest de founder drie regels boilerplate voor hij bij
    het werk komt."""
    n = {"id": "n2", "by": "compliance", "project_id": "p1", "snippet": VASTGELOPEN,
         "poort": {"deur": "mens_werk", "klasse": ""}}
    html = _kaart_html(_St(), n)
    assert "Decide whether to exclude this overlap" in html
    assert "Project van Harry Hemp vastgelopen" not in html


def test_de_kaart_zit_echt_in_het_paneel_dat_de_modal_toont():
    """`_spanning_pane` is wat de modal in een iframe rendert. Zonder deze test kan de kaart
    bestaan zonder dat de founder hem ooit ziet — precies wat er misging."""
    n = {"id": "n3", "by": "compliance", "project_id": "p1", "snippet": BESLUIT,
         "poort": {"deur": "deur_besluit", "klasse": "compliance-besluit"}}
    html = _spanning_pane(_St(), n)
    assert "Compliance werpt dit op" in html
    assert "Wat ik van jou nodig heb" in html


def test_zonder_kaart_gegevens_valt_het_terug_op_de_tekst():
    """Fail-soft: een leeg scherm is erger dan een lelijke regel."""
    n = {"id": "n4", "by": "", "snippet": "iets zonder herkomst"}
    html = _spanning_pane(_St(), n)
    assert "iets zonder herkomst" in html
