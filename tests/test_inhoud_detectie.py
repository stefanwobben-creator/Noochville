"""Wat telt als resultaat van een skill — generieke inhouds-detectie i.p.v. drie allowlists.

De oude opzet had `_LIST_KEYS`/`_TEXT_KEYS`/`_METRIC_KEYS`: een skill moest zijn uitvoer in een
sleutel stoppen die toevallig in die lijsten stond, anders las een geslaagde run als "leeg". Dat
ging drie keer mis — `projectverzoek` (pid/titel), `claims_check` (bevindingen), `content_check` —
en kostte 87 weggegooide resultaten over 9 skills. Een allowlist die elke nieuwe skill een
gezegende sleutelnaam laat raden is stille koppeling.

De valkuil aan de ándere kant is even duur: "ok:True zonder error = gelukt" zou een schone
site-scan als lege deliverable boeken. Daarom detecteert deze laag INHOUD, niet afwezigheid van
fouten — en de expliciete signalen (`error`, `no_data`) blijven leidend.

Drie eigenschappen die hier bewaakt worden:
  1. inhoud wordt herkend zonder dat de sleutelnaam bekend hoeft te zijn;
  2. run-administratie (tellers, weeknummers, vlaggen) telt NIET als inhoud;
  3. legitiem leeg is een ANTWOORD, geen kennisgat.
"""
from __future__ import annotations

import pytest

from nooch_village.inhabitant import Inhabitant as I


def c(result):
    return I._classify_result(result)


# ── 1. Expliciete signalen winnen ───────────────────────────────────────────

def test_expliciete_signalen_blijven_leidend():
    """Zoals een skill het zelf zegt, wint van elke heuristiek."""
    assert c({"error": "stuk"})[0] == "fout"
    assert c({"ok": False, "error": "stuk"})[0] == "fout"
    assert c({"no_data": True, "reason": "niets gevonden"})[0] == "leeg"
    # ...zelfs als er verder inhoud in staat: de skill weet het beter dan wij.
    assert c({"no_data": True, "bevindingen": [1, 2]})[0] == "leeg"
    assert c({"error": "stuk", "hits": [1]})[0] == "fout"


# ── 2. Inhoud wordt herkend zonder gezegende sleutelnaam ────────────────────

@pytest.mark.parametrize("result,verwacht_sleutel", [
    ({"ok": True, "bevindingen": [{"term": "planet-safe"}], "score": 88}, "bevindingen"),
    ({"ok": True, "pid": "abc", "naar_rol": "copywriter", "titel": "Kopregel schrijven"}, "titel"),
    ({"ok": True, "een_gloednieuwe_sleutel": [{"x": 1}]}, "een_gloednieuwe_sleutel"),
    ({"ok": True, "zwakste_claim": "45% is ongegrond", "revisie": "noem de bron"}, "zwakste_claim"),
    ({"ok": True, "gram_co2e": 12.5}, "gram_co2e"),
    ({"ok": True, "conclusie": "3x bevestigd bewijs voor mycelium"}, "conclusie"),
])
def test_inhoud_wordt_herkend_ongeacht_de_naam(result, verwacht_sleutel):
    """DE reden voor deze laag: geen enkele nieuwe skill hoeft nog een sleutelnaam te raden."""
    status, archetype = c(result)
    assert status == "gelukt", result
    assert archetype[1] == verwacht_sleutel


def test_de_rijkste_inhoud_wint():
    """Een lijst met records zegt meer dan een los getal; bij gelijke vorm de grootste. Zonder die
    tweede regel won 'pid' van 'titel' puur op sleutelvolgorde."""
    assert c({"ok": True, "score": 88, "bevindingen": [1, 2]})[1] == ("list", "bevindingen")
    assert c({"ok": True, "pid": "abc", "titel": "een veel langere titel"})[1] == ("text", "titel")


def test_keuze_is_reproduceerbaar():
    r = {"ok": True, "a": [1, 2], "b": [3, 4], "score": 9}
    assert c(r) == c(r) == c(dict(r))


# ── 3. Run-administratie is GEEN inhoud (de over-acceptatie-kant) ───────────

def test_alleen_tellers_en_status_is_leeg():
    """'ok:True zonder error = gelukt' zou hier een lege deliverable boeken. Dat is de fout aan de
    andere kant, en die is even duur."""
    assert c({"ok": True})[0] == "leeg"
    assert c({"ok": True, "total": 5, "gescand": 3, "week": "2026-32"})[0] == "leeg"
    assert c({"ok": True, "count": 0, "aantal": 12, "versie": "2026-07-18.2"})[0] == "leeg"
    assert c({"ok": True, "skipped": True, "at": 1786000000})[0] == "leeg"


