"""Vier dingen uit echt gebruik van de projectkaart.

Geen van de vier was een bug in de zin van "het werkt niet". Alle vier waren gedrag dat klopte op
papier en irriteerde in de praktijk — het soort dat alleen boven komt als iemand de kaart echt
gebruikt, en dat daarna weer terugsluipt zodra niemand het vastlegt.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views import projects as P

ROLE = "mother_earth__nooch__brand_visual_designer"


def _kaart(tmp_path, *, rw=True):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    pid = st.projects.create(ROLE, "Interactie", "human", status="queued", done_when="af")
    st.projects.start(pid)
    cl = st.projects.checklist_add(pid, "tasks")["id"]
    # TWEE items: met één item maakt afvinken de checklist compleet, en dán schrijft de
    # review-poort "✅ Checklist voltooid — klaar voor review" in de wall. Dat is een
    # PROJECTGEBEURTENIS en geen echo van het vinkje; die hoort er wél te staan.
    st.projects.check_add(pid, cl, "Eerste stap")
    st.projects.check_add(pid, cl, "Tweede stap")
    item = cockpit2._Stores(dd).projects.get(pid)["checklists"][0]["items"][0]["id"]
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "text": ["mijn comment"],
                                        "author": ["human:"], "next": ["/"]}, username="guest")
    html = P.render_project(cockpit2._Stores(dd), pid, csrf_token=("TOK" if rw else ""))
    return dd, pid, cl, item, html


def _wall_regels(dd, pid):
    return [e for e in (cockpit2._Stores(dd).projects.get(pid).get("log") or [])
            if isinstance(e, dict) and (e.get("text") or "").strip()]


# ── 1. afvinken echoot niet in de wall ───────────────────────────────────────
def test_een_kaal_vinkje_zet_geen_regel_in_de_wall(tmp_path):
    """Het vinkje stáát al op de checklist, twee centimeter hoger. Dezelfde staat een tweede keer
    in de wall zetten is ruis — en bij een lange checklist verdrinkt het echte gesprek erin.
    Zelfde regel als "één huis per eigenschap"."""
    dd, pid, cl, item, _ = _kaart(tmp_path)
    voor = len(_wall_regels(dd, pid))
    cockpit2.dispatch(dd, "check_toggle", {"pid": [pid], "clid": [cl], "item": [item],
                                           "next": ["/"]}, username="guest")
    assert cockpit2._Stores(dd).projects.get(pid)["checklists"][0]["items"][0]["done"] is True
    assert len(_wall_regels(dd, pid)) == voor, "afvinken schreef tóch in de wall"


def test_afvinken_MET_een_reden_schrijft_wel(tmp_path):
    """Een reden is nieuwe informatie die nergens anders staat: waarom dit item afging, niet dát
    het afging. Dat hoort juist wél in de wall."""
    from nooch_village import project_items
    dd, pid, cl, item, _ = _kaart(tmp_path)
    st = cockpit2._Stores(dd)
    voor = len(_wall_regels(dd, pid))
    project_items.resolve_item(st.projects, pid, cl, item, "done", by="mens",
                               reason="leverancier bevestigde per mail")
    regels = _wall_regels(dd, pid)
    assert len(regels) == voor + 1
    assert "leverancier bevestigde" in regels[-1]["text"]


# ── 2. opslaan houdt je op de kaart ──────────────────────────────────────────
def test_comment_bewerken_stuurt_je_terug_naar_het_project(tmp_path):
    """Zonder `next` valt de dispatch terug op "/" en beland je op het beginscherm — weg uit het
    project waarin je aan het werk was."""
    dd, pid, _, _, html = _kaart(tmp_path)
    form = html[html.index("fentry-edit"):]
    form = form[:form.index("</form>")]
    assert f"name=\"next\" value=\"/project?pid={pid}" in form or \
           f"name='next' value='/project?pid={pid}" in form, form[:300]


def test_opslaan_landt_ook_echt_daar(tmp_path):
    dd, pid, _, _, _ = _kaart(tmp_path)
    eid = _wall_regels(dd, pid)[-1]["id"]
    nxt, msg = cockpit2.dispatch(dd, "feed_edit",
                                 {"pid": [pid], "item": [eid], "text": ["bijgewerkt"],
                                  "next": [f"/project?pid={pid}"]}, username="guest")
    assert nxt.startswith(f"/project?pid={pid}"), nxt
    assert not cockpit2.is_weigering(msg), msg
    assert _wall_regels(dd, pid)[-1]["text"] == "bijgewerkt"


# ── 3. bewerken gebeurt in het veld zelf ─────────────────────────────────────
def test_bewerken_is_inline_en_niet_een_tweede_veld_eronder(tmp_path):
    """Een <details> dat een kopie van de bubbel opent, laat je twee versies van dezelfde regel
    naast elkaar lezen en je moet raden welke de echte is. Zoals het aanpassen van de projecttitel
    al werkt: het veld staat op de plek van de tekst."""
    dd, pid, _, _, html = _kaart(tmp_path)
    assert "fentry-edit" in html and "data-fb=" in html      # bubbel en editor delen een plek
    # De oude klapper was `<details class='fedit'><summary>Edit</summary>`. Alleen díe is weg;
    # `.fedit` zelf leeft nog voor de hand-off-klapper op checklist-items.
    assert "<summary class='flink'>Edit</summary>" not in html
    # de editor start verborgen en de bubbel zichtbaar
    i = html.index("fentry-edit")
    assert "hidden" in html[i:i + 200]


def test_read_only_toont_geen_editor(tmp_path):
    """De terugweg naar de kaart hing eerst aan `if rw:` en werd daarbuiten gebruikt — read-only
    viel om met een UnboundLocalError. Hij beschrijft WAAR je bent, niet of je mag schrijven."""
    dd, pid, _, _, html = _kaart(tmp_path, rw=False)
    assert "fentry-edit" not in html and ">Edit</button>" not in html
    assert "Interactie" in html                              # en de kaart rendert gewoon


# ── 4. terminale statussen in de status-pulldown ─────────────────────────────
def test_archiveren_en_verwijderen_zitten_in_de_status_pulldown(tmp_path):
    """Het zijn eindpunten van hetzelfde veld: waar een project staat. Ze stonden onderaan de rail
    onder een eigen "More", los van de plek waar je de status verandert — twee menu's voor één
    vraag is er één te veel."""
    dd, pid, _, _, html = _kaart(tmp_path)
    rail = html[html.index("pkaart-rail"):]
    menu = rail[rail.index("aria-label='change status'"):]
    menu = menu[:menu.index("</details>")]
    for actie in ("proj_status", "proj_done", "proj_archive", "proj_delete"):
        assert f"value='{actie}'" in menu, f"{actie} niet in de status-pulldown"
    assert "rail-meer" not in rail                            # het aparte ⋯-menu is weg
    assert ">More<" not in rail


def test_verwijderen_blijft_om_bevestiging_vragen(tmp_path):
    """Verplaatsen mag de drempel niet weghalen: delete is onomkeerbaar, archiveren niet."""
    dd, pid, _, _, html = _kaart(tmp_path)
    i = html.index("value='proj_delete'")
    blok = html[max(0, i - 300):i + 100]
    assert "confirm(" in blok and "Archiving keeps the project" in blok
    assert "menuitem danger" in blok
