"""Een overdracht is een verzoek, geen dump.

`handoff` zette wel een project op het bord van de andere rol, maar de ontvanger zag alleen "📥
Binnengekomen als projectverzoek. Klaar wanneer: X" — zonder wie het vroeg, vanuit welke
verantwoordelijkheid, wat die rol tegenkwam en wat er precies gevraagd wordt. Dan is de eerste
handeling van elke ontvanger het uitzoeken van iets wat de gever al wist.

De kaart is symmetrisch: van-rol en aan-rol staan er allebei op, met de vraag ertussen.
"""
from __future__ import annotations

from nooch_village.project_items import handoff, verzoekkaart


class _Def:
    def __init__(self, naam):
        self.name = naam
        self.accountabilities = []
        self.purpose = ""
        self.domains = []


class _Rec:
    def __init__(self, rid, naam):
        self.id = rid
        self.definition = _Def(naam)


class _Records:
    def __init__(self, recs):
        self._r = {r.id: r for r in recs}

    def get(self, rid):
        return self._r.get(rid)


RECS = _Records([_Rec("compliance", "Compliance"), _Rec("website_watcher", "Website Watcher")])


class _Ledger:
    def __init__(self):
        self.projects, self.feed = {}, []

    def create(self, owner, scope, trigger, **kw):
        pid = f"p{len(self.projects)}"
        self.projects[pid] = {"id": pid, "owner": owner, "scope": scope, **kw}
        return pid

    def add_feed_entry(self, pid, text, **kw):
        self.feed.append((pid, text, kw))


def test_de_kaart_draagt_de_vier_delen():
    k = verzoekkaart(van_rol="compliance", van_accountability="Checking every public claim",
                     spanning="de FAQ-pagina claimt 'clean' zonder definitie",
                     vraag="zet de herschreven zin op de FAQ-pagina",
                     done="de nieuwe zin staat live")
    assert "Verzoek van compliance" in k
    assert "vanuit accountability: Checking every public claim" in k
    assert "wat zij tegenkwamen: de FAQ-pagina claimt" in k
    assert "wat zij van jou vragen: zet de herschreven zin" in k
    assert "klaar wanneer: de nieuwe zin staat live" in k


def test_de_kaart_gebruikt_de_leesbare_rolnaam():
    led = _Ledger()
    uit = handoff(led, "website_watcher", "zet de zin op de FAQ", records=RECS,
                  van_rol="compliance", van_accountability="Checking every public claim",
                  spanning="claim zonder definitie", vraag="pas de FAQ-tekst aan")
    assert uit["ok"]
    tekst = led.feed[0][1]
    assert "Verzoek van Compliance" in tekst          # naam, niet de rol-id


def test_zonder_afzender_doet_de_kaart_niet_alsof():
    """Ontbreekt de herkomst, dan zegt de kaart 'een rol' — geen verzonnen precisie."""
    k = verzoekkaart(van_rol="", van_accountability="", spanning="", vraag="", done="iets")
    assert "Verzoek van een rol" in k
    assert "vanuit accountability" not in k


def test_de_vraag_valt_terug_op_het_done_criterium():
    """Liever het done-criterium herhalen dan een lege 'wat vragen zij van jou'-regel."""
    k = verzoekkaart(van_rol="compliance", van_accountability="", spanning="iets", vraag="",
                     done="de zin staat live")
    assert "wat zij van jou vragen: de zin staat live" in k


def test_de_overdracht_blijft_werken_zonder_de_nieuwe_velden():
    """Bestaande aanroepers geven ze nog niet mee; die mogen niet breken."""
    led = _Ledger()
    uit = handoff(led, "compliance", "doe iets", records=RECS)
    assert uit["ok"] and led.feed and "Verzoek van een rol" in led.feed[0][1]
