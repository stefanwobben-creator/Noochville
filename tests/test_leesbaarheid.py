"""Deel 2 van de leesbaarheidslaag: het oordeel, en de poort die het feit bewaakt.

Deel 1 (`systeemtaal`) is deterministisch en draait altijd. Dit deel is het model, en daarvoor geldt
één eis boven alles: **feitbehoud gaat vóór politoer.** Een leesbaar-maar-fout bericht is erger dan
een lelijk-maar-juist bericht, en een afkeuring is hier geen storing maar het vangnet — de ruwe
tekst blijft dan gewoon staan.

De eis is scherper dan "verdraai het feit niet". Het is BEHOUD VAN EPISTEMISCH NIVEAU:

  1. de slag om de arm blijft staan;
  2. alternatieven blijven heel;
  3. er komt geen detail bij;
  4. Engels wordt letterlijk vertaald — vertalen is waar een model het snelst iets bijverzint.

1 en 3 zijn te MÉTEN en staan daarom in `bevinding.feitbehoud`; gemeten is sterker dan gevraagd,
want een model dat zijn eigen tekst beoordeelt kijkt zijn eigen huiswerk na. 2 en 4 zijn oordeel en
blijven in de prompt.

TWEE VALSE AFWIJZINGEN, allebei gevonden door de meting op echte spanningen en niet door de tests
die ik erbij schreef. Ze staan hieronder als regressie, want ze zijn dezelfde fout: op LETTERS
zoeken waar je op WOORDEN bedoelt.
"""
from __future__ import annotations

from nooch_village import bevinding as bv

BRON = ("⚠️ Puls-uitval: rol 'harry_hemp' liet geen hartslag na op 2026-08-29 — mogelijk "
        "niet-uitvoering (hook/service), geen fout gemeld.")


# ── de gemeten helft van feitbehoud ─────────────────────────────────────────

def test_stelliger_dan_de_bron_wordt_afgekeurd():
    """Het ijkpunt-geval zelf: de bron zei "mogelijk", de herschrijving "waarschijnlijk"."""
    ok, reden = bv.feitbehoud(BRON, "Waarschijnlijk draait zijn achtergrondproces niet meer.")
    assert ok is False and "slag om de arm" in reden


def test_een_verzonnen_getal_wordt_afgekeurd():
    ok, reden = bv.feitbehoud(BRON, "De dagpuls draaide 3 dagen niet.")
    assert ok is False and "'3'" in reden


def test_een_datum_mag_leesbaarder_geschreven_worden():
    """"2026-08-29" → "29 augustus 2026" is geen nieuw feit maar hetzelfde feit, leesbaar."""
    ok, _ = bv.feitbehoud(BRON, "Er kwam geen foutmelding op 29 augustus 2026.")
    assert ok is True


def test_zonder_bron_keurt_de_poort_niets_af():
    """Fail-open: valt er niets te vergelijken, dan is er ook niets te weigeren."""
    assert bv.feitbehoud("", "wat dan ook")[0] is True
    assert bv.feitbehoud(BRON, "")[0] is True


# ── de twee valse afwijzingen, als regressie ────────────────────────────────

def test_onduidelijk_is_geen_zekerheid():
    """EERSTE VALSE AFWIJZING. De poort zocht op losse letters en las "ONduidelijk" als "duidelijk" —
    het woord dat de slag om de arm juist vasthoudt, gelezen als het tegendeel. De poort die
    feitbehoud bewaakt kan zelf een feit verdraaien."""
    zin = "Nu is onduidelijk of de rol niet is gestart of dat er iets mis is met het proces."
    assert bv.feitbehoud(BRON, zin)[0] is True


def test_zeker_weten_is_geen_stellige_bewering():
    """TWEEDE VALSE AFWIJZING. "We moeten zeker weten of alles werkt" is een WENS om te controleren,
    precies het tegenovergestelde van een stellige bewering over de oorzaak. Het kale "zeker" is in
    het Nederlands te veelzijdig om als zekerheidsclaim te tellen."""
    assert bv.feitbehoud(BRON, "We moeten zeker weten of alles correct functioneert.")[0] is True


