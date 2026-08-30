"""De vijf lezerstests, uit de policy en niet uit een kopie hier.

WAAROM DIT EEN EIGEN MODULE IS EN GEEN LITERAL IN DE PROMPT. De lezerstests staan in COPYCHECK-001,
en die policy is governance-eigendom: iemand mag hem wijzigen in de cockpit. Zou de leesbaarheidslaag
zijn eigen kopie dragen, dan drijven de twee uit elkaar zodra iemand de policy bijwerkt — precies de
`reference, don't copy`-regel uit CLAUDE.md, en precies wat er misging bij `by="dialoog"`: een feit
op twee plekken drijft af zonder dat iets zich meldt.

WELKE HELFT. Alleen de BEGRIJPELIJKHEID (de vijf reader tests), niet de merkstem. Een watchdog-alarm
hoort plat en duidelijk te lezen, niet als homepage-copy. De voice checks (Smirk, Try-Hard, Hedge) en
de tone-of-voice-regels blijven waar ze horen: bij de copy-tools, waar een mens over een klanttekst
oordeelt.

DE TERUGVAL IS ZICHTBAAR. Is de policy er niet (verse installatie, andere data_dir), dan draait deze
laag door op een korte ingebouwde samenvatting — maar hij LOGT dat, want een permanente terugval die
niemand ziet is een stille kwaliteitsdaling. Zelfde regel als bij de lexicale terugval van de
kennis-index: fail-soft mag de degradatie niet onzichtbaar maken.
"""
from __future__ import annotations

import logging
import os
import re

log = logging.getLogger("village.helderheid")

POLICY_ID = "COPYCHECK-001"

# De kop waar de lezerstests onder staan. Verandert die in de policy, dan valt deze module terug én
# meldt hij dat — liever luid degraderen dan stil de verkeerde helft meenemen.
_KOP = re.compile(r"\*\*Reader tests\*\*(.*?)(?:\n\s*\*\*|\Z)", re.S | re.I)

# NOODVERBAND, geen tweede waarheid. Alleen in gebruik als de policy onbereikbaar is, en dan met een
# waarschuwing in het log. Bewust kort: wie dit leest moet zien dat het een samenvatting is en de
# echte tekst in COPYCHECK-001 staat.
_TERUGVAL = """- Vreemde in de trein: volgt iemand die ons niet kent deze zin zonder jouw uitleg?
- De uitleg-vraag: heeft een zin een tweede zin nodig om te kloppen? Dan deugt de eerste niet.
- Insiderstaal: staat er een woord dat alleen wij gebruiken? Vervang het.
- Actie: weet de lezer na afloop wat hij moet doen of denken?
- Veertien: kan een veertienjarige dit hardop voorlezen en menen?"""


def reader_tests(data_dir: str = "") -> tuple[str, bool]:
    """(tekst, uit_policy). `uit_policy=False` betekent: noodverband, en dat is een signaal."""
    try:
        from nooch_village.attachments import AttachmentStore
        a = AttachmentStore(os.path.join(data_dir or "data", "attachments.json")).get(POLICY_ID)
        blok = _KOP.search(getattr(a, "body", "") or "") if a is not None else None
        if blok:
            tekst = "\n".join(r.strip() for r in blok.group(1).strip().splitlines() if r.strip())
            if tekst:
                return tekst, True
        reden = "policy ontbreekt" if a is None else "kop 'Reader tests' niet gevonden"
    except Exception as e:                                    # noqa: BLE001 — nooit blokkeren
        reden = str(e)
    log.warning("helderheid: lezerstests niet uit %s (%s) — noodverband in gebruik, de laag draait "
                "op een samenvatting in plaats van op de policy", POLICY_ID, reden)
    return _TERUGVAL, False
