"""De deterministische helft van de copy-checker: wat je kunt vergelijken, vergelijk je.

TWEE LAGEN, EN DEZE IS DE ONDERSTE. Wat mechanisch te toetsen is — een verboden woord, een
lengtelimiet, een claim die een bron nodig heeft — hoort niet naar een model. Het oordeel (toon,
stem, of een zin wérkt) gaat naar de chat, via een gegronde plak-prompt.

DE CHECKER HERSCHRIJFT NIETS. Nina schreef de tekst; wij wijzen aan waar iets wringt en stellen iets
voor. Zij beslist. Spiegelbeeld van de leesbaarheidslaag: daar herschrijven we machinewerk vóór een
mens, hier laten we mensenwerk staan en adviseren we.

HET STRUCTUURBLOK, EN WAAROM HET IN DE BODY STAAT. De regels moeten uit de POLICY komen, niet uit een
kopie in code — anders drijven ze uit elkaar zodra iemand de policy bijwerkt. Maar prosa parsen is
fragiel op precies de plek waar het telt: prosa noemt een DREMPEL ("maximum one exclamation mark"),
geen PREDICAAT (wát je telt). Die kennis landt hoe dan ook in code.

Dus: een machine-leesbaar blok IN de policy-body, naast de prosa. Niet in `meta` — dat is onzichtbaar
in de editor waar de eigenaar werkt, en wat je niet ziet drijft stil af.

    ```check
    verboden: friend, join the movement, duurzame keuze
    bron_vereist: biodegradable, compostable
    max_emoji: 0 | Zero emoji
    max_uitroepteken: 1 | Maximum one exclamation mark per text
    ```

DE KOPPELTEST IS DE PRIJS VAN DIE TWEEDE VORM. Een blok is een tweede plek waar hetzelfde staat, en
onze eigen conventie zegt dat een tweede plek afdrijft tenzij iets klaagt. Dus klaagt er iets: elke
term uit het blok moet in de PROSA van diezelfde policy voorkomen, en elke numerieke limiet draagt
het prosa-fragment dat hem uitspreekt. Het blok mag geen regel dragen die de prosa niet noemt.
"""
from __future__ import annotations

import re

#: DE GROND VAN DE CHECKER, expliciet en los van de generator.
#:
#: De generator componeert zijn stack via `copy_stack`: erfenis plus bewuste inclusies, met lagen die
#: iemand in de UI aan of uit kan zetten. Dat is juist voor SCHRIJVEN — je wilt merk en kader erbij
#: kunnen halen. Maar de grond waartegen je TOETST mag niet stil veranderen omdat iemand een
#: generator-instelling omzet. Een checker die gisteren op vier policies toetste en vandaag op drie,
#: zonder dat iemand dat besloot, geeft een groen scherm dat niets betekent.
#:
#: Twee tools, twee gronden. De brand- en design-policies vallen hier bewust buiten: die gaan over
#: het visuele medium, niet over tekst, en horen bij een eventuele aparte brand-tool op Brand &
#: Visual Designer.
COPY_POLICIES = ("COPYCHECK-001", "POSITIONSTAT-001", "TONEOFVOICE-001", "STANCE-001")


def regels_uit(att, policies=COPY_POLICIES) -> list[tuple[str, dict]]:
    """(policy_id, blok) voor elke policy uit de vaste set die een structuurblok draagt.

    Een policy zonder blok levert niets — geen valse zekerheid. Levert extractie voor een policy
    geen checkbare tekstregel op, dan hoort hij hier gewoon leeg te blijven; hij draagt dan niets bij
    en dat is een eerlijke uitkomst, geen gat."""
    uit = []
    for pid in policies:
        try:
            a = att.get(pid)
        except Exception:                                    # noqa: BLE001
            a = None
        if a is None:
            continue
        blok = parse_blok(getattr(a, "body", "") or "")
        if blok:
            uit.append((pid, blok))
    return uit


def check_alles(tekst: str, att, policies=COPY_POLICIES) -> list[dict]:
    """Alle bevindingen over de hele gecureerde set, met per bevinding de bronpolicy."""
    uit = []
    for pid, blok in regels_uit(att, policies):
        uit.extend(check(tekst, blok, policy_id=pid))
    return uit


#: De fence waarin het blok staat. Bewust een eigen taal-tag: een lezer ziet meteen dat dit geen
#: voorbeeld is maar de regels zelf.
_FENCE = re.compile(r"```check\s*\n(.*?)```", re.S | re.I)

#: Lijst-sleutels (komma-gescheiden termen) en limiet-sleutels (getal + prosa-anker).
_LIJSTEN = ("verboden", "bron_vereist", "verplicht")
_LIMIET = re.compile(r"^max_([a-z_]+)$")

#: Getalwoorden die in prosa voorkomen. Klein gehouden: de echte limieten zijn 0, 1 en 2.
_GETALWOORD = {0: ("0", "zero", "nul", "geen"), 1: ("1", "one", "één", "een"),
               2: ("2", "two", "twee"), 3: ("3", "three", "drie")}


