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
    _created_full, _ic, _bron_html, _stamp, _md, _md_naar_bron, _parse_multipart,
    _link_host, _psec, _ICON_ADD_EMOJI, _person_name, _footer, _NU_LINK, _DS_LINK,
    _SIDE_CIRCLE, _SIDE_OVERLEG, _initials,
    _IC_CHECK, _IC_INFO, _IC_CHAT, _IC_LINK, _IC_DL,
    _IC_DESC, _IC_CLOCK, _IC_FILE, _IC_TARGET,
)
from nooch_village.views.feed import (
    _feed_norm, _feed_who, _mentionables, _mentions_in,
    _hilite_mentions, _feed_entry_html, _feed_author_options,
    _wall_outcome_opts,
)
from nooch_village import channels
from nooch_village.governance import Records
from nooch_village import acc_ids, skill_meta, skill_links
from nooch_village.skill_links import SkillLinkKroniek
from nooch_village.people import PeopleStore
from nooch_village.assignments import Assignments
from nooch_village.attachments import AttachmentStore, ARTEFACT_KINDS, body_cap
from nooch_village.observations import ObservationStore
from nooch_village import observations
from nooch_village.evidence_ledger import EvidenceLedger
from nooch_village.source_status import SourceStatusStore
from nooch_village.collector import migrate_data_sources
from nooch_village import artefacts
from nooch_village.artefacts import can_write_artefact, requires_governance_ref
from nooch_village.personas import PersonaStore
from nooch_village.projects import (BEHAALD, NIET_BEHAALD, ProjectLedger, PREP_CHECKLIST_TITLE, uitvoerlijst, _MISSIE_IMPACT,
                                    _BUSINESS_IMPACT)
from nooch_village.deliverable_store import DeliverableStore
from nooch_village.channels import ChannelStore
from nooch_village.project_doc_store import ProjectDocStore
from nooch_village.radar_store import RadarStore
from nooch_village.registry_factory import shared_registry
from functools import lru_cache
from nooch_village.skill_match import plan_offers


@lru_cache(maxsize=4)
def _context_of(_dd: str):
    """De dorpscontext (settings, koppelingen, rugzakken) vanuit het COCKPIT-proces.

    Waarom dit nodig is: het cockpit heeft geen Inwoner en dus geen `self.context`, en juist daardoor
    las `plan_offers` alleen het rol-DNA. Zonder rugzak zag de matcher `web_zoek` niet, en kreeg een
    mens-getypt item "no skill · needs a human" terwijl het gereedschap er lag.

    Gecachet op de datamap: `load_context` leest drie bestanden van schijf en dat hoeft niet bij elke
    toetsaanslag. Wijzig je `config/rugzakken.json`, dan pakt het cockpit dat op na een herstart —
    hetzelfde als bij `shared_registry` hierboven, en rugzakken wijzigen is geen dagelijks werk.

    Fail-soft: lukt het laden niet, dan None, en dan gedraagt de matcher zich als voorheen (alleen
    DNA). Een cockpit dat niet opstart omdat een configbestand scheef staat is erger dan een matcher
    die een rugzak mist."""
    try:
        from nooch_village.config import load_context
        return load_context(os.path.dirname(os.path.abspath(_dd.rstrip("/"))))
    except Exception:                                     # noqa: BLE001
        logging.getLogger("cockpit2.context").debug("dorpscontext niet geladen", exc_info=True)
        return None
from nooch_village.util import refuse
from nooch_village.ai_tasks import AITaskStore, KIND_MIDDEL
from nooch_village import skill_labels
from nooch_village.checklists import ChecklistStore, CADENCES, CADENCE_LABEL
from nooch_village.metrics import MetricStore, window_cutoff, filter_samples
from nooch_village.kennisbank import (KennisbankStore, parse_blok,
                                      field as kb_field, verdict as kb_verdict,
                                      WORD_LABEL as KB_WORD_LABEL,
                                      load_atoms as kb_load_atoms)
from nooch_village.insight import Insight
from nooch_village.metric_schema import (CADANS_LABEL, MEETTYPE_LABEL, MEETWIJZE_LABEL,
                                         TIJD_LABEL, BRUIKBAAR_LABEL, VERIFICATIE_LABEL)
from nooch_village.definitions import (DefinitionStore, seed_catalog as _seed_catalog,
                                       reground_seed as _reground_seed,
                                       migrate_definitions as _migrate_definitions)
from nooch_village.cockpit2_util import _BUILD, _EXTRA_CSS, _CIRCLE_TABS, _ROLE_TABS, WEBSITE_DEVELOPER_ROLE
from nooch_village.doelen import DoelStore
from nooch_village.noochie import NoochieStore
from nooch_village.roloverleg import Agenda
from nooch_village.werkoverleg import WerkoverlegStore, STEPS as _WO_STEPS
from nooch_village.strategy_store import StrategyStore
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
        # De gespreklaag (fase 8): cirkel- en DM-kanalen wonen hier, project-kanalen
        # lopen via de ledger. Zie channels.py voor waarom dat twee plekken zijn.
        self.channels = ChannelStore(os.path.join(dd, "channels.json"), ledger=self.projects)
        self.agenda = Agenda(os.path.join(dd, "roloverleg_agenda.json"))
        self.noochie = NoochieStore(os.path.join(dd, "noochie.json"))
        self.checklists = ChecklistStore(os.path.join(dd, "checklists.json"))
        self.metrics = MetricStore(os.path.join(dd, "metrics.json"))
        self.defs = DefinitionStore(os.path.join(dd, "definitions.json"))
        self.werk = WerkoverlegStore(os.path.join(dd, "werkoverleg.json"))
        self.strategies = StrategyStore(os.path.join(dd, "strategies.json"))
        self.doelen = DoelStore(os.path.join(dd, "doelen.json"))          # Doelen: waar het werk naartoe gaat (doelen.py)
        # Welke rollen bewust meetellen in de copy-prompt-stack van een andere rol. Erfenis loopt
        # omhoog; een zusterrol insluiten is een besluit en staat daarom vastgelegd.
        self.copy_stack = CopyStackConfig(os.path.join(dd, "copy_stack.json"))
        self.radar = RadarStore(os.path.join(dd, "radar.json"))   # Radar-tool: gecureerde Inoreader-signalen per rol
        # Wat de founder met een opkomend onderwerp deed (project of watch). Geen oordeel-label:
        # clustering is berekend, de projectkeuze is strategie — zie radar_clusters.
        self.kennisbank = KennisbankStore(os.path.join(dd, "kennisbank.json"))   # laag 2: geversioneerde inzichten
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
    # Zelfde reden, andere tool: de Decision Coach hangt onder de rol die het besluit-domein houdt,
    # zodat hij vindbaar is voor wie die rol opent. Idempotent; fail-soft.
    try:
        from nooch_village.views.decision_coach import zorg_voor_tool as _dc_tool
        _dc_tool(st.records, st.att)
    except Exception as _e:                              # noqa: BLE001
        logging.getLogger("village.cockpit").warning("decision-coach-tool niet gekoppeld: %s", _e)
    # Grafstenen van #271 intrekken: notificaties die de bug "[rol X onbemand]" uitzond terwijl de
    # rol gewoon bemand was. Idempotent; items van ná de fix blijven staan (dat zou een regressie
    # zijn, geen grafsteen). Fail-soft — opruimen mag de cockpit nooit ophouden.
    # HIER STOND `notif_opruiming.archiveer_stale_onbemand`: die trok "[rol X onbemand]"-meldingen
    # in zodra de rol wél bemand bleek. Een pleister op een bug die al gefixt was — zie de les in
    # CLAUDE.md, "een fix hoort zijn eigen notificaties in te trekken". De store waar hij in
    # opruimde bestaat niet meer, dus de pleister ook niet. Het onderliggende gat (een emissie die
    # weet uit welke regel hij voortkomt) is nog steeds niet gedicht; dat staat in CLAUDE.md.
    # HIER STOND DE HAAK BIJ HET ONTSTAAN (`spanning_ontstaat.maak_verrijker`): elke nieuwe
    # spanning kreeg meteen een bevinding in gewone taal en een type. Die haak hing aan
    # `NotifStore.add` en had twee afnemers — de inbox-routering (het type) en `views/inbox._regel`
    # (de herschreven zin). Allebei zijn ze in B2 verdwenen, dus de haak schreef vanaf dat moment
    # een antwoord dat niemand meer las: een LLM-call per melding, in het niets.
    #
    # `bevinding.py` en `zelf_verwerking.py` staan er NOG WEL. Ik had ze eerst meeverwijderd, en dat
    # was fout: ze hebben eigen aanroepers buiten de poort (`founder_kaart`, `wiki`, `cli` en deze
    # module; `villageraad` was er de vijfde, tot die op 20 september 2026 zelf wegging). Alleen de
    # HAAK is weg, niet het gereedschap eronder.
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
    _acc_row, _overview_html, _fillsummary,
    _fillers_block, _role_row, _roles_html,
    _members_html, _att_html,
    render_node, render_person, render_admin,
    render_rolefillers, render_middelen,
    _CORE_ROLE_NAMES, _ICON_ADD_PERSON,
)


