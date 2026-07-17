"""Kennisbank fase 2 (intake) en fase 3 (het spel) — alles met een fake reason_fn,
geen netwerk. De principes die hier vastliggen: intake blijft dom (geen trust van de
LLM), idempotent op hash(content+bron) — zelfde claim uit een ándere bron blijft een
aparte stem — en het spel munt via de bestaande fase-1 functies (versie-bump, history)."""
from __future__ import annotations

import json

import pytest

from nooch_village.kennisbank import KennisbankStore
from nooch_village.kennisbank_intake import (build_intake_prompt, parse_intake,
                                             stable_id, intake, SUBJECTS)
from nooch_village.kennisbank_spel import (SpelStore, clusters, gather, ongebonden,
                                           spel_beurt, spel_finish, subject_van)
from nooch_village.notes_store import NotesStore


# ── fase 2: intake ───────────────────────────────────────────────────────────

_LLM_ATOMS = [
    {"content": "Leer en wol zouden veeteelt winstgevend maken (betwist).",
     "subject": "leer", "provenance": "advocacy", "source": "Patched-column",
     "flags": [], "link_hints": ["ethiek"]},
    {"content": "PETA (Camilli): wolschapen gaan na jaren alsnog naar de slacht.",
     "subject": "wol", "provenance": "advocacy", "source": "Patched-column, quote PETA",
     "flags": ["quote"], "link_hints": []},
    {"content": "Eén studie: 90% van looierij-arbeiders sterft voor hun 50e.",
     "subject": "ethiek", "provenance": "media", "source": "Patched-column, 'one study'",
     "flags": ["verificatie_vereist"], "link_hints": []},
    {"content": "Iets zonder herkenbaar onderwerp.", "subject": "iets-nieuws",
     "provenance": "gevoel", "source": "x", "flags": ["raar"], "link_hints": []},
]


def _fake_reason(prompt, **kw):
    return json.dumps(_LLM_ATOMS)


@pytest.mark.smoke
def test_intake_idempotent_en_dom(tmp_path):
    dd = str(tmp_path)
    nieuw, dubbel = intake("ruwe column", "Patched", dd, reason_fn=_fake_reason)
    assert len(nieuw) == 4 and dubbel == 0
    # re-run: NIETS dubbel, en de LLM wordt niet eens meer geraakt (input-ledger) —
    # dit vangt ook LLM-non-determinisme af (zelfde input, nét andere splitsing)
    def _boem(*a, **k):
        raise AssertionError("LLM mag bij identieke input niet opnieuw draaien")
    nieuw2, dubbel2 = intake("ruwe column", "Patched", dd, reason_fn=_boem)
    assert nieuw2 == [] and dubbel2 == 4

    notes = NotesStore(f"{dd}/notes.json")
    kaarten = {n.id: n for n in notes.all()}
    assert len(kaarten) == 4
    quote = next(n for n in kaarten.values() if "PETA" in n.claim)
    assert "quote" in quote.tags and subject_van(quote.model_dump()) == "wol"
    negentig = next(n for n in kaarten.values() if "90%" in n.claim)
    assert "verificatie_vereist" in negentig.tags
    # validator fail-closed: onbekend subject → ongesorteerd; onbekende provenance → unknown
    los = next(n for n in kaarten.values() if "zonder herkenbaar" in n.claim)
    assert subject_van(los.model_dump()) == "" and los.provenance == "unknown"
    assert "raar" not in los.tags
    # intake is dom: geen veld/zekerheid op de kaart
    for n in kaarten.values():
        assert not hasattr(n, "trust") or getattr(n, "trust", None) is None


def test_stable_id_zelfde_claim_andere_bron_is_aparte_stem():
    a = stable_id("Leer is een bijproduct.", "Patched-column")
    b = stable_id("Leer is een bijproduct.", "landbouweconomie")
    c = stable_id("Leer is een BIJPRODUCT!", "patched column")   # normalisatie
    assert a != b            # andere bron → aparte stem (woozle-guard heeft dit nodig)
    assert a == c            # zelfde content + zelfde bron → idempotent


