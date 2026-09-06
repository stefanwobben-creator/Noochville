"""Tussen 'goedgekeurd' en 'klaar' zit een gat waarin de rol bezig is. Dat gat was onzichtbaar.

Gemeten bij het eerste echte gebruik (6 september 2026): je klikt go-ahead, de kaart herlaadt
onmiddellijk, er staat nog niets — want de bordpuls is nog niet langsgeweest — en daarna beweegt het
scherm niet meer. Je moest zelf gaan verversen om te zien of er iets gebeurd was.

Twee dingen daartegen, en allebei zonder nieuwe opslag:

1. Een DERDE toestand op de balk, afgeleid uit wat er al staat: goedgekeurd én er staan nog items
   open die een skill hebben, dus de rol is aan zet.
2. De kaart die na go-ahead zelf een tijdje blijft kijken, met oplopende tussenpozen die uitdoven.
"""
from __future__ import annotations

from nooch_village.views.checklists import _gate_samenvatting


def _items(*specs):
    """specs: (done, skill) — 'exec' = niet af én met skill."""
    return [{"id": f"i{n}", "text": f"item {n}", "done": d, "skill": s}
            for n, (d, s) in enumerate(specs)]


# ── de afleiding zelf ────────────────────────────────────────────────────────

def test_openstaande_skill_items_tellen_als_werk():
    _, n = _gate_samenvatting(_items((False, "site_health"), (False, "haal_pagina")))
    assert n == 2


def test_afgevinkte_items_tellen_niet_meer():
    _, n = _gate_samenvatting(_items((True, "site_health"), (False, "haal_pagina")))
    assert n == 1


def test_alles_af_is_geen_werk_meer():
    _, n = _gate_samenvatting(_items((True, "site_health"), (True, "haal_pagina")))
    assert n == 0


def test_items_zonder_skill_zijn_geen_rolwerk():
    """Een mens-taak of een item dat niemand kan draaien maakt de rol niet bezig."""
    _, n = _gate_samenvatting(_items((False, None), (False, "")))
    assert n == 0


# ── de drie toestanden in de balk ────────────────────────────────────────────

def _balk(cl_extra, items):
    """Rendert het stukje balk zoals `render_checklists` het opbouwt, zonder de hele view."""
    from nooch_village.views import checklists as V
    wat, n_exec = V._gate_samenvatting(items)
    cl = {"id": "c1", "title": "Execution plan", **cl_extra}
    if cl.get("akkoord") is False:
        return "waiting"
    if cl.get("akkoord_door"):
        return "working" if n_exec else "approved"
    return "geen poort"


def test_voor_akkoord_wacht_hij_op_jou():
    assert _balk({"akkoord": False}, _items((False, "site_health"))) == "waiting"


def test_na_akkoord_met_werk_is_hij_bezig():
    assert _balk({"akkoord_door": "stefan@nooch.earth"},
                 _items((False, "site_health"))) == "working"


def test_na_akkoord_zonder_werk_is_hij_klaar():
    assert _balk({"akkoord_door": "stefan@nooch.earth"},
                 _items((True, "site_health"))) == "approved"


def test_een_handgemaakte_lijst_krijgt_geen_poort():
    """Zonder `akkoord`-veld is de lijst met de hand gemaakt; die heeft nooit gewacht."""
    assert _balk({}, _items((False, "site_health"))) == "geen poort"


# ── de markup en de verversing ───────────────────────────────────────────────

def test_bezig_balk_draagt_een_haakje_voor_de_frontend():
    """`data-bezig` maakt de toestand machine-leesbaar, zodat een latere spinner of een
    aria-live-melding zich eraan kan hangen zonder op de Engelse tekst te matchen."""
    import inspect
    from nooch_village.views import checklists as V
    src = inspect.getsource(V)
    assert "data-bezig='1'" in src
    assert "the role is working" in src


def test_de_kaart_blijft_na_go_ahead_zelf_kijken():
    """Zeven verversingen met oplopende tussenpozen, en ze doven uit.

    Een eeuwige poller is de makkelijke fout hier: de kaart kan uren openstaan. Daarom een eindige
    reeks, en elke tik controleert eerst of de overlay nog open is."""
    import inspect
    from nooch_village.views import projects as P
    src = inspect.getsource(P)
    assert "if(act==='plan_akkoord')" in src
    assert "[2000,5000,9000,15000,30000,60000,120000]" in src
    assert "if(ov.style.display!=='none')reopen()" in src          # niet blijven pollen na sluiten
