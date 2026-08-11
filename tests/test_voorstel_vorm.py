"""De vaste voorstel-vorm, de pre-check en de degradatie.

Dit staat er vóór de onderzoekspas zelf, met opzet. De hele week draaide om één les: een systeem dat
iets niet kan onderbouwen moet dat zéggen. Een zelfverzekerde aanbeveling die nergens op rust is
erger dan geen aanbeveling — de founder kan de twee niet uit elkaar houden en beslist er wel op.

Twee poorten, allebei vóór de founder:
  1. pre-check: een menu verpakt als voorstel gaat terug voor nog een onderzoekspas;
  2. degradatie: zakt de gegrond-as, dan vervalt de AANBEVELING, niet de bevindingen.
"""
from __future__ import annotations

import pytest

from nooch_village import voorstel_vorm as vv

GEGROND = {
    "soort": vv.SOORT_VOORSTEL,
    "actie": "Vervang 'conscious' op de FAQ-pagina door 'wij kiezen materialen op herkomst en "
             "afbreekbaarheid' en noem daarbij de twee leveranciers.",
    "bewijs": [{"bron": "claims_check", "citaat": "term 'conscious' → stoplicht orange, categorie Generiek",
                "kroniek": "abc123"}],
    "risico": "De herformulering is langer en past mogelijk niet in de bestaande kop.",
    "nodig_van_jou": "",
    "onzeker": "Of de tweede leverancier genoemd mag worden — dat contract kan ik niet inzien.",
}


# ── 1. De pre-check: een menu is geen voorstel ──────────────────────────────

def test_een_gegrond_voorstel_gaat_door():
    assert vv.keur(GEGROND) == (True, "")


@pytest.mark.parametrize("actie,fragment", [
    ("Wil je dat ik de claim vervang of laat staan?", "vraag"),
    ("Zullen we 'conscious' herformuleren of eerst juridisch laten toetsen?", "vraag"),
    ("Zullen we 'conscious' herformuleren, of eerst juridisch laten toetsen.", "beslissing"),
    ("Graag je input op de drie varianten hieronder.", "beslissing"),
    ("Herformuleren.", "geen concrete actie"),
])
def test_een_menu_verpakt_als_voorstel_wordt_afgewezen(actie, fragment):
    """Precies de route die we vervangen: de founder kreeg een menu en moest zelf het werk doen."""
    ok, waarom = vv.keur({**GEGROND, "actie": actie})
    assert ok is False and fragment in waarom


def test_een_voorstel_zonder_bron_is_een_mening():
    ok, waarom = vv.keur({**GEGROND, "bewijs": []})
    assert ok is False and "mening" in waarom


def test_bewijs_zonder_bronveld_telt_niet():
    assert vv.heeft_bewijs({"bewijs": [{"citaat": "iets"}]}) is False
    assert vv.heeft_bewijs({"bewijs": [{"bron": "claims_check", "citaat": "x"}]}) is True


# ── 2. De kale vraag: alleen met een concreet gebrek ────────────────────────

def test_een_kale_vraag_mag_alleen_met_het_concrete_gebrek():
    """Zelfde discipline als de payload-reparatie: eerst zelf proberen, pas escaleren met wát er
    precies ontbreekt — niet 'ik heb je input nodig'."""
    vraag = vv.als_vraag(GEGROND, "het leverancierscontract staat niet in een bron die ik kan lezen")
    assert vraag["soort"] == vv.SOORT_VRAAG
    assert vv.keur(vraag) == (True, "")

    leeg = vv.als_vraag(GEGROND, "")
    ok, waarom = vv.keur(leeg)
    assert ok is False and "menu" in waarom


# ── 3. De degradatie: bevindingen blijven, de aanbeveling vervalt ───────────

def test_degradatie_haalt_de_aanbeveling_weg_en_houdt_het_bewijs():
    """DE regel. Wat de skills ophaalden is echt en hoort de founder te bereiken; de aanbeveling is
    wat de critic niet gedekt vond, dus die vervalt."""
    uit = vv.degradeer(GEGROND, "geen bron dekt de claim dat afbreekbaarheid is vastgesteld")
    assert uit["soort"] == vv.SOORT_BEVINDING
    assert "Geen aanbeveling" in uit["actie"]
    assert uit["bewijs"] == GEGROND["bewijs"]                 # bevindingen ongemoeid
    assert uit["risico"] == GEGROND["risico"]