def test_lege_containers_tellen_niet():
    assert c({"hits": []})[0] == "leeg"
    assert c({"ok": True, "bevindingen": [], "suggestions": {}})[0] == "leeg"


def test_vlaggen_en_triviale_tekst_tellen_niet():
    assert c({"ok": True, "gate_ok": True})[0] == "leeg"          # bool = status, geen uitkomst
    assert c({"ok": True, "samenvatting": "-"})[0] == "leeg"
    assert c({"ok": True, "notitie": "   "})[0] == "leeg"


def test_een_score_telt_wel_maar_een_teller_niet():
    """Een getal dat een BEVINDING is telt; een getal dat de bevindingen sámenvat niet."""
    assert c({"ok": True, "score": 88})[0] == "gelukt"
    assert c({"ok": True, "total": 88})[0] == "leeg"


def test_privesleutels_tellen_niet():
    assert c({"ok": True, "_intern": [1, 2, 3]})[0] == "leeg"




def test_opmaak_hint_verandert_de_detectie_niet():
    """`_METRIC_HINTS` stuurt alleen de nóte-opmaak. Een dict onder een onbekende sleutel wordt nog
    steeds herkend — hij krijgt alleen de generieke vorm."""
    assert c({"values": {"2026-07-01": 10}})[1] == ("metric", "values")
    assert c({"gloednieuw": {"2026-07-01": 10}})[1] == ("dictlist", "gloednieuw")






def test_critic_telt_een_gerapporteerde_lege_taak_niet_als_gat():
    """DE regel waar het om draait: een project waarin alles in orde bleek mag niet op de
    substantieel-as zakken juist omdát er niets mis was."""
    from nooch_village import missie_critic as mc
    gemeld = {"id": "c", "items": [{"id": "i1", "text": "Toets de copy", "done": True,
                                    "leeg": True, "leeg_bron": "gemeld"}]}
    gat = {"id": "c", "items": [{"id": "i1", "text": "Toets de copy", "done": True,
                                 "leeg": True, "leeg_bron": "geen_inhoud"}]}
    assert mc._lege_items(gemeld) == []                          # antwoord, geen gat
    assert len(mc._lege_items(gat)) == 1
    doc = "x" * 900
    assert mc._substantieel(doc, ["bewijs"], gemeld)[0] is True
    assert mc._substantieel(doc, ["bewijs"], gat)[0] is False


def test_oude_items_zonder_bron_blijven_een_gat():
    """Terugwaartse compatibiliteit: een item van vóór deze wijziging draagt geen `leeg_bron`.
    Dat als 'gemeld' lezen zou historische gaten stilzwijgend witwassen."""
    from nooch_village import missie_critic as mc
    oud = {"id": "c", "items": [{"id": "i", "text": "t", "done": True, "leeg": True}]}
    assert len(mc._lege_items(oud)) == 1


# ── 6. De regressie die dit alles veroorzaakte ─────────────────────────────



# ── 7. Nasleep uit de eerste productiedraai ─────────────────────────────────

def test_nederlandse_metadata_sleutels_tellen_niet():
    """Op prod las een week-gated skip als geslaagd: 'reden' stond niet in de metadata-set, alleen
    het Engelse 'reason'. Precies de over-acceptatie waar de allowlist-fix voor moest oppassen."""
    assert c({"ok": True, "week": "2026-32", "skipped": True,
              "reden": "deze week al gescand"})[0] == "leeg"
    assert c({"ok": True, "refuse": "geen key", "toelichting": "x"})[0] == "leeg"


def test_geslaagde_herdraai_wist_de_oude_leeg_markering(tmp_path):
    """Een item dat eerst niets opleverde en nu wél, mag niet als kennisgat blijven meetellen —
    dat is een gat dat inmiddels gedicht is."""
    from nooch_village.projects import ProjectLedger
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("rol", "doel", "human", status="running")
    cl = led.checklist_add(pid, title="t")
    led.check_add(pid, cl["id"], "taak", skill="x")
    iid = led.get(pid)["checklists"][0]["items"][0]["id"]
    led.set_item_leeg(pid, cl["id"], iid, "niets gevonden", bron="geen_inhoud")
    assert led.get(pid)["checklists"][0]["items"][0]["leeg"] is True
    assert led.clear_item_leeg(pid, cl["id"], iid) is True
    it = led.get(pid)["checklists"][0]["items"][0]
    assert "leeg" not in it and "leeg_bron" not in it and "leeg_reden" not in it
