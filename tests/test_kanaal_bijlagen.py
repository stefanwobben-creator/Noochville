"""Een bestand in een chatbericht (22 september 2026), en de poort die er niet was.

WAT ER NIET BESTOND. `attach_add` op een project is link+titel; het PDF-naar-kennisbank-pad crasht
(`kb_intake` en `atomiseer` worden aangeroepen maar nergens geïmporteerd). Wat er WEL was en werkt
is `attach_file` — projectbijlagen, 48 bestanden en 83 MB op productie. Dat is het patroon dat
hier is hergebruikt: dezelfde multipart-tak, dezelfde groottegrens, dezelfde pad-ontsmetting.

DRIE DINGEN MOETEN HARD ZIJN:

  1. de bijlage hangt aan het BERICHT, zodat één mechanisme op allebei de achterkanten werkt
     (een projectkanaal is `project["log"]`, de rest staat in `channels.json`);
  2. wie een bestand mag zien is precies wie het kanaal mag lezen — server-side, per verzoek,
     en de URL is geen sleutel;
  3. alleen wat op de allowlist staat komt binnen, en alleen afbeelding en pdf komen inline naar
     buiten. Ons eigen domein draagt de sessie: een inline geserveerde SVG is script.

EN ÉÉN DING DAT ER AL WAS EN STUK WAS: `GET /file?pid=&aid=` deed geen enkele leescheck. Elke
ingelogde gebruiker kon elk projectbestand ophalen, ook van een `private`-project. Zie de laatste
sectie — die toetst dat gat, niet alleen de nieuwe route.
"""
from __future__ import annotations

import os

import pytest

from nooch_village import channels, cockpit2
from nooch_village.views.messages import (mag_kanaal_lezen, mag_project_lezen, render_messages,
                                          _bijlagen_html)

OWNER = "mother_earth__nooch__creator_of_shoes"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Bijlage Tester", "bijlage@test.nl")
    ander = st.people.add("Andere Mens", "ander@test.nl")
    st.assign.assign(OWNER, "person", ik.id)
    return dd, cockpit2._Stores(dd), ik, ander


def _meta(bid="b1", naam="rapport.pdf", mime="application/pdf"):
    return {"id": bid, "name": naam, "stored": f"kanaalbijlagen/x/{bid}_{naam}",
            "size": 2048, "mime": mime, "at": 0}


# ── 1. De bijlage hangt aan het bericht ─────────────────────────────────────
def test_een_bijlage_hangt_aan_het_bericht_en_niet_aan_het_kanaal(tmp_path):
    dd, st, ik, _ = _dorp(tmp_path)
    k = channels.circle_kanaal("mother_earth")
    e = st.channels.post(k, "hier is het rapport", author_id=ik.id)
    assert st.channels.add_bijlage(k, e["id"], _meta()) is True
    st2 = cockpit2._Stores(dd)
    assert st2.channels.trail(k)[0]["bijlagen"][0]["name"] == "rapport.pdf"


def test_op_een_projectkanaal_landt_hij_op_het_project(tmp_path):
    """REFERENCE, DON'T COPY — dezelfde regel als bij de reacties. Een projectkanaal ÍS
    `project["log"]`; zou de bijlage ergens anders landen, dan zie je hem in Messages wel en op de
    projectpagina niet."""
    dd, st, ik, _ = _dorp(tmp_path)
    pid = st.projects.create(OWNER, "Met een bestand", "human", status="running")
    e = st.projects.add_feed_entry(pid, "kijk hier", kind="comment",
                                   author_type="human", author_id=ik.id)
    k = channels.project_kanaal(pid)
    assert st.channels.add_bijlage(k, e["id"], _meta()) is True
    st2 = cockpit2._Stores(dd)
    assert st2.projects.get(pid)["log"][0]["bijlagen"][0]["name"] == "rapport.pdf"
    import json
    pad = f"{dd}/channels.json"
    ruw = json.load(open(pad)) if os.path.exists(pad) else {}
    assert k not in (ruw.get("kanalen") or {}), "de bijlage is óók in channels.json beland"


