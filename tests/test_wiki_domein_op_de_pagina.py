"""Het domein van een note is op zijn eigen permalink te zetten (24 september 2026).

WAAROM DIT APART MOEST. `_artefact_edit_form` kreeg het domein-veld, maar die vorm wordt alleen
voor een policy en een tool gerenderd: een note wordt sinds #567 op zijn permalink bewerkt, met de
blok-editor. Dat is 105 van de 121 artefacten, dus zonder dit stuk kon je de bulk van de wiki niet
verplaatsen.

WAAROM EEN EIGEN FORMULIERTJE EN GEEN VELD IN DE BLOK-EDITOR. De opslaan-balk van `wiki-form`
verschijnt pas als je "Edit page" hebt geklikt. Een keuzelijst die altijd zichtbaar is maar pas
opslaat als je toevallig in bewerkmodus staat, is een val: je verandert iets en er gebeurt niets.
Een eigen formulier in de kopbalk werkt altijd, raakt de blok-editor niet aan, en gebruikt
DEZELFDE actie (`artefact_edit`) met dezelfde server-side poort — dus geen tweede schrijfpad en
geen tweede validatie.

Dat `_act_artefact_edit` een formulier met alleen een domein aankan, is geen toeval: `title`,
`body` en `url` zijn daar allemaal optioneel (`… if "x" in form else None`), en `update()` laat
een veld dat `None` is met rust.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views.wiki import render_pagina


def _dorp(tmp_path, domains=("Materials", "Decision Making"), can_edit=True):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    rec = st.records.get(rol)
    rec.definition.domains = list(domains)
    st.records.put(rec)
    mens = st.people.add("Beheerder", "b@t.nl")
    if can_edit:
        st.assign.assign(rol, "person", mens.id)
    return dd, st, rol


def _pagina(st, a, can_edit=True):
    return render_pagina(st, a.id, csrf_token="TOK",
                         username="b@t.nl" if can_edit else "")


# ── 1. Het veld staat in de kopbalk ──────────────────────────────────────────
def test_de_note_pagina_toont_een_domein_keuze(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Een pagina", body="tekst", domain="Materials")
    html = _pagina(st, a)
    assert "name='domain'" in html
    assert "value='Materials' selected" in html


def test_het_veld_staat_buiten_de_bewerkbare_tekst(tmp_path):
    """NIET BINNEN `#wiki-body`, want alles daarbinnen gaat bij het opslaan mee als `body_html`.

    DE EIS WAS OOK "BOVEN DE TEKST", en dat is hij niet meer. Het veld verhuisde met #602 naar het
    metadata-blok, en dat blok staat sinds 26 september ONDER de inhoud — de administratie kreeg
    daarvóór de plek van het onderwerp. Wat overblijft is de eis die er altijd de echte was: het
    veld mag niet in het bewerkbare vlak zitten. Boven of onder is een ontwerpkeuze; erbinnen is
    dataverlies.

    OP HET ELEMENT EN NIET OP DE REST VAN DE PAGINA. "Alles ná `id='wiki-body'`" was hetzelfde
    meetpunt zolang er niets meer onder stond; nu telt dat het metadata-blok mee, en dan meet de
    toets precies het tegenovergestelde van wat hij bedoelt. Het sjabloon van het blokmenu staat
    direct achter het bewerkvlak en is dus de grens."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Een pagina", body="tekst", domain="Materials")
    html = _pagina(st, a)
    assert "name='domain'" in html
    binnen = html.split("id='wiki-body'")[1].split("id='wb-menu-sjabloon'")[0]
    assert "name='domain'" not in binnen, "het veld zit ín de bewerkbare tekst"


