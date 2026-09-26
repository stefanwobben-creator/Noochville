"""Echte afbeeldingen, uploaden via het blokmenu, en opruimen (26 september 2026).

Vier punten uit `claude/ontwerp_blokkensysteem_media_en_sleep_26sept.md`. Drie ervan zijn gebouwd;
het vierde — slepen — bleek AL GEBOUWD te zijn (#599), en dat legt `test_slepen_bestaat_al`
hieronder vast zodat niemand er een tweede mechanisme naast zet.

Stefans eis: een pagina moet tekst, een feit, een afbeelding, meer tekst, meer feiten en een link
in elke volgorde kunnen dragen. Punt 1 en 2 gaan over het beeld, punt 4 over het opruimen dat hij
daarna wil kunnen doen ("bijna alles wat er nu in staat kan weg").
"""
from __future__ import annotations

import inspect
import pathlib
import re

from conftest import js_zonder_uitleg
from nooch_village import channels, cockpit2, wiki
from nooch_village.cockpit2_util import (BLOK_MENU, _accept, _is_beeldbestand, _md,
                                         _md_naar_bron, blok_menu)
from nooch_village.views.wiki import render_pagina

CSS = (pathlib.Path(__file__).resolve().parents[1]
       / "nooch_village" / "static" / "nooch.css").read_text()
NU = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch-ui.css").read_text()
JS = (pathlib.Path(__file__).resolve().parents[1]
      / "nooch_village" / "static" / "nooch.js").read_text()

#: DE VOLGORDE UIT HET ONTWERPDOCUMENT, letterlijk: tekst → feit → afbeelding → tekst → tekst →
#: drie feiten → link. "Drie feiten" is één `{{facts}}`-blok met drie feiten erin; de markering
#: plaatst de sectie, de sectie draagt de rijen.
GEMENGD = ("Een pagina begint met gewone tekst.\n\n"
           "{{facts}}\n\n"
           "![Een schoen op de leest](/wiki-bestand/<AID>/ab12cd34_schoen.png)\n\n"
           "Tekst onder de afbeelding, want dat is de overgang die moet kloppen.\n\n"
           "En nog een alinea erachteraan.\n\n"
           "{{backlinks}}\n\n"
           "[De leveranciersbrief](/wiki-bestand/<AID>/ef56gh78_brief.pdf)\n")


def _dorp(tmp_path, body: str | None = None):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    rol = st.records.all()[0].id
    mens = st.people.add("Beheerder", "b@t.nl")
    st.assign.assign(rol, "person", mens.id)
    a = st.att.add(rol, "note", title="Gemengde pagina", body="tijdelijk")
    # `.replace` EN NIET `.format`: de body draagt `{{facts}}`, en `str.format` maakt daar
    # `{facts}` van — dan staat de markering er niet meer en valt de sectie stil naar onderaan.
    # Gevonden doordat `test_de_gemengde_pagina_leest_als_een_pagina` geen `facts`-blok zag.
    st.att.update(a.id, body=(body if body is not None else GEMENGD).replace("<AID>", a.id))
    st.att.update(a.id, meta={"feiten": [wiki.maak_feit("Een schoen weegt 300 gram"),
                                         wiki.maak_feit("Hennep bindt CO2 tijdens de groei"),
                                         wiki.maak_feit("De zool is plantaardig")]})
    return dd, st, st.att.get(a.id)


# ── 1. Een upload wordt een zichtbare afbeelding ─────────────────────────────
def test_een_afbeelding_wordt_een_echte_img():
    html = _md("![Een foto](/wiki-bestand/NOTE-1/ab_foto.png)")
    assert "<img src='/wiki-bestand/NOTE-1/ab_foto.png'" in html
    assert "alt='Een foto'" in html


def test_een_pdf_blijft_een_kaart():
    """De poort is INTENTIE ÉN VORM. Een `![…]` op iets dat geen afbeelding is, blijft de kaart
    die het altijd was — anders krijg je een gebroken `<img>` waar een leesbare naam stond."""
    html = _md("![Een brief](/wiki-bestand/NOTE-1/ab_brief.pdf)")
    assert "<img" not in html and "wb-emb" in html


