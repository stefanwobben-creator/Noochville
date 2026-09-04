"""ProjectLedger — de proces-store: volgt de status van lopend en gepland werk.

Opslag: data/projects.json (atomic write). Elke entry is een project-record:
  id, owner, scope, trigger, status, blocked_on, created_at, updated_at, outcome.
Governance-records en human_inbox blijven ongemoeid.
"""
from __future__ import annotations
import os, re, time, uuid
from nooch_village.util import atomic_write_json, read_json, synchronized as _synchronized

# MODELWIJZIGING (scope harry_hemp keyword_research): 'role' toegevoegd als geldige trigger voor een
# project dat een ROL autonoom initieert (niet 'human'/UI, niet 'clock'/puls, niet 'tension', niet
# 'noochie'/assistent). Eerste gebruiker: HarryHemp._on_keyword_decided.
# De titel van de checklist die de daemon als uitvoerplan herkent (prep schrijft 'm, _execute_checklist
# draait 'm). Eén authoritatieve bron: Inhabitant._PREP_CHECKLIST_TITLE en de cockpit-match verwijzen
# hiernaar (reference, don't copy) i.p.v. de literal "Uitvoerplan" te herhalen.
PREP_CHECKLIST_TITLE = "Uitvoerplan"

_VALID_TRIGGERS = {"clock", "human", "noochie", "tension", "role"}
_TERMINAL       = {"done"}
# Optionele impact-labels: een hulpmiddel, geen verplichting. Leeg = ongelabeld en dwingt niets af (een
# ongelabeld project mag elke statuswissel maken). De guard weigert alleen een niet-lege ongeldige waarde.
_MISSIE_IMPACT   = {"versterkt", "neutraal", "verzwakt"}
_BUSINESS_IMPACT = {"hoog", "medium", "laag"}
# effort (optionele inschatting): vervangt op termijn de #effort-hashtag-conventie (bestaande hashtags
# worden in deze scope NIET gemigreerd). Leeg = geen inschatting.
_EFFORT          = {"1u", "1d", "2d", "1w"}


