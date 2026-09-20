"""Stap 1 van de inbox-migratie: de rol-notificaties als bericht in het kanaal van hun ROL.

Wat hier bewaakt wordt is niet dat er berichten verschijnen — dat is het makkelijke deel. Het is
de **harde eis**: de verwerkingsstate moet letterlijk meekomen. 185 vastgelegde uitkomsten en 54
poort-oordelen op productie zijn oordelen van een mens; een migratie die daar een afgeleid
statusveld van maakt, gooit ze weg zonder dat iemand het ziet.

En één eigenschap die de hele vormkeuze draagt: er wordt **niets naar een mens vertaald**. Een
gearchiveerde rol houdt gewoon zijn kanaal, dus voor de negentien open items op opgeheven rollen
hoeft niemand aangewezen te worden.
"""
from __future__ import annotations

import tempfile

import pytest

from nooch_village import channels, cockpit2, notif_migratie

LEVEND = "mother_earth__nooch__compliance"
OPGEHEVEN = "librarian"          # bestaat op prod alleen nog als gearchiveerd record


@pytest.fixture()
def dorp():
    dd = tempfile.mkdtemp()
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)

    rijk = st.notif.add("role", LEVEND, "p1", snippet="claim 'natural' toetsen", by="claims-checker")
    st.notif.add_outcome(rijk["id"], intent="opgelost", label="herformuleerd")
    st.notif.mark_item_processed(rijk["id"], outcome="herformuleerd naar 'plantaardig'")
    st.notif.set_poort(rijk["id"], {"oordeel": "G2", "reden": "accountability-duplicaat"})

    st.notif.add("role", OPGEHEVEN, "p2", snippet="oud werk zonder eigenaar", by="harry_hemp")
    st.notif.add("person", "iemand", "p3", snippet="voor een mens", by="dialoog")
    return st


def _entries(st, rol):
    return st.channels.trail(channels.role_kanaal(rol), limit=1000)


# ── de harde eis ─────────────────────────────────────────────────────────────

def test_de_verwerkingsstate_komt_letterlijk_mee(dorp):
    st = dorp
    bron = next(n for n in st.notif.all() if n.get("target_id") == LEVEND)
    notif_migratie.migreer(st.notif, st.channels, apply=True)
    e = next(x for x in _entries(st, LEVEND) if x["id"] == bron["id"])
    for veld in channels.VERWERKING_VELDEN:
        if veld in bron:
            assert e["verwerking"][veld] == bron[veld], veld
    assert e["verwerking"]["outcome"] and e["verwerking"]["poort"]
    assert e["verwerking"]["verwerkingen"]        # de gestapelde uitkomsten, niet platgeslagen


def test_de_telling_voor_en_na_is_de_guard(dorp):
    """De migratie levert zijn eigen bewijs mee. Een migratie die dat niet doet, is een bewering."""
    st = dorp
    r = notif_migratie.migreer(st.notif, st.channels, apply=True)
    assert r["klopt"] is True
    assert r["voor"] == r["na"]
    assert r["na_berichten"] == r["rol_rijen"]


def test_een_wegvallend_oordeel_laat_de_guard_omvallen(dorp):
    """Zou de guard altijd True zeggen, dan bewaakt hij niets. Hier wordt hij bewust gebroken."""
    st = dorp
    notif_migratie.migreer(st.notif, st.channels, apply=True)
    kanaal = channels.role_kanaal(LEVEND)
    for e in st.channels._data["kanalen"][kanaal]:
        e.get("verwerking", {}).pop("poort", None)
    # WEGSCHRIJVEN is hier nodig, en dat is zelf een bevinding: elke schrijfmethode van
    # `ChannelStore` herlaadt onder het slot (`JsonStore._WRITE_METHODS`), dus een mutatie die
    # alleen in het geheugen staat wordt bij de volgende schrijfactie gewoon weggegooid. Prettige
    # eigenschap — maar een test die dat niet weet, toetst niets.
    st.channels._save()
    r = notif_migratie.migreer(st.notif, st.channels, apply=True)
    assert r["klopt"] is False and r["na"]["poort"] < r["voor"]["poort"]


# ── de vormkeuze ─────────────────────────────────────────────────────────────

def test_er_wordt_niets_naar_een_mens_vertaald(dorp):
    """Het kanaal is dat van de ROL. Een opgeheven rol zonder mens-vervuller migreert gewoon mee."""
    st = dorp
    notif_migratie.migreer(st.notif, st.channels, apply=True)
    e = _entries(st, OPGEHEVEN)
    assert len(e) == 1
    assert channels.soort_van(channels.role_kanaal(OPGEHEVEN)) == channels.ROLE
    # open blijft open: niemand heeft het gesloten en niemand kan dat namens de rol doen
    assert not e[0]["verwerking"].get("done") and not e[0]["verwerking"].get("archived")


def test_persoon_gerichte_items_blijven_liggen(dorp):
    """Stefans besluit gaat over rollen. Een `person:`-kanaalsoort erbij verzinnen zou een tweede
    datamodel-begrip zijn dat niemand heeft gevraagd — ze worden geteld, niet aangeraakt."""
    st = dorp
    r = notif_migratie.migreer(st.notif, st.channels, apply=True)
    assert r["persoon_rijen"] == 1
    assert not [k for k in st.channels.bestaande() if channels.soort_van(k) == channels.ROLE
                and channels.doel_van(k) == "iemand"]


def test_de_volgorde_en_het_tijdstip_blijven_van_de_notificatie(dorp):
    """`at` van de klok nemen zet drie maanden gesprek op de dag van de migratie."""
    st = dorp
    bron = {n["id"]: n["at"] for n in st.notif.all() if n.get("target_type") == "role"}
    notif_migratie.migreer(st.notif, st.channels, apply=True)
    for rol in (LEVEND, OPGEHEVEN):
        for e in _entries(st, rol):
            assert e["at"] == bron[e["id"]]


