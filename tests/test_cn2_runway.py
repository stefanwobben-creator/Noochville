"""CN2 Runway (10 oktober 2026): vaste kosten, cash, het quotiënt, en wie het mag zien en wijzigen."""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, critical_numbers, zicht
from nooch_village.finance_recurring import maak_regel
from nooch_village.vaste_kosten import maak_regel as oude_maak_regel
from nooch_village.views.metrics import _sources_for, runway
from nooch_village.views.metrics2 import render_metrics2_tab
from nooch_village.views.vaste_kosten import render_vaste_kosten
from nooch_village.views.werkoverleg import _wo_metrics

C = "mother_earth__nooch"
FC = "mother_earth__nooch__financial_controller"
BS = "mother_earth__nooch__strategic_lead_founder_steward"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    for naam, mail, rol in (("Fien", "fc@t.nl", FC), ("Bas", "bs@t.nl", BS),
                            ("Anker", "anker@t.nl", "mother_earth__circle_lead"),
                            ("Stefan", "stefan@nooch.earth", "mother_earth__nooch__shoe_developer"),
                            ("Lid", "lid@t.nl", "mother_earth__nooch__marketing_lead")):
        st.people.add(naam, mail)
        st.assign.assign(rol, "person", st.people.by_email(mail).id)
    critical_numbers.zaai(st.metrics, critical_numbers.laad(), apply=True)
    return dd


def _st(dd):
    return cockpit2._Stores(dd)


def _vul(dd, bunq=None, mollie=None, tax=None, payables=None, kosten=None, batches=()):
    """Zet de invoer van CN2 zoals de FC dat in het overleg en op /fixed-costs doet."""
    from nooch_village.productieverplichtingen import maak_regel as batch
    st = _st(dd)
    for cn, v in (("cn2_cash_bunq", bunq), ("cn2_cash_mollie", mollie), ("cn2_tax", tax),
                  ("cn2_payables", payables)):
        if v is not None:
            st.metrics.add_sample(st.metrics.by_cn(cn)["id"], v)
    if kosten is not None:
        st.vaste_kosten.zet(maak_regel("Huur", kosten, van="2026-01-01")[0])
    for b in batches:
        st.productieverplichtingen.zet(batch(*b)[0])


# ── vaste kosten ────────────────────────────────────────────────────────────

def test_een_regel_wordt_gevalideerd():
    # Sinds Finance PR 1 in centen (de terugkerende kosten); de oude CN2-vorm blijft voor de migratie.
    assert maak_regel("Huur", "1200,50", van="2026-01-01")[0]["amount_cents"] == 120050
    assert oude_maak_regel("Huur", "1200,50", van="2026-01-01")[0]["bedrag"] == 1200.5
    assert maak_regel("", "10", van="2026-01-01")[0] is None
    assert maak_regel("Huur", "veel", van="2026-01-01")[0] is None
    assert maak_regel("Huur", "10", van="")[0] is None
    assert maak_regel("Huur", "10", van="2026-05-01", tot="2026-04-01")[0] is None


def test_het_totaal_telt_alleen_wat_op_de_peildatum_loopt(tmp_path):
    st = _st(_dorp(tmp_path))
    for oms, b, van, tot in (("Huur", 1000, "2026-01-01", ""), ("Oude lease", 300, "2025-01-01", "2026-06-30"),
                             ("Nieuw abonnement", 50, "2026-11-01", "")):
        st.vaste_kosten.zet(maak_regel(oms, b, van=van, tot=tot)[0])
    assert st.vaste_kosten.totaal_op("2026-10-10") == 1000
    assert st.vaste_kosten.totaal_op("2026-06-30") == 1300                # einddatum telt nog mee
    assert st.vaste_kosten.totaal_op("2026-11-01") == 1050


# ── runway ──────────────────────────────────────────────────────────────────

def test_vrije_cash_is_cash_min_de_drie_verplichtingen(tmp_path):
    dd = _dorp(tmp_path)
    _vul(dd, bunq=30000, mollie=6000, tax=4000, payables=2000, kosten=1500,
         batches=[("Batch 3", 20000, 10000, "ordered")])               # nog 10.000 aan de fabriek
    r = runway(_st(dd))
    assert (r["cash"], r["verplichtingen"], r["vrije_cash"], r["maanden"]) == (36000.0, 100.0 * 100, 20000.0, 13.3)
    assert r["ontbreekt"] == []


