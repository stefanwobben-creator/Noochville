"""Roloverleg — het IDM-governanceoverleg (vereenvoudigd naar Holacracy's integrative decision-making).

Voorstellen (uit de triage of door de mens toegevoegd) wachten op een AGENDA en worden in het
overleg één voor één behandeld:
  1. de huidige rol is zichtbaar, daaronder de voorgestelde wijziging + reden;
  2. de Secretaris doet een good-governance-check (volledig, geen dubbele accountability, de
     -en-formulering) — dezelfde deterministische poort G0-G4;
  3. de mens kan een reactie geven → de AI past het voorstel aan (gegrond in de referentiebank);
  4. consent (aangenomen) of schadelijk (blijft staan, volgende keer oplossen);
  5. bij EINDE ROLOVERLEG worden de aangenomen voorstellen doorgevoerd (Gate + Secretary._adopt).

Niets wordt automatisch doorgevoerd: pas bij consent + einde overleg verandert de structuur.
Opslag: data/roloverleg_agenda.json (gitignored).
"""
from __future__ import annotations
import json, os, re, time, uuid
from nooch_village.util import atomic_write_json


class Agenda:
    """De agenda van het roloverleg: governance-voorstellen die op behandeling wachten."""

    def __init__(self, path: str):
        self.path = path
        self._items: list[dict] = []
        if os.path.exists(path):
            try:
                self._items = json.load(open(path))
            except Exception:
                self._items = []

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        atomic_write_json(self.path, self._items)

    def add(self, role_id: str, kind: str, change: dict, reason: str,
            by: str = "founder", title: str = "") -> str:
        """Zet een voorstel op de agenda. Dedup op (role_id, kind, eerste accountability/purpose)."""
        title = (title or role_id or "voorstel").strip()
        sig = (role_id, kind, (change.get("purpose") or "").lower(),
               tuple(a.lower() for a in change.get("add_accountabilities", [])))
        for it in self._items:
            c = it.get("change", {})
            if (it["role_id"], it["kind"], (c.get("purpose") or "").lower(),
                    tuple(a.lower() for a in c.get("add_accountabilities", []))) == sig:
                return it["id"]
        iid = uuid.uuid4().hex[:12]
        self._items.append({
            "id": iid, "role_id": role_id, "kind": kind, "change": change,
            "reason": reason or "", "by": by or "founder", "title": title,
            "status": "open", "reactions": [], "created_at": time.time()})
        self._save()
        return iid

    def all(self) -> list[dict]:
        return list(self._items)

    def open(self) -> list[dict]:
        """Nog te behandelen (open of vorige keer schadelijk bevonden)."""
        return [i for i in self._items if i["status"] in ("open", "objected")]

    def get(self, iid: str) -> dict | None:
        return next((i for i in self._items if i["id"] == iid), None)

    def react(self, iid: str, text: str) -> bool:
        it = self.get(iid)
        if it is None or not (text or "").strip():
            return False
        it.setdefault("reactions", []).append({"text": text.strip(), "at": time.time()})
        self._save()
        return True

    def update_change(self, iid: str, change: dict) -> bool:
        it = self.get(iid)
        if it is None:
            return False
        it["change"] = change
        self._save()
        return True

    def set_status(self, iid: str, status: str) -> bool:
        it = self.get(iid)
        if it is None or status not in ("open", "consented", "objected"):
            return False
        it["status"] = status
        self._save()
        return True

    def remove(self, iid: str) -> bool:
        n = len(self._items)
        self._items = [i for i in self._items if i["id"] != iid]
        if len(self._items) != n:
            self._save()
            return True
        return False


def _proposal_from_item(item: dict):
    """Bouw een Proposal uit een agenda-item (voor de Gate en het adopteren)."""
    from nooch_village.models import Proposal, GovernanceChange, ChangeKind
    kind = ChangeKind.ADD_ROLE if item.get("kind") == "add_role" else ChangeKind.AMEND_ROLE
    c = item.get("change", {})
    change = GovernanceChange(
        kind=kind, role_id=item.get("role_id"),
        purpose=c.get("purpose"), add_accountabilities=list(c.get("add_accountabilities", [])),
        remove_accountabilities=list(c.get("remove_accountabilities", [])),
        add_domains=list(c.get("add_domains", [])), new_role_parent=c.get("new_role_parent"))
    title = item.get("title", "")
    return Proposal(
        proposer_role=item.get("by") or "founder", change=change,
        tension=f"roloverleg: {title}"[:200],
        trigger_example=f"structureel besluit via roloverleg door de mens: {title[:60]}",
        rationale=item.get("reason") or title or "Roloverleg-voorstel.", source="sensed")


