"""Twee dingen die op de wall en op de kaart verkeerd LAZEN (29 september 2026, melding Stefan).

1. EEN LOGREGEL DEED ZICH VOOR ALS EEN OPMERKING. "✅ Mens-taak afgerond: …" wordt door de code
   geschreven (`project_items`), maar stond in de wall als volwaardige comment-bubbel: met
   naam-kop, met bubbel-kader, met een Edit-knop. Drie keer mis — het leest als iets wat iemand
   zei, het vraagt evenveel aandacht als een echt bericht, en het nodigt uit om een FEIT te
   herschrijven.

   HET ONDERSCHEID BESTOND AL: `kind="system"` staat sinds de eerste versie van `add_feed_entry`
   in het schema. Het scherm keek alleen naar het auteurs-TYPE, en dat is bij deze regels gewoon
   "human" — een mens vinkte het item af. Er hoefde dus niets aan de data te veranderen.

2. "DONE" MET EEN ONBEVESTIGD RAPPORT ZAG ER KLAAR UIT. De amber vraag "needs your confirmation"
   stond alleen binnenin de kaart; op het bord was er geen verschil met een project dat écht af is.
   Wat je pas ziet na openen, zie je niet.
"""
from __future__ import annotations

from nooch_village import cockpit2
from nooch_village.views import projects as P

ROL = "mother_earth__nooch__website_developer"
IK = "ik@nooch.earth"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Ik Zelf", IK)
    st.assign.assign(ROL, "person", ik.id)
    pid = st.projects.create(ROL, "Checkout flow", "human", status="running")
    return dd, pid, ik


def _wall(dd, pid, wie=IK):
    return P.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK", username=wie)


# ══ 1. De logregel ═══════════════════════════════════════════════════════════
def test_een_logregel_is_geen_comment_bubbel(tmp_path):
    dd, pid, ik = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    st.projects.add_feed_entry(pid, "✅ Mens-taak afgerond: Bel de leverancier",
                               kind="system", author_type="human", author_id=ik.id)
    h = _wall(dd, pid)
    assert "fentry-log" in h, "de logregel krijgt niet de rustige vorm"
    assert "Mens-taak afgerond" in h, "en hij staat er nog wel"
    # GEEN NAAM-KOP. `fhead` draagt avatar + naam; op een regel die niemand zei is dat een leugen.
    blok = h[h.index("fentry-log"):]
    blok = blok[:blok.index("</div>", blok.index("fbubble"))]
    assert "fhead" not in blok and "fname" not in blok


def test_op_een_logregel_staat_geen_edit_knop(tmp_path):
    """Een feit herschrijven is iets anders dan een audittrail opschonen — Remove blijft."""
    dd, pid, ik = _dorp(tmp_path)
    cockpit2._Stores(dd).projects.add_feed_entry(
        pid, "✅ Mens-taak afgerond: Bel de leverancier", kind="system",
        author_type="human", author_id=ik.id)
    h = _wall(dd, pid)
    assert "feed_edit" not in h, "de logregel is bewerkbaar"
    assert "feed_remove" in h, "de logregel is niet op te ruimen"


def test_een_echte_opmerking_houdt_zijn_bubbel(tmp_path):
    """De rustige vorm geldt alleen voor wat de CODE schreef. Anders verdwijnt het gesprek mee."""
    dd, pid, ik = _dorp(tmp_path)
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"],
                                        "text": ["dit zei ik zelf"], "next": ["/"]}, username=IK)
    h = _wall(dd, pid)
    assert "fentry-log" not in h
    assert "fhead" in h and "feed_edit" in h