def test_jargon_zoekt_woorden_geen_letters():
    """DEZELFDE FOUT IN DE BESTAANDE POORT. `jargon_in` deed een substring-vergelijking, en
    verwierp daarmee een prima herschrijving omdat er "kernproces" stond. "match" zit in
    "matchmaker", "store" in "geschiedenisstore"."""
    assert bv.jargon_in("een kernproces dat niet startte") == []
    assert bv.jargon_in("de matchmaker koppelde het werk") == []
    assert bv.jargon_in("de kern van de zaak") == ["kern"]      # het echte woord wél


# ── de poort valt terug op het origineel ────────────────────────────────────

def test_een_geweigerde_herschrijving_laat_de_ruwe_tekst_staan():
    """Afkeuren is hier geen storing maar het vangnet: `ok=False` betekent dat het scherm de ruwe
    signalering toont in plaats van een gladde gok."""
    ok, reden = bv.keur({"spanning": "Waarschijnlijk is het achtergrondproces gestopt en dat is "
                                     "een probleem voor de hele dag.",
                         "voorstel": "Kun je kijken wat er aan de hand is?", "ruw": BRON})
    assert ok is False and "slag om de arm" in reden


# ── de prompt ───────────────────────────────────────────────────────────────

def test_de_vier_eisen_staan_in_de_prompt():
    for eis in ("slag om de arm", "Alternatieven blijven heel", "geen detail bij",
                "vertaal dan letterlijk"):
        assert eis in bv._PROMPT, eis
    assert "FEITBEHOUD GAAT VÓÓR LEESBAARHEID" in bv._PROMPT


def test_de_prompt_vraagt_om_structuur_en_een_menselijke_vraag():
    for stuk in ("wat er gebeurde", "waarom dat telt", "wat er nodig is",
                 "MENSELIJKE VRAAG", "Kun je kijken wat er aan"):
        assert stuk in bv._PROMPT, stuk


def test_de_lezerstests_komen_uit_de_policy_niet_uit_een_kopie(tmp_path):
    """`reference, don't copy`: COPYCHECK-001 is governance-eigendom en mag wijzigen. Een kopie hier
    zou afdrijven zodra iemand de policy bijwerkt."""
    from nooch_village.attachments import AttachmentStore
    from nooch_village.helderheid import POLICY_ID, reader_tests
    st = AttachmentStore(str(tmp_path / "attachments.json"))
    st.add(anchor="rol", kind="policy", title="Copycheck", domain="Copycheck",
           body="bla\n\n  **Reader tests**\n  - Veertien: kan een kind dit voorlezen?\n\n  **Slot**\n",
           actor_id="t", actor_type="human")
    st._items[POLICY_ID] = st._items.pop(next(iter(st._items)))
    st._items[POLICY_ID]["id"] = POLICY_ID
    st._save()
    tekst, uit_policy = reader_tests(str(tmp_path))
    assert uit_policy is True and "Veertien: kan een kind dit voorlezen?" in tekst


def test_de_terugval_is_zichtbaar(tmp_path, caplog):
    """Fail-soft mag de degradatie niet onzichtbaar maken. Zonder policy draait de laag door op een
    samenvatting, maar dat is een signaal en geen stilte."""
    import logging
    from nooch_village.helderheid import reader_tests
    with caplog.at_level(logging.WARNING):
        tekst, uit_policy = reader_tests(str(tmp_path))
    assert uit_policy is False and "Veertien" in tekst
    assert any("noodverband" in r.message for r in caplog.records)


def test_de_herschrijver_krijgt_de_lezerstests_mee(tmp_path):
    gezien = {}

    def _nep(prompt, **kw):
        gezien["p"] = prompt
        return '{"spanning": "De dagpuls draaide niet op 29 augustus 2026, en er kwam geen ' \
               'foutmelding.", "voorstel": "Kun je kijken wat er aan de hand is?"}'

    uit = bv.herschrijf(BRON, rol="harry_hemp", reason_fn=_nep, data_dir=str(tmp_path))
    assert "Veertien" in gezien["p"]
    assert uit["ok"] is True, uit["reden"]


def test_een_citaat_blijft_staan_ook_in_het_engels():
    """GEVONDEN IN DE BRON-ANALYSE. Drie prod-berichten citeren een Engelse KLANTCLAIM in een
    Nederlandse zin: "🔴 Vervang: good for the planet — …". Dat citaat is bewijsmateriaal: iemand
    heeft precies díe woorden op de site gezien. Vertaal je het mee, dan klopt het niet meer met de
    bron — en dan is de leesbaarheidslaag bewijs gaan bewerken.

    Dezelfde familie als de Copywriter-uitzondering: Engels dat er met opzet staat, blijft."""
    assert "GECITEERDE tekst blijft staan" in bv._PROMPT
    assert "bewijsmateriaal" in bv._PROMPT