class ProjectLedger:

    def __init__(self, path: str):
        self.path = path
        self._projects: dict[str, dict] = {}
        self._mtime: float = 0.0
        self._load()

    def _load(self) -> None:
        self._projects = read_json(self.path, {})
        if os.path.exists(self.path):
            self._mtime = os.path.getmtime(self.path)

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
        if os.path.exists(self.path):
            self._mtime = os.path.getmtime(self.path)   # in-memory mtime bij → geen spurious _maybe_reload

    def _touch(self, project: dict) -> None:
        project["updated_at"] = time.time()

    # ── schrijven ──────────────────────────────────────────────────────────────

    def create(self, owner: str, scope, trigger: str,
               hypothesis: str = "", business_case: dict | None = None,
               status: str = "queued", origin: str = "",
               dod_outcome: str = "", done_when: str = "", goes_to: str = "",
               links: list[str] | None = None, parent: str | None = None,
               opdrachtgever: str = "",
               person: str | None = None, agent: str | None = None,
               private: bool = False, description: str = "", label: str = "",
               missie_impact: str = "", business_impact: str = "", effort: str = "",
               keyword: str = "") -> str:
        if trigger not in _VALID_TRIGGERS:
            raise ValueError(f"ongeldig trigger: '{trigger}'")
        if status not in ("queued", "draft", "future", "proposed"):
            raise ValueError(f"ongeldige start-status: '{status}'")
        if missie_impact and missie_impact not in _MISSIE_IMPACT:
            raise ValueError(f"ongeldige missie_impact: '{missie_impact}'")
        if business_impact and business_impact not in _BUSINESS_IMPACT:
            raise ValueError(f"ongeldige business_impact: '{business_impact}'")
        if effort and effort not in _EFFORT:
            raise ValueError(f"ongeldige effort: '{effort}'")
        pid = uuid.uuid4().hex[:12]
        now = time.time()
        # Cluster-lidmaatschap: een kind erft de cluster-root van zijn ouder (master-switch werkt
        # zo op de hele keten). Geen ouder → eigen cluster (root/standalone).
        par = self._projects.get(parent) if parent else None
        cluster = (par.get("cluster") or parent) if par else pid
        self._projects[pid] = {
            "id":         pid,
            "owner":      owner,            # rol- of cirkel-id (GlassFrog: project hoort bij een rol/cirkel)
            "person":     person,           # optioneel: de mens die het project trekt
            "agent":      agent,            # optioneel: AI-inwoner (persona-id) als trekker (beter dan GlassFrog)
            "private":    bool(private),    # 'alleen zichtbaar voor de cirkel' (GlassFrog-zichtbaarheid)
            "description": description or "",  # omschrijving (kaartdetail)
            "label":      label or "",      # kleurlabel (koppeling met organisatiedoel, later)
            "missie_impact":   missie_impact or "",    # optioneel: versterkt/neutraal/verzwakt (leeg = ongelabeld)
            "business_impact": business_impact or "",  # optioneel: hoog/medium/laag (leeg = ongelabeld)
            "effort":          effort or "",           # optioneel: 1u/1d/2d/1w (leeg = geen inschatting)
            "checklist":  [],               # [{id, text, done}] — één checklist per project
            "archived":   False,            # gearchiveerd = blijft bestaan, uit het actieve zicht
            "scope":      scope,
            "trigger":    trigger,
            "status":     status,
            "blocked_on": None,
            "created_at": now,
            "updated_at": now,
            "outcome":    None,              # geleverde eind-uitkomst (gevuld bij done)
            "hypothesis":    hypothesis or "",
            "business_case": business_case,
            "origin":     origin or "",      # "experiment" = stolt later tot accountability bij herhaling;
            #                                  "keyword_research" = autonoom door een rol aangemaakt
            "keyword":    keyword or "",      # gestructureerd + opvraagbaar bronwoord (dedup-sleutel bij keyword_research)
            "executions": 0,                 # hoe vaak een rol dit experiment heeft uitgevoerd
            "formalized": False,             # al voorgesteld als accountability? (dedup)
            "comments":   [],                # stuur-opmerkingen van de mens (de rol leest ze mee)
            "log":        [],                # gesprek: {who: 'mens'|'rol', text, at} — chat-weergave
            # DoD-contract: de rol weet hiermee wanneer hij klaar is (docs/ONTWERP_prikbord_kanban.md)
            "dod_outcome": dod_outcome or "",   # gewenste uitkomst in één zin
            "done_when":   done_when or "",     # checkbaar criterium (lege/nee-uitkomst telt ook)
            "goes_to":     goes_to or "",       # wie de uitkomst consumeert (rol/bord/mens)
            "links":       list(links or []),   # verwante projecten (de keten/het gesprek)
            "attachments": [],                  # verrijking-cards: links/bijlagen (Trello-stijl)
            "due":         None,                # deadline (ISO datum 'YYYY-MM-DD'), optioneel
            "parent":      parent,              # ouder-project (None = root/standalone)
            # WIE HET VROEG. Zonder dit is een taak die een rol voor je oppakt een eenrichtingsweg:
            # het werk gebeurt, en de opdrachtgever hoort er nooit meer iets van. Dit veld is de
            # enige plek waar die lus aan hangt (`_meld_opdrachtgever`).
            "opdrachtgever": opdrachtgever or "",
            "cluster":     cluster,             # cluster-root id (master-switch werkt hierop)
            "waiting_on":  None,                # project/briefje waarop dit wacht (resume-trigger)
        }
        self._save()
        return pid

    def open_scopes(self) -> set:
        """Scopes van niet-afgeronde projecten (voor dedup van kans-voorstellen)."""
        return {str(p.get("scope")) for p in self._projects.values()
                if p.get("status") not in _TERMINAL}

    def active(self) -> list:
        """Alle niet-afgeronde projecten (status niet terminal) — de scan-lijst voor Noochie's nudge."""
        return [p for p in self._projects.values() if p.get("status") not in _TERMINAL]

    def already_scope_nudged(self, pid: str, role_id: str) -> bool:
        """Heeft Noochie deze rol al eens voor dit project genudged? (dedup, geen herhaal-nudge)."""
        p = self._projects.get(pid)
        return bool(p) and role_id in (p.get("scope_nudges") or [])

    def mark_scope_nudge(self, pid: str, role_id: str) -> None:
        """Leg vast dat Noochie deze rol voor dit project heeft genudged (idempotent, persistent)."""
        p = self._projects.get(pid)
        if p is None:
            return
        lst = p.setdefault("scope_nudges", [])
        if role_id not in lst:
            lst.append(role_id)
            self._touch(p)
            self._save()

    # ── Het oordeel van de scope-nudge: onthouden wat er al beoordeeld is ────────────────────
    #
    # DE VLOER VOOR DE DUURSTE LLM-POST VAN HET DORP. `scope_nudge_match` was 3150 van de 8478
    # calls (37%) en leverde 165 nudges op — 5,2%. Gemeten oorzaak: de lus vraagt het model élke
    # puls opnieuw over ELK actief project, terwijl er per dag maar 2% van die projecten verandert
    # (7 van de 332 in 24 uur). Hetzelfde project, dezelfde tekst, dezelfde rollen, elke dag weer
    # dezelfde vraag.
    #
    # Dit is de vorm van `kennis_dedup`: een deterministische vloer waar het kan, het model alleen
    # voor wat de vloer niet kan uitsluiten. Hier is de vloer een vingerafdruk van de INVOER —
    # projecttekst plus de kandidaat-rollen met hun skills en accountabilities. Verandert er niets
    # aan de invoer, dan verandert het antwoord ook niet.
    #
    # FAIL-OPEN, en dat is hier de gevaarlijke kant: een vingerafdruk die wordt weggeschreven na een
    # call die NIET beantwoord werd (model weg, quota op) zou 'geen match' vastzetten tot iemand het
    # project aanraakt. De aanroeper schrijft daarom alleen als het model echt antwoordde.

    def scope_nudge_checked(self, pid: str) -> str:
        """De vingerafdruk van de invoer waarop dit project het laatst beoordeeld is ('' = nooit)."""
        p = self._projects.get(pid)
        return str((p or {}).get("scope_nudge_check") or "")

    def mark_scope_nudge_checked(self, pid: str, vinger: str) -> None:
        """Leg vast dat deze invoer beoordeeld is. Geen `_touch`: dit is machine-onderhoud, geen
        wijziging aan het project — zou het `updated_at` bumpen, dan zou de nudge-lus zichzelf
        eeuwig als 'veranderd' zien en was de vloer meteen weer weg."""
        p = self._projects.get(pid)
        if p is None or not vinger:
            return
        if p.get("scope_nudge_check") != vinger:
            p["scope_nudge_check"] = vinger
            self._save()

    def start(self, pid: str) -> bool:
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "running"
        p["blocked_on"] = None
        self._touch(p)
        self._save()
        return True

    def set_due(self, pid: str, due: str) -> bool:
        """Zet of wis de deadline (ISO 'YYYY-MM-DD'); lege string wist 'm."""
        p = self._projects.get(pid)
        if p is None:
            return False
        p["due"] = (due or "").strip() or None
        self._touch(p)
        self._save()
        return True

    def set_dod(self, pid: str, veld: str, tekst: str) -> bool:
        """Zet een DoD-contractveld: 'done_when' (waar herken je aan dat dit klaar is) of
        'dod_outcome' (het antwoord op de projectvraag bij afronding). Onderdeel van de
        projectpoort (founder, 19 jul): done = vraag beantwoord, niet werk gedaan."""
        p = self._projects.get(pid)
        if p is None or veld not in ("done_when", "dod_outcome"):
            return False
        p[veld] = (tekst or "").strip()[:1000]
        self._touch(p)
        self._save()
        return True

    def add_reaction(self, pid: str, entry_id: str, emoji: str) -> bool:
        """Voeg een emoji-reactie toe aan een feed-entry (per emoji een teller). Alleen entries met
        een id (nieuw schema) kunnen reacties dragen."""
        p = self._projects.get(pid)
        emoji = (emoji or "").strip()
        if p is None or not emoji or not entry_id:
            return False
        for entry in p.get("log", []):
            if entry.get("id") == entry_id:
                r = entry.setdefault("reactions", {})
                r[emoji] = int(r.get(emoji, 0)) + 1
                self._touch(p)
                self._save()
                return True
        return False

    def attach_add(self, pid: str, url: str = "", title: str = "", kind: str = "link") -> dict | None:
        """Voeg een verrijking-card toe (Trello-stijl bijlage). Nu: een link met optionele titel.
        Geeft de toegevoegde card terug."""
        p = self._projects.get(pid)
        url = (url or "").strip()
        if p is None or not url:
            return None
        card = {"id": uuid.uuid4().hex[:10], "kind": kind, "url": url[:500],
                "title": (title or "").strip()[:200], "at": time.time()}
        p.setdefault("attachments", []).append(card)
        self._touch(p)
        self._save()
        return card

    def attach_file(self, pid: str, name: str, stored: str, title: str = "") -> dict | None:
        """Registreer een geupload bestand (het bestand zelf is al weggeschreven door de handler).
        `stored` = pad relatief aan de data-map."""
        p = self._projects.get(pid)
        if p is None or not stored:
            return None
        card = {"id": uuid.uuid4().hex[:10], "kind": "file", "name": (name or "bestand")[:200],
                "stored": stored, "title": (title or "").strip()[:200], "at": time.time()}
        p.setdefault("attachments", []).append(card)
        self._touch(p)
        self._save()
        return card

    def attach_remove(self, pid: str, aid: str) -> bool:
        p = self._projects.get(pid)
        if p is None:
            return False
        lst = p.get("attachments", [])
        for c in list(lst):
            if c.get("id") == aid:
                lst.remove(c)
                self._touch(p)
                self._save()
                return True
        return False

    def reopen(self, pid: str) -> bool:
        """Heropen een afgerond project: haal 'done' eraf zodat het weer naar actief/wacht/toekomst
        kan. No-op als het project niet bestaat of niet afgerond is."""
        p = self._projects.get(pid)
        if p is None or p["status"] not in _TERMINAL:
            return False
        p["status"] = "running"
        p["outcome"] = None
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
        p.pop("park", None)                             # de blokkade is opgeheven; de reden vervalt mee
        self._touch(p)
        self._save()
        return True

    # ── de duurzame park-reden ───────────────────────────────────────────────
    # Waaróm een project geparkeerd staat was tot nu toe alleen af te leiden uit de fail-teller van
    # de items — en juist bij het parkeren zet `reset_item_fails` die op nul. Daardoor is een item
    # dat drie keer faalde en toen gereset werd niet te onderscheiden van een item dat nooit draaide.
    # Zolang dat verschil weg is, is elke heropening en elke melding aan de mens een gok.
    #
    # Daarom een FEIT op het project, niet een afleiding uit item-state: wie het parkeerde, wanneer,
    # om welke reden, en om welke items. Het leeft op projectniveau, dus geen enkele item-operatie
    # (reset_item_fails voorop) raakt het aan.
    PARK_REDENEN = ("human", "payload", "fails", "gemengd")

    def park(self, pid: str, reden: str, items: list, *, door: str = "") -> bool:
        """Leg vast waaróm dit project geparkeerd is. `items` = [{id, text, reden}].

        `reden` is de zwaarste noemer over de items: 'gemengd' als er meer dan één soort in zit.
        Overschrijft een eerdere park-reden — de laatste parkering is de geldende."""
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        soorten = {str(i.get("reden") or "") for i in (items or [])} - {""}
        if reden not in self.PARK_REDENEN:
            reden = soorten.pop() if len(soorten) == 1 else "gemengd"
        p["park"] = {
            "reden": reden,
            "at": time.time(),
            "door": door or "",
            "items": [{"id": str(i.get("id") or ""), "text": str(i.get("text") or "")[:200],
                       "reden": str(i.get("reden") or "")} for i in (items or [])],
        }
        self._touch(p)
        self._save()
        return True

    def park_reden(self, pid: str) -> dict:
        """De vastgelegde park-reden, of {} als dit project niet (zo) geparkeerd is."""
        p = self._projects.get(pid)
        park = (p or {}).get("park")
        return dict(park) if isinstance(park, dict) else {}

    def complete(self, pid: str, outcome: str | None = None) -> bool:
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "done"
        p["outcome"] = outcome
        # blocked_on blijft bewust staan: een review-goedkeuring is 'done' MÉT blocked_on=="review".
        # De board-watch (village._poll_board) leest die marker om cross-proces project_completed te vuren.
        self._touch(p)
        self._save()
        return True

    def mark_awaiting_review(self, pid: str) -> bool:
        """Checklist volledig af → wacht-op-review: status=blocked, blocked_on='review', plus het
        PERSISTENTE `review_raised`-vlag (restart-bestendig; gewist bij elke checklist-mutatie). Dat vlag
        voorkomt dat een volgende puls herblokkeert nadat de review is afgewezen en de rol doorwerkt.
        GEEN outcome — die wordt pas bij Done-toekenning (mens sleept wacht→done) gezet."""
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["status"] = "blocked"
        p["blocked_on"] = "review"
        p["review_raised"] = True
        self._touch(p)
        self._save()
        return True

    # Named checklists (Trello-stijl, meervoudig): p["checklists"] = [{id,title,items:[{id,text,done}]}]
    def _checklists(self, p) -> list:
        return p.setdefault("checklists", [])

    def _checklist(self, p, clid):
        for cl in self._checklists(p):
            if cl.get("id") == clid:
                return cl
        return None

    def checklist_add(self, pid: str, title: str = "") -> dict | None:
        p = self._projects.get(pid)
        if p is None:
            return None
        cl = {"id": uuid.uuid4().hex[:8], "title": (title or "").strip()[:80] or "Checklist", "items": []}
        self._checklists(p).append(cl)
        p.pop("review_raised", None)                  # checklist-mutatie → review-vlag wissen (Q2)
        self._touch(p); self._save()
        return cl

    def checklist_remove(self, pid: str, clid: str) -> bool:
        p = self._projects.get(pid)
        if p is None:
            return False
        before = len(self._checklists(p))
        p["checklists"] = [cl for cl in self._checklists(p) if cl.get("id") != clid]
        if len(p["checklists"]) != before:
            p.pop("review_raised", None)              # checklist-mutatie → review-vlag wissen (Q2)
            self._touch(p); self._save()
            return True
        return False

    def check_add(self, pid: str, clid: str, text: str, *,
                  skill: str | None = None, query: str = "", reason: str = "",
                  payload: dict | None = None, payload_ok: bool = True,
                  human_task: bool = False) -> bool:
        p = self._projects.get(pid)
        text = (text or "").strip()
        cl = self._checklist(p, clid) if p else None
        if cl is None or not text:
            return False
        item = {"id": uuid.uuid4().hex[:8], "text": text[:200], "done": False}
        if skill:  item["skill"]  = skill            # uitvoer-primitief: welke skill dit item draait
        if isinstance(payload, dict) and payload:
            item["payload"] = payload                # de LLM-gevormde input, in de vorm van input_schema
        if query:  item["query"]  = query[:200]      # legacy back-compat (→ {term: query} bij uitvoer)
        if reason: item["reason"] = reason[:300]     # 'geen skill' of 'payload onvolledig' → waarom (blijft open)
        if not payload_ok:
            item["payload_ok"] = False               # payload mist een verplicht veld → niet uitvoerbaar
        if human_task:
            # Expliciete mens-taak: geen enkele skill kan dit ooit (fysiek/offline werk). Telt NIET
            # mee in de klaar-telling — anders houdt hij het project eeuwig onaf, en dat is precies
            # de zombie die we vóór zijn. Blijft wél zichtbaar staan als openstaand mens-werk.
            item["human_task"] = True
        cl.setdefault("items", []).append(item)
        p.pop("review_raised", None)                  # checklist-mutatie → review-vlag wissen (Q2)
        self._touch(p); self._save()
        return True

    def check_toggle(self, pid: str, clid: str, item_id: str) -> bool:
        p = self._projects.get(pid)
        cl = self._checklist(p, clid) if p else None
        if cl is None:
            return False
        for it in cl.get("items", []):
            if it["id"] == item_id:
                it["done"] = not it.get("done")
                p.pop("review_raised", None)          # checklist-mutatie → review-vlag wissen (Q2)
                self._touch(p); self._save()
                return True
        return False

    def clear_item_leeg(self, pid: str, clid: str, item_id: str) -> bool:
        """Haal de leeg-markering van een item af. Nodig bij een geslaagde HERdraai: het item
        leverde eerst niets op en nu wel, en zonder deze wis blijft het als kennisgat meetellen
        bij de missie-critic — een gat dat inmiddels gedicht is."""
        p = self._projects.get(pid)
        cl = self._checklist(p, clid) if p else None
        if cl is None:
            return False
        for it in cl.get("items", []):
            if it["id"] == item_id and it.get("leeg"):
                it.pop("leeg", None); it.pop("leeg_reden", None); it.pop("leeg_bron", None)
                self._touch(p); self._save()
                return True
        return False

    def mark_critic(self, pid: str, veld: str, waarde) -> bool:
        """Zet een critic-vlag op het project (`critic_herkansing`, `critic_verdict`).

        Eigen methode i.p.v. een generieke setter: een vrije set-any-field op de ledger is precies
        hoe een store zijn schema kwijtraakt. Deze twee velden zijn het contract van de
        missie-critic met de review-gate, en verder niets."""
        if veld not in ("critic_herkansing", "critic_verdict"):
            return False
        p = self._projects.get(pid)
        if p is None:
            return False
        p[veld] = waarde
        self._touch(p)
        self._save()
        return True

    def set_item_leeg(self, pid: str, clid: str, item_id: str, reden: str = "",
                      bron: str = "geen_inhoud") -> bool:
        """Markeer een item als UITGEVOERD-MAAR-LEEG: de skill draaide, er kwam niets uit.

        Zo'n item wordt wél afgevinkt (anders zou het project de review-gate nooit halen en eeuwig
        een lege bron herproberen), maar het is geen antwoord. Zonder deze markering leest 4/4 als
        'alles beantwoord' terwijl er vier kennisgaten staan — precies de valse voltooiing waar
        `not_answered_note` tegen bestaat."""
        p = self._projects.get(pid)
        cl = self._checklist(p, clid) if p else None
        if cl is None:
            return False
        for it in cl.get("items", []):
            if it["id"] == item_id:
                it["leeg"] = True
                # `bron` scheidt een ANTWOORD van een GAT: 'gemeld' = de skill zei zelf no_data
                # (onderzocht, niets gevonden — een geldige uitkomst); 'geen_inhoud' = hij gaf iets
                # terug waar niets in zat. Alleen het tweede is ontbrekende kennis.
                it["leeg_bron"] = "gemeld" if bron == "gemeld" else "geen_inhoud"
                if reden:
                    it["leeg_reden"] = str(reden)[:200]
                self._touch(p); self._save()
                return True
        return False

    def note_item_fail(self, pid: str, clid: str, item_id: str) -> int:
        """Tel een mislukte poging (skill-fout) op een checklist-item; returnt de nieuwe teller. De
        autonome worker gebruikt dit om na een grens níét eindeloos te herproberen maar het project op
        WAITING te zetten. 'leeg' (no-data) telt NIET als fout — die vinkt het item af."""
        p = self._projects.get(pid)
        cl = self._checklist(p, clid) if p else None
        if cl is None:
            return 0
        for it in cl.get("items", []):
            if it["id"] == item_id:
                it["fails"] = int(it.get("fails") or 0) + 1
                self._touch(p); self._save()
                return it["fails"]
        return 0

    def set_item_payload(self, pid: str, clid: str, item_id: str, payload: dict) -> bool:
        """Schrijf een herstelde payload terug en maak het item weer uitvoerbaar.

        Hoort bij de reparatiepas (`Inhabitant._herstel_payloads`): een onvolledige payload is een
        planfout van de rol, geen mens-werk. De aanroeper valideert vóór hij hier komt — deze
        methode schrijft alleen, ze oordeelt niet."""
        p = self._projects.get(pid)
        cl = self._checklist(p, clid) if p else None
        if cl is None or not isinstance(payload, dict) or not payload:
            return False
        for it in cl.get("items", []):
            if it["id"] == item_id:
                it["payload"] = payload
                it.pop("payload_ok", None)               # weer uitvoerbaar
                it.pop("reason", None)                   # de oude klacht is opgelost
                self._touch(p)
                self._save()
                return True
        return False

    def set_item_human(self, pid: str, clid: str, item_id: str, human: bool = True) -> bool:
        """Markeer één item alsnog als mens-/extern werk (of haal die markering weg).

        `check_add` kon dit alleen bij het aanmaken, en de planner ziet het niet altijd goed: een
        checklist waarin "ontwerp een testprotocol" en "voer 5 testrondes uit" naast elkaar staan is
        half rol-werk en half labwerk. Zonder deze setter is de enige uitweg het hele project naar
        de backlog schuiven, en dan verdwijnt ook het deel dat een rol wél kan oppakken.

        Een mens-taak telt niet mee in de klaar-telling (`_NIET_TELBAAR`) maar blijft zichtbaar
        openstaan — zo houdt het project geen zombie-status en raakt het werk niet zoek."""
        p = self._projects.get(pid)
        cl = self._checklist(p, clid) if p else None
        if cl is None:
            return False
        for it in cl.get("items", []):
            if it["id"] == item_id:
                if human:
                    it["human_task"] = True
                else:
                    it.pop("human_task", None)
                self._touch(p)
                self._save()
                return True
        return False

    def reset_item_fails(self, pid: str, clid: str, item_ids) -> None:
        """Zet de fail-teller van deze items terug op 0 — bij het naar-WAITING-zetten, zodat een
        reactivering door de mens (waiting → actief) weer een verse reeks pogingen krijgt."""
        p = self._projects.get(pid)
        cl = self._checklist(p, clid) if p else None
        if cl is None:
            return
        ids = set(item_ids or [])
        changed = False
        for it in cl.get("items", []):
            if it["id"] in ids and it.get("fails"):
                it["fails"] = 0
                changed = True
        if changed:
            self._touch(p); self._save()

    def set_item_skipped(self, pid: str, clid: str, item_id: str, skipped: bool = True,
                         reason: str = "") -> bool:
        """Zet (of wis) 'overgeslagen' op een checklist-item: n.v.t., vervalt, of elders belegd.

        Een overgeslagen item telt NIET meer mee in de klaar-telling (`checklist_progress`), zodat
        done == telbaar weer haalbaar wordt en het project kan afronden. Het item blijft wél staan
        met zijn reden — dit is een besluit met audittrail, geen verwijdering. Onderscheid met `done`:
        done = gedaan; skipped = hoeft niet (meer) gedaan te worden."""
        p = self._projects.get(pid)
        cl = self._checklist(p, clid) if p else None
        if cl is None:
            return False
        for it in cl.get("items", []):
            if it["id"] == item_id:
                if skipped:
                    it["skipped"] = True
                    if reason:
                        it["skip_reason"] = reason[:300]
                else:
                    it.pop("skipped", None)
                    it.pop("skip_reason", None)
                p.pop("review_raised", None)          # checklist-mutatie → review-vlag wissen (Q2)
                self._touch(p); self._save()
                return True
        return False

    def mark_item_routed(self, pid: str, clid: str, item_id: str) -> bool:
        """Markeer dat de escalatie-router dit item heeft beoordeeld. De garantie dat hij één keer
        per item vuurt: zonder deze vlag doet elke reactivering dezelfde LLM-call opnieuw op
        hetzelfde vastgelopen item."""
        p = self._projects.get(pid)
        cl = self._checklist(p, clid) if p else None
        if cl is None:
            return False
        for it in cl.get("items", []):
            if it["id"] == item_id:
                it["routed"] = True
                self._touch(p); self._save()
                return True
        return False

    def set_handoff_trail(self, pid: str, trail) -> bool:
        """Zet het handoff-spoor op een project: welke rollen dit werk al zagen.

        Op het PROJECT en niet op het item, want bij een overdracht krijgt de ontvangende rol een
        vers uitvoerplan met nieuwe item-id's — het spoor moet die herplanning overleven, anders is
        de hop-teller na één overdracht weer nul en kan het werk alsnog rondjes gaan draaien."""
        p = self._projects.get(pid)
        if p is None:
            return False
        p["handoff_trail"] = [r for r in (trail or []) if r]
        self._touch(p); self._save()
        return True

    def check_remove(self, pid: str, clid: str, item_id: str) -> bool:
        p = self._projects.get(pid)
        cl = self._checklist(p, clid) if p else None
        if cl is None:
            return False
        n = len(cl.get("items", []))
        cl["items"] = [it for it in cl.get("items", []) if it["id"] != item_id]
        if len(cl["items"]) != n:
            p.pop("review_raised", None)              # checklist-mutatie → review-vlag wissen (Q2)
            self._touch(p); self._save()
            return True
        return False

    def set_item_offer(self, pid: str, clid: str, item_id: str, offer: dict) -> bool:
        """Hang een STIL skill-aanbod aan een item: een suggestie (skill+payload), NOG geen skill. Alleen
        als het item nog geen skill heeft. `offer` = {skill, payload, payload_ok}. Accepteren gebeurt via
        accept_item_offer; negeren = afwijzen (het aanbod blijft staan tot acceptatie)."""
        p = self._projects.get(pid)
        cl = self._checklist(p, clid) if p else None
        if cl is None or not (offer or {}).get("skill"):
            return False
        for it in cl.get("items", []):
            if it["id"] == item_id and not it.get("skill"):
                pl = offer.get("payload")
                it["offer"] = {"skill": offer["skill"],
                               "payload": pl if isinstance(pl, dict) else {},
                               "payload_ok": bool(offer.get("payload_ok", True))}
                self._touch(p); self._save()
                return True
        return False

    def accept_item_offer(self, pid: str, clid: str, item_id: str) -> bool:
        """Accepteer het aanbod: hang skill+payload aan het item via het bestaande checklist-model en
        verwijder het aanbod. payload_ok=False (onvolledige payload) markeert het item als niet-uitvoerbaar
        (de daemon slaat het dan over) — identiek aan het prep-pad."""
        p = self._projects.get(pid)
        cl = self._checklist(p, clid) if p else None
        if cl is None:
            return False
        for it in cl.get("items", []):
            if it["id"] == item_id and it.get("offer"):
                off = it.pop("offer")
                it["skill"] = off.get("skill")
                pl = off.get("payload")
                if isinstance(pl, dict) and pl:
                    it["payload"] = pl
                if off.get("payload_ok") is False:
                    it["payload_ok"] = False
                p.pop("review_raised", None)          # checklist-mutatie → review-vlag wissen (Q2)
                self._touch(p); self._save()
                return True
        return False

    def edit(self, pid: str, scope=None, owner: str | None = None,
             person: str | None = None, agent: str | None = None,
             private: bool | None = None, description: str | None = None,
             label: str | None = None, missie_impact: str | None = None,
             business_impact: str | None = None, effort: str | None = None,
             allow_done: bool = False) -> bool:
        """Bewerk de inhoud van een project (scope, owner, trekker mens/AI, zichtbaarheid).
        Status blijft ongemoeid; done-projecten zijn standaard vergrendeld. Met `allow_done=True`
        mag je inhoud (titel/omschrijving/...) van een afgerond project nog aanpassen. Lege strings
        voor person/agent wissen de trekker; None laat het veld ongemoeid. Geeft True bij succes."""
        p = self._projects.get(pid)
        if p is None or (p["status"] in _TERMINAL and not allow_done):
            return False
        if scope is not None and str(scope).strip():
            p["scope"] = scope
        if owner is not None and str(owner).strip():
            p["owner"] = owner
        if person is not None:
            p["person"] = person or None
        if agent is not None:
            p["agent"] = agent or None
        if private is not None:
            p["private"] = bool(private)
        if description is not None:
            p["description"] = description
        if label is not None:
            p["label"] = label
        if missie_impact is not None:      # '' = ongelabeld (wissen); validatie op de actie/create-grens
            p["missie_impact"] = missie_impact
        if business_impact is not None:
            p["business_impact"] = business_impact
        if effort is not None:
            p["effort"] = effort
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

    def archive(self, pid: str) -> bool:
        """Archiveer een project: het blijft bestaan maar verdwijnt uit het actieve zicht."""
        p = self._projects.get(pid)
        if p is None:
            return False
        p["archived"] = True
        self._touch(p)
        self._save()
        return True

    def unarchive(self, pid: str) -> bool:
        p = self._projects.get(pid)
        if p is None:
            return False
        p["archived"] = False
        self._touch(p)
        self._save()
        return True

    def remove(self, pid: str) -> bool:
        """Verwijder een project definitief (GlassFrog: project deleten). Geeft True als verwijderd."""
        if pid in self._projects:
            del self._projects[pid]
            self._save()
            return True
        return False

    def drafts(self) -> list[dict]:
        """Concept-projecten die op jouw akkoord wachten (status draft)."""
        self._maybe_reload()
        return [p for p in self._projects.values() if p.get("status") == "draft"]

    # ── de voorstel-baan (status 'proposed') ───────────────────────────────────
    # Een voorstel is GEEN project op het bord: het is een vraag aan de mens. De status staat
    # daarom bewust buiten élke autonome lus — `activate_pulse` kijkt alleen naar future/blocked,
    # `_tend_projects` naar future/queued/running en `project_worker._eligible` naar queued/running.
    # Zo kan een voorstel niet stilletjes uitgevoerd, voorbereid of geactiveerd worden. De mens is
    # de enige poort. (tests/test_proposed_veiligheid.py bevriest die garantie.)

    def proposals(self) -> list[dict]:
        """Openstaande projectvoorstellen (status proposed), nieuwste eerst."""
        self._maybe_reload()
        return sorted((p for p in self._projects.values()
                       if p.get("status") == "proposed" and not p.get("archived")),
                      key=lambda p: p.get("created_at", 0), reverse=True)

    def accept_proposal(self, pid: str, *, person: str = "") -> bool:
        """De mens neemt een voorstel aan → het wordt een gewoon standalone root-project in
        TOEKOMST en gaat vanaf daar de normale flow in (de mens activeert het zelf; de bord-puls
        raakt root-projecten bewust niet aan). `person` = de mens die het aanneemt (de trekker)."""
        p = self._projects.get(pid)
        if p is None or p.get("status") != "proposed":
            return False
        p["status"] = "future"
        if person:
            p["person"] = person
        self._touch(p)
        self._save()
        return True

    def reject_proposal(self, pid: str) -> bool:
        """De mens wijst een voorstel af → weg van het bord. Dat het is afgewezen wordt onthouden
        in de voorstel-overlay (project_proposals.py), niet hier: het project verdwijnt, de
        herinnering blijft, zodat dezelfde bron nooit opnieuw hetzelfde voorstelt."""
        p = self._projects.get(pid)
        if p is None or p.get("status") != "proposed":
            return False
        del self._projects[pid]
        self._save()
        return True

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

    def mark_tended(self, pid: str, date_iso: str) -> bool:
        """Idempotentie-anker voor het uitvoer-primitief: leg vast dat de eigenaar-rol dit project op deze
        dag heeft uitgevoerd, zodat een tweede puls dezelfde dag het niet opnieuw oppakt (geen dubbele
        notes). Done-projecten blijven ongemoeid."""
        p = self._projects.get(pid)
        if p is None or p["status"] in _TERMINAL:
            return False
        p["last_tended"] = date_iso
        self._touch(p); self._save()
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

    def add_role_message(self, pid: str, text: str) -> str | None:
        """Voeg een DIRECT antwoord van de rol toe aan het gesprek (chat-reply op een opmerking).
        Anders dan record_progress telt dit NIET als een experiment-uitvoering en raakt het de
        'worked'-vlag niet — het is conversatie, geen puls-werk.

        Geeft het note-`id` terug (of None bij lege input) — het id-patroon van add_feed_entry, zodat
        een specifieke note adresseerbaar/linkbaar is (bijv. een deliverable-store die ernaar verwijst).
        Bestaande notes zonder id blijven geldig (geen migratie); lezers filteren op `who`/`text`, niet op id."""
        p = self._projects.get(pid)
        text = (text or "").strip()
        if p is None or not text:
            return None
        nid = uuid.uuid4().hex[:10]
        p.setdefault("log", []).append({"id": nid, "who": "rol", "text": text[:1500], "at": time.time()})
        p["progress"] = text
        self._touch(p)
        self._save()
        return nid

    # Gestructureerde feed-entry (Trello-stijl kaart-discussie). Anders dan de oude {who} draagt
    # een entry nu een echte auteur (mens/persoon/AI/rol) en een soort (update vs reactie), zodat
    # zowel mensen als AI's kunnen meepraten en rol-voortgang herkenbaar in dezelfde stroom landt.
    _FEED_KINDS = ("update", "comment", "system")   # "system" = neutrale audit-entry (geen worked/progress-neveneffect)
    _AUTHOR_TYPES = ("human", "person", "persona", "role")

    def add_feed_entry(self, pid: str, text: str, *, kind: str = "comment",
                       author_type: str = "human", author_id: str = "",
                       voorstel: dict | None = None) -> dict | None:
        """Voeg een feed-item toe. `kind`: 'update' (voortgang door een rol/AI) of 'comment'
        (reactie/sturing). `author_type` ∈ human|person|persona|role. `voorstel` = een optioneel
        machine-leesbaar actie-voorstel dat een rol bij haar reactie doet ({titel, skill, payload,
        role_id}); de feed rendert er een 'maak taak'-knop bij (Level 2 @mention). Geeft de entry terug."""
        p = self._projects.get(pid)
        text = (text or "").strip()
        if p is None or not text:
            return None
        if kind not in self._FEED_KINDS:
            kind = "comment"
        if author_type not in self._AUTHOR_TYPES:
            author_type = "human"
        entry = {
            "id": uuid.uuid4().hex[:10],
            "kind": kind,
            "author": {"type": author_type, "id": author_id or ""},
            "text": text[:1500],
            "at": time.time(),
        }
        if isinstance(voorstel, dict) and voorstel.get("titel"):
            entry["voorstel"] = {
                "titel": str(voorstel.get("titel", ""))[:200],
                "skill": (str(voorstel["skill"])[:60] if voorstel.get("skill") else None),
                "payload": voorstel.get("payload") if isinstance(voorstel.get("payload"), dict) else {},
                "role_id": str(voorstel.get("role_id", ""))[:120],
            }
        p.setdefault("log", []).append(entry)
        # Een menselijke reactie is sturing: de rol pakt het opnieuw op (zoals add_comment).
        if kind == "comment" and author_type == "human":
            p["worked"] = False
        elif kind == "update":
            p["progress"] = text[:1500]
        self._touch(p)
        self._save()
        return entry

    def feed_edit(self, pid: str, entry_id: str, text: str) -> bool:
        """Wijzig de tekst van een feed-entry (eigen comment). Lege tekst doet niets."""
        p = self._projects.get(pid)
        text = (text or "").strip()
        if p is None or not text:
            return False
        for e in p.get("log", []):
            if e.get("id") == entry_id:
                e["text"] = text[:1500]
                self._touch(p); self._save()
                return True
        return False

    def feed_remove(self, pid: str, entry_id: str) -> bool:
        p = self._projects.get(pid)
        if p is None:
            return False
        n = len(p.get("log", []))
        p["log"] = [e for e in p.get("log", []) if e.get("id") != entry_id]
        if len(p["log"]) != n:
            self._touch(p); self._save()
            return True
        return False

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


