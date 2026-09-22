"""Messages: één invoerbalk, eigen berichten apart, en een avatarrail met groepering.

DRIE DINGEN MOETEN HARD ZIJN:

  1. DE BALK IS OPMAAK, GEEN FORMULIER. Paperclip, emoji, sticker, veld en knop staan náást
     elkaar in één rij — maar het zijn drie losse formulieren. De paperclip post multipart,
     elke sticker post zijn eigen naam, het veld post `msg_post`. Een <form> in een <form> is
     geen HTML: de browser gooit de binnenste weg en je klikt op een knop die niets doet. Dat
     is hier al een keer gebeurd (#556), dus het staat als test en niet als comment;
  2. GEEN TWEEDE EMOJI-LIJST. De kiezer in de balk gebruikt dezelfde `_EMOJIS_FULL` en dezelfde
     schil als de reactie-kiezer onder een bericht. Alleen de ACTIE verschilt: invoegen in je
     tekst tegenover een reactie plaatsen;
  3. GROEPEREN OP SPREKER ÉN TIJD. Drie zinnen achter elkaar van dezelfde persoon zijn één
     blok met één avatar; een reactie van een uur later krijgt zijn kop terug.

En één ding dat geen test maar een grens is: de eigen-bericht-tint komt uit de bestaande
tokens (`--green-tint` in de basislaag, `--nu-bg-alt` in de nu-laag). Geen nieuwe kleur.
"""
from __future__ import annotations

import os
import re
import time
from html.parser import HTMLParser

from nooch_village import channels, cockpit2
from nooch_village.views.messages import _bericht, _zelfde_spreker, render_messages

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = open(os.path.join(BASIS, "nooch_village", "static", "nooch.css"), encoding="utf-8").read()
NU = open(os.path.join(BASIS, "nooch_village", "static", "nooch-ui.css"), encoding="utf-8").read()
JS = open(os.path.join(BASIS, "nooch_village", "static", "nooch.js"), encoding="utf-8").read()


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    ik = st.people.add("Ik Zelf", "ik@nooch.earth")
    ander = st.people.add("Ander Iemand", "ander@nooch.earth")
    return dd, cockpit2._Stores(dd), ik.id, ander.id


def _kanaal():
    return channels.circle_kanaal("mother_earth")


def _diepste_formulier(html: str) -> int:
    class Teller(HTMLParser):
        def __init__(self):
            super().__init__()
            self.diepte = self.max = 0

        def handle_starttag(self, tag, attrs):
            if tag == "form":
                self.diepte += 1
                self.max = max(self.max, self.diepte)

        def handle_endtag(self, tag):
            if tag == "form":
                self.diepte = max(0, self.diepte - 1)

    t = Teller()
    t.feed(html)
    return t.max


# ── 1. De balk ──────────────────────────────────────────────────────────────────────────────
def test_alles_staat_in_een_balk(tmp_path):
    dd, st, ik, _a = _dorp(tmp_path)
    html = render_messages(st, ik=ik, kanaal=_kanaal(), csrf_token="t")
    # Tot het einde van de draad-sectie: de balk is daar het laatste blok. Knippen op een
    # `</div></div>` zou meetellen hoe diep de paperclip toevallig genest is.
    balk = html.split("class='msg-balk'")[1].split("</section>")[0]
    assert "msg-bijlage-add" in balk                       # paperclip
    assert "data-emo-invoeg" in balk                       # emoji
    assert "value='sticker_post'" in balk                  # stickers
    assert "id='msg-tekst'" in balk                        # het veld
    assert "value='msg_post'" in balk                      # en de verstuurknop


def test_de_balk_nest_geen_formulieren(tmp_path):
    """DE REDEN DAT DIT EEN TEST IS EN GEEN COMMENT: dit ging al een keer mis. Een knop in een
    genest formulier doet niets, en dat zie je aan niets."""
    dd, st, ik, _a = _dorp(tmp_path)
    html = render_messages(st, ik=ik, kanaal=_kanaal(), csrf_token="t")
    assert _diepste_formulier(html) == 1


def test_de_emojiknoppen_zijn_geen_submits(tmp_path):
    """Ze staan náást een formulier, niet erin — maar een knop zonder type is een submit, en
    dan post de balk bij elke emoji."""
    dd, st, ik, _a = _dorp(tmp_path)
    html = render_messages(st, ik=ik, kanaal=_kanaal(), csrf_token="t")
    for knop in re.findall(r"<button[^>]*data-emo-invoeg[^>]*>", html):
        assert "type='button'" in knop, knop


