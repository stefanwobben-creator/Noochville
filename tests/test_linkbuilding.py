"""/linkbuilding opnieuw gebouwd (28 september 2026).

HET OUDE SCHERM IS IN #516 VERWIJDERD, en de tool-kaart wees er daarna acht dagen naar — een kale
404 op de rol-tools van Marketing Lead. Dit is geen restore: het volgt het patroon dat sindsdien is
uitgewerkt voor `/site-audit` (#634), en dat is precies wat de oude versie miste.

DRIE DINGEN DIE HET OUDE SCHERM NIET HAD:

  1. DE ZOEKOPDRACHT DUURT. SerpAPI plus acht pagina's lezen is tientallen seconden; dat hoort in
     een achtergrondthread, niet in een POST-handler die een serverthread bezet houdt.
  2. EEN SLOT. Twee zoekopdrachten tegelijk schrijven door elkaar in dezelfde lijst. Het slot is
     gedeeld met de site-audit (`util.Werkslot`) — twee kopieën van dezelfde twintig regels is
     precies wat deze codebase elders al heeft opgeruimd.
  3. EEN SPOOR ALS HET MISGAAT. Een achtergrondthread heeft geen scherm om op te vallen; zonder
     dat spoor is "geen SerpAPI-sleutel" niet te onderscheiden van "nog niet geklikt".

EN HET BESLUIT BLIJFT VAN EEN MENS. De skill rangschikt (hoog/midden/laag/onbekend) — dat is een
meting op de tekst van de gids. Pitchen of negeren schrijft alleen een mens weg.
"""
from __future__ import annotations

import inspect
import time
import types

from nooch_village import cockpit2, linkbuilding as lb
from nooch_village.views.linkbuilding import MARKETING_LEAD, paneel, render_linkbuilding


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    for f in list(st.assign.fillers_of(MARKETING_LEAD, st.records.get(MARKETING_LEAD))):
        st.assign.unassign(MARKETING_LEAD, f.type, f.id)
    ik = st.people.add("Aap Een", "aap@test.nl")
    st.people.add("Beer Twee", "beer@test.nl")
    st.assign.assign(MARKETING_LEAD, "person", ik.id)
    return dd, cockpit2._Stores(dd)


def _ctx(sleutel="x", merken=("Veja",)):
    return types.SimpleNamespace(
        settings={"SERPAPI_API_KEY": sleutel} if sleutel else {},
        competitors=types.SimpleNamespace(confirmed=lambda: list(merken)))


def _target(link="https://gids.nl/a", **kw):
    basis = {"link": link, "title": "Beste barefoot merken", "source": "gids.nl",
             "priority": "hoog", "mentions": ["Veja"], "snippet": "Onze top 10"}
    basis.update(kw)
    return basis


def _doe(st, dd, actie, **velden):
    velden = {"csrf": "T", "next": "/linkbuilding", **velden}
    ctx = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/linkbuilding",
                        form=velden, username=velden.pop("_wie", "aap@test.nl"),
                        action=actie, data_dir=dd)
    return cockpit2.ACTIONS[actie](ctx)


# ══ 1. De store ══════════════════════════════════════════════════════════════
def test_een_vondst_landt_in_de_store(tmp_path):
    dd, st = _dorp(tmp_path)
    assert st.linktargets.zet_vondsten([_target()], "barefoot") == (1, 0)
    rij = cockpit2._Stores(dd).linktargets.alle()[0]
    assert rij["priority"] == "hoog" and rij["status"] == "open" and rij["query"] == "barefoot"


def test_een_tweede_zoekopdracht_overschrijft_geen_besluit(tmp_path):
    """DE REDEN DAT DIT EEN STORE IS. Je zoekt vaker dan je beslist; een gids die je vorige week
    genegeerd hebt hoort niet elke ronde opnieuw bovenaan te staan. De MEETWAARDEN worden wél
    bijgewerkt — die zijn een waarneming."""
    dd, st = _dorp(tmp_path)
    st.linktargets.zet_vondsten([_target()], "barefoot")
    st.linktargets.beslis("https://gids.nl/a", "ignore", "Aap")
    st = cockpit2._Stores(dd)
    assert st.linktargets.zet_vondsten([_target(priority="midden", title="Nieuwe titel")], "q2") == (0, 1)
    rij = cockpit2._Stores(dd).linktargets.alle()[0]
    assert rij["status"] == "ignore" and rij["door"] == "Aap"
    assert rij["priority"] == "midden" and rij["title"] == "Nieuwe titel"


