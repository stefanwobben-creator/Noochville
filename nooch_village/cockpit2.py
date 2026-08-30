"""Cockpit 2 — de GlassFrog-vormige weergave (PoC).

Read-only "plaatje": rendert de organisatie als GlassFrog (cirkel-/rolpagina's met tabs +
org-verkenner), bovenop het nieuwe datamodel (records, people, assignments, attachments). Wat we
hebben tonen we echt; wat we nog niet hebben grijzen we uit ("nog te bouwen"), zodat in één blik
zichtbaar is welke brokken resten.

Design: hergebruikt het bestaande design system van cockpit 1 (tokens + _page).
Aparte server (poort 8766) zodat cockpit 1 ongemoeid blijft. Bootstrapt bij een lege dataset de
echte Nooch-structuur (glassfrog_import.nooch_poc_org) in data/poc/, zonder de live data aan te raken.

    python -m nooch_village.cockpit2            # http://127.0.0.1:8766
"""
from __future__ import annotations
import json
import logging
import mimetypes
import os
import re
import time
import secrets
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nooch_village import auth as _auth
from nooch_village import claims_db as _claims_db
from nooch_village import claims_board as _claims_board
from nooch_village import claims_labels as _claims_labels
from nooch_village.web_base import _e, _page, _banner     # zelfde design system
from nooch_village.cockpit2_util import (
    _name, _initials, _tabbar, _avatar, _age, _fmt_due,
    _created_full, _ic, _bron_html, _stamp, _md, _parse_multipart,
    _link_host, _psec, _ICON_ADD_EMOJI, _person_name, _footer,
    _IC_CHECK, _IC_INFO, _IC_CHAT, _IC_LINK, _IC_DL,
    _IC_DESC, _IC_CLOCK, _IC_FILE, _IC_TARGET,
)
from nooch_village.views.feed import (
    _feed_norm, _feed_who, _mentionables, _mentions_in,
    _hilite_mentions, _feed_entry_html, _feed_author_options,
    _wall_outcome_opts,
)
from nooch_village.governance import Records
from nooch_village import acc_ids, skill_meta, skill_links
from nooch_village.skill_links import SkillLinkKroniek
from nooch_village.people import PeopleStore
from nooch_village.assignments import Assignments
from nooch_village.attachments import AttachmentStore, ARTEFACT_KINDS, body_cap
from nooch_village.observations import ObservationStore
from nooch_village import observations
from nooch_village.evidence_ledger import EvidenceLedger
from nooch_village import snake
from nooch_village.source_status import SourceStatusStore
from nooch_village.collector import migrate_data_sources
from nooch_village import artefacts
from nooch_village.artefacts import can_write_artefact, requires_governance_ref
from nooch_village import epic
from nooch_village.personas import PersonaStore
from nooch_village.projects import (ProjectLedger, PREP_CHECKLIST_TITLE, _MISSIE_IMPACT,
                                    _BUSINESS_IMPACT, _EFFORT)
from nooch_village.deliverable_store import DeliverableStore
from nooch_village.project_doc_store import ProjectDocStore
from nooch_village.radar_clusters import ClusterBesluitStore
from nooch_village.radar_store import RadarStore
from nooch_village import radar_promote
from nooch_village.registry_factory import shared_registry
from nooch_village.skill_match import plan_offers
from nooch_village.util import refuse
from nooch_village.ai_tasks import AITaskStore, KIND_MIDDEL
from nooch_village import skill_labels
from nooch_village.checklists import ChecklistStore, CADENCES, CADENCE_LABEL
from nooch_village.metrics import MetricStore, window_cutoff, filter_samples
from nooch_village.kennisbank import (KennisbankStore, parse_blok,
                                      field as kb_field, verdict as kb_verdict,
                                      WORD_LABEL as KB_WORD_LABEL,
                                      load_atoms as kb_load_atoms)
from nooch_village.kennisbank_intake import SUBJECTS as KB_SUBJECTS, intake as kb_intake
from nooch_village.kennisbank_spel import SpelStore, spel_finish
from nooch_village.kennisbank_staging import StagingStore, commit_atom, commit_batch
from nooch_village.views.kennisbank_staging import render_kennisbank_staging
from nooch_village.notes_store import NotesStore
from nooch_village.insight import Insight
from nooch_village.metric_schema import (CADANS_LABEL, MEETTYPE_LABEL, MEETWIJZE_LABEL,
                                         TIJD_LABEL, BRUIKBAAR_LABEL, VERIFICATIE_LABEL)
from nooch_village.definitions import (DefinitionStore, seed_catalog as _seed_catalog,
                                       reground_seed as _reground_seed,
                                       migrate_definitions as _migrate_definitions)
from nooch_village.cockpit2_util import _BUILD, _EXTRA_CSS, _CIRCLE_TABS, _ROLE_TABS, WEBSITE_DEVELOPER_ROLE
from nooch_village.notifications import NotifStore
from nooch_village.noochie import NoochieStore
from nooch_village.roloverleg import Agenda
from nooch_village.werkoverleg import WerkoverlegStore, STEPS as _WO_STEPS
from nooch_village.strategy_store import StrategyStore
from nooch_village.backlog import BacklogStore
from nooch_village import ai_match
from nooch_village import org
from nooch_village.glassfrog_import import import_org, nooch_poc_org

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}





def _default_data_dir() -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, "data")


class _Stores:
    def __init__(self, dd: str):
        os.makedirs(dd, exist_ok=True)
        self.dd = dd
        self.records = Records(os.path.join(dd, "governance_records.json"))
        self.people = PeopleStore(os.path.join(dd, "people.json"))
        self.assign = Assignments(os.path.join(dd, "assignments.json"))
        self.att = AttachmentStore(os.path.join(dd, "attachments.json"))
        self.observations = ObservationStore(os.path.join(dd, "observations.jsonl"))
        self.evidence = EvidenceLedger(os.path.join(dd, "evidence_ledger.jsonl"))   # De Kroniek — bewijsregister
        self.sources = SourceStatusStore(os.path.join(dd, "sources.json"))
        self.personas = PersonaStore(os.path.join(dd, "personas.json"))
        self.projects = ProjectLedger(os.path.join(dd, "projects.json"))
        self.deliverables = DeliverableStore(os.path.join(dd, "deliverables.json"))
        self.project_docs = ProjectDocStore(dd)   # levend einddocument per project (weergave + edit-route)
        self.ai = AITaskStore(os.path.join(dd, "ai_tasks.json"))
        # Eenmalig, idempotent: koppelingen die nog aan een index hangen krijgen het stabiele
        # acc_id van de accountability die nú op die positie staat.
        self.ai.migrate_acc_ids(self.records)
        # Legacy record.persona_id → assignments-store: één bron van waarheid voor bemensing.
        # Idempotent; zie assignments.migrate_persona_bindings voor het waarom.
        try:
            from nooch_village.assignments import migrate_persona_bindings
            migrate_persona_bindings(self.records, self.assign)
        except Exception:                                # noqa: BLE001 — nooit een pagina blokkeren
            pass
        self.match = ai_match.MatchCache(os.path.join(dd, "ai_match_cache.json"))
        self.notif = NotifStore(os.path.join(dd, "notifications.json"))
        self.agenda = Agenda(os.path.join(dd, "roloverleg_agenda.json"))
        self.noochie = NoochieStore(os.path.join(dd, "noochie.json"))
        self.checklists = ChecklistStore(os.path.join(dd, "checklists.json"))
        self.metrics = MetricStore(os.path.join(dd, "metrics.json"))
        self.defs = DefinitionStore(os.path.join(dd, "definitions.json"))
        self.werk = WerkoverlegStore(os.path.join(dd, "werkoverleg.json"))
        self.strategies = StrategyStore(os.path.join(dd, "strategies.json"))
        self.backlog = BacklogStore(os.path.join(dd, "backlog.json"))
        # Welke rollen bewust meetellen in de copy-prompt-stack van een andere rol. Erfenis loopt
        # omhoog; een zusterrol insluiten is een besluit en staat daarom vastgelegd.
        self.copy_stack = CopyStackConfig(os.path.join(dd, "copy_stack.json"))
        self.radar = RadarStore(os.path.join(dd, "radar.json"))   # Radar-tool: gecureerde Inoreader-signalen per rol
        # Wat de founder met een opkomend onderwerp deed (project of watch). Geen oordeel-label:
        # clustering is berekend, de projectkeuze is strategie — zie radar_clusters.
        self.radar_besluiten = ClusterBesluitStore(os.path.join(dd, "radar_clusters.json"))
        self.kennisbank = KennisbankStore(os.path.join(dd, "kennisbank.json"))   # laag 2: geversioneerde inzichten
        self.notes = NotesStore(os.path.join(dd, "notes.json"))   # laag 1: de atomen-bibliotheek (kennislaag)
        self.spel = SpelStore(os.path.join(dd, "kennisbank_spel.json"))   # fase 3: inzicht-dialogen
        self.staging = StagingStore(os.path.join(dd, "kennisbank_staging.json"))   # zone 2: even-nakijken
        self.library = Library(os.path.join(dd, "library.json"))   # beschermde woordenschat (Lara cureert)
        self.nominations = NominationQueue(os.path.join(dd, "keyword_nominaties.json"))   # fase 4: pending-queue
        self.nom_kroniek = NominationKroniek(os.path.join(dd, "keyword_nominaties.jsonl"))   # fase 4: beslissings-Kroniek
        self.link_kroniek = SkillLinkKroniek(os.path.join(dd, "skill_links_kroniek.jsonl"))   # koppelingen: wie hing welk middel waar


_FAC_ACC = "Rapporteren over de gezondheid van de werkoverleggen"
_FAC_CHECK = "Gezondheid werkoverleggen gerapporteerd"


def _ensure_facilitator_health(st: _Stores) -> None:
    """Idempotent: de Facilitator krijgt de accountability 'rapporteren over de gezondheid van de
    werkoverleggen', met een maandelijks checklist-item dat eraan hangt."""
    for fac in [r for r in st.records.all() if r.id.endswith("__facilitator")]:
        accs = fac.definition.accountabilities
        if _FAC_ACC not in accs:
            accs.append(_FAC_ACC)
            try:
                fac.version += 1
            except Exception:
                pass
            st.records.put(fac)
        if not any(i.get("description") == _FAC_CHECK for i in st.checklists.for_node(fac.id)):
            st.checklists.add(fac.id, _FAC_CHECK, "maand", target_type="all", by="founder")


_TRANSP_POLICY = "Rolvervullers zijn transparant over hun projecten (projectenbord bijgewerkt)."
_TRANSP_CHECK = "Projectenbord bijgewerkt (transparantie)"


def _ensure_transparency_policy(st: _Stores) -> None:
    """Idempotent: het wekelijkse checklist-item dat transparantie operationeel checkt. De
    transparantie-POLICY zelf is in fase 2 uit de policy-lijst gehaald (was eerder een note);
    de cadans blijft via dit checklist-item. Voegt GEEN string meer toe aan definition.policies."""
    roots = org.roots(st.records.all())
    root = roots[0] if roots else None
    if root is None:
        return
    if not any(i.get("description") == _TRANSP_CHECK for i in st.checklists.for_node(root.id)):
        st.checklists.add(root.id, _TRANSP_CHECK, "week", target_type="all", by="founder")


def _bootstrap(dd: str) -> None:
    """Lege PoC-dataset? Laad dan de echte Nooch-structuur in (eenmalig)."""
    st = _Stores(dd)
    if not st.records.all():
        import_org(nooch_poc_org(), st.records, st.people, st.assign)
    _ensure_facilitator_health(st)
    _ensure_transparency_policy(st)
    _seed_catalog(st.defs)        # Librarian metrics-database: zaad-definities (idempotent)
    _reground_seed(st.defs)       # bestaande definities bijwerken met nieuwe grondingen (idempotent)
    _migrate_definitions(st.defs)  # nieuwe verplichte velden (aard/aggregatie/formule) retroactief (idempotent)
    st.att.migrate()              # attachments → artefact-model (legacy tool-notes, defaults; idempotent)
    # De copy-prompt-generator hoort als gereedschap bij de rol die hem gebruikt, niet als losse
    # pagina die nergens aan hangt. Idempotent; fail-soft — een tool mag de cockpit nooit ophouden.
    try:
        from nooch_village.views.copy_prompt import zorg_voor_tool
        for _rid in _COPY_PROMPT_ROLLEN:
            zorg_voor_tool(st.records, st.att, _rid)
        for _rid, _bronnen in _COPY_STACK_ZAAD.items():
            if st.records.get(_rid) is not None:
                st.copy_stack.zaad(_rid, [b for b in _bronnen if st.records.get(b) is not None],
                                   door="system (zaad)")
    except Exception as _e:                              # noqa: BLE001
        logging.getLogger("village.cockpit").warning("copy-prompt-tool niet gekoppeld: %s", _e)
    # Grafstenen van #271 intrekken: notificaties die de bug "[rol X onbemand]" uitzond terwijl de
    # rol gewoon bemand was. Idempotent; items van ná de fix blijven staan (dat zou een regressie
    # zijn, geen grafsteen). Fail-soft — opruimen mag de cockpit nooit ophouden.
    try:
        from nooch_village.notif_opruiming import archiveer_stale_onbemand
        _op = archiveer_stale_onbemand(st.notif, st.records, st.assign)
        if _op.get("gearchiveerd"):
            logging.getLogger("village.cockpit").info(
                "opruiming: %d stale onbemand-notificatie(s) ingetrokken", _op["gearchiveerd"])
    except Exception as _e:                              # noqa: BLE001
        logging.getLogger("village.cockpit").warning("opruiming overgeslagen: %s", _e)
    # De haak bij het ONTSTAAN: elke nieuwe spanning voor een mens-bemande rol krijgt meteen zijn
    # bevinding (in gewone taal) en zijn type. Eén call per spanning, niet in een batch — wie hem
    # later opent leest de al-geschreven tekst. Fail-soft: valt dit om, dan blijft de rauwe
    # notificatie staan, want een niet-verrijkte spanning is nog steeds een spanning.
    try:
        from nooch_village.spanning_ontstaat import maak_verrijker
        st.notif.set_verrijker(maak_verrijker(st.records, st.assign, dd))
    except Exception as _e:                              # noqa: BLE001
        logging.getLogger("village.cockpit").warning("spanning-verrijker niet gezet: %s", _e)
    migrate_data_sources(dd)      # legacy visitors_day → plausible_visitors_day + Plausible actief (idempotent)
    st.metrics.migrate_metric_bindings(st.defs)   # wees-KPI's: veld/categorie uit de def + reeks-tegel-dim (idempotent)
    # OpenAlex: alle oude CUMULATIEVE concept-reeksen (openalex_works_day/citations_day, incl. ::concept)
    # weg; alleen de nieuwe 90/30-FLOW (openalex_works_90d::…) blijft. Verworpen meetopzet (bevroren
    # aggregaat), vóór meetstart. Idempotent.
    st.observations.remove_bron("openalex", keep_prefix="openalex_works_90d")
    # Trends: de Library-anker-reeksen (verworpen ontwerp, vóór meetstart) weg; alleen de nieuwe
    # stemming-paar-reeksen (trends_ratio_*) blijven. Idempotent. Zie de meetverantwoording in docs/.
    st.observations.remove_bron("trends", keep_prefix="trends_ratio_")
    # Belofte-graaf: zet eenmalig de schoen-ontleding uit de aangeleverde BOM (idempotent;
    # overschrijft gedane grondingen niet).
    from nooch_village.belofte_store import BelofteStore, seed_schoen_graaf
    seed_schoen_graaf(BelofteStore(os.path.join(dd, "belofte_grafen.json")))


from nooch_village.views.overview import (
    _filler_html, _members_of_circle, _tree_html,
    _ai_chip, _suggest_for_acc, _acc_row,
    _role_ai_overview, _overview_html, _fillsummary,
    _fillers_block, _role_row, _roles_html,
    _members_html, _att_html,
    render_node, render_person, render_patterns, render_admin,
    render_rolefillers, render_aitask,
    _CORE_ROLE_NAMES, _ICON_ADD_PERSON,
)



from nooch_village.views.projects import (
    _proj_chip, _trekker_html, _trekker_options,
    _proj_progress, _due_overdue, _progress_badge,
    _scope_text, _proj_card, _quickadd,
    _columns_html, _drag_script,
    _modal_html, _group_meta, _projects_board,
    _archived_html, _projects_tab_html,
    _person_projects_tab_html, render_project,  # noqa
    _PROJ_CHIP, _PROJ_COLS, _LABELS, _II_PREFIX,
)
from nooch_village.views.wizard import render_wizard


from nooch_village.views.checklists import (
    _cl_target_label, _cl_spark, _cl_row,
    _checklists_tab_html, _checklists_html,
)
from nooch_village.views.metrics import (
    _source_samples, _metric_points, _spark_svg, _kpi_card,
    _metric_add_forms, _shopify_window, _sources_for, _werk_fetch,
    _tile_combos, _tile_meta, _fetch, _num, _agg,
    _render_bullet, _data_table, _render_burnup,
    _render_form, _grondslag, _grondslag_popover, _llm_says_comparable,
    _render_tile, _kpi_id_from_def, _goal_options, _metric_csv, _default_form,
    _kpi_data_row, _def_tokens, _role_text, _role_relevant_defs,
    _metrics_tab_html, _break_indices, _link_card,
    _dir_select, _cad_select, _mt_select, _opt_select,
    _aard_chips, _mw_select, _mw_chip,
    render_kpi_composer,
    _MW, _SOURCE_KPIS, _RICHTING, _ORIGIN_LABEL,
)


from nooch_village.views.catalog import (
    _catalog_edit_form, _catalog_card,
    _catalog_add_form, render_catalog,
)
from nooch_village.views.signals import render_signals
from nooch_village.views.inbox import (
    render_inbox, render_verwerk, render_inbox_frag, render_inbox_chrome, _person_role_options,
)
from nooch_village.views.metrics2 import render_metrics2
from nooch_village.views.bronnen import render_bronnen
from nooch_village.views.skills import render_skills
from nooch_village.views.search import render_search, render_search_fragment
from nooch_village.views.claims import render_claims, render_rapport, rol_voor
from nooch_village import founder_kaart as _founder_kaart
from nooch_village.copy_stack import StackConfig as CopyStackConfig
from nooch_village.views.copy_prompt import render_copy_prompt
from nooch_village.views.founder_flow import render_founder_flow
from nooch_village.views.inwoners import render_inwoner, render_inwoners
from nooch_village.views.kennislaag import render_kennislaag
from nooch_village.views.wiki import render_pagina
from nooch_village.views.backlog import render_backlog
from nooch_village.views.codie import render_codie
from nooch_village.views.kennisbank import render_kennisbank, render_kennisbank_search
from nooch_village.views.kennisbank_spel import (render_kennisbank_spel,
                                                 render_kennisbank_spel_search)
from nooch_village.views.linkbuilding import render_linkbuilding
from nooch_village.views.accountabilities import render_accountabilities
from nooch_village.views.woordenschat import render_woordenschat
from nooch_village.views.keyword_lens import render_keyword_lens
from nooch_village.library import Library
from nooch_village.keyword_nominations import (NominationQueue, NominationKroniek, valid_reason)
from nooch_village.views.belofte import render_belofte


from nooch_village.views.noochie import (
    _noochie_suggest, _noochie_reply,
    render_noochie, _noochie_chrome,
)
from nooch_village.views.callbar import render_callbar

from nooch_village.views.werkoverleg import (
    _wo_hid, _wo_checkin, _wo_checklist, _wo_metrics,
    _wo_checkout, _wo_summary, render_werkoverleg,
)
from nooch_village.views.vangst import render_vangst, render_vangst_frag


_IC_GEAR = _ic("<circle cx='12' cy='12' r='3'/><path d='M19 12a7 7 0 0 0-.1-1l2-1.6-2-3.4-2.4 1a7 7 0 0 0-1.7-1l-.4-2.5h-4l-.4 2.5a7 7 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.6a7 7 0 0 0 0 2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.4 2.5h4l.4-2.5a7 7 0 0 0 1.7-1l2.4 1 2-3.4-2-1.6a7 7 0 0 0 .1-1z'/>")




def _owner_ai(st: _Stores, orec):
    """De AI-inwoner (persona) die de eigenaar-rol vervult, of None."""
    if orec is None:
        return None
    for f in st.assign.fillers_of(orec.id, record=orec):
        if f.type == "persona":
            return st.personas.get(f.id)
    return None


def _person_targets(st: _Stores, username: str) -> list:
    """De inbox-doelen van de ingelogde mens: hemzelf als persoon ÉN elke rol die hij vervult. Zo bundelt
    de inbox mentions aan de persoon (individuele actie) en aan al zijn rollen. Onbekend/guest → []."""
    if not username or username == "guest":
        return []
    person = st.people.by_email(username)
    if person is None:
        return []
    targets = [("person", person.id)]
    for r in st.records.all():
        if getattr(r, "archived", False):
            continue
        try:
            for f in st.assign.fillers_of(r.id, record=r):
                if getattr(f, "type", None) == "person" and f.id == person.id:
                    targets.append(("role", r.id))
                    break
        except Exception:
            continue
    return targets


def _scoped_project_opts(st: _Stores, n) -> str:
    """Projectlijst voor de actie-uitkomst, GESCOPET op de rol die bij deze spanning hoort (de doel-rol
    van de mention, anders de eigenaar van het bron-project). Alleen díe projecten — niet alles van
    iedereen (dat was de klacht). Fail-soft: geen rol → alleen de placeholder."""
    rid = ""
    if isinstance(n, dict):
        if n.get("target_type") == "role":
            rid = n.get("target_id") or ""
        if not rid and n.get("project_id"):
            p = st.projects.get(n.get("project_id"))
            rid = (p or {}).get("owner") or ""
    opts = ["<option value=''>— pick project —</option>"]
    if rid:
        for p in st.projects.all():
            if p.get("owner") == rid and not p.get("archived"):
                opts.append(f"<option value='{_e(p['id'])}'>{_e(str(p.get('scope') or p['id'])[:60])}</option>")
    return "".join(opts)


def _role_of_persona(st: _Stores, persona):
    """Eerste niet-gearchiveerde rol die door deze persona wordt vervuld, of None. Puur voor de
    'Rol: … purpose'-context in de reply; ontbreekt hij, dan valt die regel weg (fail-soft)."""
    if persona is None:
        return None
    for r in st.records.all():
        if getattr(r, "archived", False):
            continue
        f = _owner_ai(st, r)
        if f is not None and f.id == persona.id:
            return r
    return None


def _mentioned_personas(st: _Stores, text: str) -> list:
    """AI-personas die in `text` @genoemd zijn — via rolnaam (→ de persona die de rol vervult) of via
    de persona-naam zelf. Zelfde match-regel als _mentions_in: substring '@naam' (case-insensitief).
    Ontdubbeld op persona-id, volgorde-behoudend. Een @mens levert niets op (die krijgt enkel notificatie)."""
    t = (text or "").lower()
    out, seen = [], set()

    def _maybe(name, persona):
        if persona is None or persona.id in seen:
            return
        if ("@" + (name or "").strip().lower()) in t:
            seen.add(persona.id)
            out.append(persona)

    for r in st.records.all():                       # rolnaam → de persona die de rol vervult
        if getattr(r, "archived", False):
            continue
        _maybe(_name(r), _owner_ai(st, r))
    for p in st.personas.all():                      # persona-naam → die persona
        _maybe(p.name, p)
    return out


def _role_capabilities_block(role) -> str:
    """Accountabilities + skills (naam + korte omschrijving) van de rol, als context zodat een @genoemde
    rol kan toetsen of dialoog-info bij één van haar verantwoordelijkheden past en een concrete stap kan
    voorstellen. Fail-soft: geen rol / geen DNA / registry-bouwfout → een lege string (geen blok, geen
    fout). Verzint niets: alleen wat echt in het DNA en de registry staat."""
    if role is None:
        return ""
    try:
        dna = role.definition
        accts = list(getattr(dna, "accountabilities", []) or [])
        skills = list(getattr(dna, "skills", []) or [])
        reg = None
        try:
            reg = shared_registry()
        except Exception:
            reg = None
        skill_lines = []
        for name in skills:
            obj = reg.get(name) if reg else None
            desc = (getattr(obj, "description", "") or "").strip() if obj else ""
            skill_lines.append(f"- {name}: {desc[:120]}" if desc else f"- {name}")
        acc_txt = "\n".join(f"- {a}" for a in accts) or "(geen)"
        sk_txt = "\n".join(skill_lines) or "(geen)"
        return (f"Jouw accountabilities:\n{acc_txt}\n"
                f"Jouw skills (de ENIGE concrete tools die je hebt):\n{sk_txt}\n")
    except Exception:
        return ""


def _ai_reply(st: _Stores, pid: str, ask=None, *, persona=None, prefix: str = "") -> bool:
    """Een @genoemde (of via de meedenk-knop aangesproken) AI-rol TRIAGEERT een signaal, i.p.v. blind een
    voorstel te posten. De beslisboom (zie `_parse_triage` + `_settle_inbox`):

      1. Past het bij mijn rol?  Nee → korte afwijzing (+ optioneel welk stuk wél), item verwerkt met reden.
      2. Ja/deels, en kan ik het puur uit mijn kennis beantwoorden (geen skill/project nodig)? → antwoord
         nu direct op de wall; het inbox-item wordt verwerkt met reden 'direct beantwoord'.
      3. Ja/deels, maar er is een skill/meerdere stappen nodig? → 'ik verwerk dit via mijn inbox'. Binnen
         scope (een skill die ECHT in het DNA zit, machine-gecheckt via plan_offers) + experiment aan →
         de rol maakt er meteen zelf een project van en markeert het inbox-item verwerkt met de uitkomst.
         Buiten scope / experiment uit → het item blijft 'nieuw' voor de mens.

    Zo is er één verwerkingsplek (de inbox) met historie: elk signaal krijgt een herkomst en een uitkomst,
    of het nu van een mens kwam of de rol het zichzelf toebedeelt. `ask(prompt)->str|None` is injecteerbaar
    (test); standaard via llm.reason. Fail-closed: geen persona / geen LLM-antwoord → geen post."""
    p = st.projects.get(pid)
    if p is None:
        return False
    if persona is None:
        role = st.records.get(p.get("owner"))        # knop-variant: de eigenaar-persona
        persona = _owner_ai(st, role)
    else:
        role = _role_of_persona(st, persona)         # @mention-variant: rol enkel voor de purpose-regel
    if persona is None:
        return False
    recent = "\n".join(f"- {m.get('text', '')}" for m in (p.get("log") or [])[-6:])
    rol_line = (f"Rol: {_name(role)} — purpose: {role.definition.purpose}\n" if role is not None else "")
    capab = _role_capabilities_block(role)          # accountabilities + skills → grondslag voor de toets
    aanleiding = (prefix.strip() + "\n\n") if (prefix or "").strip() else ""
    ctx = (f"{aanleiding}"
           f"Project: {_scope_text(p)}\n"
           f"Omschrijving: {p.get('description', '') or '(geen)'}\n"
           f"{rol_line}"
           f"{capab}"
           f"Recente dialoog:\n{recent or '(nog leeg)'}\n\n"
           "Triageer dit signaal tegen JOUW accountabilities en skills. Beantwoord drie dingen:\n"
           "1. Past het bij jouw rol? (ja / deels / nee — bij deels of nee: welk stuk kun je wél oppakken)\n"
           "2. Kun je het NU beantwoorden puur uit wat je al weet (informatie delen), zonder een skill te "
           "draaien of een project te starten? Zo ja: geef dat antwoord.\n"
           "3. Kan het niet direct (er is een skill of meerdere stappen nodig)? Zeg dan kort dat je het via "
           "je inbox verwerkt. Verzin niets en claim nooit dat je iets deed wat je niet deed.\n\n"
           "Antwoord UITSLUITEND met JSON, exact dit schema: {\"fit\": \"ja|deels|nee\", \"welk_stuk\": "
           "\"<bij deels/nee: welk deel je wél kunt, anders leeg>\", \"kan_direct\": true of false, "
           "\"reactie\": \"<bij kan_direct=true je informatie-antwoord; anders een korte reactie/afwijzing, "
           "max 4 zinnen>\"}.")
    from nooch_village.personas import persona_prompt
    prompt = (persona_prompt(persona) + "\n\n" + ctx).strip()
    if ask is None:
        try:
            from nooch_village import llm
            # Persona-voorkeur vervangt de match-ladder als die er is; anders het oude gedrag.
            from nooch_village.llm_keuze import llm_voorkeur
            _lad = llm_voorkeur(st, getattr(role, "id", ""), "cockpit_mention_triage") or _match_ladder()
            out = llm.reason(prompt, ladder=_lad, json_mode=True,
                             call_site="cockpit_mention_triage")
        except Exception:
            out = None
    else:
        out = ask(prompt)
    if not out:
        return False
    tri = _parse_triage(out)
    if tri is None:
        # Fail-closed: geen bruikbare triage-JSON → plaats de platte tekst als gewone reactie (geen gok,
        # geen inbox-actie). Zo blijven oude/gestubde platte-tekst-antwoorden gewoon zichtbaar.
        txt = (out or "").strip()
        if not txt:
            return False
        st.projects.add_feed_entry(pid, txt, kind="comment", author_type="persona", author_id=persona.id)
        return True
    return _apply_triage(st, pid, role, persona, tri, prefix)


def _ask_text(p: dict, prefix: str) -> str:
    """De tekst die aan de rol gevraagd wordt (het te triageren signaal), voor de skill-machinecheck. Uit
    de aanleidende mens-comment (`prefix`, ontdaan van de 'De mens vraagt jou:'-omlijsting) of anders de
    laatste dialoog-regel. Puur afgeleid, verzint niets."""
    t = (prefix or "").strip()
    for lead in ("De mens vraagt jou:", "De mens vraagt:"):
        if t.startswith(lead):
            t = t[len(lead):].strip()
            break
    if t:
        return t
    for m in reversed(p.get("log") or []):
        if (m.get("text") or "").strip():
            return m["text"].strip()
    return ""


def _apply_triage(st: _Stores, pid: str, role, persona, tri: dict, prefix: str) -> bool:
    """Voer de getriageerde beslissing uit: post de reactie op de wall en verwerk/laat-staan het inbox-item
    (met historie). Zie `_ai_reply` voor de beslisboom. Fail-closed op deelfouten."""
    p = st.projects.get(pid)
    reactie = tri.get("reactie") or ""
    fit = tri.get("fit")
    welk = (tri.get("welk_stuk") or "").strip()
    ask = _ask_text(p or {}, prefix)

    # 1. Past niet bij de rol → korte afwijzing; item is afgehandeld (met reden), geen skill/geen project.
    if fit == "nee":
        txt = reactie or ("This does not fit my role." + (f" Could pick up: {welk}" if welk else ""))
        entry = st.projects.add_feed_entry(pid, txt, kind="comment", author_type="persona", author_id=persona.id)
        reden = "does not fit my role" + (f" — but: {welk}" if welk else "")
        _settle_inbox(st, role, pid, (entry or {}).get("id", ""), ask, processed=True, reason=reden)
        return True

    # 2/3. Past (deels): heeft beantwoorden een EIGEN skill nodig? Harde machine-check tegen het DNA.
    off = _dna_skill_for(st, role, ask)
    skill_needed = bool(off and off.get("skill"))

    # 2. Puur kennisantwoord (geen skill nodig én de rol zegt kan_direct) → nu direct op de wall.
    if not skill_needed and tri.get("kan_direct") and reactie:
        entry = st.projects.add_feed_entry(pid, reactie, kind="comment", author_type="persona", author_id=persona.id)
        _settle_inbox(st, role, pid, (entry or {}).get("id", ""), ask, processed=True,
                      reason="answered directly on the wall")
        return True

    # 3. Skill/meerdere stappen nodig → 'ik verwerk dit via mijn inbox'.
    ack = reactie or "I am picking this up and processing it via my inbox."
    entry = st.projects.add_feed_entry(pid, ack, kind="comment", author_type="persona", author_id=persona.id)
    eid = (entry or {}).get("id", "")

    # Binnen scope (eigen skill in DNA) + experiment aan → de rol verwerkt het item meteen zelf als project
    # via de vijf-uitkomsten-flow, en markeert het inbox-item verwerkt met de uitkomst (historie).
    if skill_needed and role is not None and not org.is_circle(role) and _mention_autotask_on():
        titel = (ask or reactie).strip()[:200]
        vst = {"titel": titel, "skill": off["skill"],
               "payload": off.get("payload") if isinstance(off.get("payload"), dict) else {},
               "role_id": role.id}
        new_pid = _create_task_from_voorstel(st, role, vst)
        if new_pid:
            _prov_feed(st, new_pid, f"↳ binnen scope zelf opgepakt uit dialoog op {pid}#{eid}", "")
            _prov_feed(st, pid, f"→ {_name(role)} pakte dit binnen scope zelf op: {titel}", "")
            _settle_inbox(st, role, pid, eid, ask, processed=True, reason=f"zelf opgepakt als project: {titel}")
            return True

    # Buiten scope / experiment uit / geen project gemaakt → item blijft 'nieuw' voor de mens (of de rol
    # zelf) om via de vijf-uitkomsten te verwerken.
    _settle_inbox(st, role, pid, eid, ask, processed=False, reason="")
    return True


def _dna_skill_for(st: _Stores, role, ask_text: str):
    """Harde machine-check: matcht het gevraagde (`ask_text`) op een skill die ECHT in het DNA van de rol
    zit? Retourneert {skill, payload, ...} of None. Hergebruikt plan_offers (dat de skill tegen de harde
    DNA-lijst toetst). Fail-closed: geen rol / geen skills / geen tekst / fout → None."""
    if role is None or org.is_circle(role) or not (ask_text or "").strip():
        return None
    try:
        offers = plan_offers(role, [ask_text], shared_registry(), name=_name(role))
    except Exception:
        return None
    return offers[0] if offers else None


def _settle_inbox(st: _Stores, role, pid: str, entry_id: str, ask_text: str, *,
                  processed: bool, reason: str):
    """Eén verwerkingsplek: zorg dat er een inbox-item voor deze rol op dit project bestaat en zet de
    status. Bestond er al een open item (bv. van een mens-@mention), dan wordt DAT verwerkt/gelaten; anders
    vijlt de rol er zelf één (autonome trigger). `processed=True` → verwerkt met `reason` als historie;
    `processed=False` → blijft 'nieuw' voor de mens. Fail-closed: geen rol → niets."""
    if role is None:
        return None
    rid = getattr(role, "id", "") or ""
    if not rid:
        return None
    try:
        open_items = [n for n in st.notif.for_targets([("role", rid)])
                      if n.get("project_id") == pid and not n.get("processed") and not n.get("archived")]
        n = open_items[0] if open_items else st.notif.add("role", rid, pid, entry_id,
                                                          by=_name(role), snippet=ask_text or "")
        if processed:
            st.notif.mark_item_processed(n["id"], outcome=reason, by=_name(role))
        return n
    except Exception:
        return None


def _mention_autotask_on() -> bool:
    """Experiment-schakelaar: mogen rollen een binnen-scope-stap (eigen skill) zelf tot taak maken, zonder
    mens-knop? Default UIT (env `mention_autotask` ontbreekt → veilig, alles via de knop). Aan met
    mention_autotask=1 in .env — omkeerbaar voor een week-experiment. Buiten-scope blijft altijd de knop."""
    _load_env()
    return os.getenv("mention_autotask", "0").strip().lower() in ("1", "true", "yes", "on", "ja")


def _create_task_from_voorstel(st, orec, vst) -> str | None:
    """Maak een project owned door rol `orec` uit een dialoog-voorstel, met de voorgestelde skill als
    checklist-item (de daemon voert projectwerk uit onder de EIGENAAR-rol, dus de voorstellende rol is de
    eigenaar). Returnt het nieuwe pid, of None bij een ongeldige rol/cirkel/lege titel. Puur de creatie;
    herkomst-trail en het weghalen van het voorstel doet de caller. Gedeeld door de auto- en knop-route."""
    if orec is None or org.is_circle(orec):
        return None
    titel = str((vst or {}).get("titel", "")).strip()[:200]
    if not titel:
        return None
    new_pid = st.projects.create(orec.id, titel, "human")
    sk = vst.get("skill") or None
    payload = vst.get("payload") if isinstance(vst.get("payload"), dict) else {}
    ok = True
    if sk:
        try:
            from nooch_village.skill_match import _payload_ok
            ok = _payload_ok(sk, payload, shared_registry())
        except Exception:
            ok = True
    cl = st.projects.checklist_add(new_pid, "From dialogue")
    if cl:
        st.projects.check_add(new_pid, cl["id"], titel, skill=sk, payload=payload, payload_ok=ok)
    return new_pid


def _parse_triage(out: str):
    """Split het triage-antwoord in {fit, welk_stuk, kan_direct, reactie} of None (fail-closed). Verwacht
    JSON {fit:'ja|deels|nee', welk_stuk, kan_direct:bool, reactie}. Ongeldige fit of lege reactie → None,
    zodat de caller terugvalt op een gewone platte-tekst-reactie (geen triage-gok op rommel)."""
    txt = (out or "").strip()
    try:
        from nooch_village.skill_match import _extract_json
        data = _extract_json(txt)
    except Exception:
        data = None
    if not isinstance(data, dict):
        return None
    fit = str(data.get("fit", "")).strip().lower()
    if fit not in ("ja", "deels", "nee"):
        return None
    reactie = str(data.get("reactie", "")).strip()
    if not reactie:
        return None
    return {"fit": fit, "welk_stuk": str(data.get("welk_stuk", "")).strip(),
            "kan_direct": bool(data.get("kan_direct")), "reactie": reactie}


def _reply_to_mentions(st: _Stores, pid: str, text: str) -> int:
    """Laat elke in `text` @genoemde AI-persona één keer meedenken op de wall, met de aanleidende
    comment bovenaan de context. Cap op mention_reply_limit (default 2, uit .env/env) tegen LLM-budget.
    Fail-closed: geen persona-match, geen LLM-antwoord of een exceptie → geen post, en het bestaande
    notificatie-gedrag blijft ongemoeid. Alleen de aanroeper (mens-comment) mag dit triggeren."""
    try:
        personas = _mentioned_personas(st, text)
    except Exception:
        return 0
    if not personas:
        return 0
    _load_env()
    try:
        limit = max(0, int(os.getenv("mention_reply_limit", "2")))
    except (TypeError, ValueError):
        limit = 2
    prefix = f"De mens vraagt jou: {(text or '').strip()}"
    replied = 0
    for persona in personas:
        if replied >= limit:
            break
        try:
            if _ai_reply(st, pid, persona=persona, prefix=prefix):
                replied += 1
        except Exception:
            continue
    return replied


