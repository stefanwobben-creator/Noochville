"""Gedeelde, niet-interactieve inbox-acties — één gevalideerd pad voor CLI én cockpit.

De inbox is het geauthenticeerde lokale approval-oppervlak. Deze functies voeren een
beslissing uit langs exact dezelfde weg als de CLI: ze sluiten het inbox-item én trappen
de bijbehorende domein-actie aan (bibliotheek-curatie bij keywords). Géén directe store-
write buiten die gevalideerde methodes, géén Village/netwerk, géén stdin — zodat de cockpit
ze veilig via een knop kan aanroepen.

Interactieve of bus-afhankelijke acties (means_gap, escalation, content) horen hier NIET;
die houden hun eigen pad tot ze niet-interactief gemaakt zijn.
"""
from __future__ import annotations
import re
from datetime import date


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return s[:60] or "ref"


def add_reference(notes, claim: str, grounds: str,
                  *, source: str = "cockpit", tags=None) -> dict:
    """Capture-info-rail (Add Reference): leg een feit vast als kennis-kaart. Loopt via
    de curator-contract-poort (validate_card + finalize_card) en ingest_insights —
    Engels/atomair/compleet, geen LLM, geen Village.

    Sluit de spanning NIET: één spanning kan meerdere uitkomsten hebben (ook een project,
    een governance-voorstel, ...). Afsluiten is een aparte, bewuste stap (mark_done).
    Geeft {ok, card_id?}.
    """
    from nooch_village.curate import validate_card, finalize_card
    from nooch_village.ingest import ingest_insights

    claim = (claim or "").strip()
    grounds = (grounds or "").strip()
    if not claim or not grounds:
        return {"ok": False, "error": "claim en grounds zijn allebei verplicht"}

    raw = {"id": _slug(claim), "claim": claim, "grounds": grounds,
           "tags": tags or []}
    if not validate_card(raw):
        return {"ok": False, "error": "kaart haalt het contract niet (id/claim/grounds)"}

    card = finalize_card(raw, source=source, source_date=date.today().isoformat())
    res = ingest_insights(notes, [card])
    return {"ok": True, "card_id": card["id"], "added": res["added"]}


def route_to_project(projects, owner: str, scope: str) -> dict:
    """Add Project-rail: maak een project voor een rol (de uitkomst om na te streven).
    Puur gevalideerde store-write (ProjectLedger.create), geen Village/LLM. Het project
    landt in de ledger; een draaiend dorp pakt het op.

    Sluit de spanning NIET (zie add_reference): afsluiten is een aparte stap. Geeft {ok, pid?}.
    """
    owner = (owner or "").strip()
    scope = (scope or "").strip()
    if not owner or not scope:
        return {"ok": False, "error": "owner en scope zijn allebei verplicht"}
    pid = projects.create(owner, scope, "human")
    return {"ok": True, "pid": pid, "owner": owner}


def decide_keyword(inbox, library, iid: str, decision: str,
                   reason: str = "", by: str = "human") -> dict:
    """Menselijke keyword-beslissing: sluit het item en cureer het woord in de bibliotheek.

    decision == "approve" → bibliotheek 'approved'; "reject" → 'forbidden'.
    Spiegelt de inbox-CLI exact. Geeft {ok, word?, status?, error?}.
    """
    item = inbox.get(iid)
    if item is None:
        return {"ok": False, "error": "item niet gevonden"}
    if item.get("type") != "keyword":
        return {"ok": False, "error": f"item is geen keyword ({item.get('type')})"}
    if item.get("status") != "pending":
        return {"ok": False, "error": f"item is al {item.get('status')}"}

    word = (item.get("context", {}) or {}).get("word", item.get("subject"))
    if decision == "approve":
        inbox.resolve(iid, "approved", reason=reason)
        library.curate(word, "approved",
                       rationale=reason or "menselijke goedkeuring via cockpit", by=by)
        return {"ok": True, "word": word, "status": "approved"}
    if decision == "reject":
        inbox.resolve(iid, "rejected", reason=reason)
        library.curate(word, "forbidden",
                       rationale=reason or "menselijk besluit via cockpit", by=by)
        return {"ok": True, "word": word, "status": "forbidden"}
    return {"ok": False, "error": f"onbekend besluit '{decision}'"}


def defer_item(inbox, iid: str, reason: str = "") -> dict:
    """Stel een item uit (blijft geregistreerd). Werkt voor elk type (pure bookkeeping)."""
    item = inbox.get(iid)
    if item is None:
        return {"ok": False, "error": "item niet gevonden"}
    if item.get("status") != "pending":
        return {"ok": False, "error": f"item is al {item.get('status')}"}
    inbox.resolve(iid, "deferred", reason=reason)
    return {"ok": True, "status": "deferred"}


def mark_done(inbox, iid: str, reason: str = "") -> dict:
    """Nevermind/Done-pad: de spanning vergt geen systeemactie (al afgehandeld, of hoort
    hier niet thuis). Trekt het item in (withdrawn) — geen domein-actie."""
    item = inbox.get(iid)
    if item is None:
        return {"ok": False, "error": "item niet gevonden"}
    if item.get("status") != "pending":
        return {"ok": False, "error": f"item is al {item.get('status')}"}
    inbox.resolve(iid, "withdrawn", reason=reason or "geen actie nodig / afgehandeld")
    return {"ok": True, "status": "withdrawn"}


def confirm_item(inbox, iid: str, by_human: str = "mens") -> dict:
    """Bevestig met één klik een door een rol voorgestelde sluiting (propose_close)."""
    item = inbox.get(iid)
    if item is None:
        return {"ok": False, "error": "item niet gevonden"}
    if not item.get("proposed_resolution"):
        return {"ok": False, "error": "geen voorgestelde sluiting om te bevestigen"}
    if inbox.confirm_resolution(iid, by_human=by_human):
        return {"ok": True, "status": "approved"}
    return {"ok": False, "error": "kon niet bevestigen (al gesloten?)"}
