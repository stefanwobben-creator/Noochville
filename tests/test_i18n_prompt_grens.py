"""De grens tussen i18n-batch 2A (stem) en 2C (enum-prompts mét parser).

2A heeft de STEM naar het Engels gebracht: de missietekst, de persona-preamble en de vrije-tekst-
prompts. Bewust NIET vertaald zijn de prompts waarvan een parser een NEDERLANDS antwoord-token
verwacht — die gaan pas om samen met hun parser (2C), anders valt de parsing stil om.

Deze test is de vangrail op die afspraak. Hij faalt zodra iemand één kant van zo'n paar vertaalt:
- vertaal je het prompt-token, dan mist de assert hier → je ziet meteen dat de parser mee moet;
- doe je 2C netjes (prompt + parser samen), dan pas je deze test in dezelfde commit aan en is de
  lijst weer waar.

Het is dus expliciet GEEN test die zegt "Nederlands moet blijven" — het is er een die zegt
"prompt en parser horen bij elkaar".
"""
from __future__ import annotations

import pathlib

from nooch_village.personas import Persona, persona_prompt

_PKG = pathlib.Path(__file__).resolve().parent.parent / "nooch_village"


def _src(naam: str) -> str:
    return (_PKG / naam).read_text(encoding="utf-8")


# ── 2C-werklijst: prompt-token ↔ parser die het leest ────────────────────────────────────────────

def test_mention_triage_enum_blijft_bij_zijn_parser():
    """2C gedaan op 06-09-2026: de prompt vraagt Engelse enum-waarden (yes|partly|no) en de parser
    is in dezelfde commit liberaal gemaakt — hij normaliseert BEIDE talen naar de interne waarden.

    Waarom liberaal en niet strikt omzetten: bij een niet-herkende waarde geeft `_parse_triage` None
    terug en valt de caller terug op een platte reactie. De triage verdwijnt dan geruisloos, zonder
    fout. Een model dat in het Nederlands doorschiet mag dat niet veroorzaken. Zelfde afweging als
    bij project_worker hieronder.

    De INTERNE waarden blijven Nederlands: de rest van cockpit2 hangt op `fit == "nee"`. Vertalen we
    die mee, dan moet elke consument mee in dezelfde commit — dat is 2E, niet dit."""
    s = _src("cockpit2.py")
    assert '\\"fit\\": \\"yes|partly|no\\"' in s or '"fit": "yes|partly|no"' in s
    assert '"yes": "ja"' in s and '"partly": "deels"' in s and '"no": "nee"' in s
    assert '"ja": "ja"' in s                     # overgangs-tolerantie blijft
    assert 'if fit == "nee"' in s                # de consument leest nog de interne waarde


def test_project_worker_contract_is_engels():
    """work_one is volledig om (2C): prompt Engels ÉN markers Engels. Dat mag hier, want de markers
    zijn vluchtige parse-tokens — ze worden gestript vóór het returnen, staan nergens opgeslagen en
    niets vergelijkt erop. Zo vecht de prompt niet meer tegen z'n eigen taal."""
    s = _src("project_worker.py")
    assert "CANNOT: <what is needed for that>" in s
    assert "DELIVER: <your concrete outcome or next step>" in s
    assert "KAN NIET:" not in s.split("def work_one")[1]     # niet meer voorgeschreven in de prompt


def test_project_worker_parser_blijft_liberaal():
    """Beide talen worden herkend. De Engelse is het contract; de Nederlandse is overgangs-
    tolerantie. Missen we een marker, dan valt het antwoord STIL door naar de deliverable-tak en
    wordt een geblokkeerd project als afgerond weggeschreven — daarom liberaal parsen."""
    from nooch_village.project_worker import work_one
    assert work_one("x", "r", "p", llm_reason=lambda _p: "CANNOT: a key") == {
        "ok": False, "needs": "a key"}
    assert work_one("x", "r", "p", llm_reason=lambda _p: "KAN NIET: een sleutel") == {
        "ok": False, "needs": "een sleutel"}
    assert work_one("x", "r", "p", llm_reason=lambda _p: "DELIVER: done")["outcome"] == "done"
    assert work_one("x", "r", "p", llm_reason=lambda _p: "LEVER: af")["outcome"] == "af"


