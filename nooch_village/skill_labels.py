"""Skills in mensentaal.

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
    # ── Luisteren en volgen ──────────────────────────────────────────────
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

    # ── Zoeken en onderbouwen ────────────────────────────────────────────
    "openalex_evidence": "Zoekt wetenschappelijk bewijs in de academische literatuur",
    "semscholar_tldr": "Vat wetenschappelijke papers samen tot één zin",
    "openlibrary_search_inside": "Zoekt in de volledige tekst van boeken",
    "epo_patents": "Doorzoekt het Europese patentregister",
    "google_patents": "Doorzoekt patenten wereldwijd",
    "claim_evidence": "Controleert of een merk zijn duurzaamheidsclaim kan waarmaken",
    "kroniek_interpret": "Leest terug wat we eerder onderzochten en wat dat opleverde",

    # ── Zoekwoorden en vindbaarheid ──────────────────────────────────────
    "gsc_performance": "Kijkt waarop mensen ons vinden in Google",
    "gsc_report": "Schrijft de zoekverkeer-nota",
    "keywords_everywhere": "Hangt echt zoekvolume aan wat hij tegenkomt",
    "keyword_review": "Beoordeelt of een zoekwoord bij de missie past",
    "library_lookup": "Zoekt op wat we van een woord vinden",
    "library_list": "Somt de woorden op die we goedkeurden of verboden",
    "linkbuilding_targets": "Vindt sites en lijstjes waar we genoemd willen worden",
    "plausible_stats": "Telt hoeveel mensen de site bezoeken",
    "site_health": "Kijkt of de site nog overeind staat",

    # ── Schrijven en toetsen ─────────────────────────────────────────────
    "content_schrijven": "Schrijft website-tekst in de stem van het merk",
    "content_check": "Leest publieke tekst na op verboden en onbewezen claims",
    "claims_check": "Toetst tekst aan de Europese regels voor duurzaamheidsclaims",
    "claims_site_scan": "Scant onze eigen site wekelijks op riskante claims",
    "regulation_watch": "Merkt maandelijks of de wet onder ons is verschoven",
    "bulletin_schrijven": "Schrijft het dagelijkse dorpsbulletin",
    "field_note": "Duidt de cijfers van vandaag tegen de missie",
    "voorstel_schrijven": "Werkt een vaag gevoel uit tot een concreet voorstel",

    # ── Kennis ordenen ───────────────────────────────────────────────────
    "curate": "Snijdt ruwe input tot losse, scherpe inzicht-kaartjes",
    "atomic_insights": "Haalt het patroon achter de losse datapunten vandaan",
    "verband_voorstel": "Ziet of twee kaartjes iets met elkaar te maken hebben",
    "onderzoeksvraag": "Leidt uit een trend de vraag af waarom die trend er is",

    # ── Bedrijfsvoering ──────────────────────────────────────────────────
    "shopify_sales": "Leest hoeveel paren er verkocht zijn",
    "co2_village": "Rekent uit hoeveel CO2 het denkwerk van het dorp kostte",
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
