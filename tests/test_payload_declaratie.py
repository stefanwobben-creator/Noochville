"""Elke skill met een runtime-payload-eis moet die ook DECLAREREN.

Dit is de derde keer dat declaratie afwijkt van handhaving:

  luna     een ladder-trede zonder prijs — de maandcap telde hem voor €0,00
  domein   de Librarian hield `library`, de guard bewaakte `bibliotheek`
  payload  `claims_check` eist bij het draaien "text of terms" en declareert `required_payload = ()`

Elke keer hetzelfde patroon: een eis die op twee plekken moet kloppen, met niets dat ze bindt. En
elke keer hetzelfde gevolg — de poort láát iets door dat daarna alsnog weigert, en het spoor van de
oorzaak zit diep in een puls-log. In de onderzoekspas kostte het de tweede bron: de payload-poort
gaf groen, de skill weigerde, en het voorstel rustte op één bron.

De sweep draait élke geregistreerde skill met een lege payload. Klaagt hij over een ontbrekend veld,
dan hoort dat veld in `required_payload` — anders vangt geen enkele poort het vóór de aanroep.
"""
from __future__ import annotations

import re

import pytest

from nooch_village.registry_factory import build_skill_registry
from nooch_village.skills import ontbrekende_velden

# Een klacht over ontbrekende invoer, zoals skills die formuleren.
_MIST = re.compile(r"(ontbrekende parameter|geef\s+'?\w|verplicht|is verplicht|opgeven|"
                   r"niet-leeg|ontbreekt|vereist|required)", re.I)


def _skills():
    reg = build_skill_registry()
    namen = sorted(getattr(reg, "_skills", {}) or {})
    return [(n, reg.get(n)) for n in namen]


def _klacht(obj) -> str:
    """Draai met een LEGE payload en geef de klacht terug, of "" als hij niet over invoer klaagt.

    Offline-veilig: een skill die zonder payload alsnog netwerk of config aanraakt, geeft geen
    payload-klacht maar een andere fout — die telt hier niet mee (en zou de sweep niet mogen
    laten falen op iets dat geen declaratie-gat is)."""
    try:
        uit = obj.run({}, None)
    except Exception:                                # noqa: BLE001 — geen payload-klacht
        return ""
    if not isinstance(uit, dict):
        return ""
    boodschap = str(uit.get("error") or uit.get("reason") or uit.get("reden") or "")
    if not boodschap or uit.get("no_data"):
        return ""
    return boodschap if _MIST.search(boodschap) else ""


def _validate_vangt(obj) -> bool:
    """Vangt `validate_payload` een lege payload?

    De tweede poort. `community_listening` declareert bewust `required_payload = ()` omdat zijn eis
    voorwaardelijk is (query_set_id óf queries) en laat `validate_payload` het bewaken — dat is een
    geldig ontwerp, geen gat. Een sweep die alleen naar `required_payload` kijkt zou dat als gat
    melden en me iets laten "repareren" dat al werkt. Beide poorten tellen dus."""
    vp = getattr(obj, "validate_payload", None)
    if not callable(vp):
        return False
    try:
        return bool(list(vp({}, None) or []))
    except Exception:                                # noqa: BLE001
        return False


def test_elke_runtime_payload_eis_staat_ook_in_een_poort():
    """De sweep. Klaagt een skill bij een lege payload over ontbrekende invoer, dan moet
    `required_payload` dat óók zeggen — anders geeft de poort groen en weigert de skill alsnog."""
    gaten = []
    for naam, obj in _skills():
        if obj is None:
            continue
        boodschap = _klacht(obj)
        if not boodschap:
            continue
        req = tuple(getattr(obj, "required_payload", ()) or ())
        if ontbrekende_velden(req, {}):
            continue                                 # gedeclareerd → de poort vangt het
        if _validate_vangt(obj):
            continue                                 # voorwaardelijke eis via validate_payload — ook goed
        gaten.append(f"{naam}: klaagt \"{boodschap[:70]}\" maar required_payload={req or '()'} "
                     f"en validate_payload vangt het niet")
    assert gaten == [], (
        "runtime-eis niet gedeclareerd (de payload-poort laat dit door en de skill weigert alsnog):\n"
        + "\n".join(f"  - {g}" for g in gaten))


def test_claims_check_declareert_zijn_of_of_eis():
    """Het concrete geval. Plat als ("text","terms") zou BEIDE eisen en de skill op de andere
    manier breken — de skill accepteert er één."""
    from nooch_village.skills_impl.claims_check import ClaimsCheckSkill
    req = ClaimsCheckSkill.required_payload
    assert any(isinstance(v, (tuple, list)) for v in req), "of-of-eis hoort als tuple-element"
    assert ontbrekende_velden(req, {}) == ["text|terms"]
    assert ontbrekende_velden(req, {"text": "iets"}) == []
    assert ontbrekende_velden(req, {"terms": ["iets"]}) == []


# ── De disjunctie-lezer, en dat alle drie de consumenten hem delen ──────────

@pytest.mark.parametrize("req,payload,verwacht", [
    ((("text", "terms"),), {}, ["text|terms"]),
    ((("text", "terms"),), {"text": "x"}, []),
    ((("text", "terms"),), {"terms": ["x"]}, []),
    ((("text", "terms"),), {"text": ""}, ["text|terms"]),        # leeg telt als afwezig
    (("brands", "claim"), {"brands": ["x"]}, ["claim"]),
    ((), {}, []),
])
def test_ontbrekende_velden_leest_beide_vormen(req, payload, verwacht):
    assert ontbrekende_velden(req, payload) == verwacht


def test_de_drie_consumenten_delen_een_lezer():
    """Zou elk zijn eigen lus houden, dan kent de ene de of-of-vorm wel en de andere niet — en dan
    hebben we de klasse fout die deze test moet stoppen alsnog, één laag dieper."""
    for pad in ("nooch_village/inhabitant.py", "nooch_village/skill_match.py"):
        src = open(pad, encoding="utf-8").read()
        assert "ontbrekende_velden" in src, f"{pad} leest required_payload nog zelf"