# De twee redenen waarom een item NIET meetelt in de klaar-telling. Beide betekenen "dit project
# levert dit niet", maar ze zijn niet hetzelfde en lezen dus ook anders:
#   skipped    — de mens besloot achteraf dat het niet (meer) hoeft;
#   human_task — de planner zag vooraf dat alleen een mens of externe partij dit kan doen.
# Eén constante, want de teller, de badge, het einddocument en de park-klep moeten per se dezelfde
# set uitsluiten (anders zegt de UI 4/5 terwijl de rol het project al als af beschouwt).
_NIET_TELBAAR = ("skipped", "human_task")


def _items_van(project_or_cl) -> list[dict]:
    cls = ([project_or_cl] if "items" in (project_or_cl or {})
           else (project_or_cl or {}).get("checklists") or [])
    return [it for cl in cls for it in (cl.get("items") or [])]


def skipped_items(project_or_cl) -> list[dict]:
    """De bewust overgeslagen items (mens-besluit achteraf)."""
    return [it for it in _items_van(project_or_cl) if it.get("skipped")]


def human_task_items(project_or_cl, alleen_open: bool = True) -> list[dict]:
    """De expliciete mens-taken (planner-besluit vooraf). Default alleen de nog openstaande —
    een afgevinkte mens-taak is gedaan en hoeft niet als voorbehoud gemeld te worden."""
    return [it for it in _items_van(project_or_cl)
            if it.get("human_task") and not it.get("skipped")
            and not (alleen_open and it.get("done"))]


