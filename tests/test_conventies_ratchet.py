"""Één mechaniek per ding — als poortje, niet als voornemen.

Bijna elke bug van 28 augustus 2026 was een tweede mechaniek voor iets dat al bestond: een tweede
terug-URL in een fragment, een tweede plek waar een actie landde, een tweede telling van hetzelfde
overleg. Ze faalden allemaal stil. Een tweede vorm van hetzelfde is geen extra functie; het is een
divergentie die op zijn moment wacht.

Twee poorten hier (de rest staat in `docs/CONVENTIES.md` met zijn eigen ratchet):

  1. DE STORES ZIJN BEVROREN. Een tweede checklist-store, een tweede meldingskanaal of een tweede
     projectstore verschijnt onvermijdelijk als een nieuw attribuut op `_Stores`. Toevoegen mag —
     maar dan bewust, met een regel erbij en een reden.
  2. ÉÉN PROJECTCREATIE-FORMULIER. Een mens maakt een project via de wizard. Elk ander formulier
     dat rechtstreeks een project aanmaakt is de tweede vorm.
"""
from __future__ import annotations

import pathlib
import re
import tempfile

from nooch_village import cockpit2

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"

# ── 1. de stores ────────────────────────────────────────────────────────────
#
# Voeg je er één toe, zet hem hier ERBIJ met een reden in de commit. Dat is de hele bedoeling:
# een tweede store is een besluit, geen bijvangst.
STORES = {
    "agenda", "ai", "assign", "att", "backlog", "checklists", "copy_stack", "defs",
    "deliverables", "evidence", "kennisbank", "library", "link_kroniek", "match", "metrics",
    "nom_kroniek", "nominations", "noochie", "notes", "notif", "observations", "people",
    "personas", "project_docs", "projects", "radar", "radar_besluiten", "records", "sources",
    "spel", "staging", "strategies", "werk",
}


def test_de_stores_zijn_bevroren():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    nu = {k for k in vars(st) if not k.startswith("_") and k != "dd"}
    erbij = nu - STORES
    assert erbij == set(), (
        f"nieuwe store(s) {sorted(erbij)} — zoek eerst de bestaande mechaniek (docs/CONVENTIES.md). "
        "Is het écht een nieuw ding, zet hem dan in STORES met een reden in de commit.")
    weg = STORES - nu
    assert weg == set(), f"store(s) verdwenen: {sorted(weg)} — haal ze uit STORES zodat de lijst klopt"


# Er zijn DRIE postbussen, en ze zijn geen variant van elkaar:
#
#   NotifStore  de inbox van een MENS — meldingen, spanningen, acties uit een overleg;
#   Inbox       de werkwachtrij van een INWONER (thread) — toegewezen werk dat áf moet;
#   HumanInbox  het geauthenticeerde lokale approval-oppervlak (governance, activaties).
#
# Een vierde is wél een tweede postbus: dan mist iemand de helft van zijn werk en merkt niemand het.
POSTBUSSEN = {"NotifStore", "Inbox", "HumanInbox"}


def test_er_komt_geen_vierde_postbus_bij():
    klassen = set()
    for f in ROOT.rglob("*.py"):
        for m in re.finditer(r"^class (\w*Notif\w*|\w*Inbox\w*)\b", f.read_text(encoding="utf-8"),
                             re.M):
            klassen.add(m.group(1))
    erbij = klassen - POSTBUSSEN
    assert erbij == set(), (
        f"nieuwe postbus-achtige klasse(n): {sorted(erbij)}. Er zijn er drie en ze doen elk iets "
        "anders (mens / inwoner-thread / approval) — zie docs/CONVENTIES.md. Is dit echt een vierde "
        "soort, zet hem dan in POSTBUSSEN met een reden.")
    weg = POSTBUSSEN - klassen
    assert weg == set(), f"postbus verdwenen: {sorted(weg)} — werk POSTBUSSEN bij"