def secretary_check(item: dict, records) -> list[dict]:
    """Good-governance-check door de Secretaris: deterministische poort (G0-G4) + de
    -en-formuleercheck. Geeft een lijst issues [{level: 'blok'|'let op', msg}]; leeg = in orde."""
    from nooch_village.governance import Gate
    issues: list[dict] = []
    passed, gate, reason = Gate().check(_proposal_from_item(item), records, None)
    if not passed:
        issues.append({"level": "blok", "msg": f"{gate}: {reason}"})
    new_accs = item.get("change", {}).get("add_accountabilities", [])
    # Rijpheidspoort: een accountability hoort GESTOLD te zijn (terugkerende frictie). Geen
    # bewijs? Dan is het waarschijnlijk nog een experiment → liever een project. Advies, geen veto.
    if new_accs:
        from nooch_village.maturity import friction_evidence
        if not friction_evidence(item.get("title", ""), item.get("reason", ""),
                                 " ".join(r.get("text", "") for r in item.get("reactions", []))):
            issues.append({"level": "let op",
                           "msg": "nog niet gestold: geen bewijs van terugkerende frictie. "
                                  "Overweeg dit eerst als project (experiment) te doen."})
    # Dubbel binnen DEZELFDE rol: Gate's G2 slaat de eigen rol over, dus die check doen we hier.
    rec = records.get(item.get("role_id"))
    if rec is not None:
        for na in new_accs:
            nl = na.lower()
            for ex in rec.definition.accountabilities:
                el = ex.lower()
                if el == nl or nl in el or el in nl:
                    issues.append({"level": "let op",
                                   "msg": f"de rol heeft al een vergelijkbare accountability: '{ex[:60]}'"})
                    break
    for a in new_accs:
        first = (a.strip().split(" ", 1)[0] if a.strip() else "").lower()
        if not first.endswith("en"):
            issues.append({"level": "let op",
                           "msg": f"accountability begint niet met de -en-vorm: '{a[:50]}'"})
    return issues


def _parse_role(text: str) -> dict:
    """Parse PURPOSE / ACCOUNTABILITIES / DOMEIN uit een LLM-rolherziening."""
    pm = re.search(r"PURPOSE\s*:\s*(.+)", text, re.IGNORECASE)
    dm = re.search(r"DOMEIN(?:EN)?\s*:\s*(.+)", text, re.IGNORECASE)
    am = re.search(r"ACCOUNTABILITIES\s*:\s*(.*?)(?:\nDOMEIN|\Z)", text, re.IGNORECASE | re.DOTALL)
    accs = []
    if am:
        for ln in am.group(1).splitlines():
            ln = re.sub(r"^[\-\*\d\.\)\s]+", "", ln).strip()
            if len(ln) > 2:
                accs.append(ln[:140])
    purpose = pm.group(1).strip()[:140] if pm else ""
    domein = (dm.group(1).strip() if dm else "")
    if domein.lower() in ("-", "geen", "none", ""):
        domein = ""
    return {"purpose": purpose, "accountabilities": accs[:10], "domein": domein[:140]}


