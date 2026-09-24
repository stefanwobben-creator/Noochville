"""Het domein is ook ná het aanmaken te kiezen (24 september 2026).

WAT ER ONTBRAK. Sinds brok 2 mag elk artefact een domein dragen, en `domeinen.bakje_van` leest dat
als eerste stap — het is de nauwkeurigste bron die er is. Maar je kon het alleen bij het AANMAKEN
zetten, en dan alleen op een policy. Een artefact verplaatsen vroeg dus een commando of een
handmatige ingreep in de data.

DEZELFDE POORT ALS BIJ AANMAKEN, en dat is geen nettigheid maar noodzaak: `domain` bepaalt waar
latere bewerkingen tegen gelogd worden (`gref`). Een vrij tekstveld zou betekenen dat iemand zijn
artefact onder een domein kan hangen dat de rol niet bezit, en dan wijst de audittrail naar iets
wat governance nooit heeft toegewezen. Server-side toetsen tegen `definition.domains`, net als
`_act_artefact_add` al doet.

HET VELD MOET AFWEZIG KUNNEN ZIJN. `_act_artefact_edit` bedient TWEE formulieren: dat van de
rol-tab (stuurt `body`) en de inline editor van de wiki-pagina (stuurt `body_html`). Dat tweede
formulier kent geen domein-veld. Ontbreekt het veld, dan blijft het domein staan — anders wist
elke note-bewerking stilletjes zijn eigen indeling.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views.overview import _artefact_edit_form, _domain_field


def _dorp(tmp_path, domains=("Materials",)):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    rec = st.records.get(rol)
    rec.definition.domains = list(domains)
    st.records.put(rec)
    return dd, st, rol


# ── 1. Het veld op het formulier ─────────────────────────────────────────────
def test_het_bewerk_formulier_toont_het_domein_voor_elke_soort(tmp_path):
    dd, st, rol = _dorp(tmp_path, ["Materials", "Decision Making"])
    for kind in ("policy", "tool", "note"):
        a = st.att.add(rol, kind, title="X", domain="Materials")
        html = _artefact_edit_form(a, "TOK", domains=["Materials", "Decision Making"])
        assert "name='domain'" in html, f"geen domein-veld op een {kind}"


def test_het_huidige_domein_staat_voorgeselecteerd(tmp_path):
    """Zonder voorselectie zet elke bewerking het artefact terug op het eerste domein in de lijst
    — een stille verplaatsing bij een wijziging die er niets mee te maken had."""
    dd, st, rol = _dorp(tmp_path, ["Materials", "Decision Making"])
    a = st.att.add(rol, "policy", title="X", domain="Decision Making")
    html = _artefact_edit_form(a, "TOK", domains=["Materials", "Decision Making"])
    assert "value='Decision Making' selected" in html


def test_een_rol_met_een_domein_krijgt_geen_keuzelijst(tmp_path):
    """Zelfde vorm als op het aanmaakformulier: één domein is geen keuze."""
    dd, st, rol = _dorp(tmp_path, ["Materials"])
    a = st.att.add(rol, "tool", title="X", url="/x")
    html = _artefact_edit_form(a, "TOK", domains=["Materials"])
    assert "<select" not in html
    assert "name='domain'" in html and "Materials" in html


def test_een_rol_zonder_domein_krijgt_uitleg_en_geen_veld(tmp_path):
    """DE VAL DIE `_domain_field` ZELF NIET VANGT: met een lege lijst rendert hij een `<select>`
    zonder opties — een keuzelijst waar niets in staat. De aanroeper hoort dat af te vangen, en
    dat doet het aanmaakformulier al."""
    assert "<select" in _domain_field([])          # dit is waarom de aanroeper moet ingrijpen
    dd, st, rol = _dorp(tmp_path, [])
    a = st.att.add(rol, "policy", title="X")
    html = _artefact_edit_form(a, "TOK", domains=[])
    assert "<select" not in html
    assert "no domain yet" in html


def test_zonder_domeinlijst_verandert_het_formulier_niet(tmp_path):
    """Oude aanroepers (en de wiki-pagina) geven geen domeinen mee; die horen hetzelfde formulier
    te krijgen als voorheen.

    ER STOND HIER ALLEEN "geen `name='domain'`", en dat was te weinig: een mutatie die `None` en
    `[]` op één hoop gooide liet de UITLEG-tekst verschijnen bij elke oude aanroeper, en die toets
    bleef groen. Niets extra's betekent ook geen uitleg."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "policy", title="X", domain="Materials")
    html = _artefact_edit_form(a, "TOK")
    assert "name='domain'" not in html
    assert "no domain yet" not in html
    assert "Domain" not in html


