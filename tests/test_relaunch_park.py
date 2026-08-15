"""Bulk-parkeren op één verklaard feit, zonder de substantie weg te gooien.

Een cluster spanningen hangt aan de huidige site (footer, logo, live claim-checks, pagina-fetches,
FAQ-citaten, en het capability-item "home geeft geen HTML"). Ze los afhandelen is werk aan iets dat
verdwijnt. Eén feit — de herbouw — parkeert ze allemaal, met één terugkeer-voorwaarde en één
handmatige trigger.

Drie dingen die deze tests bewaken, en het derde is het belangrijkste:

  1. parkeren is GEEN oordeel: geen founder-label, geen afwijzing;
  2. één trigger haalt alles terug, niet per item een eigen datum;
  3. de SUBSTANTIE blijft bewaard — de compliance-flags zijn input voor de herbouw. Alleen een
     verwijzing bewaren zou bij de relaunch een lege lijst opleveren als het project intussen is
     opgeruimd, en dan is de herbouw precies het bewijs kwijt waarvoor hij hem nodig had.
"""
from __future__ import annotations

import pytest

from nooch_village import relaunch_park as rp


# ── Wat valt eronder ────────────────────────────────────────────────────────

@pytest.mark.parametrize("tekst,verwacht", [
    ("Locate the Plant Based Treaty-logo on Nooch.earth footer", "footer-inspectie"),
    ("Capture the PETA Approved Vegan logo placement", "logo op de site"),
    ("🔴 Claim-scan: 1 nieuwe verboden claim op nooch.earth", "live claim-check"),
    ("⚠️ Scan onvolledig: home gaf HTTP 403", "pagina-fetch"),
    ("Scrape/fetch the live FAQ page content", "pagina-fetch"),
    ("Extract the literal quote from the FAQ page", "citaat van de site"),
    ("Onderzoek klantacceptatie van myceliumleer via consumentenreviews", ""),
    ("Bron 'gsc/clicks' levert niet meer", ""),
])
def test_alleen_site_afhankelijk_werk_valt_onder_de_parkering(tekst, verwacht):
    """Expliciete patronen, geen LLM-oordeel: bij een bulk-parkering hoort zichtbaar te zijn wát
    eronder valt. Werk dat niet aan de site hangt blijft gewoon lopen."""
    assert rp.soort(tekst) == verwacht


# ── Dubbels ─────────────────────────────────────────────────────────────────

class _Projects:
    def __init__(self, rijen):
        self._p = {r["id"]: r for r in rijen}
        self.geparkeerd, self.gedeblokkeerd = [], []

    def by_status(self, status):
        return [p for p in self._p.values() if p.get("status") == status]

    def park(self, pid, reden, items, door=""):
        self.geparkeerd.append((pid, reden))
        self._p[pid]["park"] = {"reden": reden, "items": items}
        return True

    def unblock(self, pid):
        self.gedeblokkeerd.append(pid)
        return True


class _Notif:
    def __init__(self, rijen):
        self._n = list(rijen)

    def open_for_targets(self, targets):
        return [n for n in self._n if not n.get("archived")]

    def _f(self, nid):
        return next(n for n in self._n if n["id"] == nid)

    def set_poort(self, nid, verdict):
        self._f(nid)["poort"] = verdict
        return True

    def mark_item_processed(self, nid, outcome="", by=""):
        self._f(nid).update(processed=True, outcome=outcome, processed_by=by)
        return True

    def archive_item(self, nid):
        self._f(nid)["archived"] = True
        return True


def _omgeving():
    projects = _Projects([
        {"id": "p1", "status": "queued", "owner": "compliance",
         "scope": "Locate the Plant Based Treaty-logo on Nooch.earth footer"},
        {"id": "p2", "status": "blocked", "owner": "compliance",
         "scope": "Extract the literal quote from the FAQ page"},
        {"id": "p3", "status": "queued", "owner": "harry_hemp",
         "scope": "Onderzoek draagcomfort van myceliumleer"},          # niet site-afhankelijk
    ])
    notif = _Notif([
        {"id": "n1", "target_id": "founder", "snippet": "⚠️ Scan onvolledig: home gaf HTTP 403"},
        {"id": "n2", "target_id": "founder", "snippet": "🙋 compliance: iets heel anders"},
    ])
    return projects, notif


# ── 1. Parkeren, en wat het NIET is ─────────────────────────────────────────

def test_dry_run_muteert_niets(tmp_path):
    projects, notif = _omgeving()
    uit = rp.park(str(tmp_path), projects=projects, notif=notif, targets=[("role", "founder")])
    assert uit["projecten"] == 2 and uit["notificaties"] == 1
    assert projects.geparkeerd == [] and rp.geparkeerd(str(tmp_path)) == []