def test_zonder_een_invoer_geen_runway_en_hij_zegt_welke(tmp_path):
    dd = _dorp(tmp_path)
    _vul(dd, bunq=30000, tax=0, kosten=1500)
    r = runway(_st(dd))
    assert r["maanden"] is None and r["vrije_cash"] is None
    assert r["ontbreekt"] == ["cash Mollie", "supplier payables"]
    _vul(dd, mollie=0, payables=0)
    assert runway(_st(dd))["maanden"] == 20.0                          # een nul is een antwoord


def test_geen_vaste_kosten_is_geen_runway(tmp_path):
    dd = _dorp(tmp_path)
    _vul(dd, bunq=1, mollie=1, tax=0, payables=0)
    r = runway(_st(dd))
    assert r["maanden"] is None and "fixed costs" in r["ontbreekt"]


def test_de_fabriek_50_bij_bestelling_50_bij_oplevering():
    from nooch_village.productieverplichtingen import maak_regel as batch, verplichting_cents
    assert verplichting_cents(batch("B4", 1000, 0, "open")[0]) == 100000      # nog niets besteld
    assert verplichting_cents(batch("B4", 1000, 500, "ordered")[0]) == 50000  # eerste helft betaald
    assert verplichting_cents(batch("B4", 1000, 1000, "delivered")[0]) == 0
    assert batch("B4", 1000, 1200, "ordered")[0] is None                       # meer betaald dan totaal
    assert batch("B4", "veel", 0, "open")[0] is None


@pytest.mark.parametrize("bunq,woord", [(19500 + 18000, "On target"), (19500 + 9000, "Close to target"),
                                        (19500 + 3000, "Off target")])
def test_de_grens_6_en_12_maanden(tmp_path, bunq, woord):
    """Vaste kosten 1.500/maand; verplichtingen 19.500 → vrije cash 18.000 / 9.000 / 3.000 =
    12 / 6 / 2 maanden."""
    dd = _dorp(tmp_path)
    _vul(dd, bunq=bunq, mollie=0, tax=12000, payables=7500, kosten=1500)
    st = _st(dd)
    h = render_metrics2_tab(st, st.records.get(C), "t", mset="critical")
    deel = h[h.index("Runway (months)"):]
    assert f">{woord}</span> target 12 · amber from 6" in deel


# ── zicht ───────────────────────────────────────────────────────────────────

def test_wie_mag_zien_en_wijzigen(tmp_path):
    st = _st(_dorp(tmp_path))
    rechten = {u: (zicht.mag(st, u, "finance"), zicht.mag(st, u, "finance", "wijzigen"))
               for u in ("fc@t.nl", "bs@t.nl", "stefan@nooch.earth", "anker@t.nl", "lid@t.nl",
                         "onbekend@t.nl", None, "guest")}
    # Sinds Finance PR 1 geen automatisch recht voor de anchor lead: Stefan staat er als PERSOON in.
    assert rechten == {"fc@t.nl": (True, True), "bs@t.nl": (True, False),
                       "stefan@nooch.earth": (True, True), "anker@t.nl": (False, False),
                       "lid@t.nl": (False, False), "onbekend@t.nl": (False, False),
                       None: (False, False), "guest": (True, True)}
    assert not zicht.mag(st, "fc@t.nl", "bestaat_niet")                   # onbekende groep: dicht


def test_een_lid_ziet_runway_en_cash_nergens(tmp_path):
    dd = _dorp(tmp_path)
    lid, fc = zicht.voor(_st(dd), "lid@t.nl"), zicht.voor(_st(dd), "fc@t.nl")
    rec = lid.records.get(C)
    h_lid = render_metrics2_tab(lid, rec, "t", mset="all")
    h_fc = render_metrics2_tab(fc, rec, "t", mset="all")
    for woord in ("Runway (months)", "Cash and cash equivalents", "Fixed costs per month"):
        assert woord not in h_lid, woord
        assert woord in h_fc, woord
    assert "Substantiated pages" in h_lid                                 # de rest blijft open
    assert not any(s["id"] == "runway" for s in _sources_for(lid, rec))
    cash = lid.metrics._m.by_cn("cn2_cash_bunq")["id"]
    assert lid.metrics.get(cash) is None and fc.metrics.get(cash) is not None


