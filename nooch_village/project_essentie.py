"""De essentie van een einddocument — de paar regels die op de projectkaart staan.

De kaart toonde het volledige rapport inline. Dat leest niet: je scant een bord met kaarten en
krijgt op elke kaart een document. Deze module levert de **essentie** (wat staat er, in één of
twee zinnen) en de kaart wijst voor de rest naar `/rapport?pid=…`.

HERKENNEN, NIET GENEREREN. Gemeten op de 307 documenten op productie: een expliciete
"Projectdoel"-kop bestaat 14 keer, en de eerste alinea is maar bij 30% een bruikbare zin. Maar de
overige 70% is geen chaos — het zijn twee herkenbare toestanden (het document is nog de geseede
opdracht; of de tekst zit in een codefence). Die hoef je niet door een model te halen, alleen te
herkennen. De ladder hieronder dekt 303 van de 307; de vier die doorvallen krijgen alleen de link.
Een gegenereerde TL;DR voor vier documenten is de regenerate-flow niet waard.

De ladder, goedkoop eerst:

    0  ontfence      een omhullende ```markdown-fence weg     (46x)
    1  seed          het document is nog alleen de opdracht   (107x)
    2  doelregel     de schrijver zei zelf wat het doel was   (17x)
    3  eerste_zin    de eerste echte zin uit het rapport      (179x)
    4  geen          niets bruikbaars → alleen de link        (4x)

Trede 0 is GEEN weergave-fix. `cockpit2_util._md_doc` stript de fence al bij het renderen, dus het
volledige rapport toonde altijd goed. Trede 0 bestaat omdat DEZE parser anders alleen een codeblok
ziet en over de hele tekst heen stapt.

Trede 1 vraagt het niet zelf maar aan `projects.heeft_seed_vorm` — de WEERGAVEVRAAG ("is dit
document niets dan de opdracht, welke opdracht dan ook"). Dat is bewust een andere vraag dan de
poortvraag van `dod_poort` ("is dit exact de seed van dít project"); zie het blok boven
`is_seed_van_dit_project` in projects.py voor waarom die twee uit elkaar horen te lopen. Het
sjabloon zelf leeft nog steeds op één plek. Een eigen regex op `**Klaar wanneer**` zou wél een
tweede definitie zijn, en die drijft af zodra de seed-tekst verandert.

Geen I/O, geen store, geen netwerk: tekst in, essentie uit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from nooch_village.projects import heeft_seed_vorm

# Een essentie langer dan dit leest niet meer als essentie maar als het begin van een rapport.
# Gemeten: mediaan 88 tekens, p75 200. De knip zoekt een zinsgrens vóór de harde cap.
_CAP = 240
_ZACHTE_KNIP = 160          # vanaf hier mag een zinseinde de knip bepalen

_FENCE = re.compile(r"^\s*```(?:markdown|md)?\s*\n(.*?)\n?\s*```\s*$", re.S)
_FENCE_OPEN = re.compile(r"^\s*```(?:markdown|md)\s*\n", re.S)

# "Projectdoel: …", "## Goal — …", "TL;DR: …". De scheidingsteken-eis houdt gewone zinnen die
# toevallig met "Doel" beginnen buiten de deur.
_DOELREGEL = re.compile(
    r"^\s*[#*>\s-]*(?:project\s?doel|projectdoel|project goal|doel|goal|samenvatting|summary|"
    r"tl;?dr|in het kort|essentie)\s*[:：—-]\s*(.+)$", re.I)

_HR = re.compile(r"^[-*_]{3,}$")
_LIJST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")


@dataclass(frozen=True)
class Essentie:
    """Wat er op de kaart komt.

    `soort` is er voor de view (elke trede krijgt een eigen zin op het scherm) en voor de test
    die de dekking bewaakt. `gekapt` zegt of er tekst is weggevallen — dan is de link naar het
    volledige rapport niet alleen aanbod maar noodzaak."""
    soort: str          # "seed" | "doelregel" | "eerste_zin" | "geen"
    tekst: str
    gekapt: bool = False

    @property
    def heeft_tekst(self) -> bool:
        return bool(self.tekst.strip())


def ontfence(md: str) -> str:
    """Trede 0: haal een fence weg die om het HELE document staat.

    Een niet-gesloten fence (7 van de 46 op productie) telt ook: de LLM begon met ```markdown en
    vergat af te sluiten. Een fence midden in het document blijft staan — dat is echte code."""
    s = (md or "").strip()
    m = _FENCE.match(s)
    if m:
        return m.group(1)
    if _FENCE_OPEN.match(s):
        return s.split("\n", 1)[1] if "\n" in s else ""
    return md or ""


def _schoon(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", t)).strip()


def _alineas(md: str):
    """Alleen echte prozablokken: geen koppen, lijsten, tabellen, citaten, streepjeslijnen of code.

    Een lijst of tabel kán de kern van een rapport zijn, maar als éérste zin op een kaart leest
    hij niet — daarom is hij hier geen kandidaat, niet omdat hij onbelangrijk is."""
    buf: list[str] = []
    in_code = False
    for regel in md.splitlines():
        s = regel.strip()
        if s.startswith("```"):
            in_code = not in_code
            if buf:
                yield " ".join(buf)
                buf = []
            continue
        if in_code:
            continue
        if not s or _HR.fullmatch(s) or s.startswith(("#", "|", ">")) or _LIJST.match(s):
            if buf:
                yield " ".join(buf)
                buf = []
            continue
        buf.append(s)
    if buf:
        yield " ".join(buf)


