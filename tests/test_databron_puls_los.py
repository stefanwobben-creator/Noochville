"""De databron-collector en de dode-bron-sensor zijn geen rolwerk meer (16 sept 2026).

AANLEIDING: het gdelt_tone/vegan_footwear-alert (9 dagen geen data) leidde naar de generieke
dagelijkse-observatie-collector (`_collect_daily_observations`) en de dode-bron-sensor
(`_sense_dead_sources`), die tot dan toe UITSLUITEND liepen via `WebsiteWatcherWorker._morning_pulse`
— dus alleen zolang die ene rol leefde. Slaapt of archiveert `website_watcher` (en dat gaat gebeuren,
zie claude/verwijderplan_ai_rollen.md), dan stopte niet alleen gdelt_tone maar de dagelijkse
verzameling van ELKE databron, en de melding daarvan. Exact de dagcyclus-les van 28 augustus (de
dagbel hing toen aan `facilitator`, zie test_hartslag_los.py), nu toegepast op databronnen.

Verplaatst naar Village, rechtstreeks op `dag_begint` (rolonafhankelijk) i.p.v. `pulse_completed`
(dat blijft uitsluitend een website_watcher-signaal, zie test_afslank_poort.py geval 3 — en dat
is precies waarom de bestaande vangnetten `_veilig_verweesd`/`_veilig_weesprojecten` HIER ook van
`pulse_completed` naar `dag_begint` zijn verhuisd: `pulse_completed` komt alleen van
website_watcher se eigen puls en vuurt dus nooit als die rol slaapt)."""
from __future__ import annotations

import types

from nooch_village.village import Village
import nooch_village.collector as collector_mod
import nooch_village.deadsource as deadsource_mod


class _FakeBus:
    def __init__(self):
        self.published = []

    def publish(self, event):
        self.published.append(event)


class _FakeContext:
    def __init__(self, data_dir):
        self.observations = object()
        self.sources = object()
        self.data_dir = data_dir


class _FakeVillage:
    """Geen echte Village (die bouwt bij __init__ het hele dorp op) — alleen wat de drie
    geteste methoden nodig hebben."""

    def __init__(self, data_dir):
        self.context = _FakeContext(data_dir)
        self.registry = object()
        self.bus = _FakeBus()


def test_collect_daily_observations_roept_de_echte_collector_aan(tmp_path, monkeypatch):
    calls = []

    def fake_collect(registry, sources, obs, context):
        calls.append((registry, sources, obs, context))
        return ["gdelt_tone_vegan_footwear_day"]

    monkeypatch.setattr(collector_mod, "collect_daily_observations", fake_collect)
    v = _FakeVillage(str(tmp_path))
    Village._collect_daily_observations(v)
    assert calls == [(v.registry, v.context.sources, v.context.observations, v.context)]


def test_collect_daily_observations_is_fail_closed(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kapot")

    monkeypatch.setattr(collector_mod, "collect_daily_observations", boom)
    v = _FakeVillage(str(tmp_path))
    Village._collect_daily_observations(v)      # mag niet raisen


def test_sense_dead_sources_publiceert_source_died_met_by_dorp(tmp_path, monkeypatch):
    def fake_sense(registry, context, state, emit):
        emit("gdelt_tone", "vegan_footwear", "2026-09-07", 9, "dagelijks")
        return ["gdelt_tone:vegan_footwear"]

    monkeypatch.setattr(deadsource_mod, "sense_dead_sources", fake_sense)
    v = _FakeVillage(str(tmp_path))
    Village._sense_dead_sources(v)
    assert len(v.bus.published) == 1
    ev = v.bus.published[0]
    assert ev.name == "source_died"
    assert ev.data["source"] == "gdelt_tone" and ev.data["field"] == "vegan_footwear"
    assert ev.data["days_ago"] == 9
    assert ev.data["by"] == "dorp", "niet meer een rol-id — dit is nu dorpsinfrastructuur"


def test_sense_dead_sources_is_fail_closed(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kapot")

    monkeypatch.setattr(deadsource_mod, "sense_dead_sources", boom)
    v = _FakeVillage(str(tmp_path))
    Village._sense_dead_sources(v)               # mag niet raisen


def test_veilig_databron_puls_draait_beide_stappen_in_volgorde_en_is_fail_soft_per_stap():
    order = []

    def fake_collect(self):
        order.append("collect")
        raise RuntimeError("collector kapot")

    def fake_sense(self):
        order.append("sense")

    v = _FakeVillage("")
    v._collect_daily_observations = types.MethodType(fake_collect, v)
    v._sense_dead_sources = types.MethodType(fake_sense, v)
    Village._veilig_databron_puls(v)
    assert order == ["collect", "sense"], "een falende collector mag de dode-bron-sensor niet blokkeren"


def test_source_died_hangt_aan_geen_enkele_rol_meer():
    """De statische afhankelijkheids-gate moet de verhuizing ook zo zien — anders is hij alleen in
    de runtime waar, niet in de poort die `afslanken.voer_uit` gebruikt.

    Stond op `website_watcher`, die `source_died` publiceerde tot de collector op 16 sept 2026 naar
    Village verhuisde. Die rol bestaat sinds 19 sept niet meer als klasse, dus de meting is nu
    sterker geworden: source_died hangt aan GEEN ENKELE rol. Komt hij ooit weer bij een rol terecht,
    dan faalt deze test, en dat is precies de bedoeling — dorpsinfrastructuur hoort niet in een rol
    terug te kruipen."""
    from nooch_village import afslank_afhankelijkheden as aa
    from nooch_village.governance import Records
    from nooch_village.village import BASE_DIR
    import os

    recs = Records(os.path.join(BASE_DIR, "data", "governance_records.json"))
    for rec in recs.all():
        ev = {e["event"] for e in aa.rol_afhankelijkheden(rec.id, recs)["events"]}
        assert "source_died" not in ev, f"{rec.id} publiceert source_died weer als rolwerk"
