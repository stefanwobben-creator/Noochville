"""Anchor-policies van Nooch.earth — één bron voor het hele dorp.

Elke policy heeft:
  prose            — prozatekst voor de wortelcirkel-records
  regex_patterns   — patronen voor de G4 harde-schending-detector
  intent_patterns  — (substring, reden)-paren voor de intentielaag

Importeer ANCHOR_POLICY_PROSE, HARD_VIOLATION_RE en INTENT_VIOLATIONS
overal waar policies gecontroleerd worden (governance G4, intent.py,
village seed).
"""
from __future__ import annotations
import re

_POLICIES: list[dict] = [
    {
        "key": "no_plastic_leather",
        "prose": (
            "Geen enkele rol mag een accountability hebben die plastic-gebaseerd of "
            "dierlijk-leer materiaal als on-mission goedkeurt."
        ),
        "regex_patterns": [
            r"plastic.{0,35}goed|goed.{0,35}plastic",
            r"leer.{0,35}goed|goed.{0,35}leer",
            r"leather.{0,35}approv|approv.{0,35}leather",
            r"\bpvc\b|\bkunstleer\b|\bpu-leer\b",
        ],
        "intent_patterns": [],
    },
    {
        "key": "no_advertising",
        "prose": (
            "Geen enkele rol mag uitgaven aan advertising autoriseren of plannen; "
            "betaald bereik is verboden als groeistrategie."
        ),
        "regex_patterns": [
            r"advertis\w*.{0,30}autoris|autoris\w*.{0,30}advertis",
            r"reclame.{0,25}autoris|autoris.{0,25}reclame",
            r"betaald.{0,30}adverteer|adverteer.{0,30}betaald",
            r"google.{0,10}ads.{0,20}autoris|facebook.{0,10}ads",
        ],
        "intent_patterns": [
            ("google ads",        "advertising is verboden via Anchor-policy"),
            ("facebook ads",      "advertising is verboden via Anchor-policy"),
            ("instagram ads",     "advertising is verboden via Anchor-policy"),
            ("betaald adverter",  "advertising is verboden via Anchor-policy"),
            ("betaalde reclame",  "advertising is verboden via Anchor-policy"),
            ("advertentiebudget", "advertising is verboden via Anchor-policy"),
            ("advertis",          "advertising is verboden via Anchor-policy"),
        ],
    },
    {
        "key": "only_own_channel",
        "prose": (
            "Verkoop loopt uitsluitend via de eigen website nooch.earth; "
            "geen enkele rol mag externe verkoopkanalen of marktplaatsen autoriseren."
        ),
        "regex_patterns": [],
        "intent_patterns": [
            ("marktplaats", "verkoop via externe kanalen is verboden; alleen nooch.earth"),
            ("bol.com",     "verkoop via externe kanalen is verboden; alleen nooch.earth"),
            ("amazon",      "verkoop via externe kanalen is verboden; alleen nooch.earth"),
        ],
    },
    {
        "key": "on_demand_no_stock",
        "prose": (
            "Productie is on demand; geen enkele rol mag voorraadopbouw of "
            "overproductie autoriseren of plannen."
        ),
        "regex_patterns": [
            r"massaproduct\w*|overproduct\w*|voorraadopbouw\w*",
        ],
        "intent_patterns": [
            ("voorraadopbouw", "voorraadopbouw is verboden (on-demand productie, Anchor-policy)"),
            ("overproductie",  "overproductie is verboden via Anchor-policy"),
        ],
    },
    {
        "key": "mission_check_immutable",
        "prose": (
            "De missie-toetsing (KeywordReview, G4-poort) mag nooit als accountability "
            "worden verwijderd zonder een gelijkwaardig alternatief in hetzelfde voorstel."
        ),
        "regex_patterns": [
            r"missie.{0,25}toets.{0,25}verwijder|verwijder.{0,25}missie",
        ],
        "intent_patterns": [],
    },
]

# ── publieke exports ──────────────────────────────────────────────────────────

ANCHOR_POLICY_PROSE: list[str] = [p["prose"] for p in _POLICIES]

HARD_VIOLATION_RE: re.Pattern = re.compile(
    "|".join(
        pat
        for policy in _POLICIES
        for pat in policy["regex_patterns"]
    ),
    re.I | re.S,
)

INTENT_VIOLATIONS: list[tuple[str, str]] = [
    pair
    for policy in _POLICIES
    for pair in policy["intent_patterns"]
]