def test_een_link_zonder_uitroepteken_blijft_een_kaart():
    """Zonder `!` zegt de schrijver niet dat het beeld is. Een `.png` die als link bedoeld is,
    hoort niet stiekem uitgeklapt te worden."""
    html = _md("[Een foto](/wiki-bestand/NOTE-1/ab_foto.png)")
    assert "<img" not in html and "wb-emb" in html


def test_een_drive_link_met_uitroepteken_blijft_een_kaart():
    """HET GEVAL WAAR DE OUDE CODE-OPMERKING VOOR WAARSCHUWDE. Een Drive-link heeft geen extensie,
    dus `![foto](drive-url)` zou een `<img>` worden die zonder sessie niets laadt. De
    extensie-eis vangt dat: de url moet de intentie wáármaken."""
    html = _md("![Een foto](https://drive.google.com/file/d/abc/view)")
    assert "<img" not in html and "wb-emb" in html


def test_een_externe_afbeelding_blijft_een_kaart():
    """DE DERDE VOORWAARDE, die het ontwerpdocument niet noemde.

    Het document schreef "`data-beeld` én een afbeelingsextensie" — en dat had ook
    `![x](https://ergens/x.png)` een `<img>` gemaakt, waarmee één verzoek naar een vreemde host
    per paginaweergave ontstaat. Dat is precies de beslissing die
    `test_wiki_afbeelding.test_er_wordt_geen_img_geladen` bewaakt, en die het document nergens
    terugdraait. De aanleiding was een geUPLOADE foto; die staat op onze eigen server.

    Twee toetsen over één regel, met opzet: die andere zegt "geen `<img>` voor een vreemde host",
    deze zegt waaróm de nieuwe tak daar niet overheen loopt. Verdwijnt er één, dan is de andere
    er nog."""
    assert "<img" not in _md("![Een foto](https://example.org/foto.png)")


def test_de_afbeelding_overleeft_de_rondgang():
    """DE VAL VAN #603, nu voor beeld: een tag die de weg terug niet kent wordt zijn eigen TEKST,
    en dan staat er na één bewerkronde niets meer waar de foto stond."""
    bron = "![Een foto](/wiki-bestand/NOTE-1/ab_foto.png)"
    assert _md_naar_bron(_md(bron, blokken=True)) == bron


def test_het_bijschrift_verdubbelt_niet(tmp_path):
    """Het bijschrift toont de alt-tekst, en die staat al in `alt`. Zonder `data-chrome` komt hij
    er bij de weg terug als losse tekst bij — en dan groeit de pagina elke bewerkronde."""
    html = _md("![Een foto](/wiki-bestand/NOTE-1/ab_foto.png)", blokken=True)
    assert "data-chrome" in html.split("<figcaption")[1][:60]
    heen = _md_naar_bron(html)
    assert _md_naar_bron(_md(heen, blokken=True)) == heen


def test_een_img_met_een_vreemd_schema_komt_de_opslag_niet_in():
    """DEZELFDE POORT ALS `_md`, EEN STAP EERDER. De renderer zou zo'n `src` nooit maken, maar de
    weg terug leest wat de BROWSER stuurt — en dat is geen bewijs."""
    vuil = "<div class='wb' data-blok='p'><img src='javascript:alert(1)' alt='x'></div>"
    assert "javascript:" not in _md_naar_bron(vuil)


def test_de_afbeelding_heeft_geen_kader_maar_wel_een_maat():
    """`max-width` is niet cosmetisch: een upload is zo groot als de camera hem maakte, en zonder
    die regel rekt één foto de hele kolom op."""
    regel = re.search(r"(?:^|[};])\s*\.wb-img img\{([^}]*)\}", CSS, re.M)
    assert regel, ".wb-img img heeft geen vormgeving"
    assert "max-width:100%" in regel.group(1) and "height:auto" in regel.group(1)
    # DE OMHULLENDE FLEX-KOLOM REKT ZIJN KINDEREN STANDAARD OP. Gemeten in Firefox: een foto van
    # 560px stond echt op 981px — zichtbaar wazig. `max-width` beschermt alleen tegen te groot.
    houder = re.search(r"(?:^|[};])\s*\.wb-img\{([^}]*)\}", CSS, re.M)
    assert houder and "align-items:flex-start" in houder.group(1), \
        "de flex-kolom blaast de afbeelding op tot de kolombreedte"
    assert "border:" not in regel.group(1), "de basislaag hoort geen rand te tekenen"
    assert ".nu .wb-img img" in NU, "de huisstijl-laag kent het blok niet"


