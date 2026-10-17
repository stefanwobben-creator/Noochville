"""Zoeken: actieve projecten eerst (17 oktober 2026, besluit Stefan).

Volgorde in de groep Projects: actief (niet afgerond, niet gearchiveerd), dan afgerond, dan
gearchiveerd; binnen een groep de bestaande volgorde. Alleen de VOLGORDE verandert: dezelfde
treffers, hetzelfde aantal, en de andere groepen blijven zoals ze waren."""
from __future__ import annotations

import re

from nooch_village import cockpit2
from nooch_village.views import search as S

ROL = "mother_earth__nooch__website_developer"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    pj = st.projects
    # bewust door elkaar aangemaakt: de opslagvolgorde is afgerond, gearchiveerd, actief, actief, afgerond
    ids = {
        "af1": pj.create(ROL, "Okapi sole done", "human"),
        "arch": pj.create(ROL, "Okapi sole archived", "human"),
        "act1": pj.create(ROL, "Okapi sole running", "human", status="running"),
        "act2": pj.create(ROL, "Okapi sole future", "human"),
        "af2": pj.create(ROL, "Okapi lace done", "human"),
        "anders": pj.create(ROL, "Something else", "human"),
    }
    for k in ("af1", "af2"):
        pj.get(ids[k])["status"] = "done"
    pj._save()
    pj.archive(ids["arch"])
    return dd, ids


def _volgorde(hits):
    return [h["url"].split("id=")[1] for h in hits]


def test_actief_dan_afgerond_dan_gearchiveerd_binnen_een_groep_de_oude_volgorde(tmp_path):
    dd, ids = _dorp(tmp_path)
    hits = S._projects(cockpit2._Stores(dd), ["okapi"])
    assert _volgorde(hits) == [ids["act1"], ids["act2"], ids["af1"], ids["af2"], ids["arch"]]
    # het bestaande statuslabel staat er, en er is geen nieuw label bijgekomen
    assert [h["snip"] for h in hits] == ["running", "future", "done", "done", "future"]   # archief: eigen status


def test_dezelfde_treffers_en_hetzelfde_aantal_als_voorheen(tmp_path):
    """De oude regel, hier letterlijk nagebouwd (opslagvolgorde, geen sortering): de SET treffers en
    het AANTAL zijn gelijk; alleen de volgorde verschilt."""
    dd, _ids = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    for termen in (["okapi"], ["okapi", "sole"], ["lace"], ["done"], ["niets-dat-bestaat"]):
        oud = [{"url": f"/project?id={p.get('id')}", "kind": "project",
                "titel": str(p.get("scope") or ""), "snip": str(p.get("status") or "")}
               for p in st.projects.all() if S._prive_weg(p) and S._match(str(p.get("scope") or ""), termen)]
        nieuw = S._projects(st, termen)
        assert len(nieuw) == len(oud)
        assert sorted(map(repr, nieuw)) == sorted(map(repr, oud))


def test_de_andere_groepen_veranderen_niet(tmp_path):
    dd, _ids = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    res, fouten = S._zoek(st, ["okapi"])
    assert not fouten
    per = dict(res)
    assert [len(per[g]) for g, _f in S._GROEPEN].count(0) >= 1          # er is gezocht in alle groepen
    for groep, fn in S._GROEPEN:
        if groep != "Projects":
            assert per[groep] == (fn(st, ["okapi"], None) if groep in S._PROJECTGROEPEN else fn(st, ["okapi"]))


def test_ook_in_de_live_dropdown_en_op_de_zoekpagina(tmp_path):
    """De dropdown toont er vier per groep: daar telt de volgorde het meest."""
    dd, ids = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    frag = S.render_search_fragment(st, "okapi")
    blok = frag.split("<h2>Projects (5)", 1)[1].split("</div>", 1)[0]
    zichtbaar = re.findall(r"/project\?id=([0-9a-f]+)", blok)
    assert zichtbaar == [ids["act1"], ids["act2"], ids["af1"], ids["af2"]] and "+1 more" in blok
    pagina = S.render_search(st, "okapi")
    alle = re.findall(r"/project\?id=([0-9a-f]+)", pagina.split("Projects (5)", 1)[1].split("<h2", 1)[0])
    assert alle == [ids["act1"], ids["act2"], ids["af1"], ids["af2"], ids["arch"]]