def parse_blok(body: str) -> dict:
    """Het structuurblok uit een policy-body. Geeft {} als er geen blok is.

    Vorm: {"verboden": [...], "bron_vereist": [...], "limieten": {"emoji": (0, "Zero emoji"), ...}}
    """
    m = _FENCE.search(body or "")
    if not m:
        return {}
    uit: dict = {k: [] for k in _LIJSTEN}
    uit["limieten"] = {}
    for regel in m.group(1).splitlines():
        regel = regel.strip()
        if not regel or regel.startswith("#") or ":" not in regel:
            continue
        sleutel, _, waarde = regel.partition(":")
        sleutel, waarde = sleutel.strip().lower(), waarde.strip()
        if sleutel in _LIJSTEN:
            uit[sleutel] = [t.strip() for t in waarde.split(",") if t.strip()]
            continue
        lim = _LIMIET.match(sleutel)
        if lim:
            getal, _, anker = waarde.partition("|")
            try:
                uit["limieten"][lim.group(1)] = (int(getal.strip()), anker.strip())
            except ValueError:
                continue
    return uit


def _plat(t: str) -> str:
    return " ".join((t or "").lower().split())


def koppeltest(body: str) -> list[str]:
    """Klaagt zodra blok en prosa uiteenlopen. Lege lijst = ze zeggen hetzelfde.

    Dit is de reden dat het blok mag bestaan. Zonder deze test is het een tweede waarheid die
    stilletjes iets anders gaat zeggen dan de tekst die de eigenaar leest en onderhoudt."""
    blok = parse_blok(body)
    if not blok:
        return []
    prosa = _plat(_FENCE.sub(" ", body or ""))          # de prosa is alles BUITEN het blok
    klachten = []
    for sleutel in _LIJSTEN:
        for term in blok.get(sleutel, []):
            if _plat(term) not in prosa:
                klachten.append(f"'{term}' staat in het blok ({sleutel}) maar niet in de prosa")
    for naam, (getal, anker) in (blok.get("limieten") or {}).items():
        if not anker:
            klachten.append(f"limiet '{naam}' heeft geen prosa-anker — dan is hij niet te staven")
            continue
        if _plat(anker) not in prosa:
            klachten.append(f"het anker van '{naam}' staat niet in de prosa: “{anker}”")
            continue
        # NUMERIEKE LIMIETEN HOREN OOK IN DE PROSA. Een blok dat "max 1" zegt terwijl de tekst over
        # twee gaat, is precies de divergentie waar deze test voor bestaat.
        vormen = _GETALWOORD.get(getal, (str(getal),))
        if not any(v in _plat(anker) for v in vormen):
            klachten.append(f"limiet '{naam}' = {getal}, maar het prosa-anker noemt dat getal niet")
    return klachten


# ── de check zelf ───────────────────────────────────────────────────────────

_ZIN = re.compile(r"[^.!?\n]+[.!?]?")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
_GETAL_MET_PROCENT = re.compile(r"\b\d+(?:[.,]\d+)?\s*%")


def _zinnen(tekst: str) -> list[str]:
    return [z.strip() for z in _ZIN.findall(tekst or "") if z.strip()]


def check(tekst: str, blok: dict, *, policy_id: str = "") -> list[dict]:
    """Overtredingen van het structuurblok, met het WOORDELIJKE citaat erbij.

    COPYCHECK-001 eist dat expliciet: "Quote the failing sentence, do not summarise." Een bevinding
    zonder citaat dwingt de lezer zelf te gaan zoeken, en dan is aanwijzen niets waard."""
    if not blok:
        return []
    uit: list[dict] = []
    zinnen = _zinnen(tekst)
    laag = (tekst or "").lower()

    for term in blok.get("verboden", []):
        t = term.lower()
        if t not in laag:
            continue
        citaat = next((z for z in zinnen if t in z.lower()), term)
        uit.append({"regel": f"verboden woord: “{term}”", "citaat": citaat,
                    "suggestie": "vervang of schrap dit woord", "policy": policy_id})

    for term in blok.get("bron_vereist", []):
        t = term.lower()
        if t not in laag:
            continue
        citaat = next((z for z in zinnen if t in z.lower()), term)
        uit.append({"regel": f"“{term}” is een claim die een bron nodig heeft", "citaat": citaat,
                    "suggestie": "noem de bron, of gebruik de toegestane formulering",
                    "policy": policy_id})

    for zin in zinnen:
        if _GETAL_MET_PROCENT.search(zin) and not re.search(r"\b(bron|source|volgens|per)\b", zin, re.I):
            uit.append({"regel": "percentage zonder bron", "citaat": zin,
                        "suggestie": "voeg de bron toe waar dit getal vandaan komt",
                        "policy": policy_id})

    tellers = {"emoji": len(_EMOJI.findall(tekst or "")),
               "uitroepteken": (tekst or "").count("!"),
               "em_dash": (tekst or "").count("—")}
    for naam, (grens, anker) in (blok.get("limieten") or {}).items():
        gevonden = tellers.get(naam)
        if gevonden is None or gevonden <= grens:
            continue
        uit.append({"regel": f"{naam}: {gevonden} gevonden, hoogstens {grens} toegestaan",
                    "citaat": anker or naam,
                    "suggestie": f"haal er {gevonden - grens} weg", "policy": policy_id})
    return uit
