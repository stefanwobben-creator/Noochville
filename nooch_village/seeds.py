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
    {
        "concept_id": "leather_free",
        "words": {"nl": "leervrij", "en": "leather free"},
        "status": "approved",
        "rationale": "Geen leer is een harde beleidsregel; leervrij/leather free is missie-kern, niet een leer-risico.",
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
                  members=["website_watcher", "librarian", "trends", "facilitator",
                           "concurrent_scout"])
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
                           skills=["keyword_review", "library_lookup", "verband_voorstel",
                                   "keywords_everywhere"]))
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
    scout = Record(id="concurrent_scout", type=RecordType.ROLE, parent="noochville",
                   definition=RoleDefinition(
                       purpose="Observeert de duurzame-sneakermarkt en signaleert "
                               "strategische bewegingen van directe concurrenten",
                       accountabilities=["concurrentienieuws monitoren (funding, lanceringen, "
                                         "B-Corp, materiaalinnovatie)",
                                         "een wekelijks field report schrijven",
                                         "missie-relevante zetten als spanning signaleren"],
                       skills=["competitor_news", "competitor_discover",
                               "linkbuilding_targets"]),
                   persona="Sven Spruce")
    for r in (root, watcher, librarian, trends, facilitator, scout):
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
        # Idempotent: voeg cadans-accountability toe als die ontbreekt
        fac = records.get("facilitator")
        if "de dagcyclus omroepen" not in fac.definition.accountabilities:
            fac.definition.accountabilities.insert(0, "de dagcyclus omroepen")
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
    # (De oude demote-regel voor 'content_strategist' is verwijderd: die degradeerde
    #  een sensed content_strategist naar 'demo'. De Content Strategist wordt nu via
    #  het echte governance-proces geboren — zie nooch_village/role_proposals.py — en
    #  mag dus niet automatisch naar demo worden gezet.)
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
    # Concurrent-scout: nieuwe inwoner die de markt observeert (idempotent geboren + bemenst,
    # CLASS_MAP heeft de entry, dus de Reconciler activeert 'm direct).
    if records.get("concurrent_scout") is None:
        scout = Record(id="concurrent_scout", type=RecordType.ROLE, parent=root.id,
                       definition=RoleDefinition(
                           purpose="Observeert de duurzame-sneakermarkt en signaleert "
                                   "strategische bewegingen van directe concurrenten",
                           accountabilities=["concurrentienieuws monitoren (funding, lanceringen, "
                                             "B-Corp, materiaalinnovatie)",
                                             "een wekelijks field report schrijven",
                                             "missie-relevante zetten als spanning signaleren"],
                           skills=["competitor_news"]),
                       persona="Sven Spruce")
        scout.source = "seed"
        records.put(scout)
        changed = True
    if "concurrent_scout" not in root.members:
        root.members.append("concurrent_scout")
        changed = True
    # Zorg dat de scout ook de ontdek-skill heeft (idempotent, voor bestaande records).
    scout_rec = records.get("concurrent_scout")
    if scout_rec is not None:
        scout_changed = False
        for sk in ("competitor_discover", "linkbuilding_targets"):
            if sk not in scout_rec.definition.skills:
                scout_rec.definition.skills.append(sk)
                scout_rec.version += 1
                scout_changed = True
        if scout_changed:
            records.put(scout_rec)
            changed = True
    # Zorg dat de Librarian KeywordsEverywhere heeft: hij verrijkt elke kandidaat centraal
    # met echt zoekvolume vóór de beoordeling (idempotent).
    librarian = records.get("librarian")
    if librarian is not None and "keywords_everywhere" not in librarian.definition.skills:
        librarian.definition.skills.append("keywords_everywhere")
        librarian.version += 1
        records.put(librarian)
        changed = True
    # Zorg dat Harry de onderzoeksvraag-skill heeft voor de verdiep-lus (idempotent)
    harry = records.get("harry_hemp")
    if harry is not None and "onderzoeksvraag" not in harry.definition.skills:
        harry.definition.skills.append("onderzoeksvraag")
        records.put(harry)
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
    if "the_source" not in root.members:
        root.members.append("the_source")
        changed = True

    # ── Persona's: centrale bron, herstelt verlies na save/_load ─────────────
    _PERSONAS = {
        "website_watcher": "Corry Coconut",
        "trends":          "Maisy Mushroom",
        "facilitator":     "Rupert Rubber",
        "harry_hemp":      "Harry Hemp",
        "the_source":      "Stefan",
    }
    for _rid, _persona in _PERSONAS.items():
        _rec = records.get(_rid)
        if _rec is not None and not _rec.archived and _rec.persona != _persona:
            _rec.persona = _persona
            _rec.version += 1
            records.put(_rec)
            changed = True

    if changed:
        records.put(root)

