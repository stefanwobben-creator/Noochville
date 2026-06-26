"""ProjectLedger — de proces-store: volgt de status van lopend en gepland werk.

Opslag: data/projects.json (atomic write). Elke entry is een project-record:
  id, owner, scope, trigger, status, blocked_on, created_at, updated_at, outcome.
Governance-records en human_inbox blijven ongemoeid.
"""
from __future__ import annotations
import json, os, time, uuid
from nooch_village.util import atomic_write_json

_VALID_TRIGGERS = {"clock", "human", "noochie", "tension"}
_TERMINAL       = {"done"}


class ProjectLedger:

    def __init__(self, path: str):
        self.path = path
        self._projects: dict[str, dict] = {}
        self._mtime: float = 0.0
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                self._projects = json.load(open(self.path))
                self._mtime = os.path.getmtime(self.path)
            except Exception:
                self._projects = {}

    def _maybe_reload(self) -> None:
        """Herlaad van schijf als het bestand door een extern proces is gewijzigd."""
        try:
            if os.path.exists(self.path) and os.path.getmtime(self.path) > self._mtime:
                self._load()
        except Exception:
            pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        atomic_write_json(self.path, self._projects)

    def _touch(self, project: dict) -> None:
        project["updated_at"] = time.time()

    # ── schrijven ──────────────────────────────────────────────────────────────

    def create(self, owner: str, scope, trigger: str,
               hypothesis: str = "", business_case: dict | None = None,
               status: str = "queued", origin: str = "",
               dod_outcome: str = "", done_when: str = "", goes_to: str = "",
               links: list[str] | None = None, parent: str | None = None) -> str:
        if trigger not in _VALID_TRIGGERS:
            raise ValueError(f"ongeldig trigger: '{trigger}'")
        if status not in ("queued", "draft", "future"):
            raise ValueError(f"ongeldige start-status: '{status}'")
        pid = uuid.uuid4().hex[:12]
        now = time.time()
        # Cluster-lidmaatschap: een kind erft de cluster-root van zijn ouder (master-switch werkt
        # zo op de hele keten). Geen ouder → eigen cluster (root/standalone).
        par = self._projects.get(parent) if parent else None
        cluster = (par.get("cluster") or parent) if par else pid
        self._projects[pid] = {
            "id":         pid,
            "owner":      owner,
            "scope":      scope,
            "trigger":    trigger,
            "status":     status,
            "blocked_on": None,
            "created_at": now,
            "updated_at": now,
            "outcome":    None,              # geleverde eind-uitkomst (gevuld bij done)
            "hypothesis":    hypothesis or "",
            "business_case": business_case,
            "origin":     origin or "",      # "experiment" = stolt later tot accountability bij herhaling
            "executions": 0,                 # hoe vaak een rol dit experiment heeft uitgevoerd
            "formalized": False,             # al voorgesteld als accountability? (dedup)
            "comments":   [],                # stuur-opmerkingen van de mens (de rol leest ze mee)
            "log":        [],                # gesprek: {who: 'mens'|'rol', text, at} — chat-weergave
            # DoD-contract: de rol weet hiermee wanneer hij klaar is (docs/ONTWERP_prikbord_kanban.md)
            "dod_outcome": dod_outcome or "",   # gewenste uitkomst in één zin
            "done_when":   done_when or "",     # checkbaar criterium (lege/nee-uitkomst telt ook)
            "goes_to":     goes_to or "",       # wie de uitkomst consumeert (rol/bord/mens)
            "links":       list(links or []),   # verwante projecten (de keten/het gesprek)
            "parent":      parent,              # ouder-project (None = root/standalone)
            "cluster":     cluster,             # cluster-root id (master-switch werkt hierop)
            "waiting_on":  None,                # project/briefje waarop dit wacht (resume-trigger)
        }
        self._save()
        return pid

    def open_scopes(self) -> set:
        """Scopes van niet-afgeronde projecten (voor dedup van kans-voorstellen)."""
        return {str(p.get("scope")) for p in self._projects.values()
                if p.get("status") not in _TERMINAL}

    def start(self, pid: str) -> bool:
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "running"
        p["blocked_on"] = None
        self._touch(p)
        self._save()
        return True

    def block(self, pid: str, on_role: str) -> bool:
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "blocked"
        p["blocked_on"] = on_role
        self._touch(p)
        self._save()
        return True

    def unblock(self, pid: str) -> bool:
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "running"
        p["blocked_on"] = None
        self._touch(p)
        self._save()
        return True

    def complete(self, pid: str, outcome: str | None = None) -> bool:
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "done"
        p["outcome"] = outcome
        self._touch(p)
        self._save()
        return True

    def edit(self, pid: str, scope=None, owner: str | None = None) -> bool:
        """Bewerk de inhoud van een project (scope en/of owner). Status blijft ongemoeid;
        done-projecten zijn vergrendeld. Lege waarden worden genegeerd. Geeft True bij succes."""
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        if scope is not None and str(scope).strip():
            p["scope"] = scope
        if owner is not None and str(owner).strip():
            p["owner"] = owner
        self._touch(p)
        self._save()
        return True

    def approve(self, pid: str) -> bool:
        """Keur een concept-project (draft) goed → het komt op het bord van de rol (queued).
        Alleen drafts. Zo zie je eerst de (AI-)formulering en geef je akkoord vóór het live gaat."""
        p = self._projects.get(pid)
        if p is None or p.get("status") != "draft":
            return False
        p["status"] = "queued"
        self._touch(p)
        self._save()
        return True

    def discard(self, pid: str) -> bool:
        """Gooi een concept-project (draft) weg dat je niet wilt. Alleen drafts; nooit een
        project dat al op het bord staat. Geeft True als verwijderd."""
        p = self._projects.get(pid)
        if p is None or p.get("status") != "draft":
            return False
        del self._projects[pid]
        self._save()
        return True

    def drafts(self) -> list[dict]:
        """Concept-projecten die op jouw akkoord wachten (status draft)."""
        self._maybe_reload()
        return [p for p in self._projects.values() if p.get("status") == "draft"]

    def record_progress(self, pid: str, note: str) -> bool:
        """Leg autonome voortgang vast: een rol heeft (omkeerbaar, met eigen skills) aan dit
        project gewerkt. Zet status queued→running, bewaart de uitkomst en markeert 'worked'
        (idempotent: niet nog eens oppakken). Done-projecten blijven ongemoeid."""
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["progress"] = note
        p.setdefault("log", []).append({"who": "rol", "text": note, "at": time.time()})
        p["worked"] = True
        p["executions"] = int(p.get("executions", 0)) + 1   # telt mee voor 'stollen na 3x'
        if p["status"] == "queued":
            p["status"] = "running"
        self._touch(p)
        self._save()
        return True

    def add_comment(self, pid: str, text: str) -> bool:
        """Plaats een stuur-opmerking op een project (de eigenaar-rol leest deze mee bij het werken).
        Bijv. 'richt je op technisch onderzoek naar een natuurlijke elastaan-vervanger'."""
        p = self._projects.get(pid)
        text = (text or "").strip()
        if p is None or not text:
            return False
        now = time.time()
        p.setdefault("comments", []).append({"text": text[:500], "at": now})
        p.setdefault("log", []).append({"who": "mens", "text": text[:500], "at": now})
        p["worked"] = False           # nieuwe sturing → de rol pakt het opnieuw op
        self._touch(p)
        self._save()
        return True

    def add_role_message(self, pid: str, text: str) -> bool:
        """Voeg een DIRECT antwoord van de rol toe aan het gesprek (chat-reply op een opmerking).
        Anders dan record_progress telt dit NIET als een experiment-uitvoering en raakt het de
        'worked'-vlag niet — het is conversatie, geen puls-werk."""
        p = self._projects.get(pid)
        text = (text or "").strip()
        if p is None or not text:
            return False
        p.setdefault("log", []).append({"who": "rol", "text": text[:1500], "at": time.time()})
        p["progress"] = text
        self._touch(p)
        self._save()
        return True

    def wait_for(self, pid: str, need: str, on_id: str = "") -> bool:
        """Zet een project op WACHTEN met een gestructureerde behoefte: WAT is nodig (need) en
        WAAROP het wacht (on_id = een ander project of een prikbord-briefje). De scheduler hervat
        het zodra `on_id` klaar is. Done-projecten blijven ongemoeid."""
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "blocked"
        p["blocked_on"] = need or "wacht"
        p["waiting_on"] = on_id or None
        self._touch(p)
        self._save()
        return True

    def link(self, a: str, b: str) -> bool:
        """Verbind twee projecten tot een keten/gesprek (wederzijds, zoals de notes-graaf). Geen
        zelf-link, dedup. Geeft True als er iets is bijgekomen."""
        if a == b:
            return False
        pa, pb = self._projects.get(a), self._projects.get(b)
        if pa is None or pb is None:
            return False
        changed = False
        for x, y in ((pa, b), (pb, a)):
            x.setdefault("links", [])
            if y not in x["links"]:
                x["links"].append(y); changed = True
        if changed:
            self._save()
        return changed

    def neighbors(self, pid: str) -> list[dict]:
        """De direct gelinkte projecten (beide richtingen), oudste eerst."""
        p = self._projects.get(pid)
        if p is None:
            return []
        ids = set(p.get("links", []))
        for q in self._projects.values():
            if pid in q.get("links", []):
                ids.add(q["id"])
        ids.discard(pid)
        return sorted((self._projects[i] for i in ids if i in self._projects),
                      key=lambda q: q.get("created_at", 0))

    def mark_formalized(self, pid: str) -> bool:
        """Markeer een experiment als 'voorgesteld om te stollen' (accountability op de agenda).
        Voorkomt dat hetzelfde experiment tweemaal wordt voorgedragen."""
        p = self._projects.get(pid)
        if p is None:
            return False
        p["formalized"] = True
        self._touch(p)
        self._save()
        return True

    def to_future(self, pid: str) -> bool:
        """Park een project als 'future' (later oppakken als er ruimte is). Niet-terminaal:
        het kan later weer naar running/blocked. Done-projecten blijven done."""
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "future"
        p["blocked_on"] = None
        self._touch(p)
        self._save()
        return True

    # ── lezen ──────────────────────────────────────────────────────────────────

    def get(self, pid: str) -> dict | None:
        self._maybe_reload()
        return self._projects.get(pid)

    def all(self) -> list[dict]:
        self._maybe_reload()
        return list(self._projects.values())

    def by_status(self, status: str) -> list[dict]:
        self._maybe_reload()
        return [p for p in self._projects.values() if p["status"] == status]

    def open(self) -> list[dict]:
        self._maybe_reload()
        return [p for p in self._projects.values() if p["status"] not in _TERMINAL]
