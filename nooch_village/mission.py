"""Canonieke missietekst van Nooch.earth — één bron voor het hele dorp.

De tekst is Engels (i18n fase 2A): hij voedt UITSLUITEND LLM-prompts en de purpose van een
VERS geseede wortelcirkel. Een bestaande root-purpose in de records wordt nooit overschreven
(seeds.py vult alleen als hij leeg is) — die wijzigen is founder-werk via G4.

Importeer ANCHOR_PURPOSE overal waar de missie nodig is:
governance (G4 LLM-prompt), roles (Noochie), village (wortelcirkel).
"""
import re

ANCHOR_PURPOSE = (
    "Nooch.earth is the most sustainable shoe brand in the world — to show an industry full of "
    "human, animal and planetary suffering that meliorism (always being able to do better) "
    "is real, and to inspire customers and others to set something positive in motion. "
    "Core values: no plastic, no leather, made in Europe, made to order, fair price, "
    "transparency. Growth through mission-driven organic content on nooch.earth."
)

# ── Strategie-thema's: de kernwaarden uit ANCHOR_PURPOSE, uitgeschreven naar trefwoorden zodat we
# DETERMINISTISCH (geen LLM) kunnen meten hoe strategisch relevant een tekst/kaartje is. Bewerk deze
# lijst om de focus bij te sturen (bijv. dit kwartaal extra op composteerbaarheid) — het is de enige
# plek waar de weging van de kennisbank-voorstellen aan hangt. Label = wat de gebruiker op de kaart
# ziet; termen = de trefwoorden (exacte token-match, of prefix voor termen ≥ 5 tekens: 'composteer'
# vangt 'composteerbaar'). ─────────────────────────────────────────────────────────────────────────
# TWEETALIG, EN ADDITIEF. De labels blijven Nederlands (ze zijn een interne sleutel, geen
# schermtekst), maar de tokens dekken beide talen. Reden: dit is een DETERMINISTISCHE match op losse
# woorden, en het dorp draagt sinds 06-09-2026 twee talen tegelijk — nieuwe content Engels, alles wat
# er al lag Nederlands. Kies je één taal, dan scoort de helft van je kennisbank stil op nul.
#
# Gemeten vóór deze uitbreiding: een Nederlandse zin over een composteerbare zool zonder plastic,
# gemaakt op bestelling in Portugal, raakte 4 thema's; de letterlijke Engelse vertaling ervan 3.
# Dat verschil zat niet in de inhoud maar in de woordenlijst, en dat is precies het soort stille
# scheefheid waar niemand een melding van krijgt.
#
# Additief houden is geen luxe: haal je de Nederlandse tokens weg, dan verliest élke bestaande kaart
# in de kennisbank zijn strategie-score, met terugwerkende kracht en zonder foutmelding.
STRATEGIE_THEMAS: dict[str, set[str]] = {
    "geen plastic": {"plastic", "plastics", "microplastic", "microplastics", "polyester",
                     "petroleum", "petrochemical", "aardolie", "fossiel", "fossil", "synthetisch",
                     "synthetische", "synthetic", "pla", "nylon", "elastaan", "elastan",
                     "elastane", "spandex", "polyurethane", "pu"},
    "geen leer": {"leer", "leder", "leather", "dierlijk", "dierlijke", "animal", "dier", "dieren",
                  "vee", "veeteelt", "veehouderij", "livestock", "slacht", "slachthuis",
                  "slaughter", "koe", "cow", "runder", "rundvlees", "cattle", "vegan",
                  "diervrij", "huid", "hide", "hides", "suede"},
    "afbreekbaar & biobased": {"composteerbaar", "composteren", "compostable", "afbreekbaar",
                               "biologisch", "biodegradeerbaar", "biodegradatie", "biodegradable",
                               "mycelium", "cellulose", "natuurrubber", "rubber", "biobased",
                               "en13432", "compost", "renewable", "hernieuwbaar"},
    "in europa geproduceerd": {"europa", "europe", "european", "europese", "lokaal", "lokale",
                               "local", "portugal", "portugees", "portuguese", "maakindustrie",
                               "manufacturing", "productie", "production", "fabriek", "factory",
                               "nabij", "nearshore", "nearshoring"},
    "op bestelling": {"bestelling", "order", "ordered", "demand", "voorraad", "stock",
                      "inventory", "overproductie", "overproduction", "deadstock", "maatwerk",
                      "bespoke", "afname", "preorder", "made"},
    "eerlijk werk & prijs": {"eerlijk", "eerlijke", "fair", "fairly", "loon", "lonen", "wage",
                             "wages", "uurloon", "leefbaar", "living", "arbeidsomstandigheden",
                             "arbeid", "labour", "labor", "vakbond", "union", "kinderarbeid",
                             "werknemers", "workers", "werkomstandigheden"},
    "transparantie": {"transparant", "transparent", "transparantie", "transparency", "herkomst",
                      "provenance", "traceerbaar", "traceable", "traceability", "keten", "chain",
                      "supply", "audit", "audits", "audited", "certificaat", "certificate",
                      "certificering", "certification", "gecertificeerd", "certified", "bewijs",
                      "evidence", "proof"},
}


def _mis_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def strategie_relevantie(text: str) -> tuple[int, list[str]]:
    """Deterministische strategie-score van een tekst: hoeveel van de STRATEGIE_THEMAS hij raakt, en
    welke (labels). Een term matcht op exacte token-gelijkheid, of als prefix voor termen ≥ 5 tekens
    ('composteer' vangt 'composteerbaar'). Geen LLM — veilig om op elke pagina-load te draaien."""
    toks = _mis_tokens(text)
    labels: list[str] = []
    for label, termen in STRATEGIE_THEMAS.items():
        for term in termen:
            if term in toks or (len(term) >= 5 and any(t.startswith(term) for t in toks)):
                labels.append(label)
                break
    return len(labels), labels
