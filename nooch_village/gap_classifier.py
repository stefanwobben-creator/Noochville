"""Gap-classifier: klasseer een means-gap als A / B / C via term-overlap.

Pure functie — geen bedrading, geen I/O, geen threading.

Uitkomsten
----------
A  mandaat én middelen aanwezig — gap is al gedekt, geen actie nodig.
B  mandaat aanwezig, middelen ontbreken — sens als means-gap naar de inbox.
C  geen enkele rol dekt het mandaat — echt nieuw gat, overweeg een voorstel.
"""
from __future__ import annotations
import re

# ── Drempelwaarden (empirisch; pas hier aan, niet in de beslissingslogica) ───
MANDATE_THRESHOLD: float = 0.10  # minimale mandaat-overlap om dekking te claimen
MEANS_THRESHOLD:   float = 0.15  # minimale middel-overlap om A te retourneren

# ── Stopwoorden NL + EN ───────────────────────────────────────────────────────
_STOPWORDS: frozenset[str] = frozenset({
    # NL — functionele woorden zonder onderscheidend vermogen
    "alle", "alleen", "altijd", "andere", "anderen",
    "deze", "door", "drie",
    "eerste", "eigen", "elke", "elk",
    "geen", "goed",
    "haar", "heel", "hier",
    "iets", "iemand",
    "maar", "meer", "moet", "moeten",
    "naar", "niet", "nooit",
    "omdat", "over",
    "soms", "snel",
    "toch", "twee",
    "vaak", "veel", "voor",
    "welk", "welke", "worden", "wordt",
    "zodat", "zoals", "zodra", "zonder", "zowel",
    # EN — function words
    "also", "always", "any", "been", "both",
    "each", "else",
    "from", "good", "have", "here",
    "into", "just", "more", "most",
    "never", "only", "other",
    "should", "since", "some", "such",
    "than", "that", "their", "them", "then", "this", "they", "thus",
    "very", "what", "when", "where", "which",
    "with", "would", "your",
})

_MIN_LEN: int = 4


# ── Token-helpers ─────────────────────────────────────────────────────────────

def _tokenize(text: str) -> frozenset[str]:
    """Lowercase-tokens uit vrije tekst; filtert stopwoorden en korte tokens."""
    return frozenset(
        t for t in re.split(r"[\s\W]+", text.lower())
        if len(t) >= _MIN_LEN and t not in _STOPWORDS
    )


def _skill_tokens(skills: list[str]) -> frozenset[str]:
    """Leid tokens uit skill-ID's af door op underscore te splitsen."""
    out: set[str] = set()
    for skill_id in skills:
        for part in skill_id.split("_"):
            if len(part) >= _MIN_LEN and part not in _STOPWORDS:
                out.add(part)
    return frozenset(out)


def _coverage(gap: frozenset[str], reference: frozenset[str]) -> float:
    """Fractie van gap-tokens die in reference voorkomen (0.0–1.0)."""
    if not gap:
        return 0.0
    return len(gap & reference) / len(gap)


# ── Publieke API ──────────────────────────────────────────────────────────────

def classify_gap(
    gap_description: str,
    records,
) -> tuple[str, str, str]:
    """Klasseer een means-gap-beschrijving als A, B of C.

    Parameters
    ----------
    gap_description : str
        Vrije tekst van de spanning of capaciteitsgrens.
    records : Iterable[Record]
        Alle records (gearchiveerde worden overgeslagen). Elk record heeft
        .archived, .id en .definition met .purpose, .accountabilities,
        .domains en .skills.

    Returns
    -------
    (outcome, role_id, reason)
        outcome  : "A" | "B" | "C"
        role_id  : id van de best-dekkende rol ("" bij C)
        reason   : scores en beslissingspad voor debugging
    """
    gap_sig = _tokenize(gap_description)

    best_role_id:       str   = ""
    best_mandate_score: float = 0.0
    best_means_score:   float = 0.0

    for rec in records:
        if getattr(rec, "archived", False):
            continue
        defn = rec.definition

        mandate_sig = _tokenize(" ".join(filter(None, [
            defn.purpose or "",
            " ".join(defn.accountabilities or []),
            " ".join(defn.domains or []),
        ])))
        means_sig = _skill_tokens(defn.skills or [])

        m = _coverage(gap_sig, mandate_sig)
        s = _coverage(gap_sig, means_sig)

        if m > best_mandate_score or (m == best_mandate_score and s > best_means_score):
            best_mandate_score = m
            best_means_score   = s
            best_role_id       = rec.id

    if best_mandate_score < MANDATE_THRESHOLD:
        return (
            "C",
            "",
            f"geen rol met mandaat-overlap >= {MANDATE_THRESHOLD:.2f}; "
            f"hoogste={best_mandate_score:.3f} bij '{best_role_id or '?'}'",
        )

    if best_means_score >= MEANS_THRESHOLD:
        return (
            "A",
            best_role_id,
            f"mandaat={best_mandate_score:.3f} >= {MANDATE_THRESHOLD}; "
            f"middel={best_means_score:.3f} >= {MEANS_THRESHOLD}",
        )

    return (
        "B",
        best_role_id,
        f"mandaat={best_mandate_score:.3f} >= {MANDATE_THRESHOLD}; "
        f"middel={best_means_score:.3f} < {MEANS_THRESHOLD}",
    )