# ── 2. De poort bij het opslaan ──────────────────────────────────────────────
def _bewerk(st, dd, a, **velden):
    """Eén `artefact_edit`-actie, zoals de cockpit hem aanroept."""
    # `username="guest"` = de auth-uit-stand, die `_artefact_gate` doorlaat. Met None is het
    # "ingelogd maar onbekend" en dat wordt terecht geweigerd — de poort stond hier dus vóór de
    # code die deze toets wil meten.
    form = {"aid": a.id, "csrf": "TOK", **velden}
    c = type("C", (), {"nxt": "/x", "st": st, "form": form, "username": "guest",
                       "action": "artefact_edit", "data_dir": dd})()
    c.g = lambda k, d="": form.get(k, d)
    return cockpit2._act_artefact_edit(c)


def test_een_geldig_domein_wordt_gezet(tmp_path):
    dd, st, rol = _dorp(tmp_path, ["Materials", "Decision Making"])
    a = st.att.add(rol, "policy", title="X", domain="Materials")
    _bewerk(st, dd, a, title="X", body="tekst", domain="Decision Making")
    assert st.att.get(a.id).domain == "Decision Making"


def test_een_domein_dat_de_rol_niet_bezit_wordt_geweigerd(tmp_path):
    """Zelfde poort als bij aanmaken. `domain` bepaalt waar latere bewerkingen tegen gelogd
    worden; een vrij veld zou de audittrail naar iets laten wijzen dat governance nooit
    toewees."""
    dd, st, rol = _dorp(tmp_path, ["Materials"])
    a = st.att.add(rol, "policy", title="X", domain="Materials")
    _, msg = _bewerk(st, dd, a, title="X", body="tekst", domain="Verzonnen Domein")
    assert "✗" in msg
    assert st.att.get(a.id).domain == "Materials", "het domein is toch veranderd"


def test_een_ontbrekend_veld_laat_het_domein_staan(tmp_path):
    """DE WIKI-PAGINA STUURT GEEN DOMEIN. Zou een ontbrekend veld als "leeg" gelden, dan wist
    elke note-bewerking stilletjes zijn eigen indeling."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="X", domain="Materials")
    _bewerk(st, dd, a, body_html="<p>nieuwe tekst</p>")
    assert st.att.get(a.id).domain == "Materials"


def test_een_leeg_domein_haalt_de_indeling_weg(tmp_path):
    """Expliciet leeg is iets anders dan afwezig: zo kun je een artefact terugzetten naar de
    afleiding via zijn rol."""
    dd, st, rol = _dorp(tmp_path, ["Materials"])
    a = st.att.add(rol, "policy", title="X", domain="Materials")
    _bewerk(st, dd, a, title="X", body="tekst", domain="")
    assert st.att.get(a.id).domain == ""


# ── 3. Policies blijven zich gedragen zoals ze deden ─────────────────────────
def test_een_policy_bewerken_zonder_domein_te_raken_verandert_niets(tmp_path):
    dd, st, rol = _dorp(tmp_path, ["Materials"])
    a = st.att.add(rol, "policy", title="Oud", domain="Materials")
    _bewerk(st, dd, a, title="Nieuw", body="andere tekst", domain="Materials")
    na = st.att.get(a.id)
    assert na.domain == "Materials" and na.title == "Nieuw" and na.body == "andere tekst"


def test_het_id_van_een_policy_verandert_niet_door_een_verplaatsing(tmp_path):
    """Het id is gemunt bij het AANMAKEN (`{DOMEINSLUG}-{NNN}`). Verplaatsen mag daar niet aan
    zitten: een id is een permalink, en die hoort niet te verschuiven omdat de indeling wijzigt."""
    dd, st, rol = _dorp(tmp_path, ["Materials", "Decision Making"])
    a = st.att.add(rol, "policy", title="X", domain="Materials")
    oud_id = a.id
    _bewerk(st, dd, a, title="X", body="tekst", domain="Decision Making")
    assert st.att.get(oud_id) is not None
    assert st.att.get(oud_id).id == oud_id


def test_de_versiehistorie_houdt_een_bewerking_op_een_entry(tmp_path):
    """Eén save-actie is één change_note (besluit 20 september 2026). Het domein meenemen mag daar
    geen tweede entry bij maken."""
    dd, st, rol = _dorp(tmp_path, ["Materials", "Decision Making"])
    a = st.att.add(rol, "policy", title="X", domain="Materials")
    voor = len(st.att.get(a.id).versions)
    _bewerk(st, dd, a, title="X", body="andere tekst", domain="Decision Making")
    assert len(st.att.get(a.id).versions) == voor + 1