def test_in_het_werkoverleg_alleen_voor_wie_mag(tmp_path):
    dd = _dorp(tmp_path)
    for wie, ziet in (("lid@t.nl", False), ("bs@t.nl", True), ("fc@t.nl", True)):
        st = zicht.voor(_st(dd), wie)
        assert ("Cash and cash equivalents" in _wo_metrics(st, st.records.get(C), "t")) is ziet, wie


def test_cash_invoeren_alleen_fc_en_anker(tmp_path):
    dd = _dorp(tmp_path)
    mid = _st(dd).metrics.by_cn("cn2_cash_bunq")["id"]
    for wie, mag in (("lid@t.nl", False), ("bs@t.nl", False), ("fc@t.nl", True),
                     ("stefan@nooch.earth", True)):
        _n, msg = cockpit2.dispatch(dd, "m_sample", {"mid": [mid], "value": ["1000"], "next": ["/"]},
                                    username=wie)
        assert ("✓" in msg) is mag, (wie, msg)
    s = _st(dd).metrics.get(mid)["samples"]
    assert len(s) == 2 and s[0]["door"] == _st(dd).people.by_email("fc@t.nl").id


def test_vaste_kosten_wijzigen_alleen_fc_en_anker(tmp_path):
    dd = _dorp(tmp_path)
    form = {"omschrijving": ["Huur"], "bedrag": ["1000"], "van": ["2026-01-01"], "next": ["/fixed-costs"]}
    for wie in ("lid@t.nl", "bs@t.nl"):
        with pytest.raises(cockpit2.NietGevonden):                # Finance: 404, niet verraden
            cockpit2.dispatch(dd, "vaste_kosten_zet", form, username=wie)
    assert "✓" in cockpit2.dispatch(dd, "vaste_kosten_zet", form, username="fc@t.nl")[1]
    assert _st(dd).vaste_kosten.totaal_op("2026-10-10") == 1000


def test_de_pagina_vaste_kosten_per_rol(tmp_path):
    dd = _dorp(tmp_path)
    _st(dd).vaste_kosten.zet(maak_regel("Huur", 1234, van="2026-01-01")[0])
    lid = render_vaste_kosten(_st(dd), "lid@t.nl", "t")
    assert "1,234" not in lid and "404" in lid                          # niet verraden
    bs = render_vaste_kosten(_st(dd), "bs@t.nl", "t")
    assert "€1,234.00" in bs and "verplichting_zet" not in bs           # zien, niet wijzigen
    fc = render_vaste_kosten(_st(dd), "fc@t.nl", "t")
    assert "verplichting_zet" in fc and "/finance/recurring" in fc


def test_het_zaad_maakt_de_vijf_onderdelen(tmp_path):
    st = _st(_dorp(tmp_path))
    tiles = {t["cn"]: t for t in st.metrics.tiles_of(C) if t.get("cn")}
    r = tiles["cn2_runway"]
    assert (r["niveau"], r["target"], r["oranje"], r["zicht"]) == ("critical", 12.0, 6.0, "finance")
    for cn, measure in (("cn2_cash", "cash"), ("cn2_free_cash", "vrije_cash"),
                        ("cn2_commitments", "verplichtingen"), ("cn2_tax_liabilities", "belasting"),
                        ("cn2_supplier_payables", "crediteuren"), ("cn2_fixed_costs", "vaste_kosten")):
        assert (tiles[cn]["source"], tiles[cn]["measure"], tiles[cn]["zicht"]) == ("runway", measure, "finance")
    for cn in ("cn2_cash_bunq", "cn2_cash_mollie", "cn2_tax", "cn2_payables"):
        assert st.metrics.by_cn(cn)["zicht"] == "finance"
    assert sum(1 for t in tiles.values() if t.get("niveau") == "critical") <= 3