def test_live_parkeert_projecten_en_notificaties(tmp_path):
    projects, notif = _omgeving()
    rp.park(str(tmp_path), projects=projects, notif=notif, targets=[("role", "founder")],
            dry_run=False)
    assert sorted(p for p, _ in projects.geparkeerd) == ["p1", "p2"]
    assert all(r == rp.REDEN for _, r in projects.geparkeerd)
    assert notif._n[0]["archived"] and not notif._n[1].get("archived")


def test_werk_dat_niet_aan_de_site_hangt_blijft_lopen(tmp_path):
    projects, notif = _omgeving()
    rp.park(str(tmp_path), projects=projects, notif=notif, targets=[("role", "founder")],
            dry_run=False)
    assert "p3" not in [p for p, _ in projects.geparkeerd]
    assert not notif._n[1].get("archived")


def test_parkeren_is_geen_afwijzing(tmp_path):
    """Geen founder-label, geen 'rejected'. De rol hoort dit te lezen als gehoord-en-vastgehouden;
    een afwijzing zou de Founder Flow iets onwaars leren."""
    projects, notif = _omgeving()
    rp.park(str(tmp_path), projects=projects, notif=notif, targets=[("role", "founder")],
            dry_run=False)
    uitkomst = notif._n[0]["outcome"]
    assert "geparkeerd" in uitkomst and rp.VOORWAARDE in uitkomst
    assert "afgewezen" not in uitkomst and "rejected" not in uitkomst
    assert notif._n[0]["poort"]["deur"] == "geparkeerd"


def test_elk_item_draagt_dezelfde_terugkeer_voorwaarde(tmp_path):
    """Eén trigger, geen datum per item."""
    projects, notif = _omgeving()
    rp.park(str(tmp_path), projects=projects, notif=notif, targets=[("role", "founder")],
            dry_run=False)
    staand = rp.geparkeerd(str(tmp_path))
    assert staand and {r["voorwaarde"] for r in staand} == {rp.VOORWAARDE}
    assert {r["reden"] for r in staand} == {rp.REDEN}


# ── 2. De substantie blijft ─────────────────────────────────────────────────

def test_de_volledige_tekst_wordt_bewaard_niet_alleen_een_verwijzing(tmp_path):
    """De compliance-flags zijn input voor de herbouw. Alleen een project-id bewaren levert bij de
    relaunch een lege lijst op als dat project intussen is opgeruimd."""
    projects, notif = _omgeving()
    rp.park(str(tmp_path), projects=projects, notif=notif, targets=[("role", "founder")],
            dry_run=False)
    teksten = [r["tekst"] for r in rp.geparkeerd(str(tmp_path))]
    assert any("Plant Based Treaty" in t for t in teksten)
    assert any("literal quote" in t for t in teksten)
    assert any("HTTP 403" in t for t in teksten)


def test_geparkeerd_werk_is_vindbaar_onder_zijn_soort(tmp_path):
    projects, notif = _omgeving()
    rp.park(str(tmp_path), projects=projects, notif=notif, targets=[("role", "founder")],
            dry_run=False)
    soorten = {r["soort"] for r in rp.geparkeerd(str(tmp_path))}
    assert {"footer-inspectie", "citaat van de site", "pagina-fetch"} <= soorten


# ── 3. Eén trigger terug ────────────────────────────────────────────────────

def test_heropenen_haalt_alles_in_een_keer_terug(tmp_path):
    projects, notif = _omgeving()
    rp.park(str(tmp_path), projects=projects, notif=notif, targets=[("role", "founder")],
            dry_run=False)
    uit = rp.heropen(str(tmp_path), projects=projects)
    assert uit["teruggehaald"] == 3
    assert sorted(projects.gedeblokkeerd) == ["p1", "p2"]
    assert rp.geparkeerd(str(tmp_path)) == []            # niets blijft hangen


def test_de_teruggehaalde_lijst_is_de_herbeoordelings_input(tmp_path):
    projects, notif = _omgeving()
    rp.park(str(tmp_path), projects=projects, notif=notif, targets=[("role", "founder")],
            dry_run=False)
    uit = rp.heropen(str(tmp_path), projects=projects)
    assert any("Plant Based Treaty" in r["tekst"] for r in uit["items"])


def test_heropenen_is_append_only(tmp_path):
    """Niets wordt herschreven: de parkering blijft leesbaar als historie."""
    projects, notif = _omgeving()
    rp.park(str(tmp_path), projects=projects, notif=notif, targets=[("role", "founder")],
            dry_run=False)
    rp.heropen(str(tmp_path), projects=projects)
    regels = rp.alle(str(tmp_path))
    assert len(regels) == 6 and sum(1 for r in regels if r.get("terug")) == 3
