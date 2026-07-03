"""Tripwire: een checklist-verplichting is cirkel-breed ("all") of rol-gebonden ("role"),
NOOIT per individu. Deze test maakt de ontwerpbeslissing tot code — zodra iemand een
per-individu-type toevoegt, faalt hij bewust."""
from __future__ import annotations

from nooch_village import checklists
from nooch_village.checklists import ChecklistStore, period_key


def test_target_types_zijn_exact_all_en_role():
    # De set van geldige target-types is precies {all, role} — geen per-individu-variant.
    assert set(checklists.TARGET_TYPES) == {"all", "role"}
    for verboden in ("individual", "person", "filler"):
        assert verboden not in checklists.TARGET_TYPES


def test_per_individu_type_wordt_geweigerd(tmp_path):
    # Een per-individu-type wordt niet opgeslagen maar gecoerced naar de cirkel-brede default.
    st = ChecklistStore(str(tmp_path / "cl.json"))
    for verboden in ("individual", "person", "filler"):
        it = st.add("noochville", "iets", "week", target_type=verboden)
        assert it["target_type"] == "all"


def test_all_afgevinkt_door_lid_telt_voor_de_cirkel(tmp_path):
    # target_type="all": lid A vinkt af NAMENS de cirkel. Eén status per periode (niet per lid);
    # wie afvinkte staat in reports[periode].by. Er is GEEN per-filler-statusstructuur.
    st = ChecklistStore(str(tmp_path / "cl.json"))
    it = st.add("noochville", "wekelijkse review", "week", target_type="all")
    assert st.report(it["id"], True, by="lid-A")

    item = st.get(it["id"])
    # de status geldt voor de cirkel, niet gebonden aan A
    assert ChecklistStore.current_status(item) is True
    reports = item["reports"]
    # precies één rapport voor de huidige periode; geen per-lid-vertakking
    assert set(reports.keys()) == {period_key("week")}
    rep = reports[period_key("week")]
    assert rep["by"] == "lid-A"                       # wie afvinkte staat in reports.by
    # GEEN per-individu-status: het item kent geen per-filler-veld
    assert not any(k in item for k in ("per_filler", "filler_status", "individual", "by_filler"))
