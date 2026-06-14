"""HumanInbox — de geauthenticeerde wachtrij voor menselijke beslissingen.

Twee item-typen:
  "escalation"  — governance-voorstel dat G1-G4 niet passeerde; wacht op
                  approve / reject / amend / defer van de mens.
  "activation"  — sensed onbemande rol; wacht op green-light van de mens
                  zodat de implementatie geschreven en geregistreerd kan worden.

Beveiligingsgrens (ingebakken):
  Approvals en zeker activaties mogen UITSLUITEND op het geauthenticeerde lokale
  oppervlak bevestigd worden. Geen extern of ongeauthenticeerd kanaal mag een
  approval triggeren. Notificatie (mail/bericht) is altijd alleen een heads-up
  met context — nooit een approve-knop.

State in data/human_inbox.json (gitignored met de rest van data/).
"""
from __future__ import annotations
import json, os, time, uuid
from datetime import datetime
from nooch_village.util import atomic_write_json


_VALID_STATUSES = {"pending", "approved", "rejected", "amended", "deferred"}
_VALID_TYPES    = {"escalation", "activation"}


class HumanInbox:
    """Persistente wachtrij voor menselijke beslissingen."""

    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                self._items = json.load(open(self.path))
            except Exception:
                self._items = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        atomic_write_json(self.path, self._items)

    # ── schrijven ─────────────────────────────────────────────────────────────

    def add_escalation(self, proposal_dict: dict, gate: str, reason: str) -> str:
        """Voeg een escalatie-item toe vanuit governance_review_requested.

        Duplicaatcheck op proposal_id: als het voorstel al in de inbox staat
        (ongeacht status) wordt geen nieuw item aangemaakt.
        Retourneert het item-id.
        """
        pid = proposal_dict.get("id", "?")
        for item in self._items.values():
            if (item["type"] == "escalation"
                    and item.get("context", {}).get("proposal_id") == pid):
                return item["id"]   # al aanwezig

        iid = uuid.uuid4().hex[:12]
        change = proposal_dict.get("change", {})
        self._items[iid] = {
            "id":         iid,
            "type":       "escalation",
            "subject":    change.get("role_id") or proposal_dict.get("proposer_role", "?"),
            "context": {
                "proposal_id":   pid,
                "proposer_role": proposal_dict.get("proposer_role"),
                "change_kind":   change.get("kind"),
                "purpose":       change.get("purpose"),
                "add_accountabilities": change.get("add_accountabilities", []),
                "add_domains":   change.get("add_domains", []),
                "tension":       proposal_dict.get("tension"),
                "trigger_example": proposal_dict.get("trigger_example"),
                "rationale":     proposal_dict.get("rationale"),
                "gate":          gate,
                "gate_reason":   reason,
            },
            "status":     "pending",
            "created_at": time.time(),
            "resolved_at": None,
            "resolution": None,
        }
        self._save()
        return iid

    def add_activation(self, role_id: str, record: dict) -> str:
        """Voeg een activatie-item toe voor een onbemande sensed-rol.

        Duplicaatcheck op role_id: als de activatie al pending of approved is,
        wordt geen nieuw item aangemaakt.
        Retourneert het item-id.
        """
        for item in self._items.values():
            if (item["type"] == "activation"
                    and item.get("subject") == role_id
                    and item["status"] in ("pending", "approved")):
                return item["id"]

        defn = record.get("definition", {})
        iid  = uuid.uuid4().hex[:12]
        self._items[iid] = {
            "id":      iid,
            "type":    "activation",
            "subject": role_id,
            "context": {
                "role_id":    role_id,
                "source":     record.get("source"),
                "purpose":    defn.get("purpose"),
                "accountabilities": defn.get("accountabilities", []),
                "domains":    defn.get("domains", []),
                "current_skills": defn.get("skills", []),
                # Wat schrijven en draaien zou worden bij een approve:
                "activation_plan": _derive_activation_plan(role_id, defn),
            },
            "status":     "pending",
            "created_at": time.time(),
            "resolved_at": None,
            "resolution": None,
        }
        self._save()
        return iid

    def resolve(self, item_id: str, action: str,
                reason: str = "", amendment: str = "") -> bool:
        """Registreer een beslissing op een item.

        action: "approved" | "rejected" | "amended" | "deferred"
        Retourneert False als het item niet bestaat of al gesloten is.
        """
        if action not in _VALID_STATUSES - {"pending"}:
            raise ValueError(f"ongeldige actie: '{action}'")
        item = self._items.get(item_id)
        if item is None:
            return False
        if item["status"] != "pending":
            return False   # al gesloten
        item["status"]      = action
        item["resolved_at"] = time.time()
        item["resolution"]  = {
            "action":    action,
            "reason":    reason,
            "amendment": amendment,
        }
        self._save()
        return True

    # ── lezen ─────────────────────────────────────────────────────────────────

    def pending(self) -> list[dict]:
        return [i for i in self._items.values() if i["status"] == "pending"]

    def all(self) -> list[dict]:
        return list(self._items.values())

    def get(self, item_id: str) -> dict | None:
        return self._items.get(item_id)

    def sync_unmanned(self, records_all: list, class_map: dict) -> int:
        """Voeg activatie-items toe voor elke sensed, onbemande rol zonder CLASS_MAP.

        Wordt aangeroepen bij opstarten en na governance_changed.
        Retourneert het aantal nieuw toegevoegde items.
        """
        added = 0
        for rec in records_all:
            if rec.archived:
                continue
            if rec.source != "sensed":
                continue
            if rec.id in class_map:
                continue
            # Actieve skills → beheer via Reconciler; hoeft niet in de inbox
            if rec.definition.skills:
                continue
            import dataclasses
            rec_dict = dataclasses.asdict(rec)
            rec_dict["type"] = rec.type.value
            iid = self.add_activation(rec.id, rec_dict)
            if self._items[iid]["status"] == "pending":
                added += 1
        return added


