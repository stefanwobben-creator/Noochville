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


def _route_kans_to_governance(records, owner: str, title: str, wat: str, waarom: str,
                              business_case, *, by: str = "", examples_block: str = "",
                              llm_reason=None) -> dict:
    """Los een kans op in governance: nieuwe rol (owner == '__new__') of een bestaande rol
    uitbreiden met een accountability. De accountability wordt Holacracy-correct geformuleerd
    (gegrond met echte voorbeelden). Via de sync-poort Gate.check + Secretary._adopt op de
    on-disk records (geen Village/bus). Geeft {status: adopted|escalated|invalid, reason}."""
    import re as _re
    from nooch_village.event_bus import EventBus
    from nooch_village.governance import Gate, Secretary
    from nooch_village.models import Proposal, GovernanceChange, ChangeKind
    owner = (owner or "").strip()
    # Formuleer de accountability volgens de Holacracy-regels (fail-closed → titel).
    acc = formulate_accountability(title, wat, examples_block=examples_block, llm_reason=llm_reason)
    if owner in ("", "__new__"):
        r_id = _re.sub(r"\W+", "_", title.lower())[:40].strip("_") or "nieuwe_rol"
        change = GovernanceChange(kind=ChangeKind.ADD_ROLE, role_id=r_id,
                                  purpose=(wat or title)[:140], new_role_parent="noochville",
                                  add_accountabilities=[acc])
    else:
        change = GovernanceChange(kind=ChangeKind.AMEND_ROLE, role_id=owner,
                                  add_accountabilities=[acc])
    proposal = Proposal(
        proposer_role=by or "founder", change=change, tension=f"kans: {title}"[:200],
        # 'structureel' + 'mens besluit' = legitieme herhalingsgrond: jij beslist via triage.
        trigger_example=f"structureel besluit via triage door de mens: {title[:60]}",
        rationale=wat or waarom or "Onderbouwde kans, mens kiest governance.",
        hypothesis=waarom, business_case=business_case, source="sensed")
    passed, gate, reason_g = Gate().check(proposal, records, None)
    if passed:
        Secretary(records, EventBus(name="triage"))._adopt(proposal)
        return {"status": "adopted", "reason": ""}
    return {"status": "escalated", "reason": f"{gate}: {reason_g}"}


def decide_opportunity(inbox, iid: str, decision: str, *, reason: str = "",
                       destination: str = "project", owner: str = "",
                       remember_constraint: bool = False, scope_override: str = "",
                       info: str = "", project_status: str = "queued", examples_block: str = "",
                       projects=None, notes=None, constraints=None, records=None) -> dict:
    """Triage van een kans (mens-poort). approve → kies bestemming: 'project' (voor `owner`,
    op het projectbord) of 'knowledge' (kennis-kaart). reject → genegeerd; bij remember_constraint
    wordt de reden een vaste huis-regel die de reflex voortaan respecteert (zo voedt jouw oordeel
    het dorp). De reden wordt altijd bewaard (leerlus). Geeft {ok, status?, ...}."""
    item = inbox.get(iid)
    if item is None or item.get("type") != "opportunity":
        return {"ok": False, "error": "kans niet gevonden"}
    if item.get("status") != "pending":
        return {"ok": False, "error": f"kans is al {item.get('status')}"}
    ctx = item.get("context") or {}
    title = ctx.get("title") or item.get("subject")
    wat = ctx.get("wat", "") or ctx.get("waarom", "")

    # 'done' en 'reject' SLUITEN het item; 'add' (project/kennis/governance) maakt een uitkomst
    # maar laat het item OPEN, zodat je meerdere uitkomsten op één kans kunt stapelen.
    if decision == "done":
        # Veiligheid: sluit niet af terwijl er nog een vraag openstaat — dan zou je het
        # antwoord (dat in de volgende puls komt) mislopen. Wacht tot 'm beantwoord is.
        dlg = ctx.get("dialogue") or []
        if any(not d.get("answered") for d in dlg):
            return {"ok": False, "status": "blocked_question",
                    "error": "Er staat nog een vraag open — het antwoord komt in de volgende "
                             "puls. Wacht daarop voor je afrondt (anders mis je het antwoord)."}
        inbox.resolve(iid, "approved", reason=(reason or "afgerond"))
        return {"ok": True, "status": "done", "title": title}
    if decision in ("reject", "dismiss", "negeer"):
        learned = False
        if remember_constraint and reason and constraints is not None:
            learned = constraints.add(reason, by="human", source=f"triage: {title[:40]}")
        inbox.resolve(iid, "rejected", reason=(reason or "kans genegeerd"))
        return {"ok": True, "status": "rejected", "title": title, "constraint_learned": learned}

    # decision == "add": maak een uitkomst, item blijft open.
    if destination == "governance" and records is not None:
        res = _route_kans_to_governance(records, owner, title, wat, ctx.get("waarom", ""),
                                        ctx.get("business_case"), by=ctx.get("by", ""),
                                        examples_block=examples_block)
        return {"ok": True, "status": "added", "destination": "governance", "title": title,
                "gov_status": res.get("status"), "gov_reason": res.get("reason", "")}
    if destination == "knowledge" and notes is not None:
        from nooch_village.insight import Insight, GroundingStatus
        import uuid as _uuid
        # 'info' = wat de mens zelf toevoegt (tactical: informatie geven); valt terug op de kans.
        claim = (info or "").strip() or title
        notes.add(Insight(id="kn_" + _uuid.uuid4().hex[:9], claim=claim,
                          grounds=(info or wat or title), source="triage",
                          status=GroundingStatus.UNRESOLVED, tags=["triage"]))
        return {"ok": True, "status": "added", "destination": "knowledge", "title": title}
    # project (default): dedup op scope + eigenaar, zodat 2 projecten voor verschillende rollen kunnen.
    scope = (scope_override or "").strip() or title
    owner = (owner or ctx.get("by") or "village").strip()
    if projects is not None:
        dup = any(str(p.get("scope")) == scope and p.get("owner") == owner
                  and p.get("status") not in ("done",) for p in projects.all())
        if not dup:
            projects.create(owner, scope, "human", hypothesis=wat,
                            business_case=ctx.get("business_case"), status=project_status)
    return {"ok": True, "status": "added", "destination": "project",
            "title": scope, "owner": owner, "draft": project_status == "draft"}


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
        from nooch_village.llm import reason as llm_reason
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


