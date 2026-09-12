"""tegenspraak — kritische tegenspraak vóór 'done' (founder, 22 jul).

Het dorp gathert en schrijft volop, en heeft domein-checks (content_check voor copy, claims_check
voor compliance), maar geen ALGEMENE skill die een willekeurige deliverable of claim ADVERSARIEEL
toetst voordat hij als klaar geldt. Deze skill vult dat gat: gegeven een stuk output (en optioneel
de onderbouwing waarop het zou moeten rusten), zoekt hij de zwakste of meest overdreven claim, wat
ongegrond is, het sterkste tegenargument, en geeft een concrete revisie of de verplichte nuance.
Voor élke rol, op élke output — de 'waarheidslat' van de Kroniek als bruikbaar gereedschap.

Read-only, fail-soft: zonder LLM of zonder tekst geeft-ie geen oordeel i.p.v. een verzonnen 'ok'.
Legt de toetsing vast in De Kroniek, zodat Lara ziet welke rollen hun eigen werk tegenspreken en of
het de lat haalde.

SCOPE 57 (skill-review 12-09-2026). De wall las "usable (4): 4 results" met vier losse zinnen: de
lijst `ongegrond` won de vorm en het oordeel zelf stond nergens leesbaar. Nu draagt `text` het
oordeel voorop ("VERDICT: needs revision — 4 unsupported claims: …; revision: …") en zijn de
ongegronde beweringen records (`bevindingen`), zodat wall en verslag oordeel + revisie tonen.
Placeholder-bewijs ("To be populated from claim_evidence results" — 46 live items) wordt geweigerd:
een toets tegen een placeholder is schijn-toetsing. Prompt en oordeelwaarden zijn Engels, zoals de
wall en het verslag; `ongegrond` blijft als alias staan voor de missie-critic.
"""
from __future__ import annotations

import json
import re

from nooch_village.skills import Skill
from nooch_village.llm_keuze import skill_ladder

# De twee oordeelwaarden (Engels sinds scope 57). De missie-critic leest ze via `NEEDS_REVISION`.
HOLDS = "holds"
NEEDS_REVISION = "needs revision"

# Tekst die geen bewijs is maar een gat waar bewijs had moeten staan. Live schreef de planner
# "To be populated from claim_evidence results" in `bewijs` — de skill toetste dan een verzonnen
# tekst tegen een verzonnen onderbouwing en gaf een oordeel dat nergens op rustte.
_PLACEHOLDER = re.compile(r"to be (?:populated|filled|determined|added|completed)|\bTODO\b|\bTBD\b|"
                          r"\[…\]|\[\.\.\.\]|\[insert[^\]]*\]|\bplaceholder\b", re.I)


def leest_als_placeholder(tekst: str) -> str:
    """Het placeholder-fragment dat in `tekst` staat, of "" als de tekst als echt materiaal leest."""
    m = _PLACEHOLDER.search(tekst or "")
    return m.group(0) if m else ""