def test_de_cash_kpi_van_prod_wordt_bunq_en_de_tegel_wordt_de_som(tmp_path):
    """Op prod staan sinds #702 een KPI `cn2_cash` en een tegel die hem toont. Bouw ze uit: dezelfde
    KPI wordt de bunq-rekening (met zijn metingen), de tegel toont de som. Niets dubbel."""
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = _st(dd)
    oude_kpi = st.metrics.add_kpi(C, "Cash and cash equivalents", "EUR")
    st.metrics.set_item_extra(oude_kpi["id"], cn="cn2_cash", zicht="finance")
    st.metrics.add_sample(oude_kpi["id"], 777)
    st.metrics.add_tile(C, f"kpi:{oude_kpi['id']}", "value", "none", "getal",
                        extra={"cn": "cn2_cash", "zicht": "finance"})
    st = _st(dd)
    rapport = {r["sleutel"]: r["actie"] for r in critical_numbers.zaai(st.metrics, critical_numbers.laad(), apply=True)}
    assert rapport["cn2_cash_bunq"] == "update" and rapport["cn2_cash"] == "update"
    st = _st(dd)
    bunq = st.metrics.by_cn("cn2_cash_bunq")
    assert bunq["id"] == oude_kpi["id"] and bunq["name"] == "Cash — bunq" and bunq["samples"][0]["value"] == 777
    cash_tegels = [t for t in st.metrics.tiles_of(C) if t.get("cn") == "cn2_cash"]
    assert len(cash_tegels) == 1 and (cash_tegels[0]["source"], cash_tegels[0]["measure"]) == ("runway", "cash")
    st = _st(dd)
    assert {r["actie"] for r in critical_numbers.zaai(st.metrics, critical_numbers.laad(), apply=True)} == {"ongewijzigd"}


def test_verplichtingen_wijzigen_alleen_fc_en_anker(tmp_path):
    dd = _dorp(tmp_path)
    form = {"batch": ["Batch 4"], "totaal": ["20000"], "betaald": ["10000"], "status": ["ordered"],
            "next": ["/fixed-costs"]}
    for wie in ("lid@t.nl", "bs@t.nl"):
        with pytest.raises(cockpit2.NietGevonden):
            cockpit2.dispatch(dd, "verplichting_zet", form, username=wie)
    assert "✓" in cockpit2.dispatch(dd, "verplichting_zet", form, username="fc@t.nl")[1]
    assert _st(dd).productieverplichtingen.totaal_cents() == 1000000


def test_de_invoerpagina_toont_alle_onderdelen(tmp_path):
    dd = _dorp(tmp_path)
    h = render_vaste_kosten(_st(dd), "fc@t.nl", "t")
    for kop in ("Runway inputs", "Cash — bunq", "Cash — Mollie", "Tax liabilities", "Supplier payables",
                "Production commitments (open batches)", "Fixed costs per month", "missing: cash bunq"):
        assert kop in h, kop
    assert "value='m_sample'" in h and "verplichting_zet" in h and "/finance/costs" in h


# ── de routes gebruiken de kijker-versie ────────────────────────────────────

def test_de_routes_schermen_af_voor_een_lid(tmp_path):
    """De echte handler: een ingelogd lid ziet de runway op geen enkele metrics-route, de FC wel."""
    import http.client
    import threading
    from http.server import HTTPServer
    from nooch_village import auth as _auth

    dd = _dorp(tmp_path)
    mid = _st(dd).metrics.by_cn("cn2_cash_bunq")["id"]
    _st(dd).metrics.add_sample(mid, 4321)
    sessies = _auth.SessionStore()
    httpd = HTTPServer(("127.0.0.1", 0), cockpit2.make_handler(dd, "T", sessions=sessies))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    poort = httpd.server_address[1]

    def get(pad, wie):
        conn = http.client.HTTPConnection("127.0.0.1", poort, timeout=10)
        conn.request("GET", pad, headers={"Cookie": f"nv_session={sessies.create(wie)}"})
        r = conn.getresponse()
        body = r.read().decode("utf-8", "replace")
        conn.close()
        return body

    try:
        for pad in (f"/node?id={C}&tab=metrics&mset=all", f"/metrics2?node={C}&mset=all",
                    f"/werkoverleg?circle={C}&step=metrics"):
            assert "Runway (months)" not in get(pad, "lid@t.nl"), pad
        assert "Runway (months)" in get(f"/node?id={C}&tab=metrics&mset=all", "fc@t.nl")
        assert "4321" not in get(f"/metric_export?mid={mid}", "lid@t.nl")
        assert "4321" in get(f"/metric_export?mid={mid}", "fc@t.nl")
    finally:
        httpd.shutdown()