def empty_items(project_or_cl) -> list:
    """Items die zijn uitgevoerd maar niets opleverden (`leeg`). Afgevinkt, maar geen antwoord."""
    items = (project_or_cl.get("items", []) if isinstance(project_or_cl, dict)
             and "items" in project_or_cl else None)
    if items is None:
        items = []
        for cl in (project_or_cl.get("checklists") or []):
            items += cl.get("items") or []
    return [it for it in items if it.get("leeg") and not it.get("skipped")]


def not_answered_note(project_or_cl, max_toon: int = 2) -> str:
    """Één leesbare regel over wat dit project NIET beantwoordt: overgeslagen taken plus nog
    openstaande mens-taken. Leeg als er niets uitstaat.

    Eén bron, want de badge, het einddocument, de afrond-uitkomst en de review-melding moeten alle
    vier hetzelfde zeggen: dit project rondt af zónder deze ta(a)k(en). Dat is de rem op valse
    voltooiing — 4/4 mag nooit lezen als 'alles gedaan'."""
    delen = []
    weg = skipped_items(project_or_cl)
    mens = human_task_items(project_or_cl)
    # Uitgevoerd-maar-leeg hoort in dezelfde regel: het is afgevinkt, maar het beantwoordt niets.
    # Zonder deze groep is een project waarin élke taak leegliep niet van een afgerond project te
    # onderscheiden — de duurste vorm van valse voltooiing.
    leeg = empty_items(project_or_cl)
    for groep, label, redenveld in ((weg, "overgeslagen", "skip_reason"),
                                    (mens, "mens-taak/taken open", "reason"),
                                    (leeg, "uitgevoerd zonder resultaat", "leeg_reden")):
        if not groep:
            continue
        stukken = []
        for it in groep[:max_toon]:
            reden = (it.get(redenveld) or "").strip()
            stukken.append(f"'{(it.get('text') or '?')[:60]}'" + (f" ({reden[:80]})" if reden else ""))
        rest = len(groep) - len(stukken)
        delen.append(f"{len(groep)} taak/taken {label}: " + ", ".join(stukken)
                     + (f" (+{rest} andere)" if rest > 0 else ""))
    return " · ".join(delen)


