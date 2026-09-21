"""Fase 12 — wélk element een lijn krijgt, en hoe dik.

DE DIAGNOSE DIE DEZE FASE BEGON (Stefan, op het live resultaat van fase 9/10): alles oogt als
hetzelfde kader, dus knop, navigatie, informatie en label zijn niet meer van elkaar te
onderscheiden. De oorzaak was niet een verkeerde kleur of een verkeerd lettertype — het was dat de
kader-taal van een CONTAINER ook op alles anders was gezet.

DE ROLVERDELING, en dit bestand toetst hem op PATROON en niet op de exacte waarden:

    container (kaart, tabel, invoerveld)  de zwaarste lijn — `var(--nu-border)`, 2px
    primaire actie                        gevuld, GEEN lijn (de vulling is het signaal)
    secundaire actie                      wel een lijn, maar dunner dan een container
    navigatie / tabs / filters            geen lijn in rust; actief = gewicht of vulling
    label / badge / status                geen lijn; een lichte tint draagt het vlak
    informatie (cijfers, voortgang)       typografie en witruimte

WAAROM EEN TEST EN GEEN AFSPRAAK. Dezelfde reden als bij de inline-style-ratchet: de regel is niet
moeilijk, hij is onzichtbaar. De volgende `.chip`-variant die "even" `var(--nu-border)` pakt ziet
er in de editor identiek uit aan een goede, en pas op het scherm zie je dat er weer een doosje
bij is gekomen. Deze test kijkt naar de TOKENS, niet naar hoe iets eruitziet.

DE TWEEDE RONDE (20 september, besluit Stefan): de families die in de eerste ronde buiten de zes
afgesproken regels vielen, zijn alsnog meegenomen — zelfde regel, consequent doorgetrokken. Bij het
doorvoeren bleek de eerste telling (negen selectors) te grof: een deel daarvan zijn CONTAINERS
(`wz-card`, `cardmenu-b`, `eff`) en die horen hun lijn juist te houden. `test_de_containers_in_die_families_houden_hun_lijn` bewaakt dat, want een regel die "haal
overal het kader weg" wordt, sloopt de rolverdeling van de andere kant.
"""
from __future__ import annotations

import pathlib
import re

NU = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch-ui.css").read_text()
_ONTCOM = re.sub(r"/\*.*?\*/", "", NU, flags=re.S)

#: De klassen die per rol GEEN container-lijn mogen dragen. Een nieuwe knop of chip hoort hier bij
#: te komen; dat is goedkoper dan hem later op een screenshot terugvinden.
GEEN_CONTAINER_LIJN = ("btn", "pill", "chip", "badge", "cl-filter", "nu-status",
                       "c2-tabs", "c2-subnav", "msg-kanaal", "amber", "outline",
                       # Tweede ronde (20 sept, besluit Stefan): dezelfde regel doorgetrokken naar
                       # de families die in de eerste ronde buiten de zes vielen.
                       # (`ibx-plus`, `ibx-btn`, `ibx-alaan`, `ibx-add` en `ibx-launch` stonden
                       # hier ook, tot op 21 september bleek dat de inbox-lade nooit bestond.)
                       "wz-btn", "wz-add", "wz-chip", "wz-badge", "c2-burger",
                       # En het voortgangs-atoom: informatie, dus geen kader.
                       "nu-progress",
                       # Derde ronde (21 sept): een VELD is geen container. Zie
                       # `test_een_veld_draagt_een_onderlijn_geen_kader`.
                       "ctrl", "fieldform", "title-edit")

#: Het token dat de zwaarste lijn draagt. Eén plek, zodat "2px" hier geen tweede waarheid wordt.
CONTAINER_TOKEN = "var(--nu-border)"


def _regels() -> list[tuple[str, str]]:
    return [(" ".join(sel.split()), " ".join(body.split()))
            for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _ONTCOM)]


def _body(patroon: str) -> str:
    """De declaraties van de eerste regel waarvan de SELECTOR op dit patroon matcht.

    Het patroon matcht op de GENORMALISEERDE selector (zonder accolades), dus een patroon met
    begin- en eindanker betekent precies die ene regel: de kale knop en niet `.nu .btn:hover`."""
    for sel, body in _regels():
        if re.search(patroon, sel):
            return body
    raise AssertionError(f"geen regel gevonden voor {patroon!r}")


def _breedte(body: str) -> float:
    m = re.search(r"border(?:-\w+)?:\s*([\d.]+)px", body)
    assert m, f"geen expliciete randdikte in: {body[:80]}"
    return float(m.group(1))


def _randkleur(body: str) -> str:
    m = re.search(r"border(?:-color)?:[^;]*?(transparent|var\(--nu-[a-z-]+\))", body)
    return m.group(1) if m else ""


# ── de container houdt de zwaarste lijn ──────────────────────────────────────────────────────

