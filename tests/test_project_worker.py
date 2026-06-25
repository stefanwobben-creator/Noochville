"""Autonome project-uitvoering: een rol werkt (omkeerbaar, tekst-only, met eigen capaciteit) aan
z'n queued projecten. Nieuwe capaciteit/onomkeerbaar → KAN NIET → geblokkeerd voor de mens."""
from __future__ import annotations

from nooch_village.projects import ProjectLedger
from nooch_village.project_worker import work_one, work_projects


def test_work_one_levert():
    res = work_one("Reviews tonen op de productpagina", "analyst", "groei",
                   llm_reason=lambda p: "LEVER: Een korte tekst met 3 voorbeeldreviews.")
    assert res["ok"] and "voorbeeldreviews" in res["outcome"]


def test_work_one_kan_niet():
    res = work_one("Nieuwsbrief versturen", "analyst", "groei",
                   llm_reason=lambda p: "KAN NIET: een e-mailtool die ik niet heb")
    assert res["ok"] is False and "e-mailtool" in res["needs"]


def test_work_one_failclosed():
    assert work_one("x", "r", "p", llm_reason=lambda p: None)["ok"] is False


def test_work_projects_voert_uit_blokkeert_en_is_idempotent(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    p_do = led.create("analyst", "Blog schrijven over veganisme", "human")       # queued
    p_no = led.create("analyst", "Adverteren op Google", "human")                # queued
    led.create("scout", "Iets afgeronds", "human", status="queued")
    led.complete(led.create("librarian", "klaar", "human"))                      # done → niet oppakken

    def fake_llm(prompt):
        return ("KAN NIET: advertentiebudget en een advertentietool"
                if "Adverteren" in prompt else "LEVER: Een eerste blogdraft.")

    res = work_projects(led, records=None, llm_reason=fake_llm, limit=5)
    assert res["worked"] == 2 and res["blocked"] == 1
    assert led.get(p_do)["status"] == "running" and led.get(p_do)["progress"].startswith("Een eerste")
    assert led.get(p_do)["worked"] is True
    assert led.get(p_no)["status"] == "blocked" and "advertentie" in led.get(p_no)["blocked_on"]
    # idempotent: tweede ronde pakt het uitgevoerde project niet opnieuw
    res2 = work_projects(led, records=None, llm_reason=fake_llm, limit=5)
    assert res2["worked"] == 0


def test_work_projects_respecteert_limit(tmp_path):
    led = ProjectLedger(str(tmp_path / "p.json"))
    for i in range(4):
        led.create("analyst", f"project {i}", "human")     # queued
    res = work_projects(led, records=None, llm_reason=lambda p: "LEVER: gedaan", limit=2)
    assert res["worked"] == 2 and res["skipped"] == 2