def test_open_staat_boven_en_hoog_boven_laag(tmp_path):
    """Dit scherm is een werklijst, geen archief."""
    dd, st = _dorp(tmp_path)
    st.linktargets.zet_vondsten([_target("https://a.nl", priority="laag"),
                                 _target("https://b.nl", priority="hoog"),
                                 _target("https://c.nl", priority="midden")], "q")
    st.linktargets.beslis("https://b.nl", "pursue", "Aap")
    rijen = cockpit2._Stores(dd).linktargets.alle()
    assert [r["link"] for r in rijen] == ["https://c.nl", "https://a.nl", "https://b.nl"]


def test_een_onbekend_besluit_wordt_geweigerd(tmp_path):
    """Fail-closed: alleen pitchen of negeren, en alleen op een doelwit dat bestaat."""
    dd, st = _dorp(tmp_path)
    st.linktargets.zet_vondsten([_target()], "q")
    assert st.linktargets.beslis("https://gids.nl/a", "misschien", "Aap") is False
    assert st.linktargets.beslis("https://bestaat.niet", "pursue", "Aap") is False


def test_hij_heet_niet_zoals_de_verwijderde_store():
    """"niet de oude LinkTargets terughalen". Een gelijke naam zou lezen als een restore, en de
    vorm is ook anders: JsonStore, één bestand, besluit per rij in plaats van drie lijsten."""
    assert not hasattr(lb, "LinkTargets")
    assert issubclass(lb.LinkTargetQueue, __import__("nooch_village.util", fromlist=["x"]).JsonStore)


# ══ 2. De zoekopdracht ═══════════════════════════════════════════════════════
class _NepSkill:
    naam = "linkbuilding_targets"

    def __init__(self, uit):
        self.uit, self.gezien = uit, []

    def run(self, payload, context=None):
        self.gezien.append(payload)
        return self.uit


class _NepRegistry:
    def __init__(self, skill):
        self.skill = skill

    def get(self, naam):
        return self.skill if naam == "linkbuilding_targets" else None


def test_de_merken_komen_uit_de_bevestigde_concurrenten(tmp_path):
    """KANDIDATEN TELLEN NIET MEE. Bevestigen is een besluit; ze meesturen zou dat besluit
    stilzwijgend nemen, en juist de prioriteit "hoog" leunt erop."""
    dd, st = _dorp(tmp_path)
    skill = _NepSkill({"ok": True, "targets": [_target()], "query": "barefoot"})
    lb.zoek_en_bewaar(st.linktargets, _ctx(merken=("Veja", "Allbirds")), _NepRegistry(skill),
                      topic="barefoot")
    assert skill.gezien[0]["brands"] == ["Veja", "Allbirds"]
    assert skill.gezien[0]["topic"] == "barefoot"
    assert cockpit2._Stores(dd).linktargets.telling()["open"] == 1


def test_zonder_onderwerp_stuurt_hij_er_geen_mee(tmp_path):
    """Leeg laten betekent "gebruik de staande `linkbuilding_query`" — dat is het contract van de
    skill zelf (payload > config > zichtbaar weigeren). Een lege string meesturen zou dat contract
    doorbreken."""
    dd, st = _dorp(tmp_path)
    skill = _NepSkill({"ok": True, "targets": []})
    lb.zoek_en_bewaar(st.linktargets, _ctx(), _NepRegistry(skill), topic="  ")
    assert "topic" not in skill.gezien[0]


def test_een_mislukte_zoekopdracht_schrijft_niets_weg(tmp_path):
    dd, st = _dorp(tmp_path)
    skill = _NepSkill({"ok": False, "error": "SERPAPI_API_KEY ontbreekt"})
    uit = lb.zoek_en_bewaar(st.linktargets, _ctx(), _NepRegistry(skill))
    assert uit["ok"] is False
    assert cockpit2._Stores(dd).linktargets.alle() == []


# ══ 3. Het slot en de achtergrondthread ══════════════════════════════════════
def test_de_knop_wacht_niet_op_de_zoekopdracht(tmp_path, monkeypatch):
    """Gemeten met een trage nep-zoektocht, niet beweerd — en met een nep, want de echte gaat het
    internet op en dan meet een toets de dag en niet de code."""
    dd, st = _dorp(tmp_path)
    bezig = []

    def _traag(*a, **kw):
        bezig.append(time.time())
        time.sleep(1.5)
        return {"ok": True, "targets": []}

    monkeypatch.setattr(lb, "zoek_en_bewaar", _traag)
    monkeypatch.setattr(cockpit2, "_context_of", lambda _dd: _ctx())
    start = time.time()
    _pad, melding = _doe(st, dd, "linkbuilding_zoek", topic="barefoot")
    assert time.time() - start < 0.5, "de POST bleef hangen"
    assert melding.startswith("🔎")
    time.sleep(.3)
    assert bezig, "de zoekopdracht is niet gestart"
    assert lb.slot(dd).staat() is not None, "het slot staat niet aan tijdens de run"
    time.sleep(1.6)
    assert lb.slot(dd).staat() is None, "het slot is niet teruggegeven"