def test_degradatie_bewaart_wat_er_stond_zodat_het_leerbaar_blijft():
    uit = vv.degradeer(GEGROND, "reden")
    assert uit["gedegradeerd_van"].startswith("Vervang 'conscious'")
    assert uit["waarom_gedegradeerd"] == "reden"


def test_degradatie_maakt_de_open_vraag_expliciet():
    """Niet 'wat wil je', maar 'wat ontbreekt om dit wél te kunnen zeggen'."""
    uit = vv.degradeer(GEGROND, "geen LCA of certificering gevonden")
    assert "Wat ontbreekt om dit te onderbouwen: geen LCA" in uit["onzeker"]
    assert GEGROND["onzeker"] in uit["onzeker"]                # de eigen onzekerheid blijft staan


def test_een_gedegradeerd_voorstel_is_zichtbaar_gedegradeerd():
    """De founder moet in één oogopslag zien dat dit geen aanbeveling is."""
    tekst = vv.render(vv.degradeer(GEGROND, "reden"))
    assert tekst.startswith("⚠️ GEDEGRADEERD")


def test_degradatie_raakt_het_origineel_niet_aan():
    origineel = dict(GEGROND)
    vv.degradeer(GEGROND, "reden")
    assert GEGROND == origineel


# ── 4. De vaste vorm ────────────────────────────────────────────────────────

def test_de_vorm_heeft_vijf_velden_in_leesvolgorde():
    assert vv.VELDEN == ("actie", "bewijs", "risico", "nodig_van_jou", "onzeker")


def test_render_toont_de_bron_en_de_kroniek_verwijzing():
    tekst = vv.render(GEGROND)
    assert "claims_check: term 'conscious' → stoplicht orange" in tekst
    assert "[kroniek:abc123]" in tekst


def test_een_leeg_nodig_van_jou_valt_weg():
    """Een voorstel dat altijd iets van de founder vraagt is weer een menu."""
    assert "Wat ik van je nodig heb" not in vv.render(GEGROND)
    met = vv.render({**GEGROND, "nodig_van_jou": "toegang tot het leverancierscontract"})
    assert "Wat ik van je nodig heb" in met


# ── 5. De drie bedradingsfixes uit het debuut ───────────────────────────────

def test_de_payload_komt_uit_het_schema_niet_uit_een_gok():
    """Op het debuut gaf de pas een vaste {text, term, claim, query} mee. Bij `claim_evidence`
    paste dat niet ("geef brands (niet-leeg) en een claim op"), dus draaide juist de bron níet die
    de concrete actie had kunnen leveren — en het voorstel rustte op één bron."""
    from unittest.mock import patch
    from types import SimpleNamespace
    from nooch_village import onderzoekspas as op

    class _Skill:
        input_schema = "brands: list (verplicht); claim: str (verplicht)"
        required_payload = ("brands", "claim")

    gezien = {}

    class _Inh:
        registry = SimpleNamespace(get=lambda naam: _Skill())

        def _payload_opnieuw(self, skill, tekst, schema, mist, huidig):
            gezien.update({"schema": schema, "mist": list(mist)})
            return {"brands": ["nooch"], "claim": tekst}

        def _missing_required(self, skill, payload):
            return [f for f in _Skill.required_payload if not payload.get(f)]

        def _payload_issues(self, skill, payload):
            return []

    payload, waarom = op._payload_voor(_Inh(), "claim_evidence", "is 'conscious' onderbouwd?")
    assert payload == {"brands": ["nooch"], "claim": "is 'conscious' onderbouwd?"}
    assert waarom == ""
    assert gezien["schema"].startswith("brands:")          # het schema stuurt, niet een gok
    assert gezien["mist"] == ["brands", "claim"]


