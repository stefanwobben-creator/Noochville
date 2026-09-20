"""Fase 10 — de huisstijl uit de échte nooch.earth-beelden, en de dekking van `nooch-ui.css`.

Twee soorten bewaking:

1. **De kleurwaarden zijn gesampled, niet gekozen.** Ze komen uit `claude/huisstijl_referentie_*`
   (elke pixel geteld met Pillow, zie `claude/fase10_huisstijl_inventarisatie.md` §5). Wie ze
   wijzigt moet opnieuw samplen, niet schatten — dat is precies de fout die deze fase begon: zes
   van de acht "afwijkingen" die ik eerst rapporteerde waren getoetst aan een beschrijving in
   woorden en niet aan het beeld, en bleken pixel-exact goed te staan.

2. **Een klassenfamilie doet pas mee als `nooch-ui.css` hem aanstuurt.** `/project/nieuw` stond
   gewoon in `_NU_ROUTES` en zag er tóch oud uit, omdat de wizard met een eigen `wz-*`-familie
   rendert. Route in de lijst ≠ herstyled.
"""
from __future__ import annotations

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
NU = (REPO / "nooch_village" / "static" / "nooch-ui.css").read_text()
OUD = (REPO / "nooch_village" / "static" / "nooch.css").read_text()

_ONTCOM = lambda t: re.sub(r"/\*.*?\*/", "", t, flags=re.S)


def _tokens(css: str) -> dict[str, str]:
    blok = re.search(r"\.nu\s*\{(.*?)\n\}", _ONTCOM(css), re.S)
    assert blok, "het .nu-tokenblok is niet te vinden"
    return dict(re.findall(r"(--nu-[a-z-]+)\s*:\s*([^;]+);", blok.group(1)))


def test_de_kleuren_zijn_de_gesampelde_waarden():
    """Elke waarde hieronder is geteld in claude/huisstijl_referentie_email.png of
    -productpagina.jpg. Verandert er één, dan hoort daar een nieuwe sampling bij."""
    t = _tokens(NU)
    assert t["--nu-bg"] == "#FFFAFA"            # 84,4% van de e-mail
    assert t["--nu-surface"] == "#FFFFFF"       # 6,4%
    assert t["--nu-neon"] == "#00FF00"          # de CTA-vulling, met zwarte tekst erop
    assert t["--nu-accent"] == "#00A551"        # de aankondigingsbalk, met witte tekst erop
    assert t["--nu-bg-alt"] == "#E2FFE3"        # het lichtgroene vlak (18% van de productpagina)
    assert t["--nu-accent-text"] == "#1F9D55"   # #14713C kwam in geen van beide beelden voor
    assert t["--nu-muted"] == "#58595B"
    assert t["--nu-border-subtle"] == "#E6E7E8"
    assert t["--nu-text"] == "#000000"          # bewust één token: #1A1A1A is met het oog gelijk


def test_de_referentiebeelden_staan_in_de_repo():
    """Zonder de beelden is de vorige test een lijst getallen zonder herkomst."""
    for naam in ("huisstijl_referentie_productpagina.jpg", "huisstijl_referentie_email.png"):
        p = REPO / "claude" / naam
        assert p.exists() and p.stat().st_size > 100_000, naam


def test_att_en_qadd_worden_aangestuurd():
    """De twee families die in zes views terugkomen. Zie §3 groep A van de inventarisatie."""
    for klasse in ("att-lbl", "att-body", "att-name", "att-ic", "att-sep", "att-pop",
                   "qadd", "qadd-form", "qadd-x"):
        assert re.search(rf"\.nu[^{{]*\.{re.escape(klasse)}\b", NU), f".{klasse} mist een nu-regel"


def test_elke_oude_look_op_att_en_qadd_is_overschreven():
    """Structureel, niet op naam: pak elke selector in nooch.css die op een `att-`/`qadd-`-klasse
    een radius, schaduw of rand zet, en eis dat nooch-ui.css diezelfde klasse aanstuurt."""
    schuldig = set()
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _ONTCOM(OUD)):
        if not re.search(r"(border-radius|box-shadow|border)\s*:", body):
            continue
        for k in re.findall(r"\.((?:att|qadd)[a-z-]*)", sel):
            schuldig.add(k)
    for k in sorted(schuldig):
        assert re.search(rf"\.nu[^{{]*\.{re.escape(k)}\b", NU), \
            f".{k} zet in nooch.css nog rand/radius/schaduw en wordt niet overschreven"