def test_de_rustige_vorm_staat_waar_hij_wint():
    """Geen inline style: een modifier op het bestaande `.fentry`, zoals `-opdracht` en `-attach`.

    MAAR NIET WAAR DIE TWEE STAAN, en dat is geen slordigheid: de designsysteem-helft kadert
    `.fbubble` met `:root .fbubble` in. Een regel in de componentlaag heeft dezelfde specificiteit
    en staat eerder in het bestand, dus hij verliest — dat was precies te zien in de browser: de
    logregel hield zijn kader. De vorm staat daarom in de DS-helft, de marge in de componentlaag."""
    from conftest import basis_css, designsysteem_css
    assert ".fentry-log{" in basis_css()
    ds = designsysteem_css()
    assert ":root .fentry-log .fbubble {" in ds
    assert ds.index(":root .fbubble") < ds.index(":root .fentry-log .fbubble"), (
        "de uitzondering staat vóór de regel die hij moet overrulen")


# ══ 2. Het kaartsignaal ══════════════════════════════════════════════════════
def test_done_met_onbevestigd_rapport_draagt_het_op_de_kaart(tmp_path):
    dd, pid, ik = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    kaart_voor = P._proj_card(st, st.projects.get(pid), "TOK", "/projects")
    assert "needs your confirmation" not in kaart_voor

    st.project_docs.write_concept(pid, "## Result\nAchieved.", bronnen=["checklist"])
    st = cockpit2._Stores(dd)
    kaart = P._proj_card(st, st.projects.get(pid), "TOK", "/projects")
    assert "needs your confirmation" in kaart
    # HETZELFDE CHIPJE ALS BINNENIN: dezelfde toestand hoort er niet op twee plekken anders uit te
    # zien — en een kleur is nooit de enige drager, dus het woord staat erbij.
    assert "chip amber" in kaart


def test_een_bevestigd_project_draagt_niets(tmp_path):
    """Zodra het concept weg is, is er niets meer te bevestigen — en dan hoort de kaart te zwijgen."""
    dd, pid, ik = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    st.project_docs.write_concept(pid, "## Result\nAchieved.")
    st.project_docs.clear_concept(pid)
    kaart = P._proj_card(cockpit2._Stores(dd), st.projects.get(pid), "TOK", "/projects")
    assert "needs your confirmation" not in kaart


def test_een_leeg_concept_is_geen_signaal(tmp_path):
    """Een concept-bestand zonder tekst is geen wachtend rapport; de kaart-binnenkant stelt dezelfde
    eis (`(concept.get("tekst") or "").strip()`)."""
    dd, pid, ik = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    st.project_docs.write_concept(pid, "   ")
    kaart = P._proj_card(cockpit2._Stores(dd), st.projects.get(pid), "TOK", "/projects")
    assert "needs your confirmation" not in kaart


# ══ 3. Wie het schreef, staat erboven ════════════════════════════════════════
def test_een_bericht_van_een_ander_draagt_diens_naam(tmp_path):
    """"You" BOVEN ANDERMANS BERICHT was geen keuze maar een gat: het auteurstype "human" matchte
    geen enkele tak in `_feed_who` en viel door naar de laatste regel. Dat viel niet op zolang
    mens-entries geen auteur DROEGEN — sinds de wall-poort de person-id meeschrijft is het gewoon
    de verkeerde naam boven een bericht dat je niet eens mag bewerken."""
    dd, pid, ik = _dorp(tmp_path)
    ander = cockpit2._Stores(dd).people.add("Ander Iemand", "ander@nooch.earth")
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"],
                                        "text": ["dit schreef ik"], "next": ["/"]},
                      username="ander@nooch.earth")
    h = _wall(dd, pid)                                  # bekeken als IK, geschreven door ANDER
    assert "Ander Iemand" in h
    assert ">You<" not in h, "het bericht van een ander leest nog als van jezelf"
    assert ander.id not in h.split("fbubble")[0], "het kale id staat op het scherm"


