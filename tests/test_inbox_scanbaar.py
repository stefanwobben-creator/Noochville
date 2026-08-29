"""Inbox scanbaar — één regel per item, met chip, bevinding en de hoofdactie inline.

Drie beloften:
  1. je ziet per regel WAT er van je gevraagd wordt (besluit / verzoek / governance);
  2. je leest de bevinding, niet de interne verpakking;
  3. je kunt een item afhandelen zonder de modal te openen — met dezelfde knoppen, niet een
     tweede set.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views.inbox import (_besluit_knoppen, _een_regel, _verzoek_knoppen,
                                       render_inbox, render_verwerk)

ROL = "mother_earth__nooch__creator_of_shoes"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _item(st, **extra):
    return st.notif.add("role", ROL, extra.pop("pid", ""), by="harry_hemp",
                        snippet="Project van X vastgelopen op 1 mens-/extern item", extra=extra)


# ── 1. de chip zegt wat er van je gevraagd wordt ────────────────────────────

def test_elk_type_krijgt_zijn_eigen_chip(tmp_path):
    dd, st = _st(tmp_path)
    for soort, woord in (("founder", "besluit"), ("naar_rol", "verzoek"),
                         ("governance", "governance")):
        st.notif._items = []
        _item(st, type=soort)
        html = render_inbox(st, [("role", ROL)], csrf_token="t")
        assert f"<span class='chip outline'>{woord}</span>" in html, soort


def test_een_item_zonder_type_krijgt_geen_verzonnen_chip(tmp_path):
    dd, st = _st(tmp_path)
    _item(st)
    html = render_inbox(st, [("role", ROL)], csrf_token="t")
    for woord in ("besluit", "verzoek", "governance"):
        assert f"<span class='chip outline'>{woord}</span>" not in html


# ── 2. de bevinding, niet de verpakking ─────────────────────────────────────

def test_de_regel_toont_de_bevinding_als_die_er_is():
    n = {"snippet": "Project van X vastgelopen op 1 mens-/extern item",
         "bevinding": {"ok": True, "spanning": "De leverancier reageert niet meer op onze mail."}}
    assert _een_regel(n) == "De leverancier reageert niet meer op onze mail."


def test_een_afgekeurde_bevinding_wint_niet_van_de_ruwe_tekst():
    """`ok=False` betekent: deze tekst haalde de poort niet. Hem tóch tonen zou een halve zin als
    samenvatting presenteren."""
    n = {"snippet": "de ruwe signalering",
         "bevinding": {"ok": False, "spanning": "…afgekapte", "reden": "houdt middenin op"}}
    assert _een_regel(n) == "de ruwe signalering"


# ── 3. afhandelen zonder modal, met dezelfde knoppen ────────────────────────

def test_een_verzoek_is_af_te_handelen_vanuit_de_lijst(tmp_path):
    dd, st = _st(tmp_path)
    _item(st, type="naar_rol")
    html = render_inbox(st, [("role", ROL)], csrf_token="t")
    assert "handle here" in html
    for actie in ("accepteer", "aanpassen", "weiger"):
        assert f"value='{actie}'" in html
    assert "value='verzoek_besluit'" in html
    assert "value='notif_klaar'" in html


def test_de_lijst_gebruikt_dezelfde_knoppen_als_de_verwerkpagina(tmp_path):
    """Geen tweede set: als de verwerk-pagina er een veld bij krijgt, krijgt de lijst hem ook."""
    dd, st = _st(tmp_path)
    n = _item(st, type="naar_rol")
    lijst = render_inbox(st, [("role", ROL)], csrf_token="t")
    for blok in _verzoek_knoppen(n, "t").split("</details>"):
        if blok.strip():
            assert blok in lijst
    assert _verzoek_knoppen(n, "t") in render_verwerk(st, n, csrf_token="t")


def test_zonder_bron_geen_lege_uitklap(tmp_path):
    """Een item zonder verzoek-type en zonder bron-project heeft geen knop die in één handeling
    klopt. Dan komt er geen uitklap — een lege accordeon is erger dan geen accordeon."""
    dd, st = _st(tmp_path)
    _item(st, type="governance")
    html = render_inbox(st, [("role", ROL)], csrf_token="t")
    assert "handle here" not in html
    assert "More…" in html                       # de diepte blijft bereikbaar


def test_ja_nee_suggestie_alleen_met_een_bron_om_op_te_antwoorden(tmp_path):
    dd, st = _st(tmp_path)
    assert _besluit_knoppen({"id": "x"}, "t") == ""
    assert "notif_besluit" in _besluit_knoppen({"id": "x", "project_id": "p1"}, "t")


def test_zonder_schrijfsessie_geen_knoppen(tmp_path):
    """Geen csrf = geen schrijf-sessie. Dan ook geen actie in de lijst (fail-closed)."""
    dd, st = _st(tmp_path)
    _item(st, type="naar_rol")
    html = render_inbox(st, [("role", ROL)], csrf_token="")
    assert "handle here" not in html


# ── 4. een actie uit het werkoverleg ────────────────────────────────────────

def test_een_actie_krijgt_zijn_eigen_chip(tmp_path):
    """Als 'verzoek' zou de kaart vragen of het bij je rol past. Dat gesprek is in het overleg al
    gevoerd — de afspraak staat, alleen de uitvoering niet."""
    dd, st = _st(tmp_path)
    _item(st, type="actie")
    html = render_inbox(st, [("role", ROL)], csrf_token="t")
    assert "<span class='chip outline'>actie</span>" in html


def test_de_actiekaart_vraagt_niet_opnieuw_om_akkoord(tmp_path):
    """Twee handelingen, geen intentie-wizard: afvinken, of er een project van maken."""
    dd, st = _st(tmp_path)
    n = _item(st, type="actie")
    html = render_verwerk(st, n, csrf_token="t")
    assert "Wat doe je met deze actie?" in html
    assert "notif_klaar" in html                      # afvinken
    assert "maak er een project van" in html
    assert "Wat doe je met dit verzoek?" not in html  # niet de verzoek-kaart
    assert "What do you need?" not in html            # en niet de volle wizard


def test_de_actiekaart_toont_geen_kaal_persoons_id(tmp_path):
    """De founder-kaart vertelt "<rol> werpt dit op" en zoekt die rol op in de records. Bij een
    actie staat er een PERSOON in `by` — die vindt hij niet, en dan stond er een kaal id op het
    scherm. De herkomst van een actie is het overleg."""
    dd, st = _st(tmp_path)
    mens = st.people.all()[0]
    n = st.notif.add("person", mens.id, "", by=mens.id,
                     snippet="reply to complaint e-mail",
                     extra={"type": "actie", "herkomst": "↳ uit het werkoverleg van nooch"})
    html = render_verwerk(st, n, csrf_token="t")
    assert mens.id not in html                            # nergens een kaal id
    assert "werpt dit op" not in html                     # en niet de rol-kaart
    assert "Actie voor jou" in html          # herkomst-neutraal: de bron staat in `herkomst`
    assert "↳ uit het werkoverleg van nooch" in html


# ── 5. de woorden volgen het type ───────────────────────────────────────────

def test_een_actie_heet_geen_spanning(tmp_path):
    """Eén neutrale term is voor alles half goed: "spanning" klopt voor een gesensd signaal maar
    niet voor een afspraak uit een overleg. De kaart weet zijn type al."""
    dd, st = _st(tmp_path)
    mens = st.people.all()[0]
    n = st.notif.add("person", mens.id, "", by=mens.id, snippet="reply to complaint",
                     extra={"type": "actie"})
    html = render_verwerk(st, n, csrf_token="t")
    assert "<h1>Actie afronden</h1>" in html
    assert "<h3>Actie</h3>" in html
    assert "Actie afgerond" in html
    # niet op het losse woord toetsen: dat staat ook in een CSS-klassenaam. De ZICHTBARE koppen.
    for spanningswoord in ("Process tension", "<h3>Tension</h3>", "Done with this tension"):
        assert spanningswoord not in html, spanningswoord


def test_de_andere_soorten_houden_hun_eigen_woorden(tmp_path):
    """Verzoek houdt zijn vocabulaire, governance en besluit blijven ongewijzigd, en alles zonder
    eigen type blijft 'tension' — anders verandert dit label-werk stilletjes vier schermen."""
    dd, st = _st(tmp_path)
    for soort in ("naar_rol", "governance", "founder", ""):
        st.notif._items = []
        n = _item(st, **({"type": soort} if soort else {}))
        html = render_verwerk(st, n, csrf_token="t")
        assert "<h1>Process tension</h1>" in html, soort or "(typeloos)"
        assert "Actie afronden" not in html, soort or "(typeloos)"