def test_de_qadd_schaduw_is_expliciet_uitgezet():
    """`.qadd-form textarea` was het enige invoerveld met een `box-shadow`. Een schaduw is in deze
    huisstijl geen stijlkeuze maar een fout — de referentie heeft er nul."""
    assert re.search(r"\.nu \.qadd-form textarea\s*\{[^}]*box-shadow:\s*none", NU, re.S)
    assert "var(--shadow)" in OUD          # hij staat er nog, voor de geparkeerde schermen


def test_geen_enkele_nieuwe_regel_valt_buiten_de_nu_scope():
    """Eén regel zonder `.nu` ervoor raakt élk scherm, ook de 27 geparkeerde."""
    regels = [r.split("{")[0].strip() for r in _ONTCOM(NU).split("}") if "{" in r]
    buiten = [r for r in regels if r and not r.startswith(".nu") and not r.startswith("@")]
    assert not buiten, f"regels buiten de scope: {buiten}"


# ── Typografie: de vier punten die de referentiebeelden letterlijk tonen ─────────────────────

def test_koppen_staan_in_hoofdletters():
    """NINE PLANTS, ONE SHOE · GROW A PAIR · QUESTIONS PEOPLE ACTUALLY ASKED. Er staat geen enkele
    kop in onderkast op de productpagina. `.nu h2, .nu h3` zette hier eerst `text-transform: none`."""
    for sel in (r"\.nu h1", r"\.nu h2, \.nu h3"):
        blok = re.search(rf"{sel}\s*\{{([^}}]*)\}}", NU, re.S)
        assert blok, sel
        assert "text-transform: uppercase" in blok.group(1), sel
    assert "text-transform: none" not in _ONTCOM(NU).split(".nu .pill")[0]


def test_knoptekst_staat_in_hoofdletters():
    """ORDER NOW · BECOME FOUNDING MEMBER · ALL REVIEWS · READ THE LETTERS."""
    blok = re.search(r"\.nu \.btn \{([^}]*)\}", NU, re.S)
    assert blok and "text-transform: uppercase" in blok.group(1)


def test_geen_enkele_ronde_hoek_meer():
    """Structureel, niet op naam: élke border-radius in het bestand moet 0 zijn, met als enige
    uitzondering de 50% van de statusvormen — dat is vorm-codering, geen decoratie.
    `.c2-navct` stond op 999px en was de laatste overgebleven pil."""
    waarden = {w.strip() for w in re.findall(r"border-radius:\s*([^;}]+)", _ONTCOM(NU))}
    assert waarden <= {"0", "50%"}, f"onverwachte radius: {waarden - {'0', '50%'}}"


def test_elke_eyebrow_in_de_oude_css_wordt_aangestuurd():
    """De vingerafdruk van een eyebrow: klein, hoofdletters, vet. Elke selector in nooch.css die
    daaraan voldoet moet binnen `.nu` een tegenhanger hebben — anders staat er op een van de
    negentien schermen nog een groen-of-grijs labeltje in de oude maatvoering."""
    # Bewust buiten beeld, met de reden erbij. Geen stille uitzonderingen.
    BUITEN = {
        ".tile-t": "staat op /metrics2, een van de 27 geparkeerde schermen",
        ".fkind": "geen enkele view rendert hem nog — dode CSS na fase 1-9",
        ".einddoc-toggle": "idem, dode CSS",
        ".smeta dt": "idem, dode CSS",
        ".kn-spelvraag .wie": "kennisbank-UI, in fase 2b verwijderd — dode CSS",
        ".wz-now .lb": "idem, dode CSS",
    }
    gemist = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _ONTCOM(OUD)):
        maat = re.search(r"font-size:\s*\.(\d+)rem", body)
        if not (maat and int(maat.group(1)[:2].ljust(2, "0")) <= 78):
            continue
        if "text-transform:uppercase" not in body.replace(" ", ""):
            continue
        if "font-weight:700" not in body.replace(" ", ""):
            continue
        if sel.strip() in BUITEN:
            continue
        kern = sel.strip().split()[-1].lstrip(".")
        if not re.search(rf"\.nu[^{{]*[\s.]{re.escape(kern)}\b", NU):
            gemist.append(sel.strip())
    assert not gemist, f"eyebrow-achtige selectors zonder nu-regel: {gemist}"


