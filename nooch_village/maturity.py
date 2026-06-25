"""Rijpheid en omkeerbaarheid — de twee poorten uit docs/GOVERNANCE_FILOSOFIE.md.

- Een **accountability** mag pas ontstaan als een kans is GESTOLD: er is bewijs van terugkerende
  frictie (kwam meermaals terug, anderen wachten erop). Anders hoort het een experiment (project)
  te blijven. `friction_evidence()` toetst dat.
- Een **project** (experiment) kent maar één poort: kan het ONHERSTELBARE schade doen? Zo nee, dan
  mag het vrij (Holacracy: alles mag tenzij verboden). `irreversible_harm()` toetst dat.

Beide zijn lichte, deterministische heuristieken (geen LLM, geen netwerk); ze adviseren en
beslissen niet hard — de mens houdt de poort.
"""
from __future__ import annotations
import re

# Signalen dat een kans is gestold (terugkerende frictie) → rijp voor een accountability.
_FRICTION = (
    "meermaals", "meerdere keren", "terugkerend", "terugkomt", "blijft terugkomen", "structureel",
    "wekelijks", "dagelijks", "elke week", "elke maand", "elke keer", "iedere keer", "telkens",
    "herhaaldelijk", "steeds weer", "vaak", "wachten", "wacht erop", "wacht op",
    "strandt", "blijft liggen", "loopt vast",
)

# Signalen dat een actie ONOMKEERBAAR / risicovol kan zijn → project eerst langs de mens.
_IRREVERSIBLE = (
    "publiceer", "publiceren", "gepubliceerd", "live zetten", "live gaan", "naar buiten",
    "adverteren", "advertentie", "betaald", "geld uitgeven", "uitgeven", "kopen", "bestellen",
    "betaling", "verwijder", "verwijderen", "wissen", "schrappen", "annuleren",
    "mailen naar klanten", "klanten mailen", "nieuwsbrief versturen", "versturen naar",
    "klantdata", "persoonsgegevens", "productie", "contract", "onomkeerbaar", "definitief",
    "prijs verlagen", "prijs verhogen", "korting",
)


def friction_evidence(*texts: str) -> bool:
    """True als de tekst bewijs van terugkerende frictie draagt (rijp voor een accountability)."""
    blob = " ".join(t or "" for t in texts).lower()
    return any(kw in blob for kw in _FRICTION)


def irreversible_harm(*texts: str) -> bool:
    """True als de tekst wijst op mogelijk ONOMKEERBARE schade (project eerst langs de mens).
    Conservatief: bij twijfel False (omkeerbaar → mag vrij), tenzij een duidelijk signaal."""
    blob = " ".join(t or "" for t in texts).lower()
    return any(re.search(r"\b" + re.escape(kw), blob) for kw in _IRREVERSIBLE)