def amend_with_reaction(item: dict, reaction: str, *, role_snapshot: dict | None = None,
                        examples_block: str = "", llm_reason=None) -> dict:
    """De AI herziet op basis van jouw reactie de HELE rol (purpose + accountabilities + evt.
    domein), Holacracy-correct en gegrond in de referentiebank. Voor een bestaande rol levert dit
    een echte diff op (add/remove accountabilities) t.o.v. de huidige rol. Fail-closed zonder LLM
    of zonder leesbaar antwoord → de wijziging blijft ongemoeid. Geeft de (nieuwe) change-dict."""
    from nooch_village.governance_examples import ACCOUNTABILITY_RULES
    change = dict(item.get("change", {}))
    reaction = (reaction or "").strip()
    if not reaction:
        return change
    if llm_reason is None:
        from nooch_village.llm import reason as llm_reason
    is_add = item.get("kind") == "add_role"
    snap = role_snapshot or {}
    # 'Huidige' rol zoals de mens 'm ziet: bij add_role = het voorstel; bij amend = de echte rol
    # plus de al voorgestelde toevoeging.
    if is_add:
        cur_purpose = change.get("purpose", "")
        cur_accs = list(change.get("add_accountabilities", []))
    else:
        cur_purpose = change.get("purpose") or snap.get("purpose", "")
        cur_accs = list(dict.fromkeys(list(snap.get("accountabilities", []))
                                      + list(change.get("add_accountabilities", []))))
    acc_txt = "\n".join(f"- {a}" for a in cur_accs) or "- (nog geen)"
    prompt = (
        "Je herziet in een roloverleg (Holacracy) een hele rol op basis van de reactie van de mens.\n\n"
        + ACCOUNTABILITY_RULES + "\n\n" + (examples_block + "\n\n" if examples_block else "")
        + f"Rol nu:\nPURPOSE: {cur_purpose}\nACCOUNTABILITIES:\n{acc_txt}\n\n"
        f"Reactie van de mens: {reaction}\n\n"
        "Geef de VOLLEDIG herziene rol, met de reactie verwerkt. Behoud wat goed is, pas aan/voeg "
        "toe/laat weg wat de reactie vraagt. Antwoord EXACT in dit formaat:\n"
        "PURPOSE: <reden van bestaan, geen -en-vorm>\n"
        "ACCOUNTABILITIES:\n- <accountability, -en-vorm>\n- <...>\n"
        "DOMEIN: <exclusief beheer, of '-'>")
    parsed = _parse_role(llm_reason(prompt) or "")
    if not parsed["purpose"] and not parsed["accountabilities"]:
        return change                                   # fail-closed: niets bruikbaars terug
    new = dict(change)
    if parsed["purpose"]:
        new["purpose"] = parsed["purpose"]
    desired = parsed["accountabilities"]
    if desired:
        if is_add:
            new["add_accountabilities"] = desired       # nieuwe rol: de hele set is 'toe te voegen'
        else:
            real = list(snap.get("accountabilities", []))
            dl = {d.lower() for d in desired}
            rl = {r.lower() for r in real}
            new["add_accountabilities"] = [d for d in desired if d.lower() not in rl]
            new["remove_accountabilities"] = [r for r in real if r.lower() not in dl]
    if parsed["domein"]:
        new["add_domains"] = [parsed["domein"]]
    return new


def flip_facet(item: dict, *, examples_block: str = "", llm_reason=None) -> dict:
    """Zet een amend-voorstel om tussen PURPOSE (ziel) en ACCOUNTABILITY (activiteit), voor als de
    AI de bedoeling verkeerd inschatte. Geeft de nieuwe change-dict. Alleen zinvol bij amend_role."""
    from nooch_village.inbox_actions import formulate_purpose, formulate_accountability
    change = dict(item.get("change", {}))
    title, reason = item.get("title", ""), item.get("reason", "")
    is_purpose_now = bool(change.get("purpose")) and not change.get("add_accountabilities")
    if is_purpose_now:
        acc = formulate_accountability(title, reason, examples_block=examples_block, llm_reason=llm_reason)
        return {"add_accountabilities": [acc]}
    purpose = formulate_purpose(title, reason, examples_block=examples_block, llm_reason=llm_reason)
    return {"purpose": purpose, "add_accountabilities": []}


def apply_consented(agenda: Agenda, records) -> list[dict]:
    """Einde roloverleg: voer de aangenomen (consented) voorstellen door via de poort + Secretaris.
    Geslaagd → geadopteerd en van de agenda af. Gate blokkeert → blijft staan als 'schadelijk'
    (objected) met reden. Geeft een samenvatting per voorstel."""
    from nooch_village.event_bus import EventBus
    from nooch_village.governance import Gate, Secretary
    sec = Secretary(records, EventBus(name="roloverleg"))
    out: list[dict] = []
    for item in [i for i in agenda.all() if i["status"] == "consented"]:
        proposal = _proposal_from_item(item)
        passed, gate, reason = Gate().check(proposal, records, None)
        if passed:
            sec._adopt(proposal)
            agenda.remove(item["id"])
            out.append({"title": item["title"], "status": "adopted"})
        else:
            agenda.set_status(item["id"], "objected")
            out.append({"title": item["title"], "status": "escalated",
                        "gate": gate, "reason": reason})
    return out