def test_de_eyebrow_is_een_definitie_en_geen_twaalfde_naam():
    """Elf namen wijzen naar één regel. Zou elk van die elf een eigen blok krijgen, dan is het
    probleem dat deze stap oplost gewoon verplaatst."""
    assert NU.count("text-transform: uppercase; letter-spacing: .06em") == 1
    vorm = re.search(r"([^{}]*\.nu-eyebrow[^{}]*)\{[^}]*letter-spacing: \.06em", NU, re.S)
    assert vorm and len(re.findall(r"\.nu ", vorm.group(1))) >= 10


def test_link_knoppen_staan_ook_in_hoofdletters():
    """`+ add project` en `by role / by person` zijn links die als knop gelezen worden. Ze vielen
    buiten `.nu .btn` en bleven dus in onderkast staan terwijl de echte knoppen al om waren — in de
    broncode onzichtbaar, in de browser meteen te zien."""
    blok = re.search(r"\.nu \.addlink, \.nu \.vswitch a, \.nu \.flink \{([^}]*)\}", NU, re.S)
    assert blok and "text-transform: uppercase" in blok.group(1)


def test_green_dark_ratchet():
    """#14713C komt in GEEN van beide referentiebeelden voor, en staat 57 keer in nooch.css.

    Dit is een ratchet in de vorm die het dorp al kent (`_STYLE_WHITELIST`, `_PREFIX_CEILING`):
    het getal mag alleen omlaag. Elke stap van groep A die een scherm aanpakt hoort er een paar af
    te halen; komt er één bij, dan is er een oude groene kleur teruggekropen op een scherm dat al
    om was.
    """
    _PLAFOND = 36          # 20 sep, na groep A+B+C: 57 selectors, 21 met een nu-tegenhanger
    zonder = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _ONTCOM(OUD)):
        if "var(--green-dark)" not in body:
            continue
        kern = sel.strip().split(",")[0].strip().split()[-1].lstrip(".").split(":")[0]
        if kern and not re.search(rf"\.nu[^{{]*[\s.]{re.escape(kern)}\b", NU):
            zonder.append(sel.strip()[:40])
    assert len(zonder) <= _PLAFOND, (
        f"{len(zonder)} selectors met --green-dark zonder nu-tegenhanger (plafond {_PLAFOND}). "
        f"Gestegen? Dan is er een oude groentint teruggekomen: {zonder[:5]}")


# ── De dekkings-ratchet per view ─────────────────────────────────────────────────────────────

VIEWS = REPO / "nooch_village" / "views"

#: Hoeveel klasse-gebruiken per view dragen nog de oude look zónder tegenhanger in nooch-ui.css.
#: Zelfde vorm als `_STYLE_WHITELIST` en `_PREFIX_CEILING`: het getal mag alleen OMLAAG. Een view
#: die stijgt heeft een nieuwe klasse gekregen uit het oude palet — dat is de fout die deze hele
#: fase opruimt, en dan wil je het bij het schrijven weten en niet bij een screenshot.
_DEKKING_PLAFOND = {
    "projects.py": 7,        # rest is vorm, geen kleur: mform, mdot, car
    "messages.py": 1,
    "roloverleg.py": 1,      # `pdisc` zet alleen background:none/border:none
    "doelen.py": 0,
    "inbox.py": 0,
    "overview.py": 0,
    "search.py": 0,
    "site_audit.py": 0,
    "vangst.py": 0,
    "werkoverleg.py": 0,
    "wiki.py": 0,
    "wizard.py": 0,
}

_VISUEEL = re.compile(r"(background|border|border-radius|box-shadow|color|font-family)\s*:", re.I)
_BASIS = (REPO / "nooch_village" / "web_base.py").read_text()


def _oude_look_klassen() -> set[str]:
    uit = set()
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _ONTCOM(OUD) + "\n" + _ONTCOM(_BASIS)):
        if _VISUEEL.search(body):
            uit |= set(re.findall(r"\.([a-z0-9_-]+)", sel))
    return uit


def _open_uses(bestand: str, oude: set[str]) -> int:
    t = (VIEWS / bestand).read_text()
    n = 0
    for m in re.finditer(r"class=['\"]([^'\"]+)['\"]", t):
        for k in m.group(1).split():
            if not re.fullmatch(r"[a-z0-9_-]+", k) or k.startswith("js-"):
                continue
            if k in oude and not re.search(rf"\.nu[^{{]*[\s.]{re.escape(k)}\b", NU):
                n += 1
    return n


