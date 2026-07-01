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
import os, re, time, uuid
from nooch_village.util import atomic_write_json, read_json


class Agenda:
    """De agenda van het roloverleg: governance-voorstellen die op behandeling wachten."""

    def __init__(self, path: str):
        self.path = path
        self._items: list[dict] = read_json(path, [], expect=list)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        atomic_write_json(self.path, self._items)

    def add(self, role_id: str, kind: str, change: dict, reason: str,
            by: str = "founder", title: str = "", example: str = "", benefit: str = "",
            group: str | None = None) -> str:
        """Zet een voorstel op de agenda. Dedup op (role_id, kind, eerste accountability/purpose).
        `reason` = de spanning die dit oplost; `example` = een concreet voorbeeld; `benefit` = hoe
        aannemen de EIGEN rol van de indiener helpt (verplicht bij een voorstel over een ándere rol —
        Holacracy 'from your role'). `group` = voorstel-id zodat één voorstel meerdere rollen kan
        raken (GlassFrog); leeg = eigen id (één rol). (Een voorstel is tension-driven.)"""
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
            "reason": reason or "", "example": example or "", "benefit": benefit or "",
            "by": by or "founder", "title": title, "group": group or iid,
            "status": "open", "reactions": [], "created_at": time.time()})
        self._save()
        return iid

    def all(self) -> list[dict]:
        return list(self._items)

    def open(self) -> list[dict]:
        """Nog te behandelen (open of vorige keer schadelijk bevonden)."""
        return [i for i in self._items if i["status"] in ("open", "objected")]

    def group_of(self, iid: str) -> str:
        it = self.get(iid)
        return (it.get("group") or it["id"]) if it else iid

    def members_of_group(self, gid: str, *, only_open: bool = False) -> list[dict]:
        """Alle rol-onderdelen van één voorstel (zelfde group). Oudste eerst."""
        ms = [i for i in self._items if (i.get("group") or i["id"]) == gid
              and (not only_open or i["status"] in ("open", "objected"))]
        return sorted(ms, key=lambda i: i.get("created_at", 0))

    def get(self, iid: str) -> dict | None:
        return next((i for i in self._items if i["id"] == iid), None)

    def react(self, iid: str, text: str) -> bool:
        it = self.get(iid)
        if it is None or not (text or "").strip():
            return False
        it.setdefault("reactions", []).append({"text": text.strip(), "at": time.time()})
        self._save()
        return True

    def add_kladblok(self, iid: str, who: str, text: str) -> bool:
        """Voeg een bericht toe aan het kladblok (chat met de AI) van een voorstel. `who` =
        'jij' of 'ai'. Het kladblok is een denkruimte naast het voorstel; het wijzigt de rol niet."""
        it = self.get(iid)
        if it is None or not (text or "").strip():
            return False
        it.setdefault("kladblok", []).append(
            {"who": who, "text": text.strip(), "at": time.time()})
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

    def update_fields(self, iid: str, **fields) -> bool:
        """Werk losse velden van een agenda-item bij (change, role_id, title, ...)."""
        it = self.get(iid)
        if it is None:
            return False
        it.update({k: v for k, v in fields.items() if v is not None})
        self._save()
        return True

    def set_objection(self, iid: str, text: str, result: dict) -> bool:
        """Bewaar een getoetst bezwaar (tekst + Facilitator-validiteitsresultaat) op het item."""
        it = self.get(iid)
        if it is None:
            return False
        it["objection"] = {"text": (text or "").strip(), "result": result, "at": time.time()}
        it["status"] = "objected" if result.get("valid") else "open"
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
    _kinds = {"add_role": ChangeKind.ADD_ROLE, "remove_role": ChangeKind.REMOVE_ROLE}
    kind = _kinds.get(item.get("kind"), ChangeKind.AMEND_ROLE)
    c = item.get("change", {})
    change = GovernanceChange(
        kind=kind, role_id=item.get("role_id"),
        purpose=c.get("purpose"), add_accountabilities=list(c.get("add_accountabilities", [])),
        remove_accountabilities=list(c.get("remove_accountabilities", [])),
        add_domains=list(c.get("add_domains", [])), remove_domains=list(c.get("remove_domains", [])),
        new_role_parent=c.get("new_role_parent"), rename=c.get("rename"))
    title = item.get("title", "")
    return Proposal(
        proposer_role=item.get("by") or "founder", change=change,
        tension=f"roloverleg: {title}"[:200],
        trigger_example=f"structureel besluit via roloverleg door de mens: {title[:60]}",
        rationale=item.get("reason") or title or "Roloverleg-voorstel.", source="sensed")


