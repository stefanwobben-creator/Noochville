"""De projectpoort (founder, 19 jul — naast G0-G4): done = vraag beantwoord, niet werk
gedaan. Drie borgingen: (1) dod_poort weigert Done zolang dod_outcome leeg is en opent
zodra er een antwoord staat; (2) set_dod schrijft de twee DoD-contractvelden en niets
anders; (3) een mens-project kan met done_when geboren worden (de intake-eis leeft in de
handler; create zelf blijft vrij voor rollen)."""
from __future__ import annotations

from nooch_village.projects import ProjectLedger, dod_poort


def test_dod_poort_weigert_zonder_antwoord_en_opent_met(tmp_path):
    pj = ProjectLedger(f"{tmp_path}/projects.json")
    pid = pj.create("harry_hemp", "Hoeveel massa verliest een schoenzool?", "human")
    # dicht: geen antwoord → weiger-reden
    reden = dod_poort(pj.get(pid))
    assert reden and "Antwoord op de projectvraag" in reden
    # ook dicht voor None / leeg project (fail-closed)
    assert dod_poort(None)
    assert dod_poort({})
    # open zodra het antwoord bestaat — de poort oordeelt niet over kwaliteit
    pj.set_dod(pid, "dod_outcome", "Ca. 1-5 g per 100 km; grotendeels microplastics in "
                                   "het milieu. Bronnen in het einddocument.")
    assert dod_poort(pj.get(pid)) is None


def test_set_dod_schrijft_alleen_contractvelden(tmp_path):
    pj = ProjectLedger(f"{tmp_path}/projects.json")
    pid = pj.create("librarian", "Woordenschat-toets", "human")
    assert pj.set_dod(pid, "done_when", "Alle drie de woorden hebben een oordeel.")
    assert pj.set_dod(pid, "dod_outcome", "Twee goedgekeurd, één afgewezen.")
    p = pj.get(pid)
    assert p["done_when"] == "Alle drie de woorden hebben een oordeel."
    assert p["dod_outcome"] == "Twee goedgekeurd, één afgewezen."
    # onbekend veld of onbekend project: geweigerd, niets geschreven
    assert not pj.set_dod(pid, "scope", "hack")
    assert not pj.set_dod("bestaat_niet", "done_when", "x")
    assert pj.get(pid)["scope"] == "Woordenschat-toets"


def test_create_met_done_when(tmp_path):
    pj = ProjectLedger(f"{tmp_path}/projects.json")
    pid = pj.create("website_watcher", "Bezoekersdaling duiden", "human",
                    done_when="Er ligt één verklaring met bewijs, of drie uitgesloten oorzaken.")
    assert pj.get(pid)["done_when"].startswith("Er ligt één verklaring")