def _derive_activation_plan(role_id: str, defn: dict) -> dict:
    """Leidt af wat er geschreven en geregistreerd zou moeten worden.

    Dit is een gestructureerde beschrijving voor de mens — geen code.
    De mens keurt dit plan goed; daarna schrijft de ontwikkelaar de code
    per hand en laat die de normale code-review passeren.
    """
    accs = defn.get("accountabilities", [])
    purpose = defn.get("purpose", "")

    # Detecteer welke externe bronnen in de accountabilities vermeld worden
    sources: list[str] = []
    src_map = {
        "openlibrary":        "OpenLibrary Search Inside",
        "open library":       "OpenLibrary Search Inside",
        "semantic scholar":   "Semantic Scholar",
        "openAlex":           "OpenAlex",
        "openalex":           "OpenAlex",
        "google books":       "Google Books Ngram",
        "ngram":              "Google Books Ngram",
        "google search":      "Google Search Console",
        "gsc":                "Google Search Console",
        "plausible":          "Plausible Analytics",
        "google trends":      "Google Trends",
    }
    combined = (purpose + " " + " ".join(accs)).lower()
    for key, label in src_map.items():
        if key in combined and label not in sources:
            sources.append(label)

    class_name = "".join(w.capitalize() for w in role_id.split("_"))

    skills = []
    for src in sources:
        skill_id = src.lower().replace(" ", "_").replace("-", "_")
        skills.append({
            "skill_id":   skill_id,
            "label":      src,
            "file":       f"nooch_village/skills_impl/{skill_id}.py",
            "class_name": "".join(w.capitalize() for w in skill_id.split("_")) + "Skill",
        })

    return {
        "class_name":      class_name,
        "class_file":      f"nooch_village/roles.py (toevoegen als subklasse van Inhabitant)",
        "skills_to_write": skills,
        "class_map_entry": f'"{role_id}": {class_name}',
        "register_skills": [s["skill_id"] for s in skills],
        "note": (
            "Approval hier green-light de implementatie; de code zelf passeert "
            "daarna nog de normale per-edit code-review voordat hij commit en draait."
        ),
    }
