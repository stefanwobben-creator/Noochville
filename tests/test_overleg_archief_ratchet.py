"""Een overleg-archief is duurzaam — of het bestaat niet.

Gemeten op prod, 28 augustus 2026: negen punten met negen uitkomsten (tekst, persoon, Kroniek-id)
verdwenen zodra er een volgend overleg werd geopend. `open()` bouwde een verse state met
`agenda: list(backlog)`, en `close()` archiveerde alleen tellingen — dus het archiefrecord van dat
overleg stond op `behandeld 0, acties 0` terwijl er acht acties waren afgesproken. De notulen waren
weg; alleen de Kroniek en de aangemaakte projecten bewezen nog dat het overleg had plaatsgevonden.

De reparatie is één regel data, maar de bug is stil: er is geen foutmelding, en je merkt het pas als
je maanden later een verslag zoekt. Daarom staat hij hier vast, zoals de fragment-ratchet en de
routing-ratchet dat voor hun klasse doen.

  1. `close()` archiveert de PUNTEN, niet alleen de tellingen;
  2. een tweede overleg openen vernietigt het archiefrecord van het eerste niet — ook niet als dat
     eerste overleg nooit netjes is afgesloten;
  3. de tellingen in het archief kloppen met wat er in de punten staat.
"""
from __future__ import annotations

import os
import tempfile

from nooch_village.werkoverleg import WerkoverlegStore

C = "cirkel"


def _store(tmp_path):
    return WerkoverlegStore(str(tmp_path / "werkoverleg.json"))


def _overleg_met_werk(W, titel="Klacht", tekst="reply to complaint", persoon="p-lotte"):
    """Een overleg met één punt en één uitkomst, zoals de live-verwerking het wegschrijft."""
    W.open(C)
    iid = W.agenda_add(C, titel, by="Stefan")["id"]
    W.punt_uitkomst_add(C, iid, {"type": "actie", "rol": "", "tekst": tekst, "ref": "in de inbox",
                                 "door": "p-stefan", "persoon": persoon, "kroniek": "kr-123",
                                 "prive": False})
    W.punt_afvinken(C, iid, True)
    return iid


# ── 1. close() bewaart de punten ────────────────────────────────────────────

def test_close_archiveert_de_punten_met_hun_herkomst(tmp_path):
    W = _store(tmp_path)
    _overleg_met_werk(W)
    W.close(C)
    rec = W.log(C)[-1]
    assert rec["behandeld"] == 1 and rec["acties"] == 1
    punten = rec.get("punten")
    assert punten, "het archiefrecord draagt geen punten — dan is het verslag een rij getallen"
    u = punten[0]["uitkomsten"][0]
    assert u["tekst"] == "reply to complaint"
    assert u["persoon"] == "p-lotte"
    assert u["kroniek"] == "kr-123", "zonder Kroniek-id is de herkomst na afloop niet te vinden"


def test_het_archief_is_een_kopie_en_beweegt_niet_mee(tmp_path):
    """Zou het archief naar de levende punten wijzen, dan verandert het verslag van een gesloten
    overleg alsnog mee — en dan is 'archief' een woord zonder inhoud."""
    W = _store(tmp_path)
    iid = _overleg_met_werk(W)
    W.close(C)
    W._m[C]["agenda"][0]["title"] = "ACHTERAF GEWIJZIGD"
    W._m[C]["agenda"][0]["uitkomsten"][0]["tekst"] = "ACHTERAF GEWIJZIGD"
    rec = W.log(C)[-1]
    assert rec["punten"][0]["title"] != "ACHTERAF GEWIJZIGD"
    assert rec["punten"][0]["uitkomsten"][0]["tekst"] == "reply to complaint"


# ── 2. een tweede overleg vernietigt het eerste niet ────────────────────────

def test_een_tweede_overleg_laat_het_archief_van_het_eerste_staan(tmp_path):
    W = _store(tmp_path)
    _overleg_met_werk(W)
    W.close(C)
    W.open(C)                                          # dit wiste vroeger alles
    W.close(C)
    eerste = W.log(C)[0]
    assert eerste["acties"] == 1
    assert eerste["punten"][0]["uitkomsten"][0]["tekst"] == "reply to complaint"


def test_een_overleg_dat_nooit_werd_afgesloten_wordt_gered(tmp_path):
    """Juist een overleg dat niet netjes dichtging heeft geen archiefrecord — en dat is precies
    het geval waarin openen alles wist. Redden gaat vóór openen."""
    W = _store(tmp_path)
    _overleg_met_werk(W, tekst="check 39 for mariska")
    W._m[C]["status"] = "closed"                       # afgesloten buiten close() om
    W._save()
    assert W.log(C) == []
    W.open(C)
    rec = W.log(C)[-1]
    assert rec["punten"][0]["uitkomsten"][0]["tekst"] == "check 39 for mariska"
    assert rec["acties"] == 1
    assert rec.get("hersteld_bij_openen") is True, "een gered record hoort zichtbaar gered te zijn"


def test_een_oud_record_zonder_punten_wordt_aangevuld_en_herteld(tmp_path):
    """Records van vóór deze fix dragen tellingen die nul kunnen zijn omdat de status niet gezet
    werd. Aanvullen zonder hertellen zou een liegend 0/0-record laten staan."""
    W = _store(tmp_path)
    _overleg_met_werk(W, tekst="send message about Portugal")
    st = W._m[C]
    st["status"] = "closed"
    st["ended_at"] = 1_780_000_000.0
    st.setdefault("log", []).append({"at": st["ended_at"], "started_at": st["started_at"],
                                     "behandeld": 0, "acties": 0, "projecten": 0, "info": 0,
                                     "roloverleg": 0, "checkout": {}})   # zoals het archief het droeg
    W._save()
    W.open(C)
    rec = W.log(C)[-1]
    assert len(W.log(C)) == 1, "het record hoort AANGEVULD, niet gedupliceerd"
    assert rec["acties"] == 1 and rec["behandeld"] == 1     # herteld, niet het oude nul
    assert rec["punten"][0]["uitkomsten"][0]["tekst"] == "send message about Portugal"
    assert rec.get("hersteld_bij_openen") is True


def test_redden_is_idempotent(tmp_path):
    W = _store(tmp_path)
    _overleg_met_werk(W)
    W.close(C)
    voor = len(W.log(C))
    W.open(C)
    W.close(C)
    W.open(C)
    assert len([e for e in W.log(C) if e.get("punten")]) >= 1
    # twee KEER gesloten = twee records; het derde open() heeft een lege agenda en redt dus niets.
    assert len(W.log(C)) == voor + 1, "elk overleg één record, geen dubbele reddingen"


# ── 3. de code-poort ────────────────────────────────────────────────────────

def test_open_gooit_nooit_een_niet_lege_agenda_weg():
    """De directe poort op de regel die het deed. `open()` mag geen state bouwen waarin de punten
    van het vorige overleg nergens meer staan."""
    import inspect

    bron = inspect.getsource(WerkoverlegStore.open)
    assert "_red_punten" in bron, (
        "open() redt de punten van het vorige overleg niet meer — een nieuw overleg wist dan het "
        "verslag van het vorige")
    snap = inspect.getsource(WerkoverlegStore.close)
    assert "_snapshot" in snap, "close() schrijft geen volledig archiefrecord meer"
