"""De goedkeuringsrij loopt door de inbox die een mens al gebruikt.

AANLEIDING, gemeten op 7 september 2026. Er waren twee inboxen en een mens kon er bij één:
`notifications.json` had 26 open items, `human_inbox.json` had er **78, zeventig dagen onaangeraakt**
(36 verband, 15 keyword, 15 means_gap, 8 activation, 3 suggestion, 1 kans). Die tweede had geen
pagina; de enige weg erheen was `python -m nooch_village.inbox` op de server, terwijl het cockpit er
wél naar verwees. Geen leesprobleem maar een vindprobleem.

Wat hieronder vastligt, in volgorde van belang:

1. **Nee en later mogen ALTIJD.** Op elk type, ook op een activatie. Een weigering schept niets.
   Zonder die regel bestaat er een type waarop je niet eens nee kunt zeggen, en dan groeit de rij
   weer dicht — precies wat er gebeurde.
2. **Ja mag per type, en de poort staat in CODE.** De view tekent geen ja-knop waar het niet mag,
   maar een view is een verzoek; een POST kan met de hand. `mag_ja` beslist en faalt closed.
3. **Er staat altijd een weg naar ja.** "Dit kan alleen op de commandoregel" zonder die regel erbij
   is een doodlopende weg, en dat was de fout die deze hele rij oplost.
4. **De ene inbox mag niet sneuvelen voor de andere.** Gaat de goedkeuringsrij stuk, dan blijft de
   spanningen-lade werken.
"""
from __future__ import annotations

import os

import pytest

from nooch_village import goedkeuring, inbox_actions
from nooch_village.human_inbox import HumanInbox


@pytest.fixture()
def inbox(tmp_path):
    return HumanInbox(str(tmp_path / "human_inbox.json"))


# ── 1. Nee en later mogen altijd ─────────────────────────────────────────────

@pytest.mark.parametrize("besluit", ["rejected", "deferred"])
def test_weigeren_en_uitstellen_mag_op_elk_type(inbox, besluit):
    """DE KERNTEST. Een weigering schept niets, dus er is geen grens die hij kan overschrijden. Ook
    een activatie — het duurste type dat er is — mag je vanuit het cockpit wegzetten."""
    iid = inbox.add_activation("een_slapende_rol", {"purpose": "p"})
    r = inbox_actions.weiger_of_stel_uit(inbox, iid, besluit, reason="niet meer nodig")
    assert r["ok"] is True
    assert inbox.get(iid)["status"] == besluit


def test_weigeren_kan_geen_goedkeuring_worden(inbox):
    """De veilige helft moet veilig BLIJVEN: deze functie kent 'approved' niet, wat er ook
    binnenkomt. Zou hij het doorlaten, dan is de hele grens één parameter verderop weg."""
    iid = inbox.add_activation("rol", {})
    r = inbox_actions.weiger_of_stel_uit(inbox, iid, "approved", reason="x")
    assert r["ok"] is False
    assert inbox.get(iid)["status"] == "pending"          # onaangeroerd


def test_een_al_gesloten_item_gaat_niet_twee_keer_dicht(inbox):
    iid = inbox.add_activation("rol", {})
    inbox_actions.weiger_of_stel_uit(inbox, iid, "rejected")
    r = inbox_actions.weiger_of_stel_uit(inbox, iid, "deferred")
    assert r["ok"] is False


# ── 2. Ja mag per type, en de poort faalt closed ─────────────────────────────





def test_een_type_zonder_ja_wijst_naar_een_werkende_route():
    """De tegenhanger: `ja: False` toont "yes runs on the command line" met de regel erbij. Die
    regel moet ergens landen, anders is het een tweede doodlopende weg. De CLI heeft een eerlijk
    vangnet (sluiten mét de melding dat er niets is uitgevoerd), dus dat klopt — maar de REDEN
    moet er staan, want zonder reden is het een muur."""
    for typ, spec in goedkeuring.TYPES.items():
        if spec.get("ja"):
            continue
        assert spec.get("waarom_niet"), f"{typ} heeft geen waarom_niet — dan staat er een muur"
        assert goedkeuring.waarom_niet(typ) != "this type has not been cleared for the cockpit"


def test_een_onbekend_type_krijgt_geen_ja():
    """FAIL-CLOSED. Een type dat niemand hier heeft afgewogen krijgt geen goedkeurknop; anders geeft
    het toevoegen van een nieuw item-type er stilzwijgend één cadeau."""
    assert goedkeuring.mag_ja("iets_nieuws_van_volgende_maand") is False
    assert goedkeuring.mag_ja({}) is False
    assert goedkeuring.mag_ja(None) is False


def test_de_poort_staat_in_code_en_niet_in_de_knop():
    """De view tekent geen ja-knop waar het niet mag, maar een view is een verzoek en geen garantie:
    een POST kan met de hand gestuurd worden. Daarom beslist `mag_ja` in de handler, en toetst deze
    test de handler-bron en niet het scherm."""
    import inspect
    from nooch_village import cockpit2
    src = inspect.getsource(cockpit2._act_goedkeur)
    assert "goedkeuring.mag_ja(item)" in src
    assert 'besluit == "approved"' in src


