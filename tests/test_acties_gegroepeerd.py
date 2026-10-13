"""/acties gegroepeerd (Today deel 2, 13 oktober 2026).

"From project checklists" staat per project in een `<details>` (werkt zonder JavaScript), grootste
groep eerst en alleen die open, met het aantal regels in de kop. "From your projects" is ook een
groep. Het formulier "New action" blijft werken en heeft een zichtbaar label. Wat er wordt
opgeslagen en wie wat ziet, verandert niet.
"""
from __future__ import annotations

import re

import pytest

from nooch_village import cockpit2
from nooch_village.views.acties import render_acties

ROL = "mother_earth__nooch__marketing_lead"
#: Zoals op productie (11 oktober): 24 regels over 8 projecten.
VERDELING = (("Vegan Society", 7), ("MITH report", 5), ("Portugal trip", 5), ("Barefoot", 2),
             ("Alicante", 2), ("Membership", 1), ("Subsidie", 1), ("PDP template", 1))


@pytest.fixture
def dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Lid", "lid@t.nl").id
    st.assign.assign(ROL, "person", ik)
    for titel, n in VERDELING:
        pid = st.projects.create(ROL, titel, "human", status="running")
        cl = st.projects.checklist_add(pid, "Plan")
        for i in range(n):
            st.projects.check_add(pid, cl["id"], f"{titel} stap {i}")
    # een actie van iemand anders op een project van mij: "From your projects"
    ander = st.people.add("Ander", "ander@t.nl").id
    eerste = next(p for p in st.projects.all() if p.get("scope") == "Vegan Society")
    st.acties.add(ander, "Bel de certificeerder", project=eerste["id"])
    return dd, ik


def _groepen(html: str, kop: str):
    blok = html.split(kop, 1)[1]
    return re.findall(r"<details class='box-details'( open)?><summary>(.*?) &middot; (\d+)</summary>", blok)


def test_de_groepen_tellen_op_tot_24_grootste_eerst_alleen_die_open(dorp):
    dd, ik = dorp
    h = render_acties(cockpit2._Stores(dd), ik=ik, csrf_token="T")
    assert "From project checklists &middot; 24 in 8 projects" in h
    groepen = _groepen(h, "From project checklists")
    assert sum(int(n) for _o, _naam, n in groepen) == 24
    assert [(naam, int(n)) for _o, naam, n in groepen] == sorted(
        VERDELING, key=lambda t: (-t[1], t[0].lower()))
    assert [bool(o) for o, _n, _k in groepen] == [True] + [False] * 7
    assert h.split("From project checklists", 1)[1].count("needs a human</span>") == 24


def test_from_your_projects_is_ook_een_groep_en_blijft_zichtbaar(dorp):
    dd, ik = dorp
    h = render_acties(cockpit2._Stores(dd), ik=ik, csrf_token="T")
    blok = h.split("From your projects", 1)[1].split("From project checklists", 1)[0]
    assert "<details class='box-details' open><summary>Vegan Society &middot; 1</summary>" in blok
    assert "Bel de certificeerder" in blok


def test_opvouwbaar_zonder_javascript(dorp):
    """`<details>`/`<summary>` is HTML: geen script nodig. Geen onclick of data-attribuut dat JS eist."""
    dd, ik = dorp
    h = render_acties(cockpit2._Stores(dd), ik=ik, csrf_token="T")
    for d in re.findall(r"<details class='box-details'[^>]*>", h):
        assert "onclick" not in d and "data-" not in d


def test_new_action_heeft_een_zichtbaar_label_en_het_formulier_werkt(dorp):
    dd, ik = dorp
    h = render_acties(cockpit2._Stores(dd), ik=ik, csrf_token="T")
    assert re.search(r"<label class=\"att-lbl\" for=\"actie-tekst\">New action</label>", h)
    assert "class='sr' for='actie-tekst'" not in h
    assert re.search(r"<input [^>]*id=\"actie-tekst\" name=\"tekst\"", h)
    assert "value='actie_add'" in h
    _n, msg = cockpit2.dispatch(dd, "actie_add", {"tekst": ["Nieuwe actie"], "next": ["/acties"]},
                                username="lid@t.nl")
    st = cockpit2._Stores(dd)
    assert any(a.get("tekst") == "Nieuwe actie" for a in st.acties.voor(ik)), msg
