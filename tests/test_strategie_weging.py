"""Strategische weging van de kennisbank-voorstellen (founder 24 jul): de suggestiekaart rangschikt
clusters op relevantie voor de Nooch-missie (mission.STRATEGIE_THEMAS), niet puur op grootte."""
from __future__ import annotations

from nooch_village.mission import strategie_relevantie
from nooch_village import kennisbank_spel as ks


def test_strategie_relevantie_herkent_kernwaarden_en_negeert_ruis():
    n, labels = strategie_relevantie("Zuiver natuurrubber, vrij van microplastics en dierlijke resten")
    assert n >= 2 and "geen plastic" in labels
    assert strategie_relevantie("SUPIMA heeft extra-lange stapellengte en fijnheid") == (0, [])


def test_klein_strategisch_cluster_verslaat_groot_ruis_cluster():
    subs = list(ks.SUBJECTS)
    big, small = subs[0], subs[1]
    atoms = {
        "a1": {"claim": "SUPIMA heeft extra-lange stapellengte", "tags": [big]},
        "a2": {"claim": "SUPIMA geeft betere garen-tellingen", "tags": [big]},
        "a3": {"claim": "SUPIMA kleurbehoud is superieur", "tags": [big]},
        "b1": {"claim": "Zuiver natuurrubber, vrij van microplastics en dierlijke resten", "tags": [small]},
        "b2": {"claim": "Mycelium-materiaal is composteerbaar en biobased", "tags": [small]},
    }
    cls = ks.clusters(atoms, [])
    # Het strategische cluster (2 kaarten, meerdere thema's) staat vóór het grotere ruis-cluster (3, 0).
    assert cls[0]["hub"] == small and cls[0]["strategie_score"] >= 2
    assert cls[1]["strategie_score"] == 0
    # De suggesties dragen de thema-labels mee voor de UI-badge.
    assert ks.spel_suggesties(atoms, [])[0]["strategie_themas"]


def test_spelprompt_poorten_en_caveat(tmp_path):
    # De verbeterde spelprompt bevat de kern-poorten, en het CAVEAT-veld stroomt door tot het inzicht.
    from nooch_village.kennisbank import bouw_spel_prompt, parse_blok, KennisbankStore
    pr = bouw_spel_prompt("mycelium is een belofte", [{"claim": "x", "stance": "counter"}])
    for nodig in ("NU:", "wissel nooit stiekem", "geen toetsbaar inzicht", "waarneembaar", "CAVEAT:"):
        assert nodig in pr
    blok = ("=== INZICHT ===\nTITEL: T\nCLAIM: C\nREFRAME: R\nFALSIFIER: F\n"
            "CAVEAT: leunt op één bron\n=== EINDE ===")
    assert parse_blok(blok)["caveat"] == "leunt op één bron"
    kb = KennisbankStore(f"{tmp_path}/kb.json")
    p = parse_blok(blok)
    iid = kb.add(p["claim"], reframe=p["reframe"], falsifier=p["falsifier"], caveat=p["caveat"], by="t")
    assert kb.get(iid)["caveat"] == "leunt op één bron"
    # reformulate bewaart de oude caveat in history en zet de nieuwe.
    kb.reformulate(iid, title="C2", caveat="nieuwe kanttekening", by="t")
    assert kb.get(iid)["caveat"] == "nieuwe kanttekening"
    assert kb.get(iid)["history"][-1]["caveat"] == "leunt op één bron"
