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


def curate_library_term(library, word: str, status: str,
                        reason: str = "", by: str = "human") -> dict:
    """Menselijke curatie van een bibliotheekterm vanuit het woordenschat-scherm:
    'approved' (heractiveren), 'avoid' (pauzeren: blijft referentie in de ontologie, telt
    niet meer als actieve zoekterm) of 'forbidden' (verbieden, met reden). Schrijft via de
    domein-methode Library.curate (nooit rechtstreeks in de json) en geeft de bestaande
    evidence door zodat verrijking (volume/concurrentie) een pauze overleeft.
    Geeft {ok, word?, status?, error?}."""
    word = (word or "").strip()
    if not word:
        return {"ok": False, "error": "geen woord"}
    entry = library.status(word)
    if entry is None:
        return {"ok": False, "error": f"'{word}' staat niet in de bibliotheek"}
    if status not in ("approved", "avoid", "forbidden"):
        return {"ok": False, "error": f"onbekende status '{status}'"}
    library.curate(word, status,
                   rationale=(reason or "").strip() or "menselijke curatie via cockpit",
                   evidence=entry.get("evidence"), by=by)
    return {"ok": True, "word": word, "status": status}


def ask_role(inbox, iid: str, question: str, *, by_role: str = "") -> dict:
    """Tactical-informatie (vragen): de mens stelt een rol een vraag over een item
    ('ik snap dit voorstel niet'). GEEN LLM hier — de vraag wordt geparkeerd en in de
    puls gebundeld beantwoord (zie answer_pending_questions). Item blijft open met label
    'wachten op antwoord'. Geeft {ok, status: 'waiting'}."""
    item = inbox.get(iid)
    if item is None:
        return {"ok": False, "error": "item niet gevonden"}
    if item.get("status") != "pending":
        return {"ok": False, "error": f"item is al {item.get('status')}"}
    role = by_role or (item.get("context") or {}).get("by", "")
    if not inbox.add_question(iid, question, by_role=role):
        return {"ok": False, "error": "vraag is leeg"}
    return {"ok": True, "status": "waiting", "by": role}


_ANS_RE = re.compile(r"ANTWOORD\s*(\d+)\s*:\s*(.+?)(?=\n\s*ANTWOORD\s*\d+\s*:|\Z)",
                     re.IGNORECASE | re.DOTALL)


def answer_pending_questions(inbox, *, records=None, llm_reason=None, limit: int = 20) -> dict:
    """Batch-beantwoording: bundel ALLE openstaande vragen en laat de LLM ze in één call
    beantwoorden, elk als de betreffende rol, in gewone taal (burger-frame, geen jargon).
    Schrijft de antwoorden terug op de items. Fail-closed: zonder LLM of zonder antwoord
    blijven de vragen 'wachten op antwoord'. Geeft {ok, answered, pending}.

    Dit is het bovenliggende principe: geen realtime call per vraag, maar één gebundelde
    puls-call — zoals de rest van het dorp werkt."""
    if llm_reason is None:
        import functools
        from nooch_village.llm import reason as _reason
        llm_reason = functools.partial(_reason, call_site="inbox_answer_questions")
    qs = inbox.pending_questions()[:limit]
    if not qs:
        return {"ok": True, "answered": 0, "pending": 0}

    def _purpose(role_id: str) -> str:
        if not role_id or records is None:
            return ""
        rec = records.get(role_id)
        if rec is None:
            return ""
        d = getattr(rec, "definition", None)
        return getattr(d, "purpose", "") if d else ""

    blok = []
    for n, q in enumerate(qs, 1):
        ctx = q.get("context") or {}
        rol = q.get("by") or "het dorp"
        purpose = _purpose(q.get("by"))
        onderwerp = ctx.get("title") or q.get("subject") or ""
        wat = ctx.get("wat", "")
        blok.append(
            f"VRAAG {n} (gericht aan rol '{rol}'"
            f"{f', wiens doel is: {purpose}' if purpose else ''}):\n"
            f"  Onderwerp: {onderwerp}\n"
            f"  Toelichting: {wat}\n"
            f"  De vraag van de mens: {q.get('question')}")
    prompt = (
        "Je bent een inwoner van NoochVille (duurzaam, vegan schoenenmerk Nooch.earth). "
        "De mens (oprichter) stelt per onderstaande spanning een vraag aan een rol. "
        "Beantwoord ELKE vraag als díe rol, in gewone taal die een 12-jarige begrijpt: "
        "concreet, eerlijk, kort (2 tot 4 zinnen). Geen jargon, geen Engelse vakwoorden, "
        "geen marketingtaal. Spreek over 'mensen' en 'burgers', niet over 'consumenten' of "
        "'transacties'. Als je iets niet zeker weet, zeg dat eerlijk.\n\n"
        + "\n\n".join(blok)
        + "\n\nAntwoord EXACT in dit formaat, één regel per antwoord, niets erbuiten:\n"
        + "\n".join(f"ANTWOORD {n}: <je antwoord>" for n in range(1, len(qs) + 1)))

    out = llm_reason(prompt)
    if not out:
        return {"ok": True, "answered": 0, "pending": len(qs)}
    answers = {int(m.group(1)): m.group(2).strip() for m in _ANS_RE.finditer(out)}
    answered = 0
    for n, q in enumerate(qs, 1):
        ans = answers.get(n)
        if ans and inbox.answer_question(q["iid"], q["idx"], ans):
            answered += 1
    return {"ok": True, "answered": answered, "pending": len(qs) - answered}


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