# ── 2. projectcreatie ───────────────────────────────────────────────────────
#
# Een mens maakt een project via de WIZARD.
#
# DE POORT BEWAAKT ALLEEN WAT HIJ TELT. Deze telde eerst één actienaam (`proj_add`), en toen bleef
# er een formulier op het bord staan dat de wizard opende maar er precies uitzag als een tweede
# creatie-vorm: twee tekstvelden en een groene knop. De telling zei nul, het scherm zei anders.
# Daarom telt hij nu de VORM: elk veld waarmee je een project zou beschrijven bij het aanmaken.
# Een volgende poging met andere veldnamen valt dan alsnog op.
#: De bekende, BEWUSTE voorkomens — met hun aantal, zodat de telling nooit meer nul kan zijn
#: zonder dat iemand het merkt. Als `proj_add` ooit verdwijnt, valt de "schuld opgeruimd"-regel
#: onderaan om en zegt hij dat je dit getal moet verlagen. Dát is wat een lege dict niet kon.
PROJ_FORM_PLAFOND: dict[str, int] = {
    # De dispatch-tabel + de handler zelf: `proj_add` is de OUDE directe actie, die nog leeft voor
    # de kolom-ingang op het bord. Geen formulier — een actienaam.
    "cockpit2.py": 1,
    # De project-JS reageert op de actienaam (sluit de kolom na een toevoeging). Ook geen formulier.
    "views/projects.py": 1,
}

# `done_when` als formulierveld = de creatie-vorm: alleen bij het AANMAKEN vraag je vooraf "hoe
# weet je dat dit klaar is". `proj_add` = de oude directe actie.
#
# `scope` staat er bewust NIET bij: dat veld zit ook op het bewerk-formulier van een bestaand
# project (de titel wijzigen), en dat is iets anders dan een project aanmaken. Een patroon dat
# beide vangt zou de ratchet permanent rood zetten, en een rode ratchet die je moet negeren is
# geen poort meer.
#
# DE PATRONEN ZIJN OP 8 SEPTEMBER GEREPAREERD, WANT ZE TELDEN NUL. Ze zochten naar letterlijke
# HTML in de BRONTEKST (`value='proj_add'`, `name='done_when'`), en die staat er niet meer: sinds
# de `web_base._field()`-helper worden formuliervelden GEGENEREERD, met dubbele aanhalingstekens
# en met de naam als functieargument. De actie `proj_add` leeft gewoon (`cockpit2.py:6004`) en het
# veld `done_when` ook (`cockpit2.py:1299`) — de ratchet zag alleen de vorm van vroeger.
#
# Dat is dezelfde fout die deze poort zelf al twee keer heeft gedocumenteerd ("de poort bewaakt
# alleen wat hij telt"), nu een laag dieper: hij bewaakte de SCHRIJFWIJZE in plaats van het
# resultaat. De patronen zijn daarom quote-agnostisch en er staat een tweede test onder die de
# ECHTE HTML rendert — als de generator morgen weer verandert, valt die om en deze niet.
_VORMEN = (re.compile(r"""["']proj_add["']"""),
           re.compile(r"""name=["']done_when["']|_field\([^)]*["']done_when["']"""))


def _creatie_vormen() -> dict[str, int]:
    uit: dict[str, int] = {}
    for f in sorted(ROOT.rglob("*.py")):
        rel = str(f.relative_to(ROOT))
        tekst = f.read_text(encoding="utf-8")
        n = sum(len(r.findall(tekst)) for r in _VORMEN)
        if n:
            uit[rel] = n
    return uit


def test_geen_tweede_projectcreatie_vorm():
    nu = _creatie_vormen()
    nieuw = {k: v for k, v in nu.items() if k not in PROJ_FORM_PLAFOND}
    assert nieuw == {}, (
        f"nieuwe projectcreatie-vorm in {sorted(nieuw)} — een mens maakt een project via de wizard "
        "(/project/nieuw), zodat rol, uitkomst, impact, checklist en toewijzing één vorm hebben. "
        "Een ingang mag een DEUR zijn (een link met voorvulling), geen tweede formulier.")
    te_hoog = {k: (v, PROJ_FORM_PLAFOND[k]) for k, v in nu.items() if v > PROJ_FORM_PLAFOND[k]}
    assert te_hoog == {}, f"plafond overschreden (nu, max): {te_hoog}"
    gedaald = {k: (nu.get(k, 0), v) for k, v in PROJ_FORM_PLAFOND.items() if nu.get(k, 0) < v}
    assert gedaald == {}, f"schuld opgeruimd — verlaag PROJ_FORM_PLAFOND: {gedaald}"