def test_parse_intake_fail_closed():
    assert parse_intake(None) == []
    assert parse_intake("geen json") == []
    assert parse_intake('{"niet": "een array"}') == []
    ok = parse_intake('```json\n[{"content": "x", "subject": "leer", '
                      '"provenance": "media", "source": "s"}]\n```')
    assert len(ok) == 1 and ok[0]["subject"] == "leer"
    assert "ONDERWERP-lijst" in build_intake_prompt("x") and SUBJECTS[0] in build_intake_prompt("x")


def test_intake_faalt_closed_zonder_llm(tmp_path):
    assert intake("tekst", "", str(tmp_path), reason_fn=lambda *a, **k: None) is None
    assert intake("", "", str(tmp_path), reason_fn=_fake_reason) == ([], 0)


# ── fase 3: opritten ─────────────────────────────────────────────────────────

def _atoms():
    return {
        "z1": {"claim": "PLA composteert volledig industrieel", "source": "WUR",
               "tags": ["materiaal"]},
        "z2": {"claim": "Cellulosediacetaat composteert wisselend", "source": "WUR",
               "tags": ["materiaal"]},
        "z3": {"claim": "Soleic PU bruikbaar in composteerbare zolen", "source": "rc.eu",
               "tags": ["materiaal"]},
        "w1": {"claim": "Mensen wachten maanden en kopen toch", "source": "shop",
               "tags": ["vraag"]},
        "w2": {"claim": "Winkelwagen-verlaters nemen toe na zes weken wachten",
               "source": "shop", "tags": ["vraag"]},
        "los": {"claim": "Iets ongesorteerds", "source": "x", "tags": []},
    }


@pytest.mark.smoke
def test_clusters_bottom_up_alleen_ongebonden():
    atoms = _atoms()
    cl = clusters(atoms, [], min_size=3)
    assert len(cl) == 1 and cl[0]["hub"] == "materiaal"
    assert set(cl[0]["atom_ids"]) == {"z1", "z2", "z3"}
    # eenmaal gebonden aan een inzicht → geen cluster meer (emergentie is voor vrij werk)
    inzicht = {"evidence": [{"atom_id": "z1"}, {"atom_id": "z2"}]}
    assert clusters(atoms, [inzicht], min_size=3) == []
    assert "los" in ongebonden(atoms, [])


def test_ongesorteerd_bakje_alleen_kennisbank_atomen(tmp_path):
    """Legacy Librarian-kaartjes (geen provenance) overspoelen het bakje niet;
    een kennisbank-atoom zonder onderwerp staat er wél in."""
    import types
    from nooch_village.views.kennisbank import _ongesorteerd_bakje
    atoms = {
        "legacy": {"claim": "an english librarian card", "source": "gsc", "tags": ["vegan"]},
        "kb_los": {"claim": "notitie zonder onderwerp", "source": "x",
                   "provenance": "unknown", "tags": []},
        "kb_hub": {"claim": "notitie met hub", "source": "x",
                   "provenance": "media", "tags": ["leer"]},
    }
    html = _ongesorteerd_bakje(atoms, [], csrf="t")
    assert "ongesorteerd (1)" in html
    assert "notitie zonder onderwerp" in html
    assert "librarian card" not in html and "notitie met hub" not in html


def test_gather_stance_via_llm_fail_closed():
    atoms = _atoms()
    stance_llm = lambda prompt, **kw: '[{"nr": 1, "stance": "support"}, {"nr": 2, "stance": "counter"}]'
    kand = gather("wachten is een feature geen kost", atoms, reason_fn=stance_llm)
    ids = [k["atom_id"] for k in kand]
    assert "w1" in ids and "w2" in ids
    assert any(k["stance"] == "counter" for k in kand)          # de tegen-sectie bestaat
    # zonder LLM: alles support (mens draait zelf), geen crash
    kand2 = gather("wachten is een feature", atoms, reason_fn=lambda *a, **k: None)
    assert kand2 and all(k["stance"] == "support" for k in kand2)


