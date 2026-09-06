"""De kop boven een resultaat: herkomst, oordeel, conclusie.

Wat deze tests vastleggen, in volgorde van belang:

1. **Het bewijs blijft staan.** De ruwe velden onder de kop veranderen niet, en als de conclusie
   wegvalt (geen model, exceptie, onzin terug) staat de note er precies zo bij als voorheen. Een
   leeswijzer mag ontbreken, bewijs niet.
2. **Het oordeel is geteld, niet gevraagd.** Een model dat zijn eigen output beoordeelt kijkt zijn
   eigen huiswerk na.
3. **De stem volgt het werk uit de rugzakken**, niet uit een tweede tabel die kan afdrijven.
"""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village import deliverable_kop as dk
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.skills import SkillRegistry

RUGZAKKEN = {
    "buiten": {"stagiair": "Sid", "wat": "x", "skills": ["competitor_news", "epo_patents"]},
    "schrijven": {"stagiair": "Wendy", "wat": "y", "skills": ["content_schrijven"]},
    "basis": {"stagiair": "", "wat": "z", "skills": ["escaleer"]},
}


# ── de stem volgt het werk ───────────────────────────────────────────────────

def test_stagiair_komt_uit_de_rugzak():
    assert dk.stagiair_voor(RUGZAKKEN, "competitor_news") == "Sid"
    assert dk.stagiair_voor(RUGZAKKEN, "content_schrijven") == "Wendy"


def test_geen_stagiair_bij_een_rugzak_zonder_gezicht():
    """`basis` heeft geen stagiair; dan noemen we er ook geen in plaats van er een te kiezen."""
    assert dk.stagiair_voor(RUGZAKKEN, "escaleer") == ""


def test_geen_stagiair_zonder_rugzakken_of_voor_een_los_middel():
    assert dk.stagiair_voor(None, "competitor_news") == ""
    assert dk.stagiair_voor(RUGZAKKEN, "materiaal_shortlist") == ""


# ── het oordeel is geteld ────────────────────────────────────────────────────

def test_tellen_per_archetype():
    assert dk.tel_resultaten({"items": [1, 2, 3]}, ("list", "items")) == 3
    assert dk.tel_resultaten({"items": [1], "total": 47}, ("list", "items")) == 47   # total wint
    assert dk.tel_resultaten({"d": {"a": 1, "b": 2}}, ("dictlist", "d")) == 2
    assert dk.tel_resultaten({"t": "iets"}, ("text", "t")) == 1
    assert dk.tel_resultaten({"t": "   "}, ("text", "t")) == 0


def test_niet_te_tellen_geeft_geen_oordeel():
    assert dk.tel_resultaten({"x": 1}, None) is None
    assert dk.tel_resultaten({"v": 3.4}, ("metric", "v")) is None
    assert dk.oordeel(None) == ""


def test_oordeel_drempels():
    assert dk.oordeel(0) == "nothing"
    assert dk.oordeel(1) == "thin"
    assert dk.oordeel(2) == "thin"
    assert dk.oordeel(3) == "usable"


# ── de kopregel ──────────────────────────────────────────────────────────────

def test_kop_toont_alles_wat_bekend_is():
    r = dk.kop(item_tekst="Find competitor news", skill_label="competitor_news",
               lijst="Execution plan", stagiair="Sid", aantal=4)
    assert r.startswith("📎 Find competitor news — via competitor_news")
    assert "Sid" in r and 'list “Execution plan”' in r and "usable (4)" in r


def test_kop_laat_weg_wat_onbekend_is():
    """Geen lege haakjes, geen 'onbekend': wat we niet weten noemen we niet."""
    r = dk.kop(item_tekst="X", skill_label="site_health")
    assert r == "📎 X — via site_health"


# ── de conclusie is fail-soft ────────────────────────────────────────────────

def test_conclusie_vat_samen():
    zin = dk.conclusie("Find news", "📎 …: 2 results\n• title: A\n• title: B",
                       reason_fn=lambda *a, **k: "Two items found, both older than three months.")
    assert zin == "Two items found, both older than three months."