def test_het_is_een_eigen_formulier_naast_de_blok_editor(tmp_path):
    """Eén actie, twee formulieren: het domein-formulier en `wiki-form` sturen allebei
    `artefact_edit`, maar ze raken elkaar niet. Zou het veld ín `wiki-form` zitten, dan kon je het
    alleen opslaan in bewerkmodus."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Een pagina", body="tekst", domain="Materials")
    html = _pagina(st, a)
    assert html.count("value='artefact_edit'") == 2
    # OP DE TWEE FORMULIEREN, niet op hun volgorde. Dit was "het domein staat vóór `wiki-form`",
    # en dat mat de plek in plaats van de scheiding: sinds het metadata-blok onderaan staat
    # (26 september) staat het domein er ná, en is het nog precies zo'n eigen formulier.
    in_editor = html.split("id='wiki-form'")[1].split("</form>")[0]
    assert "name='domain'" not in in_editor, \
        "het domeinveld zit ín wiki-form — dan is het alleen in bewerkmodus op te slaan"


def test_wie_niet_mag_bewerken_krijgt_geen_keuze(tmp_path):
    """Dezelfde regel als bij de bewerkknop: de poort staat vóór de belofte."""
    dd, st, rol = _dorp(tmp_path, can_edit=False)
    a = st.att.add(rol, "note", title="Een pagina", body="tekst", domain="Materials")
    html = _pagina(st, a, can_edit=False)
    assert "name='domain'" not in html


def test_een_rol_zonder_domein_krijgt_uitleg(tmp_path):
    dd, st, rol = _dorp(tmp_path, domains=[])
    a = st.att.add(rol, "note", title="Een pagina", body="tekst")
    html = _pagina(st, a)
    assert "no domain yet" in html
    # OP HET DOMEIN-VELD, niet op "staat er ergens een <select>": het feiten-formulier op deze
    # pagina heeft er zelf ook een, dus de brede versie van deze assert mat de buurman.
    assert "name='domain'" not in html


def test_een_policy_pagina_krijgt_het_veld_niet(tmp_path):
    """Die wordt bij de eigenaar-rol bewerkt, mét domein-veld (#585). Twee plekken voor dezelfde
    keuze is precies wat de leespagina van #574 vermijdt.

    LET OP WAT HIER BEWIJST WAT. Deze toets slaagt doordat `render_pagina` een policy sinds #574
    naar `_artefact_pagina` stuurt — een andere renderer, die `_domein_form` nooit aanroept. Niet
    door de soort-guard in die functie; die meet de toets hieronder. Een mutatie op de guard liet
    déze toets groen, en dat is precies het verschil."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "policy", title="Beleid", body="tekst", domain="Materials")
    assert "name='domain'" not in _pagina(st, a)


def test_de_functie_weigert_zelf_ook_een_niet_note(tmp_path):
    """De guard in `_domein_form` is vandaag onbereikbaar via `render_pagina` (zie hierboven),
    maar hij is er voor de dag dat iemand hem ergens anders aanroept. Zonder deze toets staat er
    een verdediging die niemand ooit meet."""
    from nooch_village.views.wiki import _domein_form
    dd, st, rol = _dorp(tmp_path)
    eigenaar = st.records.get(rol)
    for kind, extra in (("policy", {}), ("tool", {"url": "/x"})):
        a = st.att.add(rol, kind, title="X", domain="Materials", **extra)
        assert _domein_form(a, eigenaar, "TOK", True) == "", f"{kind} kreeg toch een veld"
    note = st.att.add(rol, "note", title="X", domain="Materials")
    assert "name='domain'" in _domein_form(note, eigenaar, "TOK", True)


# ── 2. Opslaan loopt door dezelfde poort ─────────────────────────────────────
def _bewerk(st, dd, a, **velden):
    form = {"aid": a.id, "csrf": "TOK", **velden}
    c = type("C", (), {"nxt": "/x", "st": st, "form": form, "username": "guest",
                       "action": "artefact_edit", "data_dir": dd})()
    c.g = lambda k, d="": form.get(k, d)
    return cockpit2._act_artefact_edit(c)


def test_alleen_een_domein_opsturen_laat_de_tekst_met_rust(tmp_path):
    """`title`, `body` en `url` zijn optioneel in de actie, en `update()` laat een veld dat None
    is met rust. Daarom kan dit formulier met één veld toe."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Titel blijft", body="tekst blijft", domain="Materials")
    _bewerk(st, dd, a, domain="Decision Making", next="/pagina?id=" + a.id)
    na = st.att.get(a.id)
    assert na.domain == "Decision Making"
    assert na.title == "Titel blijft" and na.body == "tekst blijft"


def test_een_domein_dat_de_rol_niet_bezit_wordt_ook_hier_geweigerd(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="X", body="y", domain="Materials")
    _, msg = _bewerk(st, dd, a, domain="Verzonnen")
    assert "✗" in msg
    assert st.att.get(a.id).domain == "Materials"


def test_het_blokmodel_blijft_ongemoeid(tmp_path):
    """De blok-editor mag hier niets van merken: zelfde soortentabel, zelfde bewerkbare body."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="X", body="### Kop\n\ntekst", domain="Materials")
    html = _pagina(st, a)
    assert "data-blok-soorten" in html
    assert "id='wiki-body'" in html
    assert "data-blok='h'" in html