# ── de trede-keuze ──────────────────────────────────────────────────────────

def test_mistral_is_de_basis_niet_gemini():
    """GEMETEN, niet gekozen. Op vier echte ijkpunten haalde mistral alle vier de feitbehoud-punten;
    gemini-flash viel af op punt 3 — het voegde "essentieel" en "onbekende gevolgen" toe,
    karakterisering die de bron niet had. Vlotter lezen weegt niet op tegen epistemische inflatie.

    En de volgorde is niet toevallig: stond de sterke trede vooraan met de dorpsstaart eronder, dan
    viel hij zonder krediet door naar gemini-flash-LITE — de goedkoopste van allemaal, precies
    degene die we niet willen."""
    assert bv.basis_ladder().split(",")[0] == "mistral:mistral-small-latest"


def test_de_klim_draait_alleen_na_een_afkeuring():
    """Geen tweede poging voor de sport: de sterke trede draait waar de goedkope aantoonbaar
    tekortschoot — volgens een deterministische poort, niet op gevoel."""
    beurten = []

    def _nep(prompt, **kw):
        beurten.append(kw.get("ladder", ""))
        return ('{"spanning": "Waarschijnlijk is het achtergrondproces gestopt en dat raakt de '
                'hele dag.", "voorstel": "Kun je kijken wat er aan de hand is?"}'
                if len(beurten) == 1 else
                '{"spanning": "Mogelijk startte een achtergrondproces niet, en er kwam geen '
                'foutmelding.", "voorstel": "Kun je kijken wat er aan de hand is?"}')

    uit = bv.herschrijf(BRON, rol="harry_hemp", reason_fn=_nep, ladder="mistral:x")
    assert len(beurten) == 2, "de klim draaide niet na de afkeuring"
    assert uit["ok"] is True and "Mogelijk" in uit["spanning"]


def test_zonder_afkeuring_geen_tweede_call():
    beurten = []

    def _nep(prompt, **kw):
        beurten.append(1)
        return ('{"spanning": "Mogelijk startte een achtergrondproces niet op 29 augustus 2026.", '
                '"voorstel": "Kun je kijken wat er aan de hand is?"}')

    bv.herschrijf(BRON, rol="harry_hemp", reason_fn=_nep, ladder="mistral:x")
    assert len(beurten) == 1


def test_een_mislukte_klim_laat_de_afkeuring_staan():
    """Levert de klim niets (geen krediet), dan blijft de ruwe tekst staan — dezelfde uitkomst als
    zonder klim, alleen een call duurder."""
    def _nep(prompt, **kw):
        if "sonnet" in kw.get("ladder", ""):
            return None                                   # geen krediet
        return ('{"spanning": "Waarschijnlijk is het achtergrondproces gestopt en dat raakt de hele '
                'dag.", "voorstel": "Kun je kijken wat er aan de hand is?"}')

    uit = bv.herschrijf(BRON, rol="harry_hemp", reason_fn=_nep, ladder="mistral:x")
    assert uit["ok"] is False and "slag om de arm" in uit["reden"]


# ── de bron levert Nederlands ───────────────────────────────────────────────

def test_de_plan_prompt_vraagt_nederlands():
    """DE BRON VAN 134 ENGELSE INBOX-BERICHTEN, en het was één regel: "Write all free text in
    English." Die tekst is geen UI-chrome maar INHOUD: hij landt als checklist-item op een project
    en als spanning in de inbox, náást bevindingen en Field Notes die allemaal Nederlands zijn.

    Bij de BRON oplossen, niet bij de laag: vertalen is precies waar een model iets bijverzint, dus
    de veiligste vertaling is de vertaling die niet nodig is."""
    import inspect

    from nooch_village.inhabitant import Inhabitant
    bron = inspect.getsource(Inhabitant._plan_checklist)
    assert "Write all free text in English" not in bron
    assert "in DUTCH" in bron
    assert "quoted claim or source stays in its original language" in bron