# ── fase 3: de dialoog + munten ──────────────────────────────────────────────

_BLOK = ("Goed gescherpt. Hier is het blok:\n\n=== INZICHT ===\n"
         "TITEL: Wachttijd bindt\nCLAIM: Wachttijd bindt de kern-doelgroep.\n"
         "REFRAME: Wachttijd is een kost die we mooi inpakken.\n"
         "FALSIFIER: Een kortere wachttijd verhoogt de conversie zichtbaar.\n=== EINDE ===")


@pytest.mark.smoke
def test_spel_tot_blok_en_munten_v10(tmp_path):
    dd = str(tmp_path)
    store = SpelStore(f"{dd}/spel.json")
    kb = KennisbankStore(f"{dd}/kennisbank.json")
    atoms = _atoms()
    sid = store.start("wachttijd is een feature",
                      [{"atom_id": "w1", "stance": "support"},
                       {"atom_id": "w2", "stance": "counter"}], by="test")

    beurten = iter(["Sterkste tegenovergestelde: ... Wat vind je?", _BLOK])
    fake = lambda prompt, **kw: next(beurten)
    assert spel_beurt(store, sid, "", atoms, reason_fn=fake)      # opening van de AI
    assert store.get(sid)["status"] == "open"
    assert spel_finish(store, sid, kb) is None                    # geen blok → niet muntbaar
    assert spel_beurt(store, sid, "mijn reactie: 70/100", atoms, reason_fn=fake)
    assert store.get(sid)["status"] == "klaar"

    iid, versie = spel_finish(store, sid, kb)
    assert versie == "1.0"
    ins = kb.get(iid)
    assert ins["title"] == "Wachttijd bindt de kern-doelgroep."
    assert ins["falsifier"].startswith("Een kortere wachttijd")
    assert [l["atom_id"] for l in ins["evidence"]] == ["w1", "w2"]     # verankerd aan de set
    assert store.get(sid)["status"] == "gemunt"
    assert spel_finish(store, sid, kb) is None                    # idempotent: nooit dubbel munten


def test_spel_herformuleer_bumpt_versie_met_history(tmp_path):
    dd = str(tmp_path)
    store = SpelStore(f"{dd}/spel.json")
    kb = KennisbankStore(f"{dd}/kennisbank.json")
    iid = kb.add("Prijs blokkeert onze kern-doelgroep", subject="prijs")
    kb.link(iid, "p1", "support")

    sid = store.start("prijs", [{"atom_id": "p1", "stance": "support"}],
                      reformulate_of=iid, by="test")
    blok = _BLOK.replace("Wachttijd bindt de kern-doelgroep.",
                         "Prijs is de drempel voor de Idealist.")
    assert spel_beurt(store, sid, "", _atoms(), reason_fn=lambda p, **k: blok)
    iid2, versie = spel_finish(store, sid, kb)
    assert iid2 == iid and versie == "1.1"
    ins = kb.get(iid)
    assert ins["title"] == "Prijs is de drempel voor de Idealist."
    assert ins["history"][0]["title"] == "Prijs blokkeert onze kern-doelgroep"
    assert [l["atom_id"] for l in ins["evidence"]] == ["p1"]      # evidence stroomt door


def test_spel_faalt_closed_zonder_llm(tmp_path):
    store = SpelStore(str(tmp_path / "spel.json"))
    sid = store.start("x", [{"atom_id": "a", "stance": "support"}])
    assert spel_beurt(store, sid, "hoi", {}, reason_fn=lambda *a, **k: None) is None
    s = store.get(sid)
    assert s["status"] == "open" and s["messages"][-1]["role"] == "ik"   # niets verloren