def test_een_payload_die_de_poort_niet_haalt_wordt_gemeld_niet_gedraaid():
    """Fail-closed én niet stil: wat wegvalt staat in `overgeslagen` en reist mee naar het voorstel."""
    from types import SimpleNamespace
    from nooch_village import onderzoekspas as op

    class _Inh:
        registry = SimpleNamespace(get=lambda naam: SimpleNamespace(
            input_schema="brands: list", required_payload=("brands",)))

        def _payload_opnieuw(self, *a):
            return {"iets_anders": 1}

        def _missing_required(self, skill, payload):
            return ["brands"]

        def _payload_issues(self, skill, payload):
            return []

    payload, waarom = op._payload_voor(_Inh(), "claim_evidence", "vraag")
    assert payload is None and "haalt de poort niet" in waarom and "brands" in waarom


def test_de_critic_krijgt_een_voorstel_eigen_doel():
    """`done_when` van het project ("de herformulering is live en door legal gezien") is het
    UITVOERINGSdoel. De grond-as rekende het niet-bereikt-zijn daarvan aan als ongegronde bewering.
    Leegmaken mag ook niet: dan slaagt de beantwoordt-as leeg."""
    from nooch_village import onderzoekspas as op
    gezien = {}

    class _Vangt:
        def run(self, payload, context=None):
            gezien["doel"] = payload.get("doel")
            return {"ok": True, "oordeel": "houdt stand", "ongegrond": []}

    project = {"id": "p", "done_when": "de herformulering is live en door legal gezien",
               "dod_outcome": "live"}
    op.poort({**GEGROND}, project=project, skill=_Vangt())
    assert gezien["doel"] == op.VOORSTEL_DOEL
    assert "live" not in gezien["doel"]
    assert op.VOORSTEL_DOEL.strip() != ""                  # niet leeg: anders meet de as niets
    assert project["done_when"] == "de herformulering is live en door legal gezien"   # origineel heel


def test_de_synthese_vraagt_om_een_aanbeveling_geen_voltooide_handeling():
    """De tweede critic-reden was terecht: "Ik geef opdracht aan copywriter" stelt de actie als
    genomen — een bewering over de werkelijkheid die geen bewijs draagt."""
    src = open("nooch_village/onderzoekspas.py", encoding="utf-8").read()
    assert "Mijn voorstel: " in src
    assert "ik geef opdracht" in src and "ik heb vervangen" in src


def test_het_voorstel_doel_is_toetsbaar_op_de_vaste_vorm():
    """`_beantwoordt` meet woord-overlap. Een doel dat abstract beschrijft wát een voorstel is
    ("onderbouwd", "welke wijziging") haalt die overlap nooit en laat de as op ELK voorstel zakken
    — gemeten toen ik het eerst zo formuleerde. In de woorden van de vorm toetst de as iets echts:
    zijn de velden gevuld?"""
    from nooch_village import missie_critic as mc, onderzoekspas as op
    doc = vv.render(GEGROND)
    assert mc._beantwoordt(doc, {"done_when": op.VOORSTEL_DOEL}, None)[0] is True
    kaal = vv.render({**GEGROND, "risico": "", "onzeker": "", "bewijs": []})
    assert mc._beantwoordt(kaal, {"done_when": op.VOORSTEL_DOEL}, None)[0] is False


def test_een_bondig_voorstel_zakt_niet_op_lengte():
    """`MIN_DOCUMENT_CHARS` (400) is op een einddocument gekalibreerd. Een voorstel is vijf velden,
    geen rapport; daarop afrekenen is een stille cap van precies de soort die we hebben weggehaald."""
    from nooch_village import missie_critic as mc, onderzoekspas as op
    assert op.MIN_VOORSTEL_CHARS < mc.MIN_DOCUMENT_CHARS
    kort = vv.render(GEGROND)[:200]
    assert mc._substantieel(kort, [{"x": 1}], None, op.MIN_VOORSTEL_CHARS)[0] is True
    assert mc._substantieel(kort, [{"x": 1}], None)[0] is False        # met de rapport-lat wél
    assert mc._substantieel("kort", [{"x": 1}], None, op.MIN_VOORSTEL_CHARS)[0] is False
