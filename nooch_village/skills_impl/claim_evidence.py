"""claim_evidence — verifieer per merk een claim tegen de merksites zelf.

Punt 2 uit de dorps-checkup: "geen skill voor directe bewijsanalyse". Deze skill vult dat gat in de
autonome variant (merknaam → webzoek → pagina lezen → gegrond bewijs), maar fail-closed en gegrond,
zodat de autonomie geen verzonnen bewijs oplevert.

Per merk: SerpAPI-zoek op `<merk> <claim>` (échte URLs), de top-N pagina's lezen, en de LLM per pagina
laten bepalen of het merk de claim maakt én of er ONDERBOUWING bij staat (certificering, norm,
labresultaat). Kernslot: het teruggegeven citaat moet LETTERLIJK in de opgehaalde paginatekst
voorkomen — anders valt het af. Zo kan de LLM geen bewijs hallucineren.

Status per merk (spiegelt de Kroniek/EvidenceLedger):
  bevestigd    = claim gevonden mét onderbouwing (gegrond citaat)
  onduidelijk  = claim gevonden zónder onderbouwing (marketing zonder bewijs)
  leeg         = pagina's leesbaar, maar geen claim gevonden
  fout         = geen enkele pagina leesbaar (technisch mislukt) / geen key

Zuivere lezer: de skill schrijft ZELF niets weg (side-effect-free). De rol/dispatch-laag legt de
bewijsregels vast in de EvidenceLedger — dat is de brug naar de Kroniek (fase 2, interpreteren).

Config/content-scheiding: het CLAIMTYPE komt via de payload (het is projectkennis, geen code). De skill
hardcodeert geen enkel merk of claim.
"""
from __future__ import annotations

import json
import logging
import os
import re

from nooch_village.skills import Skill

log = logging.getLogger("village.skill.claim_evidence")

# Engels, zoals elke prompt sinds i18n-batch 2A; de JSON-sleutels blijven de interne (Nederlandse)
# namen, want `_verify_brand` leest ze — prompt en parser horen bij elkaar (test_i18n_prompt_grens).
_VERIFY_PROMPT = (
    "Below is the text of a web page of (or about) the brand '{brand}'.\n"
    "Question 1: does the brand make the claim '{claim}' (or a clear variant of it) on this page?\n"
    "Question 2: if so, is there SUBSTANTIATION next to it — a certification, a standard, a lab "
    "result or a concrete measured value (not merely a marketing statement)?\n\n"
    "Answer ONLY with JSON, exactly this schema:\n"
    '{{"claim_aanwezig": true or false, "onderbouwd": true or false, '
    '"citaat": "a LITERAL, contiguous fragment of the text (max 30 words) that contains the claim '
    'or the substantiation; empty string if there is none"}}\n'
    "Use only the material below; invent nothing. Quote only text that is really there. "
    "No explanation outside the JSON.\n\n"
    "Page:\n{text}"
)

_MIN_SNIPPET = 20        # een citaat korter dan dit is te generiek om als grond te tellen
_MIN_PAGE = 200          # minder tekst → pagina niet zinvol leesbaar


def _norm(s: str) -> str:
    """Whitespace-genormaliseerd en case-fold, voor de letterlijk-in-tekst-check."""
    return re.sub(r"\s+", " ", s or "").strip().casefold()


def _grounded(snippet: str, text: str) -> bool:
    """Grondings-poort: het citaat moet (genormaliseerd) letterlijk in de paginatekst staan én niet
    triviaal kort zijn. Zo dekt de skill de faalmodus van de autonome variant af: geen gehallucineerd bewijs."""
    s = _norm(snippet)
    return len(s) >= _MIN_SNIPPET and s in _norm(text)


