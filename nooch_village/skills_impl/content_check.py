"""content_check — de eindcheck van een publieke tekst: claim-poort plus copy-regels.

Twee lagen:
  1. De harde claim-poort (`publication_check.review_publication`), deterministisch: rode termen uit
     de claims-database in élke publicatiesoort, de beleidswoorden (plastic, leer) en ongegronde
     claim-kaartjes in de strikte soorten (sales_page, passport). Draait ALTIJD; de notes-store is
     alleen nodig om `claim_insight_ids` te toetsen.
  2. De modeltoets tegen de merk-copyregels (`context.copy_rules`): concrete adviezen op toon,
     framing en de vier checks.

Fail-closed, en dat is de reden dat deze skill in scope 56 opnieuw is gebouwd. Tot dan keurde hij
in de meeste invoervormen goed zonder iets te toetsen: geen tekst, geen store, geen model of geen
copy_rules gaf `gate_ok: True` + `no_data` met "tekst getoetst … geen problemen" — precies de valse
goedkeuring waar de claims-keten tegen bestaat (skill-review 12-09-2026, vier gevallen
gereproduceerd). De drie uitkomsten zijn nu:
  bevindingen               de poort of het model vond iets → records mét oordeel en citaat; als een
                            laag daarnaast NIET draaide, staat dat in `text` en `niet_getoetst`
  ok: False + error         niets gevonden, maar een laag draaide niet ("niet getoetst: geen model")
                            — een gedeeltelijke toets zonder bevinding is geen goedkeuring
  no_data + reason          élke laag draaide en vond niets: onderzocht, schoon
"""
from __future__ import annotations

import json
import re

from nooch_village.skills import Skill

_KINDS = ("blog", "sales_page", "passport")

# Engels, met een grounding-regel en een JSON-vorm die de parser hieronder leest. Het oude "antwoord
# exact: OK." kwam als deliverable-tekst "OK." op de wall — een antwoord-token is geen resultaat.
_PROMPT = (
    "You are the final editor of Nooch. Check the TEXT below against the brand copy rules.\n"
    "Name concretely and briefly where the text breaks a rule or could be sharper (tone, the four "
    "checks, framing, the reader). Base every issue only on the rules and the text below; if you "
    "cannot point to a rule, do not raise the issue. If the text complies, say so.\n\n"
    "Answer ONLY with JSON, exactly this schema:\n"
    '{{"compliant": true or false, "issues": ["one concrete, actionable issue", "..."]}}\n'
    "Empty issues when compliant. No explanation outside the JSON.\n\n"
    "Copy rules:\n{rules}\n\n"
    "TEXT:\n{text}\n\n"
    "{taal}"
)


