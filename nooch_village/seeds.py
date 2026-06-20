"""Seed- en migratiefuncties voor governance-records en lexicon.

Alles hier is idempotent: veilig om bij elke Village-start aan te roepen.
"""
from __future__ import annotations
from nooch_village.governance import Records
from nooch_village.lexicon import Lexicon
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.mission import ANCHOR_PURPOSE as _ANCHOR_PURPOSE
from nooch_village.policy import ANCHOR_POLICY_PROSE as _ANCHOR_POLICIES

# ── Lexicon-zaad ──────────────────────────────────────────────────────────────

_LEXICON_SEED = [
    {
        "concept_id": "burger_frame",
        "words": {"nl": "burger", "en": "citizen"},
        "status": "avoid",
        "rationale": (
            "'burger' NL geeft hamburger-gerelateerde Trends-ruis en is als zoekterm "
            "onbruikbaar. Concept blijft in het lexicon als referentie, maar niet als "
            "actieve zoekterm."
        ),
    },
    {
        "concept_id": "conscious_consumer",
        "words": {"nl": "bewuste consument", "en": "conscious consumer"},
        "status": "approved",
        "rationale": (
            "Bewuste consument / conscious consumer beschrijft de doelgroep van Nooch: "
            "mensen die actief kiezen voor ethische, duurzame producten. "
            "Missie-aligned SEO-term in zowel NL als EN."
        ),
    },
    {
        "concept_id": "consumer_frame",
        "words": {"nl": "consument", "en": "consumer"},
        "status": "avoid",
        "rationale": (
            "Consumentenkader versterkt passiviteit en extractief gedrag; burgerframe "
            "heeft voorkeur. Symmetrisch: avoid in NL én EN."
        ),
    },
    {
        "concept_id": "sufficiency",
        "words": {"nl": "soberheid", "en": "sufficiency"},
        "status": "approved",
        "rationale": "Sufficiencybeweging sluit aan bij missie: minder verbruik als waarde.",
    },
    {
        "concept_id": "regenerative",
        "words": {"nl": "regeneratief", "en": "regenerative"},
        "status": "approved",
        "rationale": "Regeneratief ontwerp is een kernterm voor de positieve missierichting.",
    },
    {
        "concept_id": "plastic_free",
        "words": {"nl": "plasticvrij", "en": "plastic-free"},
        "status": "approved",
        "rationale": "Geen plastic is een harde beleidsregel én een SEO-kans in beide talen.",
    },
    {
        "concept_id": "sustainable",
        "words": {"nl": "duurzaam", "en": "sustainable"},
        "status": "approved",
        "rationale": "Kernwoord voor duurzame schoenenmissie in NL en EN.",
    },
    {
        "concept_id": "vegan",
        "words": {"nl": "veganistisch", "en": "vegan"},
        "status": "approved",
        "rationale": "Geen dierenleer is beleidsregel; vegan/veganistisch missie-aligned.",
    },
]


def seed_lexicon(lexicon: Lexicon) -> None:
    """Seed het meertalige lexicon idempotent met de zaad-concepten."""
    import logging
    added = lexicon.seed(_LEXICON_SEED)
    _migrate_lexicon(lexicon)
    if added:
        logging.getLogger("village.lexicon").info(
            "lexicon geseeded: %d nieuwe concepten", added)


def _migrate_lexicon(lexicon: Lexicon) -> None:
    """Pas bekende lexicon-correcties toe op bestaande data/lexicon.json. Idempotent."""
    c = lexicon.concept("burger_frame")
    if c and c.get("status") == "approved":
        lexicon.add_concept(
            "burger_frame", words=c["words"], status="avoid",
            rationale=(
                "'burger' NL geeft hamburger-gerelateerde Trends-ruis en is als zoekterm "
                "onbruikbaar."
            ),
            by="migrate",
        )
    if lexicon.concept("conscious_consumer") is None:
        lexicon.add_concept(
            "conscious_consumer",
            words={"nl": "bewuste consument", "en": "conscious consumer"},
            status="approved",
            rationale=(
                "Bewuste consument / conscious consumer beschrijft de doelgroep van Nooch."
            ),
            by="migrate",
        )


# ── Governance-seeds ──────────────────────────────────────────────────────────

