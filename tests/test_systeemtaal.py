"""De deterministische helft van de leesbaarheidslaag: swaps die altijd gebeuren.

Grond-eerst, model-laatst. Deze laag is gratis, gebeurt ook zonder krediet, en mag daarom nooit
iets doen wat context vraagt. De drie eisen die hij deelt met de model-trede staan hieronder als
tests, want ze zijn met opzet strenger dan "verdraai het feit niet":

  1. de slag om de arm blijft staan  — `mogelijk` blijft `mogelijk`;
  2. alternatieven blijven heel      — `hook of service` wordt niet stil één van de twee;
  3. er komt geen detail bij         — de swap voegt nooit iets toe dat de bron niet had.

Punt 2 is de reden dat de koepelterm bestaat. De eerste doel-versie van het ijkpunt maakte van
"mogelijk niet-uitvoering (hook of service)" het veel stelligere "waarschijnlijk draait zijn service
niet meer": één mogelijkheid in plaats van twee, en zekerder dan de bron. Dat werd met opzet en
aandacht door een mens geschreven — doet een zorgvuldige mens het al, dan doet een goedkoop model
het vaker.
"""
from __future__ import annotations

import re

from nooch_village import systeemtaal as st

# Het ijkpunt uit de spec, letterlijk zoals `Dagcyclus._run_pulse_watchdog` hem schrijft.
IJKPUNT = ("⚠️ Puls-uitval: rol 'harry_hemp' liet geen hartslag na op 2026-08-29 — mogelijk "
           "niet-uitvoering (hook/service), geen fout gemeld. Beoordeel via "
           "python -m nooch_village.inbox")


# ── de drie feitbehoud-eisen ────────────────────────────────────────────────

def test_de_slag_om_de_arm_blijft_staan():
    uit = st.ontjargon(IJKPUNT)
    assert "mogelijk" in uit.lower()
    for zekerder in ("waarschijnlijk", "vermoedelijk", "duidelijk", "zeker"):
        assert zekerder not in uit.lower(), f"de swap werd stelliger dan de bron: {zekerder}"


def test_alternatieven_blijven_heel():
    """`hook/service` mag NOOIT één van de twee worden. Een koepelterm dekt beide zonder te kiezen."""
    uit = st.ontjargon(IJKPUNT)
    assert "achtergrondproces" in uit
    assert "service" not in uit.lower() and "hook" not in uit.lower()
    # en niet dubbel: "achtergrondproces of achtergrondproces" leest als twee dingen
    assert uit.lower().count("achtergrondproces") == 1


def test_er_komt_geen_detail_bij():
    """Alles in de uitkomst moet in de bron te herleiden zijn. Geen naam, geen oorzaak, geen getal
    dat de ruwe tekst niet had."""
    uit = st.ontjargon(IJKPUNT)
    assert "harry_hemp" in uit and "2026-08-29" in uit
    # geen verzonnen oorzaak of handeling
    for verzonnen in ("herstart", "opnieuw starten", "crash", "gecrasht", "kapot"):
        assert verzonnen not in uit.lower()


def test_de_koepel_kiest_nooit_een_van_de_twee():
    """Structureel, niet alleen op dit ijkpunt: geen enkel bronwoord mag doel zijn van een ander.
    Dan zou de swap 'hook' stilletjes tot 'service' promoveren."""
    bronnen = {b.lower() for b, _ in st.SWAPS}
    for bron, doel in st.SWAPS:
        assert doel.lower() not in bronnen, f"'{bron}' → '{doel}' kiest een van de mogelijkheden"


# ── commando's ─────────────────────────────────────────────────────────────

def test_een_pure_opdracht_gaat_weg():
    assert st.ontjargon("Draai systemctl restart noochville-village om te herstellen.") == ""
    assert "python -m" not in st.ontjargon(IJKPUNT)
    assert "beoordeel" not in st.ontjargon(IJKPUNT).lower()