def test_een_bericht_zonder_auteur_is_van_someone(tmp_path):
    """De 156 mens-entries van vóór 29 september dragen geen auteur. "Someone" is dan het eerlijke
    antwoord: van iemand, niet van jou — en niet een naam die niemand kan controleren."""
    dd, pid, ik = _dorp(tmp_path)
    cockpit2._Stores(dd).projects.add_feed_entry(pid, "van lang geleden", kind="comment",
                                                 author_type="human", author_id="")
    h = _wall(dd, pid)
    assert "Someone" in h and ">You<" not in h


def test_je_eigen_bericht_draagt_je_eigen_naam(tmp_path):
    """Geen aparte tak voor "jij": je naam is je naam, ook boven je eigen regel. Dat de knoppen
    eronder wél van jou afhangen, staat los van hoe je heet."""
    dd, pid, ik = _dorp(tmp_path)
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"],
                                        "text": ["van mij"], "next": ["/"]}, username=IK)
    h = _wall(dd, pid)
    assert "Ik Zelf" in h and "feed_edit" in h


# ══ 4. De projectpagina, na het eerste echte gebruik (30 september 2026) ═════
def test_de_pakketknop_staat_niet_meer_naast_de_titel(tmp_path):
    """Stefan: "kan weg".

    EN HIJ WAS BOVENDIEN DOOD. `/project_pakket` bestaat nergens in de code — geen route, geen
    handler, geen export. Wie erop klikte kreeg de 404 van `do_GET`. Dezelfde klasse fout als de
    Linkbuilding-kaart die negen dagen naar een verwijderd scherm wees: een knop is een LINK in
    code, en verdwijnt (of komt er nooit) het scherm eronder, dan merkt niemand het tot iemand
    klikt. Hem weghalen is hier dus geen verlies maar het opruimen van een belofte."""
    import pathlib
    dd, pid, ik = _dorp(tmp_path)
    h = _wall(dd, pid)
    kop = h.split("pcard-head")[1].split("</div>")[0]
    assert "pakket" not in kop and "project_pakket" not in kop
    bron = (pathlib.Path(__file__).resolve().parents[1] / "nooch_village" / "cockpit2.py").read_text()
    assert "project_pakket" not in bron, (
        "de route bestaat inmiddels wél — dan is dit een besluit over WAAR de knop hoort")


def test_de_titel_draagt_geen_vaste_onderlijn():
    """HET WAS GEEN ONTBREKENDE REGEL MAAR EEN EXPLICIETE. `.title-edit` stond in de veld-rij van
    het designsysteem en kreeg daarmee dezelfde 1,5px onderlijn als een zoekveld — op 1,5rem/700
    leest die als een streep ONDER de titel, niet als "hier kun je typen"."""
    from conftest import designsysteem_css
    css = designsysteem_css()
    veldrij = css.split(":root textarea, :root select, :root .ctrl, :root .fieldform")[1].split("}")[0]
    assert ".title-edit" not in veldrij, "de titel hangt weer aan de veld-onderlijn"
    assert ":root input.title-edit { font-family" in css
    eigen = css.split(":root input.title-edit {")[1].split("}")[0]
    assert "border-bottom: 2px solid transparent" in eigen
    assert ":root input.title-edit:focus { border-bottom-color: var(--nu-accent)" in css
    # MÉT DE TAGNAAM, en dat is rekenwerk: het veld draagt geen `type`, dus het matcht ook
    # `:root input:not([type])` — (0,2,1) tegen (0,2,0) voor een kale klasse. Gemeten in Firefox
    # vóór deze correctie: de titel hield zijn zwarte 1,5px-onderlijn.
    assert ":root .title-edit {" not in css, "de kale klasse verliest van input:not([type])"


