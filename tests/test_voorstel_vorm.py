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


def test_de_synthese_krijgt_de_grond_boven_indruk_regel():
    """Op de tweede herdraai zakte het voorstel terecht: het noemde 'bio-based of gerecyclede
    materialen' als alternatief terwijl geen enkele bron zei welke materialen Nooch gebruikt. Als
    die interne kennis nergens in een skill zit, is het gegronde voorstel niet een verzonnen
    richting maar 'verwijder de term' of 'geef me de concrete invulling, dan verifieer ik hem'."""
    src = open("nooch_village/onderzoekspas.py", encoding="utf-8").read()
    assert "GROND VERSLAAT INDRUK" in src
    assert "schrappen" in src and "niet te onderbouwen" in src
    assert "hoe redelijk het ook klinkt" in src


# ── 6. De gereduceerde grond-toets: scope-correctie, geen versoepeling ──────

def test_de_grond_as_ziet_alleen_de_velden_die_beweringen_dragen():
    """Een risico is een hypothese, `onzeker` is per constructie een niet-bewering. Ze op
    feitelijke gegrondheid toetsen laat élk voorstel zakken ongeacht kwaliteit — geen strenge
    poort maar een kapotte. Gemeten: het debuut zakte er drie keer op."""
    kern = vv.feitelijke_kern(GEGROND)
    assert "Wat ik wil doen" in kern and "Waarom, met bewijs" in kern
    assert "Risico of kosten" not in kern and "Wat nog onzeker is" not in kern
    assert vv.DRAAGT_BEWERINGEN == ("actie", "bewijs")


def test_de_grond_as_ziet_alles_maar_beoordeelt_de_kern():
    """Zien, niet beoordelen. Een kleiner document meegeven leek net, maar dan mist de toets context
    en vráágt hij om wat je zojuist verborg: "voeg een expliciete risicoparagraaf toe" — terwijl die
    er stond. Gemeten op prod. Eén categoriefout ingeruild voor een andere."""
    from nooch_village import onderzoekspas as op
    gezien = {}

    class _Vangt:
        def run(self, payload, context=None):
            gezien.update(payload)
            return {"ok": True, "oordeel": "houdt stand", "ongegrond": []}

    op.poort(dict(GEGROND), project={"id": "p"}, skill=_Vangt())
    assert "Risico of kosten" in gezien["tekst"]              # het hele voorstel gaat mee…
    assert "Reken ze niet als ongegronde bewering" in gezien["kader"]     # …met de leesregel
    assert "Vraag er ook niet om" in gezien["kader"]
    assert "hoort in de actie of het bewijs" in gezien["kader"]           # geen dumpplek


def test_een_einddocument_merkt_niets_van_deze_optie():
    """De parameter is default-transparant: zonder `kader_extra` leest de as precies zoals op het
    einddocument."""
    from nooch_village import missie_critic as mc
    gezien = {}

    class _Vangt:
        def run(self, payload, context=None):
            gezien.update(payload)
            return {"ok": True, "oordeel": "houdt stand", "ongegrond": []}

    doc = "# R\n\n## Onderzoek plasticvrije materialen\n" + "plasticvrij vegan transparantie. " * 30
    mc.beoordeel(project={}, document=doc, deliverables=[{"id": "", "summary": "x"}],
                 checklist=None, skill=_Vangt())
    assert gezien["tekst"] == doc
    assert "VOORSTEL van een rol" not in gezien["kader"]


# ── DE acceptatietest: doel gecorrigeerd, lat niet verlaagd ────────────────

_EERLIJK = {
    "soort": vv.SOORT_VOORSTEL,
    "actie": "Mijn voorstel: verwijder de term 'conscious/bewust' uit de live tekst totdat er een "
             "concrete onderbouwing is.",
    "bewijs": [{"bron": "claims_check", "citaat": "bevindingen[0].stoplicht = orange", "kroniek": "a1"},
               {"bron": "claims_check", "citaat": "bevindingen[0].waarom = Modejargon zonder inhoud.",
                "kroniek": "a1"}],
    "risico": "Schrappen zonder vervangtekst kan de copy tijdelijk minder krachtig maken.",
    "nodig_van_jou": "",
    "onzeker": "Ik heb geen concrete invulling kunnen vaststellen — claim_evidence gaf counts.leeg=1.",
}

_OVERREACH = {**_EERLIJK,
              "actie": "Mijn voorstel: vervang 'conscious' door een verwijzing naar de bio-based en "
                       "gerecyclede materialen die Nooch gebruikt."}


def test_het_eerlijke_voorstel_houdt_zijn_risico_buiten_de_grond_toets():
    """Kant 1: het risico-veld dat de as drie keer liet zakken komt er niet meer in."""
    kern = vv.feitelijke_kern(_EERLIJK)
    assert "minder krachtig" not in kern
    assert "verwijder de term" in kern


def test_de_overreach_blijft_wel_in_de_grond_toets():
    """Kant 2, en dit is waar het om draait: de verzonnen materiaalrichting staat in de ACTIE, dus
    die blijft de grond-as passeren. Zou hij hier wegvallen, dan was de poort gebroken in plaats van
    gecorrigeerd."""
    kern = vv.feitelijke_kern(_OVERREACH)
    assert "bio-based en gerecyclede materialen die Nooch gebruikt" in kern