def seed_records(records: Records) -> None:
    """Schrijf de vijf seed-rollen als er nog geen wortelcirkel is. Idempotent."""
    if records.root() is not None:
        return
    root = Record(id="noochville", type=RecordType.CIRCLE, parent=None,
                  definition=RoleDefinition(
                      purpose=_ANCHOR_PURPOSE, skills=[],
                      policies=_ANCHOR_POLICIES),
                  members=["website_watcher", "librarian", "trends", "facilitator"])
    watcher = Record(id="website_watcher", type=RecordType.ROLE, parent="noochville",
                     definition=RoleDefinition(
                         purpose="Bewaakt de online gezondheid en groei van Nooch.earth",
                         accountabilities=["site monitoren", "bezoekersdata duiden",
                                           "dagelijkse Field Note schrijven"],
                         skills=["site_health", "plausible_stats", "google_trends", "field_note"]),
                     persona="Corry Coconut")
    librarian = Record(id="librarian", type=RecordType.ROLE, parent="noochville",
                       definition=RoleDefinition(
                           purpose="Hoeder van de goedgekeurde woordenschat (DOMEIN: bibliotheek)",
                           accountabilities=["kandidaat-woorden beoordelen",
                                             "twijfelgevallen escaleren naar een mens"],
                           domains=["bibliotheek"],
                           skills=["keyword_review", "library_lookup"]))
    trends = Record(id="trends", type=RecordType.ROLE, parent="noochville",
                    definition=RoleDefinition(
                        purpose="Ontdekt kansen in Google Search Console en voedt de woordenschat",
                        accountabilities=["GSC-queries ophalen",
                                          "high_potential queries voorstellen aan de Librarian"],
                        skills=["gsc_performance", "gsc_report"]),
                    persona="Maisy Mushroom")
    facilitator = Record(id="facilitator", type=RecordType.ROLE, parent="noochville",
                         definition=RoleDefinition(
                             purpose="Bewaakt de geldigheid van governance-voorstellen "
                                     "zonder inhoudelijk te oordelen",
                             accountabilities=["de dagcyclus omroepen",
                                               "voorstellen toetsen op G0-G4",
                                               "geldige voorstellen direct aannemen",
                                               "risicovolle voorstellen escaleren naar de mens"],
                             skills=[]),
                         persona="Rupert Rubber")
    for r in (root, watcher, librarian, trends, facilitator):
        r.source = "seed"
        records.put(r)