def test_een_bericht_zonder_stem_is_bewerkbaar_door_wie_het_mag_weghalen(tmp_path):
    """DE 156 ANONIEME MENS-ENTRIES van vóór 29 september. Ze waren wél te VERWIJDEREN en niet te
    corrigeren: een typefout of een half geplakt bericht stond er voorgoed, of moest helemaal weg.
    Er is niemand wiens woorden je in de mond legt — het staat al naamloos op het scherm."""
    from nooch_village.cockpit2 import mag_wall_bewerken, mag_wall_verwijderen, zonder_stem
    dd, pid, ik = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    e = st.projects.add_feed_entry(pid, "Via Lotte: opusmanufacturing.com", kind="comment",
                                   author_type="human", author_id="")
    st = cockpit2._Stores(dd)
    assert zonder_stem(e) is True
    # `ik` vervult de eigenaar-rol van dit project (zie `_dorp`), dus hij mocht hem al weghalen.
    assert mag_wall_verwijderen(st, e, ik.id, pid) is True
    assert mag_wall_bewerken(st, e, ik.id, pid) is True
    h = _wall(dd, pid)
    assert "Someone" in h and "feed_edit" in h


def test_een_bericht_mét_naam_blijft_strikt_auteur_only(tmp_path):
    """DE GRENS, EN HET BESLUIT VAN 26 SEPTEMBER. Een rol-bericht mag je het zwijgen opleggen, geen
    andere woorden in de mond leggen — ook niet als je de rol bekleedt, en ook niet als het id van
    die rol leeg is (dan staat er "Role" boven, en dat is nog steeds een naam)."""
    from nooch_village.cockpit2 import mag_wall_bewerken, zonder_stem
    dd, pid, ik = _dorp(tmp_path)
    st = cockpit2._Stores(dd)
    ander = st.people.add("Ander", "ander@test.nl")
    van_ander = st.projects.add_feed_entry(pid, "van een ander mens", kind="comment",
                                           author_type="human", author_id=ander.id)
    van_rol = st.projects.add_feed_entry(pid, "van een rol", kind="comment",
                                         author_type="role", author_id=ROL)
    rol_zonder_id = {"id": "x", "kind": "comment", "at": 1.0, "text": "van een naamloze rol",
                     "author": {"type": "role", "id": ""}}
    st = cockpit2._Stores(dd)
    assert zonder_stem(van_ander) is False and zonder_stem(van_rol) is False
    assert zonder_stem(rol_zonder_id) is False, "een rol toont 'Role' — dat is een naam"
    for e in (van_ander, van_rol, rol_zonder_id):
        assert mag_wall_bewerken(st, e, ik.id, pid) is False


def test_verwijderen_houdt_je_op_de_projectpagina(tmp_path):
    """Zonder `next` valt de dispatch terug op "/": je haalt één regel weg en staat op de
    homepage. De system-log-tak gaf hem al wél mee — dezelfde knop, twee plekken, één die
    achterbleef."""
    dd, pid, ik = _dorp(tmp_path)
    cockpit2.dispatch(dd, "proj_feed", {"pid": [pid], "author": ["human:"],
                                        "text": ["weg hiermee"], "next": ["/"]}, username=IK)
    st = cockpit2._Stores(dd)
    eid = st.projects.get(pid)["log"][-1]["id"]
    h = _wall(dd, pid)
    # OP HET VERWIJDER-FORMULIER ZELF, en niet op "de eerste velden na het bericht-id". Die eerste
    # is het INLINE-BEWERKVELD, dat zijn `next` altijd al had — een mutatie liet zien dat de toets
    # daardoor groen bleef met het veld uit de verwijderknop gesloopt. Zelfde valkuil als bij de
    # aftik-knop in het werkoverleg: anker op wat het formulier UNIEK maakt.
    stuk = h[:h.index("value='feed_remove'")]
    formulier = stuk[stuk.rindex("<form"):]
    assert f"value='{eid}'" in formulier, "dit is het verkeerde bericht"
    assert "name='next'" in formulier and f"/project?pid={pid}" in formulier
    nxt, msg = cockpit2.dispatch(dd, "feed_remove",
                                 {"pid": [pid], "item": [eid],
                                  "next": [f"/project?pid={pid}"]}, username=IK)
    assert not cockpit2.is_weigering(msg), msg
    assert nxt.startswith(f"/project?pid={pid}")
