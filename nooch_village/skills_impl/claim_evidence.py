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

_VERIFY_PROMPT = (
    "Hieronder staat de tekst van een webpagina van (of over) het merk '{brand}'.\n"
    "Vraag 1: maakt het merk hierop de claim '{claim}' (of een duidelijke variant daarvan)?\n"
    "Vraag 2: zo ja, staat er ONDERBOUWING bij — een certificering, norm/standaard, labresultaat "
    "of concrete meetwaarde (dus niet enkel een marketing-bewering)?\n\n"
    "Antwoord UITSLUITEND met JSON, exact dit schema:\n"
    '{{"claim_aanwezig": true of false, "onderbouwd": true of false, '
    '"citaat": "een LETTERLIJK, aaneengesloten fragment uit de tekst (max 30 woorden) dat de claim '
    'of de onderbouwing bevat; lege string als er niets is"}}\n'
    "Verzin niets. Citeer alleen tekst die er echt staat. Geen uitleg buiten het JSON.\n\n"
    "Pagina:\n{text}"
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


class ClaimEvidenceSkill(Skill):
    name = "claim_evidence"
    cost = "credits"               # SerpAPI-zoek + pagina-fetches per merk
    side_effect_free = True        # leest/verifieert alleen; de EvidenceLedger-write doet de rol
    required_env = ("SERPAPI_API_KEY",)
    description = ("Verifieert per merk een claim (bv. afbreekbaarheid) tegen de merksites: zoekt via "
                   "SerpAPI, leest de pagina's, en legt gegrond bewijs vast (letterlijk citaat + bron-URL) "
                   "met status bevestigd/onduidelijk/leeg/fout. Fail-closed, geen verzonnen bewijs.")
    input_schema = ("brands: list[str] (verplicht — de merken om te controleren) · "
                    "claim: str (verplicht — de te verifiëren claim, bv. 'biodegradable' of 'afbreekbaar') · "
                    "optioneel: limit: int (pagina's per merk, default 3)")
    required_payload = ("brands", "claim")
    output_schema = ("ok: bool, rows: list[{brand, claim, status, evidence, source}], "
                     "counts: {status: int} | error")

    # ── De Kroniek-brug (fase 2): bewijsrijen → EvidenceLedger-records ────────────
    # De ledger kent drie eersteklas statussen. 'onduidelijk' (claim gevonden, geen onderbouwing) is
    # vanuit het BEWIJS-register een kennisgat: er is geen bevestigd bewijs → 'leeg'. Zo houdt harry_hemp's
    # waarheidslat stand: alleen echt onderbouwde claims tellen als 'bevestigd'.
    _LEDGER_STATUS = {"bevestigd": "bevestigd", "onduidelijk": "leeg", "leeg": "leeg", "fout": "fout"}

    def evidence_records(self, result: dict, *, role_id: str) -> list:
        if not isinstance(result, dict) or not result.get("ok"):
            return []
        out = []
        for row in result.get("rows", []):
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
        brands = [str(b).strip() for b in (payload.get("brands") or []) if str(b).strip()]
        claim = (payload.get("claim") or "").strip()
        try:
            limit = max(1, int(payload.get("limit", 3)))
        except (TypeError, ValueError):
            limit = 3
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
            rows.append(row)

        counts: dict = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        log.info("🔎 claim_evidence '%s' over %d merk(en): %s", claim, len(brands), counts)
        return {"ok": True, "rows": rows, "counts": counts}

    def _verify_brand(self, brand, claim, key, limit, web_read, reason) -> dict:
        """Eén merk: zoek → lees top-N → LLM-verificatie met grondings-poort. Eerste 'bevestigd' wint;
        anders houdt een gegronde 'onduidelijk' stand. Geen leesbare pagina → 'fout'."""
        base = {"brand": brand, "claim": claim, "status": "leeg", "evidence": "", "source": ""}
        try:
            results = web_read.serpapi_search(f"{brand} {claim}", key, num=max(limit, 5))
        except Exception as exc:
            log.info("claim_evidence: zoek faalde voor %s: %s", brand, exc)
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