def test_het_schrijfveld_houdt_zijn_label(tmp_path):
    """Het zichtbare label is weg (het is een chatbalk, geen formulier met veldnamen), maar een
    schermlezer hoort nog steeds te horen wat dit veld is."""
    dd, st, ik, _a = _dorp(tmp_path)
    html = render_messages(st, ik=ik, kanaal=_kanaal(), csrf_token="t")
    assert "<label class='sr' for='msg-tekst'>" in html


def test_de_kiezers_in_de_balk_klappen_omhoog():
    """GEMETEN, NIET BEDACHT: `.emoji-pop` hangt standaard ONDER zijn knop (`top:1.5rem`) en de
    balk staat onderaan het gesprek. In de browser viel de popup op 818px in een venster van
    616px — je zag 'm simpelweg niet. Binnen de balk dus andersom, en met `bottom` zodat een
    langere lijst naar boven groeit in plaats van over de balk heen te zakken."""
    # Commentaar eruit vóór het parsen: anders plakt de uitleg boven een regel aan de
    # selector vast en matcht er niets. (Diezelfde fout maakte ik hier twee keer eerder.)
    kaal = re.sub(r"/\*.*?\*/", " ", CSS, flags=re.S).replace("\n  ", "")
    per = {s.strip(): b for s, b in re.findall(r"([^{}]+)\{([^{}]*)\}", kaal)}
    pop = per.get(".msg-balk .emoji-pop", "")
    assert pop, "geen regel die de kiezer in de balk omhoog laat klappen"
    assert "top:auto" in pop and "bottom:" in pop, pop
    clip = per.get(".msg-balk .msg-bijlage-add>.qadd-form", "")
    assert "bottom:" in clip, clip


def test_de_paperclip_is_in_de_balk_een_icoon_met_een_naam(tmp_path):
    """Het woord "attach a file" zou de rij uit elkaar trekken naast twee andere iconen. Het
    verdwijnt van het scherm, niet uit de pagina: `title` voor de muis, `aria-label` voor wie
    het niet ziet."""
    dd, st, ik, _a = _dorp(tmp_path)
    html = render_messages(st, ik=ik, kanaal=_kanaal(), csrf_token="t")
    # BINNEN DE BALK ZOEKEN. Op de kale klasse matchte de eerste `<summary class='muted'>` van
    # de pagina — "＋ new conversation" in de kanalenlijst — en dan meet de test iets anders
    # dan hij beweert.
    balk = html.split("class='msg-balk'")[1].split("</section>")[0]
    sam = re.search(r"<summary class='muted'([^>]*)>([^<]*)</summary>", balk)
    assert sam, "geen paperclip-summary in de balk"
    assert "aria-label='attach a file'" in sam.group(1)
    assert sam.group(2).strip() == "📎"


# ── 2. Geen tweede emoji-lijst ──────────────────────────────────────────────────────────────
def test_de_balk_en_de_reactie_kiezer_delen_de_lijst(tmp_path):
    """Zou de balk zijn eigen lijst krijgen, dan is de ene na één wijziging langer dan de
    andere zonder dat iemand het merkt — precies wat `reactie_blok` zelf al beschrijft."""
    from nooch_village.views.feed import _EMOJIS_FULL, emoji_invoeg_knoppen, reactie_blok
    invoeg = emoji_invoeg_knoppen("msg-tekst")
    _rx, reactie = reactie_blok({"id": "e1"}, "t", {"kanaal": _kanaal()})
    for emo, _kw in _EMOJIS_FULL:
        assert emo in invoeg and emo in reactie, emo
    assert invoeg.count("<button") == len(_EMOJIS_FULL)


def test_beide_kiezers_gebruiken_dezelfde_schil(tmp_path):
    from nooch_village.views.feed import emoji_invoeg_knoppen, emoji_kiezer, reactie_blok
    _rx, reactie = reactie_blok({"id": "e1"}, "t", {"kanaal": _kanaal()})
    balk = emoji_kiezer(emoji_invoeg_knoppen("msg-tekst"), titel="emoji")
    for klasse in ("emoji-pick", "emoji-pop", "emo-search", "emo-grid", "data-emo-zoek"):
        assert klasse in reactie and klasse in balk, klasse


def test_het_zoekveld_wordt_door_de_gedeelde_mechaniek_bediend():
    """`emoFilter` stond in een inline-script van de project-modal, dus in Messages bestond de
    functie niet en deed hetzelfde zoekveld daar niets. Nu in nooch.js, op elke pagina."""
    assert "data-emo-zoek" in JS and "emoKiezer" in JS
    wire = JS.split("NV.wire = function")[1].split("};")[0]
    assert "emoKiezer(root)" in wire