def test_conclusie_krijgt_alleen_de_gerenderde_note():
    """Het model mag niets zien wat de mens niet ziet — anders kan er een feit in de conclusie
    staan dat nergens in het bewijs eronder terugkomt."""
    gezien = {}
    dk.conclusie("De vraag", "DE NOTE", reason_fn=lambda p, **k: gezien.setdefault("p", p) or "ok")
    assert "DE NOTE" in gezien["p"] and "De vraag" in gezien["p"]
    assert "only what is literally in the result" in gezien["p"]


def test_conclusie_valt_stil_bij_een_exceptie():
    def _stuk(*a, **k):
        raise RuntimeError("geen krediet")
    assert dk.conclusie("v", "note", reason_fn=_stuk) == ""


def test_conclusie_weigert_een_alinea():
    """Een model dat 'max 25 woorden' negeert levert geen conclusie maar een tweede note."""
    assert dk.conclusie("v", "note", reason_fn=lambda *a, **k: "woord " * 200) == ""


def test_conclusie_zonder_note_vraagt_niets():
    assert dk.conclusie("v", "", reason_fn=lambda *a, **k: 1 / 0) == ""


# ── de note zelf ─────────────────────────────────────────────────────────────

def _inwoner(rugzakken=None):
    rec = Record(id="rol_a", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="t", skills=["competitor_news"]), source="seed")
    ctx = SimpleNamespace(settings={"reflect_interval_seconds": "0"},
                          rugzakken=rugzakken if rugzakken is not None else RUGZAKKEN)
    return Inhabitant(rec, EventBus(name="test"), SkillRegistry(), ctx)


def test_note_zonder_conclusie_is_de_oude_note(monkeypatch):
    """DE BELANGRIJKSTE TEST. Valt het model weg, dan mag er niets verdwijnen."""
    monkeypatch.setattr(dk, "conclusie", lambda *a, **k: "")
    inw = _inwoner()
    note = inw._deliverable_note({"text": "Find news", "skill": "competitor_news"},
                                 {"items": [{"title": "A"}, {"title": "B"}, {"title": "C"}]},
                                 ("list", "items"), source="competitor_news", lijst="Execution plan")
    assert note.startswith("📎 Find news — via competitor_news · Sid · list “Execution plan” · usable (3)")
    assert "• title: A" in note and "• title: B" in note
    assert "➜" not in note


def test_note_met_conclusie_zet_hem_onder_de_kop_en_boven_het_bewijs(monkeypatch):
    monkeypatch.setattr(dk, "conclusie", lambda *a, **k: "Three items, none recent.")
    inw = _inwoner()
    note = inw._deliverable_note({"text": "Find news", "skill": "competitor_news"},
                                 {"items": [{"title": "A"}, {"title": "B"}, {"title": "C"}]},
                                 ("list", "items"), source="competitor_news")
    regels = note.splitlines()
    assert regels[0].startswith("📎 Find news")
    assert regels[1] == "➜ Three items, none recent."
    assert regels[2].startswith("• title: A")


def test_note_noemt_de_fallback_bron_en_de_stagiair_van_die_bron(monkeypatch):
    """Bij een skill-ladder-reroute telt de bron die het écht leverde, ook voor de stem."""
    monkeypatch.setattr(dk, "conclusie", lambda *a, **k: "")
    inw = _inwoner()
    note = inw._deliverable_note({"text": "Patents", "skill": "epo_patents"},
                                 {"patents": [{"title": "P"}]}, ("list", "patents"),
                                 source="google_patents")
    assert "google_patents (fallback voor epo_patents)" in note
    assert "Sid" not in note          # google_patents zit in geen rugzak → geen gezicht verzinnen


def test_note_zonder_rugzakken_noemt_geen_stagiair(monkeypatch):
    monkeypatch.setattr(dk, "conclusie", lambda *a, **k: "")
    inw = _inwoner(rugzakken={})
    note = inw._deliverable_note({"text": "X", "skill": "competitor_news"},
                                 {"items": []}, ("list", "items"), source="competitor_news")
    assert note.startswith("📎 X — via competitor_news · nothing (0)")