class ContentCheckSkill(Skill):
    name = "content_check"
    cost = "free"  # kleine begrensde LLM-tokenkost wordt bewust niet gevlagd
    side_effect_free = True
    description = ("Final check of a public text before publication: the hard claim gate (red terms "
                   "from the claims database in any kind; policy words 'plastic'/'leer' and unverified "
                   "claim cards in sales_page/passport) plus a model review against the brand copy "
                   "rules. Fail-closed: a layer that could not run is reported as 'not checked', never "
                   "as approval.")
    input_schema = ("text: str (required — the text to check) · kind: str (optional, one of "
                    "'blog' | 'sales_page' | 'passport', default 'blog'; sales_page and passport are "
                    "strict) · claim_insight_ids: list[str] (optional — ids of knowledge cards the "
                    "text relies on; must be VERIFIED for strict kinds) · locale: str (optional — "
                    "language of the review) · ladder: str (optional — own model ladder)")
    output_schema = ("ok, gate_ok: bool, text, kind, forbidden_words[str], claim_issues[{insight_id, "
                     "reason}], suggestions: str|None, bevindingen[{term, oordeel, citaat}], "
                     "niet_getoetst[str] | no_data+reason (every layer ran, nothing found) | error")
    required_payload = ("text",)

    def validate_payload(self, payload: dict, context) -> list[str]:
        p = payload or {}
        uit = []
        if not str(p.get("text") or "").strip():
            uit.append("geef 'text' (de te toetsen tekst) mee")
        kind = p.get("kind")
        if kind not in (None, "") and str(kind) not in _KINDS:
            # Bij het PLANNEN al, niet pas live: tot scope 56 viel elke onbekende soort stil terug
            # op 'blog' — de lichtste variant, zonder de claim-kaartjes te toetsen.
            uit.append(f"onbekende kind '{kind}' — kies uit {', '.join(_KINDS)}")
        return uit

    def run(self, payload: dict, context) -> dict:
        from nooch_village.publication_check import review_publication, PublicationKind, STRICT_KINDS
        payload = payload or {}
        text = str(payload.get("text") or "")
        if not text.strip():
            return {"ok": False, "error": "geef 'text' (de te toetsen tekst) mee — zonder tekst is "
                                          "er niets getoetst"}
        rauw_kind = payload.get("kind") or "blog"
        try:
            kind = PublicationKind(str(rauw_kind))
        except ValueError:
            return {"ok": False, "error": f"onbekende kind '{rauw_kind}' — kies uit "
                                          f"{', '.join(_KINDS)}"}
        claim_ids = payload.get("claim_insight_ids") or []
        if isinstance(claim_ids, str):
            claim_ids = [claim_ids]
        claim_ids = [str(c) for c in claim_ids if str(c).strip()]

        store = getattr(context, "notes", None) if context is not None else None
        data_dir = getattr(context, "data_dir", None) if context is not None else None
        niet_getoetst: list[str] = []
        # De poort draait altijd; alleen de kaartjes-toets heeft de store nodig, en alleen in de
        # strikte soorten. Zonder store gaan de ids niet mee (anders levert de poort per id een
        # 'niet te toetsen'-issue op, wat hier als 'niet getoetst' hoort te lezen, niet als bevinding).
        ids_voor_poort = claim_ids if store is not None else []
        if claim_ids and kind in STRICT_KINDS and store is None:
            niet_getoetst.append(f"{len(claim_ids)} claim card(s) not verified: no notes store in context")
        report = review_publication(text, ids_voor_poort, kind, store, data_dir=data_dir)
        if not report.database_ok:
            niet_getoetst.append("claims database not readable: only the policy words were checked")

        rules = (getattr(context, "copy_rules", "") if context is not None else "") or ""
        issues, model_weg = self._llm_check(text, rules, payload.get("locale"),
                                            ladder=payload.get("ladder"))
        if model_weg:
            niet_getoetst.append(model_weg)
        suggestions = "\n".join(issues) if issues else None

        bevindingen = self._records(report, kind, issues)
        uit = {"ok": True, "gate_ok": report.ok, "kind": str(kind),
               "bevindingen": bevindingen,
               "forbidden_words": list(report.forbidden_words),
               "claim_issues": [{"insight_id": ci.insight_id, "reason": ci.reason}
                                for ci in report.claim_issues],
               "suggestions": suggestions, "niet_getoetst": niet_getoetst}
        gecheckt = self._gecheckt(kind, claim_ids, store is not None, rules, model_weg)
        if bevindingen:
            kop = (f"{len(report.forbidden_words)} forbidden term(s), {len(report.claim_issues)} "
                   f"claim-card issue(s), {len(issues or [])} copy-rule issue(s) in this {kind}"
                   + (" — gate BLOCKS publication" if not report.ok else " — gate passes"))
            if niet_getoetst:
                kop += "; not checked: " + "; ".join(niet_getoetst)
            uit["text"] = kop
            return uit
        if niet_getoetst:
            # Niets gevonden terwijl een laag niet draaide: dat is geen goedkeuring maar een
            # onvolledige toets. Open laten mét de reden — nooit 📭 "clean".
            uit["ok"] = False
            uit["error"] = "niet getoetst: " + "; ".join(niet_getoetst) + f" (checked: {gecheckt})"
            return uit
        # Schone tekst = een ANTWOORD, geen kennisgat: élke laag draaide en vond niets.
        uit["no_data"] = True
        uit["reason"] = (f"text checked as {kind} against {gecheckt}: no forbidden words, no "
                         f"claim-card issues, no copy-rule issues")
        return uit

    @staticmethod
    def _gecheckt(kind, claim_ids, met_store: bool, rules: str, model_weg: str) -> str:
        from nooch_village.publication_check import STRICT_KINDS
        lagen = ["the claims database (red terms)"]
        if kind in STRICT_KINDS:
            lagen.append("the policy words")
            if claim_ids and met_store:
                lagen.append(f"{len(claim_ids)} claim card(s)")
        if rules and not model_weg:
            lagen.append("the copy rules (model)")
        return ", ".join(lagen)

    @staticmethod
    def _records(report, kind, issues) -> list[dict]:
        """Elke bevinding als record met `term`, `oordeel` en `citaat`, zodat wall-note en verslag
        het oordeel tonen ("• duurzaam / sustainable — red — source A: … — “…”") en niet alleen een
        kale lijst woorden."""
        from nooch_village.publication_check import FORBIDDEN_IN_SALES
        uit = []
        per_term = {str(b.get("term") or ""): b for b in report.claim_findings}
        for w in report.forbidden_words:
            b = per_term.get(w)
            if b is not None:
                bron = str(b.get("bron") or "")
                gevonden = [str(g) for g in (b.get("gevonden") or []) if str(g).strip()]
                uit.append({"term": w,
                            "oordeel": "red — blocked" + (f" — source {bron}" if bron else "")
                                       + (f": {b['bron_detail']}" if b.get("bron_detail") else ""),
                            "citaat": (f"found '{gevonden[0]}'" if gevonden else "found")
                                      + (f" — {b['waarom']}" if b.get("waarom") else "")})
            elif w in FORBIDDEN_IN_SALES:
                uit.append({"term": w, "oordeel": f"blocked — policy word, not allowed in a {kind}",
                            "citaat": f"'{w}' occurs in the text (Nooch policy: no plastic, no leather)"})
            else:
                uit.append({"term": w, "oordeel": "blocked", "citaat": f"'{w}' occurs in the text"})
        for ci in report.claim_issues:
            uit.append({"term": f"claim card {ci.insight_id}", "oordeel": "blocked — claim not verified",
                        "citaat": ci.reason})
        for issue in issues or []:
            uit.append({"term": "copy rules", "oordeel": "advice", "citaat": str(issue)})
        return uit

    def _llm_check(self, text: str, rules: str, locale: str | None = None,
                   ladder: str | None = None) -> tuple[list[str] | None, str]:
        """(issues, reden-als-niet-gedraaid). Lege issues = het model vond niets; None + reden = de
        laag draaide niet (geen copy_rules, geen model, onleesbaar antwoord) — en dat verschil is
        het hele punt van deze skill."""
        from nooch_village.llm import reason
        from nooch_village.language import instruction
        if not rules:
            return None, "copy rules not checked: no copy_rules in context"
        out = reason(_PROMPT.format(rules=rules, text=text, taal=instruction(locale)),
                     call_site="skill_content_check", json_mode=True, max_tokens=800,
                     ladder=(ladder or "").strip() or None)
        if not out or not str(out).strip():
            return None, "copy rules not checked: no model available"
        return _parse_issues(str(out)), ""


def _parse_issues(raw: str) -> list[str]:
    """De issues uit het modelantwoord. JSON volgens het schema wint; een antwoord dat alleen 'OK'
    zegt is 'geen issues' (en géén suggestie-tekst); elk ander proza telt als één issue — liever een
    advies te veel dan een model-opmerking stil weggooien."""
    t = raw.strip()
    m = re.search(r"\{.*\}", t, flags=re.S)
    if m:
        try:
            data = json.loads(m.group(0))
        except ValueError:
            data = None
        if isinstance(data, dict):
            issues = [str(i).strip() for i in (data.get("issues") or []) if str(i).strip()]
            if data.get("compliant") and not issues:
                return []
            return issues
    if re.fullmatch(r"(ok|oké|okay|compliant)[.!]?", t, flags=re.I):
        return []
    return [t]
