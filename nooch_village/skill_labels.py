"""Skills in mensentaal (Engels — de inhoudslaag is Engels sinds 06-09-2026).

De `description` op een `Skill` is voor de LLM en de ontwikkelaar geschreven: technisch, met
API-namen en formaatafspraken erin. Een dossier is voor een mens die wil weten wát deze inwoner
kan. Daarom één zin per skill, actief, zonder jargon — en de technische naam blijft eronder staan
zodat de brug tussen beide werelden zichtbaar blijft.

Eén centrale map (niet een veld op elke Skill-klasse): zo staan alle zinnen naast elkaar en zie
je meteen of de toon consistent is. Ontbreekt een skill hier, dan valt hij terug op zijn eigen
`description` — nooit op een lege regel.
"""
from __future__ import annotations

LABELS: dict[str, str] = {
    # ── Listening and tracking ──────────────────────────────────────────────
    "community_listening": "Listens on Reddit, Bluesky and YouTube to what people actually say",
    "competitor_news": "Follows the news about our competitors",
    "competitor_discover": "Spots new brands appearing on our field",
    "gdelt_tone": "Measures how the world press writes about our themes",
    "trends_categorie": "Tracks how much our themes are searched for",
    "google_trends": "Looks at what people search for, per country and language",
    "serpapi_trends": "Search volume from a paid, reliable source",
    "trend_reindex": "Tells a real emerging trend from a one-day wonder",
    "ngram_culture": "Tracks how language shifts over decades across millions of books",
    "alphavantage_index": "Follows the share prices of the sustainable index funds",

    # ── Searching and substantiating ────────────────────────────────────────────
    "openalex_evidence": "Finds scientific evidence in the academic literature",
    "semscholar_tldr": "Boils a scientific paper down to one sentence",
    "openlibrary_search_inside": "Searches the full text of books",
    "epo_patents": "Searches the European patent register",
    "google_patents": "Searches patents worldwide",
    "claim_evidence": "Checks whether a brand can back up its sustainability claim",
    "cert_evidence": "Reads a certificate and files it as external evidence",
    "kroniek_interpret": "Reads back what we researched before and what it produced",

    # ── Keywords and findability ──────────────────────────────────────
    "gsc_performance": "Looks at what people find us on in Google",
    "gsc_report": "Writes the search traffic note",
    "keywords_everywhere": "Attaches real search volume to what it comes across",
    "keyword_review": "Judges whether a keyword fits the mission",
    "library_lookup": "Looks up what we think of a word",
    "library_list": "Lists the words we approved or banned",
    "linkbuilding_targets": "Finds sites and lists we want to be mentioned on",
    "plausible_stats": "Counts how many people visit the site",
    "site_health": "Checks whether the site is still standing",
    "haal_pagina": "Fetches a page and quotes the sentence a word appears in",
    "web_zoek": "Searches the open web and reads the pages it finds",
    "zoekstrategie": "Decides which sources to search, with which term and in which language",

    # ── Writing and checking ─────────────────────────────────────────────
    "content_schrijven": "Writes website copy in the brand's voice",
    "content_check": "Reviews public text for banned and unproven claims",
    "claims_check": "Tests text against the European rules for sustainability claims",
    "claims_site_scan": "Scans our own site weekly for risky claims",
    "regulation_watch": "Notices monthly whether the law has shifted under us",
    "materiaal_kwartaal": "Reports quarterly where material innovation is moving",
    "materiaal_shortlist": "Nominates 1-2 materials a month to request a sample of",
    "bulletin_schrijven": "Writes the daily village bulletin",
    "field_note": "Reads today's numbers against the mission",
    "voorstel_schrijven": "Works a vague hunch up into a concrete proposal",

    # ── Ordering knowledge ───────────────────────────────────────────────────
    "curate": "Cuts raw input into separate, sharp insight cards",
    "atomic_insights": "Pulls the pattern behind the individual data points",
    "verband_voorstel": "Sees whether two cards have anything to do with each other",
    "onderzoeksvraag": "Derives from a trend the question of why that trend exists",

    # ── Working together and self-checking ──────────────────────────────────────
    "weten_we_dit_al": "Checks first whether we already have the answer somewhere",
    "ruis_check": "Notices when a search is too broad to mean anything",
    "tegenspraak": "Argues against its own work before calling it done",
    "projectverzoek": "Puts work that belongs to another role on their board",
    "escaleer": "Brings an outcome or a decision to the right role or to a human",

    # ── Business operations ──────────────────────────────────────────────────
    "shopify_sales": "Reads how many pairs were sold",
    "co2_village": "Works out how much CO2 the village's thinking cost",
}


def label(skill_naam: str, registry=None) -> str:
    """De mensentaal-zin voor een skill. Ontbreekt die, dan de eigen omschrijving van de
    skill (afgekapt); bestaat de skill niet, dan de naam zelf — nooit een lege regel."""
    zin = LABELS.get(skill_naam)
    if zin:
        return zin
    try:
        registry = registry if registry is not None else _registry()
        skill = registry.get(skill_naam)
        if skill is not None and getattr(skill, "description", ""):
            eerste = str(skill.description).split(". ")[0].strip()
            return eerste[:120]
    except Exception:
        pass
    return skill_naam


def _registry():
    from nooch_village.registry_factory import shared_registry
    return shared_registry()


def ontbrekend(registry=None) -> list[str]:
    """Welke geregistreerde skills missen nog een mensentaal-zin? Voor de guard-test."""
    try:
        registry = registry if registry is not None else _registry()
        return sorted(n for n in registry.names() if n not in LABELS)
    except Exception:
        return []