def checklist_progress(cl_or_items) -> tuple[int, int]:
    """(afgevinkt, telbaar) voor één checklist of een lijst items — DE bron van waarheid voor
    "is deze checklist af?".

    Overgeslagen items én expliciete mens-taken tellen niet mee in de noemer (`_NIET_TELBAAR`): een
    besluit dat dit project het niet levert, mag het niet eeuwig onafgerond houden. Eén definitie,
    want de worker (review-gate), de voortgangsbalk en de kaart-badge moeten het per se over
    hetzelfde getal hebben."""
    items = cl_or_items.get("items", []) if isinstance(cl_or_items, dict) else (cl_or_items or [])
    telbaar = [it for it in items if not any(it.get(v) for v in _NIET_TELBAAR)]
    return sum(1 for it in telbaar if it.get("done")), len(telbaar)


def seed_document(dod: str) -> str:
    """De start van het levende einddocument: de 'klaar wanneer' (de uitgebreide DoD) als kop.
    De inwoner schrijft hieronder naar het antwoord toe; zodra het document van deze seed afwijkt
    is de uitkomst beantwoord (zie dod_poort). Leeg → "" (geen seed)."""
    d = (dod or "").strip()
    if not d:
        return ""
    return (f"**Klaar wanneer**\n\n{d}\n\n---\n\n"
            "*De inwoner werkt dit document bij elke puls bij en schrijft hieronder "
            "naar het antwoord toe.*\n")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# Het seed-sjabloon met een merkteken op de plek van de opdracht, zodat we de vaste kop en staart
