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