def test_opportunity_reflex_velden_blijven_bij_hun_parser():
    """2C gedaan op 06-09-2026: prompt vraagt TITLE/WHAT/WHY, parser leest beide talen.

    De verboden-woordenlijst is VERTAALD en niet geschrapt. Dat is geen stijlvoorkeur maar merkstem:
    elk woord op die lijst ('conversie', 'doelgroep', 'consument') verandert een mens in een
    transactie, en dat is precies het frame dat Nooch niet voert. Een prompt die om gewone taal
    vraagt zonder te zeggen wélke woorden fout zijn, is de helft van de instructie."""
    s = _src("inhabitant.py")
    assert "TITLE:" in s and "WHAT:" in s and "WHY:" in s
    assert 'key in ("titel", "title")' in s and 'key in ("wat", "what")' in s
    assert 'key in ("waarom", "why"' in s
    assert "target audience" in s and "consumer" in s          # de lijst is mee, niet weg
    assert "CITIZEN frame" in s


def test_noochie_weigh_in_velden_blijven_bij_hun_parser():
    """2C gedaan op 06-09-2026: prompt vraagt FINDING/QUESTION + verdict 'off_mission'.

    De INTERNE waarde blijft `niet_ok`: die wordt vergeleken in `_weigh_in` én opgeslagen in het
    dagrapport (`_persist_daily`). Meevertalen zou bestaande rapporten in de cockpit een onbekend
    oordeel geven — een migratie voor niets. Dus normaliseren aan de rand, niet doorvoeren."""
    s = _src("roles.py")
    assert "FINDING:" in s and "QUESTION:" in s and "off_mission" in s
    assert 'verdict = "niet_ok"' in s                           # genormaliseerd naar de interne waarde
    assert 'low.startswith("bevinding") or low.startswith("finding")' in s


# ── 2A-belofte: de stem is Engels én laat machine-tokens met rust ────────────────────────────────

def test_persona_preamble_is_engels_met_vangrail():
    """De preamble gaat vóór de prompts hierboven. Hij stuurt op Engels proza, maar zegt er
    expliciet bij dat voorgeschreven veldwaarden/markers letterlijk overgenomen worden — anders
    zou hij precies de tokens vertalen die de parsers hierboven nodig hebben."""
    pr = persona_prompt(Persona(id="x", name="Sid", mbti="INTJ", instructions="Nuchter."))
    assert "Always respond in English." in pr
    assert "reproduce those EXACTLY as given" in pr
    assert pr.startswith("You are Sid (INTJ).")


def test_missie_is_engels():
    from nooch_village.mission import ANCHOR_PURPOSE
    assert "most sustainable shoe brand" in ANCHOR_PURPOSE
    assert "duurzaamste" not in ANCHOR_PURPOSE


def test_strategie_themas_zijn_tweetalig():
    """2D gedaan op 06-09-2026, maar ADDITIEF: Engels erbij, Nederlands blijft.

    Dit is een deterministische match op losse woorden, en het dorp draagt twee talen tegelijk —
    nieuwe content Engels, alles wat er al lag Nederlands. Kies je één taal, dan scoort de helft van
    de kennisbank stil op nul. Zou iemand de Nederlandse tokens ooit opruimen 'omdat we Engels zijn',
    dan verliest élke bestaande kaart met terugwerkende kracht zijn strategie-score, zonder melding.
    Vandaar dat beide kanten hier apart worden vastgelegd."""
    from nooch_village.mission import STRATEGIE_THEMAS, strategie_relevantie
    assert "geen plastic" in STRATEGIE_THEMAS

    nl = "Deze zool is composteerbaar en bevat geen plastic, gemaakt op bestelling in Portugal."
    en = "This sole is compostable and contains no plastic, made to order in Portugal."
    n_nl, l_nl = strategie_relevantie(nl)
    n_en, l_en = strategie_relevantie(en)
    assert n_nl == 4 and n_en == 4, f"NL={n_nl} EN={n_en} — geen pariteit"
    assert set(l_nl) == set(l_en), "dezelfde inhoud hoort dezelfde thema's te raken"