def test_geen_engelse_berichten_meer_uit_de_founder_flow():
    """De 20 code-literals. Drie ervan stuurden Engels naar een inbox — "Bank the evidence for:" was
    er 14 van. De cockpit-CHROME blijft Engels (i18n fase 1); de berichtinhoud is Nederlands, net als
    elke andere spanning."""
    import inspect

    from nooch_village import founder_taken
    bron = inspect.getsource(founder_taken)
    for engels in ("Bank the evidence for", "Ground this claim scientifically",
                   "Approved proposal from"):
        assert engels not in bron, engels


# ── de grond-check: derde onafhankelijke deelcheck ──────────────────────────

CLAIM_BRON = ('🟠 Claim-scan: 2 model-gevonden claim(s) zonder lijstterm — "This helps reduce…" '
              '(faq), "We are on a mission…" (mission) (vermoeden, geen wet)')


def test_het_ijkpunt_van_prod_wordt_geweigerd_ook_zonder_cijfers():
    """HET GEVAL VAN 31 AUGUSTUS, op prod, op het eerste echte bericht. De bron zei letterlijk
    "(vermoeden, geen wet)"; de herschrijving maakte er "de EU-richtlijn 2024/825 (EmpCo)" van.

    De richtlijn BESTAAT — het model had gelijk — en juist dat maakt het gevaarlijk: correct maar
    ongegrond zie je bij nalezen niet, want alles klopt. De getal-check ving hem, maar bij toeval:
    zonder de cijfers was hij erdoor. Een poort die zijn vangst aan cijfers dankt, dekt niet wat hij
    lijkt te dekken."""
    met_cijfers = "Twee claims missen mogelijk een term uit de EU-richtlijn 2024/825 (EmpCo)."
    zonder = "Twee claims missen mogelijk een term uit de EU-richtlijn EmpCo."
    assert bv.feitbehoud(CLAIM_BRON, met_cijfers)[0] is False
    ok, reden = bv.feitbehoud(CLAIM_BRON, zonder)
    assert ok is False and "zonder grond" in reden, reden


def test_een_legitieme_herformulering_overleeft():
    """De andere kant. Streng afstellen mag omdat fail-open goedkoop is — maar een poort die alles
    weigert beschermt niets, hij zet de laag uit."""
    goed = "Twee claims op de site missen mogelijk een lijstterm; het is een vermoeden, geen wet."
    assert bv.feitbehoud(CLAIM_BRON, goed)[0] is True


def test_niet_elk_hoofdletterwoord_telt():
    """Bewust GESCOPED op opzoekbare gegevens. Een naam of een zin die met een hoofdletter begint is
    geen specifiek gegeven, en zou een legitieme herformulering laten sneuvelen."""
    bron = "harry_hemp liet geen hartslag na, en de faq-pagina gaf een fout"
    assert bv.feitbehoud(bron, "Harry Hemp keek naar de FAQ-pagina.")[0] is True
    assert bv.feitbehoud(bron, "Deze rol gaf geen teken van leven.")[0] is True


def test_de_naam_aan_een_acroniem_telt_wel():
    """GEVONDEN IN DE METING, niet bedacht: de bron zei "EU Green" (afgekapt), de herschrijving
    maakte er "EU Green Deal-regelgeving" van. "Deal" is een gewoon woord met een hoofdletter en
    viel dus buiten de andere patronen — maar vastgeplakt aan een acroniem is het wél een
    opzoekbare aanduiding. Zo blijft "niet elk hoofdletterwoord" overeind."""
    assert bv.feitbehoud("… uit de EU Green", "definities uit de EU Green Deal")[0] is False
    assert bv.feitbehoud("… uit de EU Green", "definities uit de EU Green")[0] is True


def test_een_koppelteken_is_geen_verschil():
    """Een poort die over spelling struikelt keurt taal af in plaats van inhoud."""
    assert bv.feitbehoud("de EU-richtlijn zegt iets", "de EU richtlijn zegt iets")[0] is True


def test_de_drie_deelchecks_overlappen_niet():
    """DE REDEN DAT HET ER DRIE ZIJN. De smokkel van 31 augustus hield zich keurig aan de
    zekerheidsregel — "mogelijk" bleef gewoon staan — en glipte langs een andere as. Eén goede check
    is zwakker dan drie die elkaar niet dekken."""
    # zekerheid geschonden, grond in orde
    assert "slag om de arm" in bv.feitbehoud("mogelijk iets", "Het is duidelijk iets.")[1]
    # grond geschonden, zekerheid in orde
    assert "zonder grond" in bv.feitbehoud("mogelijk iets", "Mogelijk iets uit de ISO-norm.")[1]
