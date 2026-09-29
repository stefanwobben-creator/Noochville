"""Vijf punten uit het gebruik van drie schermen (29 september 2026, avond — feedback Stefan).

Geen gedeeld thema behalve de bron: iemand die de schermen ECHT gebruikt, loopt tegen dingen aan
die je bij het bouwen niet ziet. Wat ze wel delen is de vorm van de oplossing — elk punt hangt aan
mechaniek die er al was:

  1. de promptkaart van de coach vergrijst als je de velden verandert zonder opnieuw te bouwen;
  2. een agendapunt afvinken kan vanuit de LIJST, met dezelfde actie als de knop op de stap zelf;
  3. de rollen van een cirkel staan in een zichtbare keuzelijst in plaats van een `<datalist>`;
  4. een accountability bijstellen zonder zijn plek in de lijst te verliezen;
  5. een hele rol plakken, die daarna het gewone voorstel-pad in gaat.
"""
from __future__ import annotations

import re

from nooch_village import cockpit2
from nooch_village.views.roloverleg import plak_rol

C = "mother_earth__nooch"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    st.people.add("Tester", "t@nooch.earth")
    return dd, cockpit2._Stores(dd)


def _doe(dd, actie, **velden):
    velden = {"csrf": "t", "next": ["/"][0], **velden}
    return cockpit2.dispatch(dd, actie, {k: [str(v)] for k, v in velden.items()}, username="guest")


# ══ 1. De coach: een prompt die achterloopt, zegt dat ════════════════════════
def test_de_promptkaart_weet_bij_welk_formulier_hij_hoort(tmp_path):
    """DE KOPPELING IS HET HELE MECHANISME. `data-verouderd-bij` wijst naar het formulier; zonder
    die verwijzing weet de JS niet wát er veranderd kan zijn en gebeurt er niets."""
    from nooch_village.views.decision_coach import render_decision_coach
    dd, st = _dorp(tmp_path)
    h = render_decision_coach(st, base_dir=".", data_dir=dd, csrf_token="t",
                              waarden={"decision": "Wisselen we van leverancier?",
                                       "deadline": "2026-10-10", "options": "ja\nnee"})
    assert "id='dc-form'" in h
    assert "data-verouderd-bij='#dc-form'" in h
    assert "is-verouderd-melding" in h and "Build the prompt" in h


def test_zonder_prompt_geen_verouderd_blok(tmp_path):
    """Nog niets gebouwd = niets dat kan achterlopen. Een melding over een prompt die er niet is,
    is ruis."""
    from nooch_village.views.decision_coach import render_decision_coach
    dd, st = _dorp(tmp_path)
    h = render_decision_coach(st, base_dir=".", data_dir=dd, csrf_token="t", waarden={})
    assert "data-verouderd-bij" not in h


def test_de_melding_staat_in_de_pagina_en_niet_in_de_javascript():
    """TAAL HOORT SERVER-SIDE. De JS zet alleen een klasse; zou hij de zin schrijven, dan staat er
    Engelse tekst in een bestand waar de taal-ratchet en de i18n-laag niet bij kunnen."""
    import pathlib
    js = (pathlib.Path(__file__).resolve().parents[1] / "nooch_village" / "static" / "nooch.js").read_text()
    blok = js.split("function verouderend")[1].split("function pollers")[0]
    assert "is-verouderd" in blok
    assert "Build the prompt" not in blok and "changed" not in blok.lower()


def test_de_css_toont_de_melding_alleen_als_hij_geldt():
    from conftest import basis_css
    css = basis_css()
    assert ".is-verouderd-melding{display:none}" in css
    assert ".is-verouderd .is-verouderd-melding{display:block" in css


# ══ 2. Werkoverleg: afvinken vanuit de agendalijst ═══════════════════════════
def _agenda(dd, punt="Een punt"):
    _doe(dd, "wo_open", circle=C)
    _doe(dd, "vangst_add", circle=C, punt=punt)
    st = cockpit2._Stores(dd)
    return st, st.werk.punten(C)[0]


def test_elk_punt_in_de_lijst_heeft_een_vinkje(tmp_path):
    dd, st = _dorp(tmp_path)
    st, it = _agenda(dd)
    frag = cockpit2.render_werkoverleg(st, C, "agenda", csrf_token="t", fragment=True)
    lijst = frag.split("wo-substeps")[1].split("</div></div>")[0]
    assert "ck-box" in lijst and "value='vangst_klaar'" in lijst
    assert f"value='{it['id']}'" in lijst