def formulate_accountability(title: str, wat: str, *, examples_block: str = "",
                             llm_reason=None) -> str:
    """Formuleer een kans tot één Holacracy-accountability (NL: -en-vorm vooraan, doorlopende
    activiteit). Gegrond met echte voorbeelden uit vergelijkbare orgs. Fail-closed → de titel."""
    from nooch_village.governance_examples import ACCOUNTABILITY_RULES
    title = (title or "").strip()
    if llm_reason is None:
        from nooch_village.llm import reason as llm_reason
    prompt = (
        "Je belegt voor NoochVille (duurzaam, vegan schoenenmerk) een kans als accountability "
        "van een rol.\n\n" + ACCOUNTABILITY_RULES + "\n\n"
        + (examples_block + "\n\n" if examples_block else "")
        + f"Kans: {title}\nToelichting: {wat}\n\n"
        "Schrijf PRECIES één accountability volgens de regels (begint met de -en-vorm, "
        "doorlopende activiteit). Eén regel, niets anders.")
    out = (llm_reason(prompt) or "").strip().splitlines()
    line = out[0].strip().strip('"- ').strip() if out else ""
    return line[:140] or title


def pick_governance_target(roster_ids, title: str, wat: str, *, examples_block: str = "",
                           llm_reason=None) -> str:
    """AI kiest of een kans een BESTAANDE rol uitbreidt of een NIEUWE rol vraagt. Geeft een
    bestaand rol-id terug, of '__new__'. Heeft overzicht over alle rollen (roster_ids) en —
    ter inspiratie — echte rollen uit vergelijkbare orgs. Fail-closed zonder LLM → '__new__'."""
    ids = [r for r in (roster_ids or []) if r and r != "noochville"]
    if not ids:
        return "__new__"
    if llm_reason is None:
        from nooch_village.llm import reason as llm_reason
    prompt = (
        "NoochVille (duurzaam schoenenmerk) gebruikt Holacracy. Een kans moet via governance "
        "belegd worden. Kies of een BESTAANDE rol hiervoor uitgebreid wordt, of dat er een NIEUWE "
        "rol nodig is. Een nieuwe rol alleen als geen bestaande rol logisch past.\n\n"
        + (examples_block + "\n\n" if examples_block else "")
        + f"Kans: {title}\nToelichting: {wat}\n\n"
        f"Bestaande rollen in NoochVille: {', '.join(ids)}\n\n"
        "Antwoord met PRECIES één regel: het rol-id van de best passende bestaande rol, "
        "of het woord __new__ als geen enkele past. Niets anders.")
    out = (llm_reason(prompt) or "").strip().lower()
    if not out:
        return "__new__"
    token = re.split(r"\s+", out)[0].strip(".:'\"")
    if token == "__new__":
        return "__new__"
    for r in ids:
        if r.lower() == token:
            return r
    return "__new__"


def formulate_project(title: str, wat: str, owner: str = "", *, llm_reason=None) -> str:
    """AI formuleert een kans tot een Holacracy-project: een heldere uitkomst-zin als AFGERONDE
    toestand (waar je naartoe werkt), niet vaag. Fail-closed zonder LLM → de oorspronkelijke titel."""
    title = (title or "").strip()
    if llm_reason is None:
        from nooch_village.llm import reason as llm_reason
    prompt = (
        "In Holacracy is een PROJECT een concrete uitkomst, geformuleerd als een AFGERONDE "
        "toestand (voltooid): bijv. 'Reviews zichtbaar op elke productpagina', 'Nieuw logo "
        "ontworpen'. Niet als vage wens, niet als doorlopende taak. Herschrijf onderstaande kans "
        "tot één zo'n korte uitkomst-zin in gewone taal. Geen jargon.\n\n"
        f"Kans: {title}\nToelichting: {wat}\n"
        f"{f'Uit te voeren door rol: {owner}' if owner else ''}\n\n"
        "Antwoord met PRECIES één korte zin, niets anders.")
    out = (llm_reason(prompt) or "").strip().splitlines()
    line = out[0].strip().strip('"').strip() if out else ""
    return line[:140] or title


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
