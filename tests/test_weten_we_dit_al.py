"""weten_we_dit_al (founder, 19 jul): geheugen-eerst voor elke bewoner, met een expliciet
ja/nee. Borgingen: (1) een sterke match over meerdere lagen → bekend=True met treffers
per laag; (2) geen directe match maar wel aangrenzend materiaal → bekend=False mét
context (bij N krijg je mee wat het dorp wél al weet); (3) niets → onontgonnen terrein;
(4) de Kroniek-brug logt bevestigd bij een direct antwoord en leeg bij een gat — context
telt bewust niet als bekend."""
from __future__ import annotations

import json
import types

from nooch_village.evidence_ledger import EvidenceLedger
from nooch_village.kennisbank import KennisbankStore
from nooch_village.projects import ProjectLedger
from nooch_village.skills_impl.weten_we_dit_al import WetenWeDitAlSkill


def _dorp(tmp_path) -> str:
    """Een klein dorp-geheugen: één inzicht, twee kaarten, twee Kroniek-regels, één
    afgerond project mét antwoord."""
    dd = str(tmp_path)
    kb = KennisbankStore(f"{dd}/kennisbank.json")
    kb.add("Barefoot schoenen activeren voetspieren aantoonbaar",
           why="EMG-studies tonen veranderde spieractivatie", subject="barefoot")
    atoms = {
        "a1": {"claim": "Wandelen in minimalistische barefoot schoenen verandert de "
                        "spieractivatie in het onderbeen", "tags": ["signal"],
               "source": "EMG-studie 2018", "provenance": "peer_reviewed"},
        "a2": {"claim": "PFAS-regelgeving dwingt de schoenenindustrie naar plasticvrije "
                        "alternatieven", "tags": ["regelgeving"], "source": "vneconomy"},
    }
    with open(f"{dd}/notes.json", "w", encoding="utf-8") as f:
        json.dump(atoms, f)
    led = EvidenceLedger(f"{dd}/evidence_ledger.jsonl")
    led.record(role_id="harry_hemp", skill="openalex_evidence",
               query="barefoot schoenen voetspieren EMG", source="openalex", status="bevestigd")
    led.record(role_id="harry_hemp", skill="epo_patents",
               query="barefoot afbreekbare zolen", source="epo_patents", status="leeg")
    pj = ProjectLedger(f"{dd}/projects.json")
    pid = pj.create("harry_hemp", "Structureer bewijs voor barefoot-claims", "human")
    pj.set_dod(pid, "dod_outcome", "327 studies gevonden; spieractivatie-effect bevestigd.")
    return dd


def test_bekend_ja_over_meerdere_lagen(tmp_path):
    dd = _dorp(tmp_path)
    ctx = types.SimpleNamespace(data_dir=dd)
    res = WetenWeDitAlSkill().run({"vraag": "wat weten we over barefoot schoenen en voetspieren?"}, ctx)
    assert res["ok"] and res["bekend"] is True
    assert res["inzichten"] and res["kaarten"]
    assert res["kroniek"]["bevestigd"]                     # de EMG-Kroniek-regel raakt sterk
    # het project raakt maar één vraagwoord (barefoot) → eerlijk als context, mét antwoord
    proj = [c for c in res["context"] if c["laag"] == "project"]
    assert proj and proj[0]["antwoord"].startswith("327 studies")
    assert res["samenvatting"].startswith("Ja")


def test_bekend_nee_maar_met_context(tmp_path):
    dd = _dorp(tmp_path)
    ctx = types.SimpleNamespace(data_dir=dd)
    # 'regelgeving' raakt alleen de PFAS-kaart, met één woord → context, geen direct antwoord
    res = WetenWeDitAlSkill().run({"vraag": "regelgeving rond composteerbaarheid"}, ctx)
    assert res["ok"] and res["bekend"] is False
    assert res["context"], "bij N hoort mee wat het dorp wél al weet"
    assert any(c["laag"] == "kaart" and "PFAS" in c["claim"] for c in res["context"])
    assert res["samenvatting"].startswith("Nee") and "context" in res["samenvatting"]


def test_onontgonnen_terrein_en_kroniek_brug(tmp_path):
    dd = _dorp(tmp_path)
    ctx = types.SimpleNamespace(data_dir=dd)
    sk = WetenWeDitAlSkill()
    leeg = sk.run({"vraag": "kwantumcomputers voor veters"}, ctx)
    assert leeg["ok"] and leeg["bekend"] is False and not leeg["context"]
    assert "onontgonnen" in leeg["samenvatting"]
    # Kroniek-brug: direct antwoord → bevestigd; gat → leeg (context telt niet als bekend)
    ja = sk.run({"vraag": "barefoot schoenen voetspieren"}, ctx)
    assert sk.evidence_records(ja, role_id="noochie")[0]["status"] == "bevestigd"
    assert sk.evidence_records(leeg, role_id="noochie")[0]["status"] == "leeg"
    assert sk.evidence_records({"ok": False}, role_id="noochie") == []


def test_lege_vraag_faalt_netjes(tmp_path):
    res = WetenWeDitAlSkill().run({"vraag": "en of de"}, types.SimpleNamespace(data_dir=str(tmp_path)))
    assert not res["ok"] and "betekenisvol" in res["error"]