# De @mention-reply doet blokkerende LLM-calls; die mogen de POST (en dus het verschijnen van de eigen
# comment op de wall) niet ophouden. Async = default (prod); tests zetten dit op False voor determinisme.
_MENTION_REPLY_ASYNC = True


def _run_mention_reply(st: _Stores, pid: str, text: str):
    """Draai de @mention-reply. Async (default): start 'm in een daemon-thread en geef de Thread terug
    (de comment staat dan al op de wall; het AI-antwoord landt zodra de LLM klaar is, zichtbaar bij de
    volgende refresh). Sync (test): draai inline en geef het aantal replies (int) terug. De stores zijn
    flock-veilig, dus een schrijf vanuit de thread is veilig; _reply_to_mentions is al fail-closed."""
    if _MENTION_REPLY_ASYNC:
        import threading
        t = threading.Thread(target=lambda: _reply_to_mentions(st, pid, text), daemon=True)
        t.start()
        return t                                     # niet-int → "AI denkt mee…"; joinbaar in de test
    return _reply_to_mentions(st, pid, text)         # int aantal replies


def _parse_trekker(val: str):
    """'person:<id>' of 'persona:<id>' → (person_id of '', agent_id of '')."""
    val = (val or "").strip()
    if val.startswith("person:"):
        return val[7:], ""
    if val.startswith("persona:"):
        return "", val[8:]
    return "", ""


def _handle_person_add(data_dir: str, form: dict, username: str | None = None) -> tuple[str, int]:
    """Maak een persoon aan in people.json met een tijdelijk wachtwoord en toon dat éénmalig.

    Velden: voornaam, achternaam, email. Geeft (HTML-body, statuscode) terug (geen redirect),
    zodat het tijdelijke wachtwoord niet in een URL of browser-history terechtkomt.
    Autorisatie: alleen anchor-lead (people-beheer is org-breed); guest mag alles.
    """
    st = _Stores(data_dir)
    actor = st.people.by_email(username) if username != "guest" else None
    if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
        return "No access — only the anchor lead may do this", 403
    if actor is None and username != "guest":
        return "No access — user not recognised", 403
    g = lambda k: (form.get(k) or [""])[0].strip()
    voornaam, achternaam, email = g("voornaam"), g("achternaam"), g("email")
    back = g("next") or "/"
    if not back.startswith("/"):
        back = "/"
    naam = " ".join(p for p in (voornaam, achternaam) if p)
    if not naam or not email:
        body = ("<div class='c2-sec'><h3>Persoon toevoegen</h3>"
                "<p style='color:#c0392b'>First name, last name and email address are required.</p>"
                f"<p><a href='{_e(back)}'>← terug</a></p></div>")
        return _page("Persoon toevoegen", body), 200

    if st.people.by_email(email) is not None:
        body = ("<div class='c2-sec'><h3>Persoon toevoegen</h3>"
                f"<p style='color:#c0392b'>Er bestaat al een persoon met {_e(email)}.</p>"
                f"<p><a href='{_e(back)}'>← terug</a></p></div>")
        return _page("Persoon toevoegen", body), 200

    person = st.people.add(naam, email)
    temp = _auth.generate_temp_password()
    st.people.set_password(person.id, _auth.hash_password(temp))

    body = (
        "<div class='c2-sec'><h3>✓ Person added</h3>"
        f"<p><b>{_e(person.name)}</b> — {_e(email)}</p>"
        "<p class='muted'>Pass on this temporary password. It is shown only once:</p>"
        f"<p style='font-size:1.4rem;font-family:monospace;background:#f4f1ec;"
        f"padding:.6rem 1rem;border-radius:6px;display:inline-block'>{_e(temp)}</p>"
        f"<p style='margin-top:1rem'><a href='{_e(back)}'>← terug</a></p></div>"
    )
    return _page("Person added", body), 200


def _handle_person_reset(data_dir: str, form: dict, username: str | None = None) -> tuple[str, int]:
    """Reset het wachtwoord van een bestaande deelnemer: zet een nieuw tijdelijk wachtwoord en
    toon dat éénmalig (niet via redirect, zodat het niet in de URL/history belandt).
    Autorisatie: alleen anchor-lead (people-beheer is org-breed); guest mag alles."""
    st = _Stores(data_dir)
    actor = st.people.by_email(username) if username != "guest" else None
    if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
        return "No access — only the anchor lead may do this", 403
    if actor is None and username != "guest":
        return "No access — user not recognised", 403
    g = lambda k: (form.get(k) or [""])[0].strip()
    pid = g("pid")
    back = g("next") or "/admin"
    if not back.startswith("/"):
        back = "/admin"
    person = st.people.get(pid)
    if person is None:
        body = ("<div class='c2-sec'><h3>Wachtwoord resetten</h3>"
                "<p style='color:#c0392b'>Person not found.</p>"
                f"<p><a href='{_e(back)}'>← terug</a></p></div>")
        return _page("Wachtwoord resetten", body), 200
    temp = _auth.generate_temp_password()
    st.people.set_password(person.id, _auth.hash_password(temp))
    body = (
        "<div class='c2-sec'><h3>✓ Wachtwoord gereset</h3>"
        f"<p><b>{_e(person.name)}</b> — {_e(person.email)}</p>"
        "<p class='muted'>Pass on this temporary password. It is shown only once:</p>"
        f"<p style='font-size:1.4rem;font-family:monospace;background:#f4f1ec;"
        f"padding:.6rem 1rem;border-radius:6px;display:inline-block'>{_e(temp)}</p>"
        f"<p style='margin-top:1rem'><a href='{_e(back)}'>← terug</a></p></div>"
    )
    return _page("Wachtwoord gereset", body), 200


_MIN_PASSWORD_LEN = 10


def _password_change(data_dir: str, form: dict, username: str | None):
    """Self-service wachtwoordwijziging (self óf geforceerd bij een temp). Valideert het huidige
    wachtwoord, het beleid (min. lengte + ≠ huidig) en de bevestiging. (True, None) bij succes → de
    caller redirect + verbreekt oude sessies; (False, foutpagina) bij een fout."""
    st = _Stores(data_dir)
    g = lambda k: (form.get(k) or [""])[0]
    current, new, confirm = g("current"), g("new"), g("confirm")
    forced = st.people.must_change(username or "")
    person = st.people.by_email(username or "")
    us = _auth.UserStore(os.path.join(data_dir, "people.json"))

    def fail(msg):
        return False, _auth.password_change_page(error=msg, forced=forced)

    if person is None:
        return fail("User not recognised.")
    # Een VRIJWILLIGE wijziging vraagt het huidige wachtwoord; een VERPLICHTE (temp na eerste login/reset)
    # NIET — de gebruiker is net via login geauthenticeerd (die verifieerde het temp al). Het huidig-veld
    # lokt daar bovendien browser-autofill van het OUDE wachtwoord uit → een onmogelijk-op-te-lossen loop.
    if not forced and not us.verify_by_email(username or "", current):
        return fail("Current password is incorrect.")
    if new != confirm:
        return fail("The new passwords do not match.")
    if len(new) < _MIN_PASSWORD_LEN:
        return fail(f"Choose at least {_MIN_PASSWORD_LEN} characters.")
    if us.verify_by_email(username or "", new):      # nieuw ≠ het huidige/temp wachtwoord (zonder typen)
        return fail("Choose a different password from your current one.")
    st.people.set_own_password(person.id, _auth.hash_password(new))
    return True, None


def is_circle_lead(person_id: str, circle_id: str, assignments) -> bool:
    """Geeft True als person_id filler is van {circle_id}__circle_lead."""
    if not person_id or not circle_id:
        return False
    role_id = f"{circle_id}__circle_lead"
    return any(f.type == "person" and f.id == person_id
               for f in assignments.fillers_of(role_id))


def is_role_filler(person_id: str, role_id: str, assignments) -> bool:
    """Geeft True als person_id een person-filler is van role_id."""
    if not person_id or not role_id:
        return False
    return any(f.type == "person" and f.id == person_id
               for f in assignments.fillers_of(role_id))


def resolve_circle_id(owner: str, records) -> str | None:
    """De cirkel van een project/metric/checklist-eigenaar, ongeacht de vorm van `owner`:
    een rol → zijn ouder-cirkel; een cirkel → zichzelf; een Individueel Initiatief
    ("ii:<circle>") → de cirkel uit de prefix. Onbekend/leeg → None."""
    if not owner:
        return None
    if owner.startswith(_II_PREFIX):
        return owner[len(_II_PREFIX):]
    rec = records.get(owner)
    if rec is None:
        return None
    return owner if org.is_circle(rec) else rec.parent


def is_circle_member(person_id: str, circle_id: str, records, assignments) -> bool:
    """True als person_id Circle Lead is van circle_id óf een rol vervult die in die
    cirkel hangt (parent == circle_id)."""
    if not person_id or not circle_id:
        return False
    if is_circle_lead(person_id, circle_id, assignments):
        return True
    return any(getattr(r, "parent", None) == circle_id
               and any(f.type == "person" and f.id == person_id
                       for f in assignments.fillers_of(r.id))
               for r in records.all())


def _role_gate(target: str, username: str | None, st) -> str | None:
    """Poort voor operationele takken. `target` = de eigenaar/node van het object
    (rol-id, cirkel-id of "ii:<circle>"). Geeft een foutmelding terug bij weigering,
    anders None (toegang). Regel: rolvervuller van de rol OF Circle Lead van de cirkel.
    "guest" (auth uit) mag alles; ingelogde-maar-onbekende wordt geweigerd."""
    if username == "guest":
        return None
    actor = st.people.by_email(username)
    if actor is None:
        return "No access — user not recognised"
    if (is_role_filler(actor.id, target, st.assign)
            or is_circle_lead(actor.id, resolve_circle_id(target, st.records), st.assign)):
        return None
    return "No access — only the role filler or Circle Lead may do this"


def _member_gate(circle_id: str, username: str | None, st) -> str | None:
    """Poort voor acties die elk lid van een cirkel mag doen (bv. een eigen Individueel
    Initiatief starten). Geeft een foutmelding terug bij weigering, anders None.
    "guest" mag alles; ingelogde-maar-onbekende wordt geweigerd."""
    if username == "guest":
        return None
    actor = st.people.by_email(username)
    if actor is None:
        return "No access — user not recognised"
    if is_circle_member(actor.id, circle_id, st.records, st.assign):
        return None
    return "No access — only members of this circle may do this"


def _wd_gate(username: str | None, st) -> str | None:
    """Poort voor het beheer van de Backlog Builder: alleen de rolvervuller van de Website
    Developer-rol. Foutmelding bij weigering, anders None. "guest" (auth uit) mag alles."""
    if username == "guest":
        return None
    actor = st.people.by_email(username)
    if actor is None:
        return "No access — user not recognised"
    if is_role_filler(actor.id, WEBSITE_DEVELOPER_ROLE, st.assign):
        return None
    return "No access — only the Website Developer may manage the backlog"


class Forbidden(Exception):
    """Een artefact-schrijfactie is geweigerd. `do_POST` vertaalt dit naar een echte HTTP 403 met
    de reden — i.p.v. de operationele 303-redirect met melding — zodat een client een expliciete
    weigering ziet en een ontbrekende governance_ref nooit een 500 wordt."""


def _web_actor_id(username: str | None, st) -> str:
    """Person-id van de ingelogde mens (voor de versie-/changelog-actor). "guest"/onbekend → ""."""
    if username in (None, "guest"):
        return ""
    actor = st.people.by_email(username)
    return actor.id if actor else ""


# De rollen die de copy-prompt-generator als gereedschap krijgen. Data, geen if-boom: een rol
# erbij is één regel. Bewust een lijst en niet "elke rol met policies" — het is een SCHRIJF-tool,
# en een rol die toevallig policies heeft is daarmee nog geen copywriter.
_COPY_PROMPT_ROLLEN = ("mother_earth__nooch__community_and_email",
                       "mother_earth__nooch__noochville__copywriter")

# Welke bronnen een schrijvende rol bij oprichting bewust meekrijgt. Rol-ids in code zijn hier
# onvermijdelijk: een inclusie IS een besluit, en een besluit dat je afleidt uit een regel is geen
# besluit meer. Alleen een zaad — zodra een mens de compositie aanraakt, wint die (zie StackConfig).
_COPY_STACK_ZAAD = {
    "mother_earth__nooch__noochville__copywriter": (
        "mother_earth__nooch__community_and_email",      # copy-governance blijft daar wonen
        "mother_earth__nooch__brand_visual_designer",    # merkstem, zusterrol
    ),
    "mother_earth__nooch__community_and_email": (
        "mother_earth__nooch__brand_visual_designer",
    ),
}


def _artefact_gate(owner_role_id: str, username: str | None, st) -> str | None:
    """Poort voor artefact-schrijfacties (add/edit/archive). Regel: rolvervuller van de eigenaar-rol
    OF Circle Lead van de omvattende cirkel — via `can_write_artefact`, dus identiek voor mens en
    (op de AI-weg) persona. Foutmelding bij weigering, anders None. "guest" (auth uit) mag alles."""
    if username == "guest":
        return None
    actor = st.people.by_email(username)
    if actor is None:
        return "No access — user not recognised"
    if can_write_artefact("person", actor.id, owner_role_id, st.records, st.assign):
        return None
    return "No access — only the role filler or Circle Lead may manage artefacts"


def _lead_gate(circle_id: str, username: str | None, st) -> str | None:
    """Poort voor acties die alleen de Circle Lead van een cirkel mag (bv. een overleg
    openen/sluiten of de agenda-flow beheren). Foutmelding bij weigering, anders None.
    "guest" mag alles; ingelogde-maar-onbekende wordt geweigerd."""
    if username == "guest":
        return None
    actor = st.people.by_email(username)
    if actor is None:
        return "No access — user not recognised"
    if is_circle_lead(actor.id, circle_id, st.assign):
        return None
    return "No access — only the Circle Lead may do this"


# ── LiveKit-video: token-uitgifte ───────────────────────────────────────────
def maak_livekit_token(room: str, identity: str, naam: str) -> str:
    """Mint een LiveKit-access-token. ÉÉN plek voor de grants-config. Pakt LIVEKIT_API_KEY /
    LIVEKIT_API_SECRET automatisch uit de env. Lazy import zodat cockpit2 importeerbaar blijft
    zonder livekit-api (de token-tak faalt dan bewust closed, zie issue_livekit_token)."""
    from livekit import api
    from datetime import timedelta
    return (api.AccessToken()
            .with_identity(identity)
            .with_name(naam)
            .with_grants(api.VideoGrants(room_join=True, room=room))
            .with_ttl(timedelta(hours=2))
            .to_jwt())


VILLAGE_ROOM = "village"


def _tab_suffix(tab: str | None) -> str:
    """Saniteer een client-tab-id tot [a-z0-9], max 12 tekens. Puur een disambiguator per tabblad —
    hij wordt alleen ACHTER de server-bepaalde base geplakt en kan die base nooit overschrijven."""
    return re.sub(r"[^a-z0-9]", "", (tab or "").lower())[:12]


def issue_livekit_token(st, username: str | None, tab: str | None = None):
    """Geef een LiveKit-token uit voor de DORP-BREDE call bar. Geeft (status_code, payload) terug.

    HARDE REGEL: `room` en de identity-BASE worden UITSLUITEND server-side bepaald — nooit uit de
    request. Er is één dorp-brede room (`VILLAGE_ROOM`). `tab` is de enige request-input en dient
    alléén als per-tabblad-suffix (`<base>#tab-<tab>`) zodat meerdere tabs van dezelfde gebruiker niet
    op een duplicate-identity-kick lopen; de suffix wordt gesanitiseerd en kan de base niet vervangen
    (geen impersonatie). De vroegere wo-<circle>-<started_at>-afleiding is vervallen."""
    # AUTHZ: iedereen-ingelogd — de call bar is dorp-breed; er is geen cirkel-structuur om aan te
    # toetsen. Elke herkende ingelogde actor krijgt een (toeschouwer-)token; deelnemen/muten is een
    # gespreksdaad, geen structuurdaad. Een niet-herkende sessie krijgt geen token (fail-closed).
    server_url = os.getenv("LIVEKIT_URL", "").strip()
    if not server_url:
        return 503, {"error": "LiveKit not configured"}
    # IDENTITY-BASE: de ingelogde actor. Guest = de lokale sessie bij auth-uit → één vaste base.
    if username and username != "guest":
        actor = st.people.by_email(username)
        if actor is None:
            return 403, {"error": "Geen herkende gebruiker"}
        base, name = actor.id, actor.name
    else:
        base, name = "guest", "Gast"
    suffix = _tab_suffix(tab)
    identity = f"{base}#tab-{suffix}" if suffix else base
    try:
        token = maak_livekit_token(VILLAGE_ROOM, identity, name)
    except Exception as e:
        # De API-secret mag NOOIT lekken: alleen het exceptietype terug, geen details.
        return 500, {"error": f"token-generatie faalde ({type(e).__name__})"}
    return 200, {"token": token, "server_url": server_url, "identity": identity}


def verwijder_livekit_room(room: str) -> bool:
    """Hef een LiveKit-room op (server-side, fail-soft). True bij succes, False als het niet lukt
    (geen creds, room al weg, netwerk) — NOOIT een exception naar de caller; het afronden van het
    overleg mag hier niet op stuklopen. De API-secret lekt niet (geen details in de return)."""
    url = os.getenv("LIVEKIT_URL", "").strip()
    if not url:
        return False
    api_url = url.replace("wss://", "https://").replace("ws://", "http://")
    try:
        import asyncio
        from livekit import api

        async def _run():
            lk = api.LiveKitAPI(api_url)          # api_key/secret uit de env
            try:
                await lk.room.delete_room(api.DeleteRoomRequest(room=room))
            finally:
                await lk.aclose()

        asyncio.run(_run())
        return True
    except Exception:
        return False


def livekit_mute_participant(identity: str, muted: bool = True) -> bool:
    """Mute/unmute de audio-track(s) van een deelnemer server-side (voor iedereen), fail-soft. True als
    er minstens één audio-track is (un)gemute, False bij geen creds / deelnemer of track weg / netwerk —
    NOOIT een exception naar de caller. De API-secret lekt niet. Zelfde patroon als
    verwijder_livekit_room (api.LiveKitAPI, wss->https-conversie, async in één asyncio.run)."""
    url = os.getenv("LIVEKIT_URL", "").strip()
    if not url or not (identity or "").strip():
        return False
    api_url = url.replace("wss://", "https://").replace("ws://", "http://")
    try:
        import asyncio
        from livekit import api

        async def _run():
            lk = api.LiveKitAPI(api_url)          # api_key/secret uit de env
            try:
                p = await lk.room.get_participant(
                    api.RoomParticipantIdentity(room=VILLAGE_ROOM, identity=identity))
                sids = [t.sid for t in p.tracks if t.type == api.TrackType.AUDIO]
                for sid in sids:
                    await lk.room.mute_published_track(api.MuteRoomTrackRequest(
                        room=VILLAGE_ROOM, identity=identity, track_sid=sid, muted=muted))
                return bool(sids)
            finally:
                await lk.aclose()

        return asyncio.run(_run())
    except Exception:
        return False


def livekit_presence():
    """Aantal deelnemers in de dorp-room, server-side via list_participants — GEEN eigen
    deelnemer-verbinding, dus kost GEEN WebRTC-minuten (in tegenstelling tot de oude observer-connect).
    Fail-soft: (0, []) zonder creds of bij een fout. Ontdubbelt op de identity-base (tab-suffix eraf)
    zodat meerdere tabs van één persoon als één deelnemer tellen. Zelfde async-in-asyncio.run-patroon
    als livekit_mute_participant."""
    url = os.getenv("LIVEKIT_URL", "").strip()
    if not url:
        return 0, []
    api_url = url.replace("wss://", "https://").replace("ws://", "http://")
    try:
        import asyncio
        from livekit import api

        async def _run():
            lk = api.LiveKitAPI(api_url)          # api_key/secret uit de env
            try:
                res = await lk.room.list_participants(api.ListParticipantsRequest(room=VILLAGE_ROOM))
                return list(res.participants)
            finally:
                await lk.aclose()

        parts = asyncio.run(_run())
        seen = {}
        for p in parts:
            base = (p.identity or "").split("#tab-")[0]
            if base:
                seen[base] = p.name or base
        return len(seen), list(seen.values())[:8]
    except Exception:
        return 0, []


# Static-assets: whitelist (geen path-traversal). Nu alleen de gevendorde LiveKit-client-bundle.
_STATIC_TYPES = {
    "livekit-client.umd.min.js": "application/javascript; charset=utf-8",
    # Design-systeem-CSS (component-laag). URL draagt ?v=<inhoud-hash> (_DS_LINK),
    # dus de browser mag lang cachen: nieuwe CSS = nieuwe URL.
    "nooch.css": "text/css; charset=utf-8",
    # De gedeelde fragment-mechaniek. URL draagt ?v=<inhoud-hash> (web_base._JS_LINK).
    "nooch.js": "application/javascript; charset=utf-8",
    "nooch-logo.svg": "image/svg+xml; charset=utf-8",
    "nooch-logo.png": "image/png",
}


def role_context(st, role_id: str, fmt: str = "json"):
    """Serialiseer de volledige rol-context als (status, content_type, body).
    `fmt="markdown"` = de systeemprompt-bron voor AI-vervullers; anders JSON."""
    if not st.records.get(role_id):
        return 404, "text/plain; charset=utf-8", "Unknown role."
    # De Kroniek mee: alleen daarmee kan een feit op een pagina zeggen of zijn grond nú nog draagt.
    ctx = artefacts.serialize_context(role_id, st.records, st.att, st.evidence)
    if fmt == "markdown":
        return 200, "text/markdown; charset=utf-8", artefacts.render_context_markdown(ctx)
    return 200, "application/json; charset=utf-8", json.dumps(ctx, ensure_ascii=False, indent=2)


class _Ctx:
    """De gedeelde dispatch-state, doorgegeven aan elke geregistreerde actie-handler."""
    __slots__ = ("st", "g", "nxt", "form", "username", "action", "data_dir", "pj")

    def __init__(self, st, g, nxt, form, username, action, data_dir):
        self.st, self.g, self.nxt = st, g, nxt
        self.form, self.username, self.action, self.data_dir = form, username, action, data_dir
        self.pj = st.projects


