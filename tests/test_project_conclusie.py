"""De Conclusion bovenaan een project (2 oktober 2026) — de opvolger van het rapport.

Een lopende samenvatting van 5-10 regels, door een mens geschreven. Een model mag een VOORSTEL
neerleggen ("✨ Draft with AI"), maar pas Save maakt er de conclusie van. "Keep as a fact" zet één
regel ervan op een wiki-pagina, met het project als bron.
"""
from __future__ import annotations

from nooch_village import cockpit2, wiki
from nooch_village.views import projects as P

ROL = "mother_earth__nooch__website_developer"
IK = "ik@nooch.earth"
ANDER = "ander@nooch.earth"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Ik Zelf", IK)
    st.assign.assign(ROL, "person", ik.id)
    st.people.add("Iemand Anders", ANDER)
    pid = st.projects.create(ROL, "Selco als leverancier beoordeeld", "human", status="running")
    return dd, pid


def _doe(dd, actie, wie=IK, **velden):
    return cockpit2.dispatch(dd, actie, {**{k: [v] for k, v in velden.items()}, "next": ["/"]},
                             username=wie)


def _p(dd, pid):
    return cockpit2._Stores(dd).projects.get(pid)


# ══ opslaan ══════════════════════════════════════════════════════════════════
def test_de_rolvervuller_slaat_de_conclusie_op(tmp_path):
    dd, pid = _dorp(tmp_path)
    _n, msg = _doe(dd, "proj_conclusie", pid=pid, conclusion="Selco levert binnen 3 weken.")
    assert not cockpit2.is_weigering(msg), msg
    assert _p(dd, pid)["conclusion"] == "Selco levert binnen 3 weken."


def test_wie_de_rol_niet_vervult_mag_niet_schrijven(tmp_path):
    dd, pid = _dorp(tmp_path)
    _n, msg = _doe(dd, "proj_conclusie", wie=ANDER, pid=pid, conclusion="niet van mij")
    assert cockpit2.is_weigering(msg) or msg.startswith("No access"), msg
    assert not _p(dd, pid).get("conclusion")


# ══ het AI-voorstel ══════════════════════════════════════════════════════════
def test_het_voorstel_raakt_de_conclusie_niet(tmp_path, monkeypatch):
    """Een model dat rechtstreeks in de conclusie schrijft, schrijft over een mens heen."""
    from nooch_village import llm
    gezien = {}
    monkeypatch.setattr(llm, "reason", lambda prompt, **kw: (gezien.update(p=prompt, kw=kw)
                                                             or "Selco kan leveren.\nCertificaat ontbreekt."))
    dd, pid = _dorp(tmp_path)
    _doe(dd, "proj_conclusie", pid=pid, conclusion="eerste versie")
    cockpit2._Stores(dd).projects.add_feed_entry(pid, "Selco belde: 3 weken levertijd.",
                                                 kind="comment", author_type="human")
    _n, msg = _doe(dd, "proj_conclusie_ai", pid=pid)
    assert msg.startswith("✨"), msg
    p = _p(dd, pid)
    assert p["conclusion"] == "eerste versie"
    assert p["conclusion_voorstel"]["tekst"].startswith("Selco kan leveren.")
    # Het materiaal: titel, gesprek en de huidige tekst. De site staat NIET in `HOOG_INZET`: die
    # lijst is bevroren en uitbreiden is een besluit (test_premium_brein) — dorpsladder, net als
    # de wiki-synthese.
    assert "Selco als leverancier beoordeeld" in gezien["p"]
    assert "3 weken levertijd" in gezien["p"] and "eerste versie" in gezien["p"]
    assert gezien["kw"]["call_site"] == "project_conclusie"


def test_opslaan_ruimt_het_voorstel_op(tmp_path):
    dd, pid = _dorp(tmp_path)
    cockpit2._Stores(dd).projects.set_conclusie_voorstel(pid, "voorstel")
    _doe(dd, "proj_conclusie", pid=pid, conclusion="voorstel, aangepast")
    p = _p(dd, pid)
    assert p["conclusion"] == "voorstel, aangepast" and "conclusion_voorstel" not in p


def test_geen_model_is_een_zichtbare_weigering_en_geen_lege_tekst(tmp_path, monkeypatch):
    from nooch_village import llm
    monkeypatch.setattr(llm, "reason", lambda prompt, **kw: None)
    dd, pid = _dorp(tmp_path)
    _n, msg = _doe(dd, "proj_conclusie_ai", pid=pid)
    assert cockpit2.is_weigering(msg), msg
    assert "conclusion_voorstel" not in _p(dd, pid)