def test_geen_enkele_naar_mens_tekst_draagt_een_commando():
    """DE INVARIANT, en hij overrulet mijn eerste regel. Ik had hier alles-of-niets: raakte het
    commando een zin met inhoud, dan bleef de zin HEEL — om het feit niet te verliezen wát er
    gedraaid was. Dat hield stand tot een echte melding het tegendeel liet zien:

        "⚠️ Capaciteit ontbreekt: bron levert niet meer — beoordeel via python -m nooch_village.inbox"

    Eén zin, inhoud én opdracht, dus alles-of-niets liet het commando gewoon staan. Een
    terminalopdracht hoort in GEEN ENKELE naar-mens-tekst; dat weegt zwaarder dan het feit wát er
    gedraaid werd — en dat feit blijft bewaard in de ruwe signalering."""
    ruw = "⚠️ Capaciteit ontbreekt: bron levert niet meer — beoordeel via python -m nooch_village.inbox"
    uit = st.ontjargon(ruw)
    assert "python -m" not in uit and "beoordeel via" not in uit.lower()
    assert "Capaciteit ontbreekt" in uit and "levert niet meer" in uit


def test_de_zin_eromheen_blijft_leesbaar():
    """Het restje na het knippen ("… beoordeel via") leest als een afgebroken zin, dus dat gaat mee."""
    zin = "De koppeling viel om nadat we systemctl restart draaiden, en sindsdien is de bel weg."
    uit = st.ontjargon(zin)
    assert "systemctl" not in uit
    assert uit.startswith("De koppeling viel om") and uit.endswith("de bel weg.")



# ── de swaps zelf ──────────────────────────────────────────────────────────

def test_woordsoort_klopt():
    """Een swap die de zin grammaticaal breekt levert het model rommel aan. `niet-uitvoering` is een
    zelfstandig naamwoord, dus het doel is dat ook."""
    assert st.ontjargon("mogelijk niet-uitvoering") == "mogelijk niet gestart"
    assert st.ontjargon("Het project is queued.") == "Het project is in de wachtrij."


def test_hoofdletter_reist_mee():
    assert st.ontjargon("Puls-uitval: geen hartslag.").startswith("De dagpuls")
    assert "de dagpuls draaide niet" in st.ontjargon("Er was puls-uitval vandaag.")


def test_lidwoord_klopt_bij_de_koepel():
    assert st.ontjargon("de hook startte niet") == "het achtergrondproces startte niet"


def test_idempotent():
    """Twee keer draaien mag niets veranderen — anders drijft een tekst weg bij elke passage."""
    for t in (IJKPUNT, "De dry-run gaf no_data terug.", "de hook of service"):
        een = st.ontjargon(t)
        assert st.ontjargon(een) == een


def test_lege_en_gewone_tekst_blijven_met_rust():
    assert st.ontjargon("") == ""
    gewoon = "De levertijden kloppen niet meer sinds vorige week."
    assert st.ontjargon(gewoon) == gewoon


def test_raakt_wijst_aan_zonder_te_wijzigen():
    assert set(st.raakt(IJKPUNT)) >= {"puls-uitval", "niet-uitvoering", "hook", "service"}
    assert st.raakt("gewone zin") == []


# ── de bedrading ───────────────────────────────────────────────────────────

def test_de_herschrijver_krijgt_de_ontjargonde_tekst():
    """Het model ziet de opgeschoonde tekst; `ruw` blijft de ECHTE ruwe tekst, want dat veld is
    herkomst en herkomst hoor je niet op te poetsen."""
    from nooch_village import bevinding as bv
    gezien = {}

    def _nep(prompt, **kw):
        gezien["prompt"] = prompt
        return '{"spanning": "De dagpuls draaide niet op 29 augustus, en niemand meldde een fout.", ' \
               '"voorstel": "Kijken wat er aan de hand is"}'

    uit = bv.herschrijf(IJKPUNT, rol="facilitator", reason_fn=_nep)
    assert "python -m" not in gezien["prompt"]
    assert "achtergrondproces" in gezien["prompt"]
    assert "mogelijk" in gezien["prompt"].lower()
    assert "niet-uitvoering" in uit["ruw"], "de herkomst is opgepoetst"


def test_een_bericht_dat_alleen_een_commando_was_valt_terug_op_het_origineel():
    """Fail-open naar het ORIGINEEL, nooit naar niets: liever lelijk-maar-juist dan leeg."""
    from nooch_village import bevinding as bv
    gezien = {}

    def _nep(prompt, **kw):
        gezien["prompt"] = prompt
        return '{"spanning": "", "voorstel": ""}'

    bv.herschrijf("Draai systemctl restart noochville-village.", rol="x", reason_fn=_nep)
    assert "systemctl" in gezien["prompt"]


