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
_VALID_TYPES    = {"escalation", "activation", "keyword", "means_gap", "suggestion",
                   "keyword_batch", "verband", "content_suggestion", "content_draft"}


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
                "proposal":      proposal_dict,  # volledige serialisatie voor reconstruct bij approve
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

        Duplicaatcheck op role_id ongeacht status: een eenmaal afgewezen of
        goedgekeurde activatie keert nooit terug als nieuw item (zoals means_gap).
        Retourneert het item-id.
        """
        for item in self._items.values():
            if (item["type"] == "activation"
                    and item.get("subject") == role_id):
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

    def add_means_gap(self, gap_key: str, description: str,
                      role_id: str | None = None) -> str:
        """Voeg een means-gap-item toe voor een structurele capaciteitsgrens.

        Routeert reflects die NIET via de governance-gate gaan (geen amend_role-voorstel).
        Duplicaatcheck op gap_key (subject), ongeacht status: eenmaal gemeld, altijd stil.
        role_id is de rol met het mandaat maar zonder de skill (B-uitkomst classify_gap).
        Retourneert het item-id.
        """
        for item in self._items.values():
            if item["type"] == "means_gap" and item.get("subject") == gap_key:
                return item["id"]

        iid = uuid.uuid4().hex[:12]
        self._items[iid] = {
            "id":         iid,
            "type":       "means_gap",
            "subject":    gap_key,
            "context":    {"gap_key": gap_key, "description": description,
                           "role_id": role_id},
            "status":     "pending",
            "created_at": time.time(),
            "resolved_at": None,
            "resolution":  None,
        }
        self._save()
        return iid

    def add_suggestion(self, gap_key: str, description: str) -> str:
        """Voeg een placeholder-suggestie toe voor een C-gap (geen mandaatdekking).

        Dedup op gap_key ongeacht status — eenmaal gesignaleerd, altijd stil.
        Dit is een inspectie-item, GEEN geboorte-aanvraag.
        Retourneert het item-id.
        """
        for item in self._items.values():
            if item["type"] == "suggestion" and item.get("subject") == gap_key:
                return item["id"]

        iid = uuid.uuid4().hex[:12]
        self._items[iid] = {
            "id":      iid,
            "type":    "suggestion",
            "subject": gap_key,
            "context": {
                "gap_key":     gap_key,
                "description": description,
                "note": (
                    "Suggestie: geen bestaande rol dekt dit mandaat. "
                    "Kandidaat voor een nieuw voorstel — ter inspectie, "
                    "geen automatische geboorte."
                ),
            },
            "status":     "pending",
            "created_at": time.time(),
            "resolved_at": None,
            "resolution":  None,
        }
        self._save()
        return iid

    def add_keyword_batch(self, market: str, tier: str,
                          candidates: list[str], estimated_credits: int,
                          geo: str | None = None, locale: str | None = None) -> str:
        """Voeg een keyword-batch-item toe ter goedkeuring door de mens.

        `geo` is de keywords_everywhere country-param waarin gemeten wordt (default: market).
        `locale` labelt de taal van de batch zodat dat label tot in keyword_proposed klopt.
        Bij een per-taal-batch is market gelijk aan de geo en is locale gezet.

        Dedup op {locale}/{market}/{tier} bij status pending (zonder locale: {market}/{tier}):
        dezelfde batch wordt niet tweemaal toegevoegd zolang hij nog open staat. Na afsluiten
        mag dezelfde batch opnieuw. Retourneert het item-id.
        """
        dedup_key = f"{locale}/{market}/{tier}" if locale else f"{market}/{tier}"
        for item in self._items.values():
            if (item["type"] == "keyword_batch"
                    and item.get("subject") == dedup_key
                    and item["status"] == "pending"):
                return item["id"]

        iid = uuid.uuid4().hex[:12]
        self._items[iid] = {
            "id":      iid,
            "type":    "keyword_batch",
            "subject": dedup_key,
            "context": {
                "market":            market,
                "geo":               geo or market,
                "locale":            locale,
                "tier":              tier,
                "candidates":        candidates,
                "estimated_credits": estimated_credits,
            },
            "status":     "pending",
            "created_at": time.time(),
            "resolved_at": None,
            "resolution":  None,
        }
        self._save()
        return iid

    def add_keyword_escalation(self, word: str, reason: str, demand: dict) -> str:
        """Voeg een keyword-escalatie-item toe vanuit human_decision_needed.

        Duplicaatcheck op word + status pending: hetzelfde woord wordt niet tweemaal
        toegevoegd zolang het nog open staat.
        Retourneert het item-id.
        """
        for item in self._items.values():
            if (item["type"] == "keyword"
                    and item.get("subject") == word
                    and item["status"] == "pending"):
                return item["id"]

        iid = uuid.uuid4().hex[:12]
        self._items[iid] = {
            "id":      iid,
            "type":    "keyword",
            "subject": word,
            "context": {
                "word":   word,
                "reason": reason,
                "demand": demand or {},
            },
            "status":     "pending",
            "created_at": time.time(),
            "resolved_at": None,
            "resolution": None,
        }
        self._save()
        return iid

    def add_verband(self, kaart_a_id: str, kaart_b_id: str,
                    voorstel_claim: str, reason: str = "") -> str:
        """Voeg een verband-voorstel toe: een door de scientist gesuggereerd verband
        tussen twee kaartjes, dat de mens kan goedkeuren (touwtje schrijven, 3c) of
        afwijzen. Dedup op het ongeordende paar, ongeacht status: eenmaal beslist,
        altijd stil. Retourneert het item-id."""
        subject = "|".join(sorted([kaart_a_id, kaart_b_id]))
        for item in self._items.values():
            if item["type"] == "verband" and item.get("subject") == subject:
                return item["id"]

        iid = uuid.uuid4().hex[:12]
        self._items[iid] = {
            "id":      iid,
            "type":    "verband",
            "subject": subject,
            "context": {
                "kaart_a_id":     kaart_a_id,
                "kaart_b_id":     kaart_b_id,
                "voorstel_claim": voorstel_claim,
                "reason":         reason,
            },
            "status":     "pending",
            "created_at": time.time(),
            "resolved_at": None,
            "resolution":  None,
        }
        self._save()
        return iid

    def add_content_suggestion(self, seed_id: str, cluster_ids: list[str],
                               reason: str = "") -> str:
        """Een gespotte content-kans: dit cluster verdient een publiek stuk. De mens
        keurt goed (-> draft) of wijst af. Dedup op seed_id, ongeacht status: eenmaal
        voorgesteld, niet opnieuw. Retourneert het item-id."""
        for item in self._items.values():
            if item["type"] == "content_suggestion" and item.get("subject") == seed_id:
                return item["id"]
        iid = uuid.uuid4().hex[:12]
        self._items[iid] = {
            "id": iid, "type": "content_suggestion", "subject": seed_id,
            "context": {"seed_id": seed_id, "cluster_ids": list(cluster_ids),
                        "reason": reason},
            "status": "pending", "created_at": time.time(),
            "resolved_at": None, "resolution": None,
        }
        self._save()
        return iid

    def add_content_draft(self, seed_id: str, kind: str, text: str,
                          claim_insight_ids: list[str]) -> str:
        """Een gegenereerde eerste draft, klaar voor de mens om te herschrijven. Dedup
        op seed_id + kind, ongeacht status. Retourneert het item-id."""
        subject = f"{seed_id}/{kind}"
        for item in self._items.values():
            if item["type"] == "content_draft" and item.get("subject") == subject:
                return item["id"]
        iid = uuid.uuid4().hex[:12]
        self._items[iid] = {
            "id": iid, "type": "content_draft", "subject": subject,
            "context": {"seed_id": seed_id, "kind": kind, "text": text,
                        "claim_insight_ids": list(claim_insight_ids)},
            "status": "pending", "created_at": time.time(),
            "resolved_at": None, "resolution": None,
        }
        self._save()
        return iid

    def resolve(self, item_id: str, action: str,
                reason: str = "", amendment: str = "",
                extra: dict | None = None) -> bool:
        """Registreer een beslissing op een item.

        action: "approved" | "rejected" | "amended" | "deferred"
        extra: optionele aanvullende velden in het resolution-object
               (bijv. skill_added, rationale, resolved_by voor means_gap).
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
            **(extra or {}),
        }
        self._save()
        return True

    # ── voorstel tot sluiten (rol stelt voor, mens bevestigt) ──────────────────

    def find_by_gap(self, gap_key: str) -> str | None:
        """Vind het pending-item met deze gap_key (suggestion/means_gap). None als geen."""
        for it in self._items.values():
            if it["status"] == "pending" and it.get("context", {}).get("gap_key") == gap_key:
                return it["id"]
        return None

    def propose_resolution(self, item_id: str, by: str, reason: str) -> bool:
        """Een rol stelt voor dit item te sluiten omdat hij de accountability nu dekt.
        Status blijft pending; de mens bevestigt met confirm_resolution. Zo blijft de
        onafhankelijke check intact (het systeem sluit z'n eigen item niet). False als geen
        pending item."""
        it = self._items.get(item_id)
        if it is None or it["status"] != "pending":
            return False
        it["proposed_resolution"] = {"by": by, "reason": reason, "at": time.time()}
        self._save()
        return True

    def confirm_resolution(self, item_id: str, by_human: str = "mens") -> bool:
        """De mens bevestigt een voorgestelde sluiting met één klik → item resolved (approved).
        False als er geen voorstel tot sluiten op het item staat."""
        it = self._items.get(item_id)
        if it is None or it["status"] != "pending":
            return False
        pr = it.get("proposed_resolution")
        if not pr:
            return False
        return self.resolve(
            item_id, "approved",
            reason=f"{pr['reason']} (voorgesteld door {pr['by']}, bevestigd door {by_human})",
            extra={"confirmed_by": by_human, "proposed_by": pr["by"]},
        )

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
