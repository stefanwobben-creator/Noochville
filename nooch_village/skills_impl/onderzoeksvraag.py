from __future__ import annotations
import json
import re
from nooch_village.skills import Skill


class OnderzoeksvraagSkill(Skill):
    """Leidt uit een bevestigde trend-kaart één onderzoekbare 'waaróm'-vraag af.

    Zelfde patroon als verband_voorstel: één LLM-call, één regel terug, fail-closed.
    Produceert geen kennis en doet geen externe research; levert alleen de vraag die
    de scientist daarna met zijn bestaande grounding-skills kan onderzoeken.

    DRIE OORZAKEN, DRIE ANTWOORDEN (scope 54). Tot dan gaf de skill voor géén model, een onparseerbaar
    antwoord én "geen" hetzelfde terug: `{"vraag": None}`. Dat classificeert als 'leeg/geen_inhoud' —
    een dorp zonder werkende ladder vinkte het item dus af als "onderzocht, niets gevonden". Nu is geen
    model een `error` (het item blijft open), en "geen zinvolle vraag" of onzin een `no_data` met reden.
    `vraag` blijft in alle gevallen staan (None bij falen) voor de verdiep-lus in roles.py.

    De prompt is Engels (de inhoudslaag sinds 06-09-2026), vraagt JSON met `json_mode` en een klein
    tokenbudget — één vraag hoeft geen 700 tokens. De payload mag naast `kaart` ook losse `word`/`claim`
    dragen, want een projectplanner heeft zelden een kaart-dict bij de hand (23 runs, 0 in 30 dagen).
    """
    name = "onderzoeksvraag"
    cost = "free"  # kleine begrensde LLM-tokenkost wordt bewust niet gevlagd
    side_effect_free = True
    description = ("Derives ONE researchable why-question from a confirmed trend: give the trend term "
                   "and what is known about it. Returns the question that the corpus sources "
                   "(openalex_evidence, epo_patents) can then be asked; 'no_data' when no sensible "
                   "question can be formed. One model call, no external research.")
    input_schema = ("kaart: {word: str, claim: str} (the trend card) — OR the two fields directly: "
                    "word: str (required — the trend term, e.g. 'barefoot shoes') and claim: str "
                    "(optional — what we know about the trend, one sentence). Optional: locale: str "
                    "(language of the answer, default English)")
    required_payload = (("kaart", "word"),)
    output_schema = ("vraag: str (one researchable question), text (the same, for the wall) | "
                     "no_data + reason (no sensible question) + vraag: None | "
                     "error (no model) + vraag: None")

    def validate_payload(self, payload: dict, context) -> list:
        """Een `kaart` die geen dict is en geen los `word` ernaast: dat is geen trend-kaart maar
        tekst, en dat weigeren we bij het plannen in plaats van live met een cryptische fout."""
        kaart = (payload or {}).get("kaart")
        word = str((payload or {}).get("word") or "").strip()
        if kaart is not None and not isinstance(kaart, dict) and not word:
            return ["'kaart' moet een dict {word, claim} zijn (of geef 'word' en 'claim' los mee)"]
        if isinstance(kaart, dict) and not str(kaart.get("word") or "").strip() and not word:
            return ["'kaart' mist 'word' (de trend-term)"]
        return []

    def run(self, payload: dict, context) -> dict:
        payload = payload if isinstance(payload, dict) else {}
        kaart = payload.get("kaart")
        if not isinstance(kaart, dict):
            kaart = {}
        word = str(kaart.get("word") or payload.get("word") or "").strip()
        claim = str(kaart.get("claim") or payload.get("claim") or "").strip()
        if not word:
            return {"error": "ontbrekende parameter: 'kaart.word' of 'word' is verplicht", "vraag": None}
        uit = self._llm(word, claim, payload.get("locale"), ladder=payload.get("ladder"))
        if uit is None:
            return {"error": "geen model beschikbaar — geen onderzoeksvraag afgeleid", "vraag": None}
        if not uit:
            return {"no_data": True, "vraag": None,
                    "reason": f"het model kon geen zinvolle onderzoeksvraag vormen bij '{word}'"}
        return {"vraag": uit, "text": uit, "word": word}

    def _llm(self, word: str, claim: str, locale: str | None = None, *, ladder=None):
        """None = geen model (of een modelfout); "" = geen zinvolle vraag; anders de vraag."""
        from nooch_village.llm import reason
        from nooch_village.language import instruction
        prompt = (
            "A search term about sustainable footwear keeps coming up as a rising trend. We want to "
            "understand the WHY underneath it by looking up scientific literature. Formulate ONE "
            "concrete, researchable question that touches the cause or mechanism behind this trend "
            "(for example the benefits, the drivers, or the evidence). Ground it only in the term and "
            "what is known below; do not add facts. Not a yes/no question, no marketing, not a "
            "compound question.\n\n"
            f"TREND TERM: {word[:120]}\n"
            f"WHAT WE KNOW: {claim[:600] or '(nothing beyond the term)'}\n\n"
            'Answer ONLY with JSON, exactly this shape: {"question": "<one researchable question>"}. '
            'If no sensible question can be formed: {"question": null}.\n'
            + instruction(locale)
        )
        try:
            out = reason(prompt, json_mode=True, max_tokens=150, call_site="skill_onderzoeksvraag",
                         ladder=ladder)
        except Exception:                                    # noqa: BLE001 — een modelfout is 'geen model'
            return None
        if not out:
            return None
        return _vraag_uit(out)


def _vraag_uit(rauw) -> str:
    """De vraag uit het modelantwoord: JSON (`question`, ook met ```-fences), en als overgangs-
    tolerantie de oude regelvorm "QUESTION:"/"VRAAG:". "" bij 'geen'/null/onparseerbaar."""
    tekst = str(rauw or "").strip()
    tekst = re.sub(r"^```(?:json)?|```$", "", tekst, flags=re.M).strip()
    data = None
    try:
        data = json.loads(tekst)
    except Exception:                                        # noqa: BLE001
        m = re.search(r"\{.*\}", tekst, re.S)
        if m:
            try:
                data = json.loads(m.group())
            except Exception:                                # noqa: BLE001
                data = None
    if isinstance(data, dict):
        v = data.get("question", data.get("vraag"))
        vraag = str(v or "").strip()
    else:
        m = re.search(r"(?:QUESTION|VRAAG):\s*(.+)", tekst, re.IGNORECASE)
        vraag = m.group(1).strip() if m else ""
    vraag = vraag.strip().strip('"').strip()
    if not vraag or vraag.lower() in ("null", "none") or vraag.lower().startswith(("geen", "none")):
        return ""
    return vraag