def formalize_ripe_experiments(ledger, agenda, threshold: int = 3) -> int:
    """Stollen: een experiment (project met origin='experiment') dat ≥ `threshold` keer is
    uitgevoerd, heeft zich bewezen als terugkerend werk → draag het automatisch voor als
    accountability op de roloverleg-agenda voor de eigenaar-rol. Dedup via de 'formalized'-vlag.
    Geeft het aantal nieuw voorgedragen experimenten. (docs/GOVERNANCE_FILOSOFIE: accountability =
    gestolde frictie; de rijpheidspoort is hier door herhaalde uitvoering aantoonbaar vervuld.)"""
    n = 0
    for p in ledger.all():
        if (p.get("origin") == "experiment" and not p.get("formalized")
                and p.get("status") not in ("done", "draft")
                and int(p.get("executions", 0)) >= threshold):
            owner = p.get("owner", "")
            scope = p.get("scope")
            acc = scope if isinstance(scope, str) else " · ".join(f"{k}: {v}" for k, v in scope.items())
            if not acc.strip():
                continue
            agenda.add(
                role_id=owner, kind="amend_role",
                change={"add_accountabilities": [acc[:140]]},
                reason=(f"{p.get('executions')}x uitgevoerd als experiment: structureel terugkerend "
                        "werk, de frictie is gestold → vastleggen als accountability"),
                by=owner, title=acc[:60],
                example=(p.get("progress") or "")[:200])
            ledger.mark_formalized(p["id"])
            n += 1
    return n


# De vier toetsvragen uit de roldenken.nl/Holacracy-handout. De MENS (bezwaarmaker) kiest per
# vraag het linker ('left' → richting geldig) of rechter ('right' → geen geldig bezwaar) antwoord.
# De facilitator/AI oordeelt NIET over de inhoud; de uitkomst volgt uit de eigen antwoorden.
_OBJ_QUESTIONS = [
    {"q": "q1", "label": "Schade",
     "vraag": "Zie je een reden waarom dit voorstel SCHADE veroorzaakt?",
     "left": "Ja, het veroorzaakt schade",
     "right": "Nee, mijn zorg is dat het onnodig of onvolledig is",
     "hint": "Schade = het vermindert de capaciteit van een rol om haar doel of "
             "verantwoordelijkheden uit te drukken (niet per se fysiek of financieel)."},
    {"q": "q2", "label": "Door dit voorstel",
     "vraag": "Wordt je zorg veroorzaakt door DIT voorstel?",
     "left": "Ja, door dit voorstel",
     "right": "Nee, het is al een zorg, ook als het voorstel werd ingetrokken"},
    {"q": "q3", "label": "Zeker, niet speculatief",
     "vraag": "Weet je dat deze impact ZAL optreden?",
     "left": "Ja, ik weet het zeker",
     "right": "Nee, ik anticipeer dat het zou kunnen optreden"},
    {"q": "q3b", "label": "Niet veilig om te proberen", "depends_on": ("q3", "right"),
     "vraag": "Zou er aanzienlijke schade kunnen optreden vóórdat we kunnen bijsturen?",
     "left": "Ja, aanzienlijke schade vóór we kunnen aanpassen",
     "right": "Nee, het is veilig genoeg om te proberen (we kunnen altijd herzien)"},
    {"q": "q4", "label": "Beperkt jouw rol",
     "vraag": "Zou het voorstel een van JOUW rollen beperken?",
     "left": "Ja, het beperkt een van mijn rollen",
     "right": "Nee, ik probeer een andere rol / de cirkel in het algemeen te helpen"},
]


def evaluate_objection(answers: dict, *, harm: str = "") -> dict:
    """Bepaal de geldigheid van een bezwaar uit de antwoorden van de bezwaarmaker op de vier
    toetsvragen (handout roldenken.nl). Geldig = op alle vragen het 'left'-antwoord; bij 'anticiperen'
    (q3=right) telt q3b mee: aanzienlijke schade vóór bijsturen (left) = geldig, veilig om te proberen
    (right) = ongeldig. De mens beslist per vraag; dit telt alleen op. Onbeantwoord = ongeldig.

    Geeft {valid, answers, harm, steps:[{label,vraag,answer,ok,gekozen}], summary}."""
    a = {k: (answers.get(k) or "").lower() for k in ("q1", "q2", "q3", "q3b", "q4")}
    steps, valid, first_fail = [], True, None
    for spec in _OBJ_QUESTIONS:
        dep = spec.get("depends_on")
        if dep and a.get(dep[0]) != dep[1]:
            continue                                    # q3b alleen relevant als q3 = anticiperen
        ans = a.get(spec["q"], "")
        # q3 is een SPLITSING, geen buis: 'right' (anticiperen) leidt naar q3b en is op zich geldig.
        if spec["q"] == "q3":
            ok = ans in ("left", "right")
        else:
            ok = ans == "left"
        gekozen = spec["left"] if ans == "left" else (spec["right"] if ans == "right" else "—")
        steps.append({"label": spec["label"], "vraag": spec["vraag"], "answer": ans,
                      "ok": ok, "gekozen": gekozen})
        if not ok:
            valid = False
            if first_fail is None:
                first_fail = spec["label"]
    summary = ("geldig bezwaar — we integreren het in het voorstel" if valid else
               (f"geen geldig bezwaar (zakt op: {first_fail})" if first_fail
                else "nog niet alle vragen beantwoord"))
    return {"valid": valid, "answers": a, "harm": (harm or "").strip(),
            "steps": steps, "summary": summary}


