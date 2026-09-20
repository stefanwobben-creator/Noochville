"""Stap 4: de synthese, het ritme en het geheugen van de weekmemo.

WAAROM ÉÉN MEMO OVER ALLE VIJF DE BRONNEN. Stefans besluit, en zijn grond: *"de synthese is waar de
waarde zit"*. Vijf losse memo's zijn vijf lijstjes; de vraag die een mens echt heeft — waar raken
deze dingen elkaar — beantwoordt geen van de vijf afzonderlijk. Daarom mag hier ook een duur model
(`weekmemo_synthese` in `llm_keuze.HOOG_INZET`): één call per week, en de enige plek in deze
pijplijn waar een model iets MAAKT in plaats van filtert.

Vier dingen liggen hier vast, en drie ervan zijn de manieren waarop zo'n memo stukgaat:

  1. FAIL-OPEN MET DE FEITEN. Valt het model weg, dan komt er een kale opsomming mét bronnen — geen
     lege memo. Dat weegt zwaarder dan bij `materiaal_memo` waar dit vandaan komt: daar viel één
     memo weg, hier vallen alle vijf de bronnen tegelijk weg.
  2. HET GEHEUGEN IS ÉÉN BOEK. Dat was de belofte bij adapter 2: met vijf bronnen zou "wat is al
     voorgelegd" anders op vijf plekken leven.
  3. HET RITME LEEFT IN HET BESTAND, niet in het geheugen — de daemon herstart en de puls draait
     vaker dan één keer per week.
  4. De prompt draagt de DREMPEL van elke bron, zodat een modelvondst (recall, een vermoeden) niet
     met dezelfde stelligheid wordt opgeschreven als een Kroniek-feit.
"""
from __future__ import annotations

from nooch_village import weekmemo as wm
from nooch_village.weekmemo import Signaal

PERIODE = "2026-W38"


def _sig(bron="legal", tekst="EU scherpt de regels voor groene claims aan",
         herkomst="h1", **extra):
    return Signaal(bron=bron, tekst=tekst, vindplaats="https://eu.example/1",
                   gevonden_op=1_800_000_000.0, herkomst=herkomst, extra=extra or {})


# ── 1. fail-open met de feiten ──────────────────────────────────────────────

def test_zonder_model_komt_er_een_kale_opsomming_met_bronnen():
    """Een lijst met bronnen is lelijk en bruikbaar; een lege memo is stilte over een week waarin
    wel degelijk iets gebeurde."""
    def _stuk(prompt, **kw):
        raise RuntimeError("geen krediet")

    tekst = wm.stel_op([_sig(), _sig(bron="bewijs", tekst="Veja onderbouwt zijn claim",
                                     herkomst="h2")], PERIODE, reason_fn=_stuk)
    assert "geen synthese beschikbaar" in tekst
    assert "groene claims" in tekst and "Veja" in tekst
    assert "https://eu.example/1" in tekst           # de bron reist mee, ook zonder model
    assert "legal" in tekst and "bewijs" in tekst    # gegroepeerd per bron


def test_een_leeg_antwoord_telt_als_geen_model():
    """Een model dat "" teruggeeft is niet hetzelfde als een model dat niets te melden heeft — de
    signalen liggen er. Stil terugvallen op de feiten is hier het juiste gedrag."""
    tekst = wm.stel_op([_sig()], PERIODE, reason_fn=lambda p, **k: "")
    assert "geen synthese beschikbaar" in tekst


def test_zonder_signalen_geen_memo():
    """Liever niets dan een memo die meldt dat er niets is. Dat laatste leert een lezer om hem
    ongeopend weg te klikken, en dan mist hij de week dat er wél iets staat."""
    assert wm.stel_op([], PERIODE, reason_fn=lambda p, **k: "iets") == ""


def test_met_model_komt_de_synthese_met_het_aantal():
    tekst = wm.stel_op([_sig(), _sig(herkomst="h2")], PERIODE,
                       reason_fn=lambda p, **k: "Twee dingen raken elkaar deze week.")
    assert tekst.startswith("🗂 Weekmemo 2026-W38")
    assert "Twee dingen raken elkaar" in tekst
    assert "(2 signalen)" in tekst


# ── 2. de prompt draagt de drempels ─────────────────────────────────────────