# kunnen aflezen ZONDER ze ergens over te tikken. Verandert `seed_document`, dan verandert dit mee.
_SEED_MERK = "\x00OPDRACHT\x00"
_SEED_KOP, _SEED_STAART = seed_document(_SEED_MERK).split(_SEED_MERK, 1)


def is_seed_document(project: dict | None, doc_text: str = "") -> bool:
    """Is dit document nog LETTERLIJK de geseede opdracht — de 'klaar wanneer'-kop zonder antwoord?

    DE ENIGE PLEK waar die vraag beantwoord wordt. `dod_poort` gebruikt hem als poortcriterium en
    de projectkaart om te weten of er een essentie te tonen valt of alleen de opdracht. Twee keer
    "is dit nog de seed" beantwoorden (bijvoorbeeld met een regex op `**Klaar wanneer**`) laat die
    antwoorden stil uit elkaar lopen zodra het sjabloon verandert.

    TWEE WEGEN, ÉÉN DEFINITIE. Eerst de directe vergelijking met de seed van dít project. Maar op
    productie heeft 84 van de 107 geseede documenten een LEEG `done_when` op het record, terwijl
    het document wél met een opdracht geseed is — de tekst leeft dan alleen nog in het document.
    Die vielen door de directe vergelijking heen (`seed_document("")` is ""), waardoor `dod_poort`
    ze als beantwoord zag en de kaart de sjabloonzin als samenvatting toonde. Daarom de tweede
    weg: is dit document gelijk aan seed_document(X) voor ÉÉNDER WELKE X? Dat is dezelfde
    definitie, alleen niet afhankelijk van een veld dat leeg kan zijn. Kop en staart komen uit
    `seed_document` zelf, dus het sjabloon staat nog steeds op één plek.

    Leeg document → False: dat is niet "nog de opdracht", dat is "nog niets". Op het scherm zijn
    dat verschillende zinnen, dus hier verschillende antwoorden."""
    dt = (doc_text or "").strip()
    if not dt:
        return False
    seed = seed_document(((project or {}).get("done_when") or ""))
    if seed and _norm(dt) == _norm(seed):
        return True
    kop, staart = _norm(_SEED_KOP), _norm(_SEED_STAART)
    n = _norm(dt)
    return bool(kop) and n.startswith(kop) and n.endswith(staart) and len(n) > len(kop) + len(staart)


