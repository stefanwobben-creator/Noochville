"""Decision Coach — de generator, de parser en het logboek.

De pagina roept geen model aan: hij vult een door mensen onderhouden sjabloon in. Deze tests
toetsen de machinerie, niet de coachingmethode — die leeft in `prompts/decision_coach_en.md` en
wordt hier bewust met een FIXTURE-sjabloon getest. Zou een test de echte tekst controleren, dan kon
niemand die tekst meer bijschaven zonder de suite te breken.

De parser is fail-closed en dat is de kern: een half gelezen sheet zet een regel in het logboek die
zegt dat er besloten is terwijl de helft ontbreekt. Elke weigering hieronder controleert daarom ook
dát er niets geschreven is.
"""
from __future__ import annotations

import json
import threading

import pytest

from nooch_village import decision_coach as dc
from nooch_village import decision_sheets as ds

SJABLOON = """<!-- template_version: 1 -->
# Decision coach ({{mode}})

Decision: {{decision}}
Deadline: {{deadline}}
Options:
{{options}}
Reversibility: {{reversibility}} · Stakes: {{stakes}} · Confidence: {{confidence}}
Decider: {{decider}} · Role: {{role}} · Others: {{stakeholders}}
Leaning: {{leaning}}
Facts: {{facts}}
"""


def _sjabloon(tmp_path, tekst: str = SJABLOON) -> str:
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / dc.BESTAND_EN).write_text(tekst, encoding="utf-8")
    return str(tmp_path)


def _blok(**over) -> str:
    waarden = {
        "Decision": "Switch the outsole supplier for batch 4",
        "Chosen option": "Stay with the current supplier for one more batch",
        "Assumption 1": "The current defect rate stays under 2%",
        "Assumption 2": "The new supplier cannot deliver before March",
        "Prediction (number and date)": "Defect rate at or below 2% on 2026-12-01",
        "Stop signal": "Two batches in a row above 3%",
        "Still unknown, and whether that is acceptable": "Their tooling cost — acceptable for now",
        "Coach version": "1",
    }
    waarden.update(over)
    regels = "\n".join(f"{label}: {waarden[label]}" for label, _ in ds.VELDEN
                       if waarden.get(label) is not None)
    return f"Some chatter before.\n{ds.START}\n{regels}\n{ds.EIND}\nSome chatter after."


# ── 1 & 2: het sjabloon renderen ─────────────────────────────────────────────

def test_sjabloon_rendert_met_alle_velden_ingevuld(tmp_path):
    base = _sjabloon(tmp_path)
    waarden = {n: f"value-{n}" for n, _ in dc.VELDEN}
    prompt, versie = dc.bouw_prompt(base, waarden)
    assert versie == "1"
    for naam, _ in dc.VELDEN:
        assert f"value-{naam}" in prompt
    assert "{{" not in prompt                              # geen achtergebleven placeholder
    assert dc.LEEG not in prompt


def test_alleen_de_drie_verplichte_velden_maakt_de_rest_not_provided(tmp_path):
    base = _sjabloon(tmp_path)
    prompt, _ = dc.bouw_prompt(base, {"decision": "Switch supplier?",
                                      "deadline": "2026-10-01",
                                      "options": "stay\nswitch"})
    assert "Switch supplier?" in prompt and "2026-10-01" in prompt
    # elk optioneel veld is vervangen door de expliciete tekst, niet door leegte
    assert prompt.count(dc.LEEG) == len([n for n, verplicht in dc.VELDEN if not verplicht])
    assert "{{" not in prompt


def test_zonder_sjabloon_geen_prompt(tmp_path):
    """Fail-closed: iets verzinnen zou een coach opleveren die de methode niet volgt."""
    with pytest.raises(dc.SjabloonOntbreekt):
        dc.bouw_prompt(str(tmp_path), {"decision": "x"})
    assert dc.versie(str(tmp_path)) == ""                  # geen bestand → geen versie, geen gok


def test_sjabloon_zonder_versiemarker_geeft_lege_versie(tmp_path):
    base = _sjabloon(tmp_path, "# no marker\nDecision: {{decision}}\n")
    _prompt, versie = dc.bouw_prompt(base, {"decision": "x"})
    assert versie == ""


# ── 3: de parser, gelukkige route ────────────────────────────────────────────

