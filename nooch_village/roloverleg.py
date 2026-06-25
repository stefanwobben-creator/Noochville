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
import json, os, time, uuid
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
    for a in item.get("change", {}).get("add_accountabilities", []):
        first = (a.strip().split(" ", 1)[0] if a.strip() else "").lower()
        if not first.endswith("en"):
            issues.append({"level": "let op",
                           "msg": f"accountability begint niet met de -en-vorm: '{a[:50]}'"})
    return issues


def amend_with_reaction(item: dict, reaction: str, *, examples_block: str = "",
                        llm_reason=None) -> dict:
    """De AI past het voorstel aan op basis van jouw reactie (Holacracy-correct, gegrond met de
    referentiebank). Past de eerste accountability aan (amend_role) of de purpose (add_role).
    Fail-closed zonder LLM → de wijziging blijft ongemoeid. Geeft de (nieuwe) change-dict."""
    from nooch_village.governance_examples import ACCOUNTABILITY_RULES
    change = dict(item.get("change", {}))
    reaction = (reaction or "").strip()
    if not reaction:
        return change
    if llm_reason is None:
        from nooch_village.llm import reason as llm_reason
    is_add = item.get("kind") == "add_role"
    huidig = (change.get("purpose", "") if is_add
              else (change.get("add_accountabilities") or [""])[0])
    wat = "de purpose van een nieuwe rol" if is_add else "een accountability van een rol"
    prompt = (
        "Je past in een roloverleg (Holacracy) een governance-voorstel aan op basis van de "
        f"reactie van de mens. Het gaat om {wat}.\n\n" + ACCOUNTABILITY_RULES + "\n\n"
        + (examples_block + "\n\n" if examples_block else "")
        + f"Voorstel nu: {huidig}\nReden: {item.get('reason','')}\n"
        f"Reactie van de mens: {reaction}\n\n"
        "Schrijf de VERBETERDE versie, voluit en afgerond, in gewone taal. "
        + ("Eén korte purpose-zin." if is_add else "Eén accountability (begint met de -en-vorm).")
        + " Eén regel, niets anders.")
    out = (llm_reason(prompt) or "").strip().splitlines()
    line = out[0].strip().strip('"- ').strip() if out else ""
    if not line:
        return change
    if is_add:
        change["purpose"] = line[:140]
    else:
        accs = list(change.get("add_accountabilities", []))
        if accs:
            accs[0] = line[:140]
        else:
            accs = [line[:140]]
        change["add_accountabilities"] = accs
    return change


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
