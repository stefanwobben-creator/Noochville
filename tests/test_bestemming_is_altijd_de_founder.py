"""De drie plekken waar een model de bestemming koos, en nu niet meer.

Besluit van Stefan, 20 september 2026: *"niet de ladder, altijd naar mij direct. Ik wil eerst alles
zelf zien voordat het verder gaat."* Bewust NIET de ladder vervuller → Circle Lead → founder die
`signaal.ontvangers` hanteert — die verdeelt, en hier wordt niet verdeeld.

`test_geen_model_routering` is de brede ratchet: hij vangt de VORM (een orakel-uitkomst die in een
bezorger belandt) waar hij ook opduikt, maar hij volgt geen dicts, attributen of callbacks. Deze
drie tests pinnen het GEDRAG van de plekken die we kennen, met een model dat expres een andere rol
probeert aan te wijzen. Zonder dat paar is "het model beslist niet" een belofte: de ratchet ziet niet
alles, en een gedragstest zonder ratchet dekt alleen wat je al bedacht had.
"""
from __future__ import annotations

import time

from nooch_village import cockpit2, signaal

CIRKEL = "mother_earth__nooch"
ANDERE_ROL = "mother_earth__nooch__creator_of_shoes"


def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def _founder(st) -> str:
    """De persoon die de terugval-rol vervult — dat is Stefan in het zaad."""
    return signaal.terugval(st)


# ── 1. de laatste meter ─────────────────────────────────────────────────────

def test_mens_ontvanger_negeert_de_rol_die_het_model_aanwijst(tmp_path):
    """Het model krijgt hier alle ruimte: het noemt met stelligheid een BESTAANDE, mens-vervulde
    rol. Vroeger landde het werk dan op het bord van die collega. Nu is het een voorstel."""
    from nooch_village.escalation_router import _mens_ontvanger

    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    stefan = _founder(st)
    assert stefan, "zonder founder-persoon toetst deze test niets"

    def _model(prompt, **kw):
        return '{"role": "%s", "kind": "missing_capability"}' % ANDERE_ROL

    rol, persoon, grond, suggestie = _mens_ontvanger(
        st, {"id": "p1", "scope": "een doel"}, "Beslis of we deze overlap uitsluiten",
        "mother_earth__nooch__website_developer", [], _model)

    assert persoon == stefan, "de bestemming hoort de founder te zijn, wat het model ook zegt"
    assert rol == "", "er wordt geen ROL meer aangewezen"
    assert "bij jou" in grond
    # En het oordeel is niet weggegooid — het reist mee als voorstel, in mensentaal.
    assert suggestie.startswith("voorstel:") and "Creator of Shoes" in suggestie


def test_zonder_model_gaat_het_bericht_naar_dezelfde_mens(tmp_path):
    """DE STILLE FOUT VAN DE OUDE VERSIE: geen modelantwoord betekende een ANDERE ontvanger
    (opdrachtgever, anders de founder). Wegvallend krediet mag nooit de bestemming verzetten."""
    from nooch_village.escalation_router import _mens_ontvanger

    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)

    def _stuk(prompt, **kw):
        raise RuntimeError("geen krediet")

    rol, persoon, grond, suggestie = _mens_ontvanger(
        st, {"id": "p1", "scope": "x", "opdrachtgever": "iemand-anders"}, "een vastgelopen stap",
        "mother_earth__nooch__website_developer", [], _stuk)
    assert persoon == _founder(st) and rol == ""
    assert suggestie == "", "geen model = geen voorstel, maar wel hetzelfde adres"


# ── 2. werk bij een rol die niets meer kan ──────────────────────────────────