def test_een_bijlage_zoeken_kan_alleen_binnen_zijn_eigen_kanaal(tmp_path):
    """Op kanaal ÉN id. Zou je op id alleen kunnen zoeken, dan is het id de sleutel en is de
    leescheck te omzeilen door de juiste string te raden."""
    dd, st, ik, _ = _dorp(tmp_path)
    k1, k2 = channels.circle_kanaal("mother_earth"), channels.circle_kanaal("mother_earth__nooch")
    e = st.channels.post(k1, "iets", author_id=ik.id)
    st.channels.add_bijlage(k1, e["id"], _meta())
    st2 = cockpit2._Stores(dd)
    assert (st2.channels.bijlage(k1, "b1") or {}).get("name") == "rapport.pdf"
    assert st2.channels.bijlage(k2, "b1") is None


# ── 2. De allowlist ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("naam,verwacht_inline", [
    ("foto.png", True), ("foto.JPG", True), ("rapport.pdf", True),
    ("notities.txt", False), ("lijst.csv", False),
    ("brief.docx", False), ("cijfers.xlsx", False), ("deck.pptx", False),
])
def test_wat_erop_staat_en_hoe_het_naar_buiten_komt(naam, verwacht_inline):
    soort = channels.bijlage_type(naam)
    assert soort is not None, naam
    assert soort[1] is verwacht_inline


@pytest.mark.parametrize("naam", ["kwaad.svg", "pagina.html", "script.js", "app.exe", "geen"])
def test_wat_er_niet_op_staat_komt_er_niet_in(naam):
    """EEN ALLOWLIST EN GEEN BLOKLIJST, want ons eigen domein draagt de sessie. Een inline
    geserveerde SVG of HTML is script met toegang tot de ingelogde sessie. Een bloklijst vergeet
    altijd iets; een allowlist vergeet hooguit een nuttig type, en dat merk je meteen."""
    assert channels.bijlage_type(naam) is None


def test_alleen_afbeelding_en_pdf_mogen_inline():
    """De harde helft van dezelfde regel: wat niet inline mag, gaat als download naar buiten."""
    for ext, (mime, inline) in channels.BIJLAGE_TYPES.items():
        if inline:
            assert mime.startswith("image/") or mime == "application/pdf", ext


def test_de_serveer_helper_zet_nosniff_en_disposition():
    """`nosniff` op ALLES, ook op een plaatje: zonder die header mag de browser alsnog zelf iets
    anders van de bytes maken dan wat wij zeggen."""
    import inspect
    bron = inspect.getsource(cockpit2.make_handler)
    blok = bron.split("def _send_bijlage")[1].split("def ")[0]
    assert '"X-Content-Type-Options", "nosniff"' in blok
    assert '"inline" if inline else "attachment"' in blok


