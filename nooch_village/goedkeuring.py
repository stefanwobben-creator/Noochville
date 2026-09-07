"""De goedkeuringsrij, leesbaar en beslisbaar vanuit de inbox die je al gebruikt.

AANLEIDING, gemeten op 7 september 2026. Er waren TWEE inboxen en een mens kon er bij één:

  · `notifications.json` — de spanningen, de envelop in het cockpit. 26 open.
  · `human_inbox.json`   — de goedkeuringsrij. **78 open, en in zeventig dagen niets aangeraakt.**
                           36 verband, 15 keyword, 15 means_gap, 8 activation, 3 suggestion, 1 kans.

Die tweede had geen pagina. De enige weg erheen was `python -m nooch_village.inbox` op de server, en
het cockpit verwees er wél naartoe ("review it via the human inbox") zonder dat er een deur was. Dat
is geen leesprobleem maar een vindprobleem: de items zijn prima te begrijpen, ze werden alleen nooit
gezien. Zeventig dagen stilstand was daarmee de voorspelbare uitkomst, niet een verrassing.

DE REGEL DIE DIT VEILIG HOUDT, en hij is met opzet één zin:

    Het cockpit mag altijd NEE of LATER zeggen. JA mag per type.

Nee en later scheppen niets: ze sluiten of verplaatsen een item en laten de wereld verder met rust.
Ja kan een rol tot leven wekken of een governance-wijziging aannemen, en dat blijft waar het hoort.
De veiligheidsgrens in `human_inbox.py` is geschreven tegen NOTIFICATIEKANALEN — een mail mag nooit
een goedkeurknop dragen, want dan forceert een extern kanaal een besluit. Het geauthenticeerde
cockpit is dat niet. Maar 'authenticated' is geen vrijbrief voor alles, dus de dure ja's blijven op
de commandoregel, met de exacte regel erbij in het scherm zodat je 'm kunt kopiëren.

Wat dat concreet betekent voor de 78: **70 zijn hiermee af te handelen, 8 niet.** Die acht zijn de
activaties, en die verdienen het ook om even ongemakkelijk te zijn.
"""
from __future__ import annotations

# Per type: wat wordt er gevraagd, mag het cockpit JA zeggen, en waarom niet als het niet mag.
#
# `vraag` is de zin die de mens leest. Hij staat hier en niet in de view, want dezelfde zin moet
# straks ook in de CLI en in een eventuele samenvatting kunnen staan — één bron, zoals bij
# `not_answered_note`. Engels, zoals de hele inhoudslaag sinds 06-09-2026.
TYPES: dict[str, dict] = {
    "verband": {
        "vraag": "Link these two cards?",
        "ja": True,
        "wat": "writes the link between the two cards",
    },
    "keyword": {
        "vraag": "Add this word to the library, or ban it?",
        "ja": True,
        "wat": "curates the word in the library",
    },
    "opportunity": {
        "vraag": "Pick this opportunity up?",
        "ja": True,
        "wat": "routes it onward",
    },
    "suggestion": {
        "vraag": "Is this suggestion worth acting on?",
        "ja": False,
        "waarom_niet": "approving starts work over the bus; the daemon has to be there for it",
    },
    "means_gap": {
        "vraag": "No tool covers this promise. Still needed?",
        "ja": False,
        "waarom_niet": "approving opens a governance round and asks for the skill's details",
    },
    "activation": {
        "vraag": "Wake this sleeping role and give it a thread?",
        "ja": False,
        "waarom_niet": "this brings a role to life — it stays on the command line on purpose",
    },
    "escalation": {
        "vraag": "This governance proposal did not pass the gate. Adopt it anyway?",
        "ja": False,
        "waarom_niet": "adopting changes the org record and runs over the bus",
    },
    "content_suggestion": {
        "vraag": "Have the strategist draft this?",
        "ja": False,
        "waarom_niet": "approving asks for reader and kind, and briefs the strategist over the bus",
    },
    "content_draft": {
        "vraag": "Publish this draft?",
        "ja": False,
        "waarom_niet": "publishing is an outward-facing act",
    },
    "keyword_batch": {
        "vraag": "Judge this batch of words?",
        "ja": False,
        "waarom_niet": "a batch is judged word by word on the command line",
    },
    "voorstel": {
        "vraag": "Adopt this proposal?",
        "ja": False,
        "waarom_niet": "adopting runs over the bus",
    },
}