# ── De matching-brug (overgang) ───────────────────────────────────────
# LABELS is sinds 06-09-2026 Engels; de inhoudslaag ging om. Maar `skills_naar_links` gebruikt
# het label als BRUG tussen een Engelse capability-id (`keywords_everywhere`) en de
# accountability-tekst van een rol ("zoekvolume bijhouden"). Die teksten zijn MANDAAT: ze staan in
# governance-records en veranderen alleen via een governance-ronde, niet met een commit. Ze zijn dus
# nog Nederlands, en blijven dat tot jij ze door de poort haalt.
#
# Vertaalden we de brug mee, dan zou de matcher stil op nul uitkomen: Engelse labels en Nederlandse
# beloftes delen geen tokens. Geen foutmelding, alleen "geen enkel middel past bij deze belofte" —
# precies het soort stille uitval waar dit systeem al vaker op is gestruikeld.
#
# Daarom deze tweede kaart: ALLEEN voor matchen, nooit voor weergave. Hij mag weg zodra de
# accountabilities via governance Engels zijn; dan valt `match_label` vanzelf terug op LABELS.
MATCH_NL: dict[str, str] = {
    "community_listening": "Luistert op Reddit, Bluesky en YouTube naar wat mensen echt zeggen",
    "competitor_news": "Volgt het nieuws over de concurrentie",
    "competitor_discover": "Spot nieuwe merken die op ons speelveld verschijnen",
    "gdelt_tone": "Meet hoe de wereldpers over onze thema's schrijft",
    "trends_categorie": "Houdt bij hoeveel er op onze thema's gezocht wordt",
    "google_trends": "Kijkt waar mensen op zoeken, per land en per taal",
    "serpapi_trends": "Zoekvolume via een betaalde, betrouwbare bron",
    "trend_reindex": "Onderscheidt een echte opkomende trend van een eendagsvlieg",
    "ngram_culture": "Volgt hoe taal over decennia verschuift in miljoenen boeken",
    "alphavantage_index": "Volgt de beurskoersen van de duurzame index-fondsen",
    "openalex_evidence": "Zoekt wetenschappelijk bewijs in de academische literatuur",
    "semscholar_tldr": "Vat wetenschappelijke papers samen tot één zin",
    "openlibrary_search_inside": "Zoekt in de volledige tekst van boeken",
    "epo_patents": "Doorzoekt het Europese patentregister",
    "google_patents": "Doorzoekt patenten wereldwijd",
    "claim_evidence": "Controleert of een merk zijn duurzaamheidsclaim kan waarmaken",
    "cert_evidence": "Leest een certificaat en legt het als extern bewijs vast",
    "kroniek_interpret": "Leest terug wat we eerder onderzochten en wat dat opleverde",
    "gsc_performance": "Kijkt waarop mensen ons vinden in Google",
    "gsc_report": "Schrijft de zoekverkeer-nota",
    "keywords_everywhere": "Hangt echt zoekvolume aan wat hij tegenkomt",
    "keyword_review": "Beoordeelt of een zoekwoord bij de missie past",
    "library_lookup": "Zoekt op wat we van een woord vinden",
    "library_list": "Somt de woorden op die we goedkeurden of verboden",
    "linkbuilding_targets": "Vindt sites en lijstjes waar we genoemd willen worden",
    "plausible_stats": "Telt hoeveel mensen de site bezoeken",
    "site_health": "Kijkt of de site nog overeind staat",
    "haal_pagina": "Haalt een pagina op en citeert de zin waarin een woord staat",
    "web_zoek": "Zoekt op het open web en leest de paginas die hij vindt",
    "zoekstrategie": "Bepaalt welke bronnen doorzocht worden, met welke term en in welke taal",
    "content_schrijven": "Schrijft website-tekst in de stem van het merk",
    "content_check": "Leest publieke tekst na op verboden en onbewezen claims",
    "claims_check": "Toetst tekst aan de Europese regels voor duurzaamheidsclaims",
    "claims_site_scan": "Scant onze eigen site wekelijks op riskante claims",
    "regulation_watch": "Merkt maandelijks of de wet onder ons is verschoven",
    "materiaal_kwartaal": "Vertelt per kwartaal waar materiaalinnovatie beweegt",
    "materiaal_shortlist": "Draagt maandelijks 1-2 materialen voor om een sample van aan te vragen",
    "bulletin_schrijven": "Schrijft het dagelijkse dorpsbulletin",
    "field_note": "Duidt de cijfers van vandaag tegen de missie",
    "voorstel_schrijven": "Werkt een vaag gevoel uit tot een concreet voorstel",
    "curate": "Snijdt ruwe input tot losse, scherpe inzicht-kaartjes",
    "atomic_insights": "Haalt het patroon achter de losse datapunten vandaan",
    "verband_voorstel": "Ziet of twee kaartjes iets met elkaar te maken hebben",
    "onderzoeksvraag": "Leidt uit een trend de vraag af waarom die trend er is",
    "weten_we_dit_al": "Kijkt eerst of we het antwoord al ergens hebben liggen",
    "ruis_check": "Merkt wanneer een zoekopdracht te breed is om iets te betekenen",
    "tegenspraak": "Spreekt het eigen werk kritisch tegen vóór het 'klaar' heet",
    "projectverzoek": "Zet werk dat bij een andere rol hoort op diens bord",
    "escaleer": "Brengt een uitkomst of een beslissing bij de juiste rol of bij de mens",
    "shopify_sales": "Leest hoeveel paren er verkocht zijn",
    "co2_village": "Rekent uit hoeveel CO2 het denkwerk van het dorp kostte",
}


def match_label(skill_naam: str) -> str:
    """Het label waarop DETERMINISTISCH gematcht wordt tegen (nog Nederlandse) beloftetekst."""
    return MATCH_NL.get(skill_naam) or label(skill_naam)
