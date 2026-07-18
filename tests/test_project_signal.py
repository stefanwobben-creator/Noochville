"""Projectbord → Radar: een project dat op done komt wordt automatisch een goedgekeurd signaal
(feed 'Projecten') in de RadarStore, zodat de founder het vanuit /signals kan promoveren naar de
kennisbank. Deterministische helper (geen LLM); link "/project?id=<pid>" + `seen` als
idempotentie-anker (heropend + opnieuw afgerond → geen tweede signaal). Dekt: de helper-velden,
de cockpit-done-hook (dispatch proj_done), het daemon-pad (village._poll_board-stub), de
backfill (dry-run vs echt) en de feed-chip op /signals."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from nooch_village import cockpit2
from nooch_village.event_bus import EventBus
from nooch_village.project_signal import backfill_done_projects, signal_from_project
from nooch_village.projects import ProjectLedger
from nooch_village.radar_promote import norm_ref
from nooch_village.radar_store import RadarStore
from nooch_village.village import Village
from nooch_village.views.signals import render_signals


def _ledger(tmp_path):
    return ProjectLedger(str(tmp_path / "projects.json"))


def _radar(tmp_path):
    return RadarStore(str(tmp_path / "radar.json"))


# ── 1. Helper: velden, fallback, idempotentie ────────────────────────────────────────────────

def test_helper_velden_uit_afgerond_project(tmp_path):
    led, radar = _ledger(tmp_path), _radar(tmp_path)
    pid = led.create("harry_hemp", "Afbreekproef hennep", "human",
                     hypothesis="hennepzolen composteren binnen 90 dagen")
    led.complete(pid, "proef geslaagd: 87% afgebroken")
    rid = signal_from_project(radar, led.get(pid))
    it = radar.get(rid)
    assert it["content"] == "proef geslaagd: 87% afgebroken"          # outcome wint van scope
    assert it["rationale"] == "hennepzolen composteren binnen 90 dagen"
    assert it["role"] == "harry_hemp" and it["feed"] == "Projecten" and it["kind"] == "project"
    assert it["source"] == "projectbord" and it["link"] == f"/project?id={pid}"
    assert it["status"] == "goedgekeurd"                              # done is al de mens-poort
    date.fromisoformat(it["published_at"][:10])                       # ISO (afrondmoment)
    assert radar.seen(f"/project?id={pid}")                           # link gemarkeerd → dedupe-anker


def test_helper_fallbacks_scope_en_village(tmp_path):
    radar = _radar(tmp_path)
    # Geen outcome → "Afgerond: <scope>"; geen owner → rol "village"; geen updated_at → nu (ISO).
    rid = signal_from_project(radar, {"id": "p1", "scope": "Kleine klus"})
    it = radar.get(rid)
    assert it["content"] == "Afgerond: Kleine klus" and it["role"] == "village"
    assert it["rationale"] == ""
    date.fromisoformat(it["published_at"][:10])
    assert signal_from_project(radar, {}) is None                     # zonder id: niets


def test_heropend_en_opnieuw_afgerond_geen_tweede_signaal(tmp_path):
    led, radar = _ledger(tmp_path), _radar(tmp_path)
    pid = led.create("harry_hemp", "Herhaalproef", "human")
    led.complete(pid, "eerste uitkomst")
    assert signal_from_project(radar, led.get(pid)) is not None
    led.reopen(pid)
    led.complete(pid, "ANDERE uitkomst na heropening")                # andere tekst, zelfde link
    assert signal_from_project(radar, led.get(pid)) is None           # link-dedupe via `seen`
    sigs = [it for it in radar.for_role("harry_hemp") if it["feed"] == "Projecten"]
    assert len(sigs) == 1 and sigs[0]["content"] == "eerste uitkomst"


# ── 2. Cockpit-hook: proj_done via dispatch maakt het signaal ────────────────────────────────

def _dd(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd


def test_cockpit_proj_done_maakt_signaal(tmp_path):
    dd = _dd(tmp_path)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Bordklus"], "trekker": [""],
                                       "next": ["/"]}, username="guest")
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    sigs = [it for it in st.radar.for_role(role) if it["feed"] == "Projecten"]
    assert len(sigs) == 1
    assert sigs[0]["status"] == "goedgekeurd" and sigs[0]["link"] == f"/project?id={pid}"
    assert sigs[0]["source"] == "projectbord"
    # Heropenen (drag terug naar actief) + opnieuw done → nog steeds één signaal.
    cockpit2.dispatch(dd, "proj_status", {"pid": [pid], "to": ["actief"], "next": ["/"]},
                      username="guest")
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    st = cockpit2._Stores(dd)
    assert len([it for it in st.radar.for_role(role) if it["feed"] == "Projecten"]) == 1


def test_signals_pagina_krijgt_projecten_feedchip(tmp_path):
    dd = _dd(tmp_path)
    role = "mother_earth__nooch__website_developer"
    cockpit2.dispatch(dd, "proj_add", {"owner": [role], "scope": ["Chip-check"], "trekker": [""],
                                       "next": ["/"]}, username="guest")
    pid = cockpit2._Stores(dd).projects.all()[0]["id"]
    cockpit2.dispatch(dd, "proj_done", {"pid": [pid], "next": ["/"]}, username="guest")
    html = render_signals(cockpit2._Stores(dd))
    assert "?feed=Projecten" in html                                  # feed-chip verschijnt vanzelf
    assert "projectbord" in html                                      # bron op de kaart


# ── 3. Daemon-pad: de board-watch (village._poll_board) maakt het signaal ────────────────────

def _watch(tmp_path, ledger, autonomous=None):
    """Minimale village-stub (zelfde patroon als test_project_completed_event) mét data_dir,
    zodat de board-watch de RadarStore zelf op data_dir kan instantiëren."""
    bus = EventBus(name="test")
    got = []
    bus.subscribe("project_completed", lambda e: got.append(e.data))
    ctx = SimpleNamespace(projects=ledger, deliverables=None, data_dir=str(tmp_path),
                          _autonomous_done=(autonomous or set()))
    return SimpleNamespace(context=ctx, bus=bus, _activated_seen=set(), _completed_seen=set()), got


def test_poll_board_maakt_signaal_bij_nieuwe_done(tmp_path):
    led = _ledger(tmp_path)
    pid = led.create("harry_hemp", "Daemon-klus", "human")
    led.complete(pid, "klaar via de daemon")
    stub, got = _watch(tmp_path, led)
    Village._poll_board(stub)
    assert len(got) == 1                                              # bestaand gedrag: event vuurt
    sigs = _radar(tmp_path).for_role("harry_hemp")
    assert len(sigs) == 1 and sigs[0]["content"] == "klaar via de daemon"
    assert sigs[0]["status"] == "goedgekeurd"
    Village._poll_board(stub)                                         # tweede poll → geen dubbel
    assert len(_radar(tmp_path).for_role("harry_hemp")) == 1


def test_poll_board_autonome_done_krijgt_wel_signaal(tmp_path):
    # Autonome dones worden voor het event geskipt (al inline aangekondigd), maar het
    # signaal hoort er WEL te komen — het is een lifecycle-feit, geen dubbel event.
    led = _ledger(tmp_path)
    pid = led.create("harry_hemp", "Autonome klus", "human")
    led.complete(pid, "autonoom afgerond")
    stub, got = _watch(tmp_path, led, autonomous={pid})
    Village._poll_board(stub)
    assert got == []                                                  # geen dubbel event (bestaand)
    assert len(_radar(tmp_path).for_role("harry_hemp")) == 1          # wél een signaal


# ── 4. Backfill: dry-run telt, echt maakt aan, herdraaien is idempotent ──────────────────────

def test_backfill_dry_run_vs_echt(tmp_path):
    led, radar = _ledger(tmp_path), _radar(tmp_path)
    a = led.create("harry_hemp", "Oud project A", "human")
    b = led.create("concurrent_scout", "Oud project B", "human")
    led.create("harry_hemp", "Loopt nog", "human")                    # geen done → telt niet mee
    led.complete(a, "uitkomst A")
    led.complete(b)                                                   # geen outcome → scope-fallback
    res = backfill_done_projects(led, radar, dry_run=True)
    assert res == {"done": 2, "created": 2, "skipped": 0}
    assert radar.for_role("harry_hemp") == [] and not radar.seen(f"/project?id={a}")   # niets geschreven
    res = backfill_done_projects(led, radar)
    assert res == {"done": 2, "created": 2, "skipped": 0}
    assert {it["content"] for it in radar.all_approved()} == {"uitkomst A", "Afgerond: Oud project B"}
    res = backfill_done_projects(led, radar)                          # herdraaien: link-dedupe
    assert res == {"done": 2, "created": 0, "skipped": 2}
    assert len(radar.all_approved()) == 2


# ── 5. norm_ref: interne projectlinks vallen niet samen bij promotie-dedupe ──────────────────

def test_norm_ref_interne_links_houden_query():
    assert norm_ref("/project?id=aaa") != norm_ref("/project?id=bbb")
    assert norm_ref("/project?id=aaa") == "/project?id=aaa"
    # Externe links houden het bestaande gedrag (utm-staart en www. eraf).
    assert norm_ref("https://www.vivo.com/x?utm_source=nb") == "vivo.com/x"
