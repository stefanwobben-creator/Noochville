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
STRATEGIE_THEMAS: dict[str, set[str]] = {
    "geen plastic": {"plastic", "microplastic", "microplastics", "polyester", "petroleum",
                     "aardolie", "fossiel", "synthetisch", "synthetische", "pla", "nylon",
                     "elastaan", "elastan"},
    "geen leer": {"leer", "leder", "dierlijk", "dierlijke", "dier", "dieren", "vee", "veeteelt",
                  "veehouderij", "slacht", "slachthuis", "koe", "runder", "rundvlees", "vegan",
                  "diervrij", "huid"},
    "afbreekbaar & biobased": {"composteerbaar", "composteren", "afbreekbaar", "biologisch",
                               "biodegradeerbaar", "biodegradatie", "mycelium", "cellulose",
                               "natuurrubber", "biobased", "en13432", "compost"},
    "in europa geproduceerd": {"europa", "europese", "lokaal", "lokale", "portugal", "portugees",
                               "maakindustrie", "productie", "fabriek", "nabij"},
    "op bestelling": {"bestelling", "voorraad", "overproductie", "maatwerk", "afname"},
    "eerlijk werk & prijs": {"eerlijk", "eerlijke", "loon", "lonen", "uurloon", "leefbaar",
                             "arbeidsomstandigheden", "arbeid", "vakbond", "kinderarbeid",
                             "werknemers", "werkomstandigheden"},
    "transparantie": {"transparant", "transparantie", "herkomst", "traceerbaar", "keten",
                      "audit", "audits", "certificaat", "certificering", "gecertificeerd", "bewijs"},
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