def test_discard_gooit_het_voorstel_weg(tmp_path):
    dd, pid = _dorp(tmp_path)
    cockpit2._Stores(dd).projects.set_conclusie_voorstel(pid, "voorstel")
    _doe(dd, "proj_conclusie_verwerp", pid=pid)
    assert "conclusion_voorstel" not in _p(dd, pid)


def test_een_ander_kan_geen_voorstel_laten_maken(tmp_path, monkeypatch):
    from nooch_village import llm
    monkeypatch.setattr(llm, "reason", lambda prompt, **kw: "x")
    dd, pid = _dorp(tmp_path)
    _doe(dd, "proj_conclusie_ai", wie=ANDER, pid=pid)
    assert "conclusion_voorstel" not in _p(dd, pid)


# ══ Keep as a fact ═══════════════════════════════════════════════════════════
def test_een_regel_uit_de_conclusie_wordt_een_feit_met_het_project_als_bron(tmp_path):
    dd, pid = _dorp(tmp_path)
    aid = cockpit2._Stores(dd).att.add(ROL, wiki.PAGINA_KIND, title="Selco (supplier)").id
    _doe(dd, "proj_conclusie", pid=pid, conclusion="Selco levert binnen 3 weken.")
    _n, msg = _doe(dd, "conclusie_naar_wiki", pid=pid, aid=aid, tekst="Selco levert binnen 3 weken.")
    assert not cockpit2.is_weigering(msg), msg
    feit = wiki.feiten(cockpit2._Stores(dd).att.get(aid))[0]
    assert feit["grond"]["soort"] == "bron" and feit["grond"]["ref"] == pid
    assert feit["grond"]["url"] == f"/project?pid={pid}"
    assert "conclusion" in feit["grond"]["citaat"]


# ══ het scherm ═══════════════════════════════════════════════════════════════
def _scherm(dd, pid, wie=IK):
    return P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK", username=wie)


def test_de_conclusie_staat_bovenaan_en_is_klikbaar_voor_de_rolvervuller(tmp_path):
    dd, pid = _dorp(tmp_path)
    _doe(dd, "proj_conclusie", pid=pid, conclusion="Selco levert binnen 3 weken.")
    h = _scherm(dd, pid)
    assert h.index("<h2>Conclusion</h2>") < h.index("<h2>Checklist</h2>")
    assert "Selco levert binnen 3 weken." in h
    blok = h[h.index("<h2>Conclusion</h2>"):h.index("<h2>Checklist</h2>")]
    assert "data-klik-bewerk" in blok and "proj_conclusie_ai" in blok
    # Zonder wiki-pagina geen "Keep as a fact": een knop die nergens heen kan hoort er niet.
    assert "conclusie_naar_wiki" not in blok
    cockpit2._Stores(dd).att.add(ROL, wiki.PAGINA_KIND, title="Selco (supplier)")
    assert "conclusie_naar_wiki" in _scherm(dd, pid)


def test_een_ander_ziet_de_conclusie_als_platte_tekst(tmp_path):
    dd, pid = _dorp(tmp_path)
    _doe(dd, "proj_conclusie", pid=pid, conclusion="Selco levert binnen 3 weken.")
    h = _scherm(dd, pid, wie=ANDER)
    blok = h[h.index("<h2>Conclusion</h2>"):h.index("<h2>Checklist</h2>")]
    assert "Selco levert binnen 3 weken." in blok
    assert "data-klik-bewerk" not in blok and "proj_conclusie_ai" not in blok


def test_een_wachtend_voorstel_staat_open_in_het_bewerkveld(tmp_path):
    dd, pid = _dorp(tmp_path)
    cockpit2._Stores(dd).projects.set_conclusie_voorstel(pid, "Het voorstel van het model.")
    h = _scherm(dd, pid)
    blok = h[h.index("<h2>Conclusion</h2>"):h.index("<h2>Checklist</h2>")]
    assert "draft conclusion" in blok and "proj_conclusie_verwerp" in blok
    form = blok[blok.index("data-bewerk="):]
    assert "Het voorstel van het model." in form
    assert form[:form.index(">")].find(" hidden") == -1, "het bewerkveld staat dicht"