def test_parser_leest_de_zeven_velden(tmp_path):
    sheet = ds.parse(_blok())
    assert sheet.decision == "Switch the outsole supplier for batch 4"
    assert sheet.chosen_option == "Stay with the current supplier for one more batch"
    assert sheet.assumption_1 == "The current defect rate stays under 2%"
    assert sheet.assumption_2 == "The new supplier cannot deliver before March"
    assert sheet.prediction == "Defect rate at or below 2% on 2026-12-01"
    assert sheet.stop_signal == "Two batches in a row above 3%"
    assert sheet.still_unknown == "Their tooling cost — acceptable for now"


def test_parser_leest_een_veld_over_meerdere_regels():
    """Een aanname mag een alinea zijn; het veld loopt tot het volgende bekende label."""
    blok = _blok()
    blok = blok.replace("Assumption 1: The current defect rate stays under 2%",
                        "Assumption 1: The current defect rate stays under 2%\n"
                        "measured over the last three batches")
    assert "measured over the last three batches" in ds.parse(blok).assumption_1


def test_leeg_optioneel_veld_mag(tmp_path):
    """'Niets meer onbekend' is een geldige uitkomst — als enige van de zeven."""
    sheet = ds.parse(_blok(**{"Still unknown, and whether that is acceptable": ""}))
    assert sheet.still_unknown == ""


# ── 4, 5, 6: de weigeringen — en elke keer: er is niets geschreven ───────────

def _niets_geschreven(tmp_path) -> bool:
    return ds.alle(str(tmp_path)) == []


def test_ontbrekende_eindmarker_wordt_geweigerd(tmp_path):
    kapot = _blok().replace(ds.EIND, "")
    with pytest.raises(ds.Geweigerd) as e:
        ds.parse(kapot)
    assert ds.EIND in str(e.value)
    assert _niets_geschreven(tmp_path)


def test_lege_chosen_option_wordt_geweigerd(tmp_path):
    with pytest.raises(ds.Geweigerd) as e:
        ds.parse(_blok(**{"Chosen option": ""}))
    assert "Chosen option" in str(e.value)
    assert _niets_geschreven(tmp_path)


@pytest.mark.parametrize("marker", ["THINKING REPORT", "This report is for you only"])
def test_thinking_report_wordt_geweigerd(tmp_path, marker):
    """Privé is privé: weigeren, niet filteren. Filteren betekent dat het eerst binnen was."""
    with pytest.raises(ds.Geweigerd) as e:
        ds.parse(f"=== {marker} ===\nlots of private reasoning\n" + _blok())
    assert "private" in str(e.value).lower()
    assert _niets_geschreven(tmp_path)


def test_weigering_noemt_elk_ontbrekend_veld(tmp_path):
    with pytest.raises(ds.Geweigerd) as e:
        ds.parse(_blok(**{"Prediction (number and date)": "", "Stop signal": ""}))
    assert "Prediction (number and date)" in str(e.value) and "Stop signal" in str(e.value)


# ── het logboek ──────────────────────────────────────────────────────────────

def test_gelogde_rij_draagt_herkomst_en_het_rauwe_blok(tmp_path):
    rauw = _blok()
    rij = ds.log_sheet(str(tmp_path), ds.parse(rauw), decider="Stefan Wobben",
                       role="mother_earth__nooch__website_developer", raw=rauw)
    assert rij["source"] == ds.BRON and rij["template_version"] == "1"
    assert rij["decider"] == "Stefan Wobben"
    assert rij["raw"] == rauw                              # ongewijzigd bewaard
    op_schijf = ds.alle(str(tmp_path))
    assert len(op_schijf) == 1 and op_schijf[0]["chosen_option"] == rij["chosen_option"]


def test_alle_geeft_nieuwste_eerst(tmp_path):
    for i in range(3):
        ds.log_sheet(str(tmp_path), ds.parse(_blok(Decision=f"besluit {i}")),
                     decider="x", role="", raw="r")
    assert [r["decision"] for r in ds.alle(str(tmp_path))] == ["besluit 2", "besluit 1", "besluit 0"]


# ── 7: gelijktijdig schrijven ────────────────────────────────────────────────

