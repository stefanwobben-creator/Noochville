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


def remove_note(notes, note_id: str) -> dict:
    """Verwijder een kennis-kaartje (NotesStore.remove ruimt ook inkomende links op).
    Voor het bewust weggooien van een niet-relevant kaartje. Geeft {ok}."""
    if not note_id:
        return {"ok": False, "error": "geen kaart-id"}
    ok = notes.remove(note_id)
    return {"ok": ok, "removed": note_id} if ok else {"ok": False, "error": "kaart niet gevonden"}


def route_to_governance(records, role_id: str, skill: str, rationale: str,
                        *, tension: str = "", gap_key: str = "") -> dict:
    """Bring to Governance-rail: ken een rol een (bestaande) skill toe via het volledige
    gevalideerde pad — Gate.check (G0-G4) + Secretary._adopt. Synchroon, geen Village/LLM:
    een skill toekennen aan een bestaande rol passeert de poort (adopt-by-default).

    Sluit de spanning NIET (multi-uitkomst-model). Geeft {ok, status, reason?}:
      adopted   — skill toegevoegd aan het rol-record
      invalid   — G0/structureel mis (rol bestaat niet, rationale te kort, ...)
      escalated — G1-G4 vraagt menselijk oordeel (niet auto-toegepast)
    """
    from nooch_village.event_bus import EventBus
    from nooch_village.governance import Gate, Secretary
    from nooch_village.models import Proposal, GovernanceChange, ChangeKind

    role_id = (role_id or "").strip()
    skill = (skill or "").strip()
    rationale = (rationale or "").strip()
    if not role_id or not skill:
        return {"ok": False, "status": "invalid", "reason": "rol en skill zijn verplicht"}
    if len(rationale) < 10:
        return {"ok": False, "status": "invalid",
                "reason": "rationale te kort (minimaal 10 tekens)"}
    if records.get(role_id) is None:
        return {"ok": False, "status": "invalid", "reason": f"rol '{role_id}' bestaat niet"}

    proposal = Proposal(
        proposer_role="human-cockpit",
        change=GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=role_id,
                                add_skills=[skill]),
        tension=tension or f"cockpit governance: skill '{skill}' voor '{role_id}'",
        trigger_example=(f"means_gap:{gap_key}" if gap_key else f"cockpit:{role_id}:{skill}"),
        rationale=rationale, source="sensed",
    )
    passed, gate_name, reason = Gate().check(proposal, records, None)
    if not passed:
        status = "invalid" if gate_name == "G0" else "escalated"
        return {"ok": False, "status": status, "gate": gate_name, "reason": reason}

    Secretary(records, EventBus(name="cockpit"))._adopt(proposal)
    return {"ok": True, "status": "adopted", "role_id": role_id, "skill": skill}


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


def override_library_term(library, word: str, decision: str,
                          reason: str = "", by: str = "human") -> dict:
    """Menselijke override van een bibliotheekterm (de escalated-berg afromen vanuit het
    dashboard). approve → 'approved', reject → 'forbidden'. Schrijft via de domein-methode
    Library.curate (niet rechtstreeks in de store). Geeft {ok, word?, status?, error?}.

    Dit is een legitieme menselijke curatie op het geauthenticeerde lokale oppervlak: de
    mens neemt het oordeel dat de Librarian naar hem escaleerde."""
    word = (word or "").strip()
    if not word:
        return {"ok": False, "error": "geen woord"}
    if library.status(word) is None:
        return {"ok": False, "error": f"'{word}' staat niet in de bibliotheek"}
    status = {"approve": "approved", "reject": "forbidden"}.get(decision)
    if status is None:
        return {"ok": False, "error": f"onbekend besluit '{decision}'"}
    library.curate(word, status,
                   rationale=reason or "menselijke override via cockpit", by=by)
    return {"ok": True, "word": word, "status": status}


def decide_opportunity(inbox, projects, iid: str, decision: str, reason: str = "") -> dict:
    """Mens beslist over een door een rol gesensde kans. approve → wordt pas dán een project
    (mens-poort hersteld). reject → genegeerd. De optionele reden wordt bewaard én voedt de
    leerlus: de rol leest 'm terug en herhaalt/kalibreert. Geeft {ok, status?, title?, error?}."""
    item = inbox.get(iid)
    if item is None or item.get("type") != "opportunity":
        return {"ok": False, "error": "kans niet gevonden"}
    if item.get("status") != "pending":
        return {"ok": False, "error": f"kans is al {item.get('status')}"}
    ctx = item.get("context") or {}
    title = ctx.get("title") or item.get("subject")
    if decision == "approve":
        if projects is not None and ctx.get("kind", "project") == "project":
            projects.create(ctx.get("by") or "village", title, "human",
                            hypothesis=ctx.get("wat", "") or ctx.get("waarom", ""),
                            business_case=ctx.get("business_case"))
        inbox.resolve(iid, "approved", reason=(reason or "kans goedgekeurd → project"))
        return {"ok": True, "status": "approved", "title": title,
                "owner": ctx.get("by", ""), "opp_kind": ctx.get("kind", "project")}
    if decision in ("reject", "dismiss", "negeer"):
        inbox.resolve(iid, "rejected", reason=(reason or "kans genegeerd"))
        return {"ok": True, "status": "rejected", "title": title}
    return {"ok": False, "error": f"onbekend besluit '{decision}'"}


