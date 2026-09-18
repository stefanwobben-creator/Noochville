"""De promptgenerator van de Decision Coach: sjabloon in, kant-en-klare prompt uit.

GEEN LLM, GEEN NETWERK. Deze module doet string-substitutie en verder niets. Het dorp betaalt hier
dus nul tokens; het model dat coacht is dat van het lid zelf, in zijn eigen chat.

HET SJABLOON IS DATA, GEEN CODE. `prompts/decision_coach_en.md` bevat de coachingmethode en wordt
door een mens onderhouden. Deze module weet alleen hoe hij hem laadt, welke versie erin staat, en
hoe `{{placeholder}}` wordt ingevuld. Zou de tekst hier in een literal staan, dan zou elke
inhoudelijke wijziging een code-deploy vragen — en dan schrijft de implementatie de methode.

FAIL-CLOSED OP EEN ONTBREKEND SJABLOON. Geen bestand → geen prompt, met een zichtbare melding.
Een generator die bij een ontbrekend sjabloon "iets" produceert, geeft een lid een coach die niet
de afgesproken methode volgt, en dat is niet te zien aan de uitvoer.
"""
from __future__ import annotations

import os
import re

#: Waar het sjabloon woont, relatief aan de projectwortel (naast `config/` en `data/`).
MAP = "prompts"
BESTAND_EN = "decision_coach_en.md"

#: De eerste regel van het sjabloon draagt zijn versie: `<!-- template_version: 1 -->`. Die versie
#: reist mee in elke gelogde rij, zodat later te zien is welke methode iemand volgde.
_VERSIE_RE = re.compile(r"<!--\s*template_version:\s*([^\s>]+)\s*-->")

#: Wat er in de prompt komt te staan voor een leeggelaten optioneel veld. Bewust geen lege string:
#: de coach moet het VERSCHIL zien tussen "hier staat niets" en "dit heb ik niet ingevuld", want
#: alleen dan kan hij ernaar vragen in plaats van eroverheen te lezen.
LEEG = "not provided"

#: Wat er in een gelogde rij komt te staan als het sheet geen `Coach version`-regel droeg. Bewust
#: een woord en geen lege string: "we weten het niet" is een ander feit dan "er was geen versie".
ONBEKENDE_VERSIE = "unknown"

#: De velden van het formulier, in de volgorde van de scope. `verplicht` bepaalt alleen of het
#: formulier erop staat te wachten; de renderer vult elk ontbrekend veld met LEEG.
VELDEN: tuple[tuple[str, bool], ...] = (
    ("decision", True),
    ("deadline", True),
    ("options", True),
    ("reversibility", False),
    ("stakes", False),
    ("facts", False),
    ("decider", False),
    ("stakeholders", False),
    ("leaning", False),
    ("confidence", False),
    ("role", False),
    ("mode", False),
)

#: De vaste keuzes. Ze staan hier en niet in de view, zodat de test ze kan lezen zonder HTML.
REVERSIBILITY = ("easily reversible", "reversible at a cost", "not really reversible")
MODES = ("FULL", "SHORT")
#: Chips in plaats van een schuifbalk: een schuifbalk suggereert een precisie die niemand heeft,
#: en het designsysteem heeft er geen klasse voor.
CONFIDENCE = ("10", "30", "50", "70", "90")


class SjabloonOntbreekt(FileNotFoundError):
    """Er is geen sjabloon om mee te renderen, dus er komt geen prompt."""


def pad(base_dir: str) -> str:
    return os.path.join(base_dir, MAP, BESTAND_EN)


def laad(base_dir: str) -> tuple[str, str]:
    """Geeft (sjabloontekst, versie). Gooit `SjabloonOntbreekt` als het bestand er niet is.

    De versie is wat er in de marker staat; ontbreekt die, dan is de versie leeg — en dat is een
    zichtbaar feit in de gelogde rij, geen gok."""
    p = pad(base_dir)
    try:
        with open(p, encoding="utf-8") as fh:
            tekst = fh.read()
    except OSError as e:
        raise SjabloonOntbreekt(
            f"Template not found at {p}. The Decision Coach renders a human-maintained template; "
            f"without it there is no prompt.") from e
    m = _VERSIE_RE.search(tekst.splitlines()[0] if tekst.splitlines() else "")
    return tekst, (m.group(1) if m else "")


def versie(base_dir: str) -> str:
    """De versie van het sjabloon op schijf, of "" als er geen sjabloon of geen marker is."""
    try:
        return laad(base_dir)[1]
    except SjabloonOntbreekt:
        return ""


def render(sjabloon: str, waarden: dict, versie: str = "") -> str:
    """Vervang elke `{{naam}}` door de ingevulde waarde, of door `not provided`.

    `{{template_version}}` is GEEN formulierveld: hij komt uit de versiemarker van het sjabloon
    zelf. Het sjabloon laat de coach die regel letterlijk in het decision sheet overnemen, zodat
    het sheet zijn eigen herkomst draagt. Zou deze waarde uit de invoer komen, dan kon een lid hem
    overschrijven; zou hij bij het loggen van schijf worden gelezen, dan logde een sheet van vorige
    week de versie van vandaag — stilzwijgend fout in precies het veld waarop je later vertrouwt.

    Alleen de velden uit `VELDEN` worden verder vervangen. Een onbekende placeholder blijft staan
    zoals hij is: dat is zichtbaar in de uitvoer en dus te repareren in het sjabloon, terwijl stil
    weglaten een gat oplevert dat niemand opmerkt."""
    uit = sjabloon
    for naam, _ in VELDEN:
        waarde = str(waarden.get(naam, "") or "").strip() or LEEG
        uit = uit.replace("{{" + naam + "}}", waarde)
    return uit.replace("{{template_version}}", versie or ONBEKENDE_VERSIE)


def bouw_prompt(base_dir: str, waarden: dict) -> tuple[str, str]:
    """Het hele pad: laden, versie lezen, invullen. Geeft (prompt, versie)."""
    sjabloon, v = laad(base_dir)
    return render(sjabloon, waarden, v), v
