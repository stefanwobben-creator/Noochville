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
        from nooch_village.llm import reason as llm_reason
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