def test_een_tweede_klik_start_geen_tweede_zoekopdracht(tmp_path, monkeypatch):
    dd, st = _dorp(tmp_path)
    monkeypatch.setattr(cockpit2, "_context_of", lambda _dd: _ctx())
    lb.slot(dd).pak("iemand anders")
    _pad, melding = _doe(st, dd, "linkbuilding_zoek")
    assert melding.startswith("⏳") and "iemand anders" in melding


def test_het_slot_is_hetzelfde_als_dat_van_de_site_audit():
    """Twee kopieën van dezelfde twintig regels lopen na één wijziging uiteen."""
    from nooch_village import site_audit
    from nooch_village.util import Werkslot
    assert "Werkslot" in inspect.getsource(lb.slot)
    assert "Werkslot" in inspect.getsource(site_audit._slot)
    assert Werkslot.VERVALT_S == site_audit.SLOT_VERVALT_S


def test_een_fout_in_de_achtergrond_laat_een_spoor(tmp_path, monkeypatch):
    """Zonder dit is "geen sleutel" niet te onderscheiden van "nog niet geklikt"."""
    dd, st = _dorp(tmp_path)
    monkeypatch.setattr(lb, "zoek_en_bewaar",
                        lambda *a, **kw: {"ok": False, "error": "SerpAPI weigerde"})
    lb.start_achtergrond(dd, _ctx(), None, door="Aap")
    time.sleep(.4)
    fout = lb.laatste_fout(dd)
    assert fout and "SerpAPI weigerde" in fout["fout"]
    assert "the last search failed" in paneel(st, _ctx(), dd, "T", mag=True)


def test_een_geslaagde_zoekopdracht_wist_het_spoor(tmp_path, monkeypatch):
    dd, st = _dorp(tmp_path)
    lb._noteer_fout(dd, "oud")
    monkeypatch.setattr(lb, "zoek_en_bewaar", lambda *a, **kw: {"ok": True, "targets": []})
    lb.start_achtergrond(dd, _ctx(), None, door="Aap")
    time.sleep(.4)
    assert lb.laatste_fout(dd) is None


# ══ 4. De ontbrekende sleutel ════════════════════════════════════════════════
def test_zonder_sleutel_geen_knop_maar_een_zin(tmp_path, monkeypatch):
    """Een knop die altijd faalt is erger dan geen knop. De skill weigert zelf ook
    (`required_env`), maar dan als achtergrondfout die niemand ziet staan.

    DE OMGEVING WORDT LEEGGEMAAKT, en niet omdat het mooier staat: `sleutel_aanwezig` leest naast
    de settings ook `os.environ`, en een eerdere test in de volle suite roept `load_context` aan —
    die laadt `.env` procesbreed. Zonder deze regel slaagt deze toets alleen op een machine zonder
    sleutel, en dat meet de machine in plaats van de code."""
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    dd, st = _dorp(tmp_path)
    h = render_linkbuilding(st, _ctx(sleutel=""), dd, csrf_token="TOK", username="aap@test.nl")
    assert "no SerpAPI key configured" in h and "SERPAPI_API_KEY" in h
    assert "linkbuilding_zoek" not in h


def test_de_actie_weigert_hem_ook(tmp_path, monkeypatch):
    """DE KETEN TOT HET EIND: het scherm laat de knop weg, en wie hem tóch post krijgt een nette
    melding in plaats van een achtergrondthread die stil sneuvelt."""
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)   # zie de toets hierboven: .env lekt
    dd, st = _dorp(tmp_path)
    monkeypatch.setattr(cockpit2, "_context_of", lambda _dd: _ctx(sleutel=""))
    _pad, melding = _doe(st, dd, "linkbuilding_zoek")
    assert melding.startswith("⛔") and "SERPAPI_API_KEY" in melding
    assert lb.slot(dd).staat() is None, "er is toch een zoekopdracht gestart"


def test_zonder_bevestigde_merken_draait_hij_wel_maar_zegt_wat_dat_kost(tmp_path):
    """De zoektocht werkt zonder merken — je vindt gidsen — maar "hoog" kan dan niet ontstaan, en
    dat is juist het signaal waar je op pitcht. Dat hoort op het scherm, niet in een handleiding."""
    dd, st = _dorp(tmp_path)
    h = render_linkbuilding(st, _ctx(merken=()), dd, csrf_token="TOK", username="aap@test.nl")
    assert "no confirmed competitor brands" in h
    assert "linkbuilding_zoek" in h, "de knop hoort te blijven"