def _parse_json(raw: str) -> dict | None:
    """Tolerante JSON-parse: strip eventuele code-fences, pak het eerste object. Faalt → None."""
    if not raw:
        return None
    t = raw.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*", "", t).strip().rstrip("`").strip()
    m = re.search(r"\{.*\}", t, flags=re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


# Bovengrens op pagina's per merk. Elke pagina is een SerpAPI-treffer (credits) plus een fetch plus
# een modelaanroep; `limit` had geen plafond, dus een planner die '20' invulde kocht twintig van elk.
MAX_LIMIT = 5
DEFAULT_LIMIT = 3

# Wat elke status betekent, in de woorden die een mens op de wall leest. `oordeel` draagt dit naast
# de kale status, zodat het verslag "• Veja (https://…) — confirmed: … — “citaat”" kan tonen.
_OORDEEL = {
    "bevestigd":   "confirmed — the claim is made with substantiation (certificate, standard, lab result)",
    "onduidelijk": "unclear — the claim is made, but without substantiation",
    "leeg":        "nothing found — pages readable, no such claim on them",
    "fout":        "failed — search or fetch failed, no page could be read",
}


class ClaimEvidenceSkill(Skill):
    name = "claim_evidence"
    cost = "credits"               # SerpAPI-zoek + pagina-fetches per merk
    side_effect_free = True        # leest/verifieert alleen; de EvidenceLedger-write doet de rol
    required_env = ("SERPAPI_API_KEY",)
    description = ("Verifies one claim per brand against the brand's own web pages: searches via "
                   "SerpAPI, reads the top pages and returns grounded evidence (a literal quote + the "
                   "source URL) with status bevestigd (claim + substantiation) / onduidelijk (claim "
                   "without substantiation) / leeg (no claim found) / fout (no page readable). "
                   "Fail-closed: no invented evidence, a quote must appear literally on the page.")
    input_schema = ("brands: list[str] (required — the brands to check; a single string is accepted) · "
                    "claim: str (required — the claim to verify, e.g. 'biodegradable' or 'plastic-free') · "
                    f"limit: int (optional — pages per brand, default {DEFAULT_LIMIT}, max {MAX_LIMIT})")
    required_payload = ("brands", "claim")
    output_schema = ("ok: bool, text, rows: list[{brand, claim, status, oordeel, evidence, citaat, "
                     "source, url}], counts: {status: int} | no_data+reason (no brand had the claim) "
                     "| error (no key, or no brand could be checked)")

    # ── De Kroniek-brug (fase 2): bewijsrijen → EvidenceLedger-records ────────────
    # De ledger kent drie eersteklas statussen. 'onduidelijk' (claim gevonden, geen onderbouwing) is
    # vanuit het BEWIJS-register een kennisgat: er is geen bevestigd bewijs → 'leeg'. Zo houdt harry_hemp's
    # waarheidslat stand: alleen echt onderbouwde claims tellen als 'bevestigd'.
    _LEDGER_STATUS = {"bevestigd": "bevestigd", "onduidelijk": "leeg", "leeg": "leeg", "fout": "fout"}

    def evidence_records(self, result: dict, *, role_id: str) -> list:
        # Op de RIJEN, niet op `ok`: een run waarin elk merk 'fout' gaf is `ok: False` (het item blijft
        # open), maar die fouten zijn eersteklas Kroniek-feiten — daarop leert de ladder.
        if not isinstance(result, dict):
            return []
        out = []
        for row in result.get("rows") or []:
            status = self._LEDGER_STATUS.get(row.get("status"))
            if status is None:
                continue
            query = " — ".join(p for p in (str(row.get("brand", "")).strip(),
                                           str(row.get("claim", "")).strip()) if p)
            out.append({
                "role_id": role_id, "skill": self.name, "query": query or "(onbekend merk)",
                "source": row.get("source") or "web", "status": status,
                "result_ref": str(row.get("evidence") or "")[:200],
            })
        return out

    def run(self, payload: dict, context=None) -> dict:
        payload = payload or {}
        brands = payload.get("brands") or []
        if isinstance(brands, str):
            # Eén merk als string: itereren over de tekens gaf "V biodegradable", "e biodegradable", …
            # — vier zoekopdrachten, vier credits, vier 'fout'-rijen (skill-review 12-09-2026).
            brands = [brands]
        brands = [str(b).strip() for b in brands if str(b).strip()]
        claim = (payload.get("claim") or "").strip()
        try:
            limit = min(MAX_LIMIT, max(1, int(payload.get("limit", DEFAULT_LIMIT))))
        except (TypeError, ValueError):
            limit = DEFAULT_LIMIT
        if not brands or not claim:
            return {"ok": False, "error": "geef brands (niet-leeg) en een claim op"}

        key = ((getattr(context, "settings", {}) or {}).get("SERPAPI_API_KEY")
               or os.getenv("SERPAPI_API_KEY"))
        if not key:
            return {"ok": False, "error": "SERPAPI_API_KEY ontbreekt — skill faalt bewust closed"}

        from nooch_village import web_read
        from nooch_village.llm import reason

        rows = []
        for brand in brands:
            row = self._verify_brand(brand, claim, key, limit, web_read, reason)
            rows.append(self._verrijk(row))

        counts: dict = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        log.info("🔎 claim_evidence '%s' over %d merk(en): %s", claim, len(brands), counts)
        uit = {"ok": True, "rows": rows, "counts": counts, "text": self._kop(claim, rows, counts)}
        # De drie uitkomsten van de brief. Tot scope 56 was een run waarin ELK merk 'fout' gaf
        # `ok: True` met een gevulde lijst → het item werd afgevinkt met een mislukking als
        # deliverable. Alle merken fout = de bron faalde (open laten, foutreden op de wall); geen
        # enkel merk met de claim (leeg/fout gemengd) = onderzocht, niets gevonden.
        if counts.get("fout", 0) == len(rows):
            return {**uit, "ok": False,
                    "error": (f"no brand could be checked for '{claim}': search or page fetch failed "
                              f"for all {len(rows)} brand(s) (SerpAPI down, key rejected or no "
                              f"readable page)")}
        if not (counts.get("bevestigd") or counts.get("onduidelijk")):
            fout = counts.get("fout", 0)
            return {**uit, "no_data": True,
                    "reason": (f"none of the {len(rows)} brand(s) makes the claim '{claim}' on the "
                               f"pages read" + (f" ({fout} brand(s) could not be checked: search or "
                                                f"fetch failed)" if fout else ""))}
        return uit

    @staticmethod
    def _verrijk(row: dict) -> dict:
        """Additief: `url` (= source), `citaat` (= evidence) en `oordeel` (= de status in woorden),
        zodat het verslag "• Veja (https://…) — confirmed — “…”" leest en niet alleen "• Veja"
        (project_verslag kent `evidence`/`source` niet als adres/strekking-veld; skill-review
        12-09-2026). De oude velden blijven staan voor `evidence_records`."""
        status = str(row.get("status") or "")
        return {**row, "url": row.get("source") or "", "citaat": row.get("evidence") or "",
                "oordeel": _OORDEEL.get(status, status)}

    @staticmethod
    def _kop(claim: str, rows: list[dict], counts: dict) -> str:
        """De leeswijzer boven de rijen: de kerncijfers in één zin."""
        delen = [f"{n} {status}" for status, n in counts.items()]
        bevestigd = [r["brand"] for r in rows if r.get("status") == "bevestigd"]
        kop = f"'{claim}' checked for {len(rows)} brand(s): " + ", ".join(delen)
        if bevestigd:
            kop += " — substantiated at " + ", ".join(bevestigd[:4])
        return kop

    def _verify_brand(self, brand, claim, key, limit, web_read, reason) -> dict:
        """Eén merk: zoek → lees top-N → LLM-verificatie met grondings-poort. Eerste 'bevestigd' wint;
        anders houdt een gegronde 'onduidelijk' stand. Geen leesbare pagina → 'fout'."""
        base = {"brand": brand, "claim": claim, "status": "leeg", "evidence": "", "source": ""}
        try:
            results = web_read.serpapi_search(f"{brand} {claim}", key, num=max(limit, 5))
        except Exception as exc:
            from nooch_village.sleutelmasker import masker
            log.info("claim_evidence: zoek faalde voor %s: %s", brand, masker(exc))
            return {**base, "status": "fout"}

        any_readable = False
        best_onduidelijk = None
        for res in results[:limit]:
            link = res.get("link") or ""
            text = web_read.fetch_text(link)
            if len(text) < _MIN_PAGE:
                continue
            any_readable = True
            raw = reason(_VERIFY_PROMPT.format(brand=brand, claim=claim, text=text[:6000]),
                         json_mode=True, call_site="skill_claim_evidence")
            data = _parse_json(raw)
            if not data or not data.get("claim_aanwezig"):
                continue
            snippet = str(data.get("citaat") or "")
            if not _grounded(snippet, text):          # citaat niet letterlijk terug te vinden → weg
                continue
            if data.get("onderbouwd"):
                return {**base, "status": "bevestigd", "evidence": snippet, "source": link}
            if best_onduidelijk is None:              # claim zonder onderbouwing: onthoud, blijf zoeken
                best_onduidelijk = {**base, "status": "onduidelijk", "evidence": snippet, "source": link}

        if best_onduidelijk is not None:
            return best_onduidelijk
        return {**base, "status": "leeg" if any_readable else "fout"}
