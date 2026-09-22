"""De live-join-knop en de herstructurering van het verwerkscherm (21 september 2026).

TWEE DINGEN, ÉÉN BEURT, want ze raken hetzelfde overleg.

1. LIVE-JOIN. Draait er een werkoverleg, dan wordt de knop in de balk "Join meeting" met een
   pulserend groen rondje. Polling, geen websocket — en de reden staat in de meting: de vraag
   kost 0,31 ms zolang je alleen de store bouwt die hem kan beantwoorden, tegen 70 ms voor alle
   stores samen. Alleen werkoverleg: roloverleg heeft geen open/dicht-staat (besluit Stefan).

2. HET VERWERKSCHERM. De spanning krijgt een band bovenaan in plaats van een klein uitklapje, en
   de Volgende/In-afwachting-keuze komt terug — schrijvend naar het PROJECT, niet naar een eigen
   veld op de uitkomst. Die keuze is op 29 augustus weggehaald omdat hij een tweede plek was die
   de wachtstatus bijhield; dat bezwaar is niet vervallen, alleen de oplossing van toen.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village import cockpit2
from nooch_village.cockpit2_util import overleg_items
from nooch_village.views.vangst import _spanning_titel, _uitkomst_formulier

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()

CIRCLE = "mother_earth__nooch"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    mens = st.people.add("Secretaris", "sec@test.nl")
    # De uitkomst-poort laat alleen de rolvervuller of de Circle Lead door. Zonder deze toewijzing
    # test je de poort en niet de wachtstand.
    st.assign.assign("mother_earth__nooch__creator_of_shoes", "person", mens.id)
    return dd, cockpit2._Stores(dd), mens


# ── 1. De live-knop ──────────────────────────────────────────────────────────
def test_de_knop_verandert_pas_als_er_echt_een_overleg_draait():
    dicht = overleg_items(CIRCLE)
    assert "Werk&shy;overleg" in dicht and "Join meeting" not in dicht
    open_ = overleg_items(CIRCLE, werk_open=True)
    assert "Join meeting" in open_ and "c2-overleg--live" in open_


def test_het_rondje_is_nooit_de_enige_drager():
    """Kleur alleen is nooit genoeg: een groen stipje is onzichtbaar in zwart-wit en voor wie
    groen niet ziet. De TEKST verandert mee, en het stipje draagt `aria-hidden` omdat het niets
    toevoegt voor wie het voorgelezen krijgt."""
    h = overleg_items(CIRCLE, werk_open=True)
    assert "Join meeting" in h                       # de tweede drager
    assert "<span class='c2-live' aria-hidden='true'></span>" in h


def test_alleen_het_werkoverleg_wordt_live():
    """Roloverleg heeft geen open/dicht-staat — zijn agenda is een lijst governance-voorstellen.
    Die staat erbij bouwen is een eigen klus en valt buiten deze ronde (besluit Stefan)."""
    h = overleg_items(CIRCLE, werk_open=True)
    rol = h.split("/roloverleg2")[1]
    assert "Join meeting" not in rol and "c2-live" not in rol


def test_de_pulse_gaat_uit_voor_wie_geen_beweging_wil():
    """Het stipje blijft staan, alleen het kloppen stopt — er gaat dus geen informatie verloren.
    Zelfde regel als bij `.ck-item.bezig`."""
    blok = "".join(CSS.split("@media (prefers-reduced-motion: reduce)")[1:])
    assert ".c2-live{animation:none}" in blok.replace(" ", "")


def test_de_poller_gedraagt_zich():
    """Drie dingen die een poller beschaafd houden: niets vragen als het tabblad verborgen is,
    bij een fout het interval verdubbelen in plaats van doorrammen, en niets vervangen als er
    niets veranderd is (anders verliest een knop die je aanwijst zijn hover)."""
    assert "document.hidden" in JS
    assert "wacht = Math.min(wacht * 2" in JS
    assert "if (nu === html) return;" in JS
    assert "visibilitychange" in JS


def test_de_poll_route_bouwt_niet_alle_stores():
    """DE HELE REDEN DAT DIT POLLING MAG ZIJN. Gemeten op productie: alle stores bouwen kost 70 ms
    per verzoek, `WerkoverlegStore(...).is_open()` 0,31 ms. Een poller die elke 20 seconden 70 ms
    serverwerk aanzet voor een ja/nee is geen polling maar een lek."""
    bron = (pathlib.Path(__file__).resolve().parents[1]
            / "nooch_village" / "cockpit2.py").read_text()
    blok = bron.split('if path == "/overleg-status":')[1].split("return")[0]
    # DE CODE, NIET DE UITLEG. De comment in dat blok NOEMT `_Stores(data_dir)` juist, om te
    # zeggen waarom het er niet staat. Een guard die zijn eigen verantwoording meetelt, verbiedt
    # de uitleg in plaats van de fout — dat is vandaag al drie keer gebeurd.
    code = "\n".join(r for r in blok.split("\n") if not r.lstrip().startswith("#"))
    assert "WerkoverlegStore" in code
    assert "_Stores(" not in code, "de poll-route bouwt alsnog alle stores"


def test_de_poll_route_faalt_closed(tmp_path):
    """Een onbekende cirkel, een kapot bestand: geen uitnodiging. Een knop die "Join meeting" zegt
    terwijl er niets draait, stuurt iemand een leeg scherm in."""
    assert overleg_items("") == ""
    assert "Join meeting" not in overleg_items(CIRCLE, werk_open=False)


# ── 2. De spanningsband ──────────────────────────────────────────────────────
def test_de_spanning_krijgt_een_band_en_geen_klein_regeltje(tmp_path):
    dd, st, mens = _dorp(tmp_path)
    it = {"id": "p1", "title": "FSC verloopt",
          "note": {"spanning": "De FSC-verklaring van Selco verloopt in november."}}
    h = _spanning_titel(st, CIRCLE, it, "TOK", "/x")
    assert "wo-band" in h
    assert "De FSC-verklaring van Selco verloopt in november." in h
    assert "wo-band-edit" in h                        # de bewerk-ingang, náást de tekst


def test_een_lege_band_zegt_wat_er_te_doen_is(tmp_path):
    """Leeg is een eigen toestand, geen leeg vlak — dat leest als een weergavefout."""
    dd, st, mens = _dorp(tmp_path)
    h = _spanning_titel(st, CIRCLE, {"id": "p1", "title": "t"}, "TOK", "/x")
    assert "nog geen spanning opgeschreven" in h
    assert "wo-band" in h


def test_de_band_vraagt_nog_steeds_niets(tmp_path):
    """DE REDEN DAT HET UITKLAPJE ER OOIT KWAM BLIJFT GELDEN: in een live overleg is er geen tijd
    om een spanning uit te schrijven, dus een groot invulvak bleef altijd leeg. De band TOONT; het
    tekstvak zit achter de potloodknop en springt niet vanzelf open."""
    dd, st, mens = _dorp(tmp_path)
    h = _spanning_titel(st, CIRCLE, {"id": "p1", "title": "t"}, "TOK", "/x")
    assert "<details class='wo-band-edit'>" in h      # dicht, geen `open`
    assert "<textarea" in h                           # het vak bestaat wel, achter de klik


def test_de_band_gebruikt_hetzelfde_opslagpad(tmp_path):
    """Alleen de INGANG is verplaatst. Eén actie, één opslagpad — anders ontstaat er een tweede
    waarheid over wat de spanningstekst is."""
    dd, st, mens = _dorp(tmp_path)
    h = _spanning_titel(st, CIRCLE, {"id": "p1", "title": "t"}, "TOK", "/x")
    assert h.count("value='vangst_tekst'") == 1


# ── 3. De status-keuze ───────────────────────────────────────────────────────
def test_de_keuze_staat_er_alleen_bij_een_project(tmp_path):
    dd, st, mens = _dorp(tmp_path)
    h = _uitkomst_formulier(st, CIRCLE, {"id": "abc", "title": "t"}, "TOK", "/x")
    # HERBOUWD OP 22 SEPTEMBER: het veld zat in een `.wo-staat`-div in één plat raster, nu in
    # het secundaire blok (`.uk-subveld`). De regel is dezelfde gebleven — verborgen bij het
    # laden, zichtbaar bij een project — en dat is wat hier gemeten wordt.
    rij = re.search(r"<div class='uk-subveld' data-staat-voor='[^']*'([^>]*)>", h)
    assert rij and "hidden" in rij.group(1), "de keuze staat open bij een actie-uitkomst"
    assert "'project'" in h


def test_de_keuze_is_het_widget_en_de_taal_van_het_bord(tmp_path):
    """GEEN TWEEDE VOCABULAIRE VOOR DEZELFDE STATUS. Dit begon als een eigen radio-paar met eigen
    woorden ("Volgende"/"In afwachting") — twee termen voor precies de statussen die het bord al
    "Active" en "Waiting" noemt, terwijl dit formulier dáárheen schrijft. Nu: hetzelfde
    `.ctrl`-pulldown-atoom als op het bord, dezelfde labels uit `_PROJ_CHIP`, en de opgeslagen
    waarden zijn de projectstatussen zelf (besluit Stefan, 21 september 2026)."""
    from nooch_village.views.projects import _PROJ_CHIP
    dd, st, mens = _dorp(tmp_path)
    h = _uitkomst_formulier(st, CIRCLE, {"id": "abc", "title": "t"}, "TOK", "/x")
    rij = re.search(r"<div class='uk-subveld' data-staat-voor=.*?</select></div>", h, re.S).group(0)
    assert "<select class='ctrl'" in rij and "radio" not in rij
    assert f">{_PROJ_CHIP['running'][0]}<" in rij and f">{_PROJ_CHIP['blocked'][0]}<" in rij
    assert "value='running' selected" in rij and "value='blocked'" in rij
    # en geen eigen enum meer op het schrijfpad
    bron = (pathlib.Path(__file__).resolve().parents[1]
            / "nooch_village" / "cockpit2.py").read_text()
    assert 'g("staat") == "blocked"' in bron


def test_in_afwachting_zet_het_project_op_blocked(tmp_path):
    """DE KERN VAN DE AFSPRAAK. De keuze schrijft naar de plek waar de waarheid al staat, niet
    naast die plek. Zou hij een eigen veld op de uitkomst zetten, dan houden twee plekken
    hetzelfde bij en lopen ze na een week uit de pas — precies waarom hij op 29 augustus wegging."""
    dd, st, mens = _dorp(tmp_path)
    it = st.werk.backlog_add(CIRCLE, "FSC verloopt", by_id=mens.id)
    voor = {p["id"] for p in st.projects.all()}
    cockpit2.dispatch(dd, "vangst_uitkomst", {
        "csrf": ["t"], "circle": [CIRCLE], "iid": [it["id"]], "otype": ["project"],
        "tekst": ["Nieuwe leverancier zoeken"], "rol": ["Creator of shoes"], "persoon": [""],
        "staat": ["blocked"], "next": ["/x"]}, username="sec@test.nl")
    st2 = cockpit2._Stores(dd)
    nieuw = [p for p in st2.projects.all() if p["id"] not in voor]
    assert len(nieuw) == 1
    assert nieuw[0]["status"] == "blocked"
    assert "werkoverleg" in (nieuw[0].get("blocked_on") or "")
    # en geen tweede plek die hetzelfde bijhoudt
    uit = st2.werk.punt_get(CIRCLE, it["id"])["uitkomsten"][0]
    assert "staat" not in uit


def test_volgende_laat_het_project_gewoon_beginnen(tmp_path):
    dd, st, mens = _dorp(tmp_path)
    it = st.werk.backlog_add(CIRCLE, "FSC verloopt", by_id=mens.id)
    voor = {p["id"] for p in st.projects.all()}
    cockpit2.dispatch(dd, "vangst_uitkomst", {
        "csrf": ["t"], "circle": [CIRCLE], "iid": [it["id"]], "otype": ["project"],
        "tekst": ["Nieuwe leverancier zoeken"], "rol": ["Creator of shoes"], "persoon": [""],
        "staat": ["running"], "next": ["/x"]}, username="sec@test.nl")
    st2 = cockpit2._Stores(dd)
    nieuw = [p for p in st2.projects.all() if p["id"] not in voor]
    assert len(nieuw) == 1 and nieuw[0]["status"] != "blocked"


def test_een_wachtstand_op_een_governance_punt_doet_niets(tmp_path):
    """Die gaat naar het roloverleg en heeft daar zijn eigen agenda. Fail-closed: een keuze die
    nergens landt hoort ook niets te doen, ook niet als hij toch wordt meegepost."""
    dd, st, mens = _dorp(tmp_path)
    it = st.werk.backlog_add(CIRCLE, "Rol onduidelijk", by_id=mens.id)
    voor = {p["id"] for p in st.projects.all()}
    cockpit2.dispatch(dd, "vangst_uitkomst", {
        "csrf": ["t"], "circle": [CIRCLE], "iid": [it["id"]], "otype": ["governance"],
        "tekst": ["Domein toevoegen"], "rol": ["Creator of shoes"], "persoon": [""],
        "staat": ["blocked"], "next": ["/x"]}, username="sec@test.nl")
    st2 = cockpit2._Stores(dd)
    assert {p["id"] for p in st2.projects.all()} == voor      # geen project, dus niets geblokkeerd


# ── 4. De live-knop moet ook echt renderen ───────────────────────────────────
#
# GEVONDEN IN DE LIVE-DOORLOOP, niet door een test. De knop werd wél "Join meeting", maar bleef
# zwart-op-crème: `.c2-subnav a` (0,1,1) zet `background:none` en `color:var(--ink)`, en won
# daarmee van `.c2-overleg--live` (0,1,0). Specificiteit wint van bronvolgorde, dus hoger in het
# bestand zetten had niets geholpen. Het WITTE stipje stond op een crème vlak en was onzichtbaar;
# het enige signaal dat overbleef was de tekstwissel.
#
# Dezelfde fout trof óók de gewone overleg-knoppen: die hebben hun groene tint nooit gehad.

def _spec(sel: str) -> tuple:
    """(id's, klassen, elementen) — de drie tellers van CSS-specificiteit, genoeg voor deze vraag."""
    sel = re.sub(r"::?[a-z-]+(\([^)]*\))?", " ", sel)          # pseudo's tellen niet mee hier
    ids = len(re.findall(r"#[\w-]+", sel))
    klassen = len(re.findall(r"[.\[][\w-]+", sel))
    elementen = len(re.findall(r"(?:^|[\s>+~])([a-z][\w-]*)", sel))
    return (ids, klassen, elementen)


def _regels(css: str, naald: str, *, zet: str = "") -> list:
    """De selectors van regels die `naald` bevatten — en, met `zet`, alleen die ook die
    eigenschap zetten.

    DAT FILTER IS NODIG EN NIET KOSMETISCH. `.c2-side--rail .c2-subnav a` is (0,2,1) maar zet
    alleen `justify-content` en `padding`: hij is geen concurrent voor de kleur. Een toets die
    hem meetelt eist een specificiteit die niets oplost — en dwingt daarmee een steeds langere
    selector af voor een conflict dat niet bestaat."""
    zonder = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    return [sel.strip() for sel, body in re.findall(r"([^{}]*)\{([^{}]*)\}", zonder)
            if naald in sel and (not zet or re.search(rf"(^|;)\s*{zet}\s*:", body))]


def test_de_live_knop_wint_van_de_nav_regel():
    """DE GUARD. Niet "de regel staat er" maar "de regel wint" — dat is wat er misging."""
    nav = [s for s in _regels(CSS, ".c2-subnav a", zet="background")
           if "hover" not in s and ".c2-overleg" not in s]
    assert nav, "de nav-regel is verdwenen; deze toets meet dan niets meer"
    hoogste_nav = max(_spec(s) for r in nav for s in r.split(","))
    for klasse in (".c2-overleg", ".c2-overleg--live"):
        regels = [s for s in _regels(CSS, klasse) if "hover" not in s]
        assert regels, f"{klasse} heeft geen regel meer"
        for r in regels:
            for sel in r.split(","):
                if klasse in sel:
                    assert _spec(sel) > hoogste_nav, (
                        f"{sel.strip()} {_spec(sel)} verliest van {hoogste_nav} — "
                        f"de knop rendert dan kleurloos, zoals op 21 september live bleek")


def test_ook_in_de_nu_laag_wint_hij():
    """`.nu .c2-subnav a` zet óók `color`. Een regel op `.nu .c2-overleg` zou daar gelijk mee
    staan en dan beslist de bronvolgorde — dezelfde val, één laag hoger."""
    nu = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch-ui.css").read_text()
    nav = [s for s in _regels(nu, ".nu .c2-subnav a", zet="color")
           if "hover" not in s and ".c2-overleg" not in s]
    assert nav
    hoogste = max(_spec(s) for r in nav for s in r.split(","))
    live = [s for s in _regels(nu, ".c2-overleg--live")]
    assert live, "de nu-laag kent de live-stand niet"
    for r in live:
        for sel in r.split(","):
            if ".c2-overleg--live" in sel:
                assert _spec(sel) > hoogste, f"{sel.strip()} verliest van {hoogste}"


def test_het_stipje_staat_nooit_op_zijn_eigen_kleur():
    """Wit op wit of neon op neon is geen stip. De knop-achtergrond en de stip-vulling moeten uit
    verschillende tokens komen — in beide lagen."""
    nu = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch-ui.css").read_text()
    for css, stip_naald in ((CSS, ".c2-live"), (nu, ".nu .c2-live")):
        live_naald = ".c2-overleg--live"
        zonder = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
        regels = [(sel.strip(), body) for sel, body in
                  re.findall(r"([^{}]*)\{([^{}]*)\}", zonder)]
        knop = next(b for sel, b in regels if live_naald in sel and "hover" not in sel)
        stip = next(b for sel, b in regels
                    if stip_naald in sel and "background" in b)
        knop_bg = re.search(r"background:\s*([^;}]+)", knop)
        stip_bg = re.search(r"background:\s*([^;}]+)", stip)
        assert knop_bg and stip_bg
        assert knop_bg.group(1).strip() != stip_bg.group(1).strip(), (
            f"stip en knop delen dezelfde vulling ({knop_bg.group(1).strip()})")


# ── 5. De vorm van het verwerkscherm (21 september 2026, na de screenshot) ───
#
# Vier dingen uit de live-doorloop. Drie visueel, één functioneel — en die laatste is geen
# smaakkwestie: een agenda die onder je handen herschikt terwijl je hem afwerkt, kost je je plek.

def test_de_agenda_staat_op_indien_volgorde_oudste_bovenaan(tmp_path):
    """DE FUNCTIONELE EIS. Hij stond op nieuwste-eerst: wie iets toevoegde zag het bovenaan
    springen terwijl de rest opschoof. Een overleg werkt van boven naar beneden door wat er ligt."""
    dd, st, mens = _dorp(tmp_path)
    ids = []
    for n in ("eerste", "tweede", "derde"):
        ids.append(st.werk.backlog_add(CIRCLE, n, by_id=mens.id)["id"])
    punten = cockpit2._Stores(dd).werk.punten(CIRCLE)
    assert [p["title"] for p in punten] == ["eerste", "tweede", "derde"]
    assert [p["id"] for p in punten] == ids


def test_afvinken_verplaatst_een_punt_niet(tmp_path):
    """EN HIJ HERSCHIKT NOOIT OP STATUS. Dat een punt is afgehandeld is een EIGENSCHAP van het
    punt, geen plek in de rij — doorgestreept blijven staan, niet naar onderen springen."""
    dd, st, mens = _dorp(tmp_path)
    for n in ("eerste", "tweede", "derde"):
        st.werk.backlog_add(CIRCLE, n, by_id=mens.id)
    st2 = cockpit2._Stores(dd)
    midden = st2.werk.punten(CIRCLE)[1]
    st2.werk.punt_afvinken(CIRCLE, midden["id"], True)
    na = cockpit2._Stores(dd).werk.punten(CIRCLE)
    assert [p["title"] for p in na] == ["eerste", "tweede", "derde"]
    assert na[1]["status"] == "done"


def test_de_selectie_mag_wel_het_eerste_open_punt_kiezen(tmp_path):
    """Volgorde en selectie zijn twee dingen. De lijst blijft staan; welk punt er OPEN staat mag
    wél het eerste nog niet afgetikte zijn — anders land je op iets dat al af is."""
    from nooch_village.views.vangst import actief_punt
    dd, st, mens = _dorp(tmp_path)
    for n in ("eerste", "tweede"):
        st.werk.backlog_add(CIRCLE, n, by_id=mens.id)
    st2 = cockpit2._Stores(dd)
    eerste = st2.werk.punten(CIRCLE)[0]
    st2.werk.punt_afvinken(CIRCLE, eerste["id"], True)
    punten = cockpit2._Stores(dd).werk.punten(CIRCLE)
    assert punten[0]["title"] == "eerste"                    # de volgorde staat vast
    assert actief_punt(punten) == punten[1]["id"]            # de selectie slaat 'm over


def _binnen_kaart(css: str, klasse: str) -> dict:
    """De declaraties van de regel die `klasse` BINNEN `.wo-ocd` aanstuurt.

    OP WOORDGRENS ZOEKEN, niet op substring: `.wo-ocd` bevat letterlijk `.wo-oc`, dus een naïeve
    `in`-test vond de kaartregel zelf en concludeerde dat het formulier zijn kader nog had."""
    heel = re.compile(rf"{re.escape(klasse)}(?![\w-])")
    zonder = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    for sel, body in re.findall(r"([^{}]*)\{([^{}]*)\}", zonder):
        if ".wo-ocd" in sel and heel.search(sel) and "summary" not in sel and "[open]" not in sel:
            return {k.strip(): v.strip() for k, v in
                    (d.split(":", 1) for d in body.split(";") if ":" in d)}
    return {}


def test_er_staat_geen_doos_in_een_doos_in_een_doos():
    """DRIE KADERS IN ELKAAR. De verwerken-balk had er een, de spanningsband erin nóg een, en het
    formulier daarin een derde. Box in box in box leest als vier losse dingen in plaats van één
    spanning die je behandelt. Eén buitenkaart, en lijnen erbinnen."""
    nu = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch-ui.css").read_text()
    for css, klassen in ((CSS, (".wo-band",)), (nu, (".wo-band", ".wo-oc"))):
        for klasse in klassen:
            regels = _binnen_kaart(css, klasse)
            assert regels, f"{klasse} wordt binnen de kaart niet aangestuurd"
            assert regels.get("border") == "0", f"{klasse} houdt zijn eigen kader"
            assert "border-bottom" in regels or "background" in regels


def test_de_uitkomstenlijst_hoort_bij_dezelfde_kaart():
    """Hij stond er zonder kader los onder, en oogde daardoor aangeplakt. Geen eigen doos erbij —
    een scheidingslijn, want het is een sectie van dezelfde kaart."""
    regels = _binnen_kaart(CSS, ".c2-sec")
    assert regels.get("border-top", "").endswith("var(--border)")
    assert "padding-top" in regels


def test_het_vinkje_en_opslaan_staan_op_een_rij(tmp_path):
    """DE OPLOSSING VAN TOEN IS VERVALLEN, DE KLACHT NIET. Vinkje en Opslaan stonden ooit in
    losse flexrijen onder het raster — Opslaan zweefde rechts met een gat ernaast. Dat werd
    opgelost door ze als rastercellen 7 en 8 in te voegen, en dát is op 22 september weer
    weggegaan: acht cellen in één raster gaf elk veld dezelfde visuele lading, en de verborgen
    status liet er een dode cel achter.

    Nu een eigen voetrij (`.uk-voet`): vinkje links, Opslaan rechts, met `space-between`. Geen
    raster, dus ook geen cel om leeg te laten — en de klacht van toen (een zwevende knop met
    een gat ernaast) blijft opgelost, want de rij zet ze zelf tegenover elkaar."""
    dd, st, mens = _dorp(tmp_path)
    h = _uitkomst_formulier(st, CIRCLE, {"id": "abc", "title": "t"}, "TOK", "/x")
    voet = h.split("class='uk-voet'")[1].rsplit("</div></form>", 1)[0]
    assert "type='checkbox'" in voet and "Opslaan" in voet
    assert voet.index("type='checkbox'") < voet.index("Opslaan")
    assert "qadd-row" not in h, "er staat nog een losse flexrij in het formulier"
    assert "<div></div>" not in h, "er staat nog een lege cel in het formulier"