class TegenspraakSkill(Skill):
    name = "tegenspraak"
    cost = "free"                   # begrensde LLM-tokenkost, bewust niet gevlagd (zoals content_check)
    side_effect_free = True         # leest/redeneert, schrijft niets; het Kroniek-record beschrijft hij
    description = ("Argue against a deliverable or claim BEFORE it counts as done: the weakest or most "
                   "overstated claim, the statements the evidence does not support, the strongest "
                   "counter-argument, and a concrete revision or mandatory caveat. Any role, any "
                   "output; the text and its evidence must be real material, not placeholders.")
    input_schema = ("tekst: str (required — the deliverable or claim under test, the actual text); "
                    "bewijs: str (optional — the evidence it should rest on; leave empty if there is "
                    "none, never write a placeholder such as 'to be populated'); "
                    "doel: str (optional — the outcome the output serves); "
                    "ladder: str (optional — own model ladder, e.g. premium for a critic); "
                    "kader: str (optional — what exactly is under test; see missie_critic); "
                    "max_tokens: int (optional — answer budget; default 3000)")
    required_payload = ("tekst",)
    output_schema = ("ok, text ('VERDICT: holds|needs revision — …'), oordeel ('holds'|'needs revision'), "
                     "zwakste_claim, bevindingen (list of {label, claim}), ongegrond (the same claims as "
                     "strings, alias), tegenargument, revisie | error")

    def validate_payload(self, payload: dict, context) -> list:
        """Een placeholder in `tekst` of `bewijs` is bij het plannen al te zien: dan is er niets
        om te toetsen en hoort het item open te blijven tot het echte materiaal er is."""
        p = payload or {}
        redenen = []
        for veld in ("tekst", "bewijs"):
            frag = leest_als_placeholder(str(p.get(veld) or ""))
            if frag:
                redenen.append(f"'{veld}' reads as a placeholder ({frag!r}) — give the actual "
                               f"{'evidence' if veld == 'bewijs' else 'text'} or leave it empty")
        return redenen

    def run(self, payload: dict, context=None) -> dict:
        tekst = ((payload or {}).get("tekst") or "").strip()
        if not tekst:
            return {"error": "ontbrekende parameter: 'tekst' is verplicht"}
        bewijs = ((payload or {}).get("bewijs") or "").strip()
        doel = ((payload or {}).get("doel") or "").strip()
        for veld, waarde in (("tekst", tekst), ("bewijs", bewijs)):
            frag = leest_als_placeholder(waarde)
            if frag:
                return {"error": f"'{veld}' reads as a placeholder ({frag!r}): nothing to test against — "
                                 f"give the actual material or leave 'bewijs' empty (fail-closed)"}
        # Een eigen ladder mag: als deze skill als CRITIC draait (missie_critic) hoort het oordeel
        # van de premium-trede te komen. Een goedkoop oordeel dat als premium oordeel wordt gelezen
        # is precies de stille verwisseling die een reviewer niet kan zien.
        ladder = (((payload or {}).get("ladder") or "").strip()
                  or skill_ladder("skill_tegenspraak"))
        # Optioneel kader: WAT er precies getoetst wordt. Een aanroeper die een rapport ÓVER
        # materiaal toetst (de missie-critic) moet kunnen zeggen dat het aangehaalde materiaal het
        # onderzoeksobject is, niet de bewering van de schrijver. Zonder kader gedraagt de skill
        # zich exact als voorheen — de losse aanroepen door rollen veranderen niet.
        kader = ((payload or {}).get("kader") or "").strip()
        # Antwoordbudget. 700 volstaat voor een losse claim; een viervoudig JSON-oordeel over een
        # rapport van 6000 tekens niet — dat wordt halverwege afgekapt en is dan onparseerbaar.
        try:
            budget = max(200, int((payload or {}).get("max_tokens") or _DEFAULT_MAX_TOKENS))
        except (TypeError, ValueError):
            budget = _DEFAULT_MAX_TOKENS
        from nooch_village.llm import reason
        prompt = (
            "You are a strict, honest reviewer for Nooch (sustainable, plant-based shoes). Argue "
            "against the output below BEFORE it counts as done. Sharp but constructive: the goal is a "
            "better, more honest output, not demolition.\n\n"
            + (f"GOAL the output must serve:\n{doel}\n\n" if doel else "")
            + (f"AVAILABLE EVIDENCE (only what is written here counts as evidence):\n{bewijs}\n\n"
               if bewijs else
               "NOTE: no evidence was supplied. Treat every number, price and firm statement as "
               "potentially unsupported.\n\n")
            + f"OUTPUT UNDER TEST:\n{tekst}\n\n"
            + (f"FRAME FOR THIS REVIEW:\n{kader}\n\n" if kader else "")
            + "Do four things, using only the material above (say 'unknown' rather than assume):\n"
            "1. Name the WEAKEST or most overstated claim (one sentence).\n"
            "2. List the statements that are NOT supported by the evidence, or are firm without "
            "evidence. If everything is supported, give an empty list.\n"
            "3. Give the STRONGEST counter-argument or the most important missing counter-evidence.\n"
            "4. Give a CONCRETE revision, or the nuance/caveat that must be added.\n"
            f"Verdict: '{HOLDS}' if the output is correct and supported, otherwise '{NEEDS_REVISION}'.\n\n"
            "Answer ONLY with JSON:\n"
            f'{{"verdict":"{HOLDS} or {NEEDS_REVISION}","weakest_claim":"...","unsupported":["..."],'
            '"counter_argument":"...","revision":"..."}')
        raw = reason(prompt, call_site="skill_tegenspraak", ladder=ladder, json_mode=True,
                     max_tokens=budget)
        data = _extract(raw)
        if not isinstance(data, dict):
            # Onderscheid de twee oorzaken. "LLM weg" op een antwoord dát er is stuurt de lezer de
            # verkeerde kant op: dan ligt het aan het budget of het formaat, niet aan de leverancier.
            if raw:
                return {"ok": False, "error": (f"antwoord van {len(str(raw))} tekens is geen bruikbare "
                                               f"JSON (afgekapt op max_tokens={budget}?) — toets handmatig"),
                        "raw_lengte": len(str(raw))}
            return {"ok": False, "error": "geen bruikbaar oordeel (LLM weg) — toets handmatig"}
        # Liberaal lezen: de Engelse waarden zijn het contract, de Nederlandse ('houdt stand') de
        # overgangs-tolerantie voor een model dat doorschiet. Beide sleutelnamen om dezelfde reden.
        ruw = str(data.get("verdict") or data.get("oordeel") or "").strip().lower()
        oordeel = HOLDS if (ruw.startswith("hold") or ruw.startswith("houdt")) else NEEDS_REVISION
        ongegrond = [str(x)[:200] for x in (data.get("unsupported") or data.get("ongegrond") or [])
                     if str(x).strip()][:8]
        zwak = str(data.get("weakest_claim") or data.get("zwakste_claim") or "")[:300]
        tegen = str(data.get("counter_argument") or data.get("tegenargument") or "")[:400]
        revisie = str(data.get("revision") or data.get("revisie") or "")[:400]
        n = len(ongegrond)
        kop = f"VERDICT: {oordeel}"
        if ongegrond:
            kop += (f" — {n} unsupported claim{'s' if n != 1 else ''}: "
                    + "; ".join(c[:120] for c in ongegrond[:3]) + ("; …" if n > 3 else ""))
        elif zwak:
            kop += f" — weakest claim: {zwak[:160]}"
        if revisie:
            kop += f"; revision: {revisie[:240]}"
        return {
            "ok": True,
            "text": kop,                                   # het oordeel voorop — de leeswijzer
            "oordeel": oordeel,
            "zwakste_claim": zwak,
            "bevindingen": [{"label": "unsupported", "claim": c} for c in ongegrond],
            "ongegrond": ongegrond,                        # alias: de missie-critic leest deze lijst
            "tegenargument": tegen,
            "revisie": revisie,
        }

    def evidence_records(self, result: dict, *, role_id: str) -> list:
        """De toetsing is zelf een Kroniek-feit: een uitgevoerde review is 'bevestigd' (er ligt een
        gegrond oordeel); het oordeel zelf (holds / needs revision) staat in de meta. Zo ziet Lara
        welke rollen hun eigen werk tegenspreken en hoe vaak output moest worden bijgesteld."""
        if not isinstance(result, dict) or not result.get("ok"):
            return []
        return [{"role_id": role_id, "skill": self.name,
                 "query": (result.get("zwakste_claim") or result.get("text") or "")[:200],
                 "source": "tegenspraak", "status": "bevestigd", "result_ref": "",
                 "meta": {"oordeel": result.get("oordeel"),
                          "ongegrond": len(result.get("ongegrond") or [])}}]


# Antwoordbudget als geen aanroeper iets anders vraagt.
#
# Stond op 700, gekalibreerd op "toets één losse claim". De echte aanroep is een viervoudig
# JSON-oordeel (zwakste claim + ongegronde beweringen + tegenargument + revisie) over een deliverable
# van duizenden tekens, en die past er niet in: op productie brak het antwoord af op 1578 tekens en
# was de JSON onparseerbaar. De missie-critic loste dat voor zichzelf op met een eigen budget (#278);
# de losse aanroep door een rol bleef achter en kapte stil af — tot de eerlijke foutmelding uit #278
# het zichtbaar maakte. Eén getal, één betekenis: gelijkgetrokken.
_DEFAULT_MAX_TOKENS = 3000


def _extract(raw):
    if not raw:
        return None
    s = re.sub(r"```(?:json)?", "", str(raw)).strip()
    try:
        return json.loads(s[s.find("{"):s.rfind("}") + 1])
    except (ValueError, IndexError):
        return None