# ── De goedkeuringsrij vanuit het cockpit ────────────────────────────────────────────────────────
#
# ÉÉN PAD, TWEE INGANGEN. `_approve_verband` stond in `inbox/__main__.py` en was daarmee alleen voor
# de CLI bereikbaar. Hij staat nu hier, waar deze module voor bedoeld is ("één gevalideerd pad voor
# CLI én cockpit"), en de CLI roept dezelfde functie aan. Twee kopieën van een beslissing lopen na
# één wijziging uit de pas, en dan keurt het ene oppervlak iets anders goed dan het andere.

def decide_verband(inbox, notes, iid: str, decision: str, *, reason: str = "") -> dict:
    """Menselijk besluit op een verband-voorstel (3c): sluit het item, en bij 'approved' schrijft het
    ook het touwtje tussen de twee kaartjes.

    Het item gaat ALTIJD dicht, ook als de link niet gelegd kon worden (een kaartje verdwenen). Zou
    het openblijven, dan komt hetzelfde onbeslisbare voorstel morgen terug en groeit de rij die we
    juist leeghalen. `link_gelegd` zegt wat er echt gebeurd is."""
    item = next((i for i in inbox.all() if i.get("id") == iid), None)
    if item is None:
        return {"ok": False, "error": f"onbekend item: {iid}"}
    if item.get("type") != "verband":
        return {"ok": False, "error": f"item is geen verband ({item.get('type')})"}
    if decision not in ("approved", "rejected", "deferred"):
        return {"ok": False, "error": f"ongeldig besluit: {decision}"}
    if not inbox.resolve(iid, decision, reason=reason):
        return {"ok": False, "error": "item bestond niet meer of was al gesloten"}
    if decision != "approved":
        return {"ok": True, "link_gelegd": False}
    ctx = item.get("context") or {}
    a, b = ctx.get("kaart_a_id"), ctx.get("kaart_b_id")
    gelegd = bool(a and b and notes is not None and notes.link(a, b) is not None)
    return {"ok": True, "link_gelegd": gelegd}


def decide_runner_activatie(inbox, records, iid: str, decision: str,
                            *, reason: str = "") -> dict:
    """Menselijk besluit op een runner-activatie: mag deze rol een eigen thread krijgen?

    Zelfde vorm als `decide_verband`: valideer, sluit het item, en voer bij 'approved' het ENE ding
    uit dat de goedkeuring betekent — hier het wegnemen van `activatie_vereist`, waarna
    `heeft_runner` weer gewoon antwoordt en de Reconciler de rol bij de volgende bouw materialiseert.

    WAT EEN NEE NIET DOET: het haalt de skills NIET uit het DNA. De grant kwam via het domein en is
    een governance-feit; dit besluit gaat alleen over draaien. Wie het gereedschap ook wil weghalen
    gebruikt `afslanken.skill_intrekken` — dat zet de intrek-guard, en de seed respecteert die.

    Het item gaat ALTIJD dicht, ook als het record intussen verdwenen is. Zou het openblijven, dan
    komt dezelfde onbeslisbare vraag morgen terug en groeit de rij die we juist leeghalen.
    `poort_weg` zegt wat er echt gebeurd is."""
    item = next((i for i in inbox.all() if i.get("id") == iid), None)
    if item is None:
        return {"ok": False, "error": f"onbekend item: {iid}"}
    if item.get("type") != "runner_activatie":
        return {"ok": False, "error": f"item is geen runner_activatie ({item.get('type')})"}
    if decision not in ("approved", "rejected", "deferred"):
        return {"ok": False, "error": f"ongeldig besluit: {decision}"}
    if not inbox.resolve(iid, decision, reason=reason):
        return {"ok": False, "error": "item bestond niet meer of was al gesloten"}
    if decision != "approved":
        return {"ok": True, "poort_weg": False}
    rid = (item.get("context") or {}).get("role_id") or item.get("subject")
    rec = records.get(rid) if records is not None else None
    if rec is None or not getattr(rec, "activatie_vereist", False):
        return {"ok": True, "poort_weg": False, "role_id": rid}
    rec.activatie_vereist = False
    rec.activatie_reden = None
    records.put(rec)
    return {"ok": True, "poort_weg": True, "role_id": rid}


def weiger_of_stel_uit(inbox, iid: str, decision: str, *, reason: str = "") -> dict:
    """Nee of later, op WELK type dan ook.

    DIT IS DE VEILIGE HELFT, en daarom staat hij bewust los van elk type. Een weigering schept
    niets: ze sluit of verplaatst een item en laat de wereld verder met rust. Precies daarom mag het
    cockpit dit altijd, ook bij een activatie die het niet mag goedkeuren.

    Zou dit per type geregeld zijn, dan bestaat er ooit een type waarop je niet eens nee kunt zeggen,
    en dan groeit de rij weer dicht — wat de reden was dat er 78 items zeventig dagen bleven staan."""
    if decision not in ("rejected", "deferred"):
        return {"ok": False, "error": f"alleen weigeren of uitstellen hier, niet: {decision}"}
    if not inbox.resolve(iid, decision, reason=reason):
        return {"ok": False, "error": "onbekend item, of het was al gesloten"}
    return {"ok": True}