# Nee en later mogen ALTIJD, ongeacht type. Dat is het hele veiligheidsargument van deze module:
# een weigering schept niets. Zou dit per type geregeld worden, dan is er ooit een type waar je niet
# eens nee kunt zeggen, en dan groeit de rij weer dicht.
ALTIJD = ("rejected", "deferred")

_CLI = "ssh root@138.201.154.162 'sudo -u nooch /opt/noochville/venv/bin/python -m nooch_village.inbox {actie} {iid}'"


def vraag_van(item: dict) -> str:
    """De vraag die dit item stelt. Onbekend type → een eerlijke, algemene vraag in plaats van een
    lege regel: een item zonder vraag is een item dat niemand oppakt."""
    t = str((item or {}).get("type") or "")
    return (TYPES.get(t) or {}).get("vraag") or f"Decide on this {t or 'item'}?"


def mag_ja(item_of_type) -> bool:
    """Mag het cockpit hier JA zeggen? Onbekend type → nee. Fail-closed: een nieuw type dat niemand
    hier heeft afgewogen krijgt niet per ongeluk een goedkeurknop."""
    t = item_of_type if isinstance(item_of_type, str) else str((item_of_type or {}).get("type") or "")
    return bool((TYPES.get(t) or {}).get("ja"))


def waarom_niet(item_of_type) -> str:
    t = item_of_type if isinstance(item_of_type, str) else str((item_of_type or {}).get("type") or "")
    return (TYPES.get(t) or {}).get("waarom_niet") or "this type has not been cleared for the cockpit"


def cli_regel(item: dict, actie: str = "approve") -> str:
    """De regel om te plakken voor de ja's die hier niet mogen. Zonder deze regel is 'dit kan alleen
    op de commandoregel' een doodlopende weg, en dat was precies de fout die deze module oplost."""
    return _CLI.format(actie=actie, iid=(item or {}).get("id", "<id>"))


def samenvatting(item: dict, max_len: int = 220) -> str:
    """Waar gaat dit item over? De tekst zit onder `context`, niet bovenin — dat kostte een ronde bij
    het meten, want een script dat bovenin keek drukte 78 lege regels af en dat leest als 'deze items
    hebben geen inhoud'."""
    ctx = item.get("context") if isinstance(item.get("context"), dict) else {}
    for k in ("description", "voorstel_claim", "reason", "word", "title", "claim", "beschrijving"):
        v = ctx.get(k)
        if isinstance(v, str) and v.strip():
            s = " ".join(v.split())
            return s if len(s) <= max_len else s[: max_len - 1] + "…"
    # `subject` is de laatste redding: bij een verband is dat 'kaartA|kaartB', niet mooi maar wél
    # informatie. Liever een lelijke regel dan een lege.
    s = " ".join(str(item.get("subject") or "").split())
    return (s if len(s) <= max_len else s[: max_len - 1] + "…") or "(no description recorded)"


def open_items(inbox, *, limiet: int = 200) -> list[dict]:
    """De openstaande goedkeuringen, oudste eerst — want dat is de volgorde waarin ze pijn doen.

    Fail-soft: geen inbox, een stukke store of een onverwachte vorm levert een lege lijst. De
    spanningen-inbox mag NOOIT stukgaan omdat de goedkeuringsrij iets raars doet; dat zou de ene
    werkende inbox slopen om de andere te tonen."""
    if inbox is None:
        return []
    try:
        items = list(inbox.pending())
    except Exception:                                     # noqa: BLE001
        return []
    items = [i for i in items if isinstance(i, dict)]
    items.sort(key=lambda i: float(i.get("created_at") or i.get("at") or 0) or 0.0)
    return items[:limiet]


def tel_per_type(items) -> list[tuple[str, int]]:
    """Hoeveel per type, grootste groep eerst. Voor de kop boven de lijst: 36 verbanden achter
    elkaar leest anders als 36 losse verrassingen."""
    per: dict[str, int] = {}
    for i in items or []:
        t = str(i.get("type") or "?")
        per[t] = per.get(t, 0) + 1
    return sorted(per.items(), key=lambda x: (-x[1], x[0]))