def test_het_vinkje_zet_het_punt_om_en_terug(tmp_path):
    """DEZELFDE ACTIE als de knop onderaan het paneel — geen tweede mechanisme, alleen een tweede
    plek om hem aan te roepen."""
    dd, st = _dorp(tmp_path)
    st, it = _agenda(dd)
    _doe(dd, "vangst_klaar", circle=C, iid=it["id"], klaar="1")
    assert cockpit2._Stores(dd).werk.punten(C)[0]["status"] == "done"
    frag = cockpit2.render_werkoverleg(cockpit2._Stores(dd), C, "agenda", csrf_token="t",
                                       fragment=True)
    lijst = frag.split("wo-substeps")[1].split("</div></div>")[0]
    assert "ck-box on" in lijst, "het vakje staat niet aan"
    assert "value='0'" in lijst, "de volgende klik zou niet heropenen"


def test_zonder_schrijfrecht_geen_vinkje(tmp_path):
    """Een knop die de server daarna weigert, belooft iets wat niet kan."""
    dd, st = _dorp(tmp_path)
    st, it = _agenda(dd)
    frag = cockpit2.render_werkoverleg(st, C, "agenda", csrf_token="", fragment=True)
    assert "wo-substeps" in frag and "value='vangst_klaar'" not in frag.split("wo-substeps")[1][:800]


# ══ 3. Roloverleg: de rollen staan in een zichtbare lijst ════════════════════
def test_de_rollen_van_de_cirkel_staan_in_een_keuzelijst(tmp_path):
    dd, st = _dorp(tmp_path)
    frag = cockpit2.render_roloverleg2(st, C, csrf_token="t", fragment=True)
    assert "<datalist" not in frag, "de onzichtbare suggestielijst staat er nog"
    keuze = frag.split("name='naam_keuze'")[1].split("</select>")[0]
    assert "pick an existing role" in keuze
    namen = re.findall(r"<option value='([^']+)'>", keuze)
    assert len(namen) >= 3 and "Website Developer" in namen


def test_kiezen_uit_de_lijst_werkt_net_als_typen(tmp_path):
    dd, st = _dorp(tmp_path)
    _doe(dd, "rov2_add", circle=C, naam="", naam_keuze="Website Developer")
    items = cockpit2._Stores(dd).agenda.open()
    assert len(items) == 1 and items[0]["title"] == "Website Developer"
    assert items[0]["kind"] == "amend_role", "een bestaande rol hoort een amendement te worden"


def test_typen_wint_van_de_lijst(tmp_path):
    """Wie iets TYPT bedoelt dat — ook als er nog een keuze van een vorige poging in de lijst
    staat. Andersom zou je nieuwe rol stilletjes een amendement op een bestaande worden."""
    dd, st = _dorp(tmp_path)
    _doe(dd, "rov2_add", circle=C, naam="Sock Designer", naam_keuze="Website Developer")
    items = cockpit2._Stores(dd).agenda.open()
    assert items[0]["title"] == "Sock Designer" and items[0]["kind"] == "add_role"


# ══ 4. Een accountability bijstellen ═════════════════════════════════════════
def _voorstel(dd, naam="Sock Designer"):
    _doe(dd, "rov2_add", circle=C, naam=naam)
    return cockpit2._Stores(dd).agenda.open()[0]["id"]


def _accs(dd, iid):
    from nooch_village.views.roloverleg import _rov_draft
    st = cockpit2._Stores(dd)
    return _rov_draft(st, st.agenda.get(iid))["accs"]


def test_bijstellen_houdt_de_plek_in_de_lijst(tmp_path):
    """DE REDEN DAT DIT GEEN remove+add IS. Die combinatie zet de regel onderaan en laat het
    voorstel lezen als "deze is weg, die is nieuw" terwijl er één woord veranderde."""
    dd, st = _dorp(tmp_path)
    iid = _voorstel(dd)
    for t in ("Keeping the shop reachable", "Publishing the weekly page", "Answering questions"):
        _doe(dd, "rov2_acc_add", circle=C, iid=iid, text=t)
    _doe(dd, "rov2_acc_edit", circle=C, iid=iid, idx="1", nieuw="Publishing the weekly page on Friday")
    assert _accs(dd, iid) == ["Keeping the shop reachable",
                              "Publishing the weekly page on Friday",
                              "Answering questions"]


def test_bijstellen_naar_een_bestaande_tekst_doet_niets(tmp_path):
    """Dedup, net als bij toevoegen: twee identieke accountabilities zijn er één, en stilzwijgend
    samenvoegen zou er één laten verdwijnen."""
    dd, st = _dorp(tmp_path)
    iid = _voorstel(dd)
    for t in ("Eerste", "Tweede"):
        _doe(dd, "rov2_acc_add", circle=C, iid=iid, text=t)
    _doe(dd, "rov2_acc_edit", circle=C, iid=iid, idx="1", nieuw="eerste")
    assert _accs(dd, iid) == ["Eerste", "Tweede"]