def test_de_regel_staat_bij_de_code():
    """Deze regel moet een herschrijving van de lijst overleven."""
    import inspect
    bron = inspect.getsource(st)
    assert "geen mogelijkheden" in bron and "dichtklappen" in bron
    assert "KOEPELTERM" in bron
    assert re.search(r"1\.\s*de slag om de arm", bron)


def test_het_scherm_toont_de_opgeschoonde_leestekst():
    """GEGARANDEERD, ook zonder model. Faalt de herschrijving (geen krediet, storing), dan valt het
    scherm terug op de ruwe signalering — en die hoort dan tenminste geen `python -m …` te bevatten.
    De swap is deterministisch en betekenis-behoudend, dus hij mag zonder oordeel draaien."""
    from nooch_village.views.inbox import _een_regel, _leesbaar
    regel = _een_regel({"snippet": IJKPUNT})
    assert "python -m" not in regel and "niet-uitvoering" not in regel
    # De regel kapt op 90 tekens voor de lijst; de slag om de arm toets je op de volle tekst.
    vol = _leesbaar({}, IJKPUNT)
    assert "mogelijk" in vol.lower() and "waarschijnlijk" not in vol.lower()


def test_het_scherm_strijkt_een_commando_ook_uit_mens_ingediende_tekst():
    """DE CORRECTIE, gemeten op prod 1 september. Commando-strippen hing aan dezelfde vlag als het
    model-herschrijven, en dat lekte: een machine-melding die een MENS doorzette droeg `mens_getypt`,
    dus bleef "beoordeel via python -m …" gewoon staan op het scherm van diezelfde mens.

    De twee zorgen zijn niet hetzelfde. Een commando weghalen is geen herschrijving van iemands stem
    maar een DISPLAY-INVARIANT. Het model-herschrijven blijft wél gepoort op auteurschap."""
    from nooch_village.notifications import MENS_GETYPT
    from nooch_village.views.inbox import _leesbaar
    ruw = "⚠️ Bron levert niet meer — beoordeel via python -m nooch_village.inbox"
    for merk in ({}, {MENS_GETYPT: True}):
        assert "python -m" not in _leesbaar(merk, ruw), merk



def test_het_merk_wordt_bij_het_schrijven_vastgelegd():
    """`add()` zet het merk één keer, zodat elke latere lezer hetzelfde veld leest in plaats van
    people.json opnieuw te bevragen — en zodat blijft staan wat waar wás toen er getypt werd."""
    import tempfile

    from nooch_village.notifications import MENS_GETYPT, NotifStore
    from nooch_village.people import PeopleStore
    dd = tempfile.mkdtemp()
    p = PeopleStore(f"{dd}/people.json").add("Stefan", "s@n.nl")
    store = NotifStore(f"{dd}/notifications.json", verrijker=lambda n: {})
    van_mens = store.add("person", p.id, "", by=p.id, snippet="mijn eigen woorden")
    van_machine = store.add("person", p.id, "", by="puls-wacht", snippet="een melding")
    assert van_mens.get(MENS_GETYPT) is True
    assert MENS_GETYPT not in van_machine


def test_de_lijst_toont_de_kern_niet_de_verpakking():
    """GEMETEN op prod: 84 berichten van de laatste 30 dagen beginnen met "⏸️ Project van X
    vastgelopen op N item(s): …". De DETAILweergave haalde dat omhulsel er al af (`tensie_poort.kern`),
    de LIJST niet — precies het scherm waar je kiest wat je opent. Geen tweede ontpak-regel hier:
    `kern` is de bestaande mechaniek."""
    from nooch_village.views.inbox import _een_regel
    ruw = ("⏸️ Project van Lara the Librarian vastgelopen op 5 item(s): Kun je de exacte definities "
           "van een atomaire claim opzoeken?")
    regel = _een_regel({"snippet": ruw})
    assert not regel.startswith("⏸️") and "vastgelopen op 5" not in regel
    assert regel.startswith("Kun je de exacte definities")