def dod_poort(project: dict | None, doc_text: str = "") -> str | None:
    """De projectpoort (founder, 19 jul; verhuisd 21 jul naar het einddocument): Done vereist
    dat de uitkomst beantwoord is IN het einddocument, niet dat het werk 'gedaan' is. De poort is
    open zodra het document méér bevat dan alleen de geseede opdracht (de 'klaar wanneer'-kop).
    Deterministisch en dun: hij oordeelt niet over de kwaliteit van het antwoord, alleen dat er
    een antwoord staat. Geeft de weiger-reden terug, of None als de poort open is.

    Legacy: projecten met een ingevuld 'dod_outcome' (het oude DoD-contract-veld) blijven zo
    afrondbaar, ook zonder einddocument."""
    p = project or {}
    if (p.get("dod_outcome") or "").strip():
        return None
    dt = (doc_text or "").strip()
    if not dt:
        return ("nog niet af: het einddocument is nog leeg — schrijf eerst het antwoord op de "
                "uitkomst (of waarom die onbeantwoordbaar is)")
    if is_seed_document(p, dt):
        return ("nog niet af: het einddocument bevat alleen de opdracht (klaar wanneer), nog geen "
                "antwoord op de uitkomst")
    return None


# ── Concurrency-poort: ALLE schrijfpaden lopen door _synchronized (slot + verse read onder het slot).
# Eén auditbare lijst (1-op-1 met de methodes die self._save() aanroepen). Een NIEUW schrijfpad MOET hier
# bij — de guard-test tests/test_projectledger_concurrency.py::test_alle_schrijfpaden_gesynchroniseerd
# faalt zodra een methode die _save aanroept niet in deze lijst staat. Reads staan er bewust NIET in.
_WRITE_METHODS = (
    "create", "start", "set_due", "set_dod", "add_reaction", "attach_add", "attach_file", "attach_remove",
    "reopen", "block", "unblock", "complete", "mark_awaiting_review", "checklist_add", "checklist_remove", "check_add",
    "check_toggle", "check_remove", "set_item_skipped", "mark_item_routed", "set_handoff_trail",
    "set_item_offer", "accept_item_offer",
    "edit", "approve", "discard", "accept_proposal", "reject_proposal",
    "archive", "unarchive", "remove", "record_progress", "mark_tended", "add_comment",
    "add_role_message", "add_feed_entry", "feed_edit", "feed_remove", "wait_for", "link",
    "mark_formalized", "to_future", "mark_scope_nudge", "mark_scope_nudge_checked",
    "note_item_fail", "reset_item_fails",
    "set_item_leeg", "clear_item_leeg", "mark_critic", "park", "set_item_human", "set_item_payload",
)
for _m in _WRITE_METHODS:
    setattr(ProjectLedger, _m, _synchronized(getattr(ProjectLedger, _m)))