# ── 2. Uploaden via het blokmenu, op de +-positie ────────────────────────────
def test_het_menu_kent_afbeelding_en_bestand():
    labels = {rij[1] for rij in BLOK_MENU}
    assert "Afbeelding" in labels and "Bestand" in labels


def test_de_bestandskiezer_krijgt_de_bestaande_allowlist():
    """GEEN TWEEDE LIJST. Zou het menu een eigen opsomming dragen, dan biedt hij morgen een type
    aan dat de server weigert zonder dat iemand dat besloot."""
    per_label = {rij[1]: rij for rij in BLOK_MENU}
    alles = set(per_label["Bestand"][3].split(","))
    assert alles == set(channels.BIJLAGE_TYPES), "de bestandskiezer wijkt af van de allowlist"
    beeld = set(per_label["Afbeelding"][3].split(","))
    assert beeld <= alles, "het beeldfilter biedt iets aan dat niet geupload mag worden"
    assert all(_is_beeldbestand("x" + e) for e in beeld), "er zit een niet-afbeelding in"


def test_svg_zit_in_geen_van_beide():
    """DE DOORSNEDE IS SMALLER DAN JE ZOU RADEN: `_BEELD_EXT` kent `.svg`, de uploadlijst niet —
    een SVG kan script dragen. Precies daarom is `_accept` een doorsnede en geen kopie."""
    assert _is_beeldbestand("x.svg"), "de renderer ziet .svg niet meer als afbeelding"
    assert ".svg" not in _accept(alleen_beeld=True) and ".svg" not in _accept()


def test_de_twee_items_openen_een_kiezer_en_geen_commando():
    per_label = {rij[1]: rij for rij in BLOK_MENU}
    assert per_label["Afbeelding"][2] == "upload" and per_label["Bestand"][2] == "upload"
    assert "data-wiki-cmd='upload'" in blok_menu()


def test_de_upload_stand_schrijft_niet_in_de_body(tmp_path):
    """DE KERN VAN PUNT 2. De oude weg plakte de regel achter de OPGESLAGEN body en stuurde je
    door — dus alles wat je sinds "Edit page" had getypt was weg. In de blok-stand geeft de server
    de regel terug en zet de client hem op de `+`-positie."""
    tak = inspect.getsource(cockpit2).split('fields.get("action") == "wiki_bijlage"')[1].split(
        'fields.get("action") == "kanaal_bijlage"')[0]
    assert 'fields.get("mode") == "blok"' in tak
    vroeg = tak.index('fields.get("mode") == "blok"')
    assert vroeg < tak.index("_st.att.update("), \
        "de blok-stand moet terugkeren vóór er iets naar de body geschreven wordt"


def test_de_server_rendert_en_de_browser_zet_neer():
    """ER KOMT GEEN TWEEDE RENDERER IN JS — de regel die op drie plekken in deze codebase staat.
    De server stuurt de gerenderde HTML van één blok mee; `nooch.js` hoeft dus niet te weten wat
    een afbeeldingsextensie is of hoe een `![…]` eruitziet."""
    tak = inspect.getsource(cockpit2).split('fields.get("action") == "wiki_bijlage"')[1].split(
        'fields.get("action") == "kanaal_bijlage"')[0]
    assert '"html": _md(' in tak, "de server stuurt geen gerenderde HTML mee"
    kaal = js_zonder_uitleg(JS)
    hulp = kaal.split("function uploadInBlok")[1].split("\n  function ")[0]
    for verboden in ("![", ".png", ".jpg", "<img"):
        assert verboden not in hulp, f"de browser weet opeens van {verboden!r}"


def test_de_upload_tak_benoemt_zijn_autorisatie():
    tak = inspect.getsource(cockpit2).split('fields.get("action") == "wiki_bijlage"')[1].split(
        'fields.get("action") == "kanaal_bijlage"')[0]
    assert "AUTHZ:" in tak


