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


def test_een_verse_spanning_spreekt_zichzelf_niet_tegen():
    """Gezien op het echte scherm: "Wat ik van jou nodig heb: … dat mag alleen jij" mét daaronder
    "⚠ raakt geen founder-bevoegdheid". Een verse spanning is nog niet door de poort, dus had hij
    geen klasse en vond de kaart geen founder-accountability. Het domein komt nu uit de tekst."""
    n = {"id": "vers", "by": "compliance", "project_id": "p1", "snippet": BESLUIT}   # géén poort
    html = _kaart_html(_St(), n)
    assert "Wat ik van jou nodig heb" in html
    assert "raakt geen founder-bevoegdheid" not in html


# ── Eén kop, per type een ander lijf ────────────────────────────────────────

def test_een_founder_besluit_toont_de_besluit_actie():
    n = {"id": "f", "by": "compliance", "project_id": "p1", "snippet": BESLUIT,
         "poort": {"deur": "deur_besluit", "klasse": "compliance-besluit"}}
    html = _kaart_html(_St(), n)
    assert "Besluit voor jou" in html and "Bevestig, pas aan, of verwerp" in html


def test_een_operationeel_verzoek_toont_de_accepteer_actie():
    n = {"id": "o", "by": "compliance", "project_id": "p1", "snippet": "doe dit even",
         "poort": {"deur": "gerouteerd", "klasse": ""}}
    html = _kaart_html(_St(), n)
    assert "Operationeel verzoek" in html
    assert "Accepteer" in html and "verschijnt het als project op je bord" in html


def test_de_herschreven_bevinding_is_de_hoofdtekst():
    """De ruwe signalering blijft als herkomst, niet als wat je leest."""
    n = {"id": "b", "by": "compliance", "project_id": "p1", "snippet": BESLUIT,
         "poort": {"deur": "deur_besluit", "klasse": "compliance-besluit"},
         "bevinding": {"ok": True,
                       "spanning": "Op de veelgestelde-vragenpagina staat dat onze schoenen schoon "
                                   "zijn, zonder dat ergens staat wat we daarmee bedoelen.",
                       "voorstel": "De zin vervangen door wat we kunnen aantonen."}}
    html = _kaart_html(_St(), n)
    assert "zonder dat ergens staat wat we daarmee bedoelen" in html
    assert "Voorstel:" in html
    assert "ruwe signalering" in html          # wel bewaard, weggevouwen


def test_een_afgekeurde_bevinding_zegt_dat_hij_herschreven_moet():
    """Liever zichtbaar onaf dan een lege kaart."""
    n = {"id": "x", "by": "compliance", "project_id": "p1", "snippet": BESLUIT,
         "poort": {"deur": "deur_besluit", "klasse": "compliance-besluit"},
         "bevinding": {"ok": False, "reden": "geen concreet voorstel"}}
    html = _kaart_html(_St(), n)
    assert "moet herschreven" in html and "geen concreet voorstel" in html


def test_een_governance_spanning_krijgt_ook_een_type_en_een_lijf():
    """Op het echte scherm had de governance-kaart geen chip en geen actie-uitleg: de poort kent
    geen governance-deur, dus viel het type terug op leeg."""
    n = {"id": "g", "by": "compliance", "project_id": "p1",
         "snippet": "Dit komt wekelijks terug: geen enkele rol heeft een accountability voor het "
                    "bewaken van de onderzoeksmethode."}
    html = _kaart_html(_St(), n)
    assert "Governance-voorstel" in html
    assert "schaadt of ons achteruit zet" in html


# ── De drie knoppen op een operationeel verzoek ─────────────────────────────

def test_een_operationeel_verzoek_krijgt_de_drie_uitkomsten():
    """DE KNOPPENRIJ IS WEG, en dit is de test die hem bewaakte. Accepteren / aanpassen / weigeren
    was "in één handeling" bedoeld, maar de meting over de hele prod-historie zei: 0 weigeringen,
    0 herformuleringen, 3 accepteringen — die alle drie een project werden.

    Een verzoek is gewoon een spanning: hoort het bij je rol dan BORG je het (project), hoort het er
    niet bij dan DEEL je het door (actie). "Nee" laat een vraag nergens landen."""
    from nooch_village.views.inbox import _wizard_pane
    n = {"id": "o", "by": "compliance", "project_id": "p1", "snippet": "zet die zin op de pagina",
         "poort": {"deur": "gerouteerd", "klasse": ""}}
    html = _wizard_pane(_St(), n, "csrf-token", "", "")
    assert "verzoek_besluit" not in html
    for weg in ("Accepteren", "Formulering aanpassen", "Weigeren"):
        assert weg not in html, weg
    assert "notif_klaar" in html                      # sluiten blijft de uitgang


def test_een_pagina_voorstel_houdt_de_drie_knoppen():
    """Ander geval, geen uitzondering: bij een pagina-voorstel IS accepteren de handeling zelf."""
    from nooch_village.views.inbox import _wizard_pane
    n = {"id": "o", "by": "compliance", "project_id": "p1", "type": "naar_rol",
         "snippet": "zet die zin op de pagina",
         "pagina": {"aid": "NOTE-1", "body": "nieuwe tekst", "van_id": "p1"}}
    html = _wizard_pane(_St(), n, "csrf-token", "", "")
    assert "verzoek_besluit" in html and "new version" in html


def test_een_founder_besluit_houdt_zijn_eigen_wizard():
    """De drie knoppen zijn voor verzoeken; een besluit heeft zijn eigen vorm."""
    from nooch_village.views.inbox import _wizard_pane
    n = {"id": "f", "by": "compliance", "project_id": "p1", "snippet": BESLUIT,
         "poort": {"deur": "deur_besluit", "klasse": "compliance-besluit"}}
    html = _wizard_pane(_St(), n, "csrf-token", "", "")
    assert "verzoek_besluit" not in html


def test_het_type_van_de_haak_bepaalt_ook_de_knoppen():
    """Gezien op het echte scherm: een verse spanning toonde wél de kaart maar niet de knoppen. De
    linkerkant las het type van de haak, de rechterkant alleen het poort-oordeel dat er nog niet
    was."""
    from nooch_village.views.inbox import _wizard_pane
    n = {"id": "v", "by": "compliance", "project_id": "", "type": "naar_rol",
         "snippet": "pas de zin op de productpagina aan"}
    # De KAART leest het type nog steeds uit de haak; de knoppen zijn sinds de sloop-pass de drie
    # gewone uitkomsten, dus daar valt niets meer uit de pas te lopen.
    assert "notif_klaar" in _wizard_pane(_St(), n, "csrf", "", "")
    assert "Operationeel verzoek" in _kaart_html(_St(), n)