def test_een_rol_zonder_vervuller_en_zonder_lead_valt_terug_op_de_founder(tmp_path):
    """Gemeten op prod, 20 september 2026: de `compliance`-rol was opgeheven én zijn hele cirkel,
    dus `_circle_lead_van` vond niets en `bestemming` gaf de rol zélf terug — de rol die net was
    vastgesteld als "kan niets". `village afslank_wezen` stelde daardoor voor twee weesprojecten te
    "verhuizen" naar diezelfde dode rol: een lus die alleen het origineel archiveert."""
    dd = _dd(tmp_path)
    st = cockpit2._Stores(dd)
    # Een rol zonder mens, zonder AI, en zonder Circle Lead boven zich.
    rec = st.records.get(ANDERE_ROL)
    assert rec is not None
    for f in list(st.assign.fillers_of(ANDERE_ROL, record=rec)):
        st.assign.unassign(ANDERE_ROL, f.type, f.id)
    st2 = cockpit2._Stores(dd)
    # De Circle Lead van de omvattende cirkel weghalen, zodat de klim doodloopt.
    lead = cockpit2._circle_lead_van(st2, ANDERE_ROL)
    if lead:
        rec_lead = st2.records.get(lead)
        for f in list(st2.assign.fillers_of(lead, record=rec_lead)):
            st2.assign.unassign(lead, f.type, f.id)
        rec_lead.archived = True                 # zelfde weg als REMOVE_ROLE in de Secretary
        st2.records.put(rec_lead)
    st3 = cockpit2._Stores(dd)

    best = cockpit2.bestemming(st3, rol=ANDERE_ROL)
    assert best["doel_type"] == "person", f"viel terug op {best}"
    assert best["doel_id"] == _founder(st3)
    assert "geen Circle Lead" in (best.get("via") or "")


# ── 3. de sluitronde ────────────────────────────────────────────────────────

def test_het_panel_maakt_geen_project_meer():
    """Het panel mag JA zeggen, een trekker noemen en een scope schrijven. Wat het niet meer mag is
    dat die JA zichzelf uitvoert: vroeger werd dit een `pj.create` op de rol die het model koos."""
    from nooch_village import sluitronde as SR

    def _panel(prompt, **kw):
        return ('{"stemmen":[{"rol":"a","stem":"ja","reden":"past"}],"besluit":"ja",'
                '"onomkeerbaar":false,"waarde":5,"reden":"cruciaal voor de purpose",'
                '"owner_rol":"%s","scope":"De FAQ staat compliant online"}' % ANDERE_ROL)

    b = SR.beslis_kans({"id": "k1", "created_at": time.time(),
                        "context": {"title": "Iets volstrekt nieuws"}},
                       [{"id": "a", "naam": "A", "purpose": "p"}], [],
                       reason_fn=_panel, now=time.time())
    assert b["actie"] == "escaleer", f"het panel besliste alsnog zelf: {b}"
    # Het oordeel blijft compleet zichtbaar — dat is waar het panel voor bestaat.
    assert b["advies"] == "het panel zegt JA"
    assert b["voorgestelde_rol"] == ANDERE_ROL      # als TEKST, niet als adres
    assert b["scope"] == "De FAQ staat compliant online"
    assert b["waarde"] == 5 and b["stemmen"]
    assert "naar jou" in b["reden"]


def test_een_nee_van_het_panel_verdwijnt_niet_stil():
    """De andere helft, en de ergste: een NEE sloot de kans af (`inbox.resolve(rejected)`) en dan
    zag de mens hem nooit. Ook dat oordeel komt nu eerst langs."""
    from nooch_village import sluitronde as SR

    def _panel(prompt, **kw):
        return ('{"stemmen":[],"besluit":"nee","onomkeerbaar":false,"waarde":1,'
                '"reden":"buiten de purpose"}')

    b = SR.beslis_kans({"id": "k1", "created_at": time.time(),
                        "context": {"title": "Iets volstrekt nieuws"}},
                       [{"id": "a", "naam": "A", "purpose": "p"}], [],
                       reason_fn=_panel, now=time.time())
    assert b["actie"] == "escaleer"
    assert b["advies"] == "het panel zegt NEE" and "buiten de purpose" in b["reden"]


def test_de_deterministische_takken_beslissen_nog_wel():
    """Geen model, geen oordeel: leeftijd en scope-overlap zijn REGELS. Ze staan in de code, zijn na
    te rekenen en verschijnen in het rapport — die mogen blijven beslissen."""
    from nooch_village import sluitronde as SR

    def _nooit(prompt, **kw):                       # het panel mag hier niet eens aan bod komen
        raise AssertionError("het model werd aangeroepen voor een deterministische tak")

    oud = SR.beslis_kans({"id": "k1", "created_at": time.time() - 99 * 86400,
                          "context": {"title": "Oude kans"}},
                         [], [], reason_fn=_nooit, now=time.time(), ttl_days=14)
    assert oud["actie"] == "verlopen"

    dubbel = SR.beslis_kans({"id": "k2", "created_at": time.time(),
                             "context": {"title": "De FAQ pagina compliant maken"}},
                            [], ["De FAQ pagina compliant maken"],
                            reason_fn=_nooit, now=time.time())
    assert dubbel["actie"] == "nee" and "al gedekt" in dubbel["reden"]
