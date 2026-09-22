"""Een @-vermelding in een kanaalbericht komt aan bij de genoemde.

WAAROM DIT NODIG WAS. Een bericht in een kanaal is geen bericht AAN iemand: wie er niet toevallig
kijkt, mist het. `@naam` is precies het moment waarop de schrijver zegt dat het wél voor iemand
is. Op de project-wall gebeurde dat al (`_vermeldingen_naar_kanalen`); in Messages deed een
vermelding helemaal niets — hij was tekst met een apenstaartje ervoor.

WAT DEZE TESTS VASTZETTEN, en elke regel is een ander soort fout:

  * dat het bij de JUISTE mens landt, via dezelfde routering als elke andere signalering
    (persoon → die mens, rol → vervuller, geen vervuller → Circle Lead / founder). Geen tweede
    kopie van die tabel;
  * dat je geen kopie krijgt van iets dat al voor je neus staat: zit je in de DM met diegene,
    dan is de signalering letterlijk dezelfde tekst twee regels lager;
  * dat twee namen die naar hetzelfde doel wijzen één melding opleveren, niet twee;
  * dat er niets wordt gemeld als het bericht zelf niet geplaatst is.
"""
from __future__ import annotations

from nooch_village import channels, cockpit2
from nooch_village.cockpit2 import _vermeldingen_in_kanaal


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    zender = st.people.add("Afzender Anna", "anna@nooch.earth")
    doel = st.people.add("Doel Dirk", "dirk@nooch.earth")
    return dd, cockpit2._Stores(dd), zender.id, doel.id


def _dm_trail(st, a, b):
    return st.channels.trail(channels.dm_kanaal(a, b))


# ── 1. Hij komt aan ─────────────────────────────────────────────────────────────────────────
def test_een_vermelding_landt_in_de_dm_van_de_genoemde(tmp_path):
    dd, st, zender, doel = _dorp(tmp_path)
    kanaal = channels.circle_kanaal("mother_earth")
    n = _vermeldingen_in_kanaal(st, kanaal, "kun jij hier even naar kijken @Doel Dirk", zender)
    assert n == 1
    trail = _dm_trail(cockpit2._Stores(dd), zender, doel)
    assert len(trail) == 1
    assert "@Doel Dirk" in trail[0]["text"]
    assert (trail[0].get("herkomst") or {}).get("kanaal") == kanaal


def test_zonder_vermelding_gebeurt_er_niets(tmp_path):
    """Mutatie-controle: de test hierboven zou ook slagen als élk bericht een DM opleverde."""
    dd, st, zender, doel = _dorp(tmp_path)
    kanaal = channels.circle_kanaal("mother_earth")
    assert _vermeldingen_in_kanaal(st, kanaal, "gewoon een mededeling zonder iemand", zender) == 0
    assert _dm_trail(cockpit2._Stores(dd), zender, doel) == []


def test_een_rolvermelding_gaat_naar_de_vervuller(tmp_path):
    """DEZELFDE ROUTERING ALS DE REST. Niet omdat het hier toevallig ook zo uitkomt, maar omdat
    `signaal.ontvangers` het bepaalt — de functie die `stuur` zelf gebruikt."""
    dd, st, zender, doel = _dorp(tmp_path)
    rol = next(r for r in st.records.all()
               if not getattr(r, "archived", False) and r.id.endswith("__secretary"))
    st.assign.assign(rol.id, "person", doel)
    st = cockpit2._Stores(dd)
    from nooch_village.cockpit2_util import _name
    n = _vermeldingen_in_kanaal(st, channels.circle_kanaal("mother_earth"),
                                f"@{_name(rol)} kun jij dit vastleggen?", zender)
    assert n == 1
    assert len(_dm_trail(cockpit2._Stores(dd), zender, doel)) == 1


# ── 2. Geen dubbele signalering ─────────────────────────────────────────────────────────────
def test_in_de_dm_zelf_komt_er_geen_kopie_bij(tmp_path):
    """HET RANDGEVAL. Zit je al in het DM-kanaal met diegene, dan zou de signalering dezelfde
    tekst twee regels lager herhalen. Het bericht zelf staat er wél (dat plaatst `_act_msg_post`);
    er komt alleen niets bovenop."""
    dd, st, zender, doel = _dorp(tmp_path)
    dm = channels.dm_kanaal(zender, doel)
    assert _vermeldingen_in_kanaal(st, dm, "hoi @Doel Dirk, zie je dit?", zender) == 0
    assert _dm_trail(cockpit2._Stores(dd), zender, doel) == []