def decide_target(library, projects, word: str, decision: str, reason: str = "") -> dict:
    """Mens beslist over een doelwit-woord (waar we op willen ranken). 'project' → maak een
    content-project (we gaan hier content voor schrijven, verschijnt op het projectbord).
    'drop' → laat vallen met reden (woord → forbidden). Zelfde ja/nee-met-reden-flow als kansen."""
    word = (word or "").strip()
    if not word:
        return {"ok": False, "error": "geen woord"}
    if library.status(word) is None:
        return {"ok": False, "error": f"'{word}' staat niet in de bibliotheek"}
    if decision == "project":
        scope = f"Content schrijven gericht op '{word}'"
        if projects is not None and scope not in projects.open_scopes():
            projects.create("librarian", scope, "human",
                            hypothesis=f"Door content voor '{word}' te maken kunnen mensen die "
                                       f"hierop zoeken ons vinden en schoenen kopen.")
        return {"ok": True, "pid": "x", "owner": "librarian"}
    if decision in ("drop", "reject", "negeer"):
        library.curate(word, "forbidden",
                       rationale=reason or "doelwit laten vallen (mens)", by="human")
        return {"ok": True, "status": "forbidden", "word": word}
    return {"ok": False, "error": f"onbekend besluit '{decision}'"}


def set_word_function(library, word: str, function: str, by: str = "human") -> dict:
    """Menselijke override van de functie van een woord: 'volg' (seed) of 'doelwit' (rank).
    De heuristiek classificeert automatisch; dit corrigeert uitzonderingen vanuit de cockpit.
    Schrijft via Library.set_function (domein-methode). Geeft {ok, word?, function?, error?}."""
    word = (word or "").strip()
    if not word:
        return {"ok": False, "error": "geen woord"}
    if function not in ("volg", "doelwit"):
        return {"ok": False, "error": f"onbekende functie '{function}'"}
    if library.set_function(word, function) is None:
        return {"ok": False, "error": f"'{word}' staat niet in de bibliotheek"}
    return {"ok": True, "word": word, "function": function}


def decide_competitor_candidate(brands, brand: str, decision: str) -> dict:
    """Menselijk oordeel over een gespotte concurrent (ruizige ontdekking → mens beslist).
    confirm → vanaf nu meegenomen in de monitoring; reject → genegeerd (komt niet terug).
    Schrijft via de CompetitorBrands-store. Geeft {ok, brand?, brand_status?, error?}."""
    brand = (brand or "").strip()
    if not brand:
        return {"ok": False, "error": "geen merk"}
    if decision == "confirm":
        ok = brands.confirm(brand)
        return {"ok": ok, "brand": brand, "brand_status": "gemonitord"} if ok \
            else {"ok": False, "error": "kon niet bevestigen"}
    if decision == "reject":
        ok = brands.reject(brand)
        return {"ok": ok, "brand": brand, "brand_status": "genegeerd"} if ok \
            else {"ok": False, "error": "kon niet negeren"}
    return {"ok": False, "error": f"onbekend besluit '{decision}'"}


def decide_link_target(targets, link: str, decision: str) -> dict:
    """Menselijk oordeel over een linkbuilding-doelwit (gids/lijstje).
    pursue → ga je pitchen; ignore → niks voor Nooch. Via de LinkTargets-store.
    Geeft {ok, link?, link_status?, error?}."""
    link = (link or "").strip()
    if not link:
        return {"ok": False, "error": "geen link"}
    if decision == "pursue":
        ok = targets.pursue(link)
        return {"ok": ok, "link": link, "link_status": "te pitchen"} if ok \
            else {"ok": False, "error": "kon niet markeren"}
    if decision == "ignore":
        ok = targets.ignore(link)
        return {"ok": ok, "link": link, "link_status": "genegeerd"} if ok \
            else {"ok": False, "error": "kon niet negeren"}
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
    """Nevermind-pad: de spanning vergt geen actie (hoort hier niet thuis, of is elders
    al opgelost). Trekt het item in (withdrawn). Voor 'wél afgehandeld via uitkomsten':
    zie resolve_tension."""
    item = inbox.get(iid)
    if item is None:
        return {"ok": False, "error": "item niet gevonden"}
    if item.get("status") != "pending":
        return {"ok": False, "error": f"item is al {item.get('status')}"}
    inbox.resolve(iid, "withdrawn", reason=reason or "niets nodig / hoort hier niet")
    return {"ok": True, "status": "withdrawn"}


def resolve_tension(inbox, iid: str, reason: str = "") -> dict:
    """Klaar-pad: de spanning is afgehandeld via de uitkomsten die je produceerde
    (project, reference, governance, ...). Sluit als 'resolved' — een positieve afronding,
    niet hetzelfde als withdrawn (niets nodig)."""
    item = inbox.get(iid)
    if item is None:
        return {"ok": False, "error": "item niet gevonden"}
    if item.get("status") != "pending":
        return {"ok": False, "error": f"item is al {item.get('status')}"}
    inbox.resolve(iid, "resolved", reason=reason or "afgehandeld via uitkomsten")
    return {"ok": True, "status": "resolved"}


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