def test_gelijktijdig_loggen_verliest_geen_regel(tmp_path):
    """Het dorp schrijft dit bestand vanuit de webserver: twee leden kunnen tegelijk op Log drukken.

    Zonder lock schrijven ze in elkaars regel en is het bestand daarna deels onleesbaar. Deze test
    is de reden dat `log_sheet` een `file_lock` neemt terwijl de andere jsonl-stores dat niet doen."""
    aantal = 12
    fouten: list[Exception] = []

    def schrijf(i):
        try:
            ds.log_sheet(str(tmp_path), ds.parse(_blok(Decision=f"besluit {i}")),
                         decider=f"mens {i}", role="", raw=_blok())
        except Exception as e:                             # noqa: BLE001
            fouten.append(e)

    draden = [threading.Thread(target=schrijf, args=(i,)) for i in range(aantal)]
    for d in draden:
        d.start()
    for d in draden:
        d.join()
    assert not fouten
    regels = [r for r in open(ds.pad(str(tmp_path)), encoding="utf-8").read().splitlines() if r]
    assert len(regels) == aantal                           # geen verloren regel
    for regel in regels:
        json.loads(regel)                                  # en geen half door elkaar geschreven regel
    assert len({r["decider"] for r in ds.alle(str(tmp_path))}) == aantal


# ── de pagina ────────────────────────────────────────────────────────────────

def test_pagina_rendert_zonder_sjabloon_en_zegt_dat(tmp_path):
    """Acceptatie: wie de pagina opent ziet het formulier, ook als het sjabloon ontbreekt — en
    leest waaróm er geen prompt staat in plaats van een lege doos."""
    from nooch_village.views.decision_coach import render_decision_coach
    html = render_decision_coach(None, base_dir=str(tmp_path), data_dir=str(tmp_path),
                                 csrf_token="t",
                                 waarden={"decision": "Switch?", "deadline": "2026-10-01",
                                          "options": "stay\nswitch"})
    assert "Decision coach" in html
    assert "Template not found" in html                    # fail-closed, zichtbaar
    assert "style=" not in html                            # designsysteem, geen inline opmaak


def test_pagina_toont_de_privacyafspraak_boven_het_logboek(tmp_path):
    from nooch_village.views.decision_coach import render_decision_coach
    html = render_decision_coach(None, base_dir=str(tmp_path), data_dir=str(tmp_path),
                                 csrf_token="t")
    assert "stays in your own chat" in html
    assert html.index("stays in your own chat") < html.index("Paste the decision sheet")


def test_pagina_toont_gelogde_sheets_van_iedereen(tmp_path):
    from nooch_village.views.decision_coach import render_decision_coach
    ds.log_sheet(str(tmp_path), ds.parse(_blok(Decision="besluit van een ander")),
                 decider="Lotte Mulder", role="", raw="r")
    html = render_decision_coach(None, base_dir=str(tmp_path), data_dir=str(tmp_path))
    assert "besluit van een ander" in html and "Lotte Mulder" in html


# ── de versie reist mee in het sheet, niet vanaf schijf ──────────────────────

def test_prompt_draagt_de_sjabloonversie(tmp_path):
    """Het sjabloon zet zijn eigen versie in het sheet, zodat de coach hem alleen hoeft te kopiëren."""
    base = _sjabloon(tmp_path, SJABLOON + "\nCoach version: {{template_version}}\n")
    prompt, _ = dc.bouw_prompt(base, {"decision": "x", "deadline": "y", "options": "z"})
    assert "Coach version: 1" in prompt


def test_sjabloon_zonder_marker_zet_unknown_in_de_prompt(tmp_path):
    base = _sjabloon(tmp_path, "# no marker\nCoach version: {{template_version}}\n")
    prompt, _ = dc.bouw_prompt(base, {})
    assert f"Coach version: {dc.ONBEKENDE_VERSIE}" in prompt


def test_versie_komt_uit_het_sheet_en_nooit_van_schijf(tmp_path):
    """DE KERN VAN DE DRIFT-FIX. Een sheet dat met v1 is gemaakt en vandaag wordt geplakt terwijl er
    v2 op schijf staat, logt v1. Zou de rij de schijfversie lezen, dan was het veld stilzwijgend
    fout — en dat is precies het veld waarop je over een half jaar vertrouwt zonder te controleren."""
    _sjabloon(tmp_path, "<!-- template_version: 2 -->\n# nieuwer sjabloon\n")
    sheet = ds.parse(_blok(**{"Coach version": "1"}))
    rij = ds.log_sheet(str(tmp_path), sheet, decider="x", role="", raw="r")
    assert rij["template_version"] == "1"
    assert dc.versie(str(tmp_path)) == "2"                 # op schijf staat iets anders, en dat blijft zo


def test_sheet_zonder_coach_version_logt_unknown(tmp_path):
    sheet = ds.parse(_blok(**{"Coach version": ""}))
    assert sheet.template_version == dc.ONBEKENDE_VERSIE
    rij = ds.log_sheet(str(tmp_path), sheet, decider="x", role="", raw="r")
    assert rij["template_version"] == "unknown"