def test_de_ratchet_meet_iets():
    """HANDHAVING VEREIST WAARNEEMBAARHEID — nu op de ratchet zelf toegepast.

    Een telling die nul teruggeeft is niet te onderscheiden van een telling die niets kán zien, en
    tussen de `_field()`-migratie en 8 september was dit precies dat: beide patronen matchten
    nergens meer, want de HTML wordt sindsdien gegenereerd (dubbele quotes, naam als argument) en
    de wizard is bovendien een JS-form dat zijn body zelf opbouwt. De poort stond op groen en keek
    nergens naar.

    Deze test eist dat de telling NIET-NUL is. Dat is de goedkoopste vorm van waarneembaarheid:
    zolang `PROJ_FORM_PLAFOND` bekende voorkomens noemt, zegt een nul dat de patronen blind zijn
    geworden — en dan valt de "schuld opgeruimd"-regel hierboven óók om, met de instructie erbij."""
    nu = _creatie_vormen()
    assert nu, ("_VORMEN matcht nergens meer — de ratchet is blind, niet schoon. Kijk hoe de "
                "creatie-vorm nu geschreven wordt (`web_base._field()`? een JS-form?) en pas de "
                "patronen aan voordat je deze test groen maakt.")
    assert sum(nu.values()) >= len(PROJ_FORM_PLAFOND)


#: De plekken waar een MENS een project aanmaakt. Twee wegen, allebei bewust: de wizard is de
#: hoofdingang, `proj_add` is de kolom-ingang op het bord die dezelfde regels toepast (de
#: cardinaliteitswet staat in beide, met in `/wizard/create` letterlijk de comment "een regel die
#: maar op één van de twee geldt is geen regel").
_MENS_CREATIE = {
    "cockpit2.py:_act_proj_add",
    "cockpit2.py:/wizard/create",
}


def test_er_zijn_precies_twee_wegen_waarop_een_mens_een_project_maakt():
    """De vraag waar de vorm-telling een pròxy voor is, nu direct gesteld.

    De vorm-ratchet telt formuliervelden; dit telt CREATIE-AANROEPEN met `trigger="human"`. Een
    derde weg is precies wat de conventie verbiedt, en die glipt langs een veld-telling heen zodra
    hij andere veldnamen gebruikt — wat de wizard letterlijk deed (`uitkomst` in plaats van
    `done_when`) en waardoor niemand doorhad dat de telling nul stond."""
    import re as _re
    bron = (ROOT / "cockpit2.py").read_text(encoding="utf-8")
    regels = bron.splitlines()
    # `create(..., "human")` op de projectstore. Niet elke aanroep is een MENS-formulier: de
    # kanaal- en spanning-routes maken ook projecten, maar via een bestaand pad met een vaste vorm.
    creaties = [i + 1 for i, r in enumerate(regels)
                if _re.search(r'\b(pj|st\.projects|projects)\.create\(', r)]
    assert creaties, "geen enkele projectcreatie gevonden — het patroon is verouderd"
    # De twee MENS-ingangen dragen allebei `trigger="human"` ÉN een done-when uit een formulier.
    # De andere creaties zijn afgeleide routes met een andere trigger (`founder_flow` bij de
    # radar, `human` zonder done-when bij de kanaal-route) — die hebben geen eigen invulscherm.
    met_formulier = [n for n in creaties
                     if any('"human"' in r for r in regels[n - 1:n + 4])
                     and any("done_when=" in r for r in regels[n - 1:n + 4])]
    assert len(met_formulier) == len(_MENS_CREATIE), (
        f"{len(met_formulier)} creatie-aanroepen met een eigen done-when op regel(s) "
        f"{met_formulier} — verwacht {len(_MENS_CREATIE)}: {sorted(_MENS_CREATIE)}. Een derde weg "
        f"om als mens een project te maken is de tweede vorm die deze conventie verbiedt.")


def test_het_bord_toont_zelf_geen_formulier():
    """Gedrag naast de telling: de kolomingang is een link naar de wizard, geen invulvelden."""
    from nooch_village.views.projects import _quickadd
    q = _quickadd("mother_earth__nooch__website_developer", "actief", "t", "/node?id=x")
    assert "/project/nieuw?" in q and "role=" in q
    assert "<textarea" not in q and "<form" not in q


def test_de_bekende_ingangen_wijzen_naar_de_wizard():
    """Gedrag naast de telling: het bord en de inbox mogen niet zelf een project maken."""
    from nooch_village.views.inbox import _outcome_form
    from nooch_village.views.projects import _quickadd

    bord = _quickadd("mother_earth__nooch__website_developer", "actief", "t", "/node?id=x")
    assert "/project/nieuw?" in bord and "proj_add" not in bord
    inbox = _outcome_form("project", "n", "t", "tekst", "<option>r</option>", "", "/inbox", "u")
    assert "/project/nieuw?" in inbox and "notif_outcome" not in inbox