# ══ 5. De poort ══════════════════════════════════════════════════════════════
def test_alleen_de_marketing_lead_zoekt_en_beslist(tmp_path):
    dd, st = _dorp(tmp_path)
    st.linktargets.zet_vondsten([_target()], "q")
    st = cockpit2._Stores(dd)
    for actie, extra in (("linkbuilding_zoek", {}),
                         ("linkbuilding_besluit", {"link": "https://gids.nl/a", "besluit": "pursue"})):
        try:
            _doe(st, dd, actie, _wie="beer@test.nl", **extra)
        except cockpit2.Forbidden:
            pass
        else:                                            # pragma: no cover
            raise AssertionError(f"{actie} stond open voor een buitenstaander")
    assert cockpit2._Stores(dd).linktargets.telling()["pursue"] == 0


def test_wie_niet_mag_ziet_de_lijst_wel_maar_geen_knoppen(tmp_path):
    """Lezen is vrij; beslissen niet."""
    dd, st = _dorp(tmp_path)
    st.linktargets.zet_vondsten([_target()], "q")
    st = cockpit2._Stores(dd)
    h = render_linkbuilding(st, _ctx(), dd, csrf_token="TOK", username="beer@test.nl")
    assert "Beste barefoot merken" in h
    assert "linkbuilding_besluit" not in h and "linkbuilding_zoek" not in h


def test_de_poort_is_dezelfde_vraag_als_de_server_stelt():
    from nooch_village.views import linkbuilding as view
    assert "_role_gate(MARKETING_LEAD" in inspect.getsource(view.render_linkbuilding)
    for tak in (cockpit2._act_linkbuilding_zoek, cockpit2._act_linkbuilding_besluit):
        assert "_role_gate(MARKETING_LEAD" in inspect.getsource(tak)


# ══ 6. Het scherm ════════════════════════════════════════════════════════════
def test_elke_rij_toont_zijn_prioriteit_met_een_woord(tmp_path):
    """Kleur is nooit de enige drager — dezelfde regel als bij de statusvormen."""
    dd, st = _dorp(tmp_path)
    st.linktargets.zet_vondsten([_target("https://a.nl", priority="hoog"),
                                 _target("https://b.nl", priority="laag")], "q")
    h = render_linkbuilding(cockpit2._Stores(dd), _ctx(), dd, csrf_token="TOK",
                            username="aap@test.nl")
    assert ">hoog<" in h and ">laag<" in h
    assert h.count(">Pitch<") == 2 and h.count(">Ignore<") == 2


def test_een_beslist_doelwit_toont_wie_en_geen_knoppen_meer(tmp_path):
    dd, st = _dorp(tmp_path)
    st.linktargets.zet_vondsten([_target()], "q")
    st.linktargets.beslis("https://gids.nl/a", "pursue", "Aap Een")
    h = render_linkbuilding(cockpit2._Stores(dd), _ctx(), dd, csrf_token="TOK",
                            username="aap@test.nl")
    assert "to pitch" in h and "Aap Een" in h
    assert ">Pitch<" not in h


def test_het_paneel_ververst_zichzelf(tmp_path):
    """Zonder poller blijft "searching…" staan tot de lezer zelf ververst."""
    dd, st = _dorp(tmp_path)
    h = render_linkbuilding(st, _ctx(), dd, csrf_token="TOK", username="aap@test.nl")
    assert "data-poll='/linkbuilding-status'" in h and "id='lb-paneel'" in h


def test_de_kaart_wijst_er_weer_heen():
    """De ratchet uit `test_nav_ia_fase2` eist dat elke tool-href een bestaande route is; deze
    toets legt de andere kant vast — dat de kaart ook echt naar dit scherm wijst."""
    from nooch_village.views.overview import _ROLE_TOOLS
    hrefs = {href for _l, _d, href in _ROLE_TOOLS[MARKETING_LEAD]}
    assert "/linkbuilding" in hrefs


def test_het_is_geen_restore_van_het_oude_scherm():
    """"geen 1-op-1 restore" — het oude scherm draaide synchroon en had geen opslag voor
    beslissingen. Wat dit scherm daaraan toevoegt, staat hier als eis."""
    from nooch_village.views import linkbuilding as view
    bron = inspect.getsource(view) + inspect.getsource(lb)
    assert "start_achtergrond" in bron and "Werkslot" in bron
    assert "data-poll" in bron