_EXEMPT_PROPOSERS = {"founder", "facilitator", "secretary"}   # Circle Lead / procesrollen


def tension_validity(item: dict, *, llm_reason=None) -> tuple[bool, str]:
    """Holacracy 'from your role' bij intake: een voorstel om een ÁNDERE rol te wijzigen is alleen
    een geldige spanning als de indiener concreet kan benoemen hoe aannemen zíjn/háár eigen rol
    helpt. Kan dat niet, dan mag de Facilitator de spanning ongeldig verklaren en het punt direct
    schrappen, zónder het governance-proces te doorlopen.

    Geeft (geldig, reden-bij-ongeldig). Deterministisch: een cross-rol-voorstel zonder benefit is
    ongeldig. Is er wel een benefit en een LLM beschikbaar, dan toetst die nog of de benefit echt
    aan de eigen rol raakt (fail-open: bij twijfel/geen-LLM geldig)."""
    by = (item.get("by") or "").strip().lower()
    target = (item.get("role_id") or "").strip().lower()
    cross = bool(by) and bool(target) and by != target and by not in _EXEMPT_PROPOSERS
    if not cross:
        return True, ""                                     # eigen rol, of Circle Lead/procesrol
    benefit = (item.get("benefit") or "").strip()
    if not benefit:
        return (False, f"geen baat voor de eigen rol benoemd: '{by}' stelt een wijziging voor aan "
                f"'{target}', maar zegt niet hoe aannemen de eigen rol helpt (Holacracy: from your role)")
    if llm_reason is not None:
        ans = (llm_reason(
            f"Een rol '{by}' stelt voor om rol '{target}' te wijzigen. Onderbouwing hoe het de eigen "
            f"rol '{by}' helpt: \"{benefit}\". Raakt dit echt een spanning vanuit de rol '{by}' zelf "
            "(niet alleen 'goed voor het dorp')? Antwoord met alleen JA of NEE.") or "").strip().upper()
        if ans.startswith("NEE"):
            return (False, f"de benoemde baat raakt geen spanning vanuit de eigen rol '{by}', "
                    "maar een algemeen belang — dat is geen geldige eigen spanning")
    return True, ""


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


def build_change_from_fields(item: dict, snapshot: dict | None, *, naam: str = "",
                             purpose: str = "", accs=(), domeinen=()) -> tuple[dict, str, str]:
    """GlassFrog-stijl: bouw de change uit de DIRECT bewerkte velden (naam/purpose/accountabilities/
    domeinen). Voor een bestaande rol levert dit een echte diff op (add/remove t.o.v. de huidige
    rol); voor een nieuwe rol is alles 'toe te voegen'. Geeft (change, role_id, title)."""
    accs = [a.strip() for a in accs if a and a.strip()][:12]
    doms = [d.strip() for d in domeinen if d and d.strip()][:8]
    purpose = (purpose or "").strip()
    if item.get("kind") == "add_role":
        rid = re.sub(r"\W+", "_", (naam or purpose).lower())[:40].strip("_") or item.get("role_id", "nieuwe_rol")
        change = {"purpose": purpose[:140], "add_accountabilities": accs, "add_domains": doms,
                  "new_role_parent": item.get("change", {}).get("new_role_parent", "noochville")}
        return change, rid, (naam or purpose)[:60]
    snap = snapshot or {}
    real_a, real_d = list(snap.get("accountabilities", [])), list(snap.get("domains", []))
    la, da = {a.lower() for a in real_a}, {a.lower() for a in accs}
    ld, dd = {d.lower() for d in real_d}, {d.lower() for d in doms}
    change = {
        "add_accountabilities": [a for a in accs if a.lower() not in la],
        "remove_accountabilities": [a for a in real_a if a.lower() not in da],
        "add_domains": [d for d in doms if d.lower() not in ld],
        "remove_domains": [d for d in real_d if d.lower() not in dd]}
    if purpose and purpose != (snap.get("purpose", "") or "").strip():
        change["purpose"] = purpose[:140]
    # Naam wijzigen van een bestaande rol = een weergavenaam (record-id blijft stabiel).
    cur_name = (snap.get("name") or item.get("role_id") or "").strip()
    naam = (naam or "").strip()
    title = item.get("title")
    if naam and naam != cur_name:
        change["rename"] = naam[:60]
        title = naam[:60]
    return change, item.get("role_id"), title


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
