"""Een keuzelijst waarin drie regels identiek zijn, is geen keuze.

GEMETEN OP PROD, 29 aug 2026: vier rolnamen komen meer dan één keer voor, samen elf exemplaren —
'Circle Lead' 3x, 'Secretary' 3x, 'Facilitator' 3x, 'Circle Rep' 2x. In een dropdown staan die als
identieke regels onder elkaar; je kunt alleen gokken welke je pakt.

Drie schermen tonen dezelfde lijst en hadden het alle drie: de inbox ("From which role?"), de
projectwizard en de vangst-balk van het werkoverleg. Eén helper, drie aanroepers — geen drie
varianten die na één wijziging uit de pas lopen.
"""
from __future__ import annotations

from types import SimpleNamespace as N

from nooch_village.cockpit2_util import _rol_labels


def _rec(rid, naam, parent=""):
    return N(id=rid, parent=parent, definition=N(name=naam), archived=False, slaapt=False)


ORG = [_rec("c_nooch", "Nooch"), _rec("c_village", "Noochville"),
       _rec("lead_n", "Circle Lead", "c_nooch"),
       _rec("lead_v", "Circle Lead", "c_village"),
       _rec("sci", "Scientist", "c_nooch")]


def test_een_dubbele_naam_krijgt_zijn_cirkel():
    labels = _rol_labels([r for r in ORG if not r.id.startswith("c_")], ORG)
    assert labels["lead_n"] == "Circle Lead (Nooch)"
    assert labels["lead_v"] == "Circle Lead (Noochville)"


def test_een_unieke_naam_houdt_zijn_kale_label():
    """Geen ruis waar niets te verwarren valt."""
    labels = _rol_labels([r for r in ORG if not r.id.startswith("c_")], ORG)
    assert labels["sci"] == "Scientist"


def test_er_wordt_geteld_in_DEZE_lijst_niet_in_de_hele_organisatie():
    """Staat er maar één Circle Lead op het scherm, dan is 'Circle Lead' precies goed — ook al
    bestaan er elders nog twee."""
    labels = _rol_labels([ORG[2], ORG[4]], ORG)
    assert labels["lead_n"] == "Circle Lead"


def test_de_regel_is_generiek_niet_op_circle_lead_gebouwd():
    """Secretary, Facilitator en Circle Rep botsen op prod net zo goed; een lijst met vier
    uitzonderingen mist de vijfde."""
    org = ORG + [_rec("sec_n", "Secretary", "c_nooch"), _rec("sec_v", "Secretary", "c_village"),
                 _rec("fac_n", "Facilitator", "c_nooch"), _rec("fac_v", "Facilitator", "c_village")]
    labels = _rol_labels([r for r in org if not r.id.startswith("c_")], org)
    assert labels["sec_n"] == "Secretary (Nooch)" and labels["fac_v"] == "Facilitator (Noochville)"
    assert labels["sci"] == "Scientist"


def test_blijft_het_dubbel_dan_wint_eerlijkheid_van_netheid():
    """Twee rollen met dezelfde naam in dezelfde cirkel: dan doet de cirkel het werk niet, en zou
    een lijst beloven te onderscheiden zonder het te doen. Dat is erger dan een lelijk label — dan
    dénk je dat je kiest."""
    org = [_rec("c", "Nooch"), _rec("a", "Lead", "c"), _rec("b", "Lead", "c")]
    labels = _rol_labels(org[1:], org)
    assert labels["a"] != labels["b"]
    assert "[a]" in labels["a"] and "[b]" in labels["b"]


def test_zonder_ouder_geen_verzonnen_cirkel():
    """Fail-soft: een rol zonder parent krijgt geen bedachte cirkelnaam erachter."""
    org = [_rec("a", "Lead"), _rec("b", "Lead", "c_nooch"), _rec("c_nooch", "Nooch")]
    labels = _rol_labels(org[:2], org)
    assert labels["a"] == "Lead" and labels["b"] == "Lead (Nooch)"


def test_een_lege_lijst_valt_niet_om():
    assert _rol_labels([], []) == {}


# ── De drie schermen delen de helper ────────────────────────────────────────

def _st(org):
    return N(records=N(all=lambda: org, get=lambda i: next((r for r in org if r.id == i), None)),
             projects=N(all=lambda: []))


def test_de_inbox_dropdown_toont_de_cirkel():
    from nooch_village.views.inbox import _person_role_options
    html = _person_role_options(_st(ORG), [("role", "lead_n"), ("role", "lead_v"), ("role", "sci")])
    assert "Circle Lead (Nooch)" in html and "Circle Lead (Noochville)" in html
    assert ">Scientist<" in html                       # uniek → kaal
    assert html.count(">Circle Lead<") == 0            # geen enkele kale dubbelganger meer


def test_alle_drie_de_rolkiezers_gebruiken_dezelfde_helper():
    """ÉÉN MECHANIEK PER DING. Drie schermen tonen dezelfde lijst; drie eigen varianten lopen na de
    eerste wijziging uit de pas, en dan is het scherm waar niemand keek weer onkiesbaar."""
    import inspect

    from nooch_village.views import inbox, vangst, wizard
    for mod, fn in ((inbox, "_person_role_options"), (wizard, "_role_options"),
                    (vangst, "_rol_opties")):
        bron = inspect.getsource(getattr(mod, fn))
        assert "_rol_labels(" in bron, f"{mod.__name__}.{fn} disambigueert niet"