# ── stap 1 verwijdert niets ──────────────────────────────────────────────────

def test_notifstore_blijft_volledig_intact(dorp):
    """Stap 1 van drie: schrijven naast NotifStore. Verwijderen is stap 3."""
    st = dorp
    voor = len(st.notif.all())
    notif_migratie.migreer(st.notif, st.channels, apply=True)
    assert len(st.notif.all()) == voor


def test_de_migratie_is_idempotent(dorp):
    st = dorp
    eerste = notif_migratie.migreer(st.notif, st.channels, apply=True)
    tweede = notif_migratie.migreer(st.notif, st.channels, apply=True)
    assert eerste["geschreven"] == 2 and tweede["geschreven"] == 0
    assert tweede["bestond_al"] == 2 and tweede["klopt"] is True


def test_droogloop_schrijft_niets(dorp):
    st = dorp
    r = notif_migratie.migreer(st.notif, st.channels, apply=False)
    assert r["geschreven"] == 2
    assert _entries(st, LEVEND) == []


def test_een_droogloop_rapporteert_geen_vergelijking(dorp):
    """De eerste versie printte bij een droogloop ook de ná-kolom, en die stond op nul: acht regels
    "← WIJKT AF" met eronder "✓ tellingen kloppen". Dat leest als van alles behalve als "er is nog
    niets gebeurd" — dezelfde fout als een neutrale regel bij een no-op deploy."""
    st = dorp
    droog = notif_migratie.rapport_tekst(notif_migratie.migreer(st.notif, st.channels, apply=False))
    assert "WIJKT AF" not in droog and "tellingen kloppen" not in droog
    assert "droogloop" in droog
    echt = notif_migratie.rapport_tekst(notif_migratie.migreer(st.notif, st.channels, apply=True))
    assert "vóór" in echt and "✓ tellingen kloppen" in echt


# ── stap 2: /inbox leest uit de kanalen ──────────────────────────────────────

def _targets(st, rollen):
    return [("role", r) for r in rollen]


def test_de_kanaal_wachtrij_is_dezelfde_als_de_notifstore_wachtrij(dorp):
    """De kern van stap 2. Zou dit uiteenlopen, dan mist iemand werk zonder dat iets het zegt."""
    st = dorp
    from nooch_village import notif_migratie as nm
    t = _targets(st, [LEVEND, OPGEHEVEN])
    nm.hersync(st.notif, st.channels)
    uit_kanaal = {n["id"] for n in nm.open_uit_kanalen(st.channels, t)}
    uit_store = {n["id"] for n in st.notif.open_for_targets(t)}
    assert uit_kanaal == uit_store and uit_kanaal


def test_een_inbox_actie_landt_in_het_kanaal_zonder_sync_aanroep(dorp):
    """`NotifStore` blijft tot stap 3 de schrijver. `hersync` draait vlak vóór het lezen, dus een
    actie hoeft zichzelf niet te spiegelen — en kan dus ook niet vergeten dat te doen."""
    st = dorp
    from nooch_village import notif_migratie as nm
    t = _targets(st, [LEVEND, OPGEHEVEN])
    nm.hersync(st.notif, st.channels)
    open_voor = len(nm.open_uit_kanalen(st.channels, t))
    doel = st.notif.open_for_targets(t)[0]
    # `archive_item` weigert wat nog niet verwerkt is ("alleen wat verwerkt is mag weg"), dus eerst
    # verwerken. Dat is geen omweg in de test maar de echte volgorde op het scherm.
    st.notif.mark_item_processed(doel["id"], outcome="afgehandeld")
    assert st.notif.archive_item(doel["id"]) is True        # alleen NotifStore aangeraakt
    nm.hersync(st.notif, st.channels)
    assert len(nm.open_uit_kanalen(st.channels, t)) == open_voor - 1


def test_alle_velden_die_het_scherm_leest_komen_mee(dorp):
    """De eerste versie kopieerde twaalf handgekozen velden; de view gebruikt er zeventien. Een
    handgekozen lijst is een tweede plek waar een veld vergeten kan worden."""
    st = dorp
    from nooch_village import notif_migratie as nm
    nodig = ("bevinding", "by", "entry_id", "herkomst", "id", "ok", "pagina", "poort",
             "project_id", "snippet", "target_id", "target_type", "triage_grond", "triage_rol",
             "triage_vorm", "type", "voorstel")
    bron = next(n for n in st.notif.all() if n.get("target_id") == LEVEND)
    bron.update({k: f"waarde-{k}" for k in nodig if k not in bron})
    st.notif._save()
    nm.hersync(st.notif, st.channels)
    uit = next(n for n in nm.open_uit_kanalen(st.channels, _targets(st, [LEVEND]))
               if n["id"] == bron["id"])
    for k in nodig:
        assert k in uit, k


def test_de_route_valt_terug_op_notifstore_als_de_kanalen_falen(dorp, monkeypatch):
    """Fail-OPEN, en dat is hier de juiste kant. Een lege inbox laat iemand denken dat er geen werk
    ligt; dat is erger dan een scherm op de oude bron."""
    st = dorp
    from nooch_village import notif_migratie as nm
    monkeypatch.setattr(nm, "hersync", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stuk")))
    t = _targets(st, [LEVEND, OPGEHEVEN])
    assert {n["id"] for n in cockpit2._inbox_items(st, t)} == \
           {n["id"] for n in st.notif.open_for_targets(t)}