# ── 3. De poort ─────────────────────────────────────────────────────────────
def test_een_dm_van_anderen_is_niet_te_lezen(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    derde = st.people.add("Derde Mens", "derde@test.nl")
    st2 = cockpit2._Stores(dd)
    assert mag_kanaal_lezen(st2, channels.dm_kanaal(ander.id, derde.id), ik.id) is False
    assert mag_kanaal_lezen(st2, channels.dm_kanaal(ik.id, ander.id), ik.id) is True


def test_een_prive_project_blijft_binnen_zijn_cirkel(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    pid = st.projects.create(OWNER, "Geheim", "human", status="running")
    st.projects.edit(pid, private=True, allow_done=True)
    st2 = cockpit2._Stores(dd)
    assert mag_project_lezen(st2, pid, ik.id) is True          # vervult een rol in die cirkel
    assert mag_project_lezen(st2, pid, ander.id) is False      # geen rol, geen toegang
    assert mag_kanaal_lezen(st2, channels.project_kanaal(pid), ander.id) is False


def test_de_poort_is_fail_closed(tmp_path):
    dd, st, ik, _ = _dorp(tmp_path)
    for kanaal in ("", "raar:1", "onbekend"):
        assert mag_kanaal_lezen(st, kanaal, ik.id) is False
    assert mag_kanaal_lezen(st, channels.circle_kanaal("mother_earth"), "") is False
    assert mag_project_lezen(st, "bestaat-niet", ik.id) is False


def test_de_link_wijst_naar_de_poort_en_niet_naar_de_schijf(tmp_path):
    """Een statisch pad zou de URL tot sleutel maken, en dan geeft doorsturen toegang weg."""
    k = channels.circle_kanaal("mother_earth")
    h = _bijlagen_html({"bijlagen": [_meta()]}, k)
    assert "/bijlage?kanaal=" in h and "id=b1" in h
    assert "kanaalbijlagen/" not in h, "het pad op schijf staat in de HTML"


# ── 4. De paperclip volgt het antwoordveld ──────────────────────────────────
def test_geen_antwoordveld_dan_ook_geen_paperclip(tmp_path):
    """Uploaden naar een kanaal dat niemand leest is hetzelfde dead letter als een bericht, maar
    dan eentje die 20 MB schijf kost. Eén voorwaarde, `kan_antwoorden()` — geen tweede regel."""
    dd, st, ik, _ = _dorp(tmp_path)
    rol_kanaal = channels.dm_kanaal(ik.id, "compliance")       # tegenpartij is geen mens
    st.channels.post(rol_kanaal, "scan af", author_id="compliance")
    st2 = cockpit2._Stores(dd)
    h = render_messages(st2, ik=ik.id, kanaal=rol_kanaal, csrf_token="t")
    assert "kanaal_bijlage" not in h and "No reply box" in h

    gewoon = channels.circle_kanaal("mother_earth")
    h2 = render_messages(st2, ik=ik.id, kanaal=gewoon, csrf_token="t")
    assert "kanaal_bijlage" in h2 and "enctype='multipart/form-data'" in h2


def test_de_upload_tak_controleert_dezelfde_twee_dingen():
    """De server vertrouwt het formulier niet: hij vraagt zelf of je dit kanaal mag lezen én erin
    mag schrijven. Zonder die check is een verborgen veld genoeg om in andermans DM te uploaden."""
    import inspect
    bron = inspect.getsource(cockpit2.make_handler)
    blok = bron.split('"kanaal_bijlage"')[1].split("kb_atoom_ref_pdf")[0]
    assert "mag_kanaal_lezen" in blok and "kan_antwoorden" in blok
    assert "_upload_error" in blok and "_upload_max_bytes" in blok      # 20 MB, de bestaande grens
    assert "bijlage_type" in blok                                       # de allowlist
    assert "os.path.basename" in blok                                   # pad-ontsmetting


# ── 5. HET GAT DAT ER AL WAS: /file zonder leescheck ────────────────────────
#
# Deze sectie toetst het BESTAANDE gat, niet de nieuwe route. `GET /file?pid=&aid=` zocht het
# project op, pakte de bijlage en stuurde de bytes — zonder één check. Op productie stonden er 48
# bestanden achter, waaronder die van projecten met `private: True`.

def test_de_file_route_vraagt_nu_wie_je_bent():
    import inspect
    bron = inspect.getsource(cockpit2.make_handler)
    blok = bron.split('if path == "/file":')[1].split('self._send_bytes')[0]
    code = "\n".join(r for r in blok.split("\n") if not r.lstrip().startswith("#"))
    assert "mag_project_lezen" in code, "de /file-route heeft nog steeds geen leescheck"
    assert "404" in code                                   # bestaan is ook informatie


def test_de_twee_routes_delen_dezelfde_check():
    """Eén poort, twee deuren. Zou `/file` zijn eigen regel krijgen, dan lopen ze uit de pas en is
    het gat over een half jaar terug op de plek waar niemand meer kijkt."""
    import inspect
    bron = inspect.getsource(cockpit2.make_handler)
    bijlage = bron.split('if path == "/bijlage":')[1].split('if path == "/file":')[0]
    bestand = bron.split('if path == "/file":')[1].split('self._send_bytes')[0]
    assert "mag_kanaal_lezen" in bijlage
    assert "mag_project_lezen" in bestand
    # en `mag_kanaal_lezen` leunt voor een projectkanaal op exact diezelfde functie
    import inspect as _i
    from nooch_village.views.messages import mag_kanaal_lezen as _mk
    assert "mag_project_lezen" in _i.getsource(_mk)
