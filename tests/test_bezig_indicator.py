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


def _projects_src():
    import inspect
    from nooch_village.views import projects as P
    return inspect.getsource(P)


def test_de_kaart_kijkt_naar_het_WERK_en_niet_naar_de_klok():
    """DE KERNTEST, en een gerepareerde fout.

    Hier stond eerst [2000,5000,9000,15000,30000,60000,120000]: zeven vaste momenten die na twee
    minuten uitdoofden. Gemeten op 6 september bij het eerste echte gebruik: een plan met
    site_health + haal_pagina + plausible_stats duurt lánger dan twee minuten. De kaart viel dus
    halverwege stil en je moest alsnog zelf verversen — precies de klacht die #466 had moeten
    oplossen. Een timer weet niet of het werk klaar is; de bezig-vlag wel."""
    src = _projects_src()
    assert "if(act==='plan_akkoord'){volgStart();}" in src
    assert "[2000,5000,9000,15000,30000,60000,120000]" not in src, "de klok-versie is terug"
    assert "function volgActief(){return !!bd.querySelector('[data-bezig]');}" in src


def test_de_poller_heeft_drie_stopgronden():
    """Een poller die blijft draaien is erger dan geen poller: de kaart kan uren openstaan.

    Drie uitgangen, en ze dekken verschillende dingen. Overlay dicht = je kijkt niet meer. Vlag weg
    = het werk is klaar. Bovengrens = er hangt iets, en blijven pollen repareert dat niet."""
    src = _projects_src()
    assert "if(ov.style.display==='none'||Date.now()>volgTot){volgStop();return;}" in src
    assert "else{volgStop();}" in src                              # vlag weg → klaar
    assert "Date.now()+900000" in src                              # harde bovengrens: 15 minuten


def test_de_aanloop_is_apart_geregeld():
    """Direct na 'go ahead' staat de bezig-vlag er nog NIET: de bordpuls moet het project eerst
    oppakken. Zou de poller meteen op de vlag beslissen, dan stopt hij bij de eerste tik en heb je
    weer niets. Daarom de eerste 30 seconden onvoorwaardelijk."""
    src = _projects_src()
    assert "Date.now()-volgStartTs<30000" in src


def test_ook_bij_het_OPENEN_van_een_draaiende_kaart():
    """Anders werkt het volgen alleen in het tabblad waarin je zelf op 'go ahead' klikte. Sluit je
    de kaart en kom je terug, dan sta je weer naar een stilstaand beeld te kijken."""
    src = _projects_src()
    assert "if(volgActief())volgStart();" in src


def test_geen_twee_pollers_tegelijk():
    """`wire()` draait na élke reopen, en reopen wordt dóór de poller aangeroepen. Zonder rem start
    elke tik een tweede ketting en verdubbelt het aantal fetches per ronde.

    DE REM STAAT OP EEN VLAG EN NIET OP HET TIMER-HANDLE, en dat is het hele punt van deze test. Een
    tik zet zijn eigen handle op null vóórdat hij reopen() aanroept; stond de rem daarop, dan is hij
    op precies dat moment leeg en laat hij de tweede ketting er gewoon langs. Die versie stond hier
    even in en deze test kwam er groen doorheen — vandaar dat hij nu de vlag noemt."""
    src = _projects_src()
    assert "function volgStart(){if(volgAan)return;volgAan=true;" in src
    assert "function volgStop(){volgAan=false;" in src
    assert "function volgStart(){if(volgT)return;" not in src
