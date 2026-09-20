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

# WAT HIER WEG IS (B2, 20 september 2026): 3 test(s) over het inbox-scherm. `/inbox`,
# `/inbox/verwerk`, de lade en `NotifStore` bestaan niet meer — de wachtrij is een
# DM-stroom geworden. Verwijderd omdat hun onderwerp weg is, niet omdat ze faalden.

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
    assert st.ontjargon("Het was een dry-run.") == "Het was een proefdraai."


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
# WAT HIER WEG IS (B2, 20 september 2026): `test_het_merk_wordt_bij_het_schrijven_vastgelegd`.
# Die toetste dat `NotifStore.add` het merk `MENS_GETYPT` zette, zodat de herschrijf-poort
# andermans woorden met rust liet. Beide zijn weg: `NotifStore` is opgeheven en de poort die het
# merk moest lezen bestond om de inbox-tekst te herschrijven. In een DM-laag is vrijwel álles
# mens-tekst en wordt er sowieso niets herschreven — het merk heeft geen lezer meer.
#
# De LES staat in `docs/CONVENTIES.md` en geldt voor elke volgende poort: leg het feit vast op het
# pad dat het weet, raad het nooit achteraf. Er is hier alleen geen poort meer om hem op te toetsen.



# ── Het sjabloon eraf ───────────────────────────────────────────────────────
#
# Gered uit `tests/test_tensie_poort.py`, dat met de tensie-poort is verdwenen (20 sept 2026).
# `kern` zelf niet: hij is geen poort-logica maar een deterministische schoonmaak, dezelfde familie
# als de swaps hierboven, en `bevinding` en `zelf_verwerking` gebruiken hem allebei nog.

def test_het_sjabloon_wordt_weggehaald():
    """"Deze taak vereist een mens of externe partij" domineerde de tekst en duwde elk oordeel naar
    de verpakking, terwijl het werk eronder gewoon van een rol is."""
    from nooch_village.systeemtaal import kern
    t = ("⏸️ Project van Harry Hemp vastgelopen op 1 mens-/extern item(s): Deze taak vereist een "
         "mens of externe partij: 'Decide whether to permanently exclude this overlap'")
    assert kern(t) == "Decide whether to permanently exclude this overlap"