def test_dekking_per_view_gaat_alleen_omlaag():
    oude = _oude_look_klassen()
    te_hoog = {b: (_open_uses(b, oude), p) for b, p in _DEKKING_PLAFOND.items()
               if _open_uses(b, oude) > p}
    assert not te_hoog, f"boven het plafond (nu, plafond): {te_hoog}"


def test_het_plafond_staat_niet_te_ruim():
    """Een ratchet die tien boven de werkelijkheid staat bewaakt niets. Zakt een view, dan hoort
    het plafond in diezelfde commit mee te zakken."""
    oude = _oude_look_klassen()
    slap = {b: (_open_uses(b, oude), p) for b, p in _DEKKING_PLAFOND.items()
            if p - _open_uses(b, oude) > 0}
    assert not slap, f"plafond te ruim, verlaag het in deze commit (nu, plafond): {slap}"


def test_kleuren_zonder_merkdekking_worden_binnen_nu_geneutraliseerd():
    """--coral, --goal en het AI-paars komen in geen van beide referentiebeelden voor (0, 5 en 0
    pixels). Elke klasse die ze zet én op een nu-scherm staat, moet een tegenhanger hebben."""
    oude_klassen: dict[str, str] = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _ONTCOM(OUD)):
        for kleur in ("var(--coral)", "var(--goal)", "#7A5BD1"):
            if kleur in body:
                for k in re.findall(r"\.([a-z0-9_-]+)", sel):
                    oude_klassen[k] = kleur
    gebruikt = set()
    for bestand in _DEKKING_PLAFOND:
        t = (VIEWS / bestand).read_text()
        for m in re.finditer(r"class=['\"]([^'\"]+)['\"]", t):
            gebruikt |= set(m.group(1).split())
    # Wat er nog staat, met de view waar het thuishoort. Deze lijst mag alleen KORTER worden:
    # elke stap van groep A/C die een view aanpakt haalt er een paar af.
    _NOG_TE_DOEN = {
        "mdot",     # projects.py — een ronde stip van .55rem: vorm, geen kleur. Blijft staan.
    }
    gemist = [k for k in sorted(oude_klassen) if k in gebruikt
              and k not in _NOG_TE_DOEN
              and not re.search(rf"\.nu[^{{]*[\s.]{re.escape(k)}\b", NU)]
    assert not gemist, f"niet-merkkleuren nog levend op een nu-scherm: {gemist}"
    nog = {k for k in _NOG_TE_DOEN
           if not re.search(rf"\.nu[^{{]*[\s.]{re.escape(k)}\b", NU)}
    assert nog == _NOG_TE_DOEN, f"al afgehandeld, haal ze uit _NOG_TE_DOEN: {_NOG_TE_DOEN - nog}"


def test_routes_van_dezelfde_view_zitten_allemaal_in_de_nu_scope():
    """Groep B. `/middelen` en `/rolefillers` draaiden op dezelfde `overview.py` als `/node`,
    `/person` en `/admin` — maar stonden niet in `_NU_ROUTES`. Dezelfde rendercode zag er dus
    anders uit afhankelijk van de URL.

    Structureel geschreven: lees route→view uit de vindkaart, en eis dat een view die ÉÉN route in
    de scope heeft, ze allemaal in de scope heeft. Zo valt een volgende splitsing ook op."""
    from nooch_village.cockpit2 import _NU_ROUTES

    kaart = (REPO / "docs" / "ARCHITECTUUR.md").read_text()
    per_view: dict[str, set[str]] = {}
    for m in re.finditer(r"^\| `([^`]+)` \| `([^`]+)` \| `([^`]+)` \|", kaart, re.M):
        per_view.setdefault(m.group(3), set()).add(m.group(1))

    # `cockpit2.py` is geen view maar de dispatcher: hij "rendert" ook /login, /logout en /file.
    # Dat die niet in de scope zitten is juist het besluit, geen gat.
    per_view.pop("cockpit2.py", None)

    gespleten = {v: sorted(r - set(_NU_ROUTES))
                 for v, r in per_view.items()
                 if r & set(_NU_ROUTES) and r - set(_NU_ROUTES)}
    assert not gespleten, f"view met routes binnen én buiten de nu-scope: {gespleten}"