def test_de_conventies_staan_opgeschreven():
    """Een regel die alleen in een test staat vindt niemand terug."""
    doc = (ROOT.parent / "docs" / "CONVENTIES.md").read_text(encoding="utf-8")
    for mechaniek in ("NV.swap", "NotifStore", "de wizard", "data-qa-frag"):
        assert mechaniek in doc, mechaniek
    # De meta-les onder de projectcreatie-poort, de postbus-blinde-vlek, de afslank-poort én de
    # herschrijf-poort: alle vier waren een regel die niets kon waarnemen.
    assert "Handhaving vereist waarneembaarheid" in doc
    assert "MENS_GETYPT" in doc
    # En de trede daarboven: de afslank-poort is het vangnet voor wat je NIET kunt weghalen, geen
    # vervanging van het weghalen zelf (de cadans verhuisde naar dagcyclus.py).
    assert "Tonen is zwakker dan wegnemen" in doc
    # De kern van 30 aug: bewijs raak je niet aan, en een poort meet zijn uitkomst.
    assert "Bewijs blijft woordelijk" in doc
    assert "Een ratchet toetst gedrag, niet broncode" in doc
    assert "Chrome is Engels, inhoud is Nederlands" in doc
    assert "Onafhankelijke deelchecks dekken verschillende assen" in doc
    assert "Consolideer het mechaniek, niet de copy" in doc
    assert "Routeer op leven, niet op vermogen" in doc
    assert "Een droge run rekent door hetzelfde pad, of hij liegt" in doc
    assert "Een test die van de datum afhangt, injecteert de datum" in doc
    assert "De afzender is niet de auteur" in doc
    assert "Eén bewaakte schrijfroute per store" in doc
    assert "Meet de compositie, niet één ingrediënt" in doc
    assert "Literaal token is laag 1, claim-concept is laag 2" in doc
    assert "Structuur botst met content die de structuur bevat" in doc
    # Drie instanties in één week: dan is "later" een fictie.
    assert "Bij de derde instantie migreer je de KLASSE" in doc
    # De checker levert mechaniek, de policy levert de regel.
    assert "hij bevat nooit een regel" in doc
    assert "een bevinding zonder bronpolicy kan niet bestaan" in doc.lower()
    # De splitsing zelf, en de drie poorten die hem bewaken.
    assert "de code levert het *mechanisme*" in doc
    for poort in ("onbekende regelnaam", "leeg anker", "anker niet in de prosa"):
        assert poort in doc
    # Een lege uitkomst is een uitkomst.
    assert "zonder laag-1-voetafdruk is een geldige uitkomst" in doc
    # Volgorde van de tekst, niet van de lus.
    assert "in de volgorde waarin de LEZER het tegenkomt" in doc
    # Identifier versus label, en chrome volgt zijn lezer.
    assert "Een identifier is mechaniek, een label is content" in doc
    # De duurdere variant van no_data != nul: wat stilte met de LEZER doet.
    assert "Een onwaarneembare nul fabriceert verklaringen" in doc
    # Cache versus record bij een corrupt bestand.
    assert "Leeg beginnen mag dus, stil beginnen niet" in doc
    # Het meetinstrument zelf valideren voor je een afwezigheid meldt.
    assert "Valideer je meetinstrument voor je een afwezigheid meldt" in doc
    # Een weigering mag nooit als succes renderen.
    assert "Vals succes is erger dan stille mislukking" in doc
    assert "aan de SERVERKANT gemarkeerd" in doc
    assert "niet-leeg teruggaf" in doc
    assert "elke tak die niets doet, logt waar\u00f3m hij niets doet" in doc
    assert "chrome volgt zijn lezer" in doc.lower()
    assert "Grond stopt fabricatie, niet irrelevantie" in doc
    # Eén getal kan stijgen terwijl de suggesties slechter worden: lees het paar.
    assert "Twee getallen, niet" in doc
    assert "De poort verifieert dat het bewijs BESTAAT, niet dat het PAST" in doc
    assert "Een transportfout is onbekend, geen leegte" in doc
    # De keerzijde: los van elkaar trekken mag geen stilte opleveren bij echte uitval.
    assert "aanhoudende ophaalfout is nog steeds een capaciteitsprobleem" in doc
    assert "Drie verwerkingsuitkomsten, en weigeren zit er niet bij" in doc
    # De kern van die conventie, niet de voetnoot: een werkwoord dat werk stopt is
    # daarom geen uitkomst.
    assert "Het werkwoord bepaalt of het werk doorloopt" in doc
    assert "tests/test_conventies_ratchet.py" in doc      # het doc wijst naar zijn eigen poortje
