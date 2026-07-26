"""De grens tussen i18n-batch 2A (stem) en 2C (enum-prompts mét parser).

2A heeft de STEM naar het Engels gebracht: de missietekst, de persona-preamble en de vrije-tekst-
prompts. Bewust NIET vertaald zijn de prompts waarvan een parser een NEDERLANDS antwoord-token
verwacht — die gaan pas om samen met hun parser (2C), anders valt de parsing stil om.

Deze test is de vangrail op die afspraak. Hij faalt zodra iemand één kant van zo'n paar vertaalt:
- vertaal je het prompt-token, dan mist de assert hier → je ziet meteen dat de parser mee moet;
- doe je 2C netjes (prompt + parser samen), dan pas je deze test in dezelfde commit aan en is de
  lijst weer waar.

Het is dus expliciet GEEN test die zegt "Nederlands moet blijven" — het is er een die zegt
"prompt en parser horen bij elkaar".
"""
from __future__ import annotations

import pathlib

from nooch_village.personas import Persona, persona_prompt

_PKG = pathlib.Path(__file__).resolve().parent.parent / "nooch_village"


def _src(naam: str) -> str:
    return (_PKG / naam).read_text(encoding="utf-8")


# ── 2C-werklijst: prompt-token ↔ parser die het leest ────────────────────────────────────────────

def test_mention_triage_enum_blijft_bij_zijn_parser():
    """cockpit2._ai_reply vraagt {"fit": "ja|deels|nee"}; _parse_triage weigert al het andere
    (fail-closed → geen triage meer, stil terugvallen op een platte reactie)."""
    s = _src("cockpit2.py")
    assert '\\"fit\\": \\"ja|deels|nee\\"' in s or '"fit": "ja|deels|nee"' in s
    assert 'if fit not in ("ja", "deels", "nee")' in s


def test_project_worker_markers_blijven_bij_hun_regex():
    """project_worker.work_one is Engels proza (mini-2C) maar VRAAGT onverkort de Nederlandse
    markers KAN NIET:/LEVER: — dat is het contract met _CANT. De prompt zegt er expliciet bij dat
    ze letterlijk overgenomen moeten worden."""
    s = _src("project_worker.py")
    assert "KAN NIET: <what is needed for that>" in s
    assert "LEVER: <your concrete outcome or next step>" in s
    assert "are Dutch ON PURPOSE" in s


def test_project_worker_parser_is_tolerant_voor_afdwaling():
    """De prompt is Engels, dus een model kan naar CANNOT:/DELIVER: afdwalen. Dat mag nooit STIL
    als deliverable landen (geblokkeerd project dat er afgerond uitziet), dus de parser herkent de
    Engelse variant óók — zonder 'm voor te schrijven."""
    from nooch_village.project_worker import work_one
    assert work_one("x", "r", "p", llm_reason=lambda _p: "KAN NIET: een sleutel") == {
        "ok": False, "needs": "een sleutel"}
    assert work_one("x", "r", "p", llm_reason=lambda _p: "CANNOT: a key") == {
        "ok": False, "needs": "a key"}
    assert work_one("x", "r", "p", llm_reason=lambda _p: "LEVER: af")["outcome"] == "af"
    assert work_one("x", "r", "p", llm_reason=lambda _p: "DELIVER: done")["outcome"] == "done"


def test_opportunity_reflex_velden_blijven_bij_hun_parser():
    """inhabitant._opportunity_reflex vraagt TITEL/WAT/WAAROM; _parse_opportunity leest die sleutels."""
    s = _src("inhabitant.py")
    assert "TITEL:" in s and "WAT:" in s and "WAAROM:" in s
    assert 'key in ("titel", "title")' in s and 'key == "wat"' in s


def test_noochie_weigh_in_velden_blijven_bij_hun_parser():
    """roles.Noochie._weigh_in vraagt BEVINDING/VRAAG + verdict 'niet_ok'; _parse_noochie_report en
    parse_verdict_reason lezen die tokens."""
    s = _src("roles.py")
    assert "BEVINDING:" in s and "VRAAG:" in s and "niet_ok" in s
    assert 'low.startswith("bevinding")' in s


# ── 2A-belofte: de stem is Engels én laat machine-tokens met rust ────────────────────────────────

def test_persona_preamble_is_engels_met_vangrail():
    """De preamble gaat vóór de prompts hierboven. Hij stuurt op Engels proza, maar zegt er
    expliciet bij dat voorgeschreven veldwaarden/markers letterlijk overgenomen worden — anders
    zou hij precies de tokens vertalen die de parsers hierboven nodig hebben."""
    pr = persona_prompt(Persona(id="x", name="Sid", mbti="INTJ", instructions="Nuchter."))
    assert "Always respond in English." in pr
    assert "reproduce those EXACTLY as given" in pr
    assert pr.startswith("You are Sid (INTJ).")


def test_missie_is_engels():
    from nooch_village.mission import ANCHOR_PURPOSE
    assert "most sustainable shoe brand" in ANCHOR_PURPOSE
    assert "duurzaamste" not in ANCHOR_PURPOSE


def test_strategie_themas_blijven_nederlands():
    """De thema-trefwoorden matchen DETERMINISTISCH op (nog) Nederlandse content in de kennisbank.
    Ze vertalen hoort bij 2D (strategie-lexicon), samen met de content waarop ze matchen."""
    from nooch_village.mission import STRATEGIE_THEMAS, strategie_relevantie
    assert "geen plastic" in STRATEGIE_THEMAS
    n, labels = strategie_relevantie("Deze zool is composteerbaar en bevat geen plastic.")
    assert n >= 2 and "geen plastic" in labels