def test_een_geuploade_afbeelding_krijgt_het_uitroepteken():
    """ZONDER DIT IS DE HELE STAP VOOR NIETS: de regel zou `[naam](url)` zijn en dus als kaart
    met de bestandsnaam renderen — precies de klacht."""
    from nooch_village.cockpit2 import _wiki_bijlage_regel
    assert _wiki_bijlage_regel("NOTE-1", "ab_foto.png", "foto.png").startswith("![")
    assert _wiki_bijlage_regel("NOTE-1", "ab_brief.pdf", "brief.pdf").startswith("[")


def test_het_losse_formulier_is_weg(tmp_path):
    """Twee wegen naar dezelfde handeling is precies het risico dat de code-comment bij dat
    formulier zélf al benoemde."""
    dd, st, a = _dorp(tmp_path)
    html = render_pagina(st, a.id, csrf_token="TOK", username="b@t.nl")
    assert "value='wiki_bijlage'" not in html


# ── 3. Slepen — al gebouwd, en dat blijft zo ─────────────────────────────────
def test_slepen_bestaat_al_en_hergebruikt_het_gedeelde_mechanisme():
    """HET ONTWERPDOCUMENT VROEG DIT TE BOUWEN; het stond er al sinds #599.

    Deze toets is er dus niet om iets nieuws vast te leggen maar om te voorkomen dat er ooit een
    tweede sleepmechanisme naast komt — precies waar de code-comment boven `NV.sleep` voor
    waarschuwt: "een tweede implementatie zou betekenen dat de ene na een wijziging anders sleept
    dan de andere"."""
    kaal = js_zonder_uitleg(JS)
    haak = kaal.split("function grepen(")[1].split("\n  function ")[0]
    assert "NV.sleep(body" in haak, "de wiki roept het gedeelde sleepmechanisme niet aan"
    assert "helft: true" in haak, "vóór/ná wordt niet getoond tijdens het slepen"
    assert 'greep: ".wb-greep-knop"' in haak, "de hele blokbreedte sleept (vecht met selecteren)"
    assert "data-blok-id" in haak, "blokken hebben geen identiteit om mee te slepen"
    assert kaal.count("NV.sleep = function") == 1, "er is een tweede sleepmechanisme"


def test_het_menu_blijft_naast_het_slepen_bestaan():
    """Sleep is muis/pen. Het ↑/↓/✕-menu is de weg voor toetsenbord en touch en gaat dus niet weg
    — dezelfde toegankelijkheidsregel die al in de code staat."""
    kaal = js_zonder_uitleg(JS)
    for actie in ("omhoog", "omlaag", "verwijder"):
        assert actie in kaal


# ── 4. Archiveren en verwijderen ─────────────────────────────────────────────
def test_de_pagina_heeft_archive_en_delete(tmp_path):
    dd, st, a = _dorp(tmp_path)
    html = render_pagina(st, a.id, csrf_token="TOK", username="b@t.nl")
    assert "value='artefact_archive'" in html and "value='artefact_delete'" in html


def test_archiveren_is_geen_nieuwe_actie():
    """`artefact_archive` bestaat sinds het artefact-model en werkt op elk soort artefact — een
    pagina is een note, dus hij kon dit altijd al; er was alleen nooit een knop. Een eigen
    `wiki_archive` zou de tweede weg naar dezelfde handeling zijn."""
    assert "artefact_archive" in cockpit2.ACTIONS
    assert "wiki_archive" not in cockpit2.ACTIONS


def test_verwijderen_vraagt_om_bevestiging_en_noemt_het_alternatief(tmp_path):
    """Zelfde tekstpatroon als `proj_delete`: dezelfde handeling hoort hetzelfde te vragen."""
    dd, st, a = _dorp(tmp_path)
    html = render_pagina(st, a.id, csrf_token="TOK", username="b@t.nl")
    knop = re.search(r"<button[^>]*value='artefact_delete'[^>]*>", html)
    assert knop and "confirm(" in knop.group(0)
    assert "Archiving keeps the page" in knop.group(0)


def test_wie_niet_mag_bewerken_ziet_de_knoppen_niet(tmp_path):
    """De poort staat vóór de belofte — dezelfde regel als bij de bewerkknop."""
    dd, st, a = _dorp(tmp_path)
    html = render_pagina(st, a.id, csrf_token="", username=None)
    assert "artefact_delete" not in html and "artefact_archive" not in html