from nooch_village.views.projects import (
    _proj_chip, _trekker_html, _trekker_options,
    _proj_progress, _due_overdue, _progress_badge,
    _scope_text, _proj_card, _quickadd,
    _columns_html, _drag_script,
    _modal_html, _group_meta, _projects_board,
    _archived_html, _projects_tab_html, render_projects_screen,
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
from nooch_village.views.metrics2 import render_metrics2
from nooch_village.views.bronnen import render_bronnen
from nooch_village.views.skills import render_skills
from nooch_village.views.site_audit import render_site_audit
from nooch_village.views.doelen import render_goals, render_goal
from nooch_village.views.search import (mention_hits, render_search,
                                        render_search_fragment)
from nooch_village.views.claims import render_claims, render_rapport, rol_voor
from nooch_village import founder_kaart as _founder_kaart
from nooch_village.copy_stack import StackConfig as CopyStackConfig
from nooch_village import decision_coach
from nooch_village.views.copy_prompt import render_copy_prompt
from nooch_village.views.decision_coach import render_decision_coach
from nooch_village.views.copy_check import render_copy_check
from nooch_village.views.wiki import render_wiki_index, render_pagina
from nooch_village.views.messages import render_messages
from nooch_village.views.rapport import render_projectrapport
from nooch_village.views.woordenschat import render_woordenschat
from nooch_village.views.keyword_lens import render_keyword_lens
from nooch_village.library import Library
from nooch_village.keyword_nominations import (NominationQueue, NominationKroniek, valid_reason)


from nooch_village.views.noochie import (
    _noochie_suggest, _noochie_reply,
    render_noochie, _noochie_chrome,
)

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
        return (f"Your accountabilities:\n{acc_txt}\n"
                f"Your skills (the ONLY concrete tools you have):\n{sk_txt}\n")
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
    rol_line = (f"Role: {_name(role)} — purpose: {role.definition.purpose}\n" if role is not None else "")
    capab = _role_capabilities_block(role)          # accountabilities + skills → grondslag voor de toets
    aanleiding = (prefix.strip() + "\n\n") if (prefix or "").strip() else ""
    ctx = (f"{aanleiding}"
           f"Project: {_scope_text(p)}\n"
           f"Description: {p.get('description', '') or '(none)'}\n"
           f"{rol_line}"
           f"{capab}"
           f"Recent dialogue:\n{recent or '(still empty)'}\n\n"
           "Triage this signal against YOUR accountabilities and skills. Answer three things:\n"
           "1. Does it fit your role? (yes / partly / no — if partly or no: which piece CAN you take on)\n"
           "2. Can you answer it NOW purely from what you already know (sharing information), without "
           "running a skill or starting a project? If so: give that answer.\n"
           "3. If it cannot be done directly (a skill or several steps are needed), say briefly that you "
           "handle it via your inbox. Invent nothing and never claim you did something you did not.\n\n"
           "Answer ONLY with JSON, exactly this schema: {\"fit\": \"yes|partly|no\", \"welk_stuk\": "
           "\"<if partly/no: which part you CAN do, otherwise empty>\", \"kan_direct\": true or false, "
           "\"reactie\": \"<if kan_direct=true your information answer; otherwise a short reply/refusal, "
           "max 4 sentences>\"}.")
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
        offers = plan_offers(role, [ask_text], shared_registry(), name=_name(role),
                             context=_context_of(st.dd))
    except Exception:
        return None
    return offers[0] if offers else None


def _signaleer(st: _Stores, doel_type: str, doel_id: str, tekst: str, *,
               by: str = "village", herkomst: dict | None = None) -> str:
    """Eén signalering naar de mens die hem aangaat, als DM. Geeft het bericht-id (of "").

    DIT VERVANGT `st.notif.add`. Sinds 20 september 2026 is er geen wachtrij meer met een
    verwerkingsmodel; een signalering is een bericht en de ontvanger is verantwoordelijk, zoals bij
    elk ander bericht. De routering (persoon / rolvervuller / terugval) staat in `signaal.py`, en is
    dezelfde die de 371 bestaande rijen heeft gemigreerd — twee kopieën zouden betekenen dat
    dezelfde rol-id vandaag bij de een landt en morgen bij de ander.

    Fail-closed op de tekst (leeg = geen bericht), fail-OPEN op het doel: is er geen ontvanger te
    bepalen, dan gaat het naar de terugval-rol. Een signalering die nergens landt is stiller dan
    geen signalering, want de afzender denkt dat hij iets heeft gedaan."""
    from nooch_village import signaal
    tekst = " ".join(str(tekst or "").split())
    if not tekst:
        return ""
    try:
        kanalen = signaal.stuur(st, doel_type, doel_id, tekst, by=by, herkomst=herkomst)
    except Exception:
        logging.getLogger("cockpit2.signaal").exception("signalering faalde: %s/%s",
                                                        doel_type, doel_id)
        return ""
    if not kanalen:
        return ""
    laatste = st.channels.laatste(kanalen[0]) or {}
    return str(laatste.get("id") or "")


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
    # GEDRAGSWIJZIGING, 20 september 2026. Dit zette vroeger een inbox-item neer en markeerde het
    # meteen als "verwerkt" wanneer de rol het zelf had opgepakt. Zo'n item was per definitie werk
    # dat al gedaan was — precies de ruis waarover Stefan zei: "alles wat tot dusver in de inbox is
    # gekomen kon ik niet echt veel mee". Zonder verwerkingsmodel is er geen plek meer om "al
    # gedaan" in te zetten, en een bericht sturen over werk dat af is, is geen bericht maar een log.
    # Dus: `processed=True` stuurt niets meer, `processed=False` stuurt een DM naar de mens.
    if processed:
        return None
    bid = _signaleer(st, "role", rid, ask_text or "", by=_name(role),
                     herkomst={"project": pid} if pid else None)
    return {"id": bid} if bid else None


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
    # LIBERAAL PARSEN, ZOALS project_worker. De prompt vraagt sinds 06-09-2026 Engelse enum-waarden
    # (yes|partly|no), maar een model dat in het Nederlands doorschiet mag de triage niet stilzetten:
    # bij None valt de caller terug op een platte reactie, en dan verdwijnt de triage geruisloos.
    # De INTERNE waarden blijven Nederlands, want daar hangt de rest van deze module op (fit == "nee").
    _FIT = {"yes": "ja", "partly": "deels", "no": "nee", "ja": "ja", "deels": "deels", "nee": "nee"}
    fit = _FIT.get(str(data.get("fit", "")).strip().lower(), "")
    if not fit:
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
# De copywriter-rol stond hier tot 18 sept 2026 en is opgeheven zonder opvolger; een gereedschap
# aanbieden op een gearchiveerde rol levert een kaart op die niemand ooit ziet.
_COPY_PROMPT_ROLLEN = ("mother_earth__nooch__community_and_email",)

# Welke bronnen een schrijvende rol bij oprichting bewust meekrijgt. Rol-ids in code zijn hier
# onvermijdelijk: een inclusie IS een besluit, en een besluit dat je afleidt uit een regel is geen
# besluit meer. Alleen een zaad — zodra een mens de compositie aanraakt, wint die (zie StackConfig).
_COPY_STACK_ZAAD = {
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




VILLAGE_ROOM = "village"


def _tab_suffix(tab: str | None) -> str:
    """Saniteer een client-tab-id tot [a-z0-9], max 12 tekens. Puur een disambiguator per tabblad —
    hij wordt alleen ACHTER de server-bepaalde base geplakt en kan die base nooit overschrijven."""
    return re.sub(r"[^a-z0-9]", "", (tab or "").lower())[:12]










# Static-assets: whitelist (geen path-traversal). Nu alleen de gevendorde LiveKit-client-bundle.
# ── Nooch UI v1: welke routes meedoen (fase 9) ────────────────────────────────
# De negentien schermen die in fase 7 en 8 zijn herbouwd of aangeraakt. Wat hier NIET staat doet
# bewust niet mee — /claims en /metrics2 zijn geparkeerd voor een eventuele tiende fase, de rest is
# in fase 1-8 nooit qua UI aangeraakt. De volledige lijst met redenen staat in
# claude/fase9_designsysteem_inventarisatie.md §5.
_NU_ROUTES = frozenset({
    "/", "/index.html", "/projects", "/messages", "/wiki", "/pagina",
    "/node", "/person", "/project", "/project/nieuw", "/admin", "/search",
    "/goals", "/goal", "/werkoverleg", "/roloverleg2", "/vangst",
    # Fase 10, groep B. `/middelen` en `/rolefillers` draaien op DEZELFDE `overview.py` als
    # `/node`, `/person` en `/admin`, die er al in stonden — dezelfde rendercode zag er dus anders
    # uit afhankelijk van de URL. Dat was een gat in deze lijst, geen besluit. `/site-audit` is in
    # fase 7 aangeraakt (taalresten) maar viel toen buiten de fase-9-scope.
    "/middelen", "/rolefillers", "/site-audit",
})

_STATIC_TYPES = {
    # Design-systeem-CSS (component-laag). URL draagt ?v=<inhoud-hash> (_DS_LINK),
    # dus de browser mag lang cachen: nieuwe CSS = nieuwe URL.
    "nooch.css": "text/css; charset=utf-8",
    "nooch-ui.css": "text/css; charset=utf-8",
    # De gedeelde fragment-mechaniek. URL draagt ?v=<inhoud-hash> (web_base._JS_LINK).
    "nooch.js": "application/javascript; charset=utf-8",
    "nooch-logo.svg": "image/svg+xml; charset=utf-8",
    "nooch-logo.png": "image/png",
}

#: De merk-stickers. De MAP is de bron van waarheid — een tweede lijst hier zou betekenen dat een
#: sticker die je toevoegt een 404 geeft tot iemand deze regel bijwerkt. De whitelist blijft intact:
#: alleen de namen die bij het opstarten daadwerkelijk in die map stonden komen erin, dus een naam
#: met `..` erin kan er niet tussen komen. `test_stickers.py` bewaakt de inhoud en de grootte.
_STICKER_MAP = os.path.join(os.path.dirname(__file__), "static", "stickers")
try:
    STICKERS = tuple(sorted(n for n in os.listdir(_STICKER_MAP) if n.endswith(".gif")))
except OSError:                                        # map ontbreekt → geen stickers, geen crash
    STICKERS = ()
for _s in STICKERS:
    _STATIC_TYPES["stickers/" + _s] = "image/gif"

#: Wat er ECHT in de kiezer komt. `friday-dance.gif` staat er bewust niet in (Stefan, 22 sept
#: 2026): de herkomst is onbevestigd — hij lijkt niet uit het eigen Nooch_Earth-kanaal te komen.
#: Het bestand blijft wél geserveerd, zodat een bericht dat hem al draagt niet stukgaat; hij is
#: alleen niet meer te KIEZEN. Komt de bevestiging, dan is dit één regel terug.
_STICKER_UIT = ("friday-dance.gif",)
STICKERS_PICKER = tuple(s for s in STICKERS if s not in _STICKER_UIT)


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
        # Alleen de deur ónder Active maakt meteen actief; alles anders begint slapend (scope 49).
        create_status = "running" if col == "actief" else "future"
        orec = st.records.get(owner)
        if orec is not None and org.is_circle(orec):
            # Een cirkel doet geen uitvoerend werk: projecten horen bij een rol of Individueel Initiatief.
            return nxt, "✗ a circle cannot contain a project — pick a role or Individual Action"
        # DE CARDINALITEITSWET, alleen als er niets gekozen is. Een expliciete keuze wint altijd:
        # deze regel vult een gat, hij overrulet geen mens. Zie `vervulling` voor de drie takken.
        #
        # NA de cirkel-check: een cirkel is geen rol, dus "deze rol heeft 2 vervullers" is daar een
        # onzinnige weiger-reden. Wie een cirkel kiest hoort te horen dát het een cirkel is.
        if not person and not agent and owner and not owner.startswith(_II_PREFIX):
            person, agent, _weiger = toewijzing_bij_aanmaak(st, owner)
            if _weiger:
                return nxt, _weiger
        # De intake-poort van 19 jul ("waar herken je aan dat dit klaar is?") vroeg een aparte
        # done-when. Sinds 12 sep 2026 is de titel zelf de uitkomst (Stefan: "de projectformuleringen
        # zijn al zo geschreven dat het gewenste resultaat beschreven is"): een meegegeven done-when
        # blijft welkom, zonder wordt het de titel. Zelfde regel als /wizard/create.
        done_when = (g("done_when") or "").strip() or scope
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
        # TWEE INGANGEN, ÉÉN OPSLAG. De wiki-editor laat je in de tekst zelf typen en stuurt dus
        # HTML terug (`body_html`); het formulier op een tool of policy stuurt markdown (`body`).
        # Beide komen hier binnen en worden hier markdown — dat is wat er wordt bewaard. De
        # omzetting staat VÓÓR de lengtecontrole, anders wordt een pagina afgekeurd op de lengte
        # van zijn opmaak in plaats van op die van zijn tekst.
        if "body_html" in form and "body" not in form:
            nieuw_body = _md_naar_bron(g("body_html"))
        elif "body" in form:
            nieuw_body = g("body")
        else:
            nieuw_body = None
        te_lang = _body_te_lang(nieuw_body, cur.kind) if nieuw_body is not None else ""
        if te_lang:
            return nxt, te_lang
        gref = f"domain:{cur.domain}" if getattr(cur, 'domain', '') else f"role:{cur.anchor}"
        actor_id = _web_actor_id(username, st)
        upd = st.att.update(cur.id,
                            title=(g("title") if "title" in form else None),
                            body=nieuw_body,
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


def _vermeldingen_in_kanaal(st, kanaal: str, tekst: str, afzender: str) -> int:
    """Elke @-vermelding in een kanaalbericht wordt één signalering. Geeft het aantal terug.

    EEN BERICHT IN EEN KANAAL IS GEEN BERICHT AAN IEMAND. Wie niet toevallig in dat kanaal kijkt,
    mist het. `@naam` is precies het moment waarop de schrijver zegt dat het wél voor iemand is,
    en dan hoort het bij die persoon te landen — in zijn DM, zoals elke andere signalering.

    DEZELFDE ROUTERING ALS DE REST, en dat is het hele punt van `_signaleer`: persoon → die mens,
    rol → zijn vervuller(s), geen vervuller → de Circle Lead en anders de founder. Hier een eigen
    lus over `assign.fillers_of` schrijven zou de tweede kopie zijn die de docstring van
    `_signaleer` verbiedt — dan landt dezelfde rol-id vandaag bij de een en morgen bij de ander.

    DRIE KEER NIET STUREN, en elke reden is een andere:

      1. `@jezelf` — een bericht aan jezelf is geen signalering.
      2. JE ZIT AL IN DAT GESPREK. `signaal.stuur` post in `dm_kanaal(afzender, ontvanger)`. Is dat
         hetzelfde kanaal als waar je nu typt, dan zou de signalering letterlijk dezelfde tekst
         twee regels lager herhalen. We vragen `signaal.ontvangers` dus vooraf wie het zouden
         worden — dezelfde functie die `stuur` zelf gebruikt, geen nagebouwde variant.
      3. TWEE KEER DEZELFDE NAAM, of een persona-naam naast de rolnaam die hij vervult: beide
         wijzen naar hetzelfde doel. Ontdubbeld op (soort, id), dus maximaal één melding per doel.

    Wat hier NIET wordt opgelost: een rol met twee vervullers waarvan er één je gespreksgenoot is.
    Die krijgt zijn kopie alsnog, want `stuur` stuurt naar alle vervullers en dat per ontvanger
    onderdrukken zou de routering opnieuw moeten uitschrijven. `stuur` kiest daar bewust voor
    dubbel boven niemand; die afweging blijft van hem."""
    from nooch_village import channels, signaal
    from nooch_village.views.feed import _mentionables, _mentions_in
    _, by_name = _mentionables(st)
    gezien: set = set()
    n = 0
    for ty, tid, _nm in _mentions_in(tekst, by_name):
        # Een persona-naam staat in `by_name` als de ROL die hij vervult, dus die valt vanzelf
        # onder "role". Een ander soort is er niet; komt hij er ooit, dan moet iemand hier kijken.
        if ty not in ("person", "role") or (ty, tid) in gezien:
            continue
        gezien.add((ty, tid))
        wie, _reden = signaal.ontvangers(st, ty, tid)
        blijft = [p for p in wie
                  if p and p != afzender and channels.dm_kanaal(afzender, p) != kanaal]
        if not blijft:
            continue
        if _signaleer(st, ty, tid, tekst, by=afzender, herkomst={"kanaal": kanaal}):
            n += 1
    return n


def _act_msg_post(c):
    """Eén bericht in een kanaal (fase 8).

    # AUTHZ: iedereen-ingelogd — meedoen aan een gesprek is deelnemen, geen structuurmutatie;
    # dezelfde regel als de project-wall waar deze laag uit voortkomt.
    #
    # WEL EEN HERKENDE AUTEUR. Een bericht zonder afzender kan niemand beantwoorden, en in een
    # DM-kanaal bepaalt de afzender wélk kanaal het is. Fail-closed dus, en met de reden erbij.
    # EN ALLEEN IN JE EIGEN DM: een kanaal tussen twee andere mensen is niet van jou."""
    from nooch_village import channels
    nxt, st, g, username = c.nxt, c.st, c.g, c.username
    kanaal = (g("kanaal") or "").strip()
    if channels.soort_van(kanaal) not in (channels.PROJECT, channels.CIRCLE,
                                          channels.DM, channels.TOPIC):
        return nxt, "✗ unknown channel"
    ik = _web_actor_id(username, st)
    if not ik:
        return nxt, "✗ log in as a person to write — a message needs an author"
    if channels.soort_van(kanaal) == channels.DM and ik not in channels.dm_leden(kanaal):
        return nxt, "✗ that conversation is not yours"
    # DE POORT STAAT OOK SERVER-SIDE, niet alleen als ontbrekend invoerveld. Een DM waarvan de
    # tegenpartij een rol- of systeemnaam is (alle gemigreerde inbox-berichten) leest niemand; een
    # bericht daarheen is een dead letter. Het scherm toont er geen veld, en deze regel zorgt dat
    # een handmatige POST er ook niet langs komt.
    from nooch_village.views.messages import kan_antwoorden
    if not kan_antwoorden(st, kanaal, ik):
        return nxt, "✗ nobody reads that channel — start a project or write to a person"
    entry = st.channels.post(kanaal, g("tekst"), author_type="human", author_id=ik)
    if not entry:
        return nxt, "✗ a message needs text"
    # PAS NA HET PLAATSEN. Lukt het bericht niet, dan is er niets om iemand op te wijzen; en
    # een signalering die vooruitloopt op een bericht dat er niet komt is een verwijzing naar niets.
    gemeld = _vermeldingen_in_kanaal(st, kanaal, g("tekst"), ik)
    return nxt, "💬 posted" + (f" · {gemeld} mentioned" if gemeld else "")


def _terug_naar(c, kanaal: str) -> str:
    """Waar je na het plaatsen van een sticker weer uitkomt: in het gesprek.

    NIET `c.nxt`, EN DAAR LIEP IK IN. `dispatch` zet `nxt` op "/" als het formulier geen `next`
    draagt, en "/" is waar — dus een `or`-terugval eronder doet nooit iets. Gevolg: klikken op
    een sticker gooide je naar het projectenbord. Gevonden door te klikken, niet door te lezen:
    de test dekte het plaatsen wél en de bestemming niet."""
    gevraagd = c.g("next")
    if gevraagd.startswith("/messages"):
        return gevraagd
    return "/messages?k=" + urllib.parse.quote(kanaal)


def _sticker_poort(c):
    """(ik, kanaal) als deze mens hier een sticker mag plaatsen, anders (None, melding).

    DEZELFDE POORT ALS HET ANTWOORDVELD, en bewust geen tweede regel: een sticker is een
    bericht. Staat er geen schrijfveld, dan staat de kiezer er ook niet, en dan hoort een
    handmatige POST er net zo min langs te komen."""
    from nooch_village.views.messages import kan_antwoorden, mag_kanaal_lezen
    kanaal = (c.g("kanaal") or "").strip()
    ik = _web_actor_id(c.username, c.st)
    if not ik:
        return None, "✗ log in as a person to write — a message needs an author"
    if not (mag_kanaal_lezen(c.st, kanaal, ik) and kan_antwoorden(c.st, kanaal, ik)):
        return None, "✗ nobody reads that channel"
    return (ik, kanaal), ""


def _sticker_hang(st, kanaal: str, ik: str, tekst: str, meta: dict) -> bool:
    """Plaats het bericht en hang de sticker eraan. Hetzelfde recept als `kanaal_bijlage`:
    eerst het bericht, want een bijlage hangt aan een BERICHT en niet aan een kanaal."""
    entry = st.channels.post(kanaal, tekst, author_type="human", author_id=ik)
    if entry is None:
        return False
    meta["at"] = time.time()
    return bool(st.channels.add_bijlage(kanaal, entry["id"], meta))


def _act_sticker_post(c):
    """Een sticker uit de VASTE RIJ in een kanaal plaatsen.

    # AUTHZ: iedereen-ingelogd — zie `_sticker_poort`: dezelfde voorwaarde als het antwoordveld.

    ER WORDT NIETS GEKOPIEERD. De acht eigen stickers staan in het pakket en worden al
    geserveerd; ze per bericht naar `data/kanaalbijlagen/` schrijven zou betekenen dat dezelfde
    100 kB er bij elke high-five nog een keer bij komt. De bijlage verwijst dus naar
    `stickers/<naam>`, en `/bijlage` weet dat die uit de statische map komen. Dat is geen
    uitzondering op de leescheck: die staat vóór het ophalen en verandert niet.

    De NAAM wordt getoetst tegen `STICKERS_PICKER` en niet tegen de schijf, dus een
    teruggetrokken sticker (`_STICKER_UIT`) kan ook via een handmatige POST niet alsnog."""
    naam = (c.g("naam") or "").strip()
    poort, melding = _sticker_poort(c)
    if poort is None:
        return c.nxt, melding
    ik, kanaal = poort
    if naam not in STICKERS_PICKER:
        return c.nxt, "✗ unknown sticker"
    pad = os.path.join(os.path.dirname(__file__), "static", "stickers", naam)
    label = naam[:-4].replace("-", " ")
    ok = _sticker_hang(c.st, kanaal, ik, f"🏷 {label}", {
        "id": uuid.uuid4().hex[:10], "name": naam, "stored": "stickers/" + naam,
        "size": os.path.getsize(pad) if os.path.exists(pad) else 0,
        "mime": "image/gif", "soort": "sticker"})
    return _terug_naar(c, kanaal), ("🏷 sticker geplaatst" if ok else "✗ could not post")


def _act_giphy_post(c):
    """Een gekozen Giphy-sticker plaatsen: server-side ophalen, verkleinen, bewaren.

    # AUTHZ: iedereen-ingelogd — zie `_sticker_poort`.

    ALLEEN EEN ID REIST MEE, nooit een URL. Zou de client het adres meesturen, dan bepaalt de
    client wat deze server gaat ophalen — elk intern adres, elk bestand achter de firewall.
    `giphy.haal` zoekt het adres er zelf bij en toetst meteen opnieuw of de eigenaar nog het
    merkkanaal is; `giphy.download` weigert alles buiten `*.giphy.com` en alles boven de cap.

    DEZELFDE VERKLEINING ALS DE EIGEN RIJ (`stickers.optimaliseer_bytes`). Een Giphy-GIF is
    vaak enkele megabytes; zonder die stap staat er straks een draad met stickers die tien keer
    zwaarder zijn dan de acht uit het pakket, en dan is het verschil tussen de twee helften van
    de kiezer zichtbaar in de laadtijd.

    Fail-soft, met de reden: Giphy uit of onbereikbaar geeft een melding en geen bericht."""
    from nooch_village import giphy, stickers as sticker_opt
    poort, melding = _sticker_poort(c)
    if poort is None:
        return c.nxt, melding
    ik, kanaal = poort
    treffer = giphy.haal(c.g("gif"))
    if not treffer:
        return c.nxt, "✗ that sticker is no longer available in the Nooch channel"
    ruw = giphy.download(treffer["url"])
    if not ruw:
        return c.nxt, "✗ could not fetch that sticker"
    try:
        klein = sticker_opt.optimaliseer_bytes(ruw)
    except Exception:                                       # noqa: BLE001 — onleesbare GIF
        logging.getLogger("cockpit2.giphy").warning("giphy-gif niet te verkleinen", exc_info=True)
        return c.nxt, "✗ could not process that sticker"
    bid = uuid.uuid4().hex[:10]
    naam = (re.sub(r"[^a-z0-9-]+", "-", (treffer["naam"] or "sticker").lower()).strip("-")
            or "sticker")[:60] + ".gif"
    veilig_kanaal = kanaal.replace(":", "_").replace("/", "_").replace("|", "_")
    rel = os.path.join("kanaalbijlagen", veilig_kanaal, bid + "_" + naam)
    full = os.path.join(c.data_dir, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as fh:
        fh.write(klein)
    ok = _sticker_hang(c.st, kanaal, ik, f"🏷 {treffer['naam'] or 'sticker'}", {
        "id": bid, "name": naam, "stored": rel, "size": len(klein),
        "mime": "image/gif", "soort": "sticker"})
    return _terug_naar(c, kanaal), (
        f"🏷 sticker geplaatst ({len(ruw) // 1024} kB → {len(klein) // 1024} kB)"
        if ok else "✗ could not post")


def _act_kanaal_ontvolg(c):
    """Haal een kanaal uit JOUW lijst in Messages.

    # AUTHZ: iedereen-ingelogd — dit raakt uitsluitend de eigen lijst van de ingelogde mens. Er
    # wordt niets verwijderd en niemand anders merkt er iets van; het kanaal en zijn hele trail
    # blijven staan. Fail-closed op de identiteit: zonder herkende mens is er geen lijst om uit te
    # halen, en dan doet deze actie niets.

    HET TEGENWICHT VAN "OPENEN IS TOEVOEGEN". Zonder deze actie zou één klik op een zoekresultaat
    een kanaal voorgoed in je lijst zetten, en dan is de lijst binnen een week weer de muur die
    hij was. Terugvinden doe je zoals de eerste keer: zoeken."""
    nxt, st, g, username = c.nxt, c.st, c.g, c.username
    ik = _web_actor_id(username, st)
    if not ik:
        return nxt, "✗ log in as a person to manage your channel list"
    kanaal = g("kanaal") or ""
    if not st.people.ontvolg(ik, kanaal):
        return nxt, "✗ that channel is not on your list"
    from nooch_village.views.messages import _label
    return nxt, f"✓ {_label(st, kanaal, ik)} removed from your list — search to find it again"


def _act_topic_add(c):
    """Een los kanaal aanmaken: een onderwerp zonder project, cirkel of persoon eronder.

    # AUTHZ: iedereen-ingelogd — dit VOEGT een gespreksplek toe en overschrijft of verwijdert
    # niets. Zelfde niveau als `_claims_gate` sinds fase 5, en als `msg_post` hierboven: meedoen
    # aan een gesprek is deelnemen, geen structuurmutatie. Een herkende auteur is wél nodig, zodat
    # er van elk kanaal een maker bekend is.

    DIT DRAAIT EEN EERDER BESLUIT OM. Bij fase 8 (19 september 2026) is expliciet gekozen: "één
    cirkelkanaal per bestaande cirkel, geen vrije onderwerp-kanalen zoals #batch-4". Op 20
    september is dat herzien, en de reden staat in `claude/implementatiebrief_opruiming_19sept.md`
    bij fase 10 punt 1: met 442 projectkanalen is Messages onbruikbaar zonder zoeken én zonder zelf
    een kanaal te kunnen beginnen. Een herziening, geen stille uitbreiding.

    GEEN LIDMAATSCHAP. Iedereen ziet alle losse kanalen. Dat is een tweede nieuw datamodel-begrip
    en hoort niet in dezelfde ronde als het eerste (besluit Stefan)."""
    nxt, st, g, username = c.nxt, c.st, c.g, c.username
    ik = _web_actor_id(username, st)
    if not ik:
        return nxt, "✗ log in as a person to start a channel — a channel needs an owner"
    naam = " ".join((g("naam") or "").split())
    if not naam:
        return nxt, "✗ give the channel a name"
    kanaal = st.channels.maak_topic(naam, door=ik)
    if not kanaal:
        return nxt, "✗ give the channel a name"
    return f"/messages?k={urllib.parse.quote(kanaal)}", f"💬 channel “{naam}” is open"


def _act_keep_in_wiki(c):
    """Eén bericht uit een projectgesprek als FEIT op een wiki-pagina, met herkomst (fase 7).

    # AUTHZ: rolvervuller of Circle Lead van de PAGINA — dezelfde poort als `pagina_feit_add`.
    # Bewust niet losser: een feit is inhoud van die pagina, en wie hem mag schrijven is een
    # bestaande regel. Dat betekent wel dat je een feit niet zomaar op andermans pagina kunt
    # zetten; komt dat in de weg te zitten, dan is dat een governance-vraag en geen UI-vraag.

    DE HERKOMST IS HET PUNT. Een losse zin in een wiki is een bewering; dezelfde zin mét "uit
    project X, gezegd door Y op datum Z" is navolgbaar. Daarom `soort="bron"`: dat is herkomst,
    geen bewijs — `wiki.grond_status` leest hem als `ongecontroleerd` en niet als `gegrond`, en
    dat is precies goed voor een uitspraak uit een gesprek."""
    from nooch_village import wiki
    nxt, st, g, username, data_dir = c.nxt, c.st, c.g, c.username, c.data_dir
    pagina = st.att.get(g("aid"))
    if pagina is None or pagina.kind != wiki.PAGINA_KIND:
        return nxt, "✗ page not found"
    p = st.projects.get(g("pid"))
    if p is None:
        return nxt, "✗ project not found"
    entry = next((e for e in (p.get("log") or []) if str(e.get("id") or "") == g("item")), None)
    if entry is None:
        return nxt, "✗ message not found"
    tekst = " ".join(str(entry.get("text") or "").split())
    if not tekst:
        return nxt, "✗ nothing to keep — the message has no text"
    _deny = _artefact_gate(pagina.anchor, username, st)        # check vóór de mutatie
    if _deny:
        raise Forbidden(_deny)

    from nooch_village.views.feed import _feed_norm, _feed_who
    _kind, atype, aid = _feed_norm(entry)
    wie, _ = _feed_who(st, atype, aid)
    herkomst = f"{_scope_text(p) or p.get('id', '')} · {wie} · {_stamp(entry.get('at'))}"
    feit = wiki.maak_feit(tekst, soort="bron", ref=str(p.get("id") or ""), citaat=herkomst)
    if feit is None:
        return nxt, "✗ a fact needs text"
    meta = dict(getattr(pagina, "meta", None) or {})
    meta["feiten"] = list(wiki.feiten(pagina)) + [feit]
    actor_id = _web_actor_id(username, st)
    gref = f"role:{pagina.anchor}"
    upd = st.att.update(pagina.id, meta=meta, actor_id=actor_id, actor_type="person",
                        governance_ref=gref, change_note="feit uit projectgesprek")
    artefacts.log_change(data_dir, action="edit", artefact=upd, records=st.records,
                         actor_id=actor_id, actor_type="person", governance_ref=gref)
    return nxt, f"✓ kept on {upd.title or upd.id}"


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
    # OOK DIT IS EEN GEWONE DM (B2, besluit Stefan 20 september 2026). In B1 stond hier nog dat een
    # pagina-voorstel een "verzoek met een beslissing" was en daarom niet naar een DM kon. Die
    # redenering is ingetrokken, en terecht: een voorstel is door een mens gemaakt en heeft geen
    # automatische consequentie. Het IS een suggestie. Wie de rol vervult past de pagina zelf aan
    # als hij het ermee eens is — net als bij elke andere wiki-bewerking — en een genegeerd
    # voorstel betekent gewoon dat de pagina blijft zoals hij was. Daar is geen status voor nodig,
    # en dus ook geen wachtrij om hem in te bewaren.
    _signaleer(st, "role", ontv["rol"], snippet, by=van_id or (username or ""))
    naar = _name(st.records.get(ontv["rol"])) or ontv["rol"]
    return nxt, f"✓ proposal sent to {naar}"


def _act_proj_status(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        to = g("to")
        # WIE het verplaatste gaat het status_log in (scope 48): de persoon, anders de loginnaam.
        _wie = st.people.by_email(username) if username and username != "guest" else None
        door = _wie.id if _wie else (username or "")
        pj.reopen(g("pid"), door)   # was het 'done', haal dat er eerst af zodat heractiveren kan
        if to == "actief":
            # SLEPEN NAAR ACTIEF IS EEN ANTWOORD, geen statuswijziging alleen. Stond dit project
            # geparkeerd op een stap die alleen een mens kan doen, dan zegt deze handeling "ja, ik
            # ben ermee bezig". Leggen we dat niet vast, dan loopt de rol bij de volgende puls op
            # hetzelfde item vast en parkeert opnieuw — de lus die Stefan op 9 september meldde.
            # Alleen hier, want dit is de MENS-route; `board_loop` start projecten ook, en die
            # claimt niets namens iemand.
            _mijn = pj.claim_human_items(g("pid"), door=door)
            pj.start(g("pid"), door)
            if _mijn:
                return nxt, (f"✓ verplaatst · {len(_mijn)} stap"
                             f"{'' if len(_mijn) == 1 else 'pen'} staat nu op jou")
        elif to == "wacht":
            pj.block(g("pid"), "—", door)
        elif to == "toekomst":
            pj.to_future(g("pid"), door)
        msg = "✓ verplaatst"
        return nxt, msg


def _act_proj_done(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pid = g("pid")
        # GEEN DOCUMENT-POORT MEER. Hier stond de projectpoort (founder 19 jul, verhuisd 21 jul
        # naar het einddocument): Done werd geweigerd zolang het document leeg was of alleen de
        # geseede opdracht bevatte. Stefan heeft die 4 sep 2026 ingetrokken — een Done vereist geen
        # einddocument. Een goed getitelde, echt afgeronde taak is Done, en dat oordeel is van de
        # mens, niet van een poort die naar het document kijkt in plaats van naar het werk.
        #
        # Bewust ook GEEN zachte variant: geen nudge, geen waarschuwing, geen bevestigingsvraag.
        # Die zijn expliciet afgewezen — half blokkeren is de traagheid houden zonder de zekerheid.
        #
        # Gemeten op de draaiende server bij het intrekken: 65 projecten stonden hierop vast
        # (44 met een leeg document, 21 met alleen de opdracht). Zie tests/test_project_dod_poort.py
        # voor de regel die dit besluit vastlegt in plaats van in iemands hoofd.
        #
        # Het document wordt hier nog wél gelezen: het voedt verderop de conclusie van het
        # radarsignaal. Bij het weghalen van de poort ging deze lezing eerst mee, en omdat de
        # signaal-aanmaak fail-soft in een `except` zit, verdween het signaal stil — de suite ving
        # het, de logging niet.
        _ds = getattr(st, "project_docs", None)
        _doc = _ds.read(pid) if _ds is not None else ""
        # Outcome met behoud van de telling; de mens kent Done toe ná review (Q3).
        p = pj.get(pid) or {}
        cl = uitvoerlijst(p)                     # dezelfde lijst als de rol afwerkte, niet 'die ene naam'
        if cl is not None:
            # De uitkomst is wat er later over dit project wordt teruggelezen: overgeslagen taken
            # horen daar expliciet in, anders leest een project dat afrondde zonder zijn kernitem
            # als volledig beantwoord (valse voltooiing).
            from nooch_village.projects import checklist_progress, not_answered_note
            done, telbaar = checklist_progress(cl)
            weg = not_answered_note(cl)
            outcome = (f"checklist complete ({done}/{telbaar}) — approved after review"
                       + (f" · {weg} — this part is NOT answered" if weg else ""))
        else:
            outcome = "approved after review"
        _wie = st.people.by_email(username) if username and username != "guest" else None
        pj.complete(pid, outcome, door=(_wie.id if _wie else (username or ""))); msg = "✓ afgerond"
        # HIER STELDE HET VERSLAG ZICHZELF SAMEN bij het afsluiten: één LLM-ronde over
        # definitie + checklist + gesprek + document, weggeschreven als concept naast het
        # document. Weg op 19 september 2026 (besluit Stefan, BLOK B). De 363 bestaande
        # einddocumenten blijven leesbaar op /rapport; er komt alleen geen nieuw concept meer
        # bij. Wat een afgerond project achterlaat, zet een mens in de wiki — Keep-in-wiki,
        # fase 7. Geen vervanging hier, want een half-automatische samenvatting die niemand
        # bevestigt is precies wat we kwijt wilden.
        # DE LUS SLUIT. Vroeg iemand dit als taak, dan hoort hij nu dat het klaar is. Zonder deze
        # regel is werk dat een rol voor je oppakt een eenrichtingsweg: het gebeurt, en jij hoort
        # er nooit meer iets van. Fail-soft — een melding die niet lukt blokkeert geen afronding.
        meld_opdrachtgever(st, opdrachtgever=str(p.get("opdrachtgever") or ""),
                           wat=str(p.get("scope") or pid), bron_project=pid,
                           door=(p.get("owner") or ""))
        # Geen event vanuit dit proces — de daemon-board-watch (village._poll_board) detecteert de
        # wacht→done-overgang (blocked_on=="review") en vuurt project_completed op de in-memory bus (#10-fix).
        # HIER GING EEN DONE NAAR DE RADAR EN NAAR DE KENNIS-STAGING. Beide bestemmingen zijn op
        # 19 sept 2026 verdwenen. Een afgerond project hoort nu via Keep-in-wiki in de wiki te
        # landen — met menselijke input, niet als automatisch signaal of geatomiseerd kaartje.
        return nxt, msg




def archiveer(st, pj, pid: str) -> str:
    """Een project het bord af, mét zijn signaal. ÉÉN plek, twee ingangen: de archiveer-knop en het
    bevestigde (of bewust overgeslagen) verslag (scope 49: "als ik het rapport gemaakt heb, moet ie
    eigenlijk worden gearchiveerd"). Geeft de melding terug.

    Archiveren is het moment waarop een project echt het bord verlaat. Tot 19 sept 2026 werd het
    dan ook een signaal op /signals; die feed en de promotielaag eronder bestaan niet meer."""
    pj.archive(pid)
    msg = "🗄 gearchiveerd (blijft bestaan)"
    # Het signaal-pad bij archiveren verviel op 19 sept 2026 met de radar-promotielaag.
    return msg


def _act_proj_archive(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        return nxt, archiveer(st, pj, g("pid"))


def _act_proj_unarchive(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.unarchive(g("pid")); msg = "↩ hersteld"
        return nxt, msg


def _na_verwijderen(nxt: str, pid: str) -> str:
    """Waar ga je heen als de pagina waar je stond zojuist is weggegooid?

    DIT IS DE ENIGE ACTIE MET DAT PROBLEEM. Elke andere knop brengt je terug naar waar je was;
    verwijderen vernietigt waar je was. Gemeten op 7 september: na 'Delete' landde je op
    `/project?pid=<net verwijderd>` met "Project not found" op een pagina zonder stylesheet.

    De oorzaak zat niet in de actie maar in het formulier: `hid()` zet er al een `next` in die naar
    het project zélf wijst, en de delete-knop plakte er nóg een achter met het bord erin. `g()` leest
    `(form.get(k) or [""])[0]` — de eerste — dus won de projectpagina en deed het tweede veld niets.
    Twee velden met dezelfde naam en tegengestelde bedoeling: het formulier was het al met zichzelf
    oneens vóór de server iets deed.

    Daarom repareert deze functie het bij de ACTIE en niet alleen bij dat ene formulier. De terugweg
    staat namelijk al ín de URL die we krijgen (`/project?pid=…&back=<het bord>`), dus die halen we
    er gewoon uit. Bouwt een volgende view het formulier weer scheef, dan gaat het hier alsnog goed."""
    if not nxt or (pid and f"pid={pid}" not in nxt):
        return nxt or "/"                       # wijst nergens naar dit project: laat maar staan
    try:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(nxt).query)
        terug = (q.get("back") or [""])[0].strip()
    except Exception:                           # noqa: BLE001 — een rare URL is geen reden tot 500
        terug = ""
    return terug or "/"


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
        return _na_verwijderen(nxt, pid), msg






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


def _bevestig_met(c, oordeel: str):
    """Bevestig het concept mét een oordeel. Eén plek, twee ingangen (behaald / niet behaald).

    HET OORDEEL ZIT IN DE ACTIE, niet in een apart veld. Een HTML-submitknop draagt alleen zijn
    EIGEN naam/waarde, dus "Achieved" (name=oordeel) en "Confirm report" (name=action) konden nooit
    samen in één POST: de eerste stuurde een oordeel zonder actie (er gebeurde niets), de tweede een
    actie zonder oordeel (validatie faalde). Er was geen klik die beide droeg.

    Twee acties met het oordeel eringebakken lost dat op zonder JavaScript en zonder voorselectie —
    het zijn ACTIES, geen toggles, en dat is precies wat een keuze-zonder-default hoort te zijn."""
    nxt, st, g, username = c.nxt, c.st, c.g, c.username
    pid = g("pid")
    _deny = _role_gate((st.projects.get(pid) or {}).get("owner") or "", username, st)
    if _deny:
        return nxt, _deny
    store = getattr(st, "project_docs", None)
    if store is None:
        return nxt, "✗ no document store"
    if not (store.concept(pid).get("tekst") or "").strip():
        return nxt, "✗ no draft report to confirm"
    # DE TEKST GAAT ONGEWIJZIGD DOOR: wat de mens las is wat er wordt vastgelegd. Het oordeel is
    # het telbare deel en woont in zijn eigen veld.
    if not st.projects.set_resultaat(pid, oordeel):
        return nxt, "✗ unknown result value"
    if not store.confirm_concept(pid):
        return nxt, "✗ nothing to confirm"
    # HET BEVESTIGDE VERSLAG SLUIT HET PROJECT AF (scope 49). Stefan: "als ik een project op done
    # sleep kan ik het rapport maken; als ik dat gedaan heb moet ie eigenlijk worden gearchiveerd."
    # De kolom Done toont daarmee precies de projecten waarvan het verslag nog moet.
    return nxt, "✓ report confirmed · " + archiveer(st, st.projects, pid)


def _act_verslag_bevestig_behaald(c):
    # AUTHZ: rolvervuller of Circle Lead — het verslag hoort bij het project, dus dezelfde poort als
    # het bewerken van het document zelf. Bevestigen is een oordeel over eigen werk.
    return _bevestig_met(c, BEHAALD)


def _act_verslag_bevestig_niet_behaald(c):
    # AUTHZ: rolvervuller of Circle Lead — zie hierboven.
    return _bevestig_met(c, NIET_BEHAALD)


def _act_verslag_overslaan(c):
    # AUTHZ: rolvervuller of Circle Lead — zie _act_verslag_bevestig.
    #
    # OVERSLAAN IS EEN ANTWOORD, GEEN STILTE. Het verslag zegt dan "not recorded" in plaats van de
    # voorzet als oordeel te laten staan — anders leest een overgeslagen vraag later als een
    # bevestigd "behaald", en dat is precies de stille mislukking die we vermijden.
    nxt, st, g, username = c.nxt, c.st, c.g, c.username
    pid = g("pid")
    _deny = _role_gate((st.projects.get(pid) or {}).get("owner") or "", username, st)
    if _deny:
        return nxt, _deny
    store = getattr(st, "project_docs", None)
    concept = store.concept(pid) if store is not None else {}
    if not (concept.get("tekst") or "").strip():
        return nxt, "✗ no draft report"
    # OVERSLAAN LAAT DE TEKST OOK STAAN, maar zet er één regel onder: anders leest het rapport als
    # een bevestigd oordeel terwijl niemand er ja op zei. Toevoegen, niet herschrijven.
    st.projects.set_resultaat(pid, "overgeslagen")
    store.write_concept(pid, concept["tekst"].rstrip()
                        + "\n\n_Closed without a recorded result._",
                        bronnen=concept.get("bronnen") or [],
                        voorzet=concept.get("voorzet") or "")
    store.confirm_concept(pid)
    # Overslaan is ook een afsluiting: ook dan verlaat het project het bord (scope 49).
    return nxt, "✓ closed without a recorded result · " + archiveer(st, st.projects, pid)


def _act_verslag_bijwerken(c):
    # AUTHZ: rolvervuller of Circle Lead — zie _act_verslag_bevestig. Bijwerken raakt het CONCEPT,
    # niet het document: het blijft dus onbevestigd tot iemand er expliciet ja op zegt.
    nxt, st, g, username = c.nxt, c.st, c.g, c.username
    pid = g("pid")
    _deny = _role_gate((st.projects.get(pid) or {}).get("owner") or "", username, st)
    if _deny:
        return nxt, _deny
    store = getattr(st, "project_docs", None)
    if store is None:
        return nxt, "✗ no document store"
    huidig = store.concept(pid)
    tekst = (g("tekst") or "").strip()
    if not tekst:
        return nxt, "✗ empty draft — nothing saved"
    # De provenance blijft staan: hij beschrijft waaruit is samengesteld, en dat verandert niet
    # doordat een mens de formulering bijschaaft.
    store.write_concept(pid, tekst, bronnen=huidig.get("bronnen") or [],
                        voorzet=huidig.get("voorzet") or "")
    return nxt, "✓ draft saved — still unconfirmed"


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
    # DEZELFDE WET als bij het aanmaken, uit dezelfde helper. Dit blok had zijn eigen kopie van
    # "precies één filler → daarheen"; twee plekken die hetzelfde beslissen lopen uiteen zodra er
    # één verandert. Bij 2+ blijft het hier leeg in plaats van te weigeren: dit is een NA-correctie
    # op een owner-wissel, geen intake — de mens staat hier niet voor een formulier.
    n, soort, wie = vervulling(st, owner)
    if n == 1:
        pj.edit(pid, person=(wie if soort == "person" else ""),
                agent=(wie if soort == "persona" else ""), allow_done=True)
    else:
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


# HIER STONDEN `_act_proj_proposal_accept` en `_act_proj_proposal_reject`. Ze hadden sinds de
# verwijdering van de Founder Flow geen enkel formulier meer dat ze rendert — de dispatch kon ze
# uitvoeren, maar er was geen knop meer die ze aanriep. Weg met de rest van de lus (21 sept 2026).


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


def uren_uit(number: str, unit: str) -> int | None:
    """Getal + eenheid → uren: '2' + 'dagen' = 16 (8-urige werkdag). Leeg of ≤ 0 → None (niet geschat);
    geen getal → ValueError. ÉÉN conversieregel, voor de rail (proj_seteffort) én de wizard."""
    raw = (number or "").strip().replace(",", ".")
    if not raw:
        return None
    n = float(raw)                                            # ValueError bij onzin, voor de aanroeper
    hours = int(round(n * (8 if unit == "dagen" else 1)))
    return hours if hours > 0 else None


def _act_proj_seteffort(c):
        # AUTHZ: rolvervuller of Circle Lead — effort-inschatting is operationeel projectwerk (zelfde gate
        # als proj_setimpact). Effort wordt canoniek in uren opgeslagen ({"hours": N}); leeg = wissen.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        try:
            hours = uren_uit(g("number"), g("unit"))
        except ValueError:
            return nxt, "ongeldige effort-waarde"
        if hours is None:                                    # leeg of ≤ 0 → wissen (ongeschat)
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


def _act_proj_goal(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        # AUTHZ: rolvervuller of Circle Lead — het project blijft van zijn rol; aan welk doel het
        # bijdraagt is een operationele keuze van die rol (zelfde poort als de deadline).
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        doel = g("doel_id")
        if doel and st.doelen.get(doel) is None:
            return nxt, "✗ goal not found"
        if pj.set_doel(g("pid"), doel, g("activiteit")):
            return nxt, ("🎯 linked to goal" if doel else "✓ unlinked from goal")
        return nxt, ""


def _act_proj_depends(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        # AUTHZ: rolvervuller of Circle Lead — de planning van het eigen project (waar wacht ik op).
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        p = pj.get(g("pid")) or {}
        huidig = list(p.get("depends_on") or [])
        if g("add"):
            huidig.append(g("add"))
        if g("remove"):
            huidig = [d for d in huidig if d != g("remove")]
        if pj.set_depends_on(g("pid"), huidig):
            return nxt, ("✓ dependency added" if g("add") else "✓ dependency removed")
        return nxt, ""


def _act_goal_add(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        # AUTHZ: anchor-lead — een doel is intentielaag (founder-eigendom), geen rol-werk.
        _deny = _anchor_gate(st, username)
        if _deny:
            return nxt, _deny
        try:
            d = st.doelen.add(g("titel"), label=g("label"), dod=g("dod"), deadline=g("deadline"),
                              activiteiten=[a for a in (g("activiteiten") or "").splitlines()], by=username or "")
        except ValueError as exc:
            return nxt, f"✗ {exc}"
        return f"/goal?id={d['id']}", "🎯 goal created"


def _act_goal_edit(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        # AUTHZ: anchor-lead — zie goal_add.
        _deny = _anchor_gate(st, username)
        if _deny:
            return nxt, _deny
        velden = {k: g(k) for k in ("titel", "label", "dod", "deadline", "status") if k in c.form}
        if "activiteiten" in c.form:
            velden["activiteiten"] = [a for a in (g("activiteiten") or "").splitlines()]
        if st.doelen.update(g("id"), **velden):
            return nxt, "✓ goal saved"
        return nxt, "✗ goal not found"


def _act_goal_link(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        # AUTHZ: anchor-lead — in bulk projecten van allerlei rollen aan een doel hangen is
        # org-breed; per project doet de rol het zelf via proj_goal.
        _deny = _anchor_gate(st, username)
        if _deny:
            return nxt, _deny
        doel = g("id")
        if st.doelen.get(doel) is None:
            return nxt, "✗ goal not found"
        n = 0
        for pid in c.form.get("pids") or []:
            if pj.set_doel(pid, doel):
                n += 1
        return nxt, f"🎯 {n} project(s) linked" if n else "nothing selected"


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
        nxt, g, pj, st = c.nxt, c.g, c.pj, c.st
        msg = ""
        # AUTHZ: circle-member of iedereen-ingelogd — collaboratie: bijdragen aan de draad van
        # een project is deelnemen, geen mutatie van de structuur. Bewust ongated; de
        # sessie-check in do_POST dekt "ingelogd = mag". Dat geldt net zo voor een kanaal: een
        # duimpje is meedoen aan een gesprek, geen structuurwijziging.
        #
        # ÉÉN ACTIE, TWEE ADRESSEN. `kanaal` komt uit Messages, `pid` uit de projectfeed. Een
        # tweede actie voor "hetzelfde duimpje maar elders" zou twee plekken geven die na één
        # wijziging uit de pas lopen — en een projectkanaal komt via `ChannelStore.add_reaction`
        # sowieso weer bij dezelfde ledger uit.
        if g("kanaal"):
            gelukt = st.channels.add_reaction(g("kanaal"), g("item"), g("emoji"))
        else:
            gelukt = pj.add_reaction(g("pid"), g("item"), g("emoji"))
        if gelukt:
            msg = "✓ reactie geplaatst"
        return nxt, msg


def _act_feed_edit(c):
        nxt, g, pj = c.nxt, c.g, c.pj
        msg = ""
        # AUTHZ: circle-member of iedereen-ingelogd — collaboratie: bijdragen aan de draad van
        # een project is deelnemen, geen mutatie van de structuur. Bewust ongated; de
        # sessie-check in do_POST dekt "ingelogd = mag".
        if pj.feed_edit(g("pid"), g("item"), g("text")):
            msg = "✓ comment edited"
        return nxt, msg


def _act_feed_remove(c):
        nxt, g, pj = c.nxt, c.g, c.pj
        msg = ""
        # AUTHZ: circle-member of iedereen-ingelogd — collaboratie: bijdragen aan de draad van
        # een project is deelnemen, geen mutatie van de structuur. Bewust ongated; de
        # sessie-check in do_POST dekt "ingelogd = mag".
        pj.feed_remove(g("pid"), g("item")); msg = "🗑 comment removed"
        return nxt, msg




def _vermeldingen_naar_kanalen(st, ment, *, pid: str, tekst: str, auteur: str,
                               entry_id: str) -> int:
    """Route elke @-vermelding naar het DM-kanaal van de bedoelde mens. Geeft het aantal terug.

    DE AFZENDER MOET EEN MENS ZIJN. Een DM is tussen twee mensen; een persona of een niet-herkende
    auteur heeft geen kant van dat gesprek. In dat geval blijft het de oude notificatie — niet omdat
    dat mooier is, maar omdat een bericht van niemand nergens heen kan.

    EEN ROL IS GEEN MENS. Bij `@rolnaam` gaat het bericht naar elke PERSOON die de rol vervult. Heeft
    de rol er geen, dan valt hij terug op de notificatie: dat is precies het geval waarvoor de
    wachtrij bestaat (er ligt werk, er is nog niemand)."""
    from nooch_village import channels
    afzender = auteur if (auteur and auteur != "dialoog" and st.people.get(auteur)) else ""
    n = 0
    for ty, tid, _nm in ment:
        ontvangers: list[str] = []
        if ty == "person":
            ontvangers = [tid]
        elif ty == "role" and afzender:
            ontvangers = [f.id for f in st.assign.fillers_of(tid) if f.type == "person"]
        # JEZELF VERMELDEN LEVERT NIETS OP. Eerst filteren, dán pas besluiten of er een andere weg
        # nodig is — anders maakt `@jezelf` alsnog een kanaal met jezelf, en dat is precies wat
        # fase 8 wilde voorkomen. Dit onderscheid (niets te doen vs. geen mens om heen te sturen)
        # was er wél in de oude code en ging bijna verloren bij de omzetting naar DM.
        zelf = bool(afzender) and ontvangers == [afzender]
        ontvangers = [o for o in ontvangers if o and o != afzender]
        if zelf:
            continue
        if not afzender or not ontvangers:
            # Geen mens om heen te sturen: een rol zonder vervuller, of een auteur die geen kant
            # van een DM kan zijn. `_signaleer` zoekt dan de rolvervuller of de terugval.
            _signaleer(st, ty, tid, tekst, by=auteur,
                       herkomst={"project": pid} if pid else None)
            n += 1
            continue
        for o in ontvangers:
            st.channels.post(channels.dm_kanaal(afzender, o), tekst,
                             author_type="human", author_id=afzender,
                             herkomst={"project": pid, "entry": entry_id})
            n += 1
    return n


def _act_proj_feed(c):
        nxt, st, g, pj = c.nxt, c.st, c.g, c.pj
        msg = ""
        # AUTHZ: circle-member of iedereen-ingelogd — collaboratie: bijdragen aan de draad van
        # een project is deelnemen, geen mutatie van de structuur. Bewust ongated; de
        # sessie-check in do_POST dekt "ingelogd = mag".
        atype, _, aid = g("author").partition(":")
        atype = atype or "human"
        kind = "comment" if atype == "human" else "update"
        entry = pj.add_feed_entry(g("pid"), g("text"), kind=kind, author_type=atype, author_id=aid)
        if entry:
            msg = "💬 update geplaatst" if kind == "update" else "💬 reactie geplaatst"
            _, by_name = _mentionables(st)
            ment = _mentions_in(g("text"), by_name)
            # WIE HET TYPTE, niet het kanaal. Dit stond op `by="dialoog"` — een label voor de
            # plek, niet voor de auteur — en daardoor kon de leesbaarheids-poort niet zien dat een
            # MENS deze woorden schreef. Mensentaal hoeft niet vertaald te worden, en andermans
            # woorden herschrijven is inmenging: dan moet het record dus wel zeggen wie het was.
            # Fail-soft: geen herkenbare auteur → 'dialoog', zoals vroeger.
            _auteur = "dialoog"
            if atype == "human":
                _p = st.people.by_email(c.username) if c.username and c.username != "guest" else None
                _auteur = (_p.id if _p is not None else "dialoog")
            elif aid:
                _auteur = aid
            # HET MERK `MENS_GETYPT` IS WEG (B2, 20 september 2026). Het bestond om de
            # herschrijf-poort te vertellen dat een mens deze woorden letterlijk typte; die poort
            # (`spanning_ontstaat` + `bevinding`) is met de inbox verdwenen. Er is niets meer dat
            # andermans tekst zou kunnen herschrijven, dus een waarschuwing daartegen is ruis.
            # EEN @-VERMELDING IS EEN BERICHT, GEEN NOTIFICATIE (fase 8). Tot 19 september 2026 werd
            # elke vermelding een rij in de NotifStore. Dat is de juiste vorm voor werk dat
            # afgehandeld moet worden — daar staan er 338 van — maar niet voor "hé, kijk jij hier
            # even naar": dat is één mens die een ander aanspreekt, en dus een bericht in het
            # DM-kanaal tussen die twee.
            #
            # Een vermelding van een ROL landt bij de mensen die hem vervullen, elk in hun eigen
            # DM met de afzender. Heeft de rol geen mens-vervuller, dan valt hij terug op de
            # terugval: de Circle Lead van zijn cirkel, en anders de founder. Werk bij niemand
            # neerleggen is stiller en erger dan een melding te veel.
            _gemeld = _vermeldingen_naar_kanalen(st, ment, pid=g("pid"), tekst=g("text"),
                                                 auteur=_auteur, entry_id=entry["id"])
            if _gemeld:
                msg += f" · {_gemeld} genotificeerd"
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


def _act_checklist_uitvoer(c):
        # AUTHZ: rolvervuller of Circle Lead — dezelfde poort als check_toggle. Aanwijzen welke lijst
        # de rol afwerkt is operationeel werk binnen de rol, geen governance-besluit.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if not pj.set_checklist_uitvoer(g("pid"), g("clid")):
            return nxt, ""
        return nxt, "▶️ de rol werkt voortaan deze lijst af"


def _act_plan_akkoord(c):
        # AUTHZ: rolvervuller of Circle Lead - dit IS de menselijke poort voor uitvoering. Dezelfde
        # gate als check_toggle: wie het werk van deze rol mag afvinken, mag ook zeggen dat het mag
        # beginnen. Niet founder-only: dan zou Nina's plan op Stefan wachten.
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        if not pj.plan_akkoord(g("pid"), g("clid"), door=username or ""):
            return nxt, ""                               # geen open akkoord-vraag -> stil, geen valse melding
        # Op de wall, niet alleen in een flash: over een week is "wie zei ga maar doen, en wanneer?"
        # precies de vraag die je stelt als een project iets deed wat je niet verwachtte.
        pj.add_role_message(g("pid"), f"▶️ Execution plan approved by {username or 'a human'} — "
                                      f"the role may run the items.")
        return nxt, "▶️ plan approved — the role picks it up within seconds"


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
    # GEEN TITEL-POORT MEER. Hij stond hier omdat alleen "Uitvoerplan" werd uitgevoerd, en die
    # koppeling is verplaatst naar `projects.uitvoerlijst`: een project heeft één lijst die de rol
    # afwerkt, en welke dat is staat in een veld en niet in een naam. Aanbieden mag daarom overal —
    # het accepteren van een aanbod is juist wat een enkele lijst tot uitvoerlijst maakt (regel 3).
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
    offers = plan_offers(orec, [item.get("text", "")], shared_registry(), name=_name(orec),
                         context=_context_of(st.dd))
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


def _checklist_item(pj, pid: str, clid: str, item_id: str) -> dict | None:
    """Eén item uit een checklist. Fail-soft: onbekend project, lijst of item → None."""
    p = pj.get(pid) or {}
    for cl in (p.get("checklists") or []):
        if cl.get("id") == clid:
            return next((i for i in (cl.get("items") or []) if i.get("id") == item_id), None)
    return None




def _act_check_remove(c):
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        msg = ""
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        pj.check_remove(g("pid"), g("clid"), g("item")); msg = "🗑 item removed"
        return nxt, msg


def _act_check_rename(c):
        """De tekst van één item bijschaven.

        WAAROM DIT ER MOET ZIJN: verwijderen was het enige wat een mens met een item kon. Wie een
        formulering wilde corrigeren moest hem dus weggooien en opnieuw typen — en daarmee ging de
        skill en de payload die eraan hingen mee de prullenbak in. Een tikfout kostte zo een
        uitvoer-primitief. Bijschaven is de goedkope handeling; die hoort niet duurder te zijn dan
        weggooien."""
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        tekst = (g("text") or "").strip()
        if not tekst:
            return nxt, "✗ an item needs text — remove it instead if it can go"
        ok = pj.set_item_text(g("pid"), g("clid"), g("item"), tekst)
        return nxt, ("✎ item updated" if ok else "· nothing changed")


def _act_check_move(c):
        """Volgorde binnen één checklist. `voor` = het id waar dit item vóór komt; leeg = naar het eind.

        De volgorde is geen smaak: `uitvoerlijst` laat de rol de items van boven naar beneden
        afwerken. Omhoog slepen betekent dus "dit eerst", en dat was tot nu toe alleen te bereiken
        door alles eronder te verwijderen en opnieuw te typen."""
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        _deny = _role_gate((pj.get(g("pid")) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        ok = pj.move_item(g("pid"), g("clid"), g("item"), (g("voor") or "").strip())
        return nxt, ("↕ order updated" if ok else "· nothing moved")


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
            msg = "✓ assigned"
        elif agent and st.assign.assign(g("role"), "persona", agent):
            msg = "🤖 AI assigned"
        else:
            # STIL MISLUKKEN IS HIER HET DUURST. Bleef de keuzelijst op '— pick person —' staan,
            # dan viel deze tak door met msg="": geen vervuller, geen melding, geen reden. Dat
            # leest als "deze rol is niet te bemensen" terwijl er niets kapot is. De server zegt
            # nu zelf NEE — `⚠` markeert de redirect met ok=0 (is_weigering), dus de modal toont
            # de reden in plaats van een geslaagd ogende stilte.
            msg = "⚠ no one selected — nothing was assigned"
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
        # Zelfde regel als hierboven: "✓ removed" stond hier onvoorwaardelijk, óók als er niets
        # te verwijderen viel. Een bevestiging van werk dat niet gebeurde is erger dan stilte.
        weg = False
        if person:
            weg = st.assign.unassign(g("role"), "person", person)
        elif agent:
            weg = st.assign.unassign(g("role"), "persona", agent)
        msg = "✓ removed" if weg else "⚠ nothing removed — this filler was not on the role"
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


# AUTHZ: Circle Lead — een middel losmaken is dezelfde beslissing als het leggen, dus dezelfde
# poort als `skilllink_add`. Bewust identiek.
#
# Heette tot scope 39 `aitask_remove` en bediende twee soorten koppeling: de autonome AI-taak én
# het dorpsmiddel. De autonome soort is weg (hij beloofde uitvoering die nergens draaide), dus dit
# is nu de enige weg om een gelegd middel weer los te maken.

def _act_middel_remove(c):
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
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
        # Een actie die niets deed moet dat zeggen: een onbekende of al verwijderde tid mag geen
        # "✓ removed" opleveren, want dan leest de gebruiker een succes dat er niet was.
        if _task is None:
            return nxt, "⚠ nothing removed — this resource is no longer linked"
        if _task.kind == KIND_MIDDEL:
            st.link_kroniek.record(action="verwijderd", role_id=_task.role, acc_id=_task.acc_id,
                                   skill=_task.skill, door=username)
        st.ai.remove(_task.id)
        return nxt, "✓ removed"


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


# HIER STOND `_finetune_voorstellen`: twee alternatieve werkinstructies voor een persona
# (strakker/ruimer), door een model geschreven. Weg op 20 september 2026. Hij beslíste niets —
# de mens koos — maar een persona-werkinstructie is de KARAKTERBESCHRIJVING waarop een
# AI-inwoner draait, en een model dat zijn eigen instructie herschrijft is de zelfverbeterings-
# lus die CLAUDE.md sluit ("Harde grens: zelfverbetering stopt bij voorstellen").
#
# Bewerken kan gewoon met de hand; `_persona_kroniek` legt elke wijziging vast zoals altijd.


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
        # EEN VLAGGETJE IN DE URL, GEEN TEKSTVERGELIJKING. De viering draait op de PAGINA waar je
        # na het sluiten belandt, en die moet weten dat er net iets afgerond is. Matchen op de
        # melding hierboven zou betekenen dat het feest uitgaat zodra iemand die zin vertaalt.
        # `nooch.js` haalt de parameter er meteen weer uit, dus een refresh viert niet opnieuw.
        return (nxt + ("&" if "?" in nxt else "?") + "feest=wo"), msg


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
        # DE STAAT-KEUZE GELDT ALLEEN BIJ EEN PROJECT, en dat is geen halve uitvoering maar de
        # consequentie van de afspraak: hij schrijft naar de plek waar de waarheid al staat, en
        # die plek bestaat alleen bij een project (`status=blocked`).
        #
        # Een ACTIE gaat via `route_werk` naar de inbox van een mens of naar een bestaand project;
        # daar is geen wachtstand op het werk zelf. Er een veld bij verzinnen is precies de
        # duplicatie die op 29 augustus is opgeruimd. Een GOVERNANCE-punt gaat naar het roloverleg
        # en heeft daar zijn eigen agenda.
        #
        # Fail-closed: alles wat niet expliciet "wachtend" is, is gewoon volgende.
        # DE WAARDE IS DE PROJECTSTATUS ZELF ("blocked"), niet een eigen woord dat hier naar
        # vertaald moet worden. Het formulier spreekt de taal van de plek waar het schrijft; een
        # eigen enum ertussen is de vertaalslag waar de oude `staat` aan onderdoor ging.
        _wacht = (g("staat") == "blocked") and otype == "project"
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
            # "IN AFWACHTING" SCHRIJFT NAAR HET PROJECT ZELF, niet naar een veld op de uitkomst.
            # De wachtstatus leeft op projectniveau en hoort daar te blijven; de radio is een
            # snelkoppeling ernaartoe, geen tweede plek die hetzelfde bijhoudt. Precies daarom is
            # de keuze op 29 augustus weggehaald — en daarom kan hij nu wél terug.
            if _wacht:
                st.projects.block(pid, "wacht — besloten in het werkoverleg", door=aid)
            ref = "project aangemaakt" + (" (in afwachting)" if _wacht else "")
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
            # HIER HING DE VERRIJK-HAAK (`spanning_ontstaat.maak_verrijker`). Die haak zat op
            # `NotifStore.add` en liet een model de verse spanning herschrijven en typeren vóór hij
            # in de inbox landde. De inbox is weg, de haak is met B2 met pensioen gegaan, en het
            # oordeel dat hij droeg — bevinding + typering — heeft geen lezer meer. Wat hier nog
            # wél gebeurt is het enige dat altijd de bedoeling was: doorgeven WIE het inbracht,
            # zodat het bij het verwerken zíjn spanning is en niet die van het overleg.
            doel = wiki.ontvanger(rol, st.records, st.assign)
            if not doel.get("rol"):
                return nxt, "✗ no mailbox found for this role"
            _signaleer(st, "role", doel["rol"], tekst,
                       by=(it.get("by_id") or (actor.id if actor else "")))
            naam = _name(st.records.get(doel["rol"])) if st.records.get(doel["rol"]) else doel["rol"]
            waarom = f" ({doel['reden']})" if doel.get("reden") else ""
            detail = f"tension for {naam}{waarom}"
            st.werk.punt_resolve(circle, iid, otype, detail)
            # De bevestiging noemde vroeger het TYPE dat de poort eraan gaf ("— naar_rol"). Dat veld
            # bestond om de inbox te routeren en vervalt met de inbox; wat de lezer werkelijk wil
            # weten is bij wie het terechtkwam, en dat staat er al.
            return nxt, f"✓ tension sent to {naam}"

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


def _kan_uitvoeren(st, rol: str) -> bool:
    """Kan deze rol werk UITVOEREN? Een AI-vervuller, eigen code of eigen skills telt.

    ROUTEER OP LEVEN, NIET OP VERMOGEN. Een rol met een class KAN werken; een rol met een draaiende
    thread WERKT. Slapend of gearchiveerd telt dus niet mee, hoeveel code er ook achter zit.

    Dezelfde definitie die de Reconciler gebruikt om te bepalen of een rol een thread krijgt — hier
    LIVE uit de records berekend en niet uit een door de daemon geschreven cache. Die cache was mijn
    eerste versie en had de verkeerde faalrichting: ontbreekt het bestand (test, verse installatie,
    webserver vóór de eerste dorpsstart), dan werd "leeg" gelezen als "niemand leeft" en ging ál het
    AI-werk naar de Circle Lead. Onbekend leven is geen dood — zelfde regel als `no_data ≠ nul`, en
    wat hier niet vast te stellen is, laten we leven."""
    if not rol:
        return False
    rec = None
    try:
        rec = st.records.get(rol)
    except Exception:                                         # noqa: BLE001
        rec = None
    # SLAPEND OF GEARCHIVEERD KAN NIETS, hoeveel code er ook achter zit. Dit ontbrak, en de droge
    # sweep wees het aan: `noochie` en `facilitator` staan allebei in CLASS_MAP, dus "kan uitvoeren"
    # zei ja — terwijl ze slapen en er geen thread draait. Precies de vijf wees-projecten die deze
    # opruiming moest vinden, gemist door de vraag die hij stelde.
    #
    # KUNNEN is niet DRAAIEN. Zelfde onderscheid als bij de dagbel: de code stond er, er tikte alleen
    # niets meer.
    if rec is not None and (getattr(rec, "slaapt", False) or getattr(rec, "archived", False)):
        return False
    try:
        if any(f.type == "persona" for f in st.assign.fillers_of(rol, record=rec)):
            return True
    except Exception:                                         # noqa: BLE001
        pass
    if list(getattr(getattr(rec, "definition", None), "skills", None) or []):
        return True
    try:
        from nooch_village.village import CLASS_MAP
        return rol in CLASS_MAP
    except Exception:                                         # noqa: BLE001
        return True          # kunnen we het niet vaststellen → oude gedrag, nooit blokkeren


def mens_vervullers(st, rol: str) -> list[str]:
    """De MENSEN die deze rol vervullen. Eén plek, want drie schermen stelden dezelfde vraag.

    Sinds B2 is die ene plek `signaal.mensen_van`, want de signaal-routering stelt hem ook. Twee
    implementaties zouden betekenen dat een scherm een andere vervuller ziet dan het bericht dat
    erheen gaat — precies het soort verschil dat niemand opmerkt tot het misgaat."""
    if not rol:
        return []
    try:
        from nooch_village import signaal
        return signaal.mensen_van(st, rol)
    except Exception:                                         # noqa: BLE001
        return []


def vervulling(st, rol: str) -> tuple[int, str, str]:
    """DE CARDINALITEITSWET: hoeveel vervullers heeft deze rol, en wie is het als er één is?

    Geeft `(aantal, soort, id)` — soort is "person" of "persona", en alleen gevuld bij precies één.

    Drie takken, en elke tak heeft een eigen reden:

      0  → het project mag onbemand bij de rol op het bord staan. Dit is het ENIGE geval waarin
           onbemand eerlijk is: er is werkelijk niemand om het aan te geven.
      1  → automatisch toewijzen. Onbemand laten is hier een stille nul: de eigenaar is eenduidig,
           en hem niet invullen suggereert dat er iets te kiezen valt.
      2+ → een keuze afdwingen vóór het project op het bord mag. Een stille gok tussen twee mensen
           is erger dan geen keuze, want niemand ziet dat er gegokt is.

    EEN VERVULLER IS EEN MENS ÓF EEN PERSONA. Dat onderscheid is niet cosmetisch: `mens_vervullers`
    telt alleen mensen, en onder díe definitie heeft 14 van de 29 rollen "geen vervuller" terwijl
    11 daarvan gewoon AI-vervuld zijn. Gemeten op productie scheelt dat 135 tegen 9 projecten die
    de één-tak raken — de definitie bepaalt de hele wet. `st.assign.fillers_of` is de bron die
    beide kent, en `_resync_trekker` gebruikte hem al; deze helper maakt er één antwoord van.

    Een SLAPENDE AI-rol telt gewoon mee: de rol bestaat en houdt het mandaat, slapen is een
    losstaande vraag. Op productie verandert dat vandaag niets (de slapende rollen hebben geen
    onbemande projecten), dus de keuze draagt geen last — maar hij staat hier expliciet."""
    try:
        rec = st.records.get(rol) if rol else None
    except Exception:                                           # noqa: BLE001
        return 0, "", ""
    if rec is None:
        return 0, "", ""
    try:
        fillers = list(st.assign.fillers_of(rol, record=rec))
    except Exception:                                           # noqa: BLE001
        return 0, "", ""
    if len(fillers) == 1:
        f = fillers[0]
        return 1, f.type, f.id
    return len(fillers), "", ""


def toewijzing_bij_aanmaak(st, rol: str) -> tuple[str, str, str]:
    """`(person, agent, weigering)` voor een NIEUW project bij deze rol, zonder gekozen trekker.

    De weigering is niet-leeg bij 2+ vervullers; hij draagt een ✗ zodat `is_weigering` hem herkent
    en de client hem nooit als succes rendert."""
    n, soort, wie = vervulling(st, rol)
    if n == 1:
        return (wie if soort == "person" else ""), (wie if soort == "persona" else ""), ""
    if n >= 2:
        return "", "", (f"✗ this role has {n} fillers — pick an owner before putting it on the board")
    return "", "", ""


def standaard_trekker(st, rol: str) -> str:
    """De owner die het projectformulier voorkiest voor deze rol, of "" als er niets te kiezen valt.

    Drie takken, en de derde is de reden dat dit BOVENOP `mens_vervullers` zit en niet op
    `bestemming`:

      één vervuller     → die persoon, als default (niet als verplichting)
      meerdere          → "" — het formulier laat kiezen; een stille gok tussen twee mensen is erger
                          dan geen keuze, want niemand ziet dat er gegokt is
      geen vervuller    → "" — "no owner" blijft staan

    `bestemming()` beantwoordt dezelfde vraag voor het ROUTEREN van werk, en heeft daar een derde
    stap die hier schadelijk is: bij een onbemande rol hopt hij naar de Circle Lead. Voor werk is dat
    juist — het moet ergens landen. Voor een formulier-default zou het "no owner" stilletjes ombouwen
    tot "de Circle Lead is eigenaar", en dan maak je precies de wees-projecten die `afslank_wezen`
    achteraf opruimde, alleen met een naam erop.

    Eén mechaniek, twee consumenten: `mens_vervullers` is de bron van waarheid over wie een rol
    vervult; `bestemming` en deze helper zijn er allebei een lezer van."""
    mensen = mens_vervullers(st, rol)
    return f"person:{mensen[0]}" if len(mensen) == 1 else ""


def vervullers_map(st) -> dict:
    """Per rol de MENSEN die hem vervullen, voor de owner-kiezer in de wizard.

    Alleen rollen met TWEE of meer: bij één is er niets te kiezen (die is al de default, zie
    `standaard_trekker`) en bij nul valt er niets te tonen. Zo draagt de pagina alleen wat hij echt
    gebruikt — op prod zijn dat twee rollen.

    Zelfde bron als de default: `mens_vervullers`. Zou dit zijn eigen lijst opbouwen, dan kan het
    scherm iemand aanbieden die de default niet kent, en dan tonen twee vormen van dezelfde vraag
    een ander antwoord."""
    uit = {}
    for rec in st.records.all():
        rid = getattr(rec, "id", "")
        if not rid or getattr(rec, "archived", False):
            continue
        # EEN CIRKEL BEZIT GEEN PROJECT — `_act_proj_add` weigert dat expliciet ("a circle cannot
        # contain a project"). Zonder deze regel droeg de map `mother_earth__nooch` als
        # kiezer-ingang: onschadelijk, want de rolkiezer biedt nooit een cirkel-id, maar wel een
        # ingang die per definitie nooit bruikbaar is. Dat is de dood-maar-intact-vorm die iemand
        # later doet denken dat het wél kan.
        #
        # `org.is_circle` en geen eigen string-check: een derde definitie van "dit is een cirkel"
        # is precies hoe twee vormen van dezelfde vraag uit elkaar gaan lopen.
        if org.is_circle(rec):
            continue
        mensen = mens_vervullers(st, rid)
        if len(mensen) >= 2:
            uit[rid] = [{"v": f"person:{p}", "n": _person_name(st, p) or p} for p in mensen]
    return uit


def _circle_lead_van(st, rol: str) -> str:
    """De Circle Lead van de cirkel waar deze rol in hangt. Het adres voor werk dat NIEMAND draagt:
    een rol zonder mens én zonder AI kan niets, en dan is beleggen de handeling — niet uitvoeren."""
    try:
        from nooch_village import org
        cid = resolve_circle_id(rol, st.records)
        for r in st.records.all():
            if getattr(r, "archived", False) or org.is_circle(r):
                continue
            if getattr(r, "parent", "") == cid and "circle_lead" in r.id:
                return r.id
    except Exception:                                         # noqa: BLE001
        pass
    return ""


def bestemming(st, *, rol: str = "", persoon: str = "", keuze_kan: bool = False,
               _lead_hop: bool = False) -> dict:
    """WAAR zou dit werk landen? Zelfde beslissing als `route_werk`, zonder iets te schrijven.

    Bestaat omdat de droge run van de wees-opruiming een bestemming moet TONEN vóór er iets
    verschuift, en die vraag twee keer beantwoorden is precies de fout waar `docs/CONVENTIES.md`
    voor waarschuwt: twee vormen van dezelfde regel lopen na één wijziging uit de pas, en dan belooft
    het scherm iets anders dan er gebeurt. Eén regel, twee gebruiken — voorspellen en uitvoeren.

    Geeft {soort, doel_type, doel_id, via} terug. `via` vertelt hoe hij daar kwam (bv. de rol die
    niemand vervulde), zodat een droge run leesbaar is zonder de code ernaast te leggen."""
    if persoon:
        return {"soort": "inbox", "doel_type": "person", "doel_id": persoon, "via": ""}
    mensen = mens_vervullers(st, rol)
    if len(mensen) > 1:
        if keuze_kan:
            return {"soort": "keuze", "doel_type": "role", "doel_id": rol, "via": ""}
        # `toelichting` en niet `via`: dit is geen OMLEIDING maar de rol zelf, en dan hoort er geen
        # "[…]" voor de tekst van de ontvanger. `via` betekent "dit ligt hier omdat het ergens
        # anders niet kon", en dát moet de lezer weten.
        return {"soort": "inbox", "doel_type": "role", "doel_id": rol, "via": "",
                "toelichting": "meerdere vervullers"}
    if len(mensen) == 1:
        return {"soort": "inbox", "doel_type": "person", "doel_id": mensen[0], "via": ""}
    if rol and not _lead_hop and not _kan_uitvoeren(st, rol):
        lead = _circle_lead_van(st, rol)
        if lead and lead != rol:
            door = bestemming(st, rol=lead, _lead_hop=True)
            return {**door, "via": f"{rol} heeft geen vervuller"}
        # DE KLIM LOOPT DOOD, EN DAN IS DE FOUNDER HET ADRES — niet de rol zelf.
        #
        # `_circle_lead_van` slaat gearchiveerde records over, en dat is terecht: werk bij een
        # opgeheven Circle Lead neerleggen is hetzelfde als weggooien. Maar hij klimt één niveau en
        # stopt, en bij een CIRKEL die in zijn geheel is opgeheven is er dus geen lead meer. Dan
        # viel dit terug op `{"soort": "project", "doel_id": rol}` — de rol die net is vastgesteld
        # als "kan niets". Gemeten op prod, 20 september 2026: twee weesprojecten van de opgeheven
        # `compliance`-rol, en `village afslank_wezen` stelde voor ze te "verhuizen" naar diezelfde
        # dode rol. Dat is geen verhuizing maar een lus die het origineel archiveert.
        #
        # De terugval is dezelfde als overal elders sinds vandaag: alles wat niemand kan dragen komt
        # bij de founder (CLAUDE.md, "AI is instrument, geen rol"). Geen model, geen keuze.
        from nooch_village import signaal
        founder = signaal.terugval(st)
        if founder:
            return {"soort": "inbox", "doel_type": "person", "doel_id": founder,
                    "via": f"{rol} heeft geen vervuller en de cirkel geen Circle Lead"}
    return {"soort": "project", "doel_type": "role", "doel_id": rol, "via": ""}


def bestemming_tekst(st, best: dict) -> str:
    """De bestemming in mensentaal: een naam, geen id."""
    doel = best.get("doel_id") or ""
    if best.get("doel_type") == "person":
        naam = _person_name(st, doel) or doel
        wat = f"inbox van {naam}"
    else:
        rec = st.records.get(doel) if doel else None
        naam = (_name(rec) if rec is not None else "") or doel or "(niemand)"
        wat = {"keuze": f"keuze uit de vervullers van {naam}",
               "inbox": f"inbox van de rol {naam}"}.get(best.get("soort"), f"project bij {naam}")
    achter = best.get("via") or best.get("toelichting") or ""
    return wat + (f" — {achter}" if achter else "")


def route_werk(st, *, tekst: str, rol: str = "", persoon: str = "", herkomst: str = "",
               door: str = "", opdrachtgever: str = "", bron_project: str = "",
               prive: bool = False, keuze_kan: bool = False, van_mens: bool | None = None,
               _lead_hop: bool = False) -> tuple[str, str]:
    """Waar landt een stuk werk? ÉÉN regel, gedeeld door het werkoverleg en de project-wizard.

    Dit stond als losse tak in `_act_vangst_uitkomst` (#364). Hem hier een tweede keer uitschrijven
    zou precies de fout zijn die `docs/CONVENTIES.md` verbiedt: twee vormen van hetzelfde die na één
    wijziging uit de pas lopen — en dan landt werk stil op de verkeerde plek.

    DE REGEL, en hij kijkt naar de VERVULLER en niet naar de rol:

      persoon gegeven          → inbox bij die persoon;
      rol met ÉÉN mens         → inbox bij DIE MENS. Een rol is een mandaat, geen postbus; werk
                                 komt bij wie het draagt, met de rol als context.
      rol met MEER mensen      → ("keuze", rol): de aanroeper laat kiezen. Zelf de eerste pakken
                                 zou een stille keuze zijn, en dat is precies wat `_thuis_cirkel`
                                 fout deed. Kan de aanroeper niet kiezen (`keuze_kan=False`), dan
                                 gaat het naar de rol als geheel — zichtbaar voor alle vervullers.
      rol met NUL mensen, AI   → projectroute. Een AI-rol leest de NotifStore nooit; een bericht
                                 daarheen is stil verliezen, en verstuurd mag nooit kwijt betekenen.
      rol met NUL vervullers   → de CIRCLE LEAD. Hier ging het mis: zo'n rol kreeg gewoon een
                                 project, en dat rot weg op een bord waar niemand kijkt. Gemeten op
                                 prod: 5 open projecten op rollen die ná het aanmaken slapend
                                 werden gelegd. Een rol die niets kan uitvoeren hoort werk niet te
                                 KRIJGEN maar te laten BELEGGEN.

    `opdrachtgever` reist mee zodat de lus kan sluiten: rondt de ontvanger het af, dan krijgt de
    opdrachtgever bericht (`meld_opdrachtgever`).

    Geeft (soort, ref) terug: "inbox" / "project" / "keuze" plus een leesbare verwijzing."""
    # DE BESLISSING KOMT UIT `bestemming`, en daar staat hij één keer. Hier stond hem nóg een keer
    # uitschrijven — inclusief de lead-hop als recursie — en dat is precies de tweede vorm waar
    # docs/CONVENTIES.md voor waarschuwt. Nu voorspelt de droge run van de wees-opruiming met
    # dezelfde functie die hem straks uitvoert; ze KUNNEN niet uit elkaar lopen.
    best = bestemming(st, rol=rol, persoon=persoon, keuze_kan=keuze_kan, _lead_hop=_lead_hop)
    if best["soort"] == "keuze":
        return "keuze", rol
    doel_type, doel_id = best["doel_type"], best["doel_id"]
    if best.get("via"):
        # De ontvanger moet zien waaróm dit bij hem ligt en niet bij de rol die het vroeg.
        tekst = f"[{best['via']}] {tekst}"
    # HIER STOND DE TRIAGE-STAP (`_rolsuggestie` → `triage_rol.classificeer`): een modelaanroep die
    # een rol voorstelde mét de accountability waarop hij matcht, als annotatie bij het werk. Hij
    # veranderde de bestemming niet — de lezer accepteerde, overschreef of hield hem zelf.
    #
    # ZIJN LEZER IS IN B2 VERDWENEN. De suggestie reisde mee als `extra`-velden op `notif.add`, en
    # die velden droegen het inbox-scherm. Sinds 20 september 2026 is een melding een DM en heeft
    # een DM geen velden; de aanroep bleef staan, het resultaat ging nergens heen. Dat is niet
    # gratis: het kostte een modelaanroep per lead-hop en per project-routering, elke keer opnieuw.
    #
    # `triage_rol.py` zelf blijft staan — `menselijke_eigenaar` heeft een eigen lezer in
    # `materiaal_memo`. Wat er NU dood in ligt (`classificeer`, `noteer_uitkomst`, de
    # acceptatie-meting) staat op de sweep-lijst; dat kost niets zolang het wacht, dit wel.
    if best["soort"] == "inbox":
        # Ook hier stond het `MENS_GETYPT`-merk; zie de toelichting bij `_act_proj_feed`.
        # OOK DIT IS EEN GEWONE DM (B2). `roloverleg.py` houdt toewijzing én afronding al zélf bij,
        # los van welke wachtrij dan ook — de DM is puur de melding erbovenop. Er viel hier dus
        # nooit iets vast te leggen wat elders niet al stond, en een tweede administratie van
        # hetzelfde feit is precies wat `reference, don't copy` verbiedt.
        _signaleer(st, doel_type, doel_id, tekst, by=(door or "werkoverleg"),
                   herkomst={"project": bron_project} if bron_project else None)
        return "inbox", "in de " + bestemming_tekst(st, best)
    eigenaar = doel_id or f"{_II_PREFIX}{bron_project or ''}"
    pid = st.projects.create(eigenaar, (tekst or "").strip()[:200], "human",
                             parent=(bron_project or None), opdrachtgever=opdrachtgever or "")
    _prov_feed(st, pid, herkomst, door)
    if prive:
        st.projects.edit(pid, private=True, allow_done=True)
    return "project", "als " + bestemming_tekst(st, best)


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
        return _signaleer(st, "person", opdrachtgever, f"Klaar: {wat}", by=(door or "village"),
                          herkomst={"project": bron_project} if bron_project else None)
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
        # Hier stond een tak voor "kwam dit uit de inbox (`nid` meegegeven)": die markeerde het
        # item als verwerkt. De inbox bestaat sinds B2 niet meer, dus `nid` komt nooit meer binnen.
        return nxt, f"✓ {_LBL[otype]} created"






def _act_goedkeur(c):
        """Eén antwoord op een goedkeuring, vanuit de inbox-lade.

        DE POORT ZIT HIER, IN CODE, EN NIET IN DE KNOP. De view tekent geen ja-knop waar het niet
        mag, maar een view is een verzoek en geen garantie: een POST kan met de hand gestuurd
        worden. `goedkeuring.mag_ja` beslist, en hij faalt closed — een type dat niemand heeft
        afgewogen krijgt geen ja.

        Nee en later mogen altijd, op elk type. Dat is de hele reden dat deze rij nu in het cockpit
        staat: een weigering schept niets, dus er is geen grens die hij kan overschrijden. Zou dat
        per type geregeld zijn, dan bestaat er ooit een type waarop je niet eens nee kunt zeggen, en
        dan groeit de rij weer dicht — precies wat er zeventig dagen lang gebeurde."""
        from nooch_village import goedkeuring, inbox_actions
        from nooch_village.human_inbox import HumanInbox
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        # AUTHZ: alleen een herkende mens beslist. Dezelfde poort als bij means_gap-melden: `guest`
        # mag lezen, niet beslissen.
        if username == "guest" or (username and st.people.by_email(username) is None):
            return nxt, "No access — user not recognised"
        iid, besluit = (g("iid") or "").strip(), (g("besluit") or "").strip()
        if not iid or besluit not in ("approved", "rejected", "deferred"):
            return nxt, "✗ unknown decision"
        hi = HumanInbox(os.path.join(st.dd, "human_inbox.json"))
        item = next((i for i in hi.all() if i.get("id") == iid), None)
        if item is None:
            return nxt, "✗ item not found"
        if besluit == "approved" and not goedkeuring.mag_ja(item):
            # Niet stil weigeren: de mens moet weten WAAROM en WAAR het dan wel kan.
            return nxt, f"✗ {goedkeuring.waarom_niet(item)} — run it from the command line"
        reden = f"via cockpit door {username}"
        # Het 'verband'-itemtype verviel op 19 sept 2026 met de kaartjes-store: een touwtje tussen
        # twee kaartjes kan niet gelegd worden als er geen kaartjes meer zijn.
        if item.get("type") == "keyword" and besluit in ("approved", "rejected"):
            r = inbox_actions.decide_keyword(hi, st.library, iid,
                                             "approve" if besluit == "approved" else "reject",
                                             reason=reden)
        else:
            r = inbox_actions.weiger_of_stel_uit(hi, iid, besluit, reason=reden) \
                if besluit in goedkeuring.ALTIJD else {"ok": False, "error": "not supported here"}
        if not r.get("ok"):
            return nxt, f"✗ {r.get('error') or 'could not save that'}"
        woord = {"approved": "✓ approved", "rejected": "✓ rejected", "deferred": "✓ deferred"}[besluit]
        return nxt, woord


def _act_metrics2_fav(c):
        # Favoriet = een tegel op de node (bestaand mechanisme). Gate: cirkellid.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _member_gate(resolve_circle_id(g("node"), st.records), username, st)
        if _deny:
            return nxt, _deny
        tile = st.metrics.add_tile(g("node"), g("source"), g("measure"), g("dim") or "none", g("form") or "getal")
        return nxt, ("★ on your dashboard" if tile else "✗ could not add")


# De metrics2-tegels: AUTHZ: circle-member of iedereen-ingelogd — een tegel is een WEERGAVE op je
# eigen dashboard, geen meting en geen structuur. `_act_metrics2_fav` (toevoegen) draait wel een
# `_member_gate` op de node; wisselen en weghalen van een bestaande tegel raakt geen nieuwe data en
# blijft bewust vrij.

def _act_metrics2_unfav(c):
        ok = c.st.metrics.remove_tile(c.g("node"), c.g("tid"))
        return c.nxt, ("removed from your dashboard" if ok else "✗ not found")


def _act_metrics2_form(c):
        # AUTHZ: circle-member of iedereen-ingelogd — zie het metrics2-blok hierboven.
        # Weergave-schakelaar: de vorm van een tegel wisselen (view losgekoppeld van data).
        ok = c.st.metrics.set_tile_form(c.g("node"), c.g("tid"), c.g("form"))
        return c.nxt, ("display changed" if ok else "✗ not found")


def _act_metrics2_dim(c):
        # AUTHZ: circle-member of iedereen-ingelogd — zie het metrics2-blok hierboven.
        # Segmentatie: de dimensie van een tegel wisselen (bv. per land / per product / over tijd).
        # De view stuurt een passende vorm mee (segmentatie bepaalt welke weergaves kloppen).
        ok = c.st.metrics.set_tile_dim(c.g("node"), c.g("tid"), c.g("dim"), c.g("form"))
        return c.nxt, ("gesegmenteerd" if ok else "✗ not found")


def _act_metrics2_compare(c):
        # AUTHZ: circle-member of iedereen-ingelogd — zie het metrics2-blok hierboven.
        # Metric-vs-metric: een tweede meting koppelen (combo staaf+lijn) of leeg → vergelijking eraf.
        g = c.g
        ok = c.st.metrics.set_tile_compare(g("node"), g("tid"), g("cmp_source"),
                                           g("cmp_measure"), g("cmp_dim") or "over_tijd")
        return c.nxt, ("vergelijking ingesteld" if ok else "✗ not found")






# De twee bron-takken: AUTHZ: anchor-lead — een bron aanzetten bepaalt welke externe API's het HELE
# dorp bij elke pulse aanroept, met de sleutels van de organisatie. Dat is org-breed, niet
# rol-operationeel. Ook hier stond de omgekeerde check.

def _act_source_activate(c):
        # Externe bron aanzetten (mens-gated). Haalt pas bij de volgende pulse data op.
        src = (c.g("source") or "").strip()
        _deny = _anchor_gate(c.st, c.username)
        if _deny:
            return c.nxt, f"✗ {_deny}"
        if not src:
            return c.nxt, "✗ no source given"
        c.st.sources.set_active(src, True)
        return c.nxt, f"✓ {src} staat aan (data volgt bij de volgende pulse)"


def _act_source_deactivate(c):
        # AUTHZ: anchor-lead — zie het blok hierboven.
        src = (c.g("source") or "").strip()
        _deny = _anchor_gate(c.st, c.username)
        if _deny:
            return c.nxt, f"✗ {_deny}"
        if not src:
            return c.nxt, "✗ no source given"
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
        # AUTHZ: iedereen-ingelogd — een spanning voelen mag iedereen, en hij landt in je EIGEN
        # wachtrij (de handler bepaalt het doel zelf uit `username`, niet uit het formulier). De
        # poort die ertoe doet zit op het verwerken ervan.
        st, g, username = c.st, c.g, c.username
        text = (g("text") or "").strip()
        role = (g("role") or "").strip()
        if not text:
            return c.nxt, "✗ empty tension"
        if role and st.records.get(role) is not None:
            _signaleer(st, "role", role, text, by="zelf")
        else:
            actor = st.people.by_email(username) if username and username != "guest" else None
            _signaleer(st, "person", actor.id if actor else "", text, by="zelf")
        return c.nxt, "✓ tension added"


def _sluit_reden_terug(st, pj, n: dict, reden: str, *, aid: str, by: str,
                       kern: str = "") -> str:
    """De reden bij het sluiten terug naar wie het vroeg. Fail-soft: een mislukte terugkoppeling
    mag het sluiten nooit blokkeren, maar hij mag ook niet stil verdwijnen — vandaar de log.

    Alleen op de BRON-FEED, en niet ook als bericht aan de eigenaar-rol. Dat laatste deed
    Decide-now wel, en bij een AI-vervulde rol was dat een dead letter: die leest de NotifStore
    nooit. De feed-entry is het kanaal dat de bewoner écht weer aan het werk zet."""
    src_pid = str(n.get("project_id") or "")
    if not src_pid:
        return ""
    try:
        p = pj.get(src_pid)
        if p is None:
            return ""
        orec = st.records.get(p.get("owner") or "")
        rolnaam = _name(orec) if orec else (p.get("owner") or "rol")
        # `kern` laat de aanroeper zijn eigen zin meegeven. Zonder dat werd een weigering dubbel
        # ingepakt — "gesloten door X — reden: ✗ je verzoek is geweigerd: …" — en stond er
        # bovendien "gesloten" boven iets wat een WEIGERING is. Twee woorden voor twee dingen.
        tekst = f"@{rolnaam} " + (kern or
                                  f"Deze spanning is gesloten door {by or 'The Source'} — "
                                  f"reden: {reden}")
        entry = pj.add_feed_entry(src_pid, tekst[:1500], kind="comment",
                                  author_type="human", author_id=aid)
        return (entry or {}).get("id", "")
    except Exception:                                          # noqa: BLE001
        logging.getLogger("cockpit2.inbox").exception("reden bij sluiten niet teruggekoppeld")
        return ""


def _volledig_van(n: dict) -> str:
    """De volle tekst van een spanning — dezelfde die het formulier voorvult."""
    from nooch_village.tekstpreview import volledig
    return volledig(n or {})


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
        # AUTHZ: iedereen-ingelogd — noochie_* (send/reset/ctx) is de assistent-chat: praten, geen
        # mutatie van andermans data. Bewust ongated; de sessie-check in do_POST dekt
        # "ingelogd = mag".
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
        # AUTHZ: iedereen-ingelogd — zie `_act_noochie_send`.
        nxt, st = c.nxt, c.st
        msg = ""
        st.noochie.reset(); msg = "↺ Noochie opnieuw"
        return nxt, msg


def _act_noochie_ctx(c):
        # AUTHZ: iedereen-ingelogd — zie `_act_noochie_send`.
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




# ── Claims-checker: cureren van de claims-database ───────────────────────────
# De database (`config/claims_database.json`) is juridisch mensenwerk: deze takken schrijven alleen
# door wat een mens invoert. Sinds fase 5 is er geen domein-eigenaar meer — wie is ingelogd mag
# cureren (`_claims_gate`). De JSON-route /claims/db.json is in fase 6 verwijderd: nul verzoeken in
# veertien dagen log, en Stefan bevestigde dat niets van buiten hem aansprak.

def _act_check_handoff(c):
        """Eén checklist-item doorgeven aan een rol of persoon.

        DIT MAAKTE EEN HEEL PROJECT, en dat was de klacht. De knop vroeg om een 'done when…' en zette
        een slapend project op het bord van de ontvanger. Maar een mens die één item doorgeeft wil geen
        project, hij wil dat iemand het ziet: "@iemand, kijk jij hier even naar".

        Nu loopt het langs `route_werk` — DEZELFDE regel als het werkoverleg en de inbox. Die kijkt
        naar de VERVULLER en niet naar de rol: een mens-vervulde rol levert een bericht in de inbox
        van díe mens, een AI-rol krijgt alsnog een project (die leest de NotifStore nooit, en
        verstuurd mag nooit kwijt betekenen). Een tweede kopie van die regel hier zou na één wijziging
        uit de pas lopen en werk stil op de verkeerde plek laten landen.

        HET DOEL WORDT SERVER-SIDE OPGELOST, en fail-closed. De mens typt een naam; wij zoeken hem op
        in dezelfde lijst die het veld voedt. Staat hij er niet in, dan is dit een FOUT en geen gok —
        werk bij een geraden ontvanger neerleggen is stiller en erger dan een melding."""
        nxt, st, g, pj, username = c.nxt, c.st, c.g, c.pj, c.username
        pid = g("pid")
        _deny = _role_gate((pj.get(pid) or {}).get("owner") or "", username, st)
        if _deny:
            return nxt, _deny
        getypt = (g("naar") or g("naar_rol") or "").strip().lstrip("@")
        if not getypt:
            return nxt, "✗ pick a role or person to hand this to"
        from nooch_village.cockpit2_util import _at_doelen
        doel = next((d for d in _at_doelen(st) if d["label"].strip().lower() == getypt.lower()), None)
        if doel is None:
            return nxt, f"✗ '{getypt[:40]}' is not a role or person I know — pick one from the list"

        it = _checklist_item(pj, pid, g("clid"), g("item"))
        tekst = (it or {}).get("text", "") if it else ""
        if not tekst:
            return nxt, "✗ item not found"
        soort, ref = route_werk(st, tekst=tekst,
                                rol=doel["id"] if doel["kind"] == "role" else "",
                                persoon=doel["id"] if doel["kind"] == "person" else "",
                                herkomst=f"↳ doorgegeven uit project {pid}",
                                door=username or "", opdrachtgever=username or "",
                                bron_project=pid, van_mens=True)
        if soort == "keuze":
            return nxt, (f"✗ {doel['label']} has more than one person filling it — "
                         f"pick the person instead of the role")
        from nooch_village import project_items
        _ok, msg = project_items.resolve_item(pj, pid, g("clid"), g("item"), "doorgeven",
                                              by=username or "", naar_label=doel["label"])
        return nxt, (msg + (f" ({soort})" if soort else ""))


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


def _claims_gate(st, username: str | None) -> str | None:
    """Poort voor claims-curatie: None = mag, anders de weigering.

    # AUTHZ: iedereen-ingelogd — claims is sinds 19 september 2026 geen domein met een eigenaar
    # meer maar gereedschap dat een mens pakt (fase 5). Wie is ingelogd mag de term-database
    # bijwerken.
    #
    # WAT HIER WEG IS. De poort leidde de eigenaar-rol af uit het claims-domein en liet alleen de
    # rolvervuller of Circle Lead door. Die constructie was al één keer gerepareerd: acht takken
    # riepen `_role_gate("compliance", …)` met een literal aan, en toen die rol verhuisde hing de
    # hele curatie aan een naam die niemand meer droeg. De afleiding uit governance loste dat op,
    # maar de onderliggende aanname bleef: dat er een eigenaar HOORT te zijn. Die aanname is
    # vervallen. Het claims-domein heeft sinds 18 september geen levende eigenaar, de EmpCo-deadline
    # staat op 27 september, en een poort die niemand doorlaat is dan geen zorgvuldigheid maar een
    # blokkade.
    #
    # Wat blijft: de guest-regel (auth uit = mag alles) en fail-closed op een ingelogde die het
    # systeem niet kent. Dat is dezelfde vorm als `_role_gate` en `_member_gate`; alleen de
    # rol-eis eruit, niet de authenticatie."""
    if username == "guest":
        return None
    if st.people.by_email(username) is None:
        return "No access — user not recognised"
    return None


def _claims_gate_open(st, username: str | None) -> bool:
    """Mag deze gebruiker de claims-database cureren? Eén definitie voor zowel het tonen van de
    schrijfknoppen als het toestaan van de mutatie — de knop kan dus nooit iets beloven wat de
    dispatch-tak weigert (reference, don't copy)."""
    return _claims_gate(st, username) is None


def _claims_audit(st, username: str | None, event: str, **velden) -> None:
    """Leg de mutatie vast in de bestaande audit-trail. Geen bus in dispatch → direct schrijven."""
    try:
        with open(os.path.join(st.dd, "system_log.jsonl"), "a") as f:
            f.write(json.dumps({"event": event, "by": username or "?", "at": time.time(), **velden},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass


# De twee claims-skills draaiden tot 19 september 2026 mee op de dagpuls (`pulse_skills` in
# settings.ini). Claims is sinds fase 5 geen domein met een eigenaar meer maar gereedschap dat een
# mens pakt, en gereedschap heeft een knop nodig, geen wekker. De DNA-grant op compliance blijft
# staan: de skills MOGEN nog, ze gaan alleen niet meer uit zichzelf lopen.
_CLAIMS_KNOPPEN = {
    "claims_site_scan": "site scan",
    "regulation_watch": "regulation check",
}


def _act_claims_skill(c):
        """Draai een van de twee claims-skills op aanvraag, synchroon, en zeg wat eruit kwam.

        # AUTHZ: iedereen-ingelogd — zelfde poort als de rest van de claims-curatie (`_claims_gate`).
        #
        # SYNCHROON, en dat is een keuze. De mens staat voor het scherm en heeft net geklikt; een
        # achtergrondtaak zou betekenen dat hij niet weet of er iets gebeurt. Beide skills bewaken
        # hun eigen ritme en zijn idempotent per periode, dus twee keer klikken is niet twee keer
        # werk — dat is precies waarom ze een knop kunnen zijn."""
        naam = (c.g("skill") or "").strip()
        if naam not in _CLAIMS_KNOPPEN:
            return c.nxt, "✗ unknown claims skill"
        _deny = _claims_gate(c.st, c.username)
        if _deny:
            return c.nxt, _deny
        skill = shared_registry().get(naam)
        if skill is None:
            return c.nxt, f"✗ {naam} is not registered"
        _load_env()
        try:
            uit = skill.run({}, c.st) or {}
        except Exception as e:                              # noqa: BLE001
            logging.getLogger("cockpit2.claims").exception("%s faalde", naam)
            return c.nxt, f"✗ {_CLAIMS_KNOPPEN[naam]} failed: {type(e).__name__}"
        _claims_audit(c.st, c.username, f"claims_skill_run", skill=naam, ok=bool(uit.get("ok")))
        # De uitkomst in één regel, en een lege uitkomst zegt WAAROM hij leeg is — een skill die
        # "niets gedaan" meldt zonder reden leest als een storing (zelfde regel als bij de puls).
        if uit.get("no_data") or uit.get("skipped"):
            return c.nxt, f"· {_CLAIMS_KNOPPEN[naam]}: {uit.get('reason') or uit.get('reden') or 'nothing to do'}"
        if uit.get("ok") is False:
            reden = (uit.get("escalate") or {}).get("reason") or uit.get("error") or "unknown reason"
            return c.nxt, f"✗ {_CLAIMS_KNOPPEN[naam]}: {reden}"
        return c.nxt, f"✓ {_CLAIMS_KNOPPEN[naam]}: {uit.get('text') or 'done'}"


def _act_claims_term_add(c):
        # AUTHZ: rolvervuller of Circle Lead — compliance-domein: alleen de domein-eigenaar cureert
        # de claims-database.
        nxt, st, g, username = c.nxt, c.st, c.g, c.username
        _deny = _claims_gate(st, username)
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
        _deny = _claims_gate(st, username)
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
        _deny = _claims_gate(st, username)
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
        _deny = _claims_gate(st, username)
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
        _deny = _claims_gate(st, username)
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
        _deny = _claims_gate(st, username)
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
        _deny = _claims_gate(st, username)
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




def _act_kb_discuss(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok
    ok = c.st.kennisbank.discuss(c.g("iid"), c.g("text"), _kb_actor(c))
    return c.nxt, ("💬 kanttekening geplaatst" if ok else "✗ type an annotation first")




def _act_kb_insight_link(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok. B1: koppel een ander INZICHT
    # als steun/tegen aan het geopende inzicht (de Zettelkasten-ladder → meta-inzicht).
    ok = c.st.kennisbank.link_insight(c.g("iid"), c.g("other_id"), c.g("stance"), by=_kb_actor(c))
    return c.nxt, ("🔗 insight linked" if ok else "✗ linking failed")


def _act_kb_insight_unlink(c):
    # AUTHZ: iedereen-ingelogd — zie het kop-comment van dit blok.
    ok = c.st.kennisbank.unlink_insight(c.g("iid"), c.g("other_id"))
    return c.nxt, ("unlinked" if ok else "✗ unlinking failed")


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


def _kb_spel_set(c) -> list[dict]:
    """Gecureerde set uit het formulier: checkboxes `kaart` + per kaart `stance_<id>`."""
    ids = c.form.get("kaart") or []
    return [{"atom_id": aid, "stance": (c.g(f"stance_{aid}") or "support")}
            for aid in ids if aid]


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
# AUTHZ: rolvervuller of Circle Lead — de Library IS het domein van de Librarian, en curatie is
# volgens de domeinregel het exclusieve recht van de eigenaar (CLAUDE.md: "lezen is vrij;
# cureren/wijzigen is het exclusieve recht van de eigenaar").
#
# HIER STOND "iedereen-ingelogd", EN DAT WAS EEN GAT. Twintig regels hoger zit
# `_act_kw_nom_reject`, die precies hetzelfde domein raakt en wél `_role_gate("librarian")`
# draait. Dezelfde store, dezelfde beslissing, twee verschillende poorten — en de zwakste van de
# twee kon een woord permanent op `forbidden` zetten, wat betekent dat GEEN ENKELE bron het ooit
# nog voorstelt (`lib.status(term) is not None` blokkeert hervoorstel voor alle statussen). Eén
# klik door een willekeurige ingelogde persoon sloot dus een zoekwoord voorgoed uit de
# ontdekkingslus, zonder dat de eigenaar van het domein er iets van zag.
#
# De rechtvaardiging ("de sessie-check in do_POST dekt ingelogd = mag") gold voor beheeracties
# zonder domein-eigenaar. Deze heeft er een.

def _act_ws_curate(c, status: str, ok_msg: str):
    # Gedeelde kern voor pauzeer/verbied/heractiveer: curatie via curate_library_term.
    deny = _role_gate("librarian", c.username, c.st)
    if deny:
        return c.nxt, f"✗ {deny}"
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


def _act_decision_sheet_log(c):
    # AUTHZ: iedereen-ingelogd — elk lid logt zijn EIGEN besluit, in zijn eigen woorden. Er is geen
    # rol, domein of cirkel die een besluit van een mens over zijn eigen werk begrenst; een gate zou
    # hier alleen bepalen wie mag leren van zijn eigen voorspelling.
    from nooch_village import decision_sheets as _ds
    nxt, st, g, username = c.nxt, c.st, c.g, c.username
    rauw = g("sheet") or ""
    try:
        sheet = _ds.parse(rauw)
    except _ds.Geweigerd as e:
        # De reden gaat mee terug naar de pagina; er is niets geschreven. Bewust de volle tekst en
        # geen code: de gebruiker moet kunnen zien WELK veld ontbrak zonder te hoeven raden.
        return f"{nxt}?fout={urllib.parse.quote(str(e))}", ""
    persoon = st.people.by_email(username) if username not in (None, "guest") else None
    rollen = st.assign.roles_of("person", persoon.id) if persoon else []
    # VANUIT WELKE ROL is dit besloten? In een Holacracy-substraat is dat geen metadata maar de
    # kern. Eén rol → vanzelf ingevuld; meer dan één → de mens kiest, want alleen hij weet het.
    # De keuze wordt getoetst aan zijn eigen rollen: een formulierwaarde is een verzoek, geen feit.
    rol = (g("rol") or "").strip()
    if len(rollen) > 1 and rol not in rollen:
        return (f"{nxt}?fout=" + urllib.parse.quote(
            "Choose the role you decided from. You fill more than one, and which one this decision "
            "came from is something only you know. Nothing was saved."), "")
    if len(rollen) == 1:
        rol = rollen[0]
    if rol and rol not in rollen:
        rol = ""                                           # onbekende rol → leeg, nooit gokken
    # GEEN template_version hier: die komt uit het sheet zelf (`Coach version`). Hem hier uit het
    # sjabloon op schijf lezen zou een sheet van vorige week de versie van vandaag geven.
    _ds.log_sheet(c.data_dir, sheet,
                  decider=(persoon.name if persoon else "guest"),
                  role=rol, raw=rauw)
    return f"{nxt}?melding={urllib.parse.quote('Decision sheet logged.')}", ""


ACTIONS = {
    "decision_sheet_log": _act_decision_sheet_log,
    "tag_onderhoud_run": _act_tag_onderhoud_run,
    "copy_stack_inclusie": _act_copy_stack_inclusie,
    "kb_insight_link": _act_kb_insight_link,
    "kb_insight_unlink": _act_kb_insight_unlink,
    "kb_link": _act_kb_link,
    "kb_unlink": _act_kb_unlink,
    "kb_discuss": _act_kb_discuss,
    "kw_nominate": _act_kw_nominate,
    "kw_nom_accept": _act_kw_nom_accept,
    "kw_nom_reject": _act_kw_nom_reject,
    "ws_forbid": _act_ws_forbid,
    "ws_approve": _act_ws_approve,
    "proj_add": _act_proj_add,
    "artefact_add": _act_artefact_add,
    "artefact_edit": _act_artefact_edit,
    "artefact_archive": _act_artefact_archive,
    "msg_post": _act_msg_post,
    "sticker_post": _act_sticker_post,
    "giphy_post": _act_giphy_post,
    "topic_add": _act_topic_add,
    "kanaal_ontvolg": _act_kanaal_ontvolg,
    "keep_in_wiki": _act_keep_in_wiki,
    "pagina_feit_add": _act_pagina_feit_add,
    "pagina_feit_del": _act_pagina_feit_del,
    "pagina_voorstel": _act_pagina_voorstel,
    "proj_status": _act_proj_status,
    "proj_done": _act_proj_done,
    "proj_archive": _act_proj_archive,
    "proj_unarchive": _act_proj_unarchive,
    "proj_delete": _act_proj_delete,
    "proj_rename": _act_proj_rename,
    "proj_describe": _act_proj_describe,
    "proj_doc_edit": _act_proj_doc_edit,
    "verslag_bevestig_behaald": _act_verslag_bevestig_behaald,
    "verslag_bevestig_niet_behaald": _act_verslag_bevestig_niet_behaald,
    "verslag_overslaan": _act_verslag_overslaan,
    "verslag_bijwerken": _act_verslag_bijwerken,
    "proj_settrekker": _act_proj_settrekker,
    "proj_setowner": _act_proj_setowner,
    "proj_approve": _act_proj_approve,
    "proj_discard": _act_proj_discard,
    "proj_setimpact": _act_proj_setimpact,
    "proj_seteffort": _act_proj_seteffort,
    "proj_agendeer_verzwakt": _act_proj_agendeer_verzwakt,
    "proj_setprivate": _act_proj_setprivate,
    "proj_setdue": _act_proj_setdue,
    "proj_goal": _act_proj_goal,
    "proj_depends": _act_proj_depends,
    "goal_add": _act_goal_add,
    "goal_edit": _act_goal_edit,
    "goal_link": _act_goal_link,
    "attach_add": _act_attach_add,
    "attach_remove": _act_attach_remove,
    "react_add": _act_react_add,
    "feed_edit": _act_feed_edit,
    "feed_remove": _act_feed_remove,
    "wall_outcome": _act_wall_outcome,
    "goedkeur": _act_goedkeur,
    "notif_add": _act_notif_add,
    "metrics2_fav": _act_metrics2_fav,
    "metrics2_unfav": _act_metrics2_unfav,
    "metrics2_form": _act_metrics2_form,
    "metrics2_dim": _act_metrics2_dim,
    "metrics2_compare": _act_metrics2_compare,
    "metrics2_formula": _act_metrics2_formula,
    "source_activate": _act_source_activate,
    "source_deactivate": _act_source_deactivate,

    "proj_feed": _act_proj_feed,
    "checklist_add": _act_checklist_add,
    "checklist_remove": _act_checklist_remove,
    "plan_akkoord": _act_plan_akkoord,
    "checklist_uitvoer": _act_checklist_uitvoer,
    "check_add": _act_check_add,
    "check_accept": _act_check_accept,
    "check_toggle": _act_check_toggle,
    "check_skip": _act_check_skip,
    "check_unskip": _act_check_unskip,
    "check_remove": _act_check_remove,
    "check_rename": _act_check_rename,
    "check_move": _act_check_move,
    "role_assign": _act_role_assign,
    "role_unassign": _act_role_unassign,
    "role_focus": _act_role_focus,
    "middel_remove": _act_middel_remove,
    "skilllink_add": _act_skilllink_add,
    "means_gap_add": _act_means_gap_add,
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
    "person_edit": _act_person_edit,
    "person_remove": _act_person_remove,
    "check_handoff": _act_check_handoff,
    "claims_skill": _act_claims_skill,
    "claims_term_add": _act_claims_term_add,
    "claims_term_retract": _act_claims_term_retract,
    "claims_work_status": _act_claims_work_status,
    "claims_bewijs_link": _act_claims_bewijs_link,
    "claims_vondst_whitelist": _act_claims_vondst_whitelist,
    "claims_regel_uit_vondst": _act_claims_regel_uit_vondst,
    "claims_to_board": _act_claims_to_board,
}


#: De vormen waarin een dispatch-tak NEE zegt. Geteld in cockpit2 op 3 sep 2026: ✗ (119×),
#: ⛔ (17×), "No access…"/"Not …" (41×). Eén lijst, want de client mag hier nooit zelf naar raden.
_WEIGERING_TEKENS = ("✗", "⛔", "⚠")
_WEIGERING_WOORDEN = ("no access", "not linked", "no accountability", "not logged in",
                      "csrf token invalid")


def is_weigering(msg: str) -> bool:
    """Zegt deze melding NEE? Server-side waarheid over de uitkomst van een actie.

    VALS SUCCES IS ERGER DAN STILLE MISLUKKING. Een gebruiker die niets ziet gebeuren, kijkt
    verder; een gebruiker die "✓ moved" leest, gelooft het en gaat door. Daarom kent de server
    zelf het verschil, en raadt de client niet."""
    t = (msg or "").strip()
    if not t:
        return False
    if t[0] in _WEIGERING_TEKENS:
        return True
    laag = t.lower()
    return any(laag.startswith(w) for w in _WEIGERING_WOORDEN)


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

        def _nu_scope(self, body: str) -> str:
            """Zet `class="nu"` op <body> als deze route in fase 9 is herbouwd.

            ÉÉN PLEK, ROUTE-GESTUURD. Het alternatief was een vlag door ~19 render-functies heen
            duwen; dan staat de scope op negentien plekken en loopt hij na de eerste wijziging uit
            de pas. Hier is hij een lijst, en die lijst IS de verantwoording: wat er niet in staat
            doet bewust niet mee (zie claude/fase9_designsysteem_inventarisatie.md §5)."""
            pad = (self.path or "/").split("?", 1)[0]
            if pad not in _NU_ROUTES or "<body>" not in body:
                return body
            return body.replace("<body>", '<body class="nu">', 1).replace(
                _DS_LINK, _DS_LINK + _NU_LINK, 1)

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
                except Exception:
                    _st = None
                # DE ORGANISATIEBOOM ZAT IN DE RECHTERRAIL en staat sinds fase 7 in de zijbalk
                # links, bij de rest van de navigatie (prototype v15). Hij wordt hier gevuld en niet
                # in `_nav()` zelf, omdat hij de records nodig heeft en `_nav()` geen stores kent —
                # zelfde patroon als de begroeting hieronder.
                #
                # FASE 10 PUNT 3: de node-pagina's hielden tot nu toe hun EIGEN rail met dezelfde
                # boom erin — twee keer hetzelfde op één scherm. Die rail is weg. Wat die rail
                # extra deed, de huidige node openklappen en markeren, gebeurt nu hier: het `id`
                # uit de query gaat mee naar `_tree_html`. Zo verdwijnt de dubbele weergave zonder
                # dat de positie-in-de-organisatie verloren gaat.
                # HIER WERD DE ORGANISATIEBOOM IN DE ZIJBALK GEÏNJECTEERD. De boom is op
                # 21 september 2026 een nav-paneel geworden (`/nav-paneel?p=org`), zoals Projects
                # en Messages: hij wordt opgehaald als je erop klikt, niet meegerenderd met elke
                # pagina. Daarmee vervalt deze injectie én de `_SIDE_ORG`-placeholder.
                # De Circle-link in de zijbalk wijst naar de operationele cirkel (Nooch), dezelfde
                # node waar '/' vóór fase 7 op landde. Nu landt '/' op Projects en is de cirkel een
                # eigen nav-item, precies zoals in het prototype.
                # DE CIRKEL-AFHANKELIJKE HELFT VAN DE BALK. `_nav()` heeft geen stores en kan
                # dus niet weten over WELKE cirkel het gaat; `_send` wel. Twee plekken, dezelfde
                # bron (`_home_node`): de Circle-knop en de twee overleg-knoppen.
                if _st is not None and (_SIDE_CIRCLE in body or _SIDE_OVERLEG in body):
                    try:
                        _cid = _home_node(_st.records.all())
                        # Zelfde vorm als de vaste items (`_side_item`): monogram voor de
                        # ingeklapte rail, woord voor de volle zijbalk. Zou deze link het woord
                        # kaal dragen, dan staat er in de rail één item uit te steken.
                        from nooch_village.cockpit2_util import _side_item, overleg_items
                        body = body.replace(
                            _SIDE_CIRCLE,
                            _side_item(f"/node?id={_e(_cid)}", "Circle", "ci") if _cid else "", 1)
                        # `/werkoverleg` en `/roloverleg2` tonen het overleg van EEN CIRKEL en
                        # beginnen met `st.records.get(circle_id)`. Zonder dit id gaven ze "No
                        # circle." en "Unknown." — geen ontbrekende routes maar een ontbrekende
                        # parameter, op de enige plek die de cirkel niet in handen had.
                        body = body.replace(
                            _SIDE_OVERLEG,
                            overleg_items(_cid, werk_open=_st.werk.is_open(_cid)), 1)
                    except Exception:
                        body = body.replace(_SIDE_CIRCLE, "", 1)
                        body = body.replace(_SIDE_OVERLEG, "", 1)
                # HET PROFIEL IN DE HEADER: de initialen van de ingelogde persoon, met de volle
                # naam in title/aria-label en dezelfde link naar zijn eigen pagina.
                #
                # WAS "Hoi Stefan" in de zijbalk. Een begroeting kost een hele regel breedte voor
                # informatie die je na de eerste keer niet meer leest; wat je er wél uit haalt —
                # "ik ben ingelogd, en als wie" — past in een rondje van 32px. De NAAM verdwijnt
                # niet: hij staat in `title` voor de muis en in `aria-label` voor wie hem niet ziet.
                #
                # Voor- ÉN achternaam ("SW"), via dezelfde `_initials` die de avatars elders in
                # het dorp gebruiken — niet een eigen afkorting naast die van de berichtenlijst.
                if _st is not None:
                    try:
                        _p = _st.people.by_email(self._session_username())
                        _vol = (getattr(_p, "name", "") or "").strip()
                        _pid = getattr(_p, "id", "") or ""
                        if _vol and _pid:
                            body = body.replace(
                                "<span class='c2-av' id='c2-av'></span>",
                                f"<a class='c2-av' id='c2-av' href='/person?id={_e(_pid)}' "
                                f"title='{_e(_vol)}' aria-label='{_e(_vol)} — your profile'>"
                                f"{_e(_initials(_vol))}</a>", 1)
                    except Exception:
                        pass
                # De LiveKit-callbar is 11 aug 2026 uit de app-shell gehaald: hij werkte niet
                # betrouwbaar, en een strook die het soms doet is erger dan geen strook. De
                # /callbar-route en de LiveKit-helpers blijven bestaan (dood maar intact), zodat
                # terugzetten één regel is en er nu geen halve opruiming in de weg zit.
                body = body.replace(
                    "</body>",
                    _footer() + "</body>", 1)
            body = self._nu_scope(body)
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

        def _send_bijlage(self, data: bytes, mime: str, naam: str, *, inline: bool):
            """Bytes met de twee regels die bij ons eigen domein horen.

            `nosniff` op ALLES, ook op een plaatje: zonder die header mag de browser alsnog zelf
            iets anders van de bytes maken dan wat wij zeggen. En inline alleen voor wat de
            allowlist als inline markeert — al het andere gaat als download, zodat een bestand
            nooit als pagina op onze origin uitkomt."""
            veilig = os.path.basename(naam or "bestand").replace('"', "") or "bestand"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Disposition",
                             f'{"inline" if inline else "attachment"}; filename="{veilig}"')
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

            if path == "/overleg-status":
                # DE LIVE-STATUS VAN HET WERKOVERLEG, voor de knop in de balk.
                #
                # DEZE ROUTE STAAT BEWUST VÓÓR `_Stores(data_dir)`, en dat is het hele ontwerp.
                # Gemeten op productie: alle stores bouwen kost 70 ms per verzoek, en de vraag
                # zelf — `is_open` — kost 0,31 ms als je alleen de store bouwt die hem kan
                # beantwoorden. Een poller die elke 20 seconden 70 ms serverwerk aanzet voor een
                # ja/nee is geen polling maar een lek.
                #
                # Server-gerenderd en geen JSON: de knoppen komen uit dezelfde `overleg_items` als
                # in de balk, dus er is geen tweede plek die bepaalt hoe een live-knop eruitziet.
                from nooch_village.werkoverleg import WerkoverlegStore
                from nooch_village.cockpit2_util import overleg_items
                _cid = (qs.get("circle") or [""])[0]
                _open = False
                try:
                    _open = bool(_cid) and WerkoverlegStore(
                        os.path.join(data_dir, "werkoverleg.json")).is_open(_cid)
                except Exception:                      # noqa: BLE001
                    _open = False                      # fail-closed: liever geen uitnodiging
                self._send(overleg_items(_cid, werk_open=_open), chrome=False)
                return
            st = _Stores(data_dir)
            # ── Wachtwoordwijziging (self-service + verplichte eerste-login/na-reset-poort) ──
            if path == "/wachtwoord":
                # AUTHZ: circle-member of iedereen-ingelogd — eigen wachtwoord wijzigen
                self._send(_auth.password_change_page(forced=st.people.must_change(username or "")))
                return
            if username and st.people.must_change(username):     # poort: alles → /wachtwoord tot gewijzigd
                self._redirect_to("/wachtwoord")
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
            if path in ("/", "/index.html"):
                # PROJECTS IS DE LANDING (fase 7, prototype v15). Hiervóór kwam je op de
                # cirkelpagina uit; het bord stond daar als tab én als de plek waar je feitelijk
                # elke dag werkt. De cirkel is nu een nav-item, het bord de voordeur.
                self.send_response(302)
                self.send_header("Location", "/projects")
                self.end_headers()
                return
            if path == "/messages":
                # AUTHZ: iedereen-ingelogd — meelezen in de kanalen van het dorp is net zo vrij als
                # het bord. Schrijven vereist een HERKENDE persoon (zie _act_msg_post): een bericht
                # zonder auteur kan niemand beantwoorden.
                _ik = _web_actor_id(username, st)
                self._send(render_messages(st, ik=_ik, kanaal=(qs.get("k") or [""])[0],
                                           csrf_token=effective_csrf,
                                           msg=(qs.get("msg") or [""])[0],
                                           q=(qs.get("q") or [""])[0],
                                           lijst=bool((qs.get("list") or [""])[0]),
                                           wie=(qs.get("wie") or [""])[0]))
                return
            if path == "/wiki":
                # AUTHZ: iedereen-ingelogd — lezen is vrij (zelfde scope als de Wiki-tab op een
                # node). Schrijven gebeurt niet hier maar op de eigenaar-rol, achter zijn poort.
                self._send(render_wiki_index(st, csrf_token=effective_csrf,
                                             soort=(qs.get("kind") or ["all"])[0]))
                return
            if path == "/projects":
                # AUTHZ: iedereen-ingelogd — lezen van het bord is vrij; de mutaties eronder gaan
                # elk door hun eigen poort (proj_*), precies als op de cirkel-tab.
                default_id = _home_node(st.records.all())
                if not default_id:
                    self._send(_page("Empty", "<p>No organisation loaded yet.</p>")); return
                rec = st.records.get(default_id)
                self._send(render_projects_screen(
                    st, rec, csrf_token=effective_csrf, username=username,
                    group=(qs.get("group") or [""])[0]))
                return
            if path == "/node":
                nid = (qs.get("id") or [""])[0]
                ntab = (qs.get("tab") or ["overview"])[0]
                # Oude tabnamen (policies/notes/tools) vertaalt `render_node` zelf naar de
                # Wiki-tab met het juiste voorfilter — zie daar.
                self._send(render_node(st, nid, ntab, csrf_token=effective_csrf,
                                       kind_flt=(qs.get("kind") or [""])[0],
                                       msg=(qs.get("msg") or [""])[0],
                                       group=(qs.get("group") or [""])[0],
                                       goal=(qs.get("goal") or [""])[0],
                                       clf=(qs.get("clf") or ["due"])[0],
                                       mw=(qs.get("mw") or ["7d"])[0],
                                       van=(qs.get("van") or [""])[0],
                                       tot=(qs.get("tot") or [""])[0],
                                       compare=(qs.get("compare") or [""])[0] == "1",
                                       van_rapport=(qs.get("van_rapport") or [""])[0],
                                       username=username))
                return
            if path == "/rapport":
                # AUTHZ: iedereen-ingelogd — het rapport IS het einddocument van een project, dus
                # exact dezelfde read-scope als /project (die de kaart toont, waar het rapport tot
                # nu toe inline stond). Schrijven (proj_doc_edit, proj_regen_doc) zit achter de
                # bestaande poorten in de dispatch-takken, niet hier.
                self._send(render_projectrapport(st, (qs.get("pid") or qs.get("id") or [""])[0],
                                          csrf_token=effective_csrf, username=username,
                                          msg=(qs.get("msg") or [""])[0],
                                          back=(qs.get("back") or ["/"])[0]))
                return
            if path == "/pagina":
                # AUTHZ: iedereen-ingelogd — een wiki-pagina IS een rol-note, dus exact dezelfde
                # read-scope als /node?tab=notes (lezen is vrij, cureren is van de eigenaar-rol).
                # Schrijven zit achter de artefact-poort in de dispatch-acties, niet hier.
                self._send(render_pagina(st, (qs.get("id") or [""])[0],
                                         csrf_token=effective_csrf, username=username,
                                         msg=(qs.get("msg") or [""])[0],
                                         persoon=(qs.get("persoon") or [""])[0]))
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
                                         nid=(qs.get("nid") or [""])[0],
                                         col=(qs.get("col") or [""])[0],       # de bordkolom van de deur
                                         # Expliciete trekker wint; anders de vervuller van de
                                         # rol als default (één vervuller → voorgekozen).
                                         trekker=((qs.get("trekker") or [""])[0]
                                                  or standaard_trekker(st, (qs.get("role") or [""])[0])),
                                         eigen=_eigen,
                                         vervullers=vervullers_map(st)),
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
                                                back=(qs.get("back") or ["/"])[0], fragment=fr,
                                                username=username), fr))
                return
            if path == "/rolefillers":
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_rolefillers(st, (qs.get("role") or [""])[0],
                                                    csrf_token=effective_csrf, fragment=fr), fr))
                return
            if path == "/middelen":
                role_id = (qs.get("role") or [""])[0]
                aid = _acc_id_param(st, role_id, qs)
                fr = (qs.get("fragment") or [""])[0] == "1"
                self._send(_frag(render_middelen(st, role_id, aid,
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
            if path == "/search":
                # Globale zoekopdracht vanuit de header: roles, projects, insights, signals.
                # ?frag=1 → alleen de dropdown-inhoud (live terwijl je typt); anders de volle pagina.
                _q = (qs.get("q") or [""])[0]
                if (qs.get("frag") or [""])[0] in ("1", "true", "on"):
                    self._send(render_search_fragment(st, _q), chrome=False)
                else:
                    self._send(render_search(st, _q))
                return
            if path == "/giphy-zoek":
                # AUTHZ: iedereen-ingelogd — dezelfde poort als de rest van Messages: meedoen aan
                # een gesprek. Wat hier uitkomt zijn plaatjes uit het eigen merkkanaal, geen
                # organisatie-inhoud.
                #
                # DE SLEUTEL KOMT HIER NOOIT VANDAAN. De route geeft alleen de gevonden URL's
                # terug; `GIPHY_API_KEY` blijft in de omgeving van de server. Een clientside
                # fetch naar Giphy zou die sleutel aan iedere bezoeker uitdelen.
                #
                # FAIL-SOFT, EN DAT IS EXPLICIET: geen sleutel, geen netwerk of een hikkende
                # Giphy geeft `{"hits": []}` met status 200, niet een 5xx. De vaste rij stickers
                # staat los hiervan en blijft werken; alleen het zoekveld vindt dan niets.
                from nooch_village import giphy
                self._send_json({"hits": giphy.zoek((qs.get("q") or [""])[0])})
            if path == "/mention-search":
                # AUTHZ: iedereen-ingelogd — @-typhulp in een invoerveld.
                #
                # WAAROM DAT DE JUISTE POORT IS: deze route geeft namen van mensen en rollen
                # terug, en precies die namen toont `/search` al aan iedereen die is ingelogd —
                # het zijn letterlijk dezelfde twee functies. Een strengere poort hier zou
                # suggereren dat er iets extra's uit komt; dat is niet zo.
                #
                # EN WAT ER NIET UIT KOMT: geen id, geen e-mailadres, geen URL. Alleen een label
                # en een soort, want meer heeft de typhulp niet nodig. Komt er ooit een
                # notificatie of een koppeling achter de vermelding, dan is dat een eigen
                # besluit met een eigen autorisatievraag ("wie mag wie pingen") — geen veld dat
                # hier alvast meelift.
                self._send_json({"hits": mention_hits(st, (qs.get("q") or [""])[0])})
                return
            if path == "/nav-paneel":
                # De uitklappanelen van de navigatiebalk. Puur leeswerk, altijd chrome=False:
                # dit is een fragment dat in een openstaande pagina wordt gezet, geen scherm.
                #
                # LAZY, EN DAT IS DE HELE REDEN DAT HET EEN ROUTE IS. Het paneel meerenderen met
                # elke pagina zou elk scherm laten betalen voor een projectlijst (442) en een
                # kanalenlijst (123) die je meestal niet opent.
                from nooch_village.views.navpaneel import render_nav_paneel
                _p = (qs.get("p") or [""])[0]
                _ik = _web_actor_id(username, st)
                # `hier` = de node waar je vandaan komt, zodat de boom die tak openklapt en
                # markeert. Dat deed de oude zijbalk-injectie ook; het komt nu van de client,
                # want een fragment weet niet op welke pagina het landt.
                self._send(render_nav_paneel(st, _p, _ik,
                                             q=(qs.get("q") or [""])[0],
                                             welke=(qs.get("welke") or ["mijn"])[0],
                                             hier=(qs.get("hier") or [""])[0]),
                           chrome=False)
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
            if path == "/goals":
                # AUTHZ: iedereen-ingelogd — de doelen zijn de richting van het hele dorp, dus
                # net zo leesbaar als het bord; schrijven zit achter de anchor-poort in de takken.
                self._send(render_goals(st, csrf_token=effective_csrf, username=username,
                                        msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/goal":
                # AUTHZ: iedereen-ingelogd — zie /goals.
                self._send(render_goal(st, (qs.get("id") or [""])[0], csrf_token=effective_csrf,
                                       username=username, msg=(qs.get("msg") or [""])[0]))
                return
            if path == "/site-audit":
                # De lampjes van de shop (bereikbaar, Lighthouse, claims) uit de laatste run van
                # `village site_audit`. Puur leeswerk; de run zelf draait nooit in het cockpit.
                # `?doel=dev` toont de reeks van het preview-thema (`village site_audit --dev`).
                self._send(render_site_audit(st, doel=(qs.get("doel") or ["live"])[0]))
                return
            if path == "/bronnen":
                # Aansluit-scherm voor externe databronnen (status + aan/uit).
                self._send(render_bronnen(st, os.path.dirname(data_dir), csrf_token=effective_csrf))
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
            if path == "/catalog":
                # AUTHZ: anchor-lead — het overzicht is publiek; de geïntegreerde koppel-sectie (ruw veld
                # → indicator) rendert alleen voor de curator. guest (auth-uit) telt als curator.
                actor = st.people.by_email(username) if username and username != "guest" else None
                curator = actor is None or is_circle_lead(actor.id, "mother_earth", st.assign)
                self._send(render_catalog(st, csrf_token=effective_csrf, msg=(qs.get("msg") or [""])[0],
                                          koppel=(qs.get("koppel") or [""])[0], curator=curator))
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
                                                    mw=(qs.get("mw") or ["maand"])[0],
                                                    # `group`: de projectstap onthoudt zijn
                                                    # groepering binnen het overleg. Zonder deze
                                                    # doorgifte wees 'by person' naar de
                                                    # node-pagina en verliet je de modal.
                                                    group=(qs.get("group") or [""])[0]), fr))
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
            if path == "/copy-check":
                # AUTHZ: iedereen-ingelogd — dezelfde read-scope als /copy-prompt en
                # /node?tab=policies: de checker leest de copy-policies en rapporteert, en
                # muteert niets. Een regel wijzigen blijft bij de domein-eigenaar via de
                # artefact-routes.
                self._send(render_copy_check(_Stores(data_dir), csrf_token=effective_csrf))
                return
            if path == "/decision-coach":
                # AUTHZ: iedereen-ingelogd — lezen én schrijven staan open voor elk lid. Elk lid
                # ziet elkaars decision sheets; dat is een bewuste keuze, geen omissie: een
                # voorspelling leert je pas iets als een ander hem later kan nakijken.
                # De chips versturen hun keuze als `set_<naam>`; het hidden veld draagt de
                # vorige keuze. Een klik op een chip wint dus van wat er stond — zelfde regel als
                # de segmented picker op /copy-prompt.
                _velden = {n: (qs.get("set_" + n) or qs.get(n) or [""])[-1]
                           for n, _ in decision_coach.VELDEN}
                # De rollen van de ingelogde mens, als (id, label): waaruit hij kiest bij het
                # loggen. De view leidt bemensing niet zelf af — dat weet `assignments`.
                _p = (st.people.by_email(self._session_username())
                      if self._session_username() not in (None, "guest") else None)
                _rollen = [(r, _name(st.records.get(r)) if st.records.get(r) else r)
                           for r in (st.assign.roles_of("person", _p.id) if _p else [])]
                self._send(render_decision_coach(
                    st, base_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
                    data_dir=data_dir, csrf_token=effective_csrf, waarden=_velden, rollen=_rollen,
                    melding=(qs.get("melding") or [""])[0], fout=(qs.get("fout") or [""])[0],
                    persoon=(qs.get("persoon") or [""])[0],
                    vanaf=(qs.get("vanaf") or [""])[0], tot=(qs.get("tot") or [""])[0]))
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
                # Kennisbank-bron-PDF's, geserveerd uit data/kbref/. ALLEEN NOG LEZEN: de
                # actie die hier schreef (kb_atoom_ref_pdf) is vervallen met de kennisbank-
                # schermen. De route blijft staan zodat de bestanden die er al liggen (5 op
                # productie) opvraagbaar blijven; er komt niets meer bij.
                # Basename-only tegen path-traversal; alleen .pdf. Achter de auth-check.
                fname = os.path.basename(urllib.parse.unquote(path[len("/kbref/"):]))
                full = os.path.join(data_dir, "kbref", fname)
                if not (fname.lower().endswith(".pdf") and os.path.exists(full)):
                    self._send("<p>File not found</p>", 404); return
                with open(full, "rb") as fh:
                    self._send_bytes(fh.read(), "application/pdf")
                return
            if path == "/bijlage":
                # Een bestand dat aan een BERICHT hangt. De poort is het leesrecht op het KANAAL,
                # server-side bij elk verzoek — de URL is geen sleutel: wie hem doorstuurt geeft
                # geen toegang weg, de ontvanger moet door dezelfde poort.
                from nooch_village.views.messages import mag_kanaal_lezen
                _kan = (qs.get("kanaal") or [""])[0]
                _ik = _web_actor_id(username, st)
                if not mag_kanaal_lezen(st, _kan, _ik):
                    self._send("<p>Not found</p>", 404); return    # geen 403: bestaan is ook info
                _b = st.channels.bijlage(_kan, (qs.get("id") or [""])[0])
                # EEN STICKER UIT DE VASTE RIJ LIGT IN HET PAKKET, niet in data/. Hij wordt niet
                # per bericht gekopieerd — dezelfde 100 kB bij elke high-five is zonde — dus
                # verwijst zijn `stored` naar `stickers/<naam>`. Geen pad-join op die string maar
                # een lidmaatschapstoets op `STICKERS`: dan is er niets te ontsnappen, ook niet
                # als er ooit een `..` in een opgeslagen naam belandt.
                _full = None
                if _b:
                    _st_naam = str(_b.get("stored") or "")
                    if _st_naam.startswith("stickers/") and _st_naam[9:] in STICKERS:
                        _full = os.path.join(os.path.dirname(__file__), "static", _st_naam)
                    else:
                        _full = os.path.join(data_dir, _st_naam)
                if not (_full and os.path.exists(_full)):
                    self._send("<p>File not found</p>", 404); return
                with open(_full, "rb") as fh:
                    _data = fh.read()
                _t = channels.bijlage_type(_b.get("name", ""))
                if _t is None:
                    # Op de schijf maar niet meer op de lijst (de allowlist kan krimpen). Dan
                    # downloaden als kale bytes, nooit alsnog inline.
                    _mt, _inline = "application/octet-stream", False
                else:
                    _mt, _inline = _t
                self._send_bijlage(_data, _mt, _b.get("name", "bestand"), inline=_inline)
                return
            if path == "/file":
                # DE POORT DIE HIER NIET STOND. Deze route zocht het project op, pakte de bijlage
                # en stuurde de bytes — zonder één leescheck. Elke ingelogde gebruiker kon zo elk
                # projectbestand ophalen, ook van een project met `private: True`; op productie
                # stonden er 48 bestanden achter. Gevonden bij het ontwerp van `/bijlage`
                # (22 september 2026) en in dezelfde beurt gedicht, met DEZELFDE check.
                from nooch_village.views.messages import mag_project_lezen
                _pid = (qs.get("pid") or [""])[0]
                if not mag_project_lezen(st, _pid, _web_actor_id(username, st)):
                    self._send("<p>Not found</p>", 404); return
                p = st.projects.get(_pid)
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
            # DE WEIGERING WORDT HIER GEMARKEERD, SERVER-SIDE. Een geweigerde actie reisde als
            # melding op een 303; `fetch` volgt die redirect, dus de client zag een 200 en meldde
            # "✓ moved" terwijl de server NEE zei. Vals succes, niet stille stilte.
            #
            # De markering staat hier en niet bij de ~180 aanroepers: die geven allemaal een kale
            # (nxt, msg) terug, en dit is het ene punt waar elke melding langskomt. De emoji blijft
            # voor de MENS; `ok=0` is voor de machine. Zou de client op de emoji sniffen, dan zit de
            # betekenis in een teken dat iemand ooit vervangt door een ander teken.
            if msg and is_weigering(msg):
                sep = "&" if "?" in nxt else "?"
                nxt = f"{nxt}{sep}ok=0"
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


            # ── Markdown-voorbeeld (fragment-endpoint voor de editor-werkbalk) ─────────────
            if path == "/md-preview":
                # AUTHZ: iedereen-ingelogd — dit LEEST niets en SCHRIJFT niets. Het rendert de tekst
                # die de gebruiker zelf net heeft getypt en stuurt hem terug. Geen store wordt
                # aangeraakt, dus er is niets om te beschermen behalve de sessie zelf.
                #
                # WAAROM SERVER-SIDE EN GEEN JS-RENDERER. Het voorbeeld moet exact hetzelfde tonen
                # als wat je na opslaan ziet. Een markdown-parser in JS zou een TWEEDE renderer
                # zijn naast `_md`, en die twee lopen uiteen zodra er één regel bij komt —
                # `reference, don't copy`. Bovendien escapet `_md` eerst en pas daarna de
                # opmaak-regexes; een eigen JS-versie zou dat opnieuw goed moeten doen.
                if sessions is not None and self._session_username() is None:
                    self.send_response(403); self.end_headers(); return
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                form = urllib.parse.parse_qs(raw)
                if not secrets.compare_digest((form.get("csrf") or [""])[0], csrf_token):
                    self.send_response(403); self.end_headers(); return
                tekst = (form.get("tekst") or [""])[0]
                self._send(_md(tekst[:20000]) or "<p class='muted'>Nothing to preview yet.</p>",
                           chrome=False)
                return

            # ── Project-wizard (JSON fetch-endpoints; csrf + sessie, zoals snake) ──────────
            if path in ("/wizard/sharpen", "/wizard/plan", "/wizard/create"):
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
                        # DIT WAS STIL KAPOT. Er stond `from nooch_village.kennis_context import
                        # kennis_voor, kennis_blok`, en die module is in fase 2b verdwenen. De
                        # ImportError viel in de buitenste `except`, dus de wizard logde bij ELKE
                        # plan-aanroep een exception en nam óók het deliverable-blok niet mee — dat
                        # stond binnen dezelfde try. Fail-soft mag, maar niet zó: een pad dat altijd
                        # faalt en altijd zwijgt is geen terugval, het is een dood pad met ruis.
                        # `reeds_bekend` is de vervanging die in fase 2b voor kennis_context kwam.
                        kennis, delen = "", []
                        try:
                            from nooch_village.deliverable_context import gather_deliverable_context
                            dblok = gather_deliverable_context(
                                st.projects, goal, max_notes=5, max_chars=2000,
                                store=st.deliverables) or ""
                            if dblok:
                                delen.append("Eerder afgerond onderzoek in het dorp (gebruik dit; "
                                             "plan geen items die dit al beantwoordt):\n" + dblok)
                        except Exception:
                            logging.getLogger("cockpit2.wizard").exception("deliverable-context faalde")
                        try:
                            from nooch_village import reeds_bekend
                            kblok = reeds_bekend.blok(st.dd, goal)
                            if kblok:
                                delen.append(kblok)
                        except Exception:
                            logging.getLogger("cockpit2.wizard").exception("reeds-bekend faalde")
                        kennis = "\n\n".join(delen)
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
                    # DE TITEL IS LETTERLIJK WAT DE MENS TYPTE. Hier stond `title_from(uitkomst)`: een
                    # tweede modelrondje dat de formulering nog eens samenvatte, ook als ✨ nooit was
                    # aangeraakt. Stefan (12 sep): "als ik het toevoeg laat AI de formulering nog een
                    # keer aanpassen, dat moet nooit mogen." Het model mag VÓÓR het opslaan een
                    # suggestie in het veld zetten (zichtbaar, weg te klikken); wat er bij het opslaan
                    # in het veld staat, komt zo op het bord. Geen done-when = de titel is de done-when,
                    # net als bij het kale formulier.
                    titel = g1("titel").strip()[:200]
                    if not titel:
                        self._send_json({"error": "geen titel"}, 400); return
                    # De titel is ook de done-when. Er was een apart veld; Stefan (12 sep): "kan weg,
                    # de projectformuleringen zijn al zo geschreven dat het gewenste resultaat
                    # beschreven is." Eén tekst, één plek, en het einddocument krijgt hem als kop.
                    uitkomst = titel
                    person, agent = _parse_trekker(g1("trekker"))
                    # Dezelfde cardinaliteitswet als bij proj_add — de wizard is de andere weg naar
                    # het bord, en een regel die maar op één van de twee geldt is geen regel.
                    _role = g1("role")
                    if not person and not agent and _role and not _role.startswith(_II_PREFIX):
                        person, agent, _weiger = toewijzing_bij_aanmaak(st, _role)
                        if _weiger:
                            self._send_json({"error": _weiger}, 400); return
                    missie = g1("missie") if g1("missie") in _MISSIE_IMPACT else ""
                    business = g1("business") if g1("business") in _BUSINESS_IMPACT else ""
                    # Uren: getal + eenheid, dezelfde regel als de rail (proj_seteffort). Onzin is een
                    # 400 vóór er iets bestaat, niet een half project.
                    try:
                        hours = uren_uit(g1("uren"), g1("eenheid"))
                    except ValueError:
                        self._send_json({"error": "ongeldige effort-waarde"}, 400); return
                    # Het doel, als er een gekozen is: bestaan is een voorwaarde (zelfde regel als
                    # proj_goal), het werkpakket alleen als het doel het kent.
                    doel_id = g1("doel_id").strip()
                    activiteit = ""
                    if doel_id:
                        _doel = st.doelen.get(doel_id)
                        if _doel is None:
                            self._send_json({"error": "goal not found"}, 400); return
                        activiteit = g1("activiteit").strip()
                        if activiteit not in (_doel.get("activiteiten") or []):
                            activiteit = ""
                    # De kolom van de deur: Active → actief, Waiting → geblokkeerd, anders slapend
                    # (Future). Zelfde vertaling als proj_add, want dit is de andere weg naar
                    # hetzelfde bord. Slapend is de default (scope 49): een mens sleept naar Active.
                    col = g1("col")
                    # Titel = scope, done-when = de DoD (én de kop van het einddocument).
                    from nooch_village.projects import seed_document
                    pj = st.projects
                    pid = pj.create(role, titel, "human",
                                    status=("running" if col == "actief" else "future"),
                                    done_when=uitkomst, person=person or None,
                                    agent=agent or None, missie_impact=missie,
                                    business_impact=business)
                    if col == "wacht":
                        pj.block(pid, "—")
                    if hours:
                        pj.edit(pid, allow_done=True, effort={"hours": hours})
                    if doel_id:
                        pj.set_doel(pid, doel_id, activiteit)
                    # DE LUS SLUITEN. Kwam dit project uit een spanning, dan is het project DE
                    # uitkomst van die spanning: leg hem vast met een verwijzing naar het pid en
                    # sluit de bron. Deed de wizard dit niet, dan bleef de spanning open terwijl het
                    # project al bestond — het subsidie-geval. Fail-soft: een mislukte terugkoppeling
                    # mag nooit het zojuist gemaakte project ongedaan lijken te maken.
                    # HIER STOND DE TERUGKOPPELING NAAR HET INBOX-ITEM: `add_outcome`,
                    # `mark_done` en een feed-entry "ontstaan uit een spanning in de inbox". De
                    # inbox bestaat sinds B2 niet meer, dus `nid` komt hier nooit meer binnen. De
                    # belofte die dat blok waarmaakte — een gesloten spanning is niet weg maar
                    # terug te vinden vanaf het bord — hoeft niet meer waargemaakt te worden: er
                    # wordt niets meer gesloten, en het bericht blijft in het kanaal staan.
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
                            # DE MENS-ZOEKSTAP, ook hier. De wizard is de andere weg naar het
                            # bord; de daemon zet hem bij het voorbereiden (prepare_project), en
                            # een regel die maar op één van de twee wegen geldt is geen regel.
                            from nooch_village import mens_zoekstap
                            _mens = mens_zoekstap.item_voor_de_mens(
                                [it for it in items if isinstance(it, dict)])
                            if _mens:
                                pj.check_add(pid, cl["id"], _mens["text"], skill=None, payload=None,
                                             reason=_mens["reason"], human_task=True)
                                pj.add_role_message(pid, mens_zoekstap.bericht_voor_de_mens(
                                    titel, "", mens_zoekstap.queries(items)))
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
                    self._send_json({"pid": pid, "url": f"/project?pid={pid}", "titel": titel})
                    return
                except Exception as e:
                    logging.getLogger("cockpit2.wizard").exception("wizard-endpoint %s faalde", path)
                    self._send_json({"error": str(e)}, 500)
                    return

            if path == "/copy-check":
                # AUTHZ: iedereen-ingelogd — scannen is lezen; er wordt niets geschreven.
                username = self._session_username()
                if sessions is not None and username is None:
                    self._send("Not logged in", 403); return
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                form = urllib.parse.parse_qs(raw)
                if not secrets.compare_digest((form.get("csrf") or [""])[0], csrf_token):
                    self._send("CSRF token invalid", 403); return
                self._send(render_copy_check(_Stores(data_dir), csrf_token=csrf_token,
                                             tekst=(form.get("tekst") or [""])[0]))
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
                if fields.get("action") == "kanaal_bijlage":
                    # AUTHZ: iedereen-ingelogd die in dit kanaal mag SCHRIJVEN. Dat is dezelfde
                    # voorwaarde als het antwoordveld (`kan_antwoorden`), en bewust geen tweede
                    # regel: staat er geen antwoordveld, dan staat er ook geen paperclip. Uploaden
                    # naar een kanaal dat niemand leest is hetzelfde dead letter als een bericht,
                    # maar dan eentje die 20 MB schijf kost.
                    from nooch_village.views.messages import kan_antwoorden, mag_kanaal_lezen
                    _st = _Stores(data_dir)
                    _ik = _web_actor_id(username, _st)
                    _kan = fields.get("kanaal", "")
                    if not (_ik and mag_kanaal_lezen(_st, _kan, _ik)
                            and kan_antwoorden(_st, _kan, _ik)):
                        self._send("No access to this channel", 403); return
                    err = _upload_error(files, _upload_max_bytes())
                    if err:
                        self._send(err[0], err[1]); return
                    fname, blob = files["file"]
                    safe = os.path.basename(fname).replace("\\", "_")[:120]
                    soort = channels.bijlage_type(safe)
                    if soort is None:
                        self._send("Dit bestandstype kan niet worden bijgevoegd", 415); return
                    # Het bericht eerst: de bijlage hangt aan een BERICHT, dus zonder bericht is er
                    # niets om hem aan te hangen. De tekst is het onderschrift, of anders de naam —
                    # een lege regel in de draad zegt niets over wat er gedeeld werd.
                    tekst = " ".join((fields.get("tekst") or "").split()) or f"📎 {safe}"
                    entry = _st.channels.post(_kan, tekst, author_type="human", author_id=_ik)
                    if entry is None:
                        self._send("Could not post the message", 400); return
                    bid = uuid.uuid4().hex[:10]
                    veilig_kanaal = _kan.replace(":", "_").replace("/", "_").replace("|", "_")
                    rel = os.path.join("kanaalbijlagen", veilig_kanaal, bid + "_" + safe)
                    full = os.path.join(data_dir, rel)
                    os.makedirs(os.path.dirname(full), exist_ok=True)
                    with open(full, "wb") as fh:
                        fh.write(blob)
                    _st.channels.add_bijlage(_kan, entry["id"], {
                        "id": bid, "name": safe, "stored": rel, "size": len(blob),
                        "mime": soort[0], "at": time.time()})
                    self._redirect(fields.get("next", "/messages"), "📎 bijlage toegevoegd"); return
                if fields.get("action") in _KB_UPLOAD_WEG:
                    # AUTHZ: iedereen-ingelogd — zelfde poort als de oude kennisbank-intake had.
                    # NIET BESCHIKBAAR, GEEN CRASH. Deze drie acties (kb_intake_pdf,
                    # kb_atoom_ref_pdf, kb_bron_add) hoorden bij de kennisbank-schermen die in
                    # #516 zijn verwijderd — met de views verdwenen ook kennisbank_intake
                    # (`kb_intake`/`atomiseer`) en de stores `notes` en `staging`. De takken
                    # bleven staan en riepen namen aan die niet meer bestaan: de handler gooide
                    # NameError/AttributeError en de verbinding werd verbroken zónder antwoord
                    # (curl: status 000). Er is geen knop meer die hier post; dit vangt een oud
                    # tabblad of een bookmark op met een leesbare melding in plaats van een dode
                    # verbinding. Terug bouwen = de schermen terug bouwen, niet een import.
                    self._redirect(fields.get("next", "/"),
                                   "✗ knowledge-base intake is unavailable — the knowledge-base "
                                   "screens were removed on 20 September 2026")
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
    # Ook het CSRF-token overleeft de herstart. Anders blijft een tab die openstond tijdens een
    # deploy 403 krijgen — alleen met een andere tekst, en voor de mens is dat hetzelfde.
    csrf_token = _auth.load_or_create_csrf(os.path.join(dd, "csrf.json"))
    users    = _auth.UserStore(os.path.join(dd, "people.json"))
    # PERSISTENT: sessies moeten een deploy overleven. Leefden ze in het geheugen, dan logde elke
    # herstart iedereen uit — en tot #425 zag je dat niet eens, want de drawer slikte de 403.
    sessions = _auth.SessionStore(os.path.join(dd, "sessions.json"))
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


# De drie upload-acties van de verwijderde kennisbank-intake. Ze staan hier als NAMEN en niet
# als werkende takken: de schermen, de atomiser (kennisbank_intake) en de stores `notes` en
# `staging` zijn in #516 verwijderd, dus er is niets meer om naartoe te posten. Zie de tak in
# do_POST voor waarom ze niet gewoon vervallen zijn.
_KB_UPLOAD_WEG = ("kb_intake_pdf", "kb_atoom_ref_pdf", "kb_bron_add")


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


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="nooch_village.cockpit2")
    ap.add_argument("cmd", nargs="?", default="serve", choices=["serve"],
                    help="serve = cockpit")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--data-dir", default=None)
    a = ap.parse_args(argv)
    serve(host=a.host, port=a.port, data_dir=a.data_dir)


if __name__ == "__main__":
    main()
