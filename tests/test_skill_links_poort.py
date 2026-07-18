"""Taak 4 — de poort om, achter de vlag `skill_links_active`.

Vlag uit: gedrag identiek aan vandaag (poort op rol-DNA). Vlag aan: de poort leest
effectief(rol) = DNA ∪ koppelingen. De domeinregel geldt fail-closed in BEIDE standen.
"""
from __future__ import annotations

from nooch_village.ai_tasks import AITaskStore
from nooch_village.config import Context
from nooch_village.event_bus import EventBus
from nooch_village.inhabitant import Inhabitant
from nooch_village.models import Record, RecordType, RoleDefinition, Task
from nooch_village.skills import Skill, SkillRegistry


class _Echo(Skill):
    name = "site_health"
    description = "test"

    def run(self, payload, context):
        return {"ok": True}


class _Beslis(Skill):
    name = "keyword_review"
    description = "test — beslist in het bibliotheek-domein"

    def run(self, payload, context):
        return {"ok": True}


def _registry():
    reg = SkillRegistry()
    reg.register(_Echo())
    reg.register(_Beslis())
    return reg


def _inwoner(tmp_path, *, dna_skills=(), domains=(), vlag="0", links=None):
    rec = Record(id="rol_x", type=RecordType.ROLE, parent="wortel",
                 definition=RoleDefinition(purpose="p", accountabilities=["iets doen"],
                                           skills=list(dna_skills), domains=list(domains)))
    ctx = Context(settings={"skill_links_active": vlag}, data_dir=str(tmp_path))
    ctx.links = links
    return Inhabitant(rec, EventBus(), _registry(), ctx)


def _link_store(tmp_path, skill="site_health"):
    ai = AITaskStore(str(tmp_path / "ai.json"))
    ai.add_link("rol_x", "acc_1", skill)
    return ai


# ── Vlag uit: gedrag als vandaag ─────────────────────────────────────────────

def test_vlag_uit_koppeling_geeft_geen_toegang(tmp_path):
    inh = _inwoner(tmp_path, vlag="0", links=_link_store(tmp_path))
    assert inh.effective_skills() == set()
    assert inh.use_skill("site_health", {})["error"]
    assert inh.handle(Task(capability="site_health", payload={})).success is False


def test_vlag_uit_dna_werkt_gewoon(tmp_path):
    inh = _inwoner(tmp_path, dna_skills=["site_health"], vlag="0")
    assert inh.use_skill("site_health", {}) == {"ok": True}
    assert inh.handle(Task(capability="site_health", payload={})).success is True


# ── Vlag aan: de koppeling is de tweede sleutel ──────────────────────────────

def test_vlag_aan_koppeling_geeft_toegang(tmp_path):
    inh = _inwoner(tmp_path, vlag="1", links=_link_store(tmp_path))
    assert inh.effective_skills() == {"site_health"}
    assert inh.use_skill("site_health", {}) == {"ok": True}
    assert inh.handle(Task(capability="site_health", payload={})).success is True


def test_vlag_aan_dna_blijft_de_vloer(tmp_path):
    """Een koppeling neemt nooit iets af: DNA-skills blijven werken."""
    inh = _inwoner(tmp_path, dna_skills=["site_health"], vlag="1",
                   links=_link_store(tmp_path, "keyword_review"))
    assert "site_health" in inh.effective_skills()
    assert inh.use_skill("site_health", {}) == {"ok": True}


def test_vlag_aan_zonder_koppeling_weigert_nog_steeds(tmp_path):
    inh = _inwoner(tmp_path, vlag="1", links=AITaskStore(str(tmp_path / "leeg.json")))
    assert inh.use_skill("site_health", {})["error"]


def test_vlag_aan_zonder_store_faalt_zacht(tmp_path):
    inh = _inwoner(tmp_path, vlag="1", links=None)
    assert inh.effective_skills() == set()
    assert inh.use_skill("site_health", {})["error"]


# ── De domeinregel: fail-closed in BEIDE standen ─────────────────────────────

def test_domeinskill_geweigerd_ondanks_dna(tmp_path):
    """Verdediging in de diepte: ook een per ongeluk gegrante beslis-skill wordt geweigerd."""
    inh = _inwoner(tmp_path, dna_skills=["keyword_review"], vlag="0")
    fout = inh.use_skill("keyword_review", {})["error"]
    assert "bibliotheek" in fout and "domeinhouder" in fout
    assert inh.handle(Task(capability="keyword_review", payload={})).success is False


def test_domeinskill_geweigerd_ondanks_koppeling(tmp_path):
    inh = _inwoner(tmp_path, vlag="1", links=_link_store(tmp_path, "keyword_review"))
    assert "keyword_review" in inh.effective_skills()      # de koppeling bestaat…
    assert "domeinhouder" in inh.use_skill("keyword_review", {})["error"]   # …maar mag niet draaien


def test_domeinhouder_mag_de_beslisskill_wel(tmp_path):
    inh = _inwoner(tmp_path, dna_skills=["keyword_review"], domains=["bibliotheek"], vlag="0")
    assert inh.use_skill("keyword_review", {}) == {"ok": True}


# ── Dode-capability-audit telt beide routes ──────────────────────────────────

def test_dormant_telt_koppelingen_mee(tmp_path):
    class _Roept(Inhabitant):
        def doe(self):
            self.use_skill("site_health", {})

    rec = Record(id="rol_x", type=RecordType.ROLE, parent="w",
                 definition=RoleDefinition(purpose="p", skills=[]))
    ctx = Context(settings={"skill_links_active": "1"}, data_dir=str(tmp_path))
    ctx.links = _link_store(tmp_path)
    inh = _Roept(rec, EventBus(), _registry(), ctx)
    assert inh.dormant_capabilities() == set()          # gedekt via de koppeling

    ctx.settings["skill_links_active"] = "0"
    assert inh.dormant_capabilities() == {"site_health"}   # vlag uit: weer dood


# ── gap_classifier leest de effectieve set ───────────────────────────────────

def test_classify_gap_telt_koppelingen_mee_indien_meegegeven(tmp_path):
    from nooch_village.gap_classifier import classify_gap
    rec = Record(id="rol_x", type=RecordType.ROLE, parent="w",
                 definition=RoleDefinition(purpose="de health van de site bewaken",
                                           accountabilities=["health van de site bewaken"],
                                           skills=[]))
    gap = "de health van de site bewaken"
    assert classify_gap(gap, [rec])[0] == "B"                       # mandaat wel, middel niet
    assert classify_gap(gap, [rec], links=_link_store(tmp_path))[0] == "A"   # koppeling dekt het