def test_de_prompt_zegt_welke_bron_hoe_zeker_is():
    """Zonder dit leest het model een modelvondst met dezelfde stelligheid als een vastgesteld
    Kroniek-feit, en dan staat er in de memo iets als een gegeven wat een vermoeden is."""
    gezien = {}

    def _vang(prompt, **kw):
        gezien["prompt"] = prompt
        gezien.update(kw)
        return "iets"

    wm.stel_op([_sig(bron="claim_model", tekst="onze zolen verdwijnen in de grond")],
               PERIODE, reason_fn=_vang)
    p = gezien["prompt"]
    assert "vermoeden, geen vaststelling" in p
    assert "bewijs" in p and "Het zekerst" in p
    assert "Geen aanbevelingen en geen taken" in p     # de memo stelt voor, hij beslist niet
    assert gezien["call_site"] == wm.CALL_SITE          # eigen meetpunt
    assert (gezien["ladder"] or "").split(",")[0].startswith("anthropic:claude-sonnet")


def test_boven_de_cap_wordt_geteld_en_niet_verzwegen():
    """Boven `PROMPT_CAP` is de memo geen synthese meer maar een opsomming. Wat erbuiten valt moet
    de lezer wél weten — zelfde regel als `bevindingen_totaal` bij de scan-marker."""
    gezien = {}
    veel = [_sig(herkomst=f"h{i}", tekst=f"signaal {i}") for i in range(wm.PROMPT_CAP + 7)]
    wm.stel_op(veel, PERIODE, reason_fn=lambda p, **k: gezien.setdefault("p", p) and "x" or "x")
    assert "7 signaal/signalen vielen buiten deze lijst" in gezien["p"]


# ── 3. het geheugen: één boek voor vijf bronnen ─────────────────────────────

def test_wat_al_voorgelegd_is_komt_niet_terug(tmp_path):
    d = str(tmp_path)
    alles = [_sig(herkomst="a"), _sig(herkomst="b", bron="materiaal")]
    assert len(wm.nieuw(d, alles)) == 2
    wm.onthoud(d, ["a"])
    assert [s.herkomst for s in wm.nieuw(d, alles)] == ["b"]


def test_het_boek_gaat_over_alle_bronnen_heen(tmp_path):
    """DE BELOFTE VAN ADAPTER 2. `materiaal_memo` had zijn eigen boek omdat het de enige bron met
    een geheugen was; met vijf bronnen zou dat vijf boeken worden die hetzelfde feit bijhouden."""
    d = str(tmp_path)
    wm.onthoud(d, ["legal-1", "materiaal-1", "bewijs-1"])
    assert set(wm.voorgelegd(d)) == {"legal-1", "materiaal-1", "bewijs-1"}


def test_een_signaal_zonder_herkomst_geldt_als_nieuw(tmp_path):
    """Zonder herkomst valt er niets te onthouden. Twee keer tonen is vervelend; stil overslaan is
    erger, want dan verdwijnt het zonder dat iemand het merkt."""
    d = str(tmp_path)
    wm.onthoud(d, [""])
    assert len(wm.nieuw(d, [_sig(herkomst="")])) == 1


# ── 4. het ritme ────────────────────────────────────────────────────────────

def test_het_ritme_overleeft_een_herstart(tmp_path):
    """De daemon herstart en de puls draait vaker dan één keer per week; een vlag in het geheugen
    zou elke herstart een tweede memo opleveren."""
    d = str(tmp_path)
    assert wm.al_gedraaid(d, PERIODE) is False
    wm.markeer_gedraaid(d, PERIODE, aantal=3)
    assert wm.al_gedraaid(d, PERIODE) is True
    assert wm.al_gedraaid(d, "2026-W39") is False      # een nieuwe week mag weer


def test_ritme_en_geheugen_delen_hetzelfde_bestand_zonder_elkaar_te_wissen(tmp_path):
    """Allebei in `weekmemo.json`: een schrijver die de ander overschrijft is precies het soort
    stille dataverlies waar de lock-discipline over gaat."""
    d = str(tmp_path)
    wm.onthoud(d, ["a"])
    wm.markeer_gedraaid(d, PERIODE)
    wm.onthoud(d, ["b"])
    assert set(wm.voorgelegd(d)) == {"a", "b"}
    assert wm.al_gedraaid(d, PERIODE) is True


def test_de_synthese_site_staat_in_hoog_inzet():
    """Een toevoeging aan die lijst is een besluit — hij is bevroren in `test_premium_brein`. Hier
    staat de kant van de pijplijn: als dit ooit naar GOEDKOOP schuift, is de grond ("de synthese is
    waar de waarde zit") vervallen en hoort dat opgeschreven te worden."""
    from nooch_village import llm_keuze as lk
    assert wm.CALL_SITE in lk.HOOG_INZET and wm.CALL_SITE not in lk.GOEDKOOP