def test_de_container_draagt_de_zwaarste_lijn():
    """Als dit omvalt is de hele rolverdeling zinloos: er is dan geen lijn meer om je aan te meten."""
    body = _body(r"\.nu \.card, \.nu \.box")
    assert CONTAINER_TOKEN in body
    assert "border-radius: 0" in body and "box-shadow: none" in body   # scherp en plat blijft


def test_de_zwaarste_lijn_is_twee_pixels():
    """Het token zelf, zodat de vergelijkingen hieronder ergens tegenaan kunnen meten."""
    tokenblok = re.search(r"\.nu\s*\{(.*?)\n\}", _ONTCOM, re.S).group(1)
    assert re.search(r"--nu-border:\s*2px solid", tokenblok)


# ── de zes doorgevoerde regels ───────────────────────────────────────────────────────────────

def test_de_secundaire_knop_is_dunner_dan_een_container():
    """DE KERN VAN DE KLACHT. `.btn` trok met 2px exact dezelfde lijn als een kaart, dus een knop
    naast een kaart las als nóg een vlak."""
    assert _breedte(_body(r"^\.nu \.btn$")) < 2.0


def test_de_primaire_knop_heeft_geen_zichtbare_rand():
    """De vulling ís het signaal; een rand erbovenop is een tweede signaal voor dezelfde betekenis.

    `transparent` en niet weggelaten: de rand telt mee in de hoogte, dus weghalen zou de knop
    kleiner maken dan zijn buren."""
    body = _body(r"^\.nu \.btn\.ok$")
    assert "var(--nu-neon)" in body                      # de vulling blijft
    assert _randkleur(body) == "transparent"


def test_een_etiket_is_geen_doosje():
    """101 voorkomens in 22 bestanden: één etiket met een kader valt niet op, honderd wel."""
    body = _body(r"\.nu \.pill, \.nu \.chip")
    assert _randkleur(body) == "transparent"
    assert "var(--nu-bg-alt)" in body                    # een lichte tint draagt het vlak


def test_ook_de_chip_varianten_dragen_geen_zwarte_lijn():
    """`.amber` en `.outline` zetten hun eigen rand; zonder deze regel staat er naast een kaderloos
    etiket alsnog een zwart doosje."""
    for patroon in (r"^\.nu \.amber$", r"^\.nu \.outline$"):
        body = _body(patroon)
        assert "var(--nu-text)" not in _randkleur(body), f"{patroon} draagt nog een zwarte lijn"


def test_filters_hebben_in_rust_geen_lijn_maar_actief_wel_vulling():
    """Een rij van zes filters las als zes doosjes. Het onderscheid hoort te zitten waar het iets
    zegt: welke staat er AAN."""
    assert _randkleur(_body(r"^\.nu \.cl-filter$")) == "transparent"
    aan = _body(r"^\.nu \.cl-filter\.on$")
    assert "background: var(--nu-text)" in aan


def test_de_status_verliest_zijn_kader_maar_niet_zijn_vorm():
    """DE TOEGANKELIJKHEIDSREGEL BLIJFT. Vorm plus woord dragen de betekenis; de rand was de derde
    drager en juist die maakte van elke status een doosje. Gaat de VORM ooit mee in zo'n opruiming,
    dan zegt een gekleurd vlakje niets meer in zwart-wit."""
    assert _randkleur(_body(r"^\.nu \.nu-status$")) == "transparent"
    assert re.search(r"\.nu \.nu-status::before\s*\{[^}]*content", _ONTCOM)
    for mod in ("ok", "open", "wait", "off"):
        assert re.search(rf"\.nu-status--{mod}::before", _ONTCOM), f"de vorm van --{mod} is weg"


def test_open_en_fout_houden_hun_lijn_om_een_reden():
    """Twee uitzonderingen, allebei betekenis in plaats van decoratie: gestippeld = nog niet
    ingevuld, rood = alarm. Een stippellijn zonder lijn bestaat niet, en rood is de enige status
    waar de kleur iets zegt dat de vorm niet kan overnemen."""
    assert "dashed" in _body(r"^\.nu \.nu-status--open$")
    assert "var(--nu-danger)" in _body(r"^\.nu \.nu-status--off$")


def test_de_actieve_tab_is_dunner_dan_een_container():
    assert _breedte(_body(r"^\.nu \.c2-tabs a\.on$")) < 2.0


# ── de ratchet ───────────────────────────────────────────────────────────────────────────────

def test_geen_knop_label_of_navigatie_pakt_de_container_lijn():
    """DE RATCHET. Niet "ziet het er goed uit" maar: grijpt een element uit een andere rol het
    token dat voor containers is? Een nieuwe chip-variant die `var(--nu-border)` pakt ziet er in de
    editor identiek uit aan een goede."""
    fout = []
    for sel, body in _regels():
        if CONTAINER_TOKEN not in body:
            continue
        for klasse in GEEN_CONTAINER_LIJN:
            # Exact die klasse in de selector, niet een naam die er toevallig mee begint
            # (`.pchip-k` is geen `.chip`, `.btn-groep` zou wel meetellen).
            if re.search(rf"\.{re.escape(klasse)}(?![\w-])", sel):
                fout.append(f"{sel} → {klasse}")
    assert fout == [], (
        "deze selectors dragen de CONTAINER-lijn terwijl hun rol dat niet toelaat "
        "(zie claude/fase12_hierarchie_audit.md):\n" + "\n".join(fout))