def test_elk_thema_kent_beide_talen():
    """Per thema minstens één herkenbaar Engels én één Nederlands trefwoord.

    Een thema dat maar één taal kent is de stille versie van het probleem hierboven: hij lijkt te
    werken tot er content in de andere taal langskomt."""
    from nooch_village.mission import STRATEGIE_THEMAS
    ijk = {
        "geen plastic": ("aardolie", "petrochemical"),
        "geen leer": ("leer", "leather"),
        "afbreekbaar & biobased": ("afbreekbaar", "biodegradable"),
        "in europa geproduceerd": ("fabriek", "factory"),
        "op bestelling": ("voorraad", "inventory"),
        "eerlijk werk & prijs": ("loon", "wages"),
        "transparantie": ("herkomst", "provenance"),
    }
    assert set(ijk) == set(STRATEGIE_THEMAS), "thema toegevoegd of hernoemd zonder ijkwoorden"
    for thema, (nl_woord, en_woord) in ijk.items():
        toks = STRATEGIE_THEMAS[thema]
        assert nl_woord in toks, f"{thema}: Nederlands ijkwoord '{nl_woord}' weg"
        assert en_woord in toks, f"{thema}: Engels ijkwoord '{en_woord}' ontbreekt"


# ── De laatste Nederlandse prompt, en de vangrail eronder ────────────────────────────────────────

def test_wizard_title_vraagt_in_het_engels():
    """GEMETEN AANLEIDING (6 sept, eerste echte gebruik na #466). `sharpen_outcome` ging om, maar
    `title_from` niet. Er ging een Engelse uitkomst in en er kwam "Barefoot sneaker trend onderzoek
    afgerond" uit: half Engels, half Nederlands, boven aan de projectkaart.

    Een model antwoordt in de taal waarin je het VRAAGT, ook als de invoer een andere taal heeft.
    De invoer is materiaal, de prompt is de opdracht. Daarom staat de taalregel expliciet in de
    prompt en niet impliciet in de invoer."""
    s = _src("wizard.py")
    blok = s.split("def title_from")[1].split("def ")[0]
    assert "Always answer in English" in blok
    assert "OUTCOME:" in blok and "UITKOMST:" not in blok
    assert "Vat deze" not in blok


def test_geen_nederlandse_prompt_meer_bij_een_reason_aanroep():
    """DE RATCHET. Niet "Nederlands mag niet" maar: elke prompt die naar het model gaat is Engels,
    zodat er geen tweede `title_from` kan ontstaan die pas op het bord zichtbaar wordt.

    Hij toetst GEDRAG via de bron (welke tekst gaat er naar `reason`), niet de aanwezigheid van
    losse woorden ergens in een bestand: commentaar en docstrings zijn en blijven Nederlands, dat
    is de afspraak van dit project."""
    import pathlib
    import re

    signaal = re.compile(r'\b(Vat |Geef |Schrijf |Bepaal |Stel |Kies |Beoordeel |Maak |Noem |'
                         r'alleen de |maximaal |woorden|zinnen|uitkomst|antwoord)', re.I)
    gevonden = []
    for f in sorted(pathlib.Path(_PKG).rglob("*.py")):
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r'reason(?:_fn)?\(\s*(.{0,900}?)(?:,\s*max_tokens|,\s*call_site|\))',
                             src, re.S):
            blok = m.group(1)
            if "call_site" in blok:
                continue
            if len({x.strip() for x in signaal.findall(blok)}) >= 2:
                gevonden.append(f"{f.name}:{src[:m.start()].count(chr(10)) + 1}")
    assert not gevonden, ("Nederlandse prompt(s) naar het model, terwijl de inhoudslaag sinds "
                          f"06-09-2026 Engels is: {gevonden}")
