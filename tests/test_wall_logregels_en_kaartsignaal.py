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
