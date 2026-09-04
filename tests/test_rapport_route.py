"""De kaart wijst naar het document; het document woont op `/rapport`.

Twee dingen die deze tests bewaken en die met de hand makkelijk terugsluipen:
1. de kaart toont het volledige rapport NIET meer inline (dat was het hele punt);
2. `proj_doc_edit` en `proj_regen_doc` blijven bereikbaar — nu op de route. Bij de herindeling
   verdwenen drie acties stil omdat hun blok in een verwijderde rij zat; dat mag niet nog eens.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.projects import seed_document
from nooch_village.views import projects as P
from nooch_village.views.rapport import render_projectrapport

ROLE = "mother_earth__nooch__website_developer"
# Een UNIEKE staart: met een herhaalde zin komt de staart ook in de gekapte essentie voor, en
# dan bewijst de test niets over wat er is weggelaten.
_STAART = "Deze laatste alinea hoort alleen in het volledige rapport thuis."
_LANG = ("Het onderzoek laat zien dat er geen harde onderbouwing bestaat voor de claim. "
         + "Vervolgens beschrijft het rapport per bron waarom die niet volstaat. " * 6
         + _STAART)


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _project(dd, st, doc: str = "", done_when: str = ""):
    pid = st.projects.create(ROLE, "Hemp canvas bij een tweede leverancier", "human",
                             status="queued")
    if done_when:
        st.projects.set_dod(pid, "done_when", done_when)
    if doc:
        cockpit2._Stores(dd).project_docs.write(pid, doc)
    return pid


# ── de kaart ─────────────────────────────────────────────────────────────────
def test_kaart_toont_het_rapport_niet_meer_inline(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(dd, st, f"# Kop\n\n{_LANG}\n")
    frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    assert "einddoc-kern" in frag                       # de essentie staat er
    assert "einddoc-body" not in frag                   # het volledige rapport niet
    assert _STAART not in frag                          # en de staart al helemaal niet
    assert f"/rapport?pid={pid}" in frag                # met een weg ernaartoe


def test_kaart_bij_een_seed_toont_de_lege_staat_niet_de_opdracht(tmp_path):
    """De 'klaar wanneer'-regel als essentie zou bij 84 van de 107 de titel herhalen die er
    twee centimeter boven staat — én zeggen dat er een rapport is dat er niet is."""
    dd, st = _st(tmp_path)
    dw = "De shortlist van drie leveranciers is af"
    pid = _project(dd, st, seed_document(dw), done_when=dw)
    frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    assert "No report written yet" in frag
    assert "einddoc-kern" not in frag and dw not in frag
    assert "Read the assignment" in frag                # nog steeds één klik weg


def test_kaart_zonder_document_houdt_de_bestaande_lege_staat(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(dd, st)
    frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    assert "No end document yet" in frag
    assert "/rapport?pid=" not in frag                  # niets om heen te gaan


def test_kaart_zonder_bruikbare_essentie_toont_alleen_de_link(tmp_path):
    """Trede 4 (4x op prod): liever niets dan een fragment dat zich als samenvatting voordoet."""
    dd, st = _st(tmp_path)
    pid = _project(dd, st, "# Alleen een kop\n\n- en een lijst\n")
    frag = P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK")
    assert "einddoc-kern" not in frag
    assert "Full report" in frag


# ── de route ─────────────────────────────────────────────────────────────────
def test_route_toont_het_volledige_rapport_in_de_leeslaag(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(dd, st, f"# Kop\n\n{_LANG}\n")
    html = render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="TOK")
    assert "einddoc-body" in html                       # dezelfde leeslaag-typografie (#441)
    # ...maar ZONDER hoogte-cap. Die beschermde de kaart tegen een inline rapport; sinds het
    # rapport hier woont beschermt hij niets en maakt hij een scrollbak binnen een scrollende
    # pagina (gemeten: 1540px inhoud in 431px venster). Getoetst op de STIJL zelf, niet op een
    # klassenaam — een klasse die niets doet is geen bewijs.
    import pathlib as _pl
    _css = _pl.Path("nooch_village/static/nooch.css").read_text(encoding="utf-8")
    _regel = [r for r in _css.splitlines() if r.startswith(".einddoc-body{")]
    assert _regel and "max-height" not in _regel[0], _regel
    assert _STAART in html                              # niets weggesneden
    assert f"/project?pid={pid}" in html                # en een weg terug


def test_bewerken_en_verversen_blijven_bereikbaar_op_de_route(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(dd, st, "# Kop\n\nEen zin die als essentie kan dienen op de kaart.\n")
    html = render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="TOK")
    for actie in ("proj_doc_edit", "proj_regen_doc"):
        assert f"value='{actie}'" in html, f"{actie} onbereikbaar geworden"
    assert "/rapport?pid=" in html                      # na opslaan blijf je bij het document


def test_route_zonder_schrijfrecht_toont_geen_bewerkacties(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(dd, st, "# Kop\n\nEen zin die als essentie kan dienen op de kaart.\n")
    html = render_projectrapport(cockpit2._Stores(dd), pid, csrf_token="")
    assert "proj_doc_edit" not in html and "proj_regen_doc" not in html
    assert "einddoc-body" in html                                # lezen mag wel


def test_route_onderscheidt_seed_van_geen_document(tmp_path):
    """Drie toestanden, drie zinnen — ze op één hoop gooien is wat de kaart hiervóór deed."""
    dd, st = _st(tmp_path)
    leeg = _project(dd, st)
    dw = "De shortlist is af"
    seed = _project(dd, st, seed_document(dw), done_when=dw)
    h_leeg = render_projectrapport(cockpit2._Stores(dd), leeg, csrf_token="TOK")
    h_seed = render_projectrapport(cockpit2._Stores(dd), seed, csrf_token="TOK")
    assert "No end document yet" in h_leeg
    assert "No report written yet" in h_seed and dw in h_seed   # de opdracht staat er wél
    assert "No end document yet" not in h_seed


def test_onbekend_project_geeft_een_nette_melding(tmp_path):
    dd, _ = _st(tmp_path)
    html = render_projectrapport(cockpit2._Stores(dd), "bestaat-niet", csrf_token="TOK")
    assert "Report not found" in html


def test_de_claims_renderer_blijft_zijn_eigen_functie():
    """De naamsbotsing die #444 introduceerde: `views/claims.render_rapport` werd in cockpit2 stil
    overschreven door de project-renderer, dus de claims-aanroep gaf `uitslag` door als `st`.

    Deze test raakt het pad dat toen geen dekking had: hij roept de claims-renderer met zijn eigen
    handtekening aan. Kruipt de botsing terug, dan valt hij hier om — naast de structurele guard in
    test_architectuur.py die de dubbele naam zelf verbiedt."""
    from nooch_village.views.claims import render_rapport as claims_rapport
    from nooch_village.views.rapport import render_projectrapport
    assert claims_rapport is not render_projectrapport
    frag = claims_rapport({"bevindingen": [], "score": 100}, markten=[], bron="test",
                          csrf_token="TOK", kan_bord=False, db=None)
    assert isinstance(frag, str) and frag