def test_de_containers_in_die_families_houden_hun_lijn():
    """DE ANDERE KANT VAN DEZELFDE REGEL. Bij het doorvoeren van de tweede ronde bleek de telling
    van negen te grof: een lade, een rij, een popover en een wizard-kaart zijn CONTAINERS, en die
    horen de zwaarste lijn juist te dragen. Zonder deze test leest de vorige als "haal overal het
    kader weg", en dan is de hiërarchie van de andere kant net zo hard weg."""
    houders = " | ".join(sel for sel, body in _regels() if CONTAINER_TOKEN in body)
    # (`ibx-drawer`, `ibx-row` en `ibx-head` stonden hier ook; de lade waar ze bij hoorden bleek
    # op 21 september 2026 niet te bestaan en is met stylesheet en al verwijderd.)
    for klasse in ("wz-card", "cardmenu-b", "eff"):
        assert re.search(rf"\.{re.escape(klasse)}(?![\w-])", houders), (
            f".{klasse} is een container en hoort {CONTAINER_TOKEN} te dragen")


def test_het_voortgangs_atoom_is_informatie_geen_container():
    """Een balkje krijgt geen kader; de baan laat al zien hoe lang hij is. Dit atoom is op
    20 september bewust mét lijn gebouwd omdat dat toen het systeem was — hij hoorde bij dit
    besluit en niet ervóór."""
    body = _body(r"^\.nu progress\.nu-progress$")
    assert re.search(r"border:\s*0", body)
    assert "var(--nu-border-subtle)" in body          # de baan, subtiel en niet zwart


# ── derde ronde: een veld is geen container (21 september 2026) ──────────────────────────────

#: De besturingselementen die een onderlijn dragen in plaats van een kader.
VELDEN = ("input[type=text]", "input[type=search]", "input[type=email]", "input[type=number]",
          "textarea", "select")


def test_een_veld_draagt_een_onderlijn_geen_kader():
    """DE AANLEIDING, geteld: de projectkaart-modal had tien losse 2px-kaders in één blik — titel,
    pakket-label, omschrijving, checklist, elk hand-off-knopje en elk veld in de Details-kolom.

    De fase-12-regel zei dat een invoerveld als container zijn kader mocht houden. Dat klopt op een
    scherm met één veld en valt om op een scherm met twaalf: precies de muur van hokjes die fase 12
    moest opheffen, nu in veldvorm. Een veld krijgt nu de lijn waar je TYPT en nergens anders."""
    regels = {sel: body for sel, body in _regels()}
    veldregel = next((b for s, b in regels.items()
                      if s.startswith(".nu input[type=text]") and "border-bottom" in b), None)
    assert veldregel, "de gedeelde veldregel bestaat niet"
    assert "border: 0" in veldregel
    assert "border-bottom: 1.5px solid var(--nu-text)" in veldregel
    for veld in VELDEN:
        assert veld in " ".join(regels), f"{veld} valt buiten de veldregel"


def test_de_plek_waar_je_typt_is_de_enige_die_opvalt():
    """Zonder focus-markering ruil je een muur van hokjes in voor een vlakte zonder oriëntatie."""
    focus = [b for s, b in _regels() if ":focus" in s and "border-bottom-color" in b]
    assert focus, "een veld in focus hoort zich te onderscheiden"
    assert any("var(--nu-accent)" in b for b in focus)


def test_omhulsels_houden_hun_kader():
    """De andere kant van dezelfde regel. Een kaart, een popover of de modal zelf IS een omhulsel;
    die 2px is precies wat een veld ervan onderscheidt. Verdwijnt dit, dan is er geen hiërarchie
    meer over — alleen nog een vlakte."""
    houders = " | ".join(sel for sel, body in _regels() if CONTAINER_TOKEN in body)
    for klasse in ("card", "ovl-box", "datepop", "fbubble", "pkaart"):
        assert re.search(rf"\.{re.escape(klasse)}(?![\w-])", houders), (
            f".{klasse} is een omhulsel en hoort {CONTAINER_TOKEN} te dragen")


def test_de_rij_om_een_veld_draagt_geen_eigen_lijn():
    """`.fieldform` is een rij met een veld en een knop erin. Een lijn om de rij én onder het veld
    is twee lijnen voor één ding — en dat is hoe de muur van hokjes ontstond."""
    assert "border-bottom: 0" in _body(r"^\.nu \.fieldform$")