# ── 3. Er staat altijd een weg naar ja ───────────────────────────────────────

def test_wat_niet_mag_krijgt_de_commandoregel_erbij():
    """Zonder deze regel is 'dit kan alleen op de commandoregel' een doodlopende weg — en dat is
    letterlijk hoe die 78 items zeventig dagen bleven staan."""
    regel = goedkeuring.cli_regel({"id": "abc123"}, "approve")
    assert "nooch_village.inbox approve abc123" in regel
    assert regel.startswith("ssh ")


def test_elk_type_dat_geen_ja_mag_zegt_waarom_niet():
    for t, spec in goedkeuring.TYPES.items():
        if not spec.get("ja"):
            assert spec.get("waarom_niet"), f"{t} weigert zonder uitleg"


def test_elk_type_stelt_een_vraag():
    """Een item zonder vraag is een item dat niemand oppakt."""
    for t in goedkeuring.TYPES:
        assert goedkeuring.vraag_van({"type": t}).endswith("?"), t
    assert goedkeuring.vraag_van({"type": "onbekend"}).endswith("?")   # ook de terugval


# ── 4. De rij is leesbaar ────────────────────────────────────────────────────

def test_de_samenvatting_kijkt_onder_context(inbox):
    """DE TEKST ZIT ONDER `context`, NIET BOVENIN. Een meetscript dat bovenin keek drukte 78 lege
    regels af, en dat leest als 'deze items hebben geen inhoud' terwijl ze die wel hebben."""
    iid = inbox.add_keyword_escalation("barefoot", "te breed voor de missie", {"vol": 100})
    item = inbox.get(iid)
    assert goedkeuring.samenvatting(item) == "te breed voor de missie"




def test_open_items_staan_op_oudste_eerst(inbox):
    """Dat is de volgorde waarin ze pijn doen. Nieuwste-eerst duwt precies de items die al zeventig
    dagen wachten onderaan."""
    a = inbox.add_keyword_escalation("eerste", "r", {})
    b = inbox.add_keyword_escalation("tweede", "r", {})
    inbox._items[a]["created_at"] = 1000.0
    inbox._items[b]["created_at"] = 2000.0
    assert [i["id"] for i in goedkeuring.open_items(inbox)] == [a, b]


def test_alleen_openstaande_items(inbox):
    iid = inbox.add_keyword_escalation("weg", "r", {})
    inbox_actions.weiger_of_stel_uit(inbox, iid, "rejected")
    assert goedkeuring.open_items(inbox) == []




# ── 5. Een verband sluit ALTIJD, ook als de link niet lukt ───────────────────









# ── 6. De ene inbox sneuvelt niet voor de andere ─────────────────────────────

def test_een_stukke_goedkeuringsrij_laat_de_spanningen_met_rust():
    """DE TWEEDE KERNTEST. De spanningen-lade werkt en wordt dagelijks gebruikt; de goedkeuringsrij
    is de nieuwkomer. Een fout daar mag nooit de werkende inbox meenemen."""
    class _Stuk:
        def pending(self):
            raise RuntimeError("store kapot")

    assert goedkeuring.open_items(_Stuk()) == []
    assert goedkeuring.open_items(None) == []


def test_de_view_vangt_een_ontbrekende_store():
    """`_gk_items` leest een bestand dat er in een verse installatie nog niet is."""
    import inspect
    from nooch_village.views import inbox as V
    src = inspect.getsource(V._gk_items)
    assert "except Exception" in src and "return []" in src


# ── 7. Het scherm ────────────────────────────────────────────────────────────

def _st(tmp_path):
    from nooch_village import cockpit2
    return cockpit2._Stores(str(tmp_path))




def test_een_activatie_toont_geen_ja_maar_wel_de_regel(tmp_path):
    from nooch_village.views import inbox as V
    hi = HumanInbox(os.path.join(str(tmp_path), "human_inbox.json"))
    iid = hi.add_activation("slapende_rol", {"purpose": "p"})
    html = V._gk_row(_st(tmp_path), hi.get(iid))
    assert f"gkBeslis('{iid}','approved')" not in html     # geen ja-knop
    assert f"gkBeslis('{iid}','rejected')" in html         # nee en later wél
    assert f"gkBeslis('{iid}','deferred')" in html
    assert "nooch_village.inbox approve" in html           # en de weg ernaartoe




def test_zonder_goedkeuringen_verandert_er_niets_aan_de_lade(tmp_path):
    """Zonder de rij ziet de inbox eruit zoals hij eruitzag. Een lege sectie-kop toevoegen zou de
    lade drukker maken zonder iets te melden."""
    from nooch_village.views import inbox as V
    frag = V.render_inbox_frag(_st(tmp_path), [("role", "een_rol")])
    assert "Waiting for your approval" not in frag
    assert "data-count='0'" in frag
