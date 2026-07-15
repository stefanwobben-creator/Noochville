"""Facilitator-rolreview: een eenmalig 'project' waarin elke dorp-rol langs de Holacracy-meetlat
wordt gelegd, gegrond in de vertrouwelijke referentiebank (governance_examples). Per rol komt er
ÉÉN concreet verbetervoorstel, dat als kans in de human inbox landt — mens-gated. Niks wordt
automatisch toegepast: de Facilitator senst en stelt voor, jij beslist in de triage.

Respecteert de harde regels: sensing levert uitsluitend voorstellen op (geen self-execute), en
de referentiebank wordt alleen hier (governance-formulering) geraadpleegd, nooit in content.
"""
from __future__ import annotations
import re

# Constitutionele kernrollen en de wortelcirkel slaan we over: hun purpose/accountabilities
# liggen in de Grondwet vast, die herschrijf je niet met een verbetervoorstel.
_SKIP = {"noochville", "facilitator", "secretary", "secretaris", "lead_link",
         "rep_link", "cirkel_lead", "circle_lead"}


def _collapse(text: str) -> str:
    """Meerdere regels → één nette zin/alinea (vervolgregels samenvoegen, witruimte normaliseren)."""
    return re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip().strip('"').strip()


def _parse_review(text: str) -> dict | None:
    """Lees SUGGESTIE/WAAROM uit het LLM-antwoord. 'GEEN' → geen voorstel (rol is prima).
    De suggestie wordt VOLLEDIG meegenomen (ook over meerdere regels), zodat een voorstel als
    'Vervang X door: <nieuwe tekst>' niet halverwege afkapt."""
    if not text:
        return None
    if text.strip().upper().startswith("GEEN"):
        return None
    sug = re.search(r"SUGGESTIE\s*:\s*(.+?)(?:\nWAAROM\s*:|\Z)", text, re.IGNORECASE | re.DOTALL)
    why = re.search(r"WAAROM\s*:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    s = _collapse(sug.group(1)) if sug else ""
    if not s:
        return None
    # Ruime limieten: liever compleet dan netjes afgekapt (een halve zin is waardeloos).
    return {"suggestion": s[:600], "why": (_collapse(why.group(1))[:600] if why else "")}


def review_role(role: dict, examples_block: str = "", *, llm_reason=None) -> dict | None:
    """Beoordeel één rol tegen de Holacracy-regels + vergelijkbare echte rollen. Geeft
    {suggestion, why} of None (geen verbetering nodig / geen LLM). role = {id, purpose,
    accountabilities, domains}."""
    from nooch_village.governance_examples import ACCOUNTABILITY_RULES
    if llm_reason is None:
        import functools
        from nooch_village.llm import reason as _reason
        llm_reason = functools.partial(_reason, call_site="governance_review")
    accs = role.get("accountabilities") or []
    acc_txt = "\n".join(f"  - {a}" for a in accs) or "  (geen)"
    prompt = (
        "Je bent de Facilitator van NoochVille (duurzaam, vegan schoenenmerk) en reviewt één rol "
        "tegen de Holacracy-regels.\n\n" + ACCOUNTABILITY_RULES + "\n\n"
        + (examples_block + "\n\n" if examples_block else "")
        + f"Rol: {role.get('id')}\nPurpose: {role.get('purpose','')}\n"
        f"Accountabilities:\n{acc_txt}\n\n"
        "Geef het BELANGRIJKSTE, meest concrete verbetervoorstel voor deze rol: bijv. een "
        "accountability herschrijven naar de -en-vorm, een ontbrekend aandachtsgebied toevoegen "
        "dat vergelijkbare organisaties wél beleggen, een te gedetailleerde regel schrappen, of "
        "de purpose scherper maken. Eén voorstel, concreet en in gewone taal.\n\n"
        "BELANGRIJK: schrijf het voorstel VOLUIT en AFGEROND. Stel je voor 'Vervang X door: ...', "
        "geef dan de volledige nieuwe tekst achter 'door:'. Lever nooit een halve zin in.\n\n"
        "Antwoord EXACT zo (of 'GEEN' als de rol prima is):\n"
        "SUGGESTIE: <de volledige, concrete wijziging, voluit>\nWAAROM: <korte reden>")
    return _parse_review(llm_reason(prompt))


def _ing_start(line: str) -> bool:
    """Begint deze accountability met een -ing-werkwoord (gerund)? Best-effort: eerste woord eindigt op
    'ing'. Gebruikt om te markeren welke herformuleringen nog niet aan de vorm voldoen (mens ziet dit)."""
    w = re.sub(r"^[\-\*\s]+", "", line or "").split()
    return bool(w) and w[0].lower().endswith("ing")


def _parse_teleology(text: str) -> dict | None:
    """Lees PURPOSE / ACCOUNTABILITIES / WAAROM uit het LLM-antwoord van de teleologie-review.
    'GEEN' → None (rol is al scherp). Geeft {purpose, accountabilities:[...], why} of None bij leeg."""
    if not text or text.strip().upper().startswith("GEEN"):
        return None
    pur = re.search(r"PURPOSE\s*:\s*(.+?)(?:\nACCOUNTABILITIES\s*:|\Z)", text, re.IGNORECASE | re.DOTALL)
    acc = re.search(r"ACCOUNTABILITIES\s*:\s*(.+?)(?:\nWAAROM\s*:|\Z)", text, re.IGNORECASE | re.DOTALL)
    why = re.search(r"WAAROM\s*:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    purpose = _collapse(pur.group(1)) if pur else ""
    accs = []
    if acc:
        for ln in acc.group(1).splitlines():
            ln = ln.strip()
            if ln.startswith(("-", "*", "•")):
                a = _collapse(ln.lstrip("-*• ").strip())
                if a:
                    accs.append(a[:200])
    if not purpose and not accs:
        return None
    return {"purpose": purpose[:400], "accountabilities": accs[:12],
            "why": (_collapse(why.group(1))[:400] if why else "")}


def review_role_teleology(role: dict, *, llm_reason=None) -> dict | None:
    """Teleologie-review van één rol: toets de purpose op het BESTAANSDOEL (het einde dat de rol dient,
    niet de taken) en herformuleer 'm zo nodig; herformuleer ELKE accountability in het ENGELS, op
    B1-niveau, beginnend met een -ing-werkwoord (gerund). Geeft {purpose, accountabilities, why} of None.
    Fail-closed: geen LLM/leeg → None (niets geforceerd)."""
    if llm_reason is None:
        import functools
        from nooch_village.llm import reason as _reason
        llm_reason = functools.partial(_reason, call_site="governance_teleology")
    accs = role.get("accountabilities") or []
    acc_txt = "\n".join(f"  - {a}" for a in accs) or "  (geen)"
    prompt = (
        "Je bent de Facilitator van NoochVille (duurzaam, vegan schoenenmerk) en begeleidt een "
        "TELEOLOGIE-review van één rol.\n\n"
        "TELEOLOGIE: de purpose moet het BESTAANSDOEL van de rol uitdrukken — het einde/de reden waarvoor "
        "de rol bestaat — NIET de taken of de methode. Toets de huidige purpose daaraan en herformuleer 'm "
        "zo nodig, in het Engels op B1-niveau (eenvoudig en helder).\n"
        "ACCOUNTABILITIES: herformuleer ELKE accountability in het ENGELS, op B1-niveau, en begin ELKE "
        "accountability met een werkwoord in de -ing-vorm (gerund): bv. 'Guarding ...', 'Translating ...', "
        "'Verifying ...', 'Delivering ...'. Behoud de betekenis; splits of schrap niet zomaar.\n\n"
        f"Rol: {role.get('id')}\nHuidige purpose: {role.get('purpose','')}\n"
        f"Huidige accountabilities:\n{acc_txt}\n\n"
        "Antwoord EXACT in dit formaat (of 'GEEN' als de rol al volledig aan de standaard voldoet):\n"
        "PURPOSE: <herijkte purpose, Engels, B1, bestaansdoel>\n"
        "ACCOUNTABILITIES:\n- <-ing ... >\n- <-ing ... >\n"
        "WAAROM: <korte reden: wat er teleologisch/qua vorm scherper is geworden>")
    return _parse_teleology(llm_reason(prompt))


def teleology_review_all_roles(records, inbox, *, llm_reason=None) -> dict:
    """De governance-teleologie-review over alle operationele dorp-rollen (kernrollen/cirkels overslaan).
    De Facilitator herijkt per rol purpose + accountabilities naar de standaard (Engels, B1, -ing-vorm);
    de Secretary legt elk resultaat vast als kans in de human inbox — mens-gated, niks auto-toegepast.
    Geeft {reviewed, proposed, skipped, incomplete}. Fail-closed: zonder LLM → 0 voorstellen."""
    from nooch_village.models import RecordType
    reviewed = proposed = skipped = incomplete = 0
    for rec in records.all():
        if getattr(rec, "archived", False):
            continue
        if rec.type != RecordType.ROLE or rec.id in _SKIP:
            skipped += 1
            continue
        d = rec.definition
        role = {"id": rec.id, "purpose": d.purpose, "accountabilities": list(d.accountabilities)}
        reviewed += 1
        res = review_role_teleology(role, llm_reason=llm_reason)
        if not res:
            continue
        niet_ing = [a for a in res["accountabilities"] if not _ing_start(a)]
        if niet_ing:
            incomplete += 1                                   # gemarkeerd, niet geweigerd: de mens beslist
        acc_block = "\n".join(f"- {a}" for a in res["accountabilities"]) or "- (geen)"
        wat = (f"Purpose (EN): {res['purpose']}\n\nAccountabilities (EN, B1, -ing):\n{acc_block}"
               + (f"\n\n⚠️ Nog niet in -ing-vorm: {'; '.join(niet_ing)}" if niet_ing else ""))
        inbox.add_opportunity(
            f"Teleologie-review '{rec.id}': purpose + accountabilities (EN, B1, -ing)",
            by="facilitator", kind="governance", wat=wat, waarom=res["why"])
        proposed += 1
    return {"reviewed": reviewed, "proposed": proposed, "skipped": skipped, "incomplete": incomplete}


def _parse_teleology_opportunity(subject: str, wat: str):
    """Lees (role_id, purpose, [accountabilities]) terug uit een teleologie-kans in de human inbox.
    role_id staat in de titel ('Teleologie-review '<id>': …'); purpose + accountabilities in `wat`.
    Strips markdown-vet (**) en laat de ⚠️-markeerregel weg."""
    m = re.search(r"Teleologie-review '([^']+)'", subject or "")
    role_id = m.group(1) if m else ""
    pm = re.search(r"Purpose \(EN\):\s*(.+)", wat or "")
    purpose = _collapse(pm.group(1)).replace("*", "").strip() if pm else ""
    accs = []
    for ln in (wat or "").splitlines():
        ln = ln.strip()
        if ln.startswith(("-", "*", "•")) and "Nog niet in -ing-vorm" not in ln:
            a = _collapse(ln.lstrip("-*• ")).replace("*", "").strip()
            if a:
                accs.append(a[:200])
    return role_id, purpose, accs


def route_teleology_to_roloverleg(inbox, records, agenda) -> dict:
    """De Secretary zet de teleologie-voorstellen (uit de human inbox) op de roloverleg-agenda, zodat de
    mens ze 1-voor-1 in het roloverleg verwerkt. Per rol één amend_role: de nieuwe purpose, de oude
    accountabilities eruit en de nieuwe (EN, B1, -ing) erin. Dedup via Agenda.add. Fail-closed per item:
    geen role_id/record of lege inhoud → overslaan. Geeft {routed, skipped}."""
    routed = skipped = 0
    for it in inbox.all():
        if it.get("type") != "opportunity" or "Teleologie-review" not in it.get("subject", ""):
            continue
        role_id, purpose, accs = _parse_teleology_opportunity(
            it.get("subject", ""), (it.get("context", {}) or {}).get("wat", ""))
        rec = records.get(role_id) if role_id else None
        if rec is None or (not purpose and not accs):
            skipped += 1
            continue
        current = list(getattr(rec.definition, "accountabilities", []) or [])
        change = {"purpose": purpose or None,
                  "remove_accountabilities": current, "add_accountabilities": accs}
        agenda.add(role_id, "amend_role", change,
                   reason="Teleologie-review: purpose als bestaansdoel + accountabilities in EN, B1, -ing.",
                   by="secretary", title=f"Teleologie: {role_id}")
        routed += 1
    return {"routed": routed, "skipped": skipped}


def review_all_roles(records, examples_store, inbox, *, llm_reason=None) -> dict:
    """Loop alle operationele dorp-rollen langs, en zet per rol één verbetervoorstel als kans in
    de human inbox (by='facilitator'). Mens-gated: jij verwerkt ze in de triage. Geeft
    {reviewed, proposed, skipped}. Fail-closed: zonder LLM → 0 voorstellen."""
    from nooch_village.models import RecordType
    from nooch_village.governance_examples import few_shot_block
    reviewed = proposed = skipped = 0
    for rec in records.all():
        if getattr(rec, "archived", False):
            continue
        if rec.type != RecordType.ROLE or rec.id in _SKIP:
            skipped += 1
            continue
        d = rec.definition
        role = {"id": rec.id, "purpose": d.purpose,
                "accountabilities": list(d.accountabilities), "domains": list(d.domains)}
        reviewed += 1
        query = f"{rec.id} {d.purpose} " + " ".join(d.accountabilities)
        block = few_shot_block(examples_store, query, k=3)
        res = review_role(role, block, llm_reason=llm_reason)
        if not res:
            continue
        inbox.add_opportunity(
            f"Rol '{rec.id}' aanscherpen",
            by="facilitator", kind="governance",
            wat=res["suggestion"], waarom=res["why"])
        proposed += 1
    return {"reviewed": reviewed, "proposed": proposed, "skipped": skipped}