def test_in_de_dm_met_iemand_ANDERS_komt_hij_wel(tmp_path):
    """Mutatie-controle op de regel hierboven: het gaat om de dm met de GENOEMDE, niet om
    'je zit in een dm, dus stil'."""
    dd, st, zender, doel = _dorp(tmp_path)
    derde = cockpit2._Stores(dd).people.add("Derde Dana", "dana@nooch.earth")
    st = cockpit2._Stores(dd)
    dm_met_derde = channels.dm_kanaal(zender, derde.id)
    assert _vermeldingen_in_kanaal(st, dm_met_derde, "@Doel Dirk moet dit ook zien", zender) == 1
    assert len(_dm_trail(cockpit2._Stores(dd), zender, doel)) == 1


def test_jezelf_vermelden_levert_niets_op(tmp_path):
    dd, st, zender, _doel = _dorp(tmp_path)
    kanaal = channels.circle_kanaal("mother_earth")
    assert _vermeldingen_in_kanaal(st, kanaal, "noteer voor @Afzender Anna zelf", zender) == 0
    assert _dm_trail(cockpit2._Stores(dd), zender, zender) == []


def test_twee_verschillende_namen_voor_hetzelfde_doel_geven_een_melding(tmp_path):
    """MAX ÉÉN MELDING PER DOEL.

    DE EERSTE VERSIE VAN DEZE TEST BEWEES NIETS. Die zette dezelfde naam twee keer in de tekst —
    maar `_mentions_in` loopt over `by_name`, een dict op NAAM, dus die levert sowieso één
    treffer op. De test bleef groen met de ontdubbeling eruit gesloopt; een mutatie-controle
    liet dat zien.

    Het echte geval is twee VERSCHILLENDE namen die naar hetzelfde adres wijzen: de naam van een
    AI-inwoner staat in `by_name` als de ROL die hij vervult, dus `@Lara` en `@Librarian` zijn
    hetzelfde postvak. Twee keer sturen is twee keer dezelfde tekst in dezelfde DM."""
    dd, st, zender, doel = _dorp(tmp_path)
    rol = next(r for r in st.records.all()
               if not getattr(r, "archived", False) and r.id.endswith("__secretary"))
    st.assign.assign(rol.id, "person", doel)
    persona = st.personas.add("Sara de Schrijver")
    st.assign.assign(rol.id, "persona", persona.id)
    st = cockpit2._Stores(dd)
    from nooch_village.cockpit2_util import _name
    from nooch_village.views.feed import _mentionables
    _js, by_name = _mentionables(st)
    # Vóór de belofte: die twee namen moeten echt hetzelfde doel zijn, anders zegt de test niets.
    assert by_name[_name(rol).lower()] == by_name["sara de schrijver"] == ("role", rol.id)
    n = _vermeldingen_in_kanaal(st, channels.circle_kanaal("mother_earth"),
                                f"@{_name(rol)} — en @Sara de Schrijver, kijken jullie mee?",
                                zender)
    assert n == 1
    assert len(_dm_trail(cockpit2._Stores(dd), zender, doel)) == 1


# ── 3. Aan het bericht vast ─────────────────────────────────────────────────────────────────
def test_geen_bericht_geen_signalering(tmp_path):
    """Een lege tekst wordt niet geplaatst, en dan is er niets om iemand op te wijzen. Getoetst
    via de echte dispatch-actie, niet via de helper: de volgorde (eerst plaatsen, dan melden)
    is precies wat hier fout kan gaan."""
    dd, st, zender, doel = _dorp(tmp_path)
    kanaal = channels.circle_kanaal("mother_earth")
    _nxt, msg = cockpit2.dispatch(dd, "msg_post",
                                  {"kanaal": [kanaal], "tekst": [""]}, username="anna@nooch.earth")
    assert msg.startswith("✗")
    assert _dm_trail(cockpit2._Stores(dd), zender, doel) == []


def test_de_actie_meldt_hoeveel_er_zijn_aangesproken(tmp_path):
    dd, st, zender, doel = _dorp(tmp_path)
    kanaal = channels.circle_kanaal("mother_earth")
    _nxt, msg = cockpit2.dispatch(dd, "msg_post",
                                  {"kanaal": [kanaal], "tekst": ["hoi @Doel Dirk"]},
                                  username="anna@nooch.earth")
    assert "posted" in msg and "1 mentioned" in msg
    assert len(_dm_trail(cockpit2._Stores(dd), zender, doel)) == 1