def migrate_records(records: Records) -> None:
    """Voeg ontbrekende leden + records toe aan bestaande governance-files. Idempotent."""
    root = records.root()
    if root is None:
        return
    changed = False
    if records.get("facilitator") is None:
        facilitator = Record(id="facilitator", type=RecordType.ROLE, parent=root.id,
                             definition=RoleDefinition(
                                 purpose="Bewaakt de geldigheid van governance-voorstellen "
                                         "zonder inhoudelijk te oordelen",
                                 accountabilities=["de dagcyclus omroepen",
                                                   "voorstellen toetsen op G0-G4",
                                                   "geldige voorstellen direct aannemen",
                                                   "risicovolle voorstellen escaleren naar de mens"],
                                 skills=[]),
                             persona="Rupert Rubber")
        records.put(facilitator)
        changed = True
    else:
        # Idempotent: voeg cadans-accountability en persona toe als ze ontbreken
        fac = records.get("facilitator")
        fac_changed = False
        if "de dagcyclus omroepen" not in fac.definition.accountabilities:
            fac.definition.accountabilities.insert(0, "de dagcyclus omroepen")
            fac_changed = True
        if fac.persona != "Rupert Rubber":
            fac.persona = "Rupert Rubber"
            fac_changed = True
        if fac_changed:
            fac.version += 1
            records.put(fac)
            changed = True
    if "facilitator" not in root.members:
        root.members.append("facilitator")
        changed = True
    # Verwijder timekeeper uit members als hij er nog in zit (absorptie)
    if "timekeeper" in root.members:
        root.members.remove("timekeeper")
        changed = True
    tk = records.get("timekeeper")
    if tk is not None and not tk.archived:
        tk.archived = True
        tk.version += 1
        records.put(tk)
        changed = True
    existing_policies = set(root.definition.policies)
    for policy in _ANCHOR_POLICIES:
        if policy not in existing_policies:
            root.definition.policies.append(policy)
            changed = True
    if root.definition.purpose != _ANCHOR_PURPOSE:
        root.definition.purpose = _ANCHOR_PURPOSE
        changed = True
    cs = records.get("content_strategist")
    if cs is not None and cs.source == "sensed":
        cs.source = "demo"
        records.put(cs)
        changed = True
    _SEED_IDS = {"noochville", "website_watcher", "librarian", "trends", "facilitator"}
    for sid in _SEED_IDS:
        rec = records.get(sid)
        if rec is not None and rec.source == "sensed":
            rec.source = "seed"
            records.put(rec)
            changed = True
    # Zorg dat trends de gsc_report-skill heeft (idempotent)
    trends = records.get("trends")
    if trends is not None and "gsc_report" not in trends.definition.skills:
        trends.definition.skills.append("gsc_report")
        records.put(trends)
        changed = True
    # ── Noochie absorbeert Ronnie's bulletin-mandaat ──────────────────────────
    noochie = records.get("noochie")
    if noochie is not None:
        _NOOCHIE_PURPOSE = (
            "De droom van NoochVille levend houden in het dagelijkse dorp, "
            "en de brug zijn tussen The Source en de bewoners."
        )
        _NOOCHIE_ACCOUNTABILITIES = [
            "de missie levend houden door elke veld-notitie tegen de missie te wegen",
            "de brug zijn tussen The Source en het dorp, en The Source scherp houden",
            "creatieve governance-voorstellen aandragen, met de voorwaarde waaronder een voorstel kantelt",
            "het dagelijkse dorpsbulletin schrijven uit de village-events",
        ]
        noochie_changed = False
        if noochie.definition.purpose != _NOOCHIE_PURPOSE:
            noochie.definition.purpose = _NOOCHIE_PURPOSE
            noochie_changed = True
        if noochie.definition.accountabilities != _NOOCHIE_ACCOUNTABILITIES:
            noochie.definition.accountabilities = _NOOCHIE_ACCOUNTABILITIES
            noochie_changed = True
        if "bulletin_schrijven" not in noochie.definition.skills:
            noochie.definition.skills.append("bulletin_schrijven")
            noochie_changed = True
        if noochie_changed:
            records.put(noochie)
            changed = True
    # ── Ronnie archiveren (audittrail bewaard, geen hard verwijderen) ─────────
    ronnie = records.get("ronnie")
    if ronnie is not None and not ronnie.archived:
        ronnie.archived = True
        records.put(ronnie)
        changed = True
    if "ronnie" in root.members:
        root.members.remove("ronnie")
        changed = True

    # ── Junk-records archiveren (sensed governance-experimenten) ──────────────
    _JUNK_IDS = [
        "missie-alignment_missie-gedreven_transparantie",
        "veganistisch_missie-lens_niche-label",
        "missie-alignment_marketingtruc_veganistisch",
    ]
    for junk_id in _JUNK_IDS:
        junk = records.get(junk_id)
        if junk is not None and not junk.archived:
            junk.archived = True
            junk.version += 1
            records.put(junk)
            changed = True
        if junk_id in root.members:
            root.members.remove(junk_id)
            changed = True

    # ── The Source: de menselijke founding rol ────────────────────────────────
    if records.get("the_source") is None:
        the_source = Record(
            id="the_source",
            type=RecordType.ROLE,
            parent=root.id,
            definition=RoleDefinition(
                purpose=(
                    "De droom van NoochVille bedenken en iedereen enthousiast maken "
                    "om deze droom samen waar te maken."
                ),
                accountabilities=[
                    "de richting van NoochVille bepalen",
                    "de levende grens bewaken waar geen regel het zegt, en de residuele "
                    "verantwoordelijkheid dragen die geen enkele rol bezit, waaronder het "
                    "bijwerken van de materiaal-policy en de locale-policy",
                    "knopen doorhakken na overleg en met uitleg",
                    "vrijheid geven aan de inwoners",
                    "middelen en geld verdelen",
                    "de score bijhouden",
                    "een vangnet zijn",
                ],
                skills=[],
            ),
            source="seed",
            persona="Stefan",
        )
        records.put(the_source)
        changed = True
    else:
        # Idempotent: zet persona als die ontbreekt (bijv. na _load zonder persona-veld)
        ts = records.get("the_source")
        if ts.persona != "Stefan":
            ts.persona = "Stefan"
            ts.version += 1
            records.put(ts)
            changed = True
    if "the_source" not in root.members:
        root.members.append("the_source")
        changed = True

    if changed:
        records.put(root)


def activate_tijdgeest_wachter(records: Records) -> None:
    """Idempotent: voeg ngram_culture toe aan tijdgeest_wachter zodra het record bestaat."""
    rec = records.get("tijdgeest_wachter")
    if rec is None or rec.archived:
        return
    if "ngram_culture" not in rec.definition.skills:
        rec.definition.skills.append("ngram_culture")
        records.put(rec)


def activate_kennis_scout(records: Records) -> None:
    """Idempotent: zet v1-skills in kennis_scout-record zodra het bestaat."""
    rec = records.get("kennis_scout")
    if rec is None or rec.archived:
        return
    _V1  = ["openalex_evidence", "semscholar_tldr"]
    _OLD = ["openalex", "semantic_scholar", "openlibrary_search_inside"]
    changed = False
    for old in _OLD:
        if old in rec.definition.skills:
            rec.definition.skills.remove(old)
            changed = True
    for s in _V1:
        if s not in rec.definition.skills:
            rec.definition.skills.append(s)
            changed = True
    if changed:
        records.put(rec)
