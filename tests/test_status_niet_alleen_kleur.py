"""Een status leunt nooit alleen op kleur.

HETZELFDE PRINCIPE DAT HIER AL DRIE KEER IS TOEGEPAST, nu als ratchet: `.nu-status` draagt een vorm
én een woord, de bordkolommen dragen een merkteken vóór de kop, en de ongelezen-indicator in
Messages leunt bewust op drie dingen tegelijk (gewicht, telling, tint). Wat ontbrak was iets dat
het merkt als er een vierde bijkomt die het niet doet.

WAT "ALLEEN KLEUR" HIER BETEKENT. Een selector die een van de statustinten als achtergrond zet en
verder NIETS: geen randstijl, geen vorm, geen tweede eigenschap waaraan je hem in zwart-wit nog
herkent. De tekst of het icoon in de markup telt ook mee, maar die kan deze test niet zien — daarom
staat naast elke uitzondering in `TWEEDE_DRAGER_IN_DE_MARKUP` waar die drager dan wél zit.

DE MEETMETHODE IS DIE VAN DE FASE-12-AUDIT, letterlijk: selectors in `nooch.css` die
`--green-tint`, `--yellow-light`, `--error-tint`, `--coral` of `--goal-tint` als *background*
zetten. Dat was toen een telling (63 → 64 → 33); dit is diezelfde telling met een oordeel erachter.

DE TWEE UITZONDERINGEN UIT FASE 12 (niet opnieuw aanraken): een gestippelde status HOUDT zijn lijn,
want gestippeld betekent "nog niet gevuld" en dat bestaat niet zonder lijn; en een rode status
houdt zijn lijn, want rood is de enige plek waar de kleur zelf semantisch draagt. Die twee staan in
`nooch-ui.css` en vallen buiten dit bestand — deze test kijkt naar de basislaag.
"""
from __future__ import annotations

import pathlib
import re

_STATIC = pathlib.Path(__file__).resolve().parents[1] / "nooch_village" / "static"
CSS = (_STATIC / "nooch.css").read_text()
NU = (_STATIC / "nooch-ui.css").read_text()
_ONTCOM = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), CSS, flags=re.S)

#: De tinten die in dit systeem een STATUS dragen (de meetmethode van de fase-12-audit).
STATUSTINTEN = ("--green-tint", "--yellow-light", "--error-tint", "--coral", "--goal-tint")

#: Eigenschappen die naast kleur een tweede drager zijn: je ziet ze ook in zwart-wit.
TWEEDE_DRAGER = ("border-style", "border-left", "border-top", "border-right", "border-bottom",
                 "border:", "outline", "clip-path", "text-decoration", "font-weight",
                 "content", "box-shadow: inset")

#: Selectors waar de tweede drager in de MARKUP zit en niet in de CSS — met de vindplaats erbij,
#: want een uitzondering zonder bewijs is een vrijbrief.
TWEEDE_DRAGER_IN_DE_MARKUP = {
    ".kc-n": "het stapnummer staat ín het bolletje (views/metrics.py, `kc-step`)",
    ".noo-cta": "knop met het woord 'Noochie' erin (views/noochie.py)",
    ".noo-head": "kop met '🐸 Noochie' (views/noochie.py)",
    ".einddoc-banner": "'📄 Draft report — …' (views/rapport.py)",
    ".ck-skill": "de chip bevat de skill-NAAM als tekst (views/checklists.py)",
    ".ck-warn": "'⚠ payload incomplete' (views/checklists.py)",
    ".ck-human": "'🙋 human task …' (views/checklists.py)",
}


def _regels():
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", _ONTCOM):
        yield (" ".join(m.group(1).split()), " ".join(m.group(2).split()),
               _ONTCOM[:m.start()].count("\n") + 1)


def _heeft_nu_tegenhanger(sel: str) -> bool:
    """Stuurt `nooch-ui.css` deze klasse aan? Dan is de tint daar al vervangen door de systeemtaal
    en valt hij buiten deze telling — precies de afbakening die de fase-12-audit hanteerde
    (64 selectors in het basis-stylesheet, waarvan 33 zonder tegenhanger)."""
    return any(re.search(rf"\.nu[^{{]*[\s.]{re.escape(k)}\b", NU)
               for k in re.findall(r"\.([a-z0-9_-]+)", sel))