def _act_proj_add(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        owner = g("owner")
        # Autorisatie: bij een rol → rolvervuller of Circle Lead; bij een Individueel
        # Initiatief (ii:<circle>) mag elk lid van die cirkel zijn eigen initiatief starten.
        _deny = (_member_gate(resolve_circle_id(owner, st.records), username, st)
                 if owner.startswith(_II_PREFIX)
                 else _role_gate(owner, username, st))
        if _deny:
            return nxt, _deny
        scope = g("scope").strip()
        person, agent = _parse_trekker(g("trekker"))
        col = g("col")
        create_status = "future" if col == "toekomst" else "queued"
        orec = st.records.get(owner)
        if orec is not None and org.is_circle(orec):
            # Een cirkel doet geen uitvoerend werk: projecten horen bij een rol of Individueel Initiatief.
            return nxt, "✗ a circle cannot contain a project — pick a role or Individual Action"
        # Vang de vage intake bij de bron (founder, 19 jul): een mens-project vereist één
        # zin done_when — "waar herken je aan dat dit klaar is?" De reparatie die de rol
        # anders stilletjes in zijn checklist doet, gebeurt zo vooraf, samen met de mens.
        done_when = (g("done_when") or "").strip()
        if owner and scope and not done_when:
            return nxt, "✗ also fill in how you recognise this is done (done-when)"
        if owner and scope:
            pid = pj.create(owner, scope[:200], "human", status=create_status,
                            done_when=done_when[:200],
                            person=person or None, agent=agent or None, private=(g("private") == "1"))
            if col == "wacht":
                pj.block(pid, "—")
            msg = "➕ project added"
        return nxt, msg


def _body_te_lang(body: str, kind: str) -> str:
    """Nette weigering i.p.v. stille afkapping. De store kapt af als backstop; wie een lange
    wiki-pagina plakt hoort te horen dát hij niet past, niet later te ontdekken dat de staart weg is."""
    cap = body_cap(kind)
    if len(body or "") > cap:
        return f"✗ text too long ({len(body)}/{cap} characters) — nothing saved"
    return ""


def _act_artefact_add(c):
        nxt, st, g, form, username, action, data_dir = c.nxt, c.st, c.g, c.form, c.username, c.action, c.data_dir
        msg = ""
        # AUTHZ: rolvervuller of Circle Lead — alleen de vervuller van de eigenaar-rol (of de Circle
        # Lead van de omvattende cirkel) mag artefacten binnen dat domein aanmaken; mens én AI gelijk.
        owner = g("owner")
        _deny = _artefact_gate(owner, username, st)          # check vóór de mutatie
        if _deny:
            raise Forbidden(_deny)                            # → HTTP 403, geen 303-redirect
        kind = g("kind")
        if kind not in ARTEFACT_KINDS:
            return nxt, "✗ onbekende artefact-soort"
        domain = ""
        if kind == "policy":
            # Een policy kan alleen op een domein dat de rol ÉCHT via governance bezit. Het gekozen
            # domein wordt server-side gevalideerd tegen definition.domains; geen fallback/voorbak.
            rec = st.records.get(owner)
            owner_domains = list(getattr(rec.definition, "domains", None) or []) if rec else []
            if not owner_domains:
                return nxt, ("✗ this role has no domain yet; assign one via governance first, "
                             "then you can put a policy on it")
            chosen = g("domain").strip()
            if not chosen and len(owner_domains) == 1:
                chosen = owner_domains[0]            # één domein → vaste keuze (form stuurt 'm mee)
            if chosen not in owner_domains:
                return nxt, "✗ pick a domain this role actually owns"
            domain = chosen
        te_lang = _body_te_lang(g("body"), kind)
        if te_lang:
            return nxt, te_lang
        gref = f"domain:{domain}" if domain else f"role:{owner}"
        actor_id = _web_actor_id(username, st)
        a = st.att.add(owner, kind, title=g("title"), body=g("body"),
                       url=g("url"), domain=domain, inherit=True,   # policies gelden altijd voor iedereen
                       actor_id=actor_id, actor_type="person",
                       governance_ref=gref, change_note="aangemaakt")
        if a is None:
            return nxt, "✗ artefact not created"
        artefacts.log_change(data_dir, action="add", artefact=a, records=st.records,
                             actor_id=actor_id, actor_type="person", governance_ref=gref)
        msg = f"➕ {kind} added ({a.id})"
        return nxt, msg


def _act_artefact_edit(c):
        nxt, st, g, form, username, action, data_dir = c.nxt, c.st, c.g, c.form, c.username, c.action, c.data_dir
        msg = ""
        # AUTHZ: rolvervuller of Circle Lead — bewerken mag alleen wie de eigenaar-rol vervult.
        cur = st.att.get(g("aid"))
        if cur is None:
            return nxt, "✗ artefact not found"
        _deny = _artefact_gate(cur.anchor, username, st)      # check vóór de mutatie
        if _deny:
            raise Forbidden(_deny)
        te_lang = _body_te_lang(g("body"), cur.kind) if "body" in form else ""
        if te_lang:
            return nxt, te_lang
        gref = f"domain:{cur.domain}" if getattr(cur, 'domain', '') else f"role:{cur.anchor}"
        actor_id = _web_actor_id(username, st)
        upd = st.att.update(cur.id,
                            title=(g("title") if "title" in form else None),
                            body=(g("body") if "body" in form else None),
                            url=(g("url") if "url" in form else None),
                            actor_id=actor_id, actor_type="person",
                            governance_ref=gref, change_note="bewerkt")
        artefacts.log_change(data_dir, action="edit", artefact=upd, records=st.records,
                             actor_id=actor_id, actor_type="person", governance_ref=gref)
        msg = f"✏️ {upd.kind} updated ({upd.id})"
        return nxt, msg


def _act_artefact_archive(c):
        nxt, st, g, username, action, data_dir = c.nxt, c.st, c.g, c.username, c.action, c.data_dir
        msg = ""
        # AUTHZ: rolvervuller of Circle Lead — archiveren (nooit hard delete) mag alleen de vervuller.
        cur = st.att.get(g("aid"))
        if cur is None:
            return nxt, "✗ artefact not found"
        _deny = _artefact_gate(cur.anchor, username, st)      # check vóór de mutatie
        if _deny:
            raise Forbidden(_deny)
        gref = f"domain:{cur.domain}" if getattr(cur, 'domain', '') else f"role:{cur.anchor}"
        actor_id = _web_actor_id(username, st)
        arch = st.att.archive(cur.id, actor_id=actor_id, actor_type="person",
                              governance_ref=gref, change_note="gearchiveerd")
        artefacts.log_change(data_dir, action="archive", artefact=arch, records=st.records,
                             actor_id=actor_id, actor_type="person", governance_ref=gref)
        msg = f"🗄️ {arch.kind} gearchiveerd ({arch.id})"
        return nxt, msg


def _act_pagina_feit_add(c):
    # AUTHZ: rolvervuller of Circle Lead — een feit is inhoud van de pagina, en een pagina is een
    # note binnen het domein van de eigenaar-rol. Zelfde poort als artefact_edit, geen tweede regel.
    from nooch_village import wiki
    nxt, st, g, username, data_dir = c.nxt, c.st, c.g, c.username, c.data_dir
    cur = st.att.get(g("aid"))
    if cur is None or cur.kind != wiki.PAGINA_KIND:
        return nxt, "✗ page not found"
    _deny = _artefact_gate(cur.anchor, username, st)          # check vóór de mutatie
    if _deny:
        raise Forbidden(_deny)
    feit = wiki.maak_feit(g("tekst"), soort=g("soort"), ref=g("ref"),
                          citaat=g("citaat"), url=g("url"))
    if feit is None:
        return nxt, "✗ a fact needs text"
    # Feiten leven in meta van dezelfde note: geen tweede opslag, dus ze reizen mee in de versie-
    # historie, in het erven en in /context. Verse lees vlak vóór de update (de store her-leest
    # onder het slot, maar de meta-lijst bouwen we hier op).
    meta = dict(getattr(cur, "meta", None) or {})
    meta["feiten"] = list(wiki.feiten(cur)) + [feit]
    actor_id = _web_actor_id(username, st)
    gref = f"role:{cur.anchor}"
    upd = st.att.update(cur.id, meta=meta, actor_id=actor_id, actor_type="person",
                        governance_ref=gref, change_note="feit toegevoegd")
    artefacts.log_change(data_dir, action="edit", artefact=upd, records=st.records,
                         actor_id=actor_id, actor_type="person", governance_ref=gref)
    return nxt, f"➕ fact added ({upd.id})"


def _act_pagina_feit_del(c):
    # AUTHZ: rolvervuller of Circle Lead — zie pagina_feit_add. Verwijderen laat een versie-entry
    # achter, zodat de historie laat zien dát er een feit weg is (nooit een stille verdwijning).
    from nooch_village import wiki
    nxt, st, g, username, data_dir = c.nxt, c.st, c.g, c.username, c.data_dir
    cur = st.att.get(g("aid"))
    if cur is None or cur.kind != wiki.PAGINA_KIND:
        return nxt, "✗ page not found"
    _deny = _artefact_gate(cur.anchor, username, st)
    if _deny:
        raise Forbidden(_deny)
    huidig = list(wiki.feiten(cur))
    try:
        i = int(g("i"))
    except (TypeError, ValueError):
        return nxt, "✗ unknown fact"
    if not 0 <= i < len(huidig):
        return nxt, "✗ unknown fact"
    weg = huidig.pop(i)
    meta = dict(getattr(cur, "meta", None) or {})
    meta["feiten"] = huidig
    actor_id = _web_actor_id(username, st)
    gref = f"role:{cur.anchor}"
    upd = st.att.update(cur.id, meta=meta, actor_id=actor_id, actor_type="person",
                        governance_ref=gref,
                        change_note=f"feit verwijderd: {str(weg.get('tekst') or '')[:80]}")
    artefacts.log_change(data_dir, action="edit", artefact=upd, records=st.records,
                         actor_id=actor_id, actor_type="person", governance_ref=gref)
    return nxt, "🗑 fact removed"


def _act_pagina_voorstel(c):
    # AUTHZ: iedereen-ingelogd — een voorstel is géén mutatie. Je vraagt de eigenaar-rol iets; die
    # beslist via het bestaande verzoekmechanisme (verzoek_besluit) en pas dán wordt er geschreven.
    # Precies daarom mag dit ongated: het schrijfrecht verschuift geen millimeter.
    from nooch_village import wiki
    nxt, st, g, username = c.nxt, c.st, c.g, c.username
    cur = st.att.get(g("aid"))
    if cur is None or cur.kind != wiki.PAGINA_KIND:
        return nxt, "✗ page not found"
    voorstel = g("voorstel")
    te_lang = _body_te_lang(voorstel, cur.kind)
    if te_lang:
        return nxt, te_lang
    if not wiki.is_wijziging(cur, voorstel):
        return nxt, "✗ this is the text that is already there"
    if not g("waarom").strip():
        return nxt, "✗ say in one line what is wrong now — that is what the owner decides on"
    ontv = wiki.ontvanger(cur.anchor, st.records, st.assign)
    van_id = _web_actor_id(username, st)
    van = st.people.get(van_id) if van_id else None
    snippet, extra = wiki.voorstel_velden(
        cur, voorstel=voorstel, waarom=g("waarom"),
        van_naam=(getattr(van, "name", "") or username or "someone"), van_id=van_id or "",
        reden=ontv.get("reden") or "")
    st.notif.add("role", ontv["rol"], "", by=van_id or (username or ""),
                 snippet=snippet, extra=extra)
    naar = _name(st.records.get(ontv["rol"])) or ontv["rol"]
    return nxt, f"✓ proposal sent to {naar}"


def _act_proj_status(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        to = g("to")
        pj.reopen(g("pid"))   # was het 'done', haal dat er eerst af zodat heractiveren kan
        if to == "actief":
            pj.start(g("pid"))
        elif to == "wacht":
            pj.block(g("pid"), "—")
        elif to == "toekomst":
            pj.to_future(g("pid"))
        msg = "✓ verplaatst"
        return nxt, msg


def _act_proj_done(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pid = g("pid")
        # De projectpoort (founder, 19 jul; verhuisd 21 jul naar het einddocument): done = uitkomst
        # beantwoord in het einddocument, niet werk gedaan. Zolang het document alleen de geseede
        # opdracht bevat (of leeg is) weigert de cockpit de status Done.
        from nooch_village.projects import dod_poort
        _ds = getattr(st, "project_docs", None)
        _doc = _ds.read(pid) if _ds is not None else ""
        _dicht = dod_poort(pj.get(pid), _doc)
        if _dicht:
            return nxt, "⛔ " + _dicht
        # Outcome met behoud van de telling; de mens kent Done toe ná review (Q3).
        p = pj.get(pid) or {}
        cl = next((c for c in p.get("checklists", []) if c.get("title") == PREP_CHECKLIST_TITLE), None)
        if cl is not None:
            # De uitkomst is wat er later over dit project wordt teruggelezen: overgeslagen taken
            # horen daar expliciet in, anders leest een project dat afrondde zonder zijn kernitem
            # als volledig beantwoord (valse voltooiing).
            from nooch_village.projects import checklist_progress, not_answered_note
            done, telbaar = checklist_progress(cl)
            weg = not_answered_note(cl)
            outcome = (f"checklist voltooid ({done}/{telbaar}) — goedgekeurd na review"
                       + (f" · {weg} — dit deel is NIET beantwoord" if weg else ""))
        else:
            outcome = "goedgekeurd na review"
        pj.complete(pid, outcome); msg = "✓ afgerond"
        # DE LUS SLUIT. Vroeg iemand dit als taak, dan hoort hij nu dat het klaar is. Zonder deze
        # regel is werk dat een rol voor je oppakt een eenrichtingsweg: het gebeurt, en jij hoort
        # er nooit meer iets van. Fail-soft — een melding die niet lukt blokkeert geen afronding.
        meld_opdrachtgever(st, opdrachtgever=str(p.get("opdrachtgever") or ""),
                           wat=str(p.get("scope") or pid), bron_project=pid,
                           door=(p.get("owner") or ""))
        # Geen event vanuit dit proces — de daemon-board-watch (village._poll_board) detecteert de
        # wacht→done-overgang (blocked_on=="review") en vuurt project_completed op de in-memory bus (#10-fix).
        # Done → signaal op /signals (feed 'Projecten'): done is al de mens-poort, dus het signaal
        # komt direct goedgekeurd in de RadarStore; de founder promoveert het daar naar de kennisbank.
        # Link-dedupe ("/project?id=<pid>") maakt dit idempotent met de board-watch-hook. Fail-soft:
        # een falende signaal-aanmaak mag een done nooit blokkeren.
        # De rapport-lus (einddocument → intake → kennisbank-STAGING) draait hier bewust NIET:
        # geen synchrone LLM-call in het cockpit-proces. De daemon-board-watch herleest
        # projects.json (by_status → _maybe_reload) en pakt óók deze cockpit-done binnen één
        # poll op — daar draait project_signal.report_to_staging met de LLM-ladder.
        try:
            from nooch_village.project_signal import signal_from_project
            signal_from_project(st.radar, pj.get(pid), _doc)   # einddocument levert de conclusie
        except Exception:
            logging.getLogger("cockpit2.signals").exception("project→signaal mislukt (pid=%s)", pid)
        return nxt, msg


def _act_proj_dod(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        # Zelfde autorisatie als de andere kaart-bewerkingen: rolvervuller of Circle Lead.
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        veld = g("veld")
        if veld not in ("done_when", "dod_outcome"):
            return nxt, "✗ onbekend DoD-veld"
        if not pj.set_dod(g("pid"), veld, g("tekst")):
            return nxt, "✗ project does not exist"
        return nxt, "✓ saved"


def _act_proj_archive(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.archive(g("pid")); msg = "🗄 gearchiveerd (blijft bestaan)"
        # Archiveren is het moment waarop een project echt het bord verlaat — dán hoort het
        # (ook) als signal op /signals te staan (founder, 19 jul). Idempotent: bestond het
        # signaal al (done-hook of eerdere archivering), dan gebeurt er niets; is het al
        # verwerkt naar Oracle, dan komt het niet terug (MECE — de inhoud telt al mee).
        try:
            from nooch_village.project_signal import signal_from_project
            p = pj.get(g("pid"))
            if (p is not None and p.get("status") == "done"
                    and signal_from_project(st.radar, p)):
                msg += " · 📡 placed as a signal on /signals"
        except Exception:
            logging.getLogger("cockpit2.signals").exception(
                "project→signaal bij archiveren mislukt (pid=%s)", g("pid"))
        return nxt, msg


def _act_proj_unarchive(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.unarchive(g("pid")); msg = "↩ hersteld"
        return nxt, msg


def _act_proj_delete(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        # ── Autorisatie: Circle Lead van de cirkel van het project ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = resolve_circle_id((pj.get(g("pid")) or {}).get("owner") or "", st.records)
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "No access — only the Circle Lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        pid = g("pid")
        pj.remove(pid)
        # Cascade bij definitieve delete: index-records ÉN write-once sidecars mee-verwijderen.
        # delete_for_project logt zelf beide aantallen (records + sidecars); geen status-overgang komt hier.
        dstore = getattr(st, "deliverables", None)
        if dstore is not None:
            dstore.delete_for_project(pid)
        # Cascade: het levende einddocument (sidecar-.md) mee-verwijderen.
        docstore = getattr(st, "project_docs", None)
        if docstore is not None and docstore.delete_for(pid):
            logging.getLogger("village.project_docs").info(
                "cascade: einddocument verwijderd bij project-delete %s", pid)
        msg = "🗑 removed"
        return nxt, msg


def _act_proj_edit(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        person, agent = _parse_trekker(g("trekker"))
        pj.edit(g("pid"), scope=g("scope"), person=person, agent=agent,
                private=(g("private") == "1"), description=g("description"), label=g("label"))
        msg = "💾 saved"
        return nxt, msg


def _act_proj_comment(c):
        nxt, g, pj = c.nxt, c.g, c.pj
        msg = ""
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        if pj.add_comment(g("pid"), g("comment")):
            msg = "💬 geplaatst"
        return nxt, msg


def _act_proj_rename(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.edit(g("pid"), scope=g("scope"), allow_done=True):
            msg = "✓ title saved"
        return nxt, msg


def _act_proj_describe(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.edit(g("pid"), description=g("description"), allow_done=True):
            msg = "✓ description saved"
        return nxt, msg


def _act_proj_regen_doc(c):
        # AUTHZ: zelfde poort als de edit-route (rolvervuller of Circle Lead) — regenereren overschrijft
        # het einddocument. Forceert een verse synthese uit de deliverables ('trek oud project bij').
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        p = pj.get(g("pid"))
        if p is None:
            return nxt, "✗ project not found"
        _deny = _role_gate(p.get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        _load_env()                                          # LLM-key beschikbaar maken (zoals _ai_reply)
        import logging
        from nooch_village.inhabitant import synthesize_einddocument
        rec = st.records.get(p.get("owner"))
        ok = synthesize_einddocument(
            project_docs=st.project_docs, deliverables=st.deliverables, projects=st.projects,
            personas=st.personas, record=rec, settings={}, project=p, force_final=True,
            log=logging.getLogger("village.cockpit_regen"), data_dir=c.data_dir)
        return nxt, ("📄 rapport opnieuw gegenereerd" if ok
                     else "no report generated (no deliverables or no LLM key)")


def _act_proj_doc_edit(c):
        # AUTHZ: rolvervuller of Circle Lead — het einddocument is operationeel werk binnen de rol; de
        # mens redigeert het bij review via dezelfde poort als andere project-operaties.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        store = getattr(st, "project_docs", None)
        if store is not None:                              # atomic write; last-writer wint (v1, geen merge)
            store.write(g("pid"), g("doc"))
        return nxt, "📄 end document saved"


def _act_proj_settrekker(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        person, agent = _parse_trekker(g("trekker"))
        if pj.edit(g("pid"), person=person, agent=agent, allow_done=True):
            msg = "✓ owner saved"
        return nxt, msg


def _resync_trekker(pj, st, pid: str, owner: str, orec) -> None:
    """Na een owner-wissel mag de trekker niet VERWEESD achterblijven: is de huidige trekker een echte
    trekker maar géén filler van de nieuwe rol, zet 'm op de enige filler van die rol (indien precies
    één) of op leeg. Een al-lege trekker blijft leeg (dat is niet verweesd)."""
    p = pj.get(pid)
    if p is None:
        return
    fillers = st.assign.fillers_of(owner, record=orec)
    keys = {(f.type, f.id) for f in fillers}
    if p.get("person"):
        cur = ("person", p["person"])
    elif p.get("agent"):
        cur = ("persona", p["agent"])
    else:
        return                                                 # geen trekker → niets verweesd
    if cur in keys:
        return                                                 # trekker bezet de nieuwe rol → laat staan
    if len(fillers) == 1:                                      # precies één filler → daarheen
        f = fillers[0]
        pj.edit(pid, person=(f.id if f.type == "person" else ""),
                agent=(f.id if f.type == "persona" else ""), allow_done=True)
    else:                                                      # 0 of meerdere fillers → leeg (nooit verweesd)
        pj.edit(pid, person="", agent="", allow_done=True)


def _act_proj_setowner(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        owner = g("owner")
        orec = st.records.get(owner)
        if orec is None:
            msg = "✗ unknown role"
        elif org.is_circle(orec):
            # Een cirkel doet geen uitvoerend werk: een project hoort bij een rol.
            msg = "✗ a circle cannot contain a project — pick a role"
        elif pj.edit(g("pid"), owner=owner, allow_done=True):
            _resync_trekker(pj, st, g("pid"), owner, orec)     # geen verweesde trekker laten staan
            msg = "✓ role moved"
        return nxt, msg


def _act_proj_approve(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.approve(g("pid")):
            msg = "✓ draft approved — it is on the board now"
        return nxt, msg


def _act_proj_discard(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.discard(g("pid")):
            msg = "🗑 concept verworpen"
        return nxt, msg


def _act_proj_proposal_accept(c):
        # AUTHZ: rolvervuller-of-Circle-Lead — een voorstel aannemen zet werk op het bord van díe rol;
        # dat is operationeel projectwerk, zelfde poort als proj_approve voor een draft.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        from nooch_village import project_proposals
        if project_proposals.accept(pj, c.data_dir, g("pid"), person=username or ""):
            return nxt, "✓ proposal accepted — it is in Future now, activate it when you want"
        return nxt, ""


def _act_proj_proposal_reject(c):
        # AUTHZ: rolvervuller-of-Circle-Lead — zelfde poort als accepteren; wie erover mag beslissen
        # mag ook nee zeggen. De afwijzing wordt onthouden zodat dezelfde bron niet opnieuw voorstelt.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        from nooch_village import project_proposals
        if project_proposals.reject(pj, c.data_dir, g("pid")):
            return nxt, "🗑 proposal rejected — it will not be proposed again"
        return nxt, ""


def _act_proj_setlabel(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.edit(g("pid"), label=g("label"), allow_done=True):
            msg = "✓ label saved"
        return nxt, msg


_IMPACT_FIELDS = {"missie": ("missie_impact", _MISSIE_IMPACT), "business": ("business_impact", _BUSINESS_IMPACT)}
# effort is geen enum-label meer maar een numeriek veld (uren) → eigen tak proj_seteffort (zie hieronder)


def _act_proj_setimpact(c):
        # AUTHZ: rolvervuller-of-Circle-Lead — impact-labels zijn operationeel projectwerk (zelfde gate als
        # de andere proj_set*-takken). Leeg = wissen (ongelabeld); dat mag ook.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        spec = _IMPACT_FIELDS.get(g("kind"))
        if spec is None:
            return nxt, "onbekend impact-veld"
        field, allowed = spec
        value = g("value")
        if value and value not in allowed:
            return nxt, "ongeldige impact-waarde"
        if pj.edit(g("pid"), allow_done=True, **{field: value}):
            return nxt, ("✓ impact saved" if value else "✓ impact leeggemaakt")
        return nxt, ""


def _act_proj_seteffort(c):
        # AUTHZ: rolvervuller of Circle Lead — effort-inschatting is operationeel projectwerk (zelfde gate
        # als proj_setimpact). Effort wordt canoniek in uren opgeslagen ({"hours": N}); leeg = wissen.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        raw = (g("number") or "").strip().replace(",", ".")
        if not raw:                                          # leeg getal → wissen (ongeschat)
            pj.edit(g("pid"), allow_done=True, effort="")
            return nxt, "✓ effort leeggemaakt"
        try:
            n = float(raw)
        except ValueError:
            return nxt, "ongeldige effort-waarde"
        hours = int(round(n * (8 if g("unit") == "dagen" else 1)))   # dagen → uren (8-urige werkdag)
        if hours <= 0:
            pj.edit(g("pid"), allow_done=True, effort="")
            return nxt, "✓ effort leeggemaakt"
        pj.edit(g("pid"), allow_done=True, effort={"hours": hours})
        return nxt, "✓ effort saved"


def _act_proj_agendeer_verzwakt(c):
        # AUTHZ: circle-member — een spanning inbrengen is dezelfde laag als elders in het werkoverleg
        # (_member_gate). Signaal, geen blokkade: statuswissels blijven hier los van mogelijk.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        p = pj.get(g("pid"))
        if p is None:
            return nxt, "project not found"
        circle = resolve_circle_id(p.get("owner") or "", st.records)
        if not circle:
            return nxt, "no circle for this project"
        _deny = _member_gate(circle, username, st)
        if _deny:
            return nxt, _deny
        scope = p.get("scope")
        titel = (" · ".join(f"{k}: {v}" for k, v in scope.items())
                 if isinstance(scope, dict) else str(scope or "project"))
        actor = st.people.by_email(username) if username and username != "guest" else None
        # In de PERSISTENTE werkoverleg-backlog van de cirkel — opent géén overleg; komt bij het
        # eerstvolgende overleg vanzelf op de agenda.
        if st.werk.backlog_add(circle, f"Missie verzwakt: {titel}"[:140], by=(actor.name if actor else "")):
            return nxt, "✓ placed as a tension in the circle's tactical-meeting backlog"
        return nxt, ""


def _act_proj_setprivate(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.edit(g("pid"), private=(g("private") == "1"), allow_done=True):
            msg = "✓ visibility saved"
        return nxt, msg


def _act_proj_setdue(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.set_due(g("pid"), g("due")):
            msg = "📅 date saved" if g("due") else "✓ date removed"
        return nxt, msg


def _act_attach_add(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.attach_add(g("pid"), url=g("url"), title=g("title")):
            msg = "🔗 attachment added"
        return nxt, msg


def _act_attach_remove(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.attach_remove(g("pid"), g("aid")); msg = "🗑 attachment removed"
        return nxt, msg


def _act_react_add(c):
        nxt, g, pj = c.nxt, c.g, c.pj
        msg = ""
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        if pj.add_reaction(g("pid"), g("item"), g("emoji")):
            msg = "✓ reactie geplaatst"
        return nxt, msg


def _act_feed_edit(c):
        nxt, g, pj = c.nxt, c.g, c.pj
        msg = ""
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        if pj.feed_edit(g("pid"), g("item"), g("text")):
            msg = "✓ comment edited"
        return nxt, msg


def _act_feed_remove(c):
        nxt, g, pj = c.nxt, c.g, c.pj
        msg = ""
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        pj.feed_remove(g("pid"), g("item")); msg = "🗑 comment removed"
        return nxt, msg


def _act_ai_reply(c):
        nxt, st, g = c.nxt, c.st, c.g
        msg = ""
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        _load_env()
        msg = ("🤖 AI heeft meegedacht" if _ai_reply(st, g("pid"))
               else "no AI reply (no AI inhabitant on the role or no LLM key)")
        return nxt, msg


def _act_proj_feed(c):
        nxt, st, g, pj = c.nxt, c.st, c.g, c.pj
        msg = ""
        # Collaboratie: geen rol-gate — elke ingelogde gebruiker mag reageren/bijdragen
        # (de sessie-check in do_POST dekt "ingelogd = mag").
        atype, _, aid = g("author").partition(":")
        atype = atype or "human"
        kind = "comment" if atype == "human" else "update"
        entry = pj.add_feed_entry(g("pid"), g("text"), kind=kind, author_type=atype, author_id=aid)
        if entry:
            msg = "💬 update geplaatst" if kind == "update" else "💬 reactie geplaatst"
            _, by_name = _mentionables(st)
            ment = _mentions_in(g("text"), by_name)
            for ty, tid, nm in ment:
                st.notif.add(ty, tid, g("pid"), entry["id"], by="dialoog", snippet=g("text"))
            if ment:
                msg += f" · {len(ment)} genotificeerd"
            # @mention van een AI-persona → die persona antwoordt eenmalig op de wall. Alleen bij een
            # mens-comment: een persona-comment kan nooit een nieuwe reply triggeren (geen loop), ook
            # niet met een @erin. Cap + fail-closed zitten in _reply_to_mentions.
            if atype == "human":
                res = _run_mention_reply(st, g("pid"), g("text"))   # async: blokkeert de POST niet
                if isinstance(res, int):
                    if res:
                        msg += f" · {res} AI-antwoord{'en' if res != 1 else ''}"
                elif any(ty == "persona" for ty, _, _ in ment):
                    msg += " · AI denkt mee…"                        # async: antwoord landt zo op de wall
        return nxt, msg


def _act_checklist_add(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.checklist_add(g("pid"), g("title")):
            msg = "✓ checklist added"
        return nxt, msg


def _act_checklist_remove(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.checklist_remove(g("pid"), g("clid")); msg = "🗑 checklist removed"
        return nxt, msg


def _offer_skill(st, pj, pid: str, clid: str) -> bool:
    """Stil skill-aanbod bij een net toegevoegd checklist-item: match het item-tekst tegen de DNA-skills
    van de owner-rol en, bij een match, hang een aanbod aan het item. UITSLUITEND op de "Uitvoerplan"-
    checklist (de enige die de daemon uitvoert) en alleen bij een echte rol-owner (geen II, geen dangling).
    Draait de match in het cockpit-proces via de ladder; fail-closed — nooit een foutmelding.
    Grens: dit matcht en biedt aan; uitvoeren doet uitsluitend de daemon.

    Elke early-return logt een STABIELE code via refuse() (WARNING, laag volume — het pad draait alleen
    bij een menselijke check_add). Zonder deze regels kost "waarom geen aanbod?" uren gis-diagnose: de
    fail-closed maakte II/title-gate/geen-record/geen-DNA/geen-match/exceptie ononderscheidbaar in het log."""
    p = pj.get(pid) or {}
    owner = p.get("owner") or ""
    if not owner or owner.startswith(_II_PREFIX):        # II / geen owner → geen rol-DNA
        return refuse("OFFER_SKIP_II", "geen rol-owner (II/dangling) → geen skill-match", pid=pid, owner=owner)
    cl = next((c for c in (p.get("checklists") or []) if c.get("id") == clid), None)
    if cl is None:
        return refuse("OFFER_SKIP_NO_CL", "checklist niet gevonden op project", pid=pid, clid=clid)
    if cl.get("title") != PREP_CHECKLIST_TITLE:          # alleen de uitvoer-checklist
        return refuse("OFFER_SKIP_TITLE", "niet de Uitvoerplan-checklist → geen aanbod (title-gate)",
                      pid=pid, clid=clid, title=cl.get("title"))
    items = cl.get("items") or []
    if not items:
        return refuse("OFFER_SKIP_EMPTY", "Uitvoerplan leeg", pid=pid, clid=clid)
    item = items[-1]                                     # het net toegevoegde item (append't, dus laatste)
    if item.get("skill") or item.get("offer"):
        return refuse("OFFER_SKIP_HAS", "laatste item heeft al skill/offer", pid=pid, item=item.get("id"))
    orec = st.records.get(owner)
    if orec is None:                                     # owner-id matcht geen record → geen DNA-lookup mogelijk
        return refuse("OFFER_NO_RECORD", "owner-record niet gevonden in records", pid=pid, owner=owner)
    _load_env()                                          # LLM-keys beschikbaar maken (zoals bij _ai_reply)
    offers = plan_offers(orec, [item.get("text", "")], shared_registry(), name=_name(orec))
    off = offers[0] if offers else None
    if not off:                                          # geen match (plan_offers logt LLM-None/-exceptie apart)
        return refuse("OFFER_NO_MATCH", "geen DNA-skill matcht het item", pid=pid, owner=owner,
                      text=(item.get("text", "") or "")[:80])
    return pj.set_item_offer(pid, clid, item["id"], off)   # succes: het aanbod verschijnt in de UI


def _act_check_add(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if pj.check_add(g("pid"), g("clid"), g("text")):
            msg = "✓ item added"
            try:                                         # skill-aanbod is bijzaak: mag de toevoeging nooit breken
                if _offer_skill(st, pj, g("pid"), g("clid")):
                    msg += " · 🤖 aanbod"
            except Exception as e:                       # bv. een stille registry-bouwfout: niet meer onzichtbaar
                refuse("OFFER_UNCAUGHT", "skill-aanbod wierp een exceptie (weggevangen)",
                       pid=g("pid"), exc=type(e).__name__)
        return nxt, msg


def _act_check_accept(c):
        # AUTHZ: rolvervuller of Circle Lead — operationeel werk binnen een rol (een skill aan een item hangen)
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        msg = "🤖 picked up by the role" if pj.accept_item_offer(g("pid"), g("clid"), g("item")) else ""
        return nxt, msg


def _act_check_toggle(c):
        # AUTHZ: rolvervuller of Circle Lead — operationeel werk binnen een rol (een item af/aanvinken)
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        from nooch_village import project_items
        pid, clid, item = g("pid"), g("clid"), g("item")
        p = pj.get(pid) or {}
        it = next((x for cl in p.get("checklists", []) if cl.get("id") == clid
                   for x in cl.get("items", []) if x.get("id") == item), None)
        if it is not None and not it.get("done"):
            # Afvinken loopt via de resolutie-route: die kijkt daarna of de checklist compleet is en
            # zet het project dan op wacht-op-review. Anders sluit de mens het laatste item terwijl het
            # project geparkeerd blijft staan — een geblokkeerd project wordt immers niet meer getend.
            _ok, msg = project_items.resolve_item(pj, pid, clid, item, "done", by=username or "")
        else:
            pj.check_toggle(pid, clid, item)          # uitvinken: gewone toggle, geen review-gevolg
        return nxt, msg


def _act_check_skip(c):
        # AUTHZ: rolvervuller of Circle Lead — operationeel oordeel binnen een rol ("dit hoeft niet")
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        from nooch_village import project_items
        _ok, msg = project_items.resolve_item(pj, g("pid"), g("clid"), g("item"), "skip",
                                              reason=g("reason"), by=username or "")
        return nxt, msg


def _act_check_unskip(c):
        # AUTHZ: rolvervuller of Circle Lead — spiegel van check_skip (vergissing terugdraaien)
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        from nooch_village import project_items
        _ok, msg = project_items.resolve_item(pj, g("pid"), g("clid"), g("item"), "unskip",
                                              by=username or "")
        return nxt, msg


def _act_check_handoff(c):
        # AUTHZ: rolvervuller of Circle Lead — werk uit het EIGEN project doorgeven; de ontvangende rol
        # krijgt een gewoon queued project op haar bord (zelfde poort als de projectverzoek-skill).
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        from nooch_village import project_items
        _ok, msg = project_items.resolve_item(pj, g("pid"), g("clid"), g("item"), "handoff",
                                              reason=g("reason"), by=username or "",
                                              naar_rol=g("naar_rol"), records=st.records)
        return nxt, msg


def _act_check_remove(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.check_remove(g("pid"), g("clid"), g("item")); msg = "🗑 item removed"
        return nxt, msg


def _act_role_assign(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        actor = st.people.by_email(username) if username != "guest" else None
        rec = st.records.get(g("role"))
        circle_id = rec.parent if rec else None
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "No access — only the Circle Lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        person, agent = _parse_trekker(g("filler"))
        if person and st.assign.assign(g("role"), "person", person):
            msg = "✓ toegewezen"
        elif agent and st.assign.assign(g("role"), "persona", agent):
            msg = "🤖 AI toegewezen"
        return nxt, msg


def _act_role_unassign(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        actor = st.people.by_email(username) if username != "guest" else None
        rec = st.records.get(g("role"))
        circle_id = rec.parent if rec else None
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "No access — only the Circle Lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        person, agent = _parse_trekker(g("filler"))
        if person:
            st.assign.unassign(g("role"), "person", person)
        elif agent:
            st.assign.unassign(g("role"), "persona", agent)
        msg = "✓ removed"
        return nxt, msg


def _act_role_focus(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        actor = st.people.by_email(username) if username != "guest" else None
        rec = st.records.get(g("role"))
        circle_id = rec.parent if rec else None
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "No access — only the Circle Lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        person, agent = _parse_trekker(g("filler"))
        if person:
            st.assign.set_focus(g("role"), "person", person, g("focus"))
        elif agent:
            st.assign.set_focus(g("role"), "persona", agent, g("focus"))
        msg = "✓ focus saved"
        return nxt, msg


def _act_radar_set(c, status: str, ok_msg: str):
        """Radar-signaal goedkeuren/wegklikken. Poort op de EIGEN rol van het item (niet op een
        meegestuurde rol), zodat alleen de rolvervuller of Circle Lead cureert."""
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        it = st.radar.get(g("rid"))
        if it is None:
            return nxt, "✗ onbekend radar-signaal"
        _deny = _role_gate(it["role"], username, st)
        if _deny:
            return nxt, _deny
        st.radar.set_status(g("rid"), status)
        return nxt, ok_msg


def _act_radar_approve(c):
        nxt, msg = _act_radar_set(c, "goedgekeurd", "✓ added to the archive")
        # Config-vlag radar_auto_promote (default uit): goedkeuren promoveert dan meteen
        # door naar de kennisbank — hetzelfde codepad als de knop, dus dezelfde dedup/marker.
        if msg == "✓ added to the archive" and radar_promote.auto_promote_enabled(c.data_dir):
            _aid, pmsg = radar_promote.promote_signal(c.st, c.g("rid"))
            msg = f"{msg} · {pmsg}"
        return nxt, msg


def _act_radar_dismiss(c):
        return _act_radar_set(c, "afgewezen", "🗑 signaal weggeklikt")


def _act_radar_promote(c):
        """Goedgekeurd radar-signaal → kenniskaartje, MET tussenstap: het signaal wordt
        klaargezet bij "Even nakijken" (staging), waar de mens het kan bewerken, met andere
        signalen samenvoegen of weggooien; pas bij commit ontstaat het kaartje. Zelfde poort
        als de andere radar-curatie: de rolvervuller of Circle Lead van de rol van het
        signaal. (De radar_auto_promote-vlag blijft de directe route — die is een bewuste
        opt-out van deze review.)"""
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        it = st.radar.get(g("rid"))
        if it is None:
            return nxt, "✗ onbekend radar-signaal"
        _deny = _role_gate(it["role"], username, st)
        if _deny:
            return nxt, _deny
        bid, msg = radar_promote.stage_signal(st, g("rid"))
        if bid:
            return f"/kennisbank/staging?batch={bid}", msg
        return nxt, msg


def _act_radar_merge(c):
        """Drag&drop op /signals: twee goedgekeurde signalen worden er één, met de gekozen
        hoofdtekst uit de modal. Zelfde poort als de andere radar-curatie, op BEIDE signalen."""
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        doel, bron = st.radar.get(g("target_rid")), st.radar.get(g("source_rid"))
        if doel is None or bron is None:
            return nxt, "✗ onbekend radar-signaal"
        for it in (doel, bron):
            _deny = _role_gate(it["role"], username, st)
            if _deny:
                return nxt, _deny
        ok = st.radar.merge_signals(g("target_rid"), g("source_rid"), g("tekst"))
        return nxt, ("🧩 signals merged — the provenance of both travels along"
                     if ok else "✗ merging failed")


def _act_radar_koppel(c):
        """/signals MECE-knop: dit signaal staat (vrijwel) al in de kennisbank — koppel de
        herkomst aan het bestaande kaartje (stack_provenance, grounding +1), markeer het
        signaal als verwerkt. Zelfde poort als de andere radar-curatie."""
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        it = st.radar.get(g("rid"))
        if it is None:
            return nxt, "✗ onbekend radar-signaal"
        _deny = _role_gate(it["role"], username, st)
        if _deny:
            return nxt, _deny
        if it.get("promoted_atom_id"):
            return nxt, "Already handled — this signal is already linked"
        doel = g("doel")
        if not doel or st.notes.get(doel) is None:
            return nxt, "✗ target card not found"
        source = ((it.get("source") or "").strip() or (it.get("feed") or "").strip() or "radar")
        st.notes.stack_provenance(doel, source=source, reference=(it.get("link") or "").strip())
        st.notes.add_tags(doel, ["signal"])
        for m in it.get("merged_sources") or []:
            if m.get("source") or m.get("link"):
                st.notes.stack_provenance(doel, source=m.get("source") or "",
                                          reference=m.get("link") or "")
        st.radar.mark_promoted(g("rid"), doel)
        return nxt, "🔗 provenance linked to the existing signal — handled"


def _act_kb_stage_koppel(c):
        """MECE-knop in de staging-review: dit voorstel is hetzelfde inzicht als een bestaand
        kaartje — koppel het als extra bron (stack_provenance, grounding +1) in plaats van
        een tweede kaartje te maken. Signaal-voorstellen krijgen meteen hun promoted-marker."""
        st = c.st
        b = st.staging.get(c.g("bid"))
        a = next((x for x in (b or {}).get("atoms", []) if x["sid"] == c.g("sid")), None)
        doel = c.g("doel")
        if a is None or not doel or st.notes.get(doel) is None:
            return c.nxt, "✗ proposal or target card not found"
        st.notes.stack_provenance(doel, source=a.get("source") or "",
                                  reference=(a.get("reference") or ""))
        if a.get("radar_rids"):
            st.notes.add_tags(doel, ["signal"])
            for rid in a["radar_rids"]:
                al = st.radar.get(rid)
                if al is not None and not al.get("promoted_atom_id"):
                    st.radar.mark_promoted(rid, doel)
        st.staging.remove_atom(c.g("bid"), c.g("sid"))
        return c.nxt, "🔗 linked as an extra source to the existing signal"


def _acc_id_param(st, role_id: str, qs) -> str:
    """Het stabiele accountability-id uit de request. Valt fail-soft terug op de oude
    `acc`-index (bookmarks, oude fragment-links) door hem éénmalig om te rekenen."""
    aid = (qs.get("acc_id") or [""])[0]
    if aid:
        return aid
    rec = st.records.get(role_id)
    if rec is None:
        return ""
    try:
        idx = int((qs.get("acc") or ["-1"])[0])
    except (TypeError, ValueError):
        return ""
    return acc_ids.acc_id_at(rec.definition, idx) if idx >= 0 else ""


def _act_aitask_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: Circle Lead van de directe ouder-cirkel ──
        actor = st.people.by_email(username) if username != "guest" else None
        rec = st.records.get(g("role"))
        circle_id = rec.parent if rec else None
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "No access — only the Circle Lead may link AI tasks"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        # Stabiel acc_id (fail-soft terugval op de oude index, zie _acc_id_param).
        aid = g("acc_id")
        if not aid:
            rec_a = st.records.get(g("role"))
            try:
                acc_i = int(g("acc"))
            except (TypeError, ValueError):
                acc_i = -1
            aid = acc_ids.acc_id_at(rec_a.definition, acc_i) if (rec_a and acc_i >= 0) else ""
        pick = g("pick")
        if "::" in pick:
            agent, skill = pick.split("::", 1)
        else:
            agent, skill = g("agent"), g("wat")   # fallback (legacy)
        if agent and aid and st.ai.add(g("role"), aid, agent, skill, gelegd_door=username):
            msg = "🤖 AI linked to accountability"
        return nxt, msg


def _act_aitask_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: Circle Lead van de ouder-cirkel van de rol ──
        actor = st.people.by_email(username) if username != "guest" else None
        _task = next((t for t in st.ai.all() if t.id == g("tid")), None)
        _rec = st.records.get(_task.role) if _task else None
        circle_id = _rec.parent if _rec else None
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "No access — only the Circle Lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        if _task is not None and _task.kind == KIND_MIDDEL:
            st.link_kroniek.record(action="verwijderd", role_id=_task.role, acc_id=_task.acc_id,
                                   skill=_task.skill, door=username)
        st.ai.remove(g("tid")); msg = "✓ removed"
        return nxt, msg


# ── Skill-links: het dorpsmiddel aan een belofte ────────────────────────────
# AUTHZ: Circle Lead — de Circle Lead gaat over de middelen van een rol. Een koppeling is
# operationeel (omkeerbaar, gelogd), dus geen G-ronde; maar het blijft leidingwerk, geen
# rolhouder-werk. Zelfde poort als de AI-taken hierboven, bewust identiek.
#
# Wat hier NOOIT gebeurt: de TEKST van een accountability aanraken. Dat is mandaat en beweegt
# op governance-snelheid. Een koppeling zegt alleen 'dit middel dient die belofte'.

def _act_skilllink_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        role_id, skill = g("role"), g("skill")
        rec = st.records.get(role_id)
        # ── Autorisatie: Circle Lead van de directe ouder-cirkel ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = rec.parent if rec else None
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "No access — only the Circle Lead may link means"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        aid = _acc_id_param(st, role_id, {"acc_id": [g("acc_id")], "acc": [g("acc")]})
        if not rec or not aid:
            return nxt, "Unknown role or accountability"
        # Domeinpoort — absoluut, geen policy-omweg. Een beslis-skill kan alleen bij de
        # domeinhouder; de picker biedt hem elders niet eens aan, dit is de tweede sleutel.
        mag, reden = skill_meta.koppelbaar(skill, rec)
        if not mag:
            return nxt, f"Not linked — {reden}"
        if st.ai.add_link(role_id, aid, skill, gelegd_door=username) is None:
            return nxt, "Not linked — incomplete data"
        st.link_kroniek.record(action="gelegd", role_id=role_id, acc_id=aid,
                               skill=skill, door=username)
        return nxt, f"🔗 {skill_labels.label(skill)} linked to this accountability"


# AUTHZ: circle-member of iedereen-ingelogd — een means-gap melden is signaleren, geen mutatie
# van structuur of middelen. Het item landt in de human inbox; beslissen gebeurt daar, op het
# geauthenticeerde lokale oppervlak. Fail-closed op de onbekende ingelogde gebruiker.
def _act_means_gap_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        if username != "guest" and st.people.by_email(username) is None:
            return nxt, "No access — user not recognised"
        acc = (g("acc") or "").strip()
        if not acc:
            return nxt, "No accountability given"
        try:
            from nooch_village.human_inbox import HumanInbox
            hi = HumanInbox(os.path.join(st.dd, "human_inbox.json"))
            hi.add_means_gap(f"acc:{acc[:60]}", f"Geen middel dekt: {acc}",
                             role_id=g("role") or None, sensed_by=username)
        except Exception as exc:
            logging.getLogger("cockpit2.means_gap").warning("means_gap_add faalde: %s", exc)
            return nxt, "Reporting failed — see the logs"
        return nxt, "📥 reported as a means gap; review it via the human inbox"


# ── Inwoner-dossier: de persona als drager ──────────────────────────────────
# Alle takken hieronder: AUTHZ: anchor-lead — de persona is een org-breed object (hij reist mee
# tussen zetels), dus het beheer ervan hoort bij de anchor-lead. Fail-closed via _anchor_gate.
#
# Wat hier NOOIT gebeurt: purpose, accountabilities of domeinen aanraken. Dat is mandaat, dat
# leeft in de records en wijzigt alleen via governance (G0-G4).

# Voorstellen van de finetune-knop leven per proces, niet in een store: ze zijn een tussenstap
# in één menselijke handeling, geen feit dat bewaard moet blijven.
_finetune_cache: dict = {}


def _anchor_gate(st, username: str | None) -> str | None:
    """Alleen de anchor-lead beheert persona's. Guest (auth uit) mag alles."""
    if username == "guest":
        return None
    actor = st.people.by_email(username)
    if actor is None:
        return "No access — user not recognised"
    if not is_circle_lead(actor.id, "mother_earth", st.assign):
        return "No access — only the anchor lead manages inhabitants"
    return None


def _persona_kroniek(st, pid: str, veld: str, oud: str, nieuw: str, door: str | None) -> None:
    """Elke wijziging aan een persona is terug te lezen: oud → nieuw, wie, wanneer.
    Append-only; fail-soft (een kapotte log mag een bewerking nooit blokkeren)."""
    try:
        with open(os.path.join(st.dd, "persona_kroniek.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"pid": pid, "veld": veld, "oud": oud[:500], "nieuw": nieuw[:500],
                                "door": door or "?", "at": time.time()}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _act_persona_edit(c):
        # AUTHZ: anchor-lead — persona-beheer is org-breed (zie blok-comment hierboven).
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _anchor_gate(st, username)
        if _deny:
            return nxt, _deny
        pid = g("pid")
        oud = st.personas.get(pid)
        if oud is None:
            return nxt, "⛔ unknown inhabitant"
        st.personas.update(pid, mbti=g("mbti"), instructions=g("instructions"),
                           avatar=g("avatar"), prompt_extra=g("prompt_extra"))
        for veld, was in (("instructions", oud.instructions), ("prompt_extra", oud.prompt_extra),
                          ("mbti", oud.mbti)):
            if g(veld) != was:
                _persona_kroniek(st, pid, veld, was, g(veld), username)
        return nxt, "✓ personality updated"


def _act_persona_llm(c):
        # AUTHZ: anchor-lead — modelkeuze raakt het budget van het hele dorp.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _anchor_gate(st, username)
        if _deny:
            return nxt, _deny
        per_taak = {}
        for regel in (g("llm_per_taak") or "").splitlines():
            if "=" in regel:
                sleutel, _, waarde = regel.partition("=")
                if sleutel.strip() and waarde.strip():
                    per_taak[sleutel.strip()] = waarde.strip()
        if st.personas.update(g("pid"), llm={"default": g("llm_default"), "per_taak": per_taak}) is None:
            return nxt, "⛔ unknown inhabitant"
        return nxt, f"✓ model preference saved ({len(per_taak)} task override(s))"


def _act_persona_finetune(c):
        # AUTHZ: anchor-lead — de AI stelt voor, de mens kiest; niets wordt hier overschreven.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _anchor_gate(st, username)
        if _deny:
            return nxt, _deny
        pid = g("pid")
        persona = st.personas.get(pid)
        if persona is None:
            return nxt, "⛔ unknown inhabitant"
        voorstellen = _finetune_voorstellen(persona)
        if not voorstellen:
            # Fail-closed: geen LLM-antwoord → geen voorstellen, en zeker geen lege overschrijving.
            return nxt, "⛔ the AI gave no usable proposal — try again later"
        _finetune_cache[pid] = voorstellen
        return nxt, f"✨ {len(voorstellen)} proposal(s) — pick one"


def _act_persona_finetune_apply(c):
        # AUTHZ: anchor-lead — pas hier wordt er echt iets overschreven, na een menselijke keuze.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _anchor_gate(st, username)
        if _deny:
            return nxt, _deny
        pid, keuze = g("pid"), g("keuze")
        persona = st.personas.get(pid)
        if persona is None:
            return nxt, "⛔ unknown inhabitant"
        if not keuze.strip() or keuze.strip() == "(nu leeg)":
            _finetune_cache.pop(pid, None)
            return nxt, "✓ nothing changed"
        _persona_kroniek(st, pid, "prompt_extra", persona.prompt_extra, keuze, username)
        st.personas.update(pid, prompt_extra=keuze)
        _finetune_cache.pop(pid, None)
        return nxt, "✓ prompt extra updated"


def _finetune_voorstellen(persona) -> list:
    """Twee alternatieven voor de prompt-extra: strakker en ruimer. Fail-closed: bij een
    onbruikbaar antwoord een lege lijst, nooit een half voorstel."""
    huidig = (persona.prompt_extra or "").strip() or "(no prompt extra yet)"
    prompt = (f"Je helpt bij het finetunen van een werkinstructie voor een AI-inwoner.\n"
              f"Inwoner: {persona.name} ({persona.mbti}). Karakter: {persona.instructions}\n"
              f"Huidige werkinstructie: {huidig}\n\n"
              f"Geef TWEE alternatieven, elk maximaal twee zinnen:\n"
              f"STRAKKER: <scherper, minder ruimte voor interpretatie>\n"
              f"RUIMER: <meer ruimte, maar nog steeds concreet>\n"
              f"Antwoord met exact die twee regels, zonder inleiding.")
    try:
        from nooch_village import llm
        out = llm.reason(prompt, call_site="persona_finetune", max_tokens=300)
    except Exception:
        out = None
    if not out:
        return []
    uit = []
    for regel in out.splitlines():
        for kop, naam in (("STRAKKER:", "strakker"), ("RUIMER:", "ruimer")):
            if regel.strip().upper().startswith(kop):
                tekst = regel.split(":", 1)[1].strip()
                if tekst:
                    uit.append({"naam": naam, "tekst": tekst})
    return uit


def _act_persona_skill_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: alleen anchor-lead (mother_earth) ──
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "No access — only the anchor lead may add persona skills"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        if st.personas.add_skill(g("agent"), g("skill")):
            msg = "✓ skill added to the backpack"
        return nxt, msg


def _act_rov2_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # Autorisatie: elk cirkellid mag een voorstel op de agenda brengen
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if _rov_add_item(st, g("circle"), g("naam")):
            msg = "✓ agenda item added"
        return nxt, msg


def _act_rov2_add_to_group(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # Autorisatie: elk cirkellid mag aan een voorstel bijdragen
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if _rov_add_item(st, g("circle"), g("naam"), group=g("group")):
            msg = "✓ added to the proposal"
        return nxt, msg


def _act_rov2_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: Circle Lead van de cirkel die het overleg houdt ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = g("circle")
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "No access — only the Circle Lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        st.agenda.remove(g("iid")); msg = "🗑 removed from the proposal"
        return nxt, msg


def _act_rov2_remove_group(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: Circle Lead van de cirkel die het overleg houdt ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = g("circle")
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "No access — only the Circle Lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        gid = st.agenda.group_of(g("iid"))
        for m in st.agenda.members_of_group(gid):
            st.agenda.remove(m["id"])
        msg = "🗑 proposal removed"
        return nxt, msg


def _act_rov2_setkind(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # Autorisatie: cirkellid mag het type van zijn eigen voorstel vormgeven
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if g("kind") in ("amend_role", "remove_role"):
            st.agenda.update_fields(g("iid"), kind=g("kind"))
            msg = "proposal: remove role" if g("kind") == "remove_role" else "proposal: amend role"
        return nxt, msg


def _act_rov2_consent(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: Circle Lead van de cirkel die het overleg houdt ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = g("circle")
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "No access — only the Circle Lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        gid = st.agenda.group_of(g("iid"))
        members = st.agenda.members_of_group(gid)
        if members and not any(_rov_hard(st, m) for m in members):
            for m in members:
                st.agenda.set_status(m["id"], "consented")
            msg = "✓ consent — voorstel aangenomen"
        else:
            msg = "⛔ consent blocked — resolve the blocker(s)"
        return nxt, msg


def _act_rov2_end(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: Circle Lead van de cirkel die het overleg houdt ──
        actor = st.people.by_email(username) if username != "guest" else None
        circle_id = g("circle")
        if actor is not None and not is_circle_lead(actor.id, circle_id, st.assign):
            return nxt, "No access — only the Circle Lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        done = _rov_apply(st)
        # Sluiten = de vergadering écht afronden: haal de resterende (onbehandelde) agendapunten van
        # DEZE cirkel van de agenda, zodat de "Governance meeting"-knop niet groen blijft hangen door
        # open punten. Niet-geconsenteerde voorstellen vervallen; opnieuw indienen kan altijd.
        cleared = _rov_items(st, circle_id)
        for it in cleared:
            st.agenda.remove(it["id"])
        msg = f"✓ overleg gesloten — {len(done)} doorgevoerd"
        if cleared:
            msg += f", {len(cleared)} onbehandeld punt van de agenda gehaald"
        return nxt, msg


def _act_wo_open(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.werk.open(g("circle")); msg = "✓ werkoverleg gestart"
        return nxt, msg


def _act_wo_close(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.werk.close(g("circle"))
        # dag-observatie (tevredenheid + duur) van dit overleg wegschrijven — idempotent per dag,
        # naast de bestaande all-time aggregaten in de log.
        _lg = st.werk.log(g("circle"))
        if _lg:
            observations.record_werk_daily(st.observations, g("circle"), _lg[-1])
        msg = "✓ werkoverleg gesloten"
        return nxt, msg


def _act_wo_presence(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.werk.set_presence(g("circle"), g("pid"), g("present") == "1")
        msg = "✓ aanwezig" if g("present") == "1" else "✗ absent (tasks paused)"
        return nxt, msg


def _act_wo_present_all(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        for p in _members_of_circle(st, g("circle")):
            st.werk.set_presence(g("circle"), p.id, True)
        msg = "✓ allen aanwezig"
        return nxt, msg


def _act_vangst_add(c):
        # AUTHZ: circle-member — een punt vangen is dezelfde laag als een spanning inbrengen in het
        # werkoverleg. Vangen schrijft niets buiten de eigen cirkel.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        tekst = (g("punt") or "").strip()
        if not tekst:
            return nxt, ""                       # lege Enter is geen fout, alleen niets
        actor = st.people.by_email(username) if username and username != "guest" else None
        # De vangst gaat naar de PERSISTENTE backlog: er hoeft geen overleg open te staan, en bij het
        # eerstvolgende overleg komt het punt vanzelf op de agenda. Géén typering, géén model — dat
        # is precies het verschil tussen vangen en verwerken.
        # Loopt er een overleg? Dan hoort het punt op de agenda van DAT overleg — het is daar
        # ingebracht, en de samenvatting die straks in het archief belandt moet het bevatten.
        # Anders in de persistente backlog, die bij het eerstvolgende overleg vanzelf agenda wordt.
        if st.werk.is_open(g("circle")):
            it = st.werk.agenda_add(g("circle"), tekst, by=(actor.name if actor else ""))
            if it is not None:
                it["by_id"] = actor.id if actor else ""
                st.werk._save()
        else:
            it = st.werk.backlog_add(g("circle"), tekst, by=(actor.name if actor else ""),
                                     by_id=(actor.id if actor else ""))
        # OPTIONEEL en NIET BLOKKEREND: een `@rolnaam` in dezelfde regel wordt een hint. Lost hij
        # niet op, dan gebeurt er niets — de tekst is al vastgelegd. Een tweede veld zou de flow
        # van één veld plus Enter kapotmaken, en dát is de hele functie van dit scherm.
        if it is not None:
            from nooch_village.views.vangst import rol_uit_naam
            m = re.search(r"@([\w .&-]{2,40})", tekst)
            if m:
                rol, _reden = rol_uit_naam(st, m.group(1).strip())
                if rol:
                    it["rol_hint"] = rol
                    st.werk._save()
        return nxt, ""                           # geen banner: hij zou de cursor van het veld halen


def _act_vangst_remove(c):
        # AUTHZ: circle-member — je eigen gevangen punt weggooien blijft binnen de cirkel.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        return nxt, ("🗑 removed" if st.werk.punt_remove(g("circle"), g("iid")) else "")


def _act_vangst_tekst(c):
        # AUTHZ: circle-member — de volledige spanningstekst noteren is dezelfde laag als vangen.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.werk.punt_tekst(g("circle"), g("iid"), g("tekst"))
        return nxt, ""                           # geen banner: je typt door


def _act_vangst_klaar(c):
        # AUTHZ: circle-member — afvinken sluit je eigen agenda-punt, het verplaatst geen werk.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        klaar = g("klaar") != "0"
        if not st.werk.punt_afvinken(g("circle"), g("iid"), klaar):
            return nxt, "✗ dit punt bestaat niet meer"
        return nxt, ("✓ verwerkt" if klaar else "↺ heropend")


def _act_vangst_uitkomst_edit(c):
        # AUTHZ: circle-member — de TEKST, persoon of staat van een al vastgelegde uitkomst
        # bijstellen. Het werk zelf (het project, het bericht) is al aangemaakt en verandert hier
        # niet: dit corrigeert de regel in het overlegverslag, niet wat er elders staat.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        it = st.werk.punt_get(g("circle"), g("iid"))
        u = next((x for x in ((it or {}).get("uitkomsten") or []) if x.get("id") == g("uid")), None)
        if u is None:
            return nxt, "✗ die uitkomst bestaat niet meer"
        persoon = (g("persoon") or "").strip()
        if persoon and st.people.get(persoon) is None:
            return nxt, "✗ die persoon bestaat niet"
        tekst = (g("tekst") or "").strip()
        if not tekst:
            return nxt, "✗ een uitkomst zonder tekst is geen uitkomst"
        u["tekst"] = tekst
        u["persoon"] = persoon
        # `staat` blijft staan zoals hij was: het veld is uit de flow, de waarde niet uit de data.
        st.werk._save()
        return nxt, "✓ uitkomst bijgewerkt"


def _act_vangst_uitkomst_weg(c):
        # AUTHZ: circle-member — een uitkomst-REGEL weghalen. Wat die uitkomst al aanrichtte (een
        # project, een bericht) blijft bestaan: dat is elders vastgelegd en heeft zijn eigen weg terug.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        if st.werk.punt_uitkomst_remove(g("circle"), g("iid"), g("uid")):
            return nxt, "🗑 regel weg — wat er al van gemaakt is blijft bestaan"
        return nxt, ""


def _act_vangst_uitkomst(c):
        # AUTHZ: rolvervuller of Circle Lead van de ONTVANGENDE rol — hier wordt werk bij iemand
        # anders neergelegd, en dat is een zwaardere handeling dan het punt noteren.
        from nooch_village.views.vangst import rol_uit_naam
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        circle, iid, otype = g("circle"), g("iid"), g("otype")
        it = st.werk.punt_get(circle, iid)
        if it is None:
            return nxt, "✗ dit punt bestaat niet meer"
        tekst = (g("tekst") or it.get("title") or "").strip()
        if not tekst:
            return nxt, "✗ zeg wat de uitkomst is"

        from nooch_village import zelf_verwerking as zv
        from nooch_village.views.vangst import ELK_LID_WAARDE, INDIVIDUELE_ACTIE
        persoon = (g("persoon") or "").strip()
        if persoon == ELK_LID_WAARDE:
            persoon = ""                             # expliciet "elk cirkellid"
        elif persoon and st.people.get(persoon) is None:
            return nxt, "✗ die persoon bestaat niet"
        # GEEN staat meer op een nieuwe uitkomst: de wachtstatus leeft op projectniveau. Oude
        # uitkomsten houden hun waarde — dit stopt alleen de aanwas, het wist niets.
        prive = g("prive") == "1"
        rol, reden = rol_uit_naam(st, g("rol"))
        ruw_rol = g("rol").strip()
        individueel = (not ruw_rol) or ruw_rol.lower() == INDIVIDUELE_ACTIE.lower()
        if ruw_rol and not rol and not individueel:
            return nxt, f"✗ {reden}"             # fail-closed: liever niets dan het verkeerde bureau
        # ROL IS HIER NIET VERPLICHT — zie `views.vangst.INDIVIDUELE_ACTIE`. Werk uit een overleg mag
        # aan een PERSOON hangen zonder mandaat: "Lotte belt de leverancier even" hoort bij Lotte.
        # Dit geldt UITSLUITEND voor deze live-verwerking. De AI-spanningen die getypeerd in de inbox
        # belanden lopen via `_act_vangst_verwerk` hieronder en houden hun rol-borging; verruim die
        # kant niet "voor de consistentie".
        if individueel and not persoon:
            return nxt, ("✗ kies een persoon — zonder rol én zonder persoon hangt het werk nergens")
        if rol:
            orec = st.records.get(rol)
            if orec is not None and org.is_circle(orec):
                return nxt, "✗ een cirkel heeft geen handen — kies een rol"
            _deny = _role_gate(rol, username, st)
            if _deny:
                return nxt, _deny
        else:
            # Individuele actie: het bestaande Individueel-Initiatief-eigenaarschap van deze cirkel
            # (`ii:<circle>`), niet een verzonnen pseudo-rol. AUTHZ: circle-member — je legt werk bij
            # een persoon, niet in het mandaat van een rol.
            _deny = _member_gate(circle, username, st)
            if _deny:
                return nxt, _deny

        actor = st.people.by_email(username) if username and username != "guest" else None
        aid = actor.id if actor else ""
        prov = f"↳ uit het werkoverleg van {circle}"
        ref = ""

        eigenaar = rol or f"{_II_PREFIX}{circle}"

        if otype == "project":
            pid = _outcome_project(st, eigenaar, tekst, provenance=prov, actor_id=aid)
            if prive:
                st.projects.edit(pid, private=True, allow_done=True)
            ref = "project aangemaakt"
        elif otype == "actie":
            # EEN ACTIE KOMT TERUG VIA DE INBOX, bij de persoon die hem kreeg. De regel zelf staat
            # in `route_werk` — gedeeld met de project-wizard, want twee kopieën van dezelfde
            # routing lopen na één wijziging uit de pas en dan landt werk stil verkeerd.
            #
            # Waarom die regel bestaat: dit hing aan "het eerste lopende project van deze eigenaar",
            # letterlijk de eerste die de store teruggaf. Gemeten op prod 28-08-2026: vier
            # ongerelateerde acties belandden als checklist-items op één vreemd project, en de
            # gekozen PERSOON werd bij de bestemming niet eens gebruikt.
            _soort, ref = route_werk(st, tekst=tekst, rol=rol, persoon=persoon, herkomst=prov,
                                     door=(aid or it.get("by_id") or "werkoverleg"), prive=prive)
        # 'info' is hier weg (29 aug 2026). Hij was 0 van de 9 keer gebruikt, en hij dééd iets dat
        # de actie-route beter doet: een `notif.add` naar een rol of persoon — een los bericht dat
        # daarna nergens meer opduikt. Een mededeling aan iemand is een ACTIE, en die komt terug.
        # Een post met otype=info valt nu in de `else` hieronder: fail-closed, geen stille landing.
        elif otype == "governance":
            _outcome_roloverleg(st, circle, tekst[:60], tekst[:60], tekst,
                                by=(it.get("by") or "werkoverleg"), provenance=prov)
            ref = "op de roloverleg-agenda"
        else:
            return nxt, "✗ onbekende uitkomst"

        # HERKOMST IN DE KRONIEK. Elke uitkomst van een overleg krijgt zijn eigen bewijsregel,
        # net als elke andere waarneming in het dorp. Zonder dat is "gevoeld vanuit rol X" het
        # enige spoor, en dat is een naam — geen id waarop je later kunt terugvallen.
        kroniek_id = ""
        try:
            kr = st.evidence.record(role_id=rol or circle, skill="werkoverleg",
                                    query=(it.get("title") or tekst)[:200],
                                    source="werkoverleg", status="bevestigd",
                                    result_ref=f"{otype}: {tekst[:120]}",
                                    meta={"circle": circle, "punt": iid,
                                          "door": it.get("by") or "", "persoon": persoon})
            kroniek_id = kr.get("id", "")
        except Exception as e:                       # noqa: BLE001 — fail-soft, luid
            logging.getLogger("village.cockpit").warning(
                "werkoverleg-uitkomst niet in de Kroniek vastgelegd: %s", e)

        st.werk.punt_uitkomst_add(circle, iid, {"type": otype, "rol": rol, "tekst": tekst,
                                                "ref": ref, "door": aid, "persoon": persoon,
                                                "kroniek": kroniek_id, "prive": prive})
        # VERWERKEN IS BEHANDELEN. `summary()` telt alleen punten met status "done", en niets zette
        # die status — dus stond er na een overleg met negen uitkomsten "Items handled 0, Actions 0"
        # en "9 te doen". Het werk was er, de telling niet.
        #
        # Het punt blijft zichtbaar en je kunt er meer uitkomsten onder leggen; de knop wordt
        # "↺ heropen". Een uitkomst weghalen zet hem NIET terug op open: dat is een oordeel van de
        # mens, en die knop staat er.
        st.werk.punt_afvinken(circle, iid, True)
        naam = (_name(st.records.get(rol)) if rol and st.records.get(rol)
                else f"{INDIVIDUELE_ACTIE}: {_person_name(st, persoon)}")
        return nxt, f"✓ {otype} → {naam}"


def _act_vangst_verwerk(c):
        # AUTHZ: rolvervuller of Circle Lead — verwerken raakt de rol of het project van een ander
        # (een project op zijn bord, een spanning in zijn postbus). Vangen mag elk lid; verwerken
        # niet: dat legt werk bij iemand neer.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        circle, iid, otype = g("circle"), g("iid"), g("otype")
        it = st.werk.punt_get(circle, iid)
        if it is None:
            return nxt, "✗ this point no longer exists"
        if it.get("status") == "done":
            return nxt, "✗ already processed"
        actor = st.people.by_email(username) if username and username != "guest" else None
        tekst = (g("tekst") or it.get("title") or "").strip()
        if not tekst:
            return nxt, "✗ content is required"

        if otype == "spanning":
            from nooch_village import wiki
            rol = g("rol")
            if not rol or st.records.get(rol) is None:
                return nxt, "✗ pick a role"
            _deny = _role_gate(rol, username, st)
            if _deny:
                return nxt, _deny
            # HIER BLIJFT ROL WÉL VERPLICHT (zie hierboven, `_act_vangst_uitkomst`). Dit is de
            # AI-route: de spanning wordt getypeerd en beoordeeld, en dat oordeel rust op de
            # accountabilities van een rol. Zonder rol is er niets om aan te toetsen.
            # DE BESTAANDE PIJPLIJN, letterlijk: `add` zonder `type` betekent dat de haak van
            # `spanning_ontstaat` de bevinding schrijft en de typering doet. Hier wordt dus niets
            # getypeerd; hier wordt alleen doorgegeven wie het inbracht, zodat het bij het verwerken
            # zíjn spanning wordt en niet die van het overleg.
            #
            # De haak wordt hier EXPLICIET op deze store gezet. `_bootstrap` zet hem ook, maar op een
            # `_Stores` die daarna wordt weggegooid, en elke request bouwt een verse — dus in het
            # web-pad draaide hij nergens. Hem procesbreed aanzetten zou van élke notificatie in de
            # cockpit een model-aanroep in de request maken; dat is een eigen besluit, geen bijvangst
            # van dit scherm. Daarom precies hier, op de ene plek die erom vraagt.
            try:
                from nooch_village.spanning_ontstaat import maak_verrijker
                st.notif.set_verrijker(maak_verrijker(st.records, st.assign, c.data_dir))
            except Exception as e:                       # noqa: BLE001 — fail-soft, luid
                logging.getLogger("village.cockpit").warning(
                    "vangst: verrijk-haak niet gezet (%s) — de spanning gaat rauw door", e)
            doel = wiki.ontvanger(rol, st.records, st.assign)
            if not doel.get("rol"):
                return nxt, "✗ no mailbox found for this role"
            n = st.notif.add("role", doel["rol"], "", by=(it.get("by_id") or (actor.id if actor else "")),
                             snippet=tekst)
            naam = _name(st.records.get(doel["rol"])) if st.records.get(doel["rol"]) else doel["rol"]
            waarom = f" ({doel['reden']})" if doel.get("reden") else ""
            detail = f"tension for {naam}{waarom}"
            st.werk.punt_resolve(circle, iid, otype, detail)
            return nxt, f"✓ tension sent to {naam}" + (f" — {n.get('type') or 'not yet typed'}"
                                                      if n.get("type") else "")

        if otype == "project":
            owner = g("owner")
            orec = st.records.get(owner) if owner else None
            if orec is None:
                return nxt, "✗ pick a role owner for the project"
            if org.is_circle(orec):
                return nxt, "✗ a circle cannot hold a project — pick a role"
            _deny = _role_gate(owner, username, st)
            if _deny:
                return nxt, _deny
            _outcome_project(st, owner, tekst,
                             provenance=f"↳ captured in the tactical meeting of {circle}",
                             actor_id=(actor.id if actor else ""))
            st.werk.punt_resolve(circle, iid, otype, f"{tekst} → {_name(orec)}")
            return nxt, f"✓ project on {_name(orec)}"

        if otype == "actie":
            pid_link = g("pid_link")
            tgt = st.projects.get(pid_link) if pid_link else None
            if tgt is None:
                return nxt, "✗ target project not found"
            _deny = _role_gate(tgt.get("owner") or "", username, st)
            if _deny:
                return nxt, _deny
            if _outcome_action(st, pid_link, tekst) is None:
                return nxt, "✗ could not add the action"
            st.werk.punt_resolve(circle, iid, otype, f"{tekst} → project")
            return nxt, "✓ action added to the project"

        return nxt, "✗ unknown outcome"






# ── Gedeelde uitkomst-routes (reference, don't copy) ───────────────────────────────
# Eén plek waar een uitkomst naar de BESTAANDE stores schrijft. Gebruikt door zowel het
# werkoverleg (via de vangst-uitkomsten) als de wall-outcome-flow (_act_wall_outcome). `provenance`
# (herkomst) reist mee waar de bron een wall-comment is; het werkoverleg heeft zijn eigen audit
# (de agenda) en laat 'm leeg. Zo dupliceren we de routing-logica niet.

def _prov_feed(st, pid: str, provenance: str, actor_id: str = "") -> None:
    """Leg herkomst/rationale vast als neutrale systeem-entry op een project. No-op zonder herkomst
    of pid (dan draagt de agenda de audit — werkoverleg)."""
    if pid and provenance:
        st.projects.add_feed_entry(pid, provenance, kind="system", author_type="human", author_id=actor_id)


# `_outcome_info` STOND HIER en is verwijderd (29 aug 2026).
#
# Hij stuurde een NotifStore-item per `@mention` in de tekst — precies wat een ACTIE met `@` doet,
# alleen zonder dat het als werk terugkomt. En zonder mention stuurde hij niets, terwijl hij
# "iedereen" als bestemming meldde. Dat is de reden dat die tekst niet gepatcht is maar weggehaald:
# je repareert een leugen niet, je haalt weg wat hem uitspreekt.
#
# Gemeten voordat hij wegging: één notificatie ooit uit een wall-uitkomst, in de hele historie.


def _outcome_project(st, owner: str, title: str, *, provenance: str = "", actor_id: str = "") -> str:
    """Project → nieuw project op `owner` (trigger 'human'). Herkomst als eerste systeem-entry."""
    pid = st.projects.create(owner, (title or "").strip()[:200], "human")
    _prov_feed(st, pid, provenance, actor_id)
    return pid


def route_werk(st, *, tekst: str, rol: str = "", persoon: str = "", herkomst: str = "",
               door: str = "", opdrachtgever: str = "", bron_project: str = "",
               prive: bool = False) -> tuple[str, str]:
    """Waar landt een stuk werk? ÉÉN regel, gedeeld door het werkoverleg en de project-wizard.

    Dit stond als losse tak in `_act_vangst_uitkomst` (#364). Hem hier een tweede keer uitschrijven
    zou precies de fout zijn die `docs/CONVENTIES.md` verbiedt: twee vormen van hetzelfde die na één
    wijziging uit de pas lopen — en dan landt werk stil op de verkeerde plek.

    De regel:
      * een PERSOON leest een postbus → inbox;
      * een MENS-VERVULDE ROL ook → inbox bij de rol;
      * een AI-VERVULDE ROL leest de NotifStore NOOIT → projectroute. Een bericht daarheen is
        stil verliezen, en verstuurd mag nooit kwijt betekenen.

    `opdrachtgever` reist mee zodat de lus kan sluiten: rondt de ontvanger het af, dan krijgt de
    opdrachtgever bericht (`meld_opdrachtgever`).

    Geeft (soort, ref) terug: "inbox"/"project" plus een leesbare verwijzing."""
    doel_type, doel_id = ("person", persoon) if persoon else ("role", rol)
    if doel_type == "role":
        from nooch_village.assignments import door_mens_bemand
        try:
            leest_mee = bool(rol and door_mens_bemand(rol, st.assign, st.records))
        except Exception:                                     # noqa: BLE001
            leest_mee = False
    else:
        leest_mee = bool(persoon) and st.people.get(persoon) is not None
    if leest_mee:
        st.notif.add(doel_type, doel_id, bron_project or "", by=(door or "werkoverleg"),
                     snippet=tekst,          # geen eigen cap — de store leidt de preview af (#389)
                     extra={"type": "actie", "rol": rol, "prive": prive, "herkomst": herkomst,
                            "opdrachtgever": opdrachtgever, "bron_project": bron_project})
        naam = (_person_name(st, persoon) if persoon
                else (_name(st.records.get(rol)) or rol))
        return "inbox", f"in de inbox van {naam}"
    eigenaar = rol or f"{_II_PREFIX}{bron_project or ''}"
    pid = st.projects.create(eigenaar, (tekst or "").strip()[:200], "human",
                             parent=(bron_project or None), opdrachtgever=opdrachtgever or "")
    _prov_feed(st, pid, herkomst, door)
    if prive:
        st.projects.edit(pid, private=True, allow_done=True)
    return "project", f"als project bij {_name(st.records.get(rol)) or rol}"


def meld_opdrachtgever(st, *, opdrachtgever: str, wat: str, bron_project: str = "",
                       door: str = "") -> str:
    """Sluit de lus: de opdrachtgever hoort dat wat hij vroeg klaar is.

    Zonder dit is werk dat een rol voor je oppakt een eenrichtingsweg — het gebeurt, en jij hoort
    er nooit meer iets van. Dat is precies wat een AI-rol tot theater maakt.

    Via de inbox, want de opdrachtgever is een mens die zijn inbox leest. Geen nieuw kanaal.
    Fail-soft: een melding die niet lukt mag een afronding nooit blokkeren."""
    if not opdrachtgever or st.people.get(opdrachtgever) is None:
        return ""
    try:
        n = st.notif.add("person", opdrachtgever, bron_project or "", by=(door or "village"),
                         snippet=f"Klaar: {wat}",   # geen eigen cap (#389)
                         extra={"type": "actie", "herkomst": "↳ wat je vroeg is afgerond",
                                "afronding": True, "bron_project": bron_project})
        return n.get("id", "")
    except Exception:                                          # noqa: BLE001
        logging.getLogger("cockpit2.lus").exception("afrondings-melding mislukt")
        return ""


def _outcome_action(st, pid_link: str, title: str):
    """Action → checklist-item 'Acties uit overleg' op een bestaand project. Retourneert de checklist of None.
    LET OP: doet zelf GEEN reopen — de wall-flow reopent ná dit item (harde rand: item eerst, dán reopen)."""
    p = st.projects.get(pid_link)
    if p is None:
        return None
    cl = next((cc for cc in (p.get("checklists") or []) if cc.get("title") == "Acties uit overleg"), None)
    if cl is None:
        cl = st.projects.checklist_add(pid_link, "Acties uit overleg")
    if cl:
        st.projects.check_add(pid_link, cl["id"], (title or "").strip())
    return cl


def _outcome_note(st, note_role: str, body: str, *, actor_id: str = "", change_note: str = ""):
    """Note → artefact kind='note' op een rol. De caller checkt len(body) <= 4000 VOORAF (geen truncatie)."""
    return st.att.add(note_role, "note", body=body, actor_id=actor_id,
                      actor_type="person", change_note=change_note or "aangemaakt")


def _outcome_roloverleg(st, circle: str, name: str, title: str, detail: str,
                        by: str = "", *, provenance: str = "") -> str:
    """Roloverleg → add_role-voorstel op de roloverleg-agenda (mens-route via Secretary, NIET de
    autonome Facilitator/G0-G4). Herkomst in het `example`-veld van het voorstel."""
    slug = re.sub(r"[^a-z0-9]+", "_", (detail or "").lower()).strip("_")[:40] or "punt"
    return st.agenda.add(f"{circle}__{slug}", "add_role",
                         {"name": name or "Nieuwe rol", "new_role_parent": circle,
                          "purpose": "", "add_accountabilities": []},
                         detail, by=by or "werkoverleg", title=title or (detail or "")[:60],
                         example=provenance)



def _act_wall_outcome(c):
        # Mens routeert een wall-comment naar één van de vijf bestaande uitkomsten (dezelfde routes als
        # het werkoverleg, via de gedeelde _outcome_*-helpers). Puur mens-gestuurd: geen LLM, geen
        # persona-voorstellen (dat is deel 2). HERKOMST is verplicht: elke uitkomst draagt de bron-comment
        # mee (feed-entry / change_note / notif-payload). GEEN bus-events — cross-proces, zie de
        # netwerk-bus-naad; consistent met _act_proj_done (mens-routing behoeft geen aankondiging).
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        otype = g("otype")
        src_pid, src_eid = g("pid"), g("item")
        content = (g("content") or "").strip()       # bewerkbaar inhoud-veld, voorgevuld met de comment-tekst
        # Herkomst verplicht: zonder geldige bron-comment geen uitkomst.
        src_p = pj.get(src_pid)
        src_entry = next((e for e in (src_p or {}).get("log", []) if e.get("id") == src_eid), None) if src_p else None
        if src_p is None or src_entry is None:
            return nxt, "✗ source comment not found — an outcome requires provenance"
        if not content:
            return nxt, "✗ content is required"
        actor = st.people.by_email(username)
        aid = actor.id if actor else ""
        prov = f"↳ uit wall-comment op {src_pid}#{src_eid}"   # herkomst (geen verplichte rationale)
        title = content[:60]
        # 'info' staat er niet meer bij: hij kan niet meer gekozen worden. Oude systeem-entries op
        # de wall dragen hun tekst al UITGESCHREVEN ("→ info shared created: …"), dus de historie
        # heeft deze tabel niet nodig om leesbaar te blijven.
        _LBL = {"project": "project", "action": "action",
                "note": "note", "roloverleg": "roloverleg-punt"}

        # 'info' is hier weg (29 aug 2026), net als in de inbox en het werkoverleg: één
        # verwerk-mechaniek hoort dezelfde uitkomsten te bieden. Een post met otype=info valt nu in
        # de `else` hieronder — fail-closed, geen stille landing.
        if otype == "project":
            # AUTHZ: rolvervuller of Circle Lead — een project aanmaken raakt de rol/cirkel van de eigenaar
            owner = g("owner")
            if not owner:
                return nxt, "✗ pick a role owner for the project"
            _deny = (_member_gate(resolve_circle_id(owner, st.records), username, st)
                     if owner.startswith(_II_PREFIX) else _role_gate(owner, username, st))
            if _deny:
                return nxt, _deny
            orec = st.records.get(owner)
            if orec is not None and org.is_circle(orec):
                return nxt, "✗ a circle cannot contain a project — pick a role or Individual Action"
            _outcome_project(st, owner, content, provenance=prov, actor_id=aid)

        elif otype == "action":
            # AUTHZ: rolvervuller of Circle Lead — een actie toevoegen raakt het doel-project van de eigenaar
            pid_link = g("pid_link")
            tgt = pj.get(pid_link)
            if tgt is None:
                return nxt, "✗ target project not found"
            _deny = _role_gate(tgt.get("owner") or "", username, st)
            if _deny:
                return nxt, _deny
            # HARDE RAND 1: eerst het checklist-item toevoegen, DÁN reopen — nooit andersom. reopen wist
            # outcome; met een compleet ge-vinkte checklist zou de puls het project meteen weer op DONE
            # zetten met een vals project_completed-event. Het nieuwe (open) item maakt de checklist
            # incompleet, zodat reopen veilig is. reopen() is een no-op als het project niet terminal is.
            _outcome_action(st, pid_link, content)
            _prov_feed(st, pid_link, prov, aid)      # herkomst op het doel-project
            pj.reopen(pid_link)

        elif otype == "note":
            # AUTHZ: rolvervuller of Circle Lead — een note is een artefact bij de rol (_artefact_gate)
            note_role = g("note_role")
            if not note_role:
                return nxt, "✗ pick a role for the note"
            _deny = _artefact_gate(note_role, username, st)
            if _deny:
                return nxt, _deny
            # HARDE RAND note: >4000 tekens → weigeren met melding, geen stille truncatie.
            if len(content) > 4000:
                return nxt, f"✗ note too long ({len(content)}/4000 characters) — shorten it; no automatic truncation"
            _outcome_note(st, note_role, content, actor_id=aid, change_note=prov)

        elif otype == "roloverleg":
            # AUTHZ: circle-member — een punt voor het roloverleg agenderen mag elk cirkellid
            circle = resolve_circle_id(src_p.get("owner") or "", st.records)
            _deny = _member_gate(circle, username, st)
            if _deny:
                return nxt, _deny
            _outcome_roloverleg(st, circle, title, title, content, by=f"wall:{src_pid}", provenance=prov)

        else:
            return nxt, "✗ unknown outcome"

        # Systeem-entry op de BRON-wall: de audittrail (met herkomst) leeft op de wall.
        pj.add_feed_entry(src_pid, f"→ {_LBL[otype]} created: {title}",
                          kind="system", author_type="human", author_id=aid)
        # Kwam dit uit de inbox (nid meegegeven)? Dan is die mention nu verwerkt: leg de uitkomst + reden
        # vast als historie en haal 'm uit de nieuw/gelezen-wachtrij. Eén klik: uitkomst maken én afvinken.
        nid = (g("nid") or "").strip()
        if nid:
            st.notif.mark_item_processed(nid, outcome=f"{_LBL[otype]}: {title}", by=_person_name(st, aid))
        return nxt, f"✓ {_LBL[otype]} created"


def _act_notif_read(c):
        c.st.notif.mark_item_read(c.g("nid"))
        return c.nxt, "✓ marked as read"


def _act_notif_processed(c):
        c.st.notif.mark_item_processed(c.g("nid"))
        return c.nxt, "✓ verwerkt"


def _act_notif_delete(c):
        # Prullenbak: ruis die je niet wilt verwerken uit de wachtrij halen (zacht, dismissed-vlag).
        ok = c.st.notif.delete_item(c.g("nid"))
        return c.nxt, ("🗑 weggegooid" if ok else "✗ item not found")


def _act_metrics2_fav(c):
        # Favoriet = een tegel op de node (bestaand mechanisme). Gate: cirkellid.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _member_gate(resolve_circle_id(g("node"), st.records), username, st)
        if _deny:
            return nxt, _deny
        tile = st.metrics.add_tile(g("node"), g("source"), g("measure"), g("dim") or "none", g("form") or "getal")
        return nxt, ("★ on your dashboard" if tile else "✗ could not add")


def _act_metrics2_unfav(c):
        ok = c.st.metrics.remove_tile(c.g("node"), c.g("tid"))
        return c.nxt, ("removed from your dashboard" if ok else "✗ not found")


def _act_metrics2_form(c):
        # Weergave-schakelaar: de vorm van een tegel wisselen (view losgekoppeld van data).
        ok = c.st.metrics.set_tile_form(c.g("node"), c.g("tid"), c.g("form"))
        return c.nxt, ("display changed" if ok else "✗ not found")


def _act_metrics2_dim(c):
        # Segmentatie: de dimensie van een tegel wisselen (bv. per land / per product / over tijd).
        # De view stuurt een passende vorm mee (segmentatie bepaalt welke weergaves kloppen).
        ok = c.st.metrics.set_tile_dim(c.g("node"), c.g("tid"), c.g("dim"), c.g("form"))
        return c.nxt, ("gesegmenteerd" if ok else "✗ not found")


def _act_metrics2_compare(c):
        # Metric-vs-metric: een tweede meting koppelen (combo staaf+lijn) of leeg → vergelijking eraf.
        g = c.g
        ok = c.st.metrics.set_tile_compare(g("node"), g("tid"), g("cmp_source"),
                                           g("cmp_measure"), g("cmp_dim") or "over_tijd")
        return c.nxt, ("vergelijking ingesteld" if ok else "✗ not found")


def _act_acc_check(c):
        # Dorpsbrede accountability-check (dubbelingen + formulering) via één LLM-call; bewaart de uitkomst.
        if c.username in (None, "guest"):
            return c.nxt, "✗ not allowed"
        from nooch_village.skills_impl.accountability_check import check_accountabilities
        from nooch_village.views.accountabilities import roles_with_accountabilities
        from nooch_village import llm
        roles = roles_with_accountabilities(c.st)
        res = check_accountabilities(
            roles, lambda p: llm.reason(p, call_site="cockpit_accountability_check"))
        try:
            with open(os.path.join(c.data_dir, "accountability_check.json"), "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False)
        except Exception:
            pass
        n = len(res.get("duplicates") or []) + len(res.get("weak") or [])
        return c.nxt, f"check klaar: {n} aandachtspunt(en)"


def _act_link_pursue(c):
        # Linkbuilding-doelwit op 'pitchen' zetten (geborgd in cockpit 2).
        if c.username in (None, "guest"):
            return c.nxt, "✗ not allowed"
        from nooch_village.link_targets import LinkTargets
        store = LinkTargets(os.path.join(c.data_dir, "linkbuilding_targets.json"))
        ok = store.pursue((c.g("link") or "").strip())
        return c.nxt, ("→ being pitched" if ok else "✗ not found")


def _act_link_ignore(c):
        if c.username in (None, "guest"):
            return c.nxt, "✗ not allowed"
        from nooch_village.link_targets import LinkTargets
        store = LinkTargets(os.path.join(c.data_dir, "linkbuilding_targets.json"))
        ok = store.ignore((c.g("link") or "").strip())
        return c.nxt, ("genegeerd" if ok else "✗ not found")


def _act_source_activate(c):
        # Externe bron aanzetten (mens-gated). Haalt pas bij de volgende pulse data op.
        src = (c.g("source") or "").strip()
        if not src or c.username in (None, "guest"):
            return c.nxt, "✗ not allowed"
        c.st.sources.set_active(src, True)
        return c.nxt, f"✓ {src} staat aan (data volgt bij de volgende pulse)"


def _act_source_deactivate(c):
        src = (c.g("source") or "").strip()
        if not src or c.username in (None, "guest"):
            return c.nxt, "✗ not allowed"
        c.st.sources.set_active(src, False)
        return c.nxt, f"○ {src} staat uit"


def _act_metrics2_formula(c):
        # Eigen formule van twee bestaande reeks-metingen (A op B per dag), als formule-tegel.
        st, g, username = c.st, c.g, c.username
        _deny = _member_gate(resolve_circle_id(g("node"), st.records), username, st)
        if _deny:
            return c.nxt, _deny
        f_a, f_b, f_op = g("f_a"), g("f_b"), g("f_op") or "÷"
        f_name, f_agg = g("f_name").strip(), g("f_agg") or "gemiddelde"
        if not (f_a and f_b and f_name):
            return c.nxt, "Formula: pick measure A, measure B and a name"
        t = st.metrics.add_tile(g("node"), "formule", f_name, "none", "formule",
                                extra={"f_a": f_a, "f_op": f_op, "f_b": f_b, "aggregatie": f_agg})
        return c.nxt, ("✓ formula on your dashboard" if t else "⛔ could not create the formula")


def _act_notif_add(c):
        # Zelf een spanning toevoegen (GlassFrog-capture): vrij tekstveld + vanuit welke rol je 'm voelt.
        # Landt in je eigen inbox om daarna te verwerken. Leeg → niets.
        st, g, username = c.st, c.g, c.username
        text = (g("text") or "").strip()
        role = (g("role") or "").strip()
        if not text:
            return c.nxt, "✗ empty tension"
        if role and st.records.get(role) is not None:
            st.notif.add("role", role, "", by="zelf", snippet=text)
        else:
            actor = st.people.by_email(username) if username and username != "guest" else None
            st.notif.add("person", actor.id if actor else "guest", "", by="zelf", snippet=text)
        return c.nxt, "✓ tension added"


def _act_notif_klaar(c):
        # 'Klaar met deze spanning': het ENIGE sluitmodel. Sloot je met nul uitkomsten, dan legt de handler
        # zelf 'geen uitkomst' vast (zichtbaar voor de raadsvergadering). Redirect naar de inbox met de
        # zojuist-verwerkte spanning gemarkeerd — een klein viermoment.
        st, nid = c.st, c.g("nid")
        n = st.notif._find(nid)
        if n is not None and not st.notif.verwerkingen_of(n):
            st.notif.add_outcome(nid, intent="none", otype="none", label="geen uitkomst")
        actor = st.people.by_email(c.username) if c.username and c.username != "guest" else None
        by = _person_name(st, actor.id) if actor else ""
        st.notif.mark_done(nid, by=by)
        # Zelfde lus als bij een afgerond project: wie erom vroeg hoort dat het klaar is. Een
        # afrondings-melding meldt zichzelf niet terug — anders pingen twee mensen elkaar eindeloos.
        if n is not None and not n.get("afronding"):
            meld_opdrachtgever(st, opdrachtgever=str(n.get("opdrachtgever") or ""),
                               wat=str(n.get("snippet") or "")[:120],
                               bron_project=str(n.get("bron_project") or ""), door=by)
        return f"/inbox?done={nid}", "✓ done with this tension 🎉"


def _act_notif_outcome(c):
        # Eén uitkomst vastleggen vanuit de verwerk-wizard: maak 'm via dezelfde _outcome_*-helpers als de
        # wall (met de bron-spanning als herkomst) ÉN voeg 'm toe aan het verwerk-record. Sluit het item
        # NIET — zo kun je meerdere uitkomsten op één spanning stapelen; 'Klaar' sluit pas.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        from nooch_village.inbox_wizard import intent_of, OTYPE_LABEL
        nid = g("nid")
        n = st.notif._find(nid)
        if n is None:
            return nxt, "✗ tension not found"
        otype = g("otype")
        content = (g("content") or "").strip()
        if not content:
            return nxt, "✗ content is required"
        src_pid, src_eid = n.get("project_id", ""), n.get("entry_id", "")
        src_p = pj.get(src_pid) if src_pid else None
        actor = st.people.by_email(username) if username and username != "guest" else None
        aid = actor.id if actor else ""
        by_name = _person_name(st, aid) if aid else (username or "")
        prov = f"↳ uit inbox-spanning {nid}"
        label = OTYPE_LABEL.get(otype, otype)
        made = ""
        if otype == "action":
            # FLOW 1 — ACTIE. Twee landingsplekken, en het zijn er allebei bestaande:
            #
            #   · een LOPEND PROJECT gekozen → de actie wordt een stap in de checklist die dat
            #     project al heeft. De rol van dat project bezit die lijst, dus de `@`-keuze doet
            #     hier niets meer; dat staat ook zo op het formulier.
            #   · anders → `route_werk`, DEZELFDE routing als het werkoverleg en de wizard: een
            #     mens-vervulde rol krijgt het in zijn inbox, een AI-vervulde rol krijgt een project
            #     (die leest de NotifStore nooit). Geen doel gekozen = jijzelf.
            #
            # Geen eigen actie- of projectvorm in de inbox: dat was precies de tweede mechaniek die
            # #364 en #375 weghaalden, en hij mag hier niet terugkomen.
            pid_link = g("pid_link")
            if pid_link:
                tgt = pj.get(pid_link)
                if tgt is None:
                    return nxt, "✗ target project not found"
                # AUTHZ: rolvervuller of Circle Lead — een stap toevoegen raakt het bord van die rol
                _deny = _role_gate(tgt.get("owner") or "", username, st)
                if _deny:
                    return nxt, _deny
                _outcome_action(st, pid_link, content)
                _prov_feed(st, pid_link, prov, aid)
                pj.reopen(pid_link)
                made = f"{label} in {str(tgt.get('scope') or pid_link)[:50]}"
            else:
                # `doel` is "role:<id>" of "person:<id>" uit de `@`-keuze; leeg = voor jezelf.
                soort, _, doel_id = (g("doel") or "").partition(":")
                # EXACT ÉÉN doel. `route_werk` laat een persoon van een rol winnen, dus een rol
                # kiezen én stilzwijgend jezelf als persoon meesturen laat het werk bij JOU landen
                # terwijl het scherm de ander noemt. Een test ving dat; het is precies de soort
                # stille misrouting die #364 wegnam.
                if soort == "role" and doel_id:
                    rol, persoon = doel_id, ""
                elif soort == "person" and doel_id:
                    rol, persoon = "", doel_id
                else:
                    rol, persoon = "", (aid or "")
                if rol:
                    rrec = st.records.get(rol)
                    if rrec is None or org.is_circle(rrec) or getattr(rrec, "slaapt", False) \
                            or getattr(rrec, "archived", False):
                        return nxt, "✗ that role cannot take work right now"
                elif not persoon:
                    return nxt, "✗ no one to give this to — log in or pick someone with @"
                _s, ref = route_werk(st, tekst=content, rol=rol, persoon=persoon,
                                     herkomst=f"↳ uit een spanning in de inbox",
                                     door=aid, opdrachtgever=aid, bron_project=src_pid)
                made = f"{label} {ref}"
        elif otype == "roloverleg":
            if src_p is None:
                return nxt, "✗ no source circle for a governance-meeting item"
            circle = resolve_circle_id(src_p.get("owner") or "", st.records)
            _deny = _member_gate(circle, username, st)
            if _deny:
                return nxt, _deny
            _outcome_roloverleg(st, circle, content[:60], content[:60], content,
                                by=f"inbox:{nid}", provenance=prov)
            made = f"{label}: {content[:60]}"
        else:
            return nxt, "✗ unknown outcome"
        # Audittrail op de bron-wall (als er een bron is) + de uitkomst in het verwerk-record.
        if src_pid:
            pj.add_feed_entry(src_pid, f"→ {label} created from the inbox: {content[:60]}",
                              kind="system", author_type="human", author_id=aid)
        st.notif.add_outcome(nid, intent=intent_of(otype), otype=otype, label=made, by=by_name)
        return nxt, f"✓ {label} vastgelegd — nog een uitkomst, of klik Klaar."


def _act_notif_besluit(c):
        # Beslis direct (founder, 19 jul): ja / nee / suggestie op een spanning uit de inbox.
        # Het antwoord landt als menselijke reactie op de bron-feed (@rol; comment+human zet
        # worked=False, dus de bewoner pakt het zelf weer op) plus een notificatie aan de
        # eigenaar-rol, en de spanning sluit — beslissen ís verwerken. Zo leert het dorp
        # spanningen zelf oplossen in plaats van dat de mens het werk overneemt.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        nid = g("nid")
        n = st.notif._find(nid)
        if n is None:
            return nxt, "✗ tension not found"
        keuze = g("besluit")
        if keuze not in ("ja", "nee", "suggestie"):
            return nxt, "✗ onbekend besluit"
        toel = (g("toelichting") or "").strip()
        if keuze == "suggestie" and not toel:
            return nxt, "✗ a suggestion without content does not help the inhabitant — fill in the text"
        src_pid = n.get("project_id") or ""
        p = pj.get(src_pid) if src_pid else None
        if p is None:
            return nxt, "✗ this tension has no source project to reply on — use a ping"
        owner = p.get("owner") or ""
        orec = st.records.get(owner)
        rolnaam = _name(orec) if orec else (owner or "rol")
        actor = st.people.by_email(username) if username and username != "guest" else None
        aid = actor.id if actor else ""
        by_name = (_person_name(st, aid) if aid else (username or "The Source"))
        kop = {"ja": "✓ JA", "nee": "✗ NEE", "suggestie": "💬 SUGGESTIE"}[keuze]
        tekst = (f"@{rolnaam} Besluit van The Source op je spanning: {kop}"
                 + (f" — {toel}" if toel else ""))
        entry = pj.add_feed_entry(src_pid, tekst[:1500], kind="comment",
                                  author_type="human", author_id=aid)
        st.notif.add("role", owner, src_pid, (entry or {}).get("id", ""), by=by_name,
                     snippet=(f"{kop} op '{(n.get('snippet') or '')[:70]}'"
                              + (f" — {toel[:60]}" if toel else "")))
        st.notif.add_outcome(nid, intent="besluit", otype=f"besluit_{keuze}",
                             label=(f"besluit: {kop}" + (f" — {toel[:60]}" if toel else "")),
                             by=by_name)
        st.notif.mark_item_processed(nid, outcome=f"besluit_{keuze}", by=by_name)
        return nxt, f"✓ {kop} — je antwoord staat bij de bewoner, spanning gesloten"


def _act_notif_archive(c):
        ok = c.st.notif.archive_item(c.g("nid"))
        return c.nxt, ("🗄 gearchiveerd" if ok else "⛔ only processed items can be archived")


def _act_wo_checkout(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        # De check-out is ja/nee (`ok=1|0`), niet meer een cijfer. Een oud formulier met `score`
        # wordt bewust NIET meer geaccepteerd: dat zou een 7 als nieuwe waarde binnenlaten in een
        # veld dat nu iets anders betekent. Bestaande cijfers in archieven blijven leesbaar.
        if g("ok") in ("0", "1"):
            ok = st.werk.set_checkout(g("circle"), g("pid"), g("ok"))
            msg = "✓ genoteerd" if ok else "⛔ refused — the meeting is not (or no longer) open"
        return nxt, msg


def _act_noochie_send(c):
        nxt, st, g = c.nxt, c.st, c.g
        msg = ""
        # noochie_* (send/reset/ctx) BEWUST ongated: de assistent-chat mag elke ingelogde
        # gebruiker gebruiken (sessie-check in do_POST dekt "ingelogd = mag").
        s = st.noochie
        if g("text").strip():
            ph = s.phase
            s.add("jij", g("text"))
            _load_env()
            if ph == "ask_spanning":
                s.set_field("spanning", g("text")); s.set_phase("ask_need")
                s.add("noochie", "Great! And what do you need to solve this?")
                msg = "💬"
            elif ph == "ask_need":
                s.set_field("need", g("text")); s.set_phase("free")
                s.add("noochie", (_noochie_suggest(st) or "").strip() or "…")
                msg = "💡 suggestie"
            else:
                rep = _noochie_reply(st, g("text"))
                s.add("noochie", (rep or "No AI connection right now — think of a small "
                                  "governance-meeting proposal as a next step.").strip())
                msg = "💬"
        return nxt, msg


def _act_noochie_reset(c):
        nxt, st = c.nxt, c.st
        msg = ""
        st.noochie.reset(); msg = "↺ Noochie opnieuw"
        return nxt, msg


def _act_noochie_ctx(c):
        nxt, st, g = c.nxt, c.st, c.g
        msg = ""
        st.noochie.set_field("ctx", g("ctx")); msg = "✓ context updated"
        return nxt, msg


def _act_cl_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        # Governance-poort: alleen een al bestaande terugkerende actie (geen nieuwe verwachting).
        if g("bestaand") != "1":
            msg = "⛔ only existing recurring actions — a new expectation? via the governance meeting"
        else:
            doel = g("doel") or "all"
            tt, tid = ("role", doel[5:]) if doel.startswith("role:") else ("all", "")
            it = st.checklists.add(g("node"), g("description"), g("cadence"),
                                   target_type=tt, target_id=tid, by="founder")
            msg = "✓ checklist item added" if it else "⛔ give a description"
        return nxt, msg


def _act_cl_report(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # AUTHZ: rolvervuller of Circle Lead van de betrokken rol/cirkel — afvinken van een
        # checklist-item (namens de rol/cirkel bij target_type=all). by = wie afvinkte (de mens;
        # een AI-flow kan report() direct met by=<persona> aanroepen). Geen per-individu-verplichting.
        _deny = _role_gate((st.checklists.get(g("cid")) or {}).get("node") or "", username, st)
        if _deny:
            return nxt, _deny
        if st.checklists.report(g("cid"), g("ok") == "1", value=g("value"),
                                by=(username or "founder")):
            msg = "✓ genoteerd" if g("ok") == "1" else "✗ genoteerd (aandacht nodig)"
        return nxt, msg


def _act_cl_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate((st.checklists.get(g("cid")) or {}).get("node") or "", username, st)
        if _deny:
            return nxt, _deny
        st.checklists.remove(g("cid")); msg = "🗑 checklist item removed"
        return nxt, msg


def _act_m_add_kpi(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        pick = g("pick") or "manual"
        if pick.startswith("source:"):
            src = pick[7:]
            cat = _SOURCE_KPIS.get(src)
            it = st.metrics.add_kpi(g("node"), (cat or {}).get("name", src),
                                    (cat or {}).get("unit", ""), source=src) if cat else None
            msg = "✓ KPI from data added" if it else "⛔ unknown source KPI"
        else:
            # losse KPI; optioneel 'deel in catalogus' → maak eerst een gedeelde definitie aan
            def_id, def_version = "", 0
            if g("share") == "1":
                d = st.defs.add(g("name"), owner=g("node"), provenance="sensed",
                                unit=g("unit"), definition=g("definition"), direction=g("direction"),
                                cadence=g("cadence") or "ad-hoc", meettype=g("meettype") or "snapshot",
                                window=g("window"))
                if d:
                    def_id, def_version = d["id"], st.defs.current_version_no(d["id"])
            it = st.metrics.add_kpi(g("node"), g("name"), g("unit"), definition=g("definition"),
                                    direction=g("direction"), threshold=g("threshold"),
                                    cadence=g("cadence") or "ad-hoc", meettype=g("meettype") or "snapshot",
                                    window=g("window"), def_id=def_id, def_version=def_version)
            msg = ("✓ KPI + catalogue definition added" if (it and def_id)
                   else "✓ KPI added" if it else "⛔ give a name")
        return nxt, msg


def _act_m_add_from_def(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        did = g("def_id")
        if not did and g("def_name"):
            d = st.defs.by_name(g("def_name"))
            did = d["id"] if d else ""
        kid = _kpi_id_from_def(st, g("node"), did)
        msg = "✓ KPI from the catalogue added" if kid else "⛔ pick an existing definition from the catalogue"
        return nxt, msg


def _act_def_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: alleen anchor-lead (mother_earth) ──
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "No access — only the anchor lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        d = st.defs.add(g("name"), owner="librarian", provenance="sensed",
                        unit=g("unit"), definition=g("definition"), direction=g("direction"),
                        source=g("csource"), threshold=g("threshold"),
                        cadence=g("cadence") or "ad-hoc", meettype=g("meettype") or "snapshot",
                        window=g("window"), meetwijze=g("meetwijze") or "handmatig",
                        tijd=g("tijd"), bruikbaar=g("bruikbaar"),
                        standaard=g("standaard"), benchmark=g("benchmark"),
                        bron_url=g("bron_url"), verificatie=g("verificatie"), waarde=g("waarde"))
        msg = "✓ definition added to the catalogue" if d else "⛔ give a name"
        return nxt, msg


def _act_catalog_publish(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # AUTHZ: anchor-lead — cureert welke ruwe velden een gebruiker als indicator mag kiezen
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "No access — only the anchor lead may link the catalogue"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        naam, categorie, aard = g("naam").strip(), g("categorie").strip(), g("aard").strip()
        source, veld = g("source").strip(), g("veld").strip()
        if not (naam and categorie and aard):
            return nxt, "Name, category and nature are required"
        already = any((st.defs.current(d["id"]) or {}).get("source") == source
                      and (st.defs.current(d["id"]) or {}).get("veld") == veld for d in st.defs.all())
        if already:
            return nxt, "This field is already in the catalogue"
        # Scope-3-schema: aard expliciet; aggregatie leeg + formule=False (geen formule-veld hier).
        d = st.defs.add(naam, owner="anchor-lead", provenance="curated",
                        source=source, veld=veld, categorie=categorie, aard=aard,
                        unit=g("unit"), definition=g("definition"), meetwijze="systeem")
        msg = f"✓ ‘{naam}’ in de catalogus" if d else "Publiceren mislukt (ongeldige invoer)"
        return nxt, msg


def _act_def_amend(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: alleen anchor-lead (mother_earth) ──
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "No access — only the anchor lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        # wijzig een gedeelde catalogus-definitie; migratie bepaalt wat met de historie gebeurt
        did = g("def_id")
        old = st.defs.current(did) if did else None
        if not old:
            msg = "⛔ onbekende definitie"
        else:
            from nooch_village.definitions import suggest_migration
            new = {k: g(k) for k in ("definition", "unit", "direction", "threshold", "cadence",
                                     "meettype", "window", "meetwijze", "tijd", "bruikbaar",
                                     "standaard", "benchmark", "bron_url", "verificatie",
                                     "waarde") if g(k) != ""}
            mig = g("migration") or "auto"
            if mig == "auto":
                mig, _why = suggest_migration(old, new)
                if mig == "break" and _llm_says_comparable(old, new):
                    mig = "backcast"     # LLM: historie blijft vergelijkbaar → één reeks
            ver = st.defs.amend(did, mig, **new)
            if ver:
                fields = {k: ver.get(k) for k in ("name", "unit", "definition", "direction",
                                                  "threshold", "cadence", "meettype", "window",
                                                  "meetwijze", "benchmark", "bron_url", "verificatie",
                                                  "tijd", "bruikbaar", "standaard", "waarde")}
                st.metrics.retune_kpis_to_def(did, ver["version"], fields, mig)
                label = {"clarify": "verduidelijking (reeks intact)",
                         "backcast": "back-cast (historie hergebruikt)",
                         "break": "reeksbreuk (nieuwe versie)"}.get(mig, mig)
                msg = f"✓ definitie v{ver['version']} — {label}"
            else:
                msg = "⛔ wijziging ongeldig"
        return nxt, msg


def _act_m_add_link(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        it = st.metrics.add_link(g("node"), g("name"), g("url"))
        msg = "✓ link added" if it else "⛔ give a name and URL"
        return nxt, msg


def _act_m_sample(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate((st.metrics.get(g("mid")) or {}).get("node") or "", username, st)
        if _deny:
            return nxt, _deny
        msg = "✓ meting genoteerd" if st.metrics.add_sample(g("mid"), g("value")) else "⛔ ongeldige meting"
        return nxt, msg


def _act_m_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate((st.metrics.get(g("mid")) or {}).get("node") or "", username, st)
        if _deny:
            return nxt, _deny
        st.metrics.remove(g("mid")); msg = "🗑 metric removed"
        return nxt, msg


def _act_m_pin(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # Autorisatie: het cirkeldashboard beheren is Circle Lead-werk
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.metrics.pin(g("circle"), g("mid")); msg = "✓ on the circle dashboard"
        return nxt, msg


def _act_m_unpin(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _lead_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        st.metrics.unpin(g("circle"), g("mid")); msg = "✓ removed from the dashboard"
        return nxt, msg


def _act_indicator_activate(c):
        # AUTHZ: circle-member-of-iedereen-ingelogd — open-books-besluit: iedereen met catalogus-toegang mag
        # een indicator MÉT data op een rol/cirkel-dashboard activeren (bewust ongated). Wie/wat/wanneer
        # wordt wél geregistreerd in de audit-trail (system_log.jsonl).
        nxt, st, username = c.nxt, c.st, c.username
        node = c.g("node")
        dids = [d for d in (c.form.get("did") or []) if d]
        if not node or not dids:
            return nxt, "⛔ pick at least one indicator and a dashboard"
        added = 0
        for did in dids:
            kid = _kpi_id_from_def(st, node, did)
            if not kid:
                continue
            cur = st.defs.current(did) or {}
            dim = "time" if cur.get("aard") == "reeks" else "none"   # reeks → grafiek, moment → los getal
            if st.metrics.add_tile(node, f"kpi:{kid}", "value", dim, _default_form(dim)):
                added += 1
        try:                                    # geen bus in dispatch → direct naar de audit-trail
            with open(os.path.join(st.dd, "system_log.jsonl"), "a") as f:
                f.write(json.dumps({"event": "indicator_activated", "by": username or "?",
                                    "node": node, "def_ids": dids, "at": time.time()},
                                   ensure_ascii=False) + "\n")
        except Exception:
            pass
        return nxt, (f"✓ {added} indicator(en) geactiveerd op het dashboard" if added else "⛔ niets geactiveerd")


def _act_tile_add(c):
        nxt, st, g, form, username = c.nxt, c.st, c.g, c.form, c.username
        msg = ""
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        if g("mode") == "formule":       # scope 5: formule = A op B + aggregatie (opslag; berekening volgt)
            f_a, f_op, f_b = g("f_a"), g("f_op"), g("f_b")
            f_name, f_agg = g("f_name").strip(), g("f_agg")
            if not (f_a and f_b and f_name and f_agg):
                return nxt, "Formula: pick metric A, metric B, a name and an aggregation"
            t = st.metrics.add_tile(g("node"), "formule", f_name, "none", "formule",
                                    extra={"f_a": f_a, "f_op": f_op, "f_b": f_b, "aggregatie": f_agg})
            msg = "✓ formula KPI on the dashboard (calculation follows)" if t else "⛔ could not create the formula"
        else:
            combo = g("combo") or ""
            if combo.startswith("def:"):     # indicator direct uit de catalogus → zet als KPI op de node
                did = combo[4:]
                kid = _kpi_id_from_def(st, g("node"), did)
                cur = st.defs.current(did) or {}
                dim = "time" if cur.get("aard") == "reeks" else "none"   # reeks → grafiek, moment → los getal
                combo = f"kpi:{kid}|value|{dim}" if kid else ""
            parts = combo.split("|")
            if len(parts) == 3 and parts[0]:
                ref = g("ref_kind")
                t = st.metrics.add_tile(g("node"), parts[0], parts[1], parts[2], g("form"),
                                        target=g("target"), goal_pid=("" if ref == "benchmark" else g("goal_pid")),
                                        ref_kind=ref)
                msg = "✓ KPI on the dashboard" if t else "⛔ could not create the KPI"
            else:
                msg = "⛔ pick what you want to see"
        return nxt, msg


def _act_tile_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        _deny = _role_gate(g("node"), username, st)
        if _deny:
            return nxt, _deny
        st.metrics.remove_tile(g("node"), g("tid")); msg = "🗑 tile removed"
        return nxt, msg


def _act_rov2_set(c):   # + rov2_acc_add, rov2_acc_remove, rov2_dom_add, rov2_dom_remove
        nxt, st, g, username, action = c.nxt, c.st, c.g, c.username, c.action
        msg = ""
        # Autorisatie: cirkellid mag zijn eigen voorstel vormgeven
        _deny = _member_gate(g("circle"), username, st)
        if _deny:
            return nxt, _deny
        item = st.agenda.get(g("iid"))
        if item is not None:
            draft = _rov_draft(st, item)
            if action == "rov2_set" and g("field") in ("name", "purpose"):
                draft[g("field")] = g("value")
            elif action in ("rov2_acc_add", "rov2_dom_add") and g("text").strip():
                key = "accs" if action == "rov2_acc_add" else "domains"
                t = g("text").strip()
                if t.lower() not in {x.lower() for x in draft[key]}:   # dedup (ook bij 'herstel')
                    draft[key].append(t)
            elif action in ("rov2_acc_remove", "rov2_dom_remove"):
                key = "accs" if action == "rov2_acc_remove" else "domains"
                text = g("text")
                if text:                                              # diff-weergave: verwijder op waarde
                    draft[key] = [x for x in draft[key] if x != text]
                else:
                    try:
                        draft[key].pop(int(g("idx")))
                    except (ValueError, IndexError):
                        pass
            _rov_save_draft(st, g("iid"), draft)
            msg = "✓ proposal updated"
        return nxt, msg


def _act_backlog_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # AUTHZ: iedereen-ingelogd — elke ingelogde gebruiker mag een backlog-item indienen
        # (de sessie-check in do_POST dekt "ingelogd = mag"; guest = auth uit = mag ook)
        actor = st.people.by_email(username) if username != "guest" else None
        if st.backlog.add(g("titel"), g("beschrijving"), g("type"), g("domein"),
                          actor.id if actor else ""):
            msg = "✓ submitted to the backlog"
        return nxt, msg


def _act_backlog_update_staat(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # AUTHZ: rolvervuller website_developer — beheer van de backlog (staat verplaatsen)
        _deny = _wd_gate(username, st)
        if _deny:
            return nxt, _deny
        if st.backlog.update_staat(g("bid"), g("staat")):
            msg = "✓ state updated"
        return nxt, msg


def _act_backlog_update_prioriteit(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # AUTHZ: rolvervuller website_developer — beheer van de backlog (impact/effort)
        _deny = _wd_gate(username, st)
        if _deny:
            return nxt, _deny
        if st.backlog.update_prioriteit(g("bid"), g("impact"), g("effort")):
            msg = "✓ priority updated"
        return nxt, msg


def _act_person_edit(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: alleen anchor-lead (mother_earth) ──
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "No access — only the anchor lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        if st.people.update(g("pid"), name=g("name"), email=g("email")):
            msg = "✓ person saved"
        else:
            msg = "✗ person not found"
        return nxt, msg


def _act_person_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        msg = ""
        # ── Autorisatie: alleen anchor-lead (mother_earth) ──
        actor = st.people.by_email(username) if username != "guest" else None
        if actor is not None and not is_circle_lead(actor.id, "mother_earth", st.assign):
            return nxt, "No access — only the anchor lead may do this"
        if actor is None and username != "guest":
            return nxt, "No access — user not recognised"
        # ── einde autorisatie ──
        pid = g("pid")
        # ruim ook de rol-toewijzingen op, anders blijven die als wees achter
        for rid in list(st.assign.roles_of("person", pid)):
            st.assign.unassign(rid, "person", pid)
        if st.people.remove(pid):
            msg = "🗑 person removed"
        else:
            msg = "✗ person not found"
        return nxt, msg


def _act_lk_mute(c):
        # AUTHZ: circle-member of iedereen-ingelogd — muten is een gespreksdaad, geen structuurdaad;
        # toeschouwers zijn uitgesloten via de client-state (observer-tiles zijn niet klikbaar), niet
        # via authz. De sessie-check in do_POST dekt "ingelogd = mag" (guest = auth uit = mag ook).
        nxt, g = c.nxt, c.g
        target = g("identity").strip()
        if not target:
            return nxt, ""
        muted = g("muted") != "0"                 # muted=0 → unmute; anders mute
        ok = livekit_mute_participant(target, muted)
        verb = "gemute" if muted else "ge-unmute"
        return nxt, (f"✓ {verb}" if ok else "muting failed")


# ── Claims-checker: cureren van de claims-database ───────────────────────────
# De database (`config/claims_database.json`) is het domein van de compliance-rol. Lezen is vrij
# (route /claims/db.json); cureren is exclusief de domein-eigenaar. De juridische inhoud is
# mensenwerk — deze takken schrijven alleen door wat compliance invoert.

def _claims_bordresultaat(qs: dict) -> dict:
    """Het resultaat van de laatste 'Zet op het bord'-klik, meegegeven in de redirect-URL.
    Onleesbaar of afwezig → niets tonen; dit is presentatie, geen waarheid."""
    rauw = (qs.get("bord") or [""])[0]
    if not rauw:
        return {}
    try:
        uit = json.loads(urllib.parse.unquote(rauw))
        return uit if isinstance(uit, dict) else {}
    except (ValueError, TypeError):
        return {}


def _claims_db_stil(data_dir: str | None = None) -> dict:
    """De effectieve claims-database (seed + overlay), of een leeg omhulsel als hij onleesbaar is.
    Alleen voor rand-opmaak (landnotities); de scan zelf faalt luid via `_claims_scan`."""
    try:
        return _claims_db.load(data_dir=data_dir)
    except _claims_db.ClaimsDbError:
        return {}


def _claims_scan(form: dict, data_dir: str | None = None) -> tuple[dict, str]:
    """Toets een URL of een stuk tekst tegen de claims-database. Geeft (uitslag, bron) terug.

    De URL wordt server-side opgehaald via `safe_fetch` — inclusief SSRF-guardrail, zodat een
    ingetypte URL nooit het interne bereik van de server kan lenen. Elke fout komt als
    `{"error": ...}` terug: fail-closed, want een mislukte scan mag nooit als 'geen claims' lezen."""
    from nooch_village import safe_fetch

    url = (form.get("url") or [""])[0].strip()
    tekst = (form.get("tekst") or [""])[0]
    bron = ""
    if url:
        try:
            opgehaald = safe_fetch.haal_tekst(url)
        except safe_fetch.FetchGeweigerd as e:
            return {"error": f"{e}"}, url
        except safe_fetch.FetchMislukt as e:
            return {"error": f"{e} — plak de tekst handmatig in het tekstveld."}, url
        tekst = opgehaald["tekst"]
        bron = opgehaald["url"]
        if not tekst.strip():
            return {"error": "the page gave no readable text — paste the text manually."}, bron
    elif not tekst.strip():
        return {"error": "give a URL or paste some text."}, ""
    else:
        bron = "pasted text"
    try:
        uitslag = _claims_db.check_tekst(tekst, data_dir=data_dir)
    except _claims_db.ClaimsDbError as e:
        return {"error": str(e)}, bron
    uitslag["tekst"] = tekst
    # Contextlaag over de deterministische regex-scan: één LLM-oordeel filtert de rode/oranje
    # bevindingen die alleen als onderwerp voorkomen (kritiek, ontkenning, citaat, uitleg) naar
    # een aparte groep, en herweegt de score. Fail-soft: zonder LLM blijft het oude strenge gedrag.
    try:
        _load_env()
        from nooch_village import claims_context
        claims_context.verrijk(uitslag)
    except Exception:
        logging.getLogger("cockpit2.claims").exception("claim-contextlaag faalde")
        uitslag.setdefault("in_context", [])
        uitslag.setdefault("context_beoordeeld", False)
    return uitslag, bron


def _claims_gate_open(st, username: str | None) -> bool:
    """Mag deze gebruiker de claims-database cureren? Eén definitie voor zowel het tonen van de
    schrijfknoppen als het toestaan van de mutatie — de knop kan dus nooit iets beloven wat de
    dispatch-tak weigert (reference, don't copy)."""
    return _role_gate("compliance", username, st) is None


def _claims_audit(st, username: str | None, event: str, **velden) -> None:
    """Leg de mutatie vast in de bestaande audit-trail. Geen bus in dispatch → direct schrijven."""
    try:
        with open(os.path.join(st.dd, "system_log.jsonl"), "a") as f:
            f.write(json.dumps({"event": event, "by": username or "?", "at": time.time(), **velden},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass


def _act_claims_term_add(c):
        # AUTHZ: rolvervuller of Circle Lead — compliance-domein: alleen de domein-eigenaar cureert
        # de claims-database.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _role_gate("compliance", username, st)
        if _deny:
            return nxt, _deny
        try:
            # Curatie landt in de runtime-overlay (data/claims_runtime.json), niet in de getrackte
            # seed — zo blijft config/claims_database.json schoon voor het ff-only-deploymodel.
            nieuw, versie = _claims_db.overlay_add_term(
                c.data_dir, term=g("term").strip(), patroon=g("patroon").strip(),
                stoplicht=g("stoplicht").strip(), categorie=g("categorie").strip(),
                waarom=g("waarom").strip(), alternatief=g("alternatief").strip())
        except ValueError as e:
            return nxt, f"⛔ {e}"
        _claims_audit(st, username, "claims_term_added", term=nieuw["term"],
                      stoplicht=nieuw["stoplicht"], versie=versie)
        return nxt, f"✓ term added — database v{versie}"


def _act_claims_work_status(c):
        # AUTHZ: rolvervuller of Circle Lead — compliance-domein: de werklijst-status van een
        # site-fix is een compliance-oordeel, geen open bord.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _role_gate("compliance", username, st)
        if _deny:
            return nxt, _deny
        try:
            nr, status = int(g("nr") or 0), g("status").strip()
            versie = _claims_db.overlay_set_status(c.data_dir, nr, status)
        except (ValueError, TypeError) as e:
            return nxt, f"⛔ {e}"
        _claims_audit(st, username, "claims_work_status", nr=nr, status=status, versie=versie)
        return nxt, f"✓ #{nr} → {status} — database v{versie}"


def _act_claims_term_retract(c):
        # AUTHZ: rolvervuller of Circle Lead — compliance-domein: intrekken is curatie, net als
        # toevoegen; alleen de domein-eigenaar mag het.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _role_gate("compliance", username, st)
        if _deny:
            return nxt, _deny
        try:
            patroon = g("patroon").strip()
            versie = _claims_db.overlay_retract(c.data_dir, patroon)
        except ValueError as e:
            return nxt, f"⛔ {e}"
        _claims_audit(st, username, "claims_term_retracted", patroon=patroon, versie=versie)
        # Een seed-term blijft staan (aanwezigheid wint); de curator ziet dat aan de conflict-melding
        # op het scherm. Een runtime-toegevoegde term is nu echt weg.
        return nxt, f"✓ term ingetrokken — database v{versie}"


def _claims_kroniek(data_dir: str):
    """De Kroniek voor het claims-scherm. Eén plek, zodat de lees- en de schrijfkant nooit naar
    twee verschillende bestanden kijken."""
    return EvidenceLedger(os.path.join(data_dir, "evidence_ledger.jsonl"))


def _claims_bewijzen(data_dir: str) -> list[dict]:
    from nooch_village import claims_substantiatie
    return claims_substantiatie.vastgelegd(_claims_kroniek(data_dir))


def _act_claims_bewijs_link(c):
        # AUTHZ: rolvervuller of Circle Lead — vaststellen dát een claim onderbouwd is, is een
        # compliance-oordeel met juridisch gevolg; het is dezelfde poort als termen cureren.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _role_gate("compliance", username, st)
        if _deny:
            return nxt, _deny
        from nooch_village import claims_substantiatie
        try:
            db = _claims_db_stil(c.data_dir)
            merken = sorted(claims_substantiatie.eigen_merken(db))
            record = claims_substantiatie.leg_bewijs_vast(
                _claims_kroniek(c.data_dir), claim=g("claim"), bron=g("bron"), citaat=g("citaat"),
                merk=(merken[0] if merken else ""), door=username or "compliance")
        except ValueError as e:
            return nxt, f"⛔ {e}"
        except Exception as e:                       # noqa: BLE001 — schrijffout zichtbaar maken
            logging.getLogger("cockpit2.claims").exception("bewijs vastleggen faalde")
            return nxt, f"⛔ evidence not recorded: {e}"
        _claims_audit(st, username, "claims_bewijs_vastgelegd", claim=g("claim").strip(),
                      bron=g("bron").strip(), record=record["id"])
        return nxt, f"✓ evidence recorded ({record['id']}) — the next scan reads it as substantiation"


def _act_claims_vondst_whitelist(c):
        # AUTHZ: rolvervuller of Circle Lead — een vlag wegwuiven is een compliance-oordeel; dezelfde
        # poort als termen cureren. Een verkeerde uitzondering maakt de site stil blind.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _role_gate("compliance", username, st)
        if _deny:
            return nxt, _deny
        from nooch_village import claims_labels
        fragment, pagina = g("fragment").strip(), g("pagina").strip()
        try:
            _, versie = _claims_db.overlay_uitzondering(
                c.data_dir, fragment, pagina=pagina, waarom=g("waarom").strip(),
                door=username or "compliance")
        except ValueError as e:
            return nxt, f"⛔ {e}"
        # Het label is de opbrengst: de modelpas krijgt dit als negatief voorbeeld mee, zodat
        # dezelfde over-vlag volgende week niet terugkomt.
        claims_labels.leg_vast(c.data_dir, fragment=fragment, label=claims_labels.GEEN_CLAIM,
                               pagina=pagina, door=username or "compliance",
                               reden=g("waarom").strip())
        _claims_audit(st, username, "claims_vondst_whitelist", fragment=fragment[:120],
                      pagina=pagina, versie=versie)
        return nxt, (f"✓ marked as 'no claim' — no task, still visible in the scan report, "
                     f"and recorded as a label (v{versie})")


def _act_claims_regel_uit_vondst(c):
        # AUTHZ: rolvervuller of Circle Lead — een nieuwe regel in de claims-database is curatie van
        # het compliance-domein, ook als hij hier met één veld ontstaat.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _role_gate("compliance", username, st)
        if _deny:
            return nxt, _deny
        from nooch_village import claims_labels
        fragment = " ".join(g("fragment").split())
        if len(fragment) < 4:
            return nxt, "⛔ paste the wording itself (at least 4 characters)"
        # Het patroon wordt AFGELEID uit de zin: letterlijk, maar buigzaam op witruimte, zodat een
        # regelafbreking in de HTML de match niet breekt. De mens hoeft geen regex te schrijven —
        # dat is de drempel waardoor regelboeken normaal niet groeien.
        patroon = r"\s+".join(re.escape(w) for w in fragment.split())
        try:
            nieuw, versie = _claims_db.overlay_add_term(
                c.data_dir, term=fragment[:120], patroon=patroon, stoplicht="escaleren",
                categorie="Framing",
                waarom=(f"handmatig gevangen claim (door {username or 'compliance'}); de tool had "
                        f"hier geen term voor. Geen harde bron → compliance beoordeelt."),
                alternatief="(compliance bepaalt de veilige formulering)")
        except ValueError as e:
            return nxt, f"⛔ {e}"
        claims_labels.leg_vast(c.data_dir, fragment=fragment, label=claims_labels.CLAIM,
                               pagina=g("pagina").strip(), door=username or "compliance",
                               herkomst="handmatig")
        _claims_audit(st, username, "claims_regel_uit_vondst", term=nieuw["term"], versie=versie)
        return nxt, (f"✓ rule added as 'compliance decides' — the scan catches this wording from now "
                     f"on (database v{versie}). Set a traffic light on it in the term database.")


def _act_claims_to_board(c):
        # AUTHZ: rolvervuller of Circle Lead — compliance zet bevindingen om in werk; andere
        # rollen zien de knop niet (en de poort weigert ze hier alsnog).
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _role_gate("compliance", username, st)
        if _deny:
            return nxt, _deny
        try:
            rauw = json.loads(urllib.parse.unquote(g("bevindingen") or "{}"))
        except (ValueError, TypeError):
            return nxt, "⛔ onleesbare bevindingen"
        bevindingen = rauw.get("bevindingen") or []
        if not bevindingen:
            return nxt, "⛔ no findings to put on the board"
        verslag = _claims_board.zet_op_bord(
            st, _claims_db_stil(c.data_dir), bevindingen,
            g("bron") or rauw.get("bron", ""), rol_voor, trigger="human")
        _claims_audit(st, username, "claims_to_board", aangemaakt=len(verslag["aangemaakt"]),
                      overgeslagen=verslag["overgeslagen"])
        # De klik moet zichtbaar iets doen: wát er is aangemaakt, bij wie, en waar het al liep.
        # Het resultaat gaat mee als query-parameter zodat de view het uitklapt met links.
        # Cap: het rapport reist als query-parameter mee, en een URL is geen opslagplek. Wat niet
        # past staat gewoon op het bord — het aantal in de melding klopt altijd.
        rapport = json.dumps({"aangemaakt": verslag["aangemaakt"][:12],
                              "lopend": verslag["lopend"][:12],
                              "overgeslagen": verslag["overgeslagen"],
                              "totaal": len(verslag["aangemaakt"])}, ensure_ascii=False)
        scheiding = "&" if "?" in nxt else "?"
        return f"{nxt}{scheiding}bord={urllib.parse.quote(rapport)}", _bord_melding(verslag)


def _bord_melding(verslag: dict) -> str:
    """Eén regel die zegt wat er gebeurd is — nooit meer een stille klik."""
    n = len(verslag["aangemaakt"])
    if not n:
        return (f"✓ 0 nieuw — alle {verslag['overgeslagen']} bevinding(en) staan al als "
                f"taak of werklijst-item")
    rollen = ", ".join(f"@{naam} ({aantal})" for naam, aantal in _claims_board.per_rol(verslag["aangemaakt"]))
    staart = f" · {verslag['overgeslagen']} liepen al" if verslag["overgeslagen"] else ""
    return f"✓ {n} task(s) created → {rollen}{staart}"


# ── Kennisbank (laag 2): inzichten, bewijs-links, gesprek en versies ─────────
# Alle kb_-takken: AUTHZ: iedereen-ingelogd — kennis verzamelen is dorpsbreed (permissieve
# intake, strenge uitgang: de garbage-poort staat bij het GEBRUIK van kennis, niet bij de
# ingang). De herkomst wordt per handeling vastgelegd (by=persoon).

def _kb_actor(c) -> str:
    """Weergavenaam van de handelende mens (de lezer is ook een bron)."""
    if c.username in (None, "guest"):
        return "gast"
    p = c.st.people.by_email(c.username)
    return p.name if p else c.username


def _kb_word(c, iid: str) -> str:
    """Het zekerheids-woord van een inzicht ná een mutatie (voor de bevestiging)."""
    ins = c.st.kennisbank.get(iid)
    if ins is None:
        return ""
    atoms = kb_load_atoms(c.data_dir)
    return KB_WORD_LABEL[kb_verdict(kb_field(ins.get("evidence") or [], atoms))["word"]]


def _act_kb_new(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok
    title = c.g("title").strip()
    if not title:
        return c.nxt, "✗ type a claim first"
    iid = c.st.kennisbank.add(title, why=c.g("why"), by=_kb_actor(c))
    return f"/kennisbank?id={iid}", "➕ insight created (v1.0) — link evidence and watch how certain it becomes"


def _act_kb_link(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok
    iid, atom_id = c.g("iid"), c.g("atom_id")
    if atom_id not in kb_load_atoms(c.data_dir):
        return c.nxt, "✗ card not found in the library"
    voor = _kb_word(c, iid)
    ok = c.st.kennisbank.link(iid, atom_id, c.g("stance"),
                              annotation=c.g("annotation"), by=_kb_actor(c))
    if not ok:
        return c.nxt, "✗ linking failed"
    na = _kb_word(c, iid)
    return c.nxt, ("🔗 linked. " + (f"Zekerheid nu: {na}" if na != voor else "Zekerheid herberekend."))


def _act_kb_unlink(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok
    iid = c.g("iid")
    voor = _kb_word(c, iid)
    if not c.st.kennisbank.unlink(iid, c.g("atom_id")):
        return c.nxt, "✗ unlinking failed"
    na = _kb_word(c, iid)
    return c.nxt, ("Unlinked (the card stays in the library). "
                   + (f"Zekerheid nu: {na}" if na != voor else "Zekerheid herberekend."))


def _act_kb_annotate(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok
    ok = c.st.kennisbank.annotate(c.g("iid"), c.g("atom_id"), c.g("text"))
    return c.nxt, ("💬 note saved" if ok else "✗ note not saved")


def _act_kb_evidence(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Nieuw bewijs = een nieuw
    # ATOOM in de bibliotheek (laag 1, dom: geen oordeel bij de intake) + een link met richting.
    iid, text = c.g("iid"), c.g("text").strip()
    if not text:
        return c.nxt, "✗ typ eerst iets"
    actor = _kb_actor(c)
    bron = c.g("source").strip() or actor
    # Eigen naam als bron = een intern oordeel (meningssterkte ≠ bewijssterkte);
    # elke andere bron blijft 'unknown' tot een curator de herkomst duidt.
    prov = "internal_judgment" if bron == actor else "unknown"
    atom_id = "atom_" + uuid.uuid4().hex[:8]
    c.st.notes.add(Insight(id=atom_id, claim=text[:500], source=bron, provenance=prov))
    voor = _kb_word(c, iid)
    ok = c.st.kennisbank.link(iid, atom_id, c.g("stance") or "support", by=actor)
    if not ok:
        return c.nxt, "✗ card created but linking failed"
    na = _kb_word(c, iid)
    return c.nxt, ("➕ added. " + (f"Zekerheid nu: {na}" if na != voor else "Zekerheid herberekend."))


def _act_kb_discuss(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok
    ok = c.st.kennisbank.discuss(c.g("iid"), c.g("text"), _kb_actor(c))
    return c.nxt, ("💬 kanttekening geplaatst" if ok else "✗ type an annotation first")


def _act_kb_reformulate(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. De trage klok: claim/
    # reframe/falsifier opnieuw gemunt uit het spel; de vorige versie blijft in history.
    iid = c.g("iid")
    parsed = parse_blok(c.g("blok"))
    if not parsed["claim"]:
        return c.nxt, "✗ could not read the block — make sure there is a CLAIM: line"
    nieuwe = c.st.kennisbank.reformulate(iid, title=parsed["claim"],
                                         reframe=parsed["reframe"],
                                         falsifier=parsed["falsifier"], by=_kb_actor(c))
    if nieuwe is None:
        return c.nxt, "✗ rewording failed"
    return c.nxt, f"↻ geherformuleerd → v{nieuwe} (vorige versie bewaard)"


def _act_kb_intake(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Fase 2: ruwe tekst →
    # LLM-ladder → atomen, idempotent (hash content+bron) append aan de bibliotheek.
    # Laag 1 blijft dom: geen oordeel, geen veld; trust wordt pas in laag 2 afgeleid.
    uitkomst = kb_intake(c.g("raw"), c.g("source_hint"), c.data_dir)
    if uitkomst is None:
        return c.nxt, "✗ the note helper gave no usable answer — try again in a moment"
    nieuw, dubbel = uitkomst
    if not nieuw and not dubbel:
        return c.nxt, "✗ typ eerst iets om te noteren"
    if not nieuw:
        return c.nxt, f"Al bekend: {dubbel} notitie(s) stonden er al (niets gedupliceerd)"
    extra = f" ({dubbel} al bekend)" if dubbel else ""
    return (f"/kennisbank?nieuw={','.join(nieuw)}",
            f"✂️ we splitsten dit in {len(nieuw)} notities{extra}")


def _act_kb_intake_url(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. URL = source-adapter:
    # trafilatura haalt de hoofdtekst op, de bestaande atomiser doet de rest (geen fork).
    from nooch_village.kennisbank_sources import van_url
    uit = van_url(c.g("url"))
    if uit is None:
        return c.nxt, "✗ could not fetch this page or extract readable text from it"
    raw, label = uit
    uitkomst = kb_intake(raw, label, c.data_dir)
    if uitkomst is None:
        return c.nxt, "✗ the note helper gave no usable answer — try again in a moment"
    nieuw, dubbel = uitkomst
    if not nieuw:
        return c.nxt, f"Al bekend: {dubbel} notitie(s) stonden er al (niets gedupliceerd)"
    extra = f" ({dubbel} al bekend)" if dubbel else ""
    return (f"/kennisbank?nieuw={','.join(nieuw)}",
            f"✂️ we splitsten de pagina in {len(nieuw)} notities{extra}")


def _act_kb_stage_edit(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Staging bewerken vóór commit.
    # Onderwerp/provenance staan niet meer in het formulier (LLM classificeert; slimme
    # tags volgen later) — alleen doorgeven als ze wél zijn meegestuurd, anders zou een
    # gewone tekst-bewaar het LLM-onderwerp stilletjes wissen.
    subject = (c.form.get("subject") or [None])[0]
    provenance = (c.form.get("provenance") or [None])[0]
    ok = c.st.staging.edit_atom(c.g("bid"), c.g("sid"), content=c.g("content"),
                                subject=subject, provenance=provenance)
    return c.nxt, ("✏️ updated" if ok else "✗ not found")


def _act_kb_stage_accept(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. "✓ Bewaar → bibliotheek":
    # eventuele tekstwijziging bewaren en dit ENE voorstel meteen verwerken (founder, 19 jul:
    # verwerkt = weg uit de set, anders lijkt de actie niet gebeurd). Zelfde dedupe/MECE/
    # marker-pad als de set-commit; een leeggeraakte set ruimt zichzelf op.
    content = (c.form.get("content") or [None])[0]
    if content and content.strip():
        c.st.staging.edit_atom(c.g("bid"), c.g("sid"), content=content)
    res = commit_atom(c.st.staging, c.g("bid"), c.g("sid"), c.data_dir, radar=c.st.radar)
    if res is None:
        return c.nxt, "✗ proposal not found"
    msg = {"nieuw": "✓ in Oracle",
           "bekend": "Al bekend — niets gedupliceerd",
           "gekoppeld": "🔗 merged with an existing signal"}[res["uitkomst"]]
    if res["leeg"]:
        return "/kennisbank", f"🎉 set verwerkt · laatste voorstel: {msg}"
    return c.nxt, msg


def _act_kb_stage_delete(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    ok = c.st.staging.remove_atom(c.g("bid"), c.g("sid"))
    return c.nxt, ("🗑 weggegooid" if ok else "✗ not found")


def _act_kb_stage_merge(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    sids = [s for s in (c.form.get("sid") or []) if s]
    if len(sids) < 2:
        return c.nxt, "✗ tick at least two proposals"
    if not c.g("kop").strip():
        return c.nxt, "✗ give the composed card a heading"
    ok = c.st.staging.merge_atoms(c.g("bid"), sids, c.g("kop"))
    return c.nxt, ("🧩 samengevoegd" if ok else "✗ merging failed")


def _act_kb_stage_commit(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Pas hier landen de
    # nagekeken atomen append-only in de bibliotheek (idempotent op hash content+bron).
    res = commit_batch(c.st.staging, c.g("bid"), c.data_dir, radar=c.st.radar)
    if res is None:
        return c.nxt, "✗ this set no longer exists"
    nieuw, dubbel, gekoppeld = res
    if not nieuw and not gekoppeld:
        return "/kennisbank", (f"Al bekend: {dubbel} notitie(s) stonden er al" if dubbel
                               else "Nothing added — the set was empty")
    delen = []
    if nieuw:
        delen.append(f"✅ {nieuw} notes added to the library")
    if gekoppeld:
        delen.append(f"🔗 {gekoppeld} signal(s) merged with an existing signal in Oracle")
    if dubbel:
        delen.append(f"{dubbel} al bekend")
    return "/kennisbank", " · ".join(delen)


def _act_kb_stage_discard(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    ok = c.st.staging.discard(c.g("bid"))
    return "/kennisbank", ("Set discarded — nothing in the library" if ok else "✗ set not found")


def _act_kb_atoom_edit(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Bewerken-met-historie
    # (PR-2): de vorige claim blijft bewaard in edit_history (append-only, extractie-fouten).
    res = c.st.notes.edit_note(c.g("atom_id"), claim=c.g("claim"))
    return c.nxt, ("✏️ updated (previous version kept)" if res else "✗ editing failed")


def _act_kb_atoom_related(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. "Voeg gerelateerd feit toe":
    # een NIEUW gelinkt atoom met eigen bron (het 36%-geval), geen verrijking-in-place.
    actor = _kb_actor(c)
    bron = c.g("source").strip() or actor
    prov = "internal_judgment" if bron == actor else "unknown"
    res = c.st.notes.add_related(c.g("atom_id"), c.g("content"), bron, provenance=prov)
    if res is None:
        return c.nxt, "✗ could not add a related fact (empty, or it already exists)"
    return c.nxt, "➕ related fact added and linked"


def _act_kb_insight_link(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. B1: koppel een ander INZICHT
    # als steun/tegen aan het geopende inzicht (de Zettelkasten-ladder → meta-inzicht).
    ok = c.st.kennisbank.link_insight(c.g("iid"), c.g("other_id"), c.g("stance"), by=_kb_actor(c))
    return c.nxt, ("🔗 insight linked" if ok else "✗ linking failed")


def _act_kb_insight_unlink(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    ok = c.st.kennisbank.unlink_insight(c.g("iid"), c.g("other_id"))
    return c.nxt, ("unlinked" if ok else "✗ unlinking failed")


def _act_kb_meta_start(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. B1: speel een META-inzicht —
    # de gekoppelde inzichten van dit inzicht als input aan dezelfde copy-paste-spel-flow.
    src = c.st.kennisbank.get(c.g("iid"))
    if src is None:
        return c.nxt, "✗ insight not found"
    related = src.get("related") or []
    if len(related) < 2:
        return c.nxt, "✗ link ≥2 insights first (supporting/contradicting) to play a meta-insight"
    kaarten = []
    for r in related:
        other = c.st.kennisbank.get(r["insight_id"])
        if other is not None:
            kaarten.append({"atom_id": r["insight_id"], "stance": r.get("stance") or "support",
                            "label": other.get("title") or ""})
    sid = c.st.spel.start(f"Meta-inzicht over: {src.get('title') or ''}", kaarten,
                          by=_kb_actor(c), meta=True)
    return f"/kennisbank/spel?sid={sid}", "🎲 meta-game started — the linked insights are the hand"


def _act_kb_atoom_reference(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Een URL als bronlink bij een
    # atoom (A3): landt in het reference-veld. Een expliciet-geplakte bronlink houden we (anders
    # dan de intake-validator, die een kale artikel-URL juist dropt). Bron-propagatie (founder
    # dd 2026-07-18): dezelfde reference gaat óók naar de andere atomen met dezelfde
    # genormaliseerde bron die er nog geen hebben (nooit een bestaande overschrijven).
    url = c.g("url").strip()
    if not re.match(r"^https?://", url):
        return c.nxt, "✗ paste a valid URL (https://…)"
    if not c.st.notes.set_reference(c.g("atom_id"), url):
        return c.nxt, "✗ note not found"
    extra = c.st.notes.propagate_reference(c.g("atom_id"))
    if extra:
        return c.nxt, (f"🔗 source link attached — also set on {extra} other "
                       f"kaartje(s) met dezelfde bron")
    return c.nxt, "🔗 source link attached"


def _act_tag_voorstel_besluit(c):
    # AUTHZ: iedereen-ingelogd — tag-onderhoud-review. ✓ voert het voorstel meteen door op
    # alle kaartjes (NotesStore.retag); ✗ wijst af (komt niet opnieuw terug).
    from nooch_village.tag_onderhoud import TagVoorstellenStore, voer_voorstel_uit
    store = TagVoorstellenStore(f"{c.data_dir}/tag_voorstellen.json")
    keuze = c.g("keuze")
    if keuze == "doorvoeren":
        vs = {v["id"]: v for v in store.open_voorstellen()}
        v = vs.get(c.g("vid"))
        if v is None:
            return c.nxt, "✗ proposal not found or already decided"
        n = voer_voorstel_uit(c.st.notes, v)
        store.besluit(c.g("vid"), "doorgevoerd")
        return c.nxt, f"✓ doorgevoerd op {n} signal(s)"
    v = store.besluit(c.g("vid"), "afgewezen")
    return c.nxt, ("✗ rejected — it will not come back" if v
                   else "✗ proposal not found or already decided")


def _act_verzoek_besluit(c):
    # AUTHZ: rolvervuller of Circle Lead — beslissen over een verzoek AAN jouw rol is operationeel
    # werk binnen die rol. Wie de rol niet vervult, beslist niet over haar bord.
    #
    # Drie uitkomsten, en alle drie sluiten de spanning: accepteren zet het als project op het bord
    # (dát is de handeling waar de kaart om vraagt), aanpassen stuurt een herformulering terug naar
    # de vrager, weigeren sluit met een reden. Een verzoek dat blijft hangen is precies wat de
    # kaart moest wegnemen.
    nxt, st, g, username = c.nxt, c.st, c.g, c.username
    nid, keuze, tekst = g("nid"), g("keuze"), g("tekst")
    n = st.notif.get(nid) if hasattr(st.notif, "get") else None
    n = n or next((x for x in st.notif.all() if x.get("id") == nid), None)
    if n is None:
        return nxt, "✗ deze spanning bestaat niet meer"
    rol = str(n.get("target_id") or "")
    fout = _role_gate(rol, username, st)
    if fout:
        return nxt, fout
    bev = dict(n.get("bevinding") or {})
    titel = (bev.get("voorstel") or bev.get("spanning") or n.get("snippet") or "")[:200]

    pag = dict(n.get("pagina") or {})

    def _terug(bericht: str) -> None:
        """Antwoord aan de vrager. Een rol-verzoek gaat terug naar de ROL; een pagina-voorstel komt
        van een MENS, en die leest zijn persoon-inbox — een 'rol' met een persoon-id erin zou een
        dead letter zijn (zelfde val als @rol-berichten aan AI-rollen)."""
        if pag:
            wie = str(pag.get("van_id") or "")
            if wie:
                st.notif.add("person", wie, "", by=rol, snippet=bericht)
            return
        van = str(n.get("by") or "")
        if van:
            st.notif.add("role", van, n.get("project_id") or "", by=rol, snippet=bericht)

    if keuze == "accepteer" and pag:
        # Een PAGINA-voorstel is al concreet: de tekst ís de vraag, dus accepteren is de handeling
        # zelf (een nieuwe versie) en niet een project dat het nog een keer moet gaan doen.
        # De artefact-poort geldt onverkort — schrijven mag alleen de vervuller van de eigenaar-rol
        # of de Circle Lead van de omvattende cirkel, precies zoals bij artefact_edit.
        cur = st.att.get(pag.get("aid") or "")
        if cur is None or cur.kind != "note":
            return nxt, "✗ deze pagina bestaat niet meer"
        _deny = _artefact_gate(cur.anchor, username, st)
        if _deny:
            return nxt, _deny
        nieuw = str(pag.get("body") or "")
        te_lang = _body_te_lang(nieuw, cur.kind)
        if te_lang:
            return nxt, te_lang
        actor_id = _web_actor_id(username, st)
        gref = f"role:{cur.anchor}"
        upd = st.att.update(cur.id, body=nieuw, actor_id=actor_id, actor_type="person",
                            governance_ref=gref,
                            change_note=f"voorstel van {pag.get('van_naam') or 'iemand'} aangenomen")
        artefacts.log_change(c.data_dir, action="edit", artefact=upd, records=st.records,
                             actor_id=actor_id, actor_type="person", governance_ref=gref)
        st.notif.mark_item_processed(nid, outcome=f"toegepast op {cur.id}", by=username or "")
        st.notif.archive_item(nid)
        return nxt, f"✓ accepted — new version of {cur.id} saved"

    if keuze == "accepteer":
        from nooch_village.project_items import handoff
        van = str(n.get("by") or "")
        uit = handoff(st.projects, rol, titel, records=st.records, van_rol=van,
                      van_accountability=_founder_kaart.eigen_accountability(
                          van, str(n.get("snippet") or ""), st.records),
                      spanning=bev.get("spanning") or str(n.get("snippet") or ""),
                      vraag=bev.get("voorstel") or "")
        if uit.get("error"):
            return nxt, f"✗ {uit['error']}"
        st.notif.mark_item_processed(nid, outcome=f"geaccepteerd → project {uit['pid']}",
                                     by=username or "")
        st.notif.archive_item(nid)
        return nxt, f"✓ geaccepteerd — staat als project op het bord van {_name(st.records.get(rol))}"

    if keuze == "aanpassen":
        if not tekst.strip():
            return nxt, "✗ schrijf op hoe het verzoek wél zou kloppen"
        st.notif.add_outcome(nid, intent="aanpassen", otype="note", label=tekst[:200],
                             by=username or "")
        _terug(f"↩ herformulering gevraagd op je verzoek: {tekst[:120]}")
        return nxt, "✓ herformulering teruggestuurd naar de vrager"

    if keuze == "weiger":
        if not tekst.strip():
            return nxt, "✗ een weigering zonder reden leert de vrager niets"
        st.notif.mark_item_processed(nid, outcome=f"geweigerd: {tekst[:160]}", by=username or "")
        st.notif.archive_item(nid)
        _terug(f"✗ je verzoek is geweigerd: {tekst[:120]}")
        return nxt, "✓ geweigerd, met reden terug naar de vrager"

    return nxt, "✗ onbekende keuze"


def _act_copy_stack_inclusie(c):
    # AUTHZ: anchor-lead — org-brede configuratie. Welke rol meetelt in de schrijf-stack van een
    # andere rol raakt hoe elke tekst van die rol klinkt; dat is geen keuze van de schrijver.
    fout = _anchor_gate(c.st, c.username)
    if fout:
        return c.nxt, fout
    rol, bron = c.g("rol"), c.g("bron")
    aan = c.g("aan") == "1"
    if c.st.records.get(rol) is None or c.st.records.get(bron) is None:
        return c.nxt, "Unknown role"
    door = (c.username or "onbekend")
    if not c.st.copy_stack.zet(rol, bron, aan, door=door):
        return c.nxt, "No change"
    naam = _name(c.st.records.get(bron))
    return c.nxt, (f"✓ {naam} included in this role's stack" if aan
                   else f"✗ {naam} removed from this role's stack")


def _act_tag_onderhoud_run(c):
    # AUTHZ: iedereen-ingelogd — de ronde nu draaien (buiten het weekritme om). Fail-closed:
    # zonder LLM komen er simpelweg geen voorstellen.
    from nooch_village.tag_onderhoud import draai_onderhoud
    res = draai_onderhoud(c.data_dir, force=True)
    if not res.get("gedraaid"):
        return c.nxt, "No tags to review"
    if not res.get("voorstellen"):
        return c.nxt, "🏷 round run — the LLM saw nothing to clean up (or was unavailable)"
    return c.nxt, (f"🏷 ronde gedraaid: {res['nieuw']} nieuw voorstel(len) "
                   f"({res['voorstellen'] - res['nieuw']} al bekend/afgewezen)")


def _act_kb_atoom_purge(c):
    # AUTHZ: iedereen-ingelogd — ⚙-actie. Definitief weggooien kan alleen op een kaartje dat
    # al op de black-list staat (eerst verwijderen, dan pas definitief). Afweging bewust bij
    # de mens: na een purge kan dezelfde tekst in principe opnieuw binnenkomen.
    ok = c.st.notes.purge(c.g("atom_id"))
    return c.nxt, ("🔥 definitief weggegooid" if ok
                   else "✗ not found or not deleted yet")


def _act_kb_blacklist_leeg(c):
    # AUTHZ: iedereen-ingelogd — ⚙-actie: de hele black-list in één keer definitief legen.
    n = c.st.notes.purge_archived()
    return c.nxt, (f"🔥 black-list geleegd: {n} definitief weggegooid" if n
                   else "The blacklist was already empty")


def _act_kb_atoom_subject(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Curatie van het
    # ongesorteerd-bakje: een mens hangt een subject-loze notitie aan een hub.
    subject = c.g("subject")
    if subject not in KB_SUBJECTS:
        return c.nxt, "✗ pick a subject from the list"
    if not c.st.notes.add_tags(c.g("atom_id"), [subject]):
        return c.nxt, "✗ note not found"
    return c.nxt, f"📥 gesorteerd naar '{subject}'"


def _act_kb_atoom_merge(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Drag&drop-merge
    # (statements-herontwerp dd 2026-07-18): sleep een statement op een ander → modal →
    # één kaart met de gekozen tekst als nieuwe versie. De herkomst van het bron-atoom
    # stapelt op het doel (zie NotesStore.merge_into: merged_from + supersede-spoor +
    # "; "-gestapelde source/reference); verwijzingen elders — in andere atomen én in
    # kennisbank-inzichten — worden herwezen; het bron-atoom verdwijnt uit de lijst
    # (gearchiveerd, nooit gewist). Verving de oude selectie-merge ("Voeg samen") —
    # die interactie is in het herontwerp opgegaan in het slepen.
    target_id, source_id = c.g("target_id"), c.g("source_id")
    if not target_id or not source_id:
        return c.nxt, "✗ merge: drag one statement onto the other"
    if target_id == source_id:
        return c.nxt, "✗ merging with itself does nothing — drag onto a different statement"
    kaart = c.st.notes.merge_into(target_id, source_id, c.g("tekst"), by=_kb_actor(c))
    if kaart is None:
        return c.nxt, "✗ merge failed — statement not found (any more) or text empty"
    c.st.kennisbank.rewire_atom(source_id, target_id)
    return c.nxt, f"🧩 merged → v{kaart.version} (provenance of both kept)"


def _act_kb_atoom_archive(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Archiveren ≠ wissen.
    ids = [a for a in (c.form.get("atoom") or []) if a] or [c.g("atom_id")]
    ok = sum(1 for aid in ids if aid and c.st.notes.archive(aid))
    if not ok:
        return c.nxt, "✗ select a note first"
    return c.nxt, f"📦 {ok} notitie(s) gearchiveerd — terug te zetten via 'Gearchiveerd'"


def _act_kb_atoom_unarchive(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    ok = c.st.notes.archive(c.g("atom_id"), archived=False)
    return c.nxt, ("↩ restored to the library" if ok else "✗ restoring failed")


def _act_kb_atoom_naar_spel(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Voedt de spel-hand
    # (richting draai je in het spel). Sinds de founder-ronde dd 2026-07-18 komt dit uit
    # het statement-detail (één atoom per keer); de meervoudsvorm blijft fail-soft werken.
    ids = [a for a in (c.form.get("atoom") or []) if a]
    sid = c.g("sid")
    if not ids:
        return c.nxt, "✗ select a note first"
    if not sid or c.st.spel.get(sid) is None:
        return c.nxt, "✗ pick an open game"
    ok = sum(1 for aid in ids if c.st.spel.add_kaart(sid, aid, "support"))
    return f"/kennisbank/spel?sid={sid}", f"🔗 {ok} card(s) linked to your hand"


def _kb_spel_set(c) -> list[dict]:
    """Gecureerde set uit het formulier: checkboxes `kaart` + per kaart `stance_<id>`."""
    ids = c.form.get("kaart") or []
    return [{"atom_id": aid, "stance": (c.g(f"stance_{aid}") or "support")}
            for aid in ids if aid]


def _act_kb_spel_start(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Start een dialoog
    # met de gecureerde set; bij reformulate_of wordt het een versie-spel.
    kaarten = _kb_spel_set(c)
    hunch = c.g("hunch").strip()
    if not hunch:
        return c.nxt, "✗ typ eerst je vermoeden"
    if not kaarten:
        return c.nxt, "✗ tick at least one card"
    sid = c.st.spel.start(hunch, kaarten, reformulate_of=c.g("reformulate_of"),
                          by=_kb_actor(c))
    return f"/kennisbank/spel?sid={sid}", "🎲 game started — the thinking partner opens"


def _act_kb_spel_add(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. De hand uitbreiden
    # (taak 2): idempotent, kaart moet in de bibliotheek bestaan.
    if c.g("atom_id") not in kb_load_atoms(c.data_dir):
        return c.nxt, "✗ card not found in the library"
    ok = c.st.spel.add_kaart(c.g("sid"), c.g("atom_id"), c.g("stance") or "support",
                             annotation=c.g("annotation"))
    return c.nxt, ("🔗 linked to your hand" if ok else "✗ linking failed")


def _act_kb_spel_remove(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    ok = c.st.spel.remove_kaart(c.g("sid"), c.g("atom_id"))
    return c.nxt, ("Removed from your hand (the card stays in the library)" if ok
                   else "✗ removing failed")


def _act_kb_spel_flip(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Richting in één klik.
    ok = c.st.spel.flip_kaart(c.g("sid"), c.g("atom_id"))
    return c.nxt, ("↔ richting gedraaid" if ok else "✗ flipping failed")


def _act_kb_spel_finish(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. Munt het inzicht uit
    # het teruggeplakte blok (copy-paste-spel): v1.0, of versie-bump bij herformuleren.
    res = spel_finish(c.st.spel, c.g("sid"), c.st.kennisbank, c.g("blok"))
    if res is None:
        return c.nxt, "✗ could not read the block — make sure there is a CLAIM: line"
    iid, versie = res
    woord = ("new version v" + versie) if versie != "1.0" else "inzicht gemaakt (v1.0)"
    return f"/kennisbank?id={iid}", f"✓ {woord} — de zekerheid rekent live mee"


def _act_kw_nominate(c):
    # AUTHZ: circle-member of iedereen-ingelogd — iedereen mag een keyword NOMINEREN; het
    # schrijven naar de beschermde woordenschat blijft voorbehouden aan Lara (kw_nom_accept).
    term = c.g("term").strip()
    if not term:
        return c.nxt, "✗ no keyword given"
    ok = c.st.nominations.nominate(term, by=_kb_actor(c))
    return c.nxt, (f"🗳 “{term}” genomineerd — Lara beslist" if ok
                   else f"“{term}” staat al in de wachtrij")


def _act_kw_nom_accept(c):
    # AUTHZ: rolvervuller of Circle Lead — alleen de Library-rolvervuller (Lara) schrijft de
    # beschermde woordenschat. _role_gate faalt closed (guest mag; onbekende geweigerd).
    deny = _role_gate("librarian", c.username, c.st)
    if deny:
        return c.nxt, f"✗ {deny}"
    term = c.g("term").strip()
    status = c.g("status") or "approved"          # approved | forbidden
    if status not in ("approved", "forbidden"):
        return c.nxt, "✗ invalid status"
    reason = c.g("reason").strip()
    c.st.library.curate(term, status, rationale=reason, by=_kb_actor(c))
    c.st.nom_kroniek.record(role_id=_kb_actor(c), term=term, decision="accept",
                            reason=reason or f"aangenomen als {status}")
    c.st.nominations.remove(term)
    return c.nxt, f"✓ “{term}” geborgd als {status}"


def _act_kw_nom_reject(c):
    # AUTHZ: rolvervuller of Circle Lead — alleen de Library-rolvervuller (Lara) beslist over
    # de woordenschat. Afwijzen dwingt een echte reden af (borging), fail-closed.
    deny = _role_gate("librarian", c.username, c.st)
    if deny:
        return c.nxt, f"✗ {deny}"
    term = c.g("term").strip()
    reason = c.g("reason").strip()
    if not valid_reason(reason):
        return c.nxt, "✗ a rejection requires a real reason (not empty or “n/a”)"
    c.st.nom_kroniek.record(role_id=_kb_actor(c), term=term, decision="reject", reason=reason)
    c.st.nominations.remove(term)
    return c.nxt, f"✗ “{term}” afgewezen — geborgd in de Kroniek"


# ── Woordenschat-beheer (/woordenschat): de mens cureert de Library vanuit cockpit 2 ────────
# AUTHZ: iedereen-ingelogd — de sessie-check in do_POST dekt "ingelogd = mag" (zelfde regel als
# de andere beheer-schrijfacties zonder extra rolcheck). Schrijven loopt uitsluitend via de
# domein-methodes (inbox_actions → Library.curate), nooit in de json. Bewust minimaal:
# alleen verbied + heractiveer/goedkeuren; functie (doelwit/volg) bepaalt de heuristiek zelf.

def _act_ws_curate(c, status: str, ok_msg: str):
    # Gedeelde kern voor pauzeer/verbied/heractiveer: curatie via curate_library_term.
    from nooch_village.inbox_actions import curate_library_term
    res = curate_library_term(c.st.library, c.g("word"), status,
                              reason=c.g("reason"), by=_kb_actor(c))
    return c.nxt, (ok_msg.format(word=res["word"]) if res.get("ok")
                   else f"✗ {res.get('error')}")


def _act_ws_forbid(c):
    # Verbieden: status → forbidden; zonder reden geldt de default-rationale in curate_library_term.
    return _act_ws_curate(c, "forbidden", "✗ “{word}” verboden")


def _act_ws_approve(c):
    # Heractiveren (of geëscaleerd goedkeuren): status → approved.
    return _act_ws_curate(c, "approved", "✓ “{word}” geactiveerd (approved)")


# ── Founder Flow: de graduele-autonomie-trainingslus ─────────────────────────────────────────
# Alle takken hieronder: AUTHZ: anchor-lead — de flow bepaalt hoeveel de AI zelfstandig mag doen
# aan radar-triage, claim-oordelen en content-goedkeuring. Dat is een org-brede bevoegdheid (het
# raakt drie domeinen tegelijk) en het is de founder-rol die hem uitoefent, dus dezelfde poort als
# persona-beheer. Fail-closed via _anchor_gate; guest (auth uit) mag alles.

def _ff_niveaus(c):
    from nooch_village.founder_flow import NIVEAU_BESTAND, NiveauStore
    return NiveauStore(os.path.join(c.data_dir, NIVEAU_BESTAND))


def _act_ff_beslis(c):
        # AUTHZ: anchor-lead — zie het blok-comment hierboven.
        from nooch_village import founder_flow as ff
        from nooch_village import founder_taken
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _anchor_gate(st, username)
        if _deny:
            return nxt, _deny
        taak, item, oordeel = g("taak"), g("item"), g("oordeel")
        if taak not in ff.TAKEN or oordeel not in ff.OORDELEN.get(taak, ()):
            return nxt, "✗ unknown task or judgement"
        niveaus = _ff_niveaus(c)
        niveau = niveaus.niveau(taak)
        correctie = g("correctie") == "1"
        cfg = ff.instellingen(c.data_dir, taak)
        audit = ff.in_auditsteekproef(taak, item, cfg.get("audit_pct", 0))

        # Het AI-voorstel komt ALTIJD van de server, nooit uit het formulier. Een voorstel dat de
        # client meestuurt is een voorstel dat de client kan zetten, en dan meet de promotiepoort
        # niets. Bij een eerste beslissing rekent de wachtrij het opnieuw uit; bij een correctie
        # staat het al in de log (het item is dan uit de wachtrij verdwenen).
        labels = ff.alle(c.data_dir)
        if correctie:
            eerder = ff.laatste_per_item(labels, taak).get(item, {})
            ai, titel = eerder.get("ai"), eerder.get("titel", "")
        else:
            bron = founder_taken.item_van(st, c.data_dir, taak, item, niveau)
            if bron is None:
                return nxt, "✗ this item is no longer in the queue"
            ai, titel = bron.get("ai"), bron.get("titel", "")

        melding = founder_taken.voer_uit(st, c.data_dir, taak, item, oordeel)
        try:
            seconden = max(0.0, time.time() - float(g("getoond") or 0))
        except (TypeError, ValueError):
            seconden = 0.0
        ff.leg_vast(c.data_dir, taak=taak, item=item, mens=oordeel, ai=ai,
                    ai_getoond=ff.toont_voorstel_vooraf(niveau, audit) or correctie,
                    niveau=niveau, door=username or "?", seconden=seconden,
                    correctie=correctie, audit=audit, titel=titel)

        # Een nieuw blind audit-oordeel is precies het moment waarop het bewijs verandert, dus
        # hier wordt de demotie-poort gerekend. Omhoog vraagt een handtekening, omlaag gebeurt
        # vanzelf: wachten op een mens betekent dat een afwijkend model ondertussen doorwerkt.
        terugval = ff.pas_demotie_toe(niveaus, ff.alle(c.data_dir), taak,
                                      ff.instellingen(c.data_dir, taak))
        if terugval:
            melding = f"{melding} · {terugval}"

        # Blind beslist → de onthulling hoort erbij, anders leert de founder niets van de
        # vergelijking. Hij reist als query-parameter mee; de view rendert 'm bovenaan.
        if not correctie and not ff.toont_voorstel_vooraf(niveau, audit):
            sleutel = urllib.parse.quote(f"{taak}|{item}|{oordeel}|{ai or ''}|{niveau}")
            scheiding = "&" if "?" in nxt else "?"
            return f"{nxt}{scheiding}onthuld={sleutel}", melding
        return nxt, melding


def _act_ff_promote(c):
        # AUTHZ: anchor-lead — een trede omhoog breidt uit wat de AI zonder mens mag doen; die
        # handtekening is mensenwerk, ook als de meting groen staat.
        from nooch_village import founder_flow as ff
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _anchor_gate(st, username)
        if _deny:
            return nxt, _deny
        taak = g("taak")
        if taak not in ff.TAKEN:
            return nxt, "✗ unknown task"
        niveaus = _ff_niveaus(c)
        niveau = niveaus.niveau(taak)
        cfg = ff.instellingen(c.data_dir, taak)
        # Fail-closed: de poort wordt hier opnieuw gerekend. Dat de knop zichtbaar was, is geen
        # bewijs dat hij dat nog steeds mag zijn — de meting kan tussen render en klik gezakt zijn.
        kan, reden = ff.promoveerbaar(ff.alle(c.data_dir), taak, niveau, cfg)
        if not kan:
            return nxt, f"✗ promotion blocked: {reden}"
        nieuw = ff.volgende(niveau)
        niveaus.zet(taak, nieuw, door=username or "?", reden=reden)
        return nxt, f"✓ {ff.TAAK_LABEL[taak]} → level {nieuw} ({reden})"


def _act_ff_demote(c):
        # AUTHZ: anchor-lead — een trede terug is de rem op drift; altijd toegestaan, nooit gemeten.
        from nooch_village import founder_flow as ff
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _anchor_gate(st, username)
        if _deny:
            return nxt, _deny
        taak = g("taak")
        if taak not in ff.TAKEN:
            return nxt, "✗ unknown task"
        niveaus = _ff_niveaus(c)
        niveau = niveaus.niveau(taak)
        if niveau == "A":
            return nxt, "already at A"
        nieuw = ff.vorige(niveau)
        niveaus.zet(taak, nieuw, door=username or "?", reden=g("reden") or "stepped back by the founder")
        return nxt, f"↩ {ff.TAAK_LABEL[taak]} → level {nieuw}"


def _act_ff_run(c):
        # AUTHZ: anchor-lead — dit past AI-voorstellen echt toe (radar wegvegen, bordtaken,
        # @rol-berichten). Alleen op niveau C/D, en nooit op de auditsteekproef.
        from nooch_village import founder_flow as ff
        from nooch_village import founder_taken
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _anchor_gate(st, username)
        if _deny:
            return nxt, _deny
        taak = g("taak")
        if taak not in ff.TAKEN:
            return nxt, "✗ unknown task"
        niveau = _ff_niveaus(c).niveau(taak)
        if niveau not in ("C", "D"):
            return nxt, "✗ the AI only works through the queue from level C"
        cfg = ff.instellingen(c.data_dir, taak)
        verslag = founder_taken.verwerk_automatisch(st, c.data_dir, taak, niveau, cfg)
        # Wat is blijven liggen wordt genoemd, niet stil weggelaten: een melding die alleen het
        # aantal verwerkte items geeft, leest als "alles gedaan" terwijl dat niet zo is.
        staart = ""
        if verslag["audit"]:
            staart += f" · {verslag['audit']} held back for your audit"
        if verslag["zonder_voorstel"]:
            staart += f" · {verslag['zonder_voorstel']} skipped (no proposal)"
        return nxt, f"🤖 the AI handled {verslag['verwerkt']} item(s){staart}"


def _act_ff_cluster(c):
        """Een opkomend onderwerp promoveren naar een project, of parkeren als 'watch'.

        Bewust GEEN label en geen trede. De clustering en de bronnen-teller zijn berekend, en de
        vraag of een stijgend onderwerp een project waard is, is een strategische keuze die niet
        uit een steekproef te leren valt — die hoort niet in de graduele-autonomie-machinerie.
        Wat hier wordt vastgelegd is alleen wat de founder besloot, zodat een afgehandeld
        onderwerp niet elke week opnieuw om aandacht vraagt."""
        # AUTHZ: anchor-lead — zie het blok-comment boven de Founder Flow-takken.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _anchor_gate(st, username)
        if _deny:
            return nxt, _deny
        sleutel, keuze = g("sleutel"), g("keuze")
        onderwerp = g("onderwerp").strip()
        if not sleutel or keuze not in ("project", "watch"):
            return nxt, "✗ unknown topic or choice"
        ref = ""
        if keuze == "project":
            rol = g("rol") or "harry_hemp"
            if st.records.get(rol) is None:
                return nxt, "✗ the role behind this topic no longer exists"
            # Hetzelfde aanmaakpad als het projectenbord: een radar-onderwerp levert een echt
            # project op, geen aparte soort werk.
            ref = st.projects.create(rol, f"Onderzoek opkomend onderwerp: {onderwerp[:160]}",
                                     "founder_flow", status="queued", origin="radar_cluster",
                                     done_when="we weten of dit onderwerp iets voor Nooch betekent",
                                     description=g("bewijs")[:600])
        st.radar_besluiten.zet(sleutel, keuze, onderwerp=onderwerp, door=username or "?", ref=ref)
        return nxt, (f"📌 project created for “{onderwerp[:60]}”" if keuze == "project"
                     else f"👁 watching “{onderwerp[:60]}” — it stays in the trend view")


ACTIONS = {
    "ff_beslis": _act_ff_beslis,
    "ff_cluster": _act_ff_cluster,
    "ff_promote": _act_ff_promote,
    "ff_demote": _act_ff_demote,
    "ff_run": _act_ff_run,
    "kb_new": _act_kb_new,
    "kb_intake": _act_kb_intake,
    "kb_intake_url": _act_kb_intake_url,
    "kb_stage_edit": _act_kb_stage_edit,
    "kb_stage_accept": _act_kb_stage_accept,
    "kb_stage_delete": _act_kb_stage_delete,
    "kb_stage_merge": _act_kb_stage_merge,
    "kb_stage_commit": _act_kb_stage_commit,
    "kb_stage_discard": _act_kb_stage_discard,
    "kb_atoom_subject": _act_kb_atoom_subject,
    "kb_atoom_purge": _act_kb_atoom_purge,
    "tag_voorstel_besluit": _act_tag_voorstel_besluit,
    "tag_onderhoud_run": _act_tag_onderhoud_run,
    "copy_stack_inclusie": _act_copy_stack_inclusie,
    "verzoek_besluit": _act_verzoek_besluit,
    "kb_blacklist_leeg": _act_kb_blacklist_leeg,
    "kb_atoom_edit": _act_kb_atoom_edit,
    "kb_atoom_related": _act_kb_atoom_related,
    "kb_atoom_reference": _act_kb_atoom_reference,
    "kb_insight_link": _act_kb_insight_link,
    "kb_insight_unlink": _act_kb_insight_unlink,
    "kb_meta_start": _act_kb_meta_start,
    "kb_atoom_merge": _act_kb_atoom_merge,
    "kb_atoom_archive": _act_kb_atoom_archive,
    "kb_atoom_unarchive": _act_kb_atoom_unarchive,
    "kb_atoom_naar_spel": _act_kb_atoom_naar_spel,
    "kb_spel_start": _act_kb_spel_start,
    "kb_spel_add": _act_kb_spel_add,
    "kb_spel_remove": _act_kb_spel_remove,
    "kb_spel_flip": _act_kb_spel_flip,
    "kb_spel_finish": _act_kb_spel_finish,
    "kb_link": _act_kb_link,
    "kb_unlink": _act_kb_unlink,
    "kb_annotate": _act_kb_annotate,
    "kb_evidence": _act_kb_evidence,
    "kb_discuss": _act_kb_discuss,
    "kb_reformulate": _act_kb_reformulate,
    "kw_nominate": _act_kw_nominate,
    "kw_nom_accept": _act_kw_nom_accept,
    "kw_nom_reject": _act_kw_nom_reject,
    "ws_forbid": _act_ws_forbid,
    "ws_approve": _act_ws_approve,
    "proj_add": _act_proj_add,
    "artefact_add": _act_artefact_add,
    "artefact_edit": _act_artefact_edit,
    "artefact_archive": _act_artefact_archive,
    "pagina_feit_add": _act_pagina_feit_add,
    "pagina_feit_del": _act_pagina_feit_del,
    "pagina_voorstel": _act_pagina_voorstel,
    "proj_status": _act_proj_status,
    "proj_done": _act_proj_done,
    "proj_dod": _act_proj_dod,
    "proj_archive": _act_proj_archive,
    "proj_unarchive": _act_proj_unarchive,
    "proj_delete": _act_proj_delete,
    "proj_edit": _act_proj_edit,
    "proj_comment": _act_proj_comment,
    "proj_rename": _act_proj_rename,
    "proj_describe": _act_proj_describe,
    "proj_doc_edit": _act_proj_doc_edit,
    "proj_regen_doc": _act_proj_regen_doc,
    "proj_settrekker": _act_proj_settrekker,
    "proj_setowner": _act_proj_setowner,
    "proj_approve": _act_proj_approve,
    "proj_discard": _act_proj_discard,
    "proj_proposal_accept": _act_proj_proposal_accept,
    "proj_proposal_reject": _act_proj_proposal_reject,
    "proj_setlabel": _act_proj_setlabel,
    "proj_setimpact": _act_proj_setimpact,
    "proj_seteffort": _act_proj_seteffort,
    "proj_agendeer_verzwakt": _act_proj_agendeer_verzwakt,
    "proj_setprivate": _act_proj_setprivate,
    "proj_setdue": _act_proj_setdue,
    "attach_add": _act_attach_add,
    "attach_remove": _act_attach_remove,
    "react_add": _act_react_add,
    "feed_edit": _act_feed_edit,
    "feed_remove": _act_feed_remove,
    "wall_outcome": _act_wall_outcome,
    "notif_read": _act_notif_read,
    "notif_processed": _act_notif_processed,
    "notif_outcome": _act_notif_outcome,
    "notif_besluit": _act_notif_besluit,
    "notif_klaar": _act_notif_klaar,
    "notif_delete": _act_notif_delete,
    "notif_add": _act_notif_add,
    "notif_archive": _act_notif_archive,
    "metrics2_fav": _act_metrics2_fav,
    "metrics2_unfav": _act_metrics2_unfav,
    "metrics2_form": _act_metrics2_form,
    "metrics2_dim": _act_metrics2_dim,
    "metrics2_compare": _act_metrics2_compare,
    "metrics2_formula": _act_metrics2_formula,
    "source_activate": _act_source_activate,
    "source_deactivate": _act_source_deactivate,
    "link_pursue": _act_link_pursue,
    "link_ignore": _act_link_ignore,
    "acc_check": _act_acc_check,

    "ai_reply": _act_ai_reply,
    "proj_feed": _act_proj_feed,
    "checklist_add": _act_checklist_add,
    "checklist_remove": _act_checklist_remove,
    "check_add": _act_check_add,
    "check_accept": _act_check_accept,
    "check_toggle": _act_check_toggle,
    "check_skip": _act_check_skip,
    "check_unskip": _act_check_unskip,
    "check_handoff": _act_check_handoff,
    "check_remove": _act_check_remove,
    "role_assign": _act_role_assign,
    "role_unassign": _act_role_unassign,
    "role_focus": _act_role_focus,
    "radar_approve": _act_radar_approve,
    "radar_dismiss": _act_radar_dismiss,
    "radar_promote": _act_radar_promote,
    "radar_merge": _act_radar_merge,
    "radar_koppel": _act_radar_koppel,
    "kb_stage_koppel": _act_kb_stage_koppel,
    "aitask_add": _act_aitask_add,
    "aitask_remove": _act_aitask_remove,
    "skilllink_add": _act_skilllink_add,
    "means_gap_add": _act_means_gap_add,
    "persona_skill_add": _act_persona_skill_add,
    "rov2_add": _act_rov2_add,
    "rov2_add_to_group": _act_rov2_add_to_group,
    "rov2_remove": _act_rov2_remove,
    "rov2_remove_group": _act_rov2_remove_group,
    "rov2_setkind": _act_rov2_setkind,
    "rov2_consent": _act_rov2_consent,
    "rov2_end": _act_rov2_end,
    "wo_open": _act_wo_open,
    "wo_close": _act_wo_close,
    "wo_presence": _act_wo_presence,
    "wo_present_all": _act_wo_present_all,
    "vangst_add": _act_vangst_add,
    "vangst_tekst": _act_vangst_tekst,
    "vangst_klaar": _act_vangst_klaar,
    "vangst_uitkomst": _act_vangst_uitkomst,
    "vangst_uitkomst_weg": _act_vangst_uitkomst_weg,
    "vangst_uitkomst_edit": _act_vangst_uitkomst_edit,
    "vangst_remove": _act_vangst_remove,
    "vangst_verwerk": _act_vangst_verwerk,
    "wo_checkout": _act_wo_checkout,
    "noochie_send": _act_noochie_send,
    "noochie_reset": _act_noochie_reset,
    "noochie_ctx": _act_noochie_ctx,
    "cl_add": _act_cl_add,
    "cl_report": _act_cl_report,
    "cl_remove": _act_cl_remove,
    "m_add_kpi": _act_m_add_kpi,
    "m_add_from_def": _act_m_add_from_def,
    "def_add": _act_def_add,
    "catalog_publish": _act_catalog_publish,
    "def_amend": _act_def_amend,
    "m_add_link": _act_m_add_link,
    "m_sample": _act_m_sample,
    "m_remove": _act_m_remove,
    "m_pin": _act_m_pin,
    "m_unpin": _act_m_unpin,
    "tile_add": _act_tile_add,
    "indicator_activate": _act_indicator_activate,
    "tile_remove": _act_tile_remove,
    "rov2_set": _act_rov2_set,
    "rov2_acc_add": _act_rov2_set,
    "rov2_acc_remove": _act_rov2_set,
    "rov2_dom_add": _act_rov2_set,
    "rov2_dom_remove": _act_rov2_set,
    "backlog_add": _act_backlog_add,
    "backlog_update_staat": _act_backlog_update_staat,
    "backlog_update_prioriteit": _act_backlog_update_prioriteit,
    "person_edit": _act_person_edit,
    "person_remove": _act_person_remove,
    "lk_mute": _act_lk_mute,
    "claims_term_add": _act_claims_term_add,
    "claims_term_retract": _act_claims_term_retract,
    "claims_work_status": _act_claims_work_status,
    "claims_bewijs_link": _act_claims_bewijs_link,
    "claims_vondst_whitelist": _act_claims_vondst_whitelist,
    "claims_regel_uit_vondst": _act_claims_regel_uit_vondst,
    "claims_to_board": _act_claims_to_board,
    "persona_edit": _act_persona_edit,
    "persona_llm": _act_persona_llm,
    "persona_finetune": _act_persona_finetune,
    "persona_finetune_apply": _act_persona_finetune_apply,
}


def dispatch(data_dir: str, action: str, form: dict, username: str | None = None):
    """Verwerk een POST-actie. Geeft (redirect-URL, korte bevestiging) terug.

    `username` = e-mailadres van de ingelogde gebruiker (None = onbekend, "guest" = geen auth
    geconfigureerd). De rol-takken (role_assign/role_unassign/role_focus) dwingen autorisatie af:
    alleen de Circle Lead van de directe ouder-cirkel mag muteren. "guest" (auth uit) mag alles;
    een ingelogde maar onbekende gebruiker wordt geweigerd."""
    st = _Stores(data_dir)
    g = lambda k: (form.get(k) or [""])[0]
    nxt = g("next") or "/"
    if not nxt.startswith("/"):
        nxt = "/"
    handler = ACTIONS.get(action)
    if handler is None:
        return nxt, ""                 # onbekende actie: no-op (was: fall-through naar eind-return)
    return handler(_Ctx(st, g, nxt, form, username, action, data_dir))


# Niets is publiek: een uitgelogde bezoeker gaat overal naar /login. /login en /logout worden in
# do_GET vóór de auth-check afgehandeld en blijven dus bereikbaar. Er is geen asset/health-route die
# publiek moet blijven (/file staat al achter de auth-check).
_PUBLIC_GET: set[str] = set()


# Het kennis-budget van de wizard, in seconden. Er wacht een MENS voor een scherm, en zijn browser
# stapt eruit na `AI_TIMEOUT_MS` (12s, views/wizard.py). Het budget is met opzet een fractie daarvan:
# de raadpleging is de aanloop, het model is het werk, en de aanloop mag het werk niet opeten.
#
# Gemeten op prod 28 aug 2026: de raadpleging kostte 29,4s en het plannen zelf 3,3s. De server maakte
# de checklist keurig af en schreef hem in een verbinding die al dicht was — vier keer een
# BrokenPipeError in het log en vier keer "the assistant could not be reached" op het scherm.
#
# Dit knijpt alleen de semantische stap af; alle lexicale bronnen blijven staan (zie
# `kennis_context.kennis_voor`). Voor de daemon verandert er niets: die geeft geen budget mee.
_WIZARD_KENNIS_BUDGET_S = 2.5


def _home_node(recs) -> str:
    """De node waarop '/' opent: de operationele cirkel (Nooch), niet de anchor (Mother Earth) —
    daar gebeurt het meeste werk. Fallback: eerste sub-cirkel van de root, anders de root zelf,
    anders '' (geen organisatie geladen)."""
    roots = org.roots(recs)
    if not roots:
        return ""
    subs = [k for k in org.children_of(recs, roots[0].id) if org.is_circle(k)]
    return next((s.id for s in subs if s.id == "mother_earth__nooch"),
                subs[0].id if subs else roots[0].id)


def make_handler(data_dir: str, csrf_token: str,
                 sessions: "_auth.SessionStore | None" = None,
                 users: "_auth.UserStore | None" = None):
    class H(BaseHTTPRequestHandler):
        def _session_username(self) -> str | None:
            if sessions is None:
                return "guest"
            token = _auth.get_session_token(self.headers)
            return sessions.get_username(token) if token else None

        def _redirect_to(self, location: str, cookie: str | None = None) -> None:
            self.send_response(303)
            self.send_header("Location", location)
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()

        def _send(self, body: str, code: int = 200, chrome: bool = True):
            # Globale chrome = de inbox-drawer (launcher + uitschuif-paneel links + modal). Alleen voor een
            # sessie en alleen op volledige HTML-pagina's (met </body>). chrome=False voor de inbox-routes
            # zelf (die zijn de drawer-inhoud / het fragment; injecteren zou de drawer in zichzelf nesten).
            # De dorp-brede call bar is terug (founder 21 jul); de Noochie-rail blijft bewust weg
            # ('chatten met de raad' komt later als eigen feature). De call bar-iframe start hidden en
            # onthult zichzelf pas als LiveKit geconfigureerd is (token ok), dus ongeconfigureerd = geen bar.
            if chrome and self._session_username() is not None and "</body>" in body:
                try:
                    _st = _Stores(data_dir)
                    _ro = _person_role_options(_st, _person_targets(_st, self._session_username()))
                except Exception:
                    _st, _ro = None, ""
                # Pattern-fix (founder 23 jul): ELKE pagina die nog geen organisatieboom-rail heeft
                # krijgt hem hier alsnog, zodat je bij élke tool je navigatie houdt — niet alleen op het
                # projectenbord. Node-pagina's hebben al een `c2-rail` en worden overgeslagen. De rail
                # wordt vóór de main geïnjecteerd; flex-order (.c2-rail{order:1}) zet hem toch rechts.
                if _st is not None and "c2-rail" not in body and "class='c2-wrap'>" in body:
                    try:
                        from nooch_village.views.overview import _tree_html
                        _rail = f"<div class='c2-rail'>{_tree_html(_st, '')}</div>"
                        body = body.replace("<div class='c2-wrap'>",
                                            f"<div class='c2-wrap'>{_rail}", 1)
                    except Exception:
                        pass
                # Persoonlijke begroeting in de header: voornaam van de ingelogde persoon, klikbaar
                # naar de eigen persoonspagina (/person?id=...).
                if _st is not None:
                    try:
                        _p = _st.people.by_email(self._session_username())
                        _vn = ((getattr(_p, "name", "") or "").split() or [""])[0]
                        _pid = getattr(_p, "id", "") or ""
                        if _vn:
                            _naam = (f"<a href='/person?id={_e(_pid)}'>{_e(_vn)}</a>"
                                     if _pid else _e(_vn))
                            body = body.replace(
                                "<span class='c2-greet' id='c2-greet'></span>",
                                f"<span class='c2-greet' id='c2-greet'>Hoi {_naam}</span>", 1)
                    except Exception:
                        pass
                # De LiveKit-callbar is 11 aug 2026 uit de app-shell gehaald: hij werkte niet
                # betrouwbaar, en een strook die het soms doet is erger dan geen strook. De
                # /callbar-route en de LiveKit-helpers blijven bestaan (dood maar intact), zodat
                # terugzetten één regel is en er nu geen halve opruiming in de weg zit.
                body = body.replace(
                    "</body>",
                    render_inbox_chrome(csrf_token, _ro) + _footer() + "</body>", 1)
            b = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self._schrijf(b)

        def _schrijf(self, b: bytes) -> bool:
            """Het antwoord naar de client schrijven. False = de client was er niet meer.

            EEN VERBROKEN VERBINDING IS GEEN FOUT VAN ONS. De browser breekt af (de gebruiker
            navigeert weg, of een fetch-timeout zoals `AI_TIMEOUT_MS` in de wizard verloopt), en pas
            daarna komt ons antwoord aan bij een socket die al dicht is. Dat leverde tot nu toe een
            grafsteen op: een BrokenPipeError met volledige traceback, doorgegeven aan de
            `except Exception` van de route, die er dan een HTTP 500 van maakte — een 500 die
            niemand meer kón ontvangen. In de logs las dat als "het endpoint faalde", terwijl het
            werk juist AF was; op prod stonden zo vier /wizard/plan-"fouten" die in werkelijkheid
            vier voltooide checklists waren.

            Daarom hier gevangen en niet doorgegeven: er valt niets meer te doen of te melden aan
            een verbinding die weg is. Eén rustige INFO-regel met het pad, zodat het zichtbaar
            blijft dat er iemand vertrok — dat is een signaal over TRAAGHEID, niet over falen."""
            try:
                self.wfile.write(b)
                return True
            except (BrokenPipeError, ConnectionResetError):
                logging.getLogger("cockpit2").info(
                    "client vertrok voordat het antwoord verstuurd was (%s, %d bytes)",
                    self.path, len(b))
                return False

        def _send_bytes(self, data: bytes, content_type: str, filename: str = "",
                        cache_secs: int = 0):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            if cache_secs:
                self.send_header("Cache-Control", f"public, max-age={cache_secs}")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self._schrijf(data)

        def _send_json(self, payload: dict, code: int = 200):
            b = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self._schrijf(b)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            qs = urllib.parse.parse_qs(query)

            # ── Login / logout ──────────────────────────────────────────────
            if path == "/login":
                next_url = (qs.get("next") or ["/"])[0]
                self._send(_auth.login_page(next_url))
                return
            if path == "/logout":
                token = _auth.get_session_token(self.headers)
                if token and sessions:
                    sessions.delete(token)
                self._redirect_to("/login", _auth.clear_cookie())
                return

            # ── Auth-check voor niet-publieke GETs ─────────────────────────
            username = self._session_username()
            if username is None and path not in _PUBLIC_GET:
                self._redirect_to(f"/login?next={urllib.parse.quote(self.path)}")
                return

            # Publieke views krijgen geen CSRF-token → geen schrijfknoppen
            effective_csrf = csrf_token if username else ""

            st = _Stores(data_dir)
            # ── Wachtwoordwijziging (self-service + verplichte eerste-login/na-reset-poort) ──
            if path == "/wachtwoord":
                # AUTHZ: circle-member of iedereen-ingelogd — eigen wachtwoord wijzigen
                self._send(_auth.password_change_page(forced=st.people.must_change(username or "")))
                return
            if username and st.people.must_change(username):     # poort: alles → /wachtwoord tot gewijzigd
                self._redirect_to("/wachtwoord")
                return
            if path == "/snake":
                # AUTHZ: ingelogde-member — verborgen easter-egg 'Snaker'; puur fun, los van alles.
                # De login-redirect hierboven dekt de niet-ingelogde gebruiker al af.
                # chrome=False: geen dorp-brede call bar/Noochie-rail injecteren — de pagina draait als
                # fullscreen-overlay-iframe op de cockpit; de bar leeft in de PARENT en wordt daar via
                # body.overlay-open verborgen. Injecteren zou hier een tweede (ongestylede) bar geven.
                self._send(snake.render_snake_page(st, username, effective_csrf), chrome=False)
                return
            if path == "/context":
                # AUTHZ: iedereen-ingelogd — rol-context is dezelfde read-scope als /node?tab=notes
                # (één rol), dus in auth-uit óók voor guest zichtbaar; alleen de persoon-context-
                # aggregatie blijft gated (besluit 2026-07-03). De login-redirect hierboven dekt de
                # niet-ingelogde gebruiker al af.
                # OPEN PUNT (niet nu): geen read-scope-per-rol. Elke ingelogde gebruiker (+ guest in
                # auth-uit) leest élke rol-context. Nu ongevaarlijk (geen artefacten; anchor-policies
                # zijn publieke missieprincipes), maar zodra rollen gevoelige policies/notes krijgen
                # (business-model, leveranciers-afspraken) is een per-rol read-scope nodig.
                status, ctype, body = role_context(st, (qs.get("id") or [""])[0],
                                                    (qs.get("format") or ["json"])[0])
                b = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self._schrijf(b)
                return
            if path == "/epic/frame":
                # NASA EPIC-frame (server-side naar ~512px JPEG geresized) doorserveren; key blijft server-side.
                data = epic.frame_bytes((qs.get("image") or [""])[0], (qs.get("date") or [""])[0])
                if data:
                    self._send_bytes(data, "image/jpeg")
                else:
                    self._send("", 404)
                return
            if path in ("/", "/index.html"):
                default_id = _home_node(st.records.all())
                if default_id:
                    self.send_response(302)
                    self.send_header("Location", f"/node?id={default_id}")
                    self.end_headers()
                    return
                self._send(_page("Empty", "<p>No organisation loaded yet.</p>"))
                return
            if path == "/node":
                nid = (qs.get("id") or [""])[0]
                ntab = (qs.get("tab") or ["overview"])[0]
                self._send(render_node(st, nid, ntab, csrf_token=effective_csrf,
                                       msg=(qs.get("msg") or [""])[0],
                                       group=(qs.get("group") or [""])[0],
                                       clf=(qs.get("clf") or ["due"])[0],
                                       mw=(qs.get("mw") or ["7d"])[0],
                                       van=(qs.get("van") or [""])[0],
                                       tot=(qs.get("tot") or [""])[0],
                                       compare=(qs.get("compare") or [""])[0] == "1",
                                       username=username))
                return
            if path == "/backlog":
                # AUTHZ: iedereen-ingelogd — inbrengen mag iedereen (dat is het punt van een
                # backlog). Beheren (staat, prioriteit) zit achter `_wd_gate` in de dispatch-takken,
                # niet hier; deze route toont alleen wat je mag zien.
                self._send(render_backlog(st, csrf=effective_csrf, username=username,
                                          msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/pagina":
                # AUTHZ: iedereen-ingelogd — een wiki-pagina IS een rol-note, dus exact dezelfde
                # read-scope als /node?tab=notes (lezen is vrij, cureren is van de eigenaar-rol).
                # Schrijven zit achter de artefact-poort in de dispatch-acties, niet hier.
                self._send(render_pagina(st, (qs.get("id") or [""])[0],
                                         csrf_token=effective_csrf, username=username,
                                         msg=(qs.get("msg") or [""])[0]))
                return
            # Modal-fragmenten krijgen hun eigen <style> mee, zodat ze altijd verse CSS tonen
            # (de overlay hergebruikt anders de stylesheet van de eerste pagina-load).
            def _frag(out: str, is_frag: bool) -> str:
                return (f"<style>{_EXTRA_CSS}</style>{out}") if is_frag else out

            if path == "/project/nieuw":
                # De geleide project-wizard (founder 20 jul). Standalone = vol scherm (geen Noochie-rail);
                # in de modal-overlay (?fragment=1) alleen de body, met een voorgeselecteerde rol.
                fr = (qs.get("fragment") or [""])[0] == "1"
                # `ruw`/`uitkomst` zijn de voorvulling uit de plek waar je vandaan komt (het bord
                # of een inbox-spanning). Wat de mens al intypte hoort hij niet over te tikken.
                # `mine=1` komt uit de inbox: daar maak je alleen een project voor een rol die
                # je ZELF vervult. Geen aparte wizard — dezelfde, met een smallere rolkiezer.
                _eigen = None
                if (qs.get("mine") or [""])[0] == "1":
                    _eigen = [tid for ty, tid in _person_targets(st, username) if ty == "role"]
                self._send(render_wizard(st, effective_csrf,
                                         role=(qs.get("role") or [""])[0], fragment=fr,
                                         ruw=(qs.get("ruw") or [""])[0],
                                         uitkomst=(qs.get("uitkomst") or [""])[0],
                                         trekker=(qs.get("trekker") or [""])[0],
                                         eigen=_eigen),
                           chrome=False)
                return

            if path == "/project":
                fr = (qs.get("fragment") or [""])[0] == "1"
                # Accepteer ?id= als alias voor ?pid= (founder 20 jul): de projectsignalen linken
                # historisch met ?id= (tevens de dedup-sleutel in `seen`), maar de route las alleen
                # ?pid= → "Project not found". Alias ipv linkformaat wijzigen houdt de dedup stabiel.
                _pid = (qs.get("pid") or qs.get("id") or [""])[0]
                self._send(_frag(render_project(st, _pid, csrf_token=effective_csrf,
                                                msg=(qs.get("msg") or [""])[0],
                                                back=(qs.get("back") or ["/"])[0], fragment=fr), fr))
                return
            if path == "/rolefillers":
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_rolefillers(st, (qs.get("role") or [""])[0],
                                                    csrf_token=effective_csrf, fragment=fr), fr))
                return
            if path == "/aitask":
                role_id = (qs.get("role") or [""])[0]
                aid = _acc_id_param(st, role_id, qs)
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_aitask(st, role_id, aid,
                                               csrf_token=effective_csrf, fragment=fr), fr))
                return
            if path == "/person":
                self._send(render_person(st, (qs.get("id") or [""])[0],
                                         tab=(qs.get("tab") or ["rollen"])[0],
                                         username=username, csrf_token=effective_csrf))
                return
            if path == "/admin":
                self._send(render_admin(st, csrf_token=effective_csrf, msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/founder":
                # De trainingslus van de founder: drie taken, elk met een eigen rijpheidsniveau.
                # Achter dezelfde sessie-auth als de rest; de schrijfacties gaan door _anchor_gate.
                self._send(render_founder_flow(
                    st, data_dir, csrf_token=effective_csrf,
                    msg=(qs.get("msg") or [""])[0], ritme=(qs.get("ritme") or ["dag"])[0],
                    onthuld=(qs.get("onthuld") or [""])[0],
                    radar_view=(qs.get("radar") or ["trend"])[0], username=username))
                return
            if path == "/_patterns":
                self._send(render_patterns(effective_csrf))
                return
            if path == "/signals":
                # Dorp-brede lijst van goedgekeurde radar-signalen (read-only aggregatie). Publiek zoals
                # het overzicht; achter de sessie-auth zoals alles.
                self._send(render_signals(st, csrf_token=effective_csrf, feed=(qs.get("feed") or [""])[0]))
                return
            if path == "/inbox":
                # De inbox van de ingelogde mens: mentions aan hem (als persoon of via zijn rollen).
                tgts = _person_targets(st, username)
                # chrome=False: de drawer wordt door _send geïnjecteerd op ANDERE pagina's; deze route IS
                # de drawer-inhoud (fragment) of de standalone-fallback, dus geen drawer-in-drawer.
                if (qs.get("frag") or [""])[0]:
                    self._send(render_inbox_frag(st, tgts, csrf_token=effective_csrf), chrome=False)
                    return
                nm = ""
                if username and username != "guest":
                    _p = st.people.by_email(username)
                    nm = _p.name if _p else ""
                done = (qs.get("done") or [""])[0]
                self._send(render_inbox(st, tgts, csrf_token=effective_csrf, naam=nm, done=done), chrome=False)
                return
            if path == "/search":
                # Globale zoekopdracht vanuit de header: roles, projects, insights, signals.
                # ?frag=1 → alleen de dropdown-inhoud (live terwijl je typt); anders de volle pagina.
                _q = (qs.get("q") or [""])[0]
                if (qs.get("frag") or [""])[0] in ("1", "true", "on"):
                    self._send(render_search_fragment(st, _q), chrome=False)
                else:
                    self._send(render_search(st, _q))
                return
            if path == "/skills":
                # Skills-catalogus: wat kan het dorp al, en waarvoor moet tooling komen.
                # Puur leeswerk. De human inbox voedt het 'gewenst'-blok; fail-soft als hij
                # er (nog) niet is — dan blijft dat blok simpelweg leeg.
                try:
                    from nooch_village.human_inbox import HumanInbox
                    _hi = HumanInbox(os.path.join(data_dir, "human_inbox.json"))
                except Exception:
                    _hi = None
                self._send(render_skills(st, _hi))
                return
            if path == "/bronnen":
                # Aansluit-scherm voor externe databronnen (status + aan/uit).
                self._send(render_bronnen(st, os.path.dirname(data_dir), csrf_token=effective_csrf))
                return
            if path == "/codie":
                # Codie-backlog: de capaciteit-gaten die de escalatie-router oogstte, geclusterd
                # per ontbrekende capaciteit. Read-only — de mens-poort zit op het pad van gat naar
                # code-wijziging, niet op dit scherm.
                self._send(render_codie(data_dir))
                return
            if path == "/inzichten":
                # Kennislaag: de inzicht-kaarten die de Librarian ving (read-only).
                self._send(render_kennislaag(data_dir))
                return
            if path == "/kennisbank":
                # Kennisbank (laag 2): geversioneerde inzichten met een berekend veld van
                # zekerheid boven de atomen (notes.json). ?id= opent het detail als drawer;
                # ?hunch= zoekt kaarten (top-down), ?speel= toont een cluster-set (bottom-up),
                # ?nieuw= toont de atomen van de laatste intake.
                try:
                    _pag = max(1, int((qs.get("pag") or ["1"])[0]))
                except ValueError:
                    _pag = 1
                try:
                    _cl = max(0, int((qs.get("cluster") or ["0"])[0]))
                except ValueError:
                    _cl = 0
                try:
                    _sug = max(0, int((qs.get("sug") or ["0"])[0]))
                except ValueError:
                    _sug = 0
                self._send(render_kennisbank(st, kid=(qs.get("id") or [""])[0],
                                             q=(qs.get("q") or [""])[0],
                                             csrf_token=effective_csrf,
                                             msg=(qs.get("msg") or [""])[0],
                                             hunch=(qs.get("hunch") or [""])[0],
                                             speel=(qs.get("speel") or [""])[0],
                                             nieuw=(qs.get("nieuw") or [""])[0],
                                             hub=(qs.get("hub") or [""])[0], pag=_pag,
                                             open_=(qs.get("open") or [""])[0], cluster=_cl,
                                             flip=(qs.get("flip") or [""])[0] in ("1", "true", "on"),
                                             sug=_sug))
                return
            if path == "/kennisbank/search":
                # Live smart-search fragment (PR-2): alleen de resultatenlijst, over de verse
                # bibliotheek. Zoekt op inhoud én bron; markeert brug-suggesties bij een
                # actief inzicht. chrome=False: het is een fragment dat de JS inplakt.
                self._send(render_kennisbank_search(st, (qs.get("q") or [""])[0],
                                                    (qs.get("hub") or [""])[0],
                                                    (qs.get("active") or [""])[0],
                                                    csrf_token=effective_csrf), chrome=False)
                return
            if path == "/kennisbank/tags":
                # Tag-onderhoud: de weekvoorstellen van de Library, mens keurt (founder, 19 jul).
                from nooch_village.views.tag_onderhoud import render_tag_onderhoud
                self._send(render_tag_onderhoud(st, csrf_token=effective_csrf,
                                                msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/kennisbank/staging":
                # Zone 2: de "even nakijken"-ronde vóór de bibliotheek (bewerken/samenvoegen/weggooien).
                self._send(render_kennisbank_staging(st, (qs.get("batch") or [""])[0],
                                                     csrf_token=effective_csrf,
                                                     msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/kennisbank/spel":
                # Het inzicht-spel, copy-paste-flow: hand cureren → prompt kopiëren →
                # blok terugplakken → munten. ?zoek= zoekt kaarten voor de hand.
                self._send(render_kennisbank_spel(st, (qs.get("sid") or [""])[0],
                                                  zoek=(qs.get("zoek") or [""])[0],
                                                  csrf_token=effective_csrf,
                                                  msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/kennisbank/spel/search":
                # Live zoek-fragment op de spel-pagina (Oracle-patroon, founder 19 jul):
                # alleen de resultaten, over de verse bibliotheek en de verse hand;
                # in-het-spel-kaarten gemarkeerd groen/rood. chrome=False: fragment.
                self._send(render_kennisbank_spel_search(st, (qs.get("sid") or [""])[0],
                                                         zoek=(qs.get("zoek") or [""])[0],
                                                         csrf_token=effective_csrf),
                           chrome=False)
                return
            if path == "/linkbuilding":
                # Linkbuilding-doelwitten geborgd in cockpit 2 (pitchen/negeren).
                self._send(render_linkbuilding(data_dir, csrf_token=effective_csrf))
                return
            if path == "/accountabilities":
                # Dorpsbrede accountability-check (dubbelingen + formulering).
                self._send(render_accountabilities(st, data_dir, csrf_token=effective_csrf))
                return
            if path == "/woordenschat":
                # Library-kansenscherm: verrijkte keywords gerangschikt op kansrijkheid; met
                # csrf-token read-write (beheer: verbied/heractiveer + nominatie-oordeel).
                # can_decide: alleen de Librarian-vervuller beslist over nominaties (zelfde
                # gate als /keywords?lens=library).
                can_decide = _role_gate("librarian", username, st) is None
                self._send(render_woordenschat(data_dir, csrf_token=effective_csrf,
                                               msg=(qs.get("msg") or [""])[0],
                                               can_decide=can_decide))
                return
            if path == "/keywords":
                # IA-fase 3: één keyword-datalaag, rol-lenzen (?lens=marketing|scientist|trends|
                # library|kroniek). IA-fase 4: nomineren kan iedereen; alleen Lara (librarian-
                # rolvervuller) beslist — can_decide gate bepaalt of accept/reject-controls renderen.
                can_decide = _role_gate("librarian", username, st) is None
                self._send(render_keyword_lens(st, (qs.get("lens") or ["trends"])[0],
                                               csrf_token=effective_csrf, can_decide=can_decide))
                return
            if path == "/long-term-trends":
                # IA-fase 2→3: de Scientist-lens is nu een lens op de gedeelde laag. Oude route
                # blijft werken via een redirect (geen dode deep-links).
                self._redirect_to("/keywords?lens=scientist")
                return
            if path == "/belofte":
                # Belofte-graaf: eerste-principes-ontleding, sterkte op het zwakste onderdeel (read-only, stap 1).
                bid = (qs.get("id") or [""])[0]
                self._send(render_belofte(data_dir, bid))
                return
            if path == "/metrics2":
                # Nieuw catalogus-plus-dashboard-scherm, náást het bestaande metrics-scherm.
                node = (qs.get("node") or [""])[0]
                rec = st.records.get(node) if node else None
                win = (qs.get("mw") or ["7d"])[0]
                compare = (qs.get("compare") or [""])[0] in ("1", "true", "on")
                van = (qs.get("van") or [""])[0]
                tot = (qs.get("tot") or [""])[0]
                self._send(render_metrics2(st, rec, csrf_token=effective_csrf, win=win,
                                           compare=compare, van=van, tot=tot))
                return
            if path == "/inbox/verwerk":
                # De twee-panelen-verwerkpagina voor één spanning: links de spanning, rechts de wizard.
                # chrome=False: draait als modal-iframe binnen de drawer; geen tweede drawer injecteren.
                nid = (qs.get("nid") or [""])[0]
                n = st.notif._find(nid)
                ro = _wall_outcome_opts(st)[0] if n is not None else ""
                po = _scoped_project_opts(st, n) if n is not None else ""
                self._send(render_verwerk(st, n, csrf_token=effective_csrf, role_opts=ro, pj_opts=po),
                           chrome=False)
                return
            if path == "/catalog":
                # AUTHZ: anchor-lead — het overzicht is publiek; de geïntegreerde koppel-sectie (ruw veld
                # → indicator) rendert alleen voor de curator. guest (auth-uit) telt als curator.
                actor = st.people.by_email(username) if username and username != "guest" else None
                curator = actor is None or is_circle_lead(actor.id, "mother_earth", st.assign)
                self._send(render_catalog(st, csrf_token=effective_csrf, msg=(qs.get("msg") or [""])[0],
                                          koppel=(qs.get("koppel") or [""])[0], curator=curator))
                return
            if path == "/catalogus_koppelen":
                # Samengevoegd in /catalog (scope 4): geen los scherm meer → 303 naar het koppel-onderdeel.
                src = (qs.get("source") or [""])[0]
                self._redirect_to(f"/catalog?koppel={urllib.parse.quote(src or '1')}")
                return
            if path == "/kpi_new":
                self._send(render_kpi_composer(st, (qs.get("node") or [""])[0],
                                               csrf_token=effective_csrf, msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/noochie":
                self._send(render_noochie(st, effective_csrf, (qs.get("ctx") or [""])[0]))
                return
            if path == "/vangst":
                # Vangen scheiden van verwerken. Geen modal (js-modal zou het
                # altijd-zichtbare veld in een overlay stoppen, en dan is de één-toets-flow weg).
                # `.all()`, niet de store zelf: `org.roots` itereert over records. Zonder dit
                # gaf /vangst zonder ?circle= een 502 — onzichtbaar voor elke test die wél een
                # cirkel meegeeft, en precies de URL die je intikt als je het scherm zoekt.
                _c = (qs.get("circle") or [""])[0] or _home_node(st.records.all())
                _open = (qs.get("open") or [""])[0]
                if (qs.get("frag") or [""])[0]:
                    # Alleen de lijst — het veld blijft staan waar het staat, met de cursor erin.
                    #
                    # `nxt` MOET van de aanroeper komen. Stond hier de vaste /vangst-URL, dan
                    # droegen alle formulieren in de ververste lijst die terug-URL — en werd je bij
                    # de eerstvolgende uitkomst het werkoverleg uit gegooid, naar het vangscherm.
                    # Precies de bug die `render_vangst_frag(nxt=...)` al oploste voor de
                    # server-render, maar niet voor de live verversing: het fragment wist niet wie
                    # hem aanriep. Gemeten op 28-08-2026 tijdens de scherm-check.
                    from nooch_village.views.vangst import veilige_nxt
                    _nxt = veilige_nxt((qs.get("nxt") or [""])[0], _c)
                    _frag = render_vangst_frag(st, _c, csrf_token=effective_csrf,
                                               open_iid=_open, nxt=_nxt)
                    # Op verzoek van de aanroeper reist het stappenmenu-blok mee, zodat de
                    # geneste puntenlijst na een vangst óók ververst en niet alleen de teller.
                    if (qs.get("sub") or [""])[0] == "wo":
                        from nooch_village.views.werkoverleg import _agenda_substeps
                        _crec = st.records.get(_c)
                        if _crec is not None:
                            _frag += (f"<template data-nv-mirror-html='#wo-agenda-sub'>"
                                      f"{_agenda_substeps(st, _crec, _open)}</template>")
                    self._send(_frag, chrome=False)
                    return
                self._send(render_vangst(st, _c, csrf_token=effective_csrf,
                                         msg=(qs.get("msg") or [""])[0], open_iid=_open))
                return
            if path == "/werkoverleg":
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_werkoverleg(st, (qs.get("circle") or [""])[0],
                                                    (qs.get("step") or ["checkin"])[0],
                                                    csrf_token=effective_csrf, fragment=fr,
                                                    # `open` is wat de gedeelde vangst-component
                                                    # terugstuurt; `iid` is de oudere naam. Beide
                                                    # accepteren houdt het blok open na een uitkomst.
                                                    iid=((qs.get("iid") or [""])[0]
                                                         or (qs.get("open") or [""])[0]),
                                                    kpi=(qs.get("kpi") or [""])[0],
                                                    mw=(qs.get("mw") or ["maand"])[0]), fr))
                return
            if path == "/callbar":
                # AUTHZ: iedereen-ingelogd — de route levert alleen de bar-UI (iframe-body); de
                # daadwerkelijke toegang bewaakt /livekit-token zelf. Achter de sessie-auth zoals alles.
                # chrome=False: deze pagina IS de bar en mag de iframe niet in zichzelf injecteren.
                self._send(render_callbar(csrf_token=effective_csrf), chrome=False)
                return
            if path == "/livekit-token":
                # Enige request-input: `tab` (per-tabblad-suffix). Room + identity-base bepaalt de
                # server zelf (zie issue_livekit_token). AUTHZ: iedereen-ingelogd, in die functie.
                status, payload = issue_livekit_token(st, username, (qs.get("tab") or [""])[0])
                self._send_json(payload, status)
                return
            if path == "/livekit-presence":
                # Goedkope presence voor de callbar: telt deelnemers in de dorp-room server-side, ZONDER
                # zelf te verbinden. Vervangt de oude observer-connect die WebRTC-minuten opslurpte.
                count, names = livekit_presence()
                self._send_json({"count": count, "names": names}, 200)
                return
            if path == "/claims/db.json":
                # AUTHZ: iedereen-ingelogd — naslagwerk, lezen is vrij (domein-regel: cureren is
                # exclusief compliance, en dat loopt via de dispatch-takken hieronder).
                try:
                    self._send_bytes(
                        json.dumps(_claims_db.load(data_dir=data_dir), ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8")
                except _claims_db.ClaimsDbError as e:
                    self._send_json({"error": str(e)}, 500)   # fail-closed: liever een fout dan lege lijst
                return
            if path == "/claims":
                # AUTHZ: iedereen-ingelogd — checken is voor alle rollen; muteren kan hier niet
                # (de schrijfknoppen hangen aan de compliance-gate in _act_claims_*).
                self._send(render_claims(
                    csrf_token=effective_csrf,
                    msg=(qs.get("msg") or [""])[0],
                    tab=(qs.get("tab") or ["check"])[0],
                    kan_cureren=_claims_gate_open(_Stores(data_dir), username),
                    zoek=(qs.get("q") or [""])[0],
                    data_dir=data_dir,
                    bewijzen=_claims_bewijzen(data_dir),
                    labels=_claims_labels.telling(data_dir),
                    bordresultaat=_claims_bordresultaat(qs)))
                return
            if path == "/copy-prompt":
                # AUTHZ: iedereen-ingelogd — dezelfde read-scope als /node?tab=policies en
                # /context: de pagina toont policies die die routes ook al tonen, en schrijft
                # niets. Wijzigen blijft bij de domein-eigenaar via de artefact-routes.
                # De segmented picker verstuurt zijn keuze als `set_<naam>`; het hidden veld draagt
                # de vorige keuze. Een klik op de picker wint dus van wat er stond.
                _soort = (qs.get("set_soort") or qs.get("soort") or [""])[-1]
                _doel = (qs.get("set_doel") or qs.get("doel") or [""])[-1]
                _aware = (qs.get("set_awareness") or qs.get("awareness") or [""])[-1]
                # De schakelaars en de compositie zijn org-configuratie, geen schrijfkeuze: alleen
                # de anchor-lead ziet ze. Fail-closed — geen vlag is de lees-versie.
                _admin = _anchor_gate(st, self._session_username()) is None
                self._send(render_copy_prompt(st,
                                              rol=(qs.get("rol") or [""])[0],
                                              soort=_soort,
                                              brief=(qs.get("brief") or [""])[0],
                                              uit=(qs.get("uit") or [""])[0],
                                              doel=_doel, awareness=_aware, admin=_admin))
                return
            if path == "/inwoners":
                # AUTHZ: iedereen-ingelogd — het dorp mag zien wie er woont; bewerken zit achter
                # de anchor-lead-poort in de dispatch-takken.
                self._send(render_inwoners(_Stores(data_dir), msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/inwoner":
                # AUTHZ: iedereen-ingelogd — lezen mag iedereen; het formulier verschijnt alleen
                # mét csrf (ingelogd) en de schrijfactie toetst apart op anchor-lead.
                st = _Stores(data_dir)
                pid = (qs.get("id") or [""])[0]
                self._send(render_inwoner(st, pid, csrf_token=effective_csrf,
                                          msg=(qs.get("msg") or [""])[0],
                                          voorstellen=_finetune_cache.get(pid, [])))
                return
            if path.startswith("/static/"):
                name = path[len("/static/"):]
                ct = _STATIC_TYPES.get(name)                 # whitelist → geen path-traversal
                if ct is None:
                    self._send("Not found", 404); return
                try:
                    with open(os.path.join(os.path.dirname(__file__), "static", name), "rb") as _f:
                        _data = _f.read()
                except OSError:
                    self._send("Not found", 404); return
                # Alle whitelisted statics zijn versieloos-of-gehasht → dag-cache is veilig
                # (nooch.css draagt een inhoud-hash in de URL, zie _DS_LINK).
                self._send_bytes(_data, ct, cache_secs=86400); return
            if path == "/roloverleg2":
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_roloverleg2(st, (qs.get("circle") or [""])[0],
                                                    (qs.get("iid") or [""])[0],
                                                    csrf_token=effective_csrf, fragment=fr), fr))
                return
            if path == "/metric_export":
                res = _metric_csv(st, (qs.get("mid") or [""])[0])
                if res is None:
                    self._send("<p>KPI not found</p>", 404); return
                fname, body = res
                self._send_bytes(body.encode("utf-8"), "text/csv; charset=utf-8", fname)
                return
            if path.startswith("/kbref/"):
                # Kennisbank-bron-PDF's (kb_atoom_ref_pdf): geserveerd uit data/kbref/.
                # Basename-only tegen path-traversal; alleen .pdf. Achter de auth-check.
                fname = os.path.basename(urllib.parse.unquote(path[len("/kbref/"):]))
                full = os.path.join(data_dir, "kbref", fname)
                if not (fname.lower().endswith(".pdf") and os.path.exists(full)):
                    self._send("<p>File not found</p>", 404); return
                with open(full, "rb") as fh:
                    self._send_bytes(fh.read(), "application/pdf")
                return
            if path == "/file":
                p = st.projects.get((qs.get("pid") or [""])[0])
                aid = (qs.get("aid") or [""])[0]
                att = next((a for a in (p.get("attachments") or [])
                            if a.get("id") == aid and a.get("kind") == "file"), None) if p else None
                full = os.path.join(data_dir, att["stored"]) if att else None
                if not (full and os.path.exists(full)):
                    self._send("<p>File not found</p>", 404); return
                with open(full, "rb") as fh:
                    data = fh.read()
                mt = mimetypes.guess_type(att.get("name", ""))[0] or "application/octet-stream"
                self._send_bytes(data, mt)
                return
            self._send("<p>404</p>", 404)

        def _redirect(self, nxt: str, msg: str):
            if msg:
                sep = "&" if "?" in nxt else "?"
                nxt = f"{nxt}{sep}msg={urllib.parse.quote(msg)}"
            self.send_response(303); self.send_header("Location", nxt); self.end_headers()

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            ctype = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length") or 0)

            # ── Login POST ──────────────────────────────────────────────────
            if path == "/login":
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                form = urllib.parse.parse_qs(raw)
                email    = (form.get("email") or [""])[0].strip()
                password = (form.get("password") or [""])[0]
                next_url = (form.get("next") or ["/"])[0]
                if users and users.verify_by_email(email, password):
                    _Stores(data_dir).people.touch_login(email)
                    token = sessions.create(email) if sessions else ""
                    self._redirect_to(next_url or "/", _auth.set_cookie(token))
                else:
                    self._send(_auth.login_page(next_url, error="Email address or password is incorrect."))
                return

            if path == "/snake/score":
                # AUTHZ: ingelogde-member — iedereen mag spelen; de score wordt ONDER de sessie-gebruiker
                # geschreven (nooit een meegestuurde naam), en alleen als hij hoger is dan het record.
                username = self._session_username()
                if sessions is not None and username is None:
                    self._send("Not logged in", 403); return
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                form = urllib.parse.parse_qs(raw)
                if not secrets.compare_digest((form.get("csrf") or [""])[0], csrf_token):
                    self._send("CSRF token invalid", 403); return
                self._send_json(snake.handle_score(_Stores(data_dir), username, (form.get("score") or ["0"])[0]))
                return

            # ── Project-wizard (JSON fetch-endpoints; csrf + sessie, zoals snake) ──────────
            if path in ("/wizard/sharpen", "/wizard/plan", "/wizard/impact",
                            "/wizard/rollen", "/wizard/create"):
                username = self._session_username()
                if sessions is not None and username is None:
                    self._send_json({"error": "not logged in"}, 403); return
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                form = urllib.parse.parse_qs(raw)
                if not secrets.compare_digest((form.get("csrf") or [""])[0], csrf_token):
                    self._send_json({"error": "csrf"}, 403); return
                g1 = lambda k: (form.get(k) or [""])[0]
                st = _Stores(data_dir)
                try:
                    if path == "/wizard/sharpen":
                        from nooch_village.wizard import sharpen_outcome, board_anchors
                        _ankers = board_anchors(st.projects.all())   # eigen bord = stem van het team
                        self._send_json({"uitkomst": sharpen_outcome(g1("ruw"), anchors=_ankers)})
                        return
                    if path == "/wizard/impact":
                        # Een GOK voor moeite en impact, bedoeld om in één tik bij te stellen.
                        # Fail-soft: geen model = een leeg antwoord, en de chips blijven leeg.
                        from nooch_village.wizard import guess_impact
                        self._send_json(guess_impact(g1("idee"), rol=g1("role")))
                        return
                    if path == "/wizard/rollen":
                        # GEGROND, niet geraden: de match komt uit de effectieve skillset van een
                        # WAKKERE rol tegen de skill die de planner al aan een stap hing. Daarom
                        # werkt dit ook zonder model — er valt niets te fantaseren, alleen op te
                        # zoeken. Geen stappen met een skill = een lege sectie, geen blokkade.
                        from nooch_village import skill_links
                        from nooch_village.wizard import roles_for
                        try:
                            _items = json.loads(g1("items") or "[]")
                        except ValueError:
                            _items = []
                        # Twee tredes: eerst de gratis skill-opzoeking, en alleen als die leeg
                        # is één begrensd modelrondje over de roster. De ladder komt via dezelfde
                        # ingang als elders (`llm_voorkeur`), zodat er geen tweede modelbeleid
                        # ontstaat. Fail-open: geen model → lege lijst → 'wijs zelf toe'.
                        try:
                            from nooch_village.llm_keuze import llm_voorkeur
                            _lad = llm_voorkeur(st, g1("role"), "rol_match")
                        except Exception:
                            _lad = None
                        self._send_json({"rollen": roles_for(
                            _items if isinstance(_items, list) else [],
                            records=st.records, ai=st.ai, skills_of=skill_links.effectief,
                            ladder=_lad)})
                        return
                    if path == "/wizard/plan":
                        from nooch_village.wizard import plan_items
                        from nooch_village import skill_links
                        from nooch_village.registry_factory import shared_registry
                        rec = st.records.get(g1("role"))
                        reg = shared_registry()
                        catalog = []
                        for nm in sorted(skill_links.effectief(rec, st.ai)):
                            sk = reg.get(nm)
                            if sk is not None:
                                catalog.append({"name": nm,
                                                "description": getattr(sk, "description", "") or "",
                                                "input": getattr(sk, "input_schema", "") or ""})
                        req = lambda nm: tuple(getattr(reg.get(nm), "required_payload", ()) or ())
                        goal = g1("uitkomst")
                        # Geheugen-eerst (zoals de daemon-planner): raadpleeg de kennislaag én eerder
                        # afgerond onderzoek vóór het plannen, zodat de wizard voortbouwt i.p.v.
                        # opnieuw verzamelt. Fail-soft: een lege/kapotte store → geen sectie.
                        kennis = ""
                        try:
                            from nooch_village.kennis_context import kennis_voor, kennis_blok
                            from nooch_village.deliverable_context import gather_deliverable_context
                            delen = []
                            try:
                                dblok = gather_deliverable_context(
                                    st.projects, goal, max_notes=5, max_chars=2000,
                                    store=st.deliverables) or ""
                            except Exception:
                                dblok = ""
                            if dblok:
                                delen.append("Eerder afgerond onderzoek in het dorp (gebruik dit; "
                                             "plan geen items die dit al beantwoordt):\n" + dblok)
                            kblok = kennis_blok(kennis_voor(st.dd, goal,
                                                            deadline=_WIZARD_KENNIS_BUDGET_S))
                            if kblok:
                                delen.append(kblok)
                            kennis = "\n\n".join(delen)
                        except Exception:
                            logging.getLogger("cockpit2.wizard").exception("geheugen-raadpleging faalde")
                        # ÉÉN MODELBELEID. Dit is dezelfde beslissing als `plan_checklist` in de
                        # daemon — welk werk er gebeurt — en een fout hier plant zich voort in elke
                        # stap die eruit volgt. Hij hoort dus op hetzelfde brein te draaien, via
                        # dezelfde ingang (`llm_voorkeur` → `ladder_voor`), niet op de dorpsladder
                        # omdat hij toevallig anders heet. Fail-soft: None = de dorpsladder.
                        try:
                            from nooch_village.llm_keuze import llm_voorkeur
                            _ladder = llm_voorkeur(st, g1("role"), "wizard_plan")
                        except Exception:
                            _ladder = None
                        items = plan_items(goal, catalog, required_of=req, kennis=kennis,
                                           ladder=_ladder, data_dir=data_dir)
                        self._send_json({"items": items})
                        return
                    # /wizard/create
                    role = g1("role")
                    orec = st.records.get(role)
                    if not role or (orec is not None and org.is_circle(orec)):
                        self._send_json({"error": "pick a valid role (not a circle)"}, 400); return
                    _deny = _role_gate(role, username, st)
                    if _deny:
                        self._send_json({"error": _deny}, 403); return
                    uitkomst = g1("uitkomst").strip()
                    if not uitkomst:
                        self._send_json({"error": "geen uitkomst"}, 400); return
                    person, agent = _parse_trekker(g1("trekker"))
                    missie = g1("missie") if g1("missie") in _MISSIE_IMPACT else ""
                    business = g1("business") if g1("business") in _BUSINESS_IMPACT else ""
                    effort = g1("tijd") if g1("tijd") in _EFFORT else ""
                    # Kort = de titel (scope), uitgebreid = de DoD (done_when + kop van het einddocument).
                    from nooch_village.wizard import title_from
                    from nooch_village.projects import seed_document
                    titel = title_from(uitkomst) or uitkomst[:80]
                    pj = st.projects
                    pid = pj.create(role, titel[:200], "human", status="queued",
                                    done_when=uitkomst, person=person or None,
                                    agent=agent or None, missie_impact=missie,
                                    business_impact=business, effort=effort)
                    # Seed het levende einddocument met de DoD als kop. Vanaf hier is de projectpoort
                    # doc-gedreven: Done kan pas als het document van deze seed afwijkt (echt antwoord).
                    try:
                        ds = getattr(st, "project_docs", None)
                        if ds is not None:
                            ds.write(pid, seed_document(uitkomst))
                    except Exception:
                        logging.getLogger("cockpit2.wizard").exception("einddoc-seed faalde (pid=%s)", pid)
                    try:
                        items = json.loads(g1("items") or "[]")
                    except ValueError:
                        items = []
                    if isinstance(items, list) and items:
                        cl = pj.checklist_add(pid, title=PREP_CHECKLIST_TITLE)
                        if cl is not None:
                            for it in items:
                                if not isinstance(it, dict) or not (it.get("tekst") or "").strip():
                                    continue
                                pj.check_add(pid, cl["id"], it["tekst"],
                                             skill=(it.get("skill") or None),
                                             payload=(it.get("payload") if isinstance(it.get("payload"), dict) else None),
                                             payload_ok=bool(it.get("ok", True)))
                    # TAKEN NAAR ROLLEN, pas nu — het project moet eerst bestaan, anders heeft
                    # de taak niets om naar terug te wijzen en kan de lus niet sluiten.
                    actor = st.people.by_email(username) if username and username != "guest" else None
                    aid = actor.id if actor else ""
                    taken_ref = []
                    try:
                        taken = json.loads(g1("taken") or "[]")
                    except ValueError:
                        taken = []
                    for t in (taken if isinstance(taken, list) else []):
                        if not isinstance(t, dict):
                            continue
                        t_rol = str(t.get("rol") or "").strip()
                        t_tekst = str(t.get("tekst") or "").strip()
                        if not t_rol or not t_tekst:
                            continue
                        trec = st.records.get(t_rol)
                        if trec is None or org.is_circle(trec) or getattr(trec, "slaapt", False) \
                                or getattr(trec, "archived", False):
                            continue          # fail-closed: geen werk naar een rol die stilstaat
                        _s, _ref = route_werk(st, tekst=t_tekst, rol=t_rol,
                                              herkomst=f"↳ gevraagd bij het aanmaken van {titel}",
                                              door=aid, opdrachtgever=aid, bron_project=pid)
                        taken_ref.append({"rol": t_rol, "ref": _ref})
                    # WERKT DE SUGGESTIE EIGENLIJK? Eén regel per project, dom geteld, zodat
                    # kill-of-houden over een week op een getal gaat en niet op een gevoel.
                    # Fail-soft: meten mag een aanmaak nooit blokkeren.
                    try:
                        from nooch_village.checklist_vorm import noteer_acceptatie
                        _int = lambda k: int(g1(k) or 0) if (g1(k) or "0").isdigit() else 0
                        noteer_acceptatie(data_dir, aangeboden=_int("sug_aan"),
                                          overgenomen=_int("sug_over"), eigen=_int("sug_eigen"),
                                          pid=pid)
                    except Exception:
                        logging.getLogger("cockpit2.wizard").exception("acceptatie-spoor faalde")
                    self._send_json({"pid": pid, "url": f"/project?pid={pid}", "titel": titel,
                                     "taken": taken_ref})
                    return
                except Exception as e:
                    logging.getLogger("cockpit2.wizard").exception("wizard-endpoint %s faalde", path)
                    self._send_json({"error": str(e)}, 500)
                    return

            if path == "/claims/scan":
                # AUTHZ: iedereen-ingelogd — lezen/scannen is vrij; muteren blijft compliance.
                # De URL wordt SERVER-side opgehaald (safe_fetch, met SSRF-guardrail), niet door de
                # browser via een publieke proxy — die proxies zijn rate-limited of betaald.
                username = self._session_username()
                if sessions is not None and username is None:
                    self._send("Not logged in", 403); return
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                form = urllib.parse.parse_qs(raw)
                if not secrets.compare_digest((form.get("csrf") or [""])[0], csrf_token):
                    self._send("CSRF token invalid", 403); return
                st = _Stores(data_dir)
                uitslag, bron = _claims_scan(form, data_dir)
                markten = [m for m in (form.get("markt") or []) if m]
                frag = render_rapport(uitslag, markten=markten, bron=bron,
                                      csrf_token=csrf_token,
                                      kan_bord=_claims_gate_open(st, username),
                                      db=_claims_db_stil(data_dir))
                if (form.get("frag") or [""])[0] == "1":
                    self._send(frag, chrome=False)           # live scan: alleen het rapport terug
                else:                                        # zonder JS: de hele pagina mét rapport
                    self._send(render_claims(csrf_token=csrf_token, tab="check",
                                             kan_cureren=_claims_gate_open(st, username),
                                             url=(form.get("url") or [""])[0],
                                             tekst=(form.get("tekst") or [""])[0],
                                             markten=markten, rapport=frag, data_dir=data_dir))
                return

            if path == "/wachtwoord":
                # AUTHZ: circle-member of iedereen-ingelogd — eigen wachtwoord wijzigen (self + geforceerd)
                username = self._session_username()
                if sessions is not None and username is None:
                    self._redirect_to("/login"); return
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                form = urllib.parse.parse_qs(raw)
                ok, page = _password_change(data_dir, form, username)
                if ok:
                    if sessions is not None:      # haak: verbreek oude sessies, behoud de eigen (no-op nu)
                        sessions.invalidate_user(username, keep_token=_auth.get_session_token(self.headers))
                    self._redirect_to((form.get("next") or ["/"])[0] or "/")
                else:
                    self._send(page, 200)
                return

            if path != "/action":
                self._send("<p>404</p>", 404); return

            # ── Sessie-check voor alle /action POSTs ────────────────────────
            username = self._session_username()
            if sessions is not None and username is None:
                self._send("Not logged in", 403); return
            # Bestand-upload (multipart): apart afhandelen; bestand wegschrijven + registreren.
            if ctype.startswith("multipart/form-data") and "boundary=" in ctype:
                # nginx capt de body op 25M (413 vóór de app); de app-limiet ligt bewust lager (20M) zodat
                # de app zelf de nette fout geeft voor bestanden tussen de app-limiet en de nginx-cap.
                raw = self.rfile.read(length) if length else b""
                boundary = ctype.split("boundary=", 1)[1].strip().strip('"')
                fields, files = _parse_multipart(raw, boundary)
                if not secrets.compare_digest(fields.get("csrf", ""), csrf_token):
                    self._send("CSRF token invalid", 403); return
                if fields.get("action") == "attach_file":
                    err = _upload_error(files, _upload_max_bytes())
                    if err:                                  # te groot / geen bestand → expliciete fout, geen no-op
                        self._send(err[0], err[1]); return
                    fname, blob = files["file"]
                    pid = fields.get("pid", "")
                    safe = os.path.basename(fname).replace("\\", "_")[:120]
                    rel = os.path.join("attachments", pid, uuid.uuid4().hex[:8] + "_" + safe)
                    full = os.path.join(data_dir, rel)
                    os.makedirs(os.path.dirname(full), exist_ok=True)
                    with open(full, "wb") as fh:
                        fh.write(blob)
                    _Stores(data_dir).projects.attach_file(pid, safe, rel)
                    self._redirect(fields.get("next", "/"), "📎 bijlage geupload"); return
                if fields.get("action") == "kb_atoom_ref_pdf":
                    # AUTHZ: iedereen-ingelogd — kennisbank. Een PDF als bronlink bij een atoom.
                    # Statements-herontwerp: de PDF wordt óók bewaard (data/kbref/) en reference
                    # wordt het geserveerde pad (/kbref/…) — zo opent de Bron-link in het detail
                    # het document zelf. Oudere references (kale document-labels) blijven geldig
                    # en renderen als tekst (fail-soft).
                    err = _upload_error(files, _upload_max_bytes())
                    if err:
                        self._send(err[0], err[1]); return
                    fname, blob = files["file"]
                    nxt = fields.get("next", "/kennisbank")
                    kbref_pad = _save_kbref_pdf(data_dir, fname, blob)
                    _notes = _Stores(data_dir).notes
                    ok = _notes.set_reference(fields.get("atom_id", ""), kbref_pad)
                    # Bron-propagatie (founder dd 2026-07-18): zelfde genormaliseerde
                    # bron zonder reference → krijgt dezelfde PDF-link mee.
                    extra = _notes.propagate_reference(fields.get("atom_id", "")) if ok else 0
                    msg = ("🔗 PDF linked as a source link"
                           + (f" — also set on {extra} other card(s) with the same source"
                              if extra else "")) if ok else "✗ note not found"
                    self._redirect(nxt, msg)
                    return
                if fields.get("action") == "kb_intake_pdf":
                    # AUTHZ: iedereen-ingelogd — kennisbank-intake. PDF = source-adapter:
                    # tekst-extractie + chunken, elke chunk door de bestaande atomiser
                    # (ledger per chunk → her-uploaden idempotent; een gefaalde chunk
                    # komt bij een volgende upload vanzelf terug).
                    err = _upload_error(files, _upload_max_bytes())
                    if err:
                        self._send(err[0], err[1]); return
                    from nooch_village.kennisbank_sources import van_pdf
                    fname, blob = files["file"]
                    chunks = van_pdf(blob, os.path.basename(fname))
                    if chunks is None:
                        self._redirect(fields.get("next", "/kennisbank"),
                                       "✗ no text layer found in this PDF (a scan? "
                                       "OCR is out of scope for v1)"); return
                    nieuw_alles: list[str] = []
                    dubbel_alles = mislukt = 0
                    for chunk_raw, label in chunks:
                        uitkomst = kb_intake(chunk_raw, label, data_dir)
                        if uitkomst is None:
                            mislukt += 1
                            continue
                        _nieuw, _dubbel = uitkomst
                        nieuw_alles.extend(_nieuw)
                        dubbel_alles += _dubbel
                    delen = [f"✂️ {len(nieuw_alles)} notities uit {len(chunks)} delen"]
                    if dubbel_alles:
                        delen.append(f"{dubbel_alles} al bekend")
                    if mislukt:
                        delen.append(f"{mislukt} deel/delen mislukt — upload nogmaals "
                                     f"voor de rest (niets raakt dubbel)")
                    nxt = "/kennisbank" + (f"?nieuw={','.join(nieuw_alles)}" if nieuw_alles else "")
                    self._redirect(nxt, " · ".join(delen)); return
                if fields.get("action") == "kb_bron_add":
                    # AUTHZ: iedereen-ingelogd — kennisbank zone 2. Eén ingang: tekst OF bestand →
                    # auto-detect → adapter → atomiser → STAGING-batch (niet direct de bibliotheek;
                    # de mens kijkt na op /kennisbank/staging).
                    from nooch_village.kennisbank_sources import (bron_reference,
                                                                  detect_and_extract)
                    from nooch_village.kennisbank_intake import atomiseer
                    username = self._session_username()
                    fname, blob = files.get("file", ("", b""))
                    res = detect_and_extract(text=fields.get("bron_text", ""),
                                             filename=fname if blob else "", data=blob)
                    if res["chunks"] is None:
                        self._redirect("/kennisbank?open=bron",
                                       f"✗ {res.get('error') or 'niets herkend'}"); return
                    stores = _Stores(data_dir)
                    atoms: list[dict] = []
                    label = res["chunks"][0][1]
                    mislukt = 0
                    # Atomiciteit-bovengrens per document (fix-brief bug 2): een lang stuk of een
                    # referentielijst mag niet in tientallen mini-kaartjes ontploffen. Zodra de cap
                    # gehaald is stoppen we met verdere chunks — de mens ziet in de staging wat er is.
                    _DOC_CAP = 40
                    for craw, clabel in res["chunks"]:
                        got = atomiseer(craw, clabel, tabular=res["tabular"])
                        if got is None:
                            mislukt += 1
                            continue
                        atoms += got
                        label = clabel
                        if len(atoms) >= _DOC_CAP:
                            atoms = atoms[:_DOC_CAP]
                            break
                    if not atoms:
                        self._redirect("/kennisbank?open=bron",
                                       "✗ the atomiser returned nothing usable"); return
                    # Founder 19 jul: de link of PDF die bij het aanmaken is GEBRUIKT wordt
                    # de reference van alle kaartjes — een geplakte URL, of de bewaarde
                    # bron-PDF (data/kbref/, zelfde recept als kb_atoom_ref_pdf). Die wint
                    # van een LLM-overgetypte DOI (kan doodlopen); alleen bij geplakte
                    # tekst blijft de atomiser-reference staan.
                    kbref_pad = ""
                    if blob and (fname or "").lower().endswith(".pdf"):
                        kbref_pad = _save_kbref_pdf(data_dir, fname, blob)
                    echte_bron = bron_reference(fields.get("bron_text", ""), kbref_pad)
                    if echte_bron:
                        for a in atoms:
                            a["reference"] = echte_bron
                    bid = stores.staging.create(res["kind"], label, atoms,
                                                tabular=res["tabular"],
                                                by=(username if username != "guest" else ""))
                    extra = f" · {mislukt} deel/delen mislukt" if mislukt else ""
                    self._redirect(f"/kennisbank/staging?batch={bid}",
                                   f"✂️ {len(atoms)} voorstellen uit {res['kind']} — even nakijken{extra}")
                    return
                self._redirect(fields.get("next", "/"), ""); return
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            form = urllib.parse.parse_qs(raw)
            token = (form.get("csrf") or [""])[0]
            if not secrets.compare_digest(token, csrf_token):
                self._send("CSRF token invalid", 403); return
            action = (form.get("action") or [""])[0]
            # person_add: rendert een pagina die het tijdelijke wachtwoord éénmalig toont
            # (niet via redirect, zodat het wachtwoord niet in de URL/history belandt).
            if action == "person_add":
                self._send(*_handle_person_add(data_dir, form, username=username))
                return
            if action == "person_reset_password":
                self._send(*_handle_person_reset(data_dir, form, username=username))
                return
            if action == "lk_mute":
                # AJAX-actie vanuit de call bar: geen full-page redirect (de bar blijft staan),
                # alleen een korte 200 met de bevestiging. Business-logica leeft in de dispatch-tak.
                _, msg = dispatch(data_dir, action, form, username=username)
                self._send(msg or "ok", 200)
                return
            try:
                nxt, msg = dispatch(data_dir, action, form, username=username)
            except Forbidden as e:
                self._send(str(e), 403); return    # geweigerde artefact-mutatie → echte 403 + reden
            self._redirect(nxt, msg)

        def log_message(self, *_):
            pass
    return H


def serve(host: str = "127.0.0.1", port: int = 8766, data_dir: str | None = None) -> None:
    if host not in _LOCAL_HOSTS:
        raise SystemExit(f"Cockpit 2 weigert niet-lokale host '{host}'.")
    dd = data_dir or _default_data_dir()
    _load_env()   # LLM-keys beschikbaar maken voor 'AI praat mee'
    _bootstrap(dd)
    csrf_token = secrets.token_urlsafe(32)
    users    = _auth.UserStore(os.path.join(dd, "people.json"))
    sessions = _auth.SessionStore()
    _Stores(dd).people.backfill_must_change()   # markeer uitstaande temps 'moet wijzigen' (idempotent)
    httpd = ThreadingHTTPServer((host, port), make_handler(dd, csrf_token, sessions, users))
    httpd.daemon_threads = True
    print(f"Cockpit 2 (GlassFrog shape, PoC) at http://{host}:{port}  —  Ctrl-C to stop")
    print(f"Dataset: {dd}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nCockpit 2 stopped.")
    finally:
        httpd.server_close()


def _match_ladder() -> str:
    """Eén werkende, lokaal beschikbare trede voor de matcher. Default Anthropic (Gemini vereist
    google-generativeai). Override via env LLM_MATCH_LADDER (bijv. 'mistral')."""
    return os.getenv("LLM_MATCH_LADDER", "anthropic")


def _save_kbref_pdf(data_dir: str, fname: str, blob: bytes) -> str:
    """Bewaar een bron-PDF in data/kbref/ en geef het geserveerde pad (/kbref/…) terug —
    de ene plek voor dit opslag-recept (kb_atoom_ref_pdf én kb_bron_add gebruiken hem)."""
    safe = os.path.basename(fname).replace("\\", "_")[:120]
    if not safe.lower().endswith(".pdf"):
        safe += ".pdf"
    stored = uuid.uuid4().hex[:8] + "_" + safe
    full = os.path.join(data_dir, "kbref", stored)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as fh:
        fh.write(blob)
    return "/kbref/" + stored


def _upload_max_bytes() -> int:
    """Max upload-grootte in bytes (config-key upload_max_bytes, default 20M). BEWUST onder de nginx-cap
    (25M) zodat de app zelf de nette fout kan geven i.p.v. nginx (413). Accepteert '20M'/'20MB'/bytes."""
    raw = (os.getenv("upload_max_bytes", "") or "").strip().upper()
    if not raw:
        return 20 * 1024 * 1024
    try:
        if raw.endswith("MB"):
            return int(raw[:-2]) * 1024 * 1024
        if raw.endswith("M"):
            return int(raw[:-1]) * 1024 * 1024
        return int(raw)
    except ValueError:
        return 20 * 1024 * 1024


def _upload_error(files: dict, limit: int):
    """Valideer een multipart-upload vóór wegschrijven. Geeft (melding, http-status) bij een probleem,
    anders None. Vervangt de oude stille no-op: een ontbrekend/leeg bestand of een te groot bestand
    levert nu een expliciete fout i.p.v. een lege redirect."""
    fname, blob = (files.get("file") or ("", b""))
    if not (fname and blob):
        return ("No file selected", 400)
    if len(blob) > limit:
        return (f"Bestand te groot (max {limit // (1024 * 1024)} MB)", 413)
    return None


from nooch_village.views.roloverleg import (
    _rov_kindlabel, _rov_children, _rov_items, _rov_open,
    _rov_groups, _rov_initials, _rov_add_item, _rov_hard,
    _rov_signals, _rov_dupes, _rov_apply,
    _rov_draft, _rov_snapshot, _rov_save_draft,
    _rov_member_block, _rov_editor,
    render_roloverleg2,
)


def _load_env() -> None:
    """Laad project-.env in os.environ (idempotent, setdefault), zodat de losse cockpit2-CLI
    dezelfde LLM-keys ziet als de volledige village. Zoekt .env in cwd en repo-root."""
    import pathlib
    seen = set()
    for cand in (os.path.join(os.getcwd(), ".env"),
                 os.path.join(pathlib.Path(__file__).resolve().parent.parent, ".env")):
        if cand in seen or not os.path.exists(cand):
            continue
        seen.add(cand)
        for line in open(cand):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def refresh_matches(data_dir: str | None = None, ask=None, progress=None) -> int:
    """Achtergrond-pas: laat de LLM per (accountability, skill) oordelen en cache het, zodat het
    cadeautje semantisch matcht. Zonder key/`ask` is dit een no-op (fail-closed); de render valt
    dan terug op lexicaal + concept. `ask` is injecteerbaar voor tests."""
    dd = data_dir or _default_data_dir()
    _bootstrap(dd)
    st = _Stores(dd)
    if ask is None:
        try:
            from nooch_village import llm
        except Exception:
            return 0

        def ask(acc: str, skill: str):
            prompt = ("Ondersteunt de vaardigheid een verantwoordelijkheid? Antwoord met enkel "
                      f"'ja' of 'nee'.\nVerantwoordelijkheid: {acc}\nVaardigheid: {skill}")
            out = llm.reason(prompt, ladder=_match_ladder(), call_site="cockpit_match_pair")
            if not out:
                return None
            o = out.strip().lower()
            if o.startswith("ja") or o.startswith("yes"):
                return True
            if o.startswith("nee") or o.startswith("no"):
                return False
            return None

    skills = sorted({s for p in st.personas.all() for s in (p.skills or [])})
    accs = sorted({a for r in st.records.all() if not org.is_circle(r)
                   for a in (r.definition.accountabilities or [])})
    pairs = [(a, s) for a in accs for s in skills]
    return ai_match.refresh_semantic(pairs, ask, st.match, skip_cached=True, progress=progress)


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="nooch_village.cockpit2")
    ap.add_argument("cmd", nargs="?", default="serve", choices=["serve", "match"],
                    help="serve = cockpit; match = achtergrond semantische matcher vullen")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--data-dir", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "match":
        _load_env()   # zorg dat .env-keys beschikbaar zijn voor de losse CLI
        # Snelle key-check: zonder LLM-key heeft de achtergrond-pas niets te doen.
        try:
            from nooch_village import llm
            has_key = bool(llm.reason("antwoord met 'ok'", ladder=_match_ladder(), call_site="cockpit_match_keycheck"))
        except Exception:
            has_key = False
        if not has_key:
            print("No working LLM key found. The matcher already runs on lexical + concept "
                  "(code ~ feature, bug ~ testscript); the semantic layer only adds something "
                  "with an Anthropic or Gemini key in .env. Nothing to do.")
            return

        def progress(i, total, acc, skill):
            print(f"  [{i}/{total}] {acc[:40]} ↔ {skill[:30]}", flush=True)

        print("Semantic matcher: fetching verdicts (already-cached pairs are skipped)…",
              flush=True)
        n = refresh_matches(a.data_dir, progress=progress)
        print(f"Done: {n} new pairs determined and cached.")
        return
    serve(host=a.host, port=a.port, data_dir=a.data_dir)


if __name__ == "__main__":
    main()