def test_een_lege_tekst_of_rare_index_verandert_niets(tmp_path):
    dd, st = _dorp(tmp_path)
    iid = _voorstel(dd)
    _doe(dd, "rov2_acc_add", circle=C, iid=iid, text="Eerste")
    _doe(dd, "rov2_acc_edit", circle=C, iid=iid, idx="0", nieuw="   ")
    _doe(dd, "rov2_acc_edit", circle=C, iid=iid, idx="9", nieuw="Negende")
    _doe(dd, "rov2_acc_edit", circle=C, iid=iid, idx="geen getal", nieuw="Iets")
    assert _accs(dd, iid) == ["Eerste"]


def test_de_bijstel_knop_staat_bij_de_accountabilities_en_niet_bij_de_domeinen(tmp_path):
    """Gevraagd voor accountabilities. Een domein is een naam, geen zin die je herformuleert."""
    dd, st = _dorp(tmp_path)
    iid = _voorstel(dd)
    _doe(dd, "rov2_acc_add", circle=C, iid=iid, text="Keeping the shop reachable")
    _doe(dd, "rov2_dom_add", circle=C, iid=iid, text="nooch.earth")
    frag = cockpit2.render_roloverleg2(cockpit2._Stores(dd), C, csrf_token="t", fragment=True,
                                       iid=iid)
    accs, doms = frag.split("Accountabilities")[1].split("Domains")
    assert "rov2_acc_edit" in accs
    assert "rov2_acc_edit" not in doms and "rov2_dom_edit" not in doms


# ══ 5. Een hele rol plakken ══════════════════════════════════════════════════
PLAK = """role: Sock Designer
purpose: Socks that outlive the shoe
domain: sokken
Keeping the sock range in stock
Publishing the care instructions"""


def test_de_parser_kent_drie_labels_en_de_rest_is_accountability():
    r = plak_rol(PLAK)
    assert r["naam"] == "Sock Designer"
    assert r["purpose"] == "Socks that outlive the shoe"
    assert r["domains"] == ["sokken"]
    assert r["accs"] == ["Keeping the sock range in stock", "Publishing the care instructions"]


def test_een_accountability_met_een_dubbele_punt_blijft_een_accountability():
    """Anders verdwijnt "Publishing the page: on Friday" stilzwijgend in een veld dat niemand
    bedoelde. Alleen de drie bekende labels tellen."""
    r = plak_rol("role: X\nPublishing the page: on Friday")
    assert r["accs"] == ["Publishing the page: on Friday"]


def test_meerdere_domeinen_mogen_elk_op_een_regel():
    r = plak_rol("role: X\ndomain: a\ndomain: b")
    assert r["domains"] == ["a", "b"]


def test_plakken_zet_een_compleet_voorstel_op_de_agenda(tmp_path):
    dd, st = _dorp(tmp_path)
    _n, msg = _doe(dd, "rov2_plak", circle=C, tekst=PLAK)
    assert not cockpit2.is_weigering(msg), msg
    assert "2 accountabilities" in msg
    st = cockpit2._Stores(dd)
    it = st.agenda.open()[0]
    assert it["title"] == "Sock Designer" and it["kind"] == "add_role"
    from nooch_village.views.roloverleg import _rov_draft
    d = _rov_draft(st, it)
    assert d["purpose"] == "Socks that outlive the shoe"
    assert d["domains"] == ["sokken"] and len(d["accs"]) == 2
    # EN HET LOOPT DOOR HET GEWONE PAD: de change is herberekend, dus het scherm en de
    # consent-poort zien een normaal voorstel.
    ch = it if isinstance(it.get("change"), dict) else {}
    assert st.agenda.get(it["id"])["change"].get("add_accountabilities"), ch


def test_zonder_role_regel_gebeurt_er_niets(tmp_path):
    """Fail-closed: de naam is het enige veld waar de rest aan hangt."""
    dd, st = _dorp(tmp_path)
    _n, msg = _doe(dd, "rov2_plak", circle=C, tekst="purpose: iets\nKeeping things")
    assert cockpit2.is_weigering(msg) and "role:" in msg
    assert cockpit2._Stores(dd).agenda.open() == []


def test_plakken_op_een_bestaande_rol_vult_aan(tmp_path):
    """Dan is het een AMENDEMENT, en zijn de huidige accountabilities de basis. Overschrijven zou
    bestaand werk laten verdwijnen zonder dat het voorstel dat zegt."""
    dd, st = _dorp(tmp_path)
    rec = cockpit2._Stores(dd).records.get("mother_earth__nooch__website_developer")
    was = list(rec.definition.accountabilities)
    _doe(dd, "rov2_plak", circle=C, tekst="role: Website Developer\nWatching the uptime")
    st = cockpit2._Stores(dd)
    it = st.agenda.open()[0]
    from nooch_village.views.roloverleg import _rov_draft
    d = _rov_draft(st, it)
    assert it["kind"] == "amend_role"
    assert d["accs"][:len(was)] == was and d["accs"][-1] == "Watching the uptime"