# ── 3. Eigen berichten, en de rail ──────────────────────────────────────────────────────────
def test_een_eigen_bericht_staat_apart(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal()
    st.channels.post(k, "van mij", author_type="human", author_id=ik)
    st.channels.post(k, "van een ander", author_type="human", author_id=ander)
    st = cockpit2._Stores(dd)
    html = render_messages(st, ik=ik, kanaal=k, csrf_token="t")
    mijn = html.split("van mij")[0]
    assert "msg-item--ik" in mijn
    # ... en het bericht van de ander niet
    diens = html.split("msg-item--ik")[1].split("van een ander")[0]
    assert "msg-item--ik" not in diens


def test_een_ander_krijgt_een_avatar_en_jij_niet(tmp_path):
    """Een rail met tien keer je eigen initialen is ruis: je weet wie jij bent."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal()
    e_ik = st.channels.post(k, "van mij", author_type="human", author_id=ik)
    e_ander = st.channels.post(k, "van ander", author_type="human", author_id=ander)
    st = cockpit2._Stores(dd)
    assert "msg-av" not in _bericht(st, e_ik, k, "t", ik)
    assert "msg-av" in _bericht(st, e_ander, k, "t", ik)


def test_drie_zinnen_achter_elkaar_zijn_een_blok(tmp_path):
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal()
    for tekst in ("eerste", "tweede", "derde"):
        st.channels.post(k, tekst, author_type="human", author_id=ander)
    st = cockpit2._Stores(dd)
    html = render_messages(st, ik=ik, kanaal=k, csrf_token="t")
    assert html.count("msg-item--volg") == 2               # twee vervolgen op één kop
    assert html.count("Ander Iemand &middot;") == 1        # en één keer de naam


def test_een_andere_spreker_breekt_het_blok(tmp_path):
    """Mutatie-controle op de test hierboven: die zou ook slagen als álles groepeerde."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal()
    st.channels.post(k, "eerste", author_type="human", author_id=ander)
    st.channels.post(k, "tussendoor", author_type="human", author_id=ik)
    st.channels.post(k, "derde", author_type="human", author_id=ander)
    st = cockpit2._Stores(dd)
    html = render_messages(st, ik=ik, kanaal=k, csrf_token="t")
    assert "msg-item--volg" not in html


def test_een_uur_later_is_een_nieuw_blok():
    """Groeperen op spreker alleen zou een reactie van morgenochtend onder het blok van
    gisteravond plakken, zonder tijd en zonder naam."""
    nu = time.time()
    a = {"author": {"type": "human", "id": "p1"}, "at": nu}
    kort = {"author": {"type": "human", "id": "p1"}, "at": nu + 60}
    laat = {"author": {"type": "human", "id": "p1"}, "at": nu + 3600}
    assert _zelfde_spreker(kort, a) is True
    assert _zelfde_spreker(laat, a) is False
    assert _zelfde_spreker(a, None) is False


def test_de_avatarkolom_blijft_staan_bij_een_vervolg(tmp_path):
    """Leeg, maar wel aanwezig: anders springt de tekst van een vervolgbericht naar links."""
    dd, st, ik, ander = _dorp(tmp_path)
    k = _kanaal()
    e1 = st.channels.post(k, "eerste", author_type="human", author_id=ander)
    e2 = st.channels.post(k, "tweede", author_type="human", author_id=ander)
    st = cockpit2._Stores(dd)
    vervolg = _bericht(st, e2, k, "t", ik, vorige=e1)
    assert "msg-item--volg" in vervolg
    assert "class='msg-av'></div>" in vervolg              # de kolom is er, leeg


# ── 4. Geen nieuwe kleur ────────────────────────────────────────────────────────────────────
def test_de_eigen_bubbel_gebruikt_een_bestaand_token():
    basis = re.search(r"\.msg-item--ik \.msg-body\{([^}]*)\}", CSS.replace("\n  ", "")).group(1)
    assert "var(--green-tint)" in basis, basis
    nu = [b for s, b in re.findall(r"([^{}]+)\{([^{}]*)\}", NU)
          if ".nu .msg-item--ik .msg-body" in s]
    assert nu and "var(--nu-bg-alt)" in nu[0], nu
    # geen losse hexkleur erbij verzonnen
    assert not re.search(r"\.msg-(item|body|balk)[^{}]*\{[^}]*#[0-9a-fA-F]{3,6}", CSS)