def _is_zin(t: str) -> bool:
    """Een zin, geen fragment. Vier afwijzingen, elk uit de meting:

    te kort (115x "Klaar wanneer"), een label dat op ':' eindigt (18x "Bevindingen:"), geen
    zinseinde (11x), en een opsomming die op één regel is platgeslagen (21x "- URL: … - Status:")."""
    if len(t) < 40 or t.endswith(":"):
        return False
    if not re.search(r"[.!?]", t):
        return False
    return t.count(" - ") < 2 and t.count(" · ") < 2


def _kap(t: str) -> tuple[str, bool]:
    """Kap op een zinsgrens als dat kan, anders op een woordgrens. Nooit midden in een woord."""
    if len(t) <= _CAP:
        return t, False
    knip = max((t.rfind(p, _ZACHTE_KNIP, _CAP) for p in (". ", "! ", "? ")), default=-1)
    if knip > 0:
        return t[:knip + 1], True
    ruimte = t.rfind(" ", _ZACHTE_KNIP, _CAP)
    return (t[:ruimte] if ruimte > 0 else t[:_CAP]).rstrip(" ,;:-") + "…", True


def essentie_van(doc: str) -> Essentie:
    """De ladder. Eerste trede die raakt, wint.

    Neemt geen project aan: wat je op de kaart toont is uit het document alleen te bepalen. De
    poortvraag ("is dit Done") heeft het record wél nodig en woont daarom elders."""
    ruw = doc or ""
    # Trede 1 vóór het ontfencen: de seed wordt nooit gefencet opgeslagen, dus ontfencen zou de
    # vormvergelijking juist kapotmaken.
    if heeft_seed_vorm(ruw):
        return Essentie("seed", "")
    md = ontfence(ruw)
    if not md.strip():
        return Essentie("geen", "")

    regels = [r for r in md.splitlines() if r.strip()]
    for r in regels[:12]:
        m = _DOELREGEL.match(r)
        if m:
            t = _schoon(m.group(1))
            if len(t) >= 25:
                tekst, gekapt = _kap(t)
                return Essentie("doelregel", tekst, gekapt)

    for blok in _alineas(md):
        t = _schoon(blok)
        if _is_zin(t):
            tekst, gekapt = _kap(t)
            return Essentie("eerste_zin", tekst, gekapt)

    return Essentie("geen", "")