def _kleur_alleen() -> list[tuple[str, str, int]]:
    uit = []
    for sel, body, lijn in _regels():
        if not any(re.search(rf"background[^;]*var\({t}\)", body) for t in STATUSTINTEN):
            continue
        if any(d in body for d in TWEEDE_DRAGER):
            continue
        if _heeft_nu_tegenhanger(sel):
            continue
        uit.append((sel, body, lijn))
    return uit


def test_geen_statusindicator_leunt_alleen_op_kleur():
    fout = [f"nooch.css:{lijn}  {sel}" for sel, _b, lijn in _kleur_alleen()
            if sel not in TWEEDE_DRAGER_IN_DE_MARKUP]
    assert fout == [], (
        "deze selectors zetten een statustint als achtergrond en hebben verder geen enkele "
        "eigenschap die in zwart-wit overblijft. Geef ze een vorm, een randstijl of een woord — "
        "of, als de tweede drager in de markup zit, zet hem met vindplaats in "
        "TWEEDE_DRAGER_IN_DE_MARKUP.\n" + "\n".join(fout))


def test_de_uitzonderingen_bestaan_nog_echt():
    """Een uitzonderingenlijst die naar verdwenen selectors wijst, is een lijst die niets meer
    toelaat én niets meer uitlegt. Verdwijnt er een, dan hoort hij hier ook weg."""
    aanwezig = {sel for sel, _b, _l in _regels()}
    weg = [s for s in TWEEDE_DRAGER_IN_DE_MARKUP if s not in aanwezig]
    assert weg == [], f"deze uitzonderingen bestaan niet meer als selector: {weg}"


# ── de drie gevallen die op 20 september zijn rechtgezet ──────────────────────────────────────

def test_de_missie_stip_draagt_een_vorm_per_waarde():
    """Drie stippen die alleen in kleur verschilden, met de betekenis in een `title` — en een title
    verschijnt niet op een telefoon. Nu: gevulde cirkel, open ring, driehoek."""
    vormen = {sel: body for sel, body, _l in _regels() if sel.startswith(".mdot.")}
    assert "clip-path" in vormen[".mdot.r"]                    # driehoek
    assert "border" in vormen[".mdot.n"] and "background:none" in vormen[".mdot.n"]  # open ring
    assert "var(--green)" in vormen[".mdot.g"]                 # gevuld, de basisvorm is al rond


def test_de_checklist_rijen_dragen_een_randstijl():
    """Solide = gemist, gestippeld = te doen, niets = gedaan. Drie standen, ook zonder kleur."""
    per = {sel: body for sel, body, _l in _regels() if sel.startswith(".cl-")}
    # DE BASIS STAAT OP `.cl-row` (22 sept 2026): een doorzichtige 3px-rand op ÉLKE rij, zodat
    # de tekst van een rij mét status niet 3px opschuift ten opzichte van de rij erboven. De
    # twee standen variëren daar alleen nog op — `.cl-attn` erft `solid`, `.cl-todo` zet
    # `dashed`. Deze test las eerst `solid` letterlijk in `.cl-attn`; dat zou nu een terugkeer
    # van de dubbele declaratie afdwingen.
    basis = next(b for s, b, _ in _regels() if s.split(",")[0].strip() == ".cl-row")
    assert "solid" in basis and "transparent" in basis
    assert "dashed" in per[".cl-todo"]
    assert "dashed" not in per[".cl-attn"]          # blijft dus solide


def test_de_drie_gevallen_dragen_ook_een_woord():
    """Een vorm en een randstijl helpen wie KIJKT. Een schermlezer ziet geen van beide, dus het
    woord staat er in de markup bij — dat is de derde drager, net als bij de ongelezen-indicator."""
    proj = (pathlib.Path(__file__).resolve().parents[1]
            / "nooch_village" / "views" / "projects.py").read_text()
    ck = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "views" / "checklists.py").read_text()
    assert "class='sr'>Mission impact:" in proj
    assert "aria-hidden='true'" in proj                       # de stip zelf zwijgt dan
    assert "Missed" in ck and "Due" in ck and "class='sr'>" in ck