def test_verwijderen_is_zwaarder_gepoort_dan_archiveren():
    """Archiveren mag de rolvervuller, weggooien alleen de Circle Lead — dezelfde verdeling als
    bij projecten, en om dezelfde reden: een pagina kan bewijs dragen waar een ander naar wijst."""
    arch = inspect.getsource(cockpit2._act_artefact_archive)
    weg = inspect.getsource(cockpit2._act_artefact_delete)
    assert "_artefact_gate" in arch and "is_circle_lead" not in arch
    assert "is_circle_lead" in weg
    assert "AUTHZ:" in weg, "elke nieuwe dispatch-tak benoemt zijn autorisatiekeuze"


def test_verwijderen_neemt_de_bestanden_mee(tmp_path):
    """De body is de enige verwijzing naar een upload, en die gaat hier weg. Laten staan betekent
    schijfruimte die niemand ooit nog terugvindt."""
    import os
    dd, st, a = _dorp(tmp_path)
    map_ = os.path.join(dd, "attachments", "wiki", a.id)
    os.makedirs(map_, exist_ok=True)
    open(os.path.join(map_, "ab12cd34_schoen.png"), "wb").write(b"png")
    # DE POORT IS DE CIRCLE LEAD, dus die moet de opstelling echt zijn — anders toetst dit
    # alleen dat de weigering werkt. `is_circle_lead` kijkt naar `<cirkel>__circle_lead`.
    mens = st.people.by_email("b@t.nl")
    cirkel = cockpit2.resolve_circle_id(a.anchor, st.records)
    st.assign.assign(f"{cirkel}__circle_lead", "person", mens.id)
    assert cockpit2.is_circle_lead(mens.id, cirkel, st.assign), "de opstelling klopt niet"

    class _C:
        pass
    c = _C()
    c.nxt, c.username, c.data_dir, c.st = f"/pagina?id={a.id}", "b@t.nl", dd, st
    c.g = lambda k: {"aid": a.id}.get(k, "")
    nxt, msg = cockpit2._act_artefact_delete(c)
    assert st.att.get(a.id) is None, "het artefact staat er nog"
    assert not os.path.isdir(map_), "de geuploade bestanden staan er nog"
    assert a.id not in nxt, "je landt op de pagina die je net hebt weggegooid"


def test_de_historie_wordt_gelogd_voordat_de_rij_verdwijnt():
    """`log_change` LEEST het artefact, dus hij moet draaien zolang het er nog is — anders staat
    er over wat verdween niets in het changelog, en dat is precies wanneer je het nodig hebt."""
    src = inspect.getsource(cockpit2._act_artefact_delete)
    assert src.index("log_change") < src.index("st.att.remove(")


# ── De gemengde testpagina als geheel ────────────────────────────────────────
def test_de_gemengde_pagina_leest_als_een_pagina(tmp_path):
    """DE VOLGORDE UIT HET ONTWERPDOCUMENT, in één render: tekst → feit → afbeelding → tekst →
    tekst → (drie feiten in dat ene blok) → link."""
    dd, st, a = _dorp(tmp_path)
    html = render_pagina(st, a.id, csrf_token="TOK", username="b@t.nl")
    body = html.split("id='wiki-body'")[1].split("id='wb-menu-sjabloon'")[0]
    volgorde = [m.group(1) for m in re.finditer(r"data-blok='([a-z]+)'", body)]
    assert "facts" in volgorde and "backlinks" in volgorde and "embed" in volgorde
    assert volgorde.index("facts") < volgorde.index("embed") < volgorde.index("backlinks")
    assert "<img src='/wiki-bestand/" in body, "de afbeelding rendert niet als beeld"
    assert body.count("class='ptitle'") == 3, "de drie feiten staan er niet"


def test_de_gemengde_pagina_overleeft_de_rondgang(tmp_path):
    """Alle zeven blokvormen door dezelfde weg terug, in elkaars gezelschap. Los werkt elk van
    deze; dat ze elkáár niet opeten is de vraag die alleen een gemengde pagina stelt."""
    dd, st, a = _dorp(tmp_path)
    eerste = _md(a.body, blokken=True)
    assert _md(_md_naar_bron(eerste), blokken=True) == eerste