def test_een_dragend_feit_in_risico_ontsnapt_en_de_prompt_verbiedt_dat():
    """De sluiproute, expliciet benoemd. De reductie kan niet afdwingen dat een feit op de juiste
    plek staat; de synthese-prompt moet dat doen, en die instructie hoort er hard in te staan."""
    sluip = {**_EERLIJK, "risico": "Nooch gebruikt uitsluitend mycelium en gerecycled PET."}
    assert "mycelium" not in vv.feitelijke_kern(sluip)         # ontsnapt inderdaad
    src = open("nooch_village/onderzoekspas.py", encoding="utf-8").read()
    assert "VOORWAARDELIJKE vorm" in src
    assert "hoort in de actie of in het bewijs, niet hier" in src
    assert "Negatieve " in src and "niet wat waar is" in src


# ── 7. De opdracht is toelaatbaar bewijs — context, geen vrijbrief ──────────

def test_de_gegeven_feiten_van_de_opdracht_gaan_mee_als_bewijs():
    """`ec4e5e0b0fc0` zakte op "de onderbouwing noemt geen paginalocatie of FAQ" terwijl de FAQ-URL
    letterlijk in de opdracht staat. De opdracht is een gegeven; hem uitsluiten is toetsen met te
    weinig materiaal — dezelfde soort fout als [:8]/[:600] op het bewijsvenster."""
    from nooch_village import onderzoekspas as op
    project = {"id": "p", "scope": "🔴 Vervang: good for the planet", "done_when": "live en gezien",
               "checklists": [{"items": [{"text": "Onderzoek de tekst op https://nooch.earth/pages/faq"}]}]}
    gegeven = op.gegeven_van(project)
    assert "good for the planet" in gegeven and "nooch.earth/pages/faq" in gegeven

    gezien = {}

    class _Vangt:
        def run(self, payload, context=None):
            gezien.update(payload)
            return {"ok": True, "oordeel": "houdt stand", "ongegrond": []}

    op.poort(dict(GEGROND), project=project, skill=_Vangt())
    assert "GEGEVEN IN DE OPDRACHT" in gezien["bewijs"]
    assert "nooch.earth/pages/faq" in gezien["bewijs"]


def test_de_opdracht_is_context_geen_vrijbrief():
    """De strakke afbakening. 'De claim staat op de FAQ-pagina' is gegrond als de opdracht die
    pagina noemt; 'de FAQ-pagina zegt X' heeft nog steeds een deliverable nodig die dat ophaalde."""
    assert "de opdracht is een feit" in vv.KADER_VOORSTEL
    assert "maakt BEWERINGEN OVER die gegevens niet gegrond" in vv.KADER_VOORSTEL
    assert "heeft een deliverable nodig" in vv.KADER_VOORSTEL
    assert "Context, geen vrijbrief" in vv.KADER_VOORSTEL


def test_zonder_gegeven_verandert_er_niets_voor_het_einddocument():
    from nooch_village import missie_critic as mc
    gezien = {}

    class _Vangt:
        def run(self, payload, context=None):
            gezien.update(payload)
            return {"ok": True, "oordeel": "houdt stand", "ongegrond": []}

    doc = "# R\n\n## Onderzoek plasticvrije materialen\n" + "plasticvrij vegan transparantie. " * 30
    mc.beoordeel(project={}, document=doc, deliverables=[{"id": "", "summary": "x"}],
                 checklist=None, skill=_Vangt())
    assert "GEGEVEN IN DE OPDRACHT" not in gezien["bewijs"]


def test_de_synthese_krijgt_de_discipline_regel():
    """De degradaties kwamen niet van verzonnen acties — die waren in alle vier bewijs-getrouw — maar
    van toegevoegde interpretatie, oorzaak en implicatie: wat score=100 betekent, waarom een bron
    leeg bleef, een zijstap naar 'gerecycled' terwijl de opdracht over 'plastic free' ging."""
    src = open("nooch_village/onderzoekspas.py", encoding="utf-8").read()
    assert "leg niets uit, veronderstel niets en impliceer niets" in src
    assert "Bij twijfel: laat het weg" in src
    assert "Leaner en volledig" in src and "verslaat rijk en gedegradeerd" in src


# ── 8. De wachtrij toont wat geldt, niet elke poging ────────────────────────

def test_de_wachtrij_toont_alleen_de_laatste_meting_per_project(tmp_path):
    """`voorstellen.jsonl` is append-only — dat is goed voor de meetreeks, niet voor een wachtrij.
    Na de tuning-rondes stonden er 46 regels voor 30 claims, met een gedegradeerde versie van
    `conscious` naast de versie die er wél doorheen kwam. Zelfde vorm als `vervangen_door` bij de
    deliverables: niets wissen, alleen de leesweg corrigeren."""
    from nooch_village import founder_taken as ft, onderzoekspas as op
    dd = str(tmp_path)
    for n, soort in enumerate(("bevinding", "bevinding", "voorstel")):
        op.leg_vast(dd, project_id="p1", rol="compliance", vraag="v",
                    voorstel={"soort": soort, "actie": f"actie {n}", "bewijs": []},
                    oordeel={"oordelen": {"gegrond": soort == "voorstel"}})
    op.leg_vast(dd, project_id="p2", rol="compliance", vraag="v",
                voorstel={"soort": "bevinding", "actie": "x", "bewijs": []},
                oordeel={"oordelen": {"gegrond": False}})

    assert len(op.alle(dd)) == 4                      # de historie blijft volledig
    items = ft._voorstel_items(None, dd)
    assert len(items) == 2                            # de wachtrij toont twee projecten
    p1 = next(i for i in items if "p1" in str(i["link"]) or True)
    assert any(i["ai"] == "bevestig" for i in items)  # de laatste van p1 is het voorstel
    assert sum(1 for i in items if i["ai"] is None) == 1