def test_log_sheet_heeft_geen_versie_parameter():
    """Een parameter zou de terugval één aanroeper verderop gewoon weer mogelijk maken."""
    import inspect
    assert "template_version" not in inspect.signature(ds.log_sheet).parameters


# ── de rolkeuze bij het loggen ───────────────────────────────────────────────

def test_een_rol_wordt_ingevuld_zonder_vraag(tmp_path):
    from nooch_village.views.decision_coach import render_decision_coach
    html = render_decision_coach(None, base_dir=str(tmp_path), data_dir=str(tmp_path),
                                 csrf_token="t", rollen=[("rol_a", "Website Developer")])
    assert "Logged from your role" in html and "Website Developer" in html
    assert "name='rol' value='rol_a'" in html
    assert "Which role did you decide from?" not in html


def test_meer_rollen_dwingt_een_keuze_af(tmp_path):
    from nooch_village.views.decision_coach import render_decision_coach
    html = render_decision_coach(None, base_dir=str(tmp_path), data_dir=str(tmp_path),
                                 csrf_token="t", rollen=[("rol_a", "Website Developer"),
                                                         ("rol_b", "Strategic Lead")])
    assert "Which role did you decide from?" in html
    assert html.count("type='radio' id='dc-rol-") == 2
    assert "checked" not in html                           # geen voorgekozen rol = geen gok


def test_geen_rollen_geeft_een_leeg_veld(tmp_path):
    from nooch_village.views.decision_coach import render_decision_coach
    html = render_decision_coach(None, base_dir=str(tmp_path), data_dir=str(tmp_path),
                                 csrf_token="t", rollen=[])
    assert "name='rol' value=''" in html


# ── vindbaarheid: de tool hangt onder een rol ────────────────────────────────

def test_tool_wordt_idempotent_op_de_rol_gezet(tmp_path):
    from nooch_village import cockpit2
    from nooch_village.views.decision_coach import TOOL_ROL, TOOL_TITEL, zorg_voor_tool
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    eerste = zorg_voor_tool(st.records, st.att)
    assert eerste and zorg_voor_tool(st.records, st.att) == eerste      # idempotent
    tools = [a for a in st.att.list(TOOL_ROL, "tool") if a.title == TOOL_TITEL]
    assert len(tools) == 1 and tools[0].url == "/decision-coach"


def test_tool_op_een_onbekende_rol_faalt_zacht(tmp_path):
    from nooch_village import cockpit2
    from nooch_village.views.decision_coach import zorg_voor_tool
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    assert zorg_voor_tool(st.records, st.att, "bestaat_niet") == ""


# ── de stabiele id ───────────────────────────────────────────────────────────

def test_twee_sheets_in_dezelfde_seconde_krijgen_verschillende_ids(tmp_path):
    """Zonder id is `timestamp + decider` de enige onderscheiding, en die is niet uniek: twee
    besluiten van dezelfde persoon binnen één seconde zijn dan hetzelfde besluit. De id is het
    handvat waarmee je in een werkoverleg naar één rij kunt wijzen."""
    import time as _t
    vast = 1789000000.0
    eerder = _t.time
    _t.time = lambda: vast                                 # dezelfde seconde afdwingen
    try:
        a = ds.log_sheet(str(tmp_path), ds.parse(_blok(Decision="eerste")),
                         decider="Stefan Wobben", role="rol_a", raw="r")
        b = ds.log_sheet(str(tmp_path), ds.parse(_blok(Decision="tweede")),
                         decider="Stefan Wobben", role="rol_a", raw="r")
    finally:
        _t.time = eerder
    assert a["timestamp"] == b["timestamp"] and a["decider"] == b["decider"]
    assert a["id"] and b["id"] and a["id"] != b["id"]
    rijen = ds.alle(str(tmp_path))
    assert len(rijen) == 2
    assert all(r.get("id") for r in rijen)                 # elke rij draagt er een
    assert len({r["id"] for r in rijen}) == 2


def test_de_id_staat_zichtbaar_en_kopieerbaar_op_de_kaart(tmp_path):
    """Een id die alleen in het bestand staat is een databasesleutel, geen handvat."""
    from nooch_village.views.decision_coach import render_decision_coach
    rij = ds.log_sheet(str(tmp_path), ds.parse(_blok()), decider="Stefan Wobben", role="", raw="r")
    html = render_decision_coach(None, base_dir=str(tmp_path), data_dir=str(tmp_path))
    assert rij["id"] in html
    assert f"data-dc-id='{rij['id']}'" in html             # kopieerknop wijst naar deze id
