"""HarryHemp maakt autonoom een onderzoeksproject van een goedgekeurd high_potential GSC-keyword.

Dekt: filter op status==approved; herkomst-check uit de LIBRARY-evidence (gsc + high_potential),
niet uit de event-payload; fail-closed bij ontbrekend record/evidence; dedup over álle statussen
(ook DONE) op keyword+origin; open-plafond uit config. Thread-vrij: de handler wordt direct aangeroepen.
"""
from __future__ import annotations
import logging
from types import SimpleNamespace

from nooch_village.roles import HarryHemp
from nooch_village.models import Record, RoleDefinition, RecordType
from nooch_village.event_bus import EventBus, Event
from nooch_village.skills import SkillRegistry
from nooch_village.projects import ProjectLedger
from nooch_village.library import Library

_SCOPE = ("Onderzoek naar '{kw}': patenten, wetenschappelijke studies "
          "en culturele trend in kaart gebracht")


def _make(tmp_path, **settings):
    bus = EventBus(name="test")
    lib = Library(str(tmp_path / "library.json"))
    ledger = ProjectLedger(str(tmp_path / "projects.json"))
    ctx = SimpleNamespace(
        settings={"tijdgeest_interval_seconds": "0", "reflect_interval_seconds": "0", **settings},
        data_dir=str(tmp_path), records=None, library=lib, projects=ledger,
    )
    rec = Record(id="harry_hemp", type=RecordType.ROLE, parent="noochville",
                 definition=RoleDefinition(purpose="The Scientist", skills=["ngram_culture"]),
                 source="seed")
    harry = HarryHemp(rec, bus, SkillRegistry(), ctx)
    return harry, lib, ledger


def _decided(word, status="approved"):
    return Event("keyword_decided", {"word": word, "status": status, "reason": "r"}, "librarian")


def _approve(lib, word, *, source="gsc", bucket="high_potential"):
    lib.curate(word, "approved", evidence={"source": source, "bucket": bucket})


def _kw_projects(ledger):
    return [p for p in ledger.all() if p.get("origin") == "keyword_research"]


# happy path: approved + gsc/high_potential → project in TOEKOMST met de juiste velden
def test_maakt_onderzoeksproject(tmp_path):
    harry, lib, ledger = _make(tmp_path)
    _approve(lib, "barefoot shoes")
    harry._on_keyword_decided(_decided("barefoot shoes"))
    ps = _kw_projects(ledger)
    assert len(ps) == 1
    p = ps[0]
    assert p["owner"] == "harry_hemp" and p["status"] == "future" and p["trigger"] == "role"
    assert p["origin"] == "keyword_research" and p["keyword"] == "barefoot shoes"
    assert p["scope"] == _SCOPE.format(kw="barefoot shoes")


# niet-approved statussen worden stil genegeerd
def test_forbidden_known_genegeerd(tmp_path):
    harry, lib, ledger = _make(tmp_path)
    _approve(lib, "vegan shoes")                       # library zegt approved...
    harry._on_keyword_decided(_decided("vegan shoes", status="forbidden"))  # ...maar event = forbidden
    harry._on_keyword_decided(_decided("vegan shoes", status="known"))
    assert _kw_projects(ledger) == []


# fail-closed: verkeerde bron of bucket, of geen library-record → geen project
def test_failclosed_herkomst(tmp_path):
    harry, lib, ledger = _make(tmp_path)
    _approve(lib, "trends woord", source="google_trends")   # geen gsc
    _approve(lib, "lage bucket", bucket="page1")             # geen high_potential
    harry._on_keyword_decided(_decided("trends woord"))
    harry._on_keyword_decided(_decided("lage bucket"))
    harry._on_keyword_decided(_decided("nooit gezien"))      # geen library-record
    assert _kw_projects(ledger) == []


# dedup over ALLE statussen (ook DONE): nooit een tweede project voor hetzelfde keyword
def test_dedup_over_alle_statussen(tmp_path):
    harry, lib, ledger = _make(tmp_path)
    _approve(lib, "midsole foam")
    harry._on_keyword_decided(_decided("midsole foam"))
    pid = _kw_projects(ledger)[0]["id"]
    ledger.get(pid)["status"] = "done"; ledger._save()       # zet het eerste op DONE
    harry._on_keyword_decided(_decided("midsole foam"))      # zelfde keyword opnieuw goedgekeurd
    assert len(_kw_projects(ledger)) == 1                    # geen tweede project


# plafond: max N open (niet-DONE) keyword_research-projecten (uit config)
def test_open_plafond(tmp_path):
    harry, lib, ledger = _make(tmp_path, keyword_research_open_limit="1")
    _approve(lib, "woord een"); _approve(lib, "woord twee")
    harry._on_keyword_decided(_decided("woord een"))         # 1 open → mag
    harry._on_keyword_decided(_decided("woord twee"))        # plafond (1/1) → niet
    ps = _kw_projects(ledger)
    assert len(ps) == 1 and ps[0]["keyword"] == "woord een"
    # zodra de eerste DONE is, is er weer plek
    ledger.get(ps[0]["id"])["status"] = "done"; ledger._save()
    harry._on_keyword_decided(_decided("woord twee"))
    assert len(_kw_projects(ledger)) == 2


# ── Branded-filter: merkqueries blijven approved in de library maar spawnen geen project ──
def test_branded_woord_geen_project(tmp_path, caplog):
    harry, lib, ledger = _make(tmp_path)                       # default branded_tokens (incl. 'nooch')
    _approve(lib, "nooches")                                    # merkquery, approved + gsc/high_potential
    with caplog.at_level(logging.DEBUG):
        harry._on_keyword_decided(_decided("nooches"))
    assert _kw_projects(ledger) == []
    assert any("branded keyword overgeslagen" in r.message for r in caplog.records)


def test_niet_branded_wel_project(tmp_path):
    harry, lib, ledger = _make(tmp_path)
    _approve(lib, "barefoot shoes")
    harry._on_keyword_decided(_decided("barefoot shoes"))
    ps = _kw_projects(ledger)
    assert len(ps) == 1 and ps[0]["keyword"] == "barefoot shoes"   # niet-branded → project zoals voorheen


def test_branded_substring_gefilterd(tmp_path):
    harry, lib, ledger = _make(tmp_path)
    _approve(lib, "nooch amsterdam")                            # 'nooch' als substring
    harry._on_keyword_decided(_decided("nooch amsterdam"))
    assert _kw_projects(ledger) == []


def test_lege_config_filter_uit(tmp_path):
    harry, lib, ledger = _make(tmp_path, branded_tokens="")     # lege config → filter uit
    _approve(lib, "nooches")
    harry._on_keyword_decided(_decided("nooches"))
    ps = _kw_projects(ledger)
    assert len(ps) == 1 and ps[0]["keyword"] == "nooches"      # alles door
