"""Een DNA-grant mag geen thread starten. Daar zit een mens tussen.

`heeft_runner` klapt om zodra een rol één GEREGISTREERDE skill in zijn DNA heeft. De domein-regrant
in `seeds.migrate_records` schrijft precies zo'n skill, en op 16 september bleek wat dat betekende:
`mother_earth__nooch__creator_of_shoes` — een rol die een MENS vervult, met nul skills — zou bij de
eerstvolgende start een eigen thread krijgen en beide materiaal-memo's elke dagpuls draaien. Niemand
had daar ja op gezegd; het volgde uit een seed-regel die over eigenaarschap ging, niet over capaciteit.

Dat is de grens uit CLAUDE.md: "uitbreiding van capaciteit is altijd mens-gated", dezelfde
geboren-versus-bemenst-splitsing als bij rollen. Een `add_role` schrijft een definitie en start geen
thread; een domein-grant schrijft gereedschap en start er net zo min een.

DE SCHEIDING DIE DIT BESTAND BEWAAKT:

    het DNA                 verandert meteen — de rol HOUDT het gereedschap
    het DRAAIEN             wacht op een mens in de human inbox
    een NEE                 laat het DNA staan en zet alleen geen thread aan
    wie al draaide          merkt niets — de poort werkt nooit met terugwerkende kracht
"""
from __future__ import annotations

from types import SimpleNamespace

from nooch_village import cockpit2, goedkeuring, materiaal_memo, org
from nooch_village.governance import Records, heeft_runner
from nooch_village.human_inbox import HumanInbox
from nooch_village.inbox_actions import decide_runner_activatie
from nooch_village.registry_factory import build_skill_registry
from nooch_village.seeds import migrate_records
from nooch_village.village import CLASS_MAP

MATERIAAL = ("materiaal_kwartaal", "materiaal_shortlist")


def _stores(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return cockpit2._Stores(dd)


def _runner(rec):
    return heeft_runner(rec, class_map=CLASS_MAP, registry=build_skill_registry())


def _houder(st):
    return org.role_for_domain(st.records.all(), materiaal_memo.eigenaar_domein(st.dd))


def _inbox(st):
    return HumanInbox(str(st.dd) + "/human_inbox.json")


def _poort_items(hi, rid):
    """De poort-items voor DEZE rol. Niet "het enige item": in de PoC-fixture heeft ook Compliance
    nul skills, dus die krijgt bij dezelfde seed-run zijn eigen poort — terecht. Een test die op
    "precies één item" leunt, toetst de fixture en niet het gedrag."""
    return [i for i in hi.all() if i["type"] == "runner_activatie" and i["subject"] == rid]


def _pending_voor(hi, rid):
    return [i for i in _poort_items(hi, rid) if i["status"] == "pending"]


# ── de poort zelf ─────────────────────────────────────────────────────────────

def test_de_grant_landt_wel_maar_de_thread_niet(tmp_path):
    """De kern. Twee uitspraken die uit elkaar moeten blijven: hij HEEFT het, hij DRAAIT het niet."""
    st = _stores(tmp_path)
    rid = _houder(st).id
    assert _runner(st.records.get(rid))[0] is False          # vooraf: geen skills, geen thread
    migrate_records(st.records)

    rec = st.records.get(rid)
    for s in MATERIAAL:
        assert s in rec.definition.skills, s                 # DNA: wél
    assert rec.activatie_vereist is True
    assert _runner(rec)[0] is False                          # thread: niet


def test_de_poort_overleeft_een_herstart(tmp_path):
    """`Records._save` serialiseert het hele dataclass, `_load` noemt elk veld met de hand. Een nieuw
    veld wordt dus wél geschreven en niet teruggelezen — en dan staat de poort in het bestand terwijl
    `heeft_runner` hem nooit ziet. Die asymmetrie meldt zichzelf niet; deze test wel."""
    st = _stores(tmp_path)
    rid = _houder(st).id
    migrate_records(st.records)
    vers = Records(st.records.path)                          # zoals een daemon-herstart hem leest
    assert vers.get(rid).activatie_vereist is True
    assert _runner(vers.get(rid))[0] is False


def test_de_reden_reist_mee(tmp_path):
    """Een dichte poort zonder reden is niet te onderscheiden van een kapotte rol."""
    st = _stores(tmp_path)
    migrate_records(st.records)
    reden = st.records.get(_houder(st).id).activatie_reden
    assert "materiaal_kwartaal" in reden and "Materials" in reden
    assert _runner(st.records.get(_houder(st).id))[1] == reden


def test_wie_al_draaide_merkt_niets(tmp_path):
    """GEEN TERUGWERKENDE KRACHT. Compliance draait vandaag op 'actieve skill'; zou de poort ook voor
    hem gelden, dan zet deze scope het halve dorp stil."""
    st = _stores(tmp_path)
    compliance = st.records.get("mother_earth__nooch__compliance")
    compliance.definition.skills = ["claims_check"]
    st.records.put(compliance)
    assert _runner(st.records.get("mother_earth__nooch__compliance"))[0] is True

    migrate_records(st.records)
    na = st.records.get("mother_earth__nooch__compliance")
    assert na.activatie_vereist is False
    assert _runner(na)[0] is True


def test_een_tweede_seed_run_zet_geen_tweede_poort(tmp_path):
    st = _stores(tmp_path)
    rid = _houder(st).id
    migrate_records(st.records)
    reden = st.records.get(rid).activatie_reden
    migrate_records(st.records)
    assert st.records.get(rid).activatie_reden == reden      # niet overschreven, niet verdubbeld


# ── de vraag aan de mens ──────────────────────────────────────────────────────

def test_de_poort_wordt_een_vraag_in_de_inbox(tmp_path):
    """Een poort zonder vraag is stilletjes niets doen met een logregel erbij."""
    st = _stores(tmp_path)
    rid = _houder(st).id
    migrate_records(st.records)
    hi = _inbox(st)
    assert hi.sync_runner_gates(st.records.all()) >= 1
    item = _pending_voor(hi, rid)[0]
    assert set(MATERIAAL) <= set(item["context"]["skills"])
    assert "HOUDT de skills" in item["context"]["effect_nee"]


def test_de_sync_is_idempotent(tmp_path):
    st = _stores(tmp_path)
    rid = _houder(st).id
    migrate_records(st.records)
    hi = _inbox(st)
    hi.sync_runner_gates(st.records.all())
    assert hi.sync_runner_gates(st.records.all()) == 0, "tweede sync mag niets toevoegen"
    assert len(_poort_items(hi, rid)) == 1


def test_het_cockpit_mag_hier_geen_ja_zeggen(tmp_path):
    """Zelfde regel als bij `activation`: nee en later mogen altijd, ja blijft op de commandoregel.
    Een rol laten draaien is geen knop-besluit."""
    assert goedkeuring.mag_ja("runner_activatie") is False
    assert goedkeuring.waarom_niet("runner_activatie")
    assert goedkeuring.vraag_van({"type": "runner_activatie"}) != "Decide on this item?"


def test_een_gearchiveerde_rol_laat_geen_vraag_achter(tmp_path):
    """De premisse vervalt: is de rol weg, dan is 'mag hij draaien?' geen vraag meer."""
    st = _stores(tmp_path)
    rid = _houder(st).id
    migrate_records(st.records)
    hi = _inbox(st)
    hi.sync_runner_gates(st.records.all())
    rec = st.records.get(rid)
    rec.archived = True
    st.records.put(rec)
    assert hi.withdraw_archived_activations(st.records.all()) >= 1
    assert _pending_voor(hi, rid) == []


# ── het besluit ───────────────────────────────────────────────────────────────

def test_ja_neemt_de_poort_weg(tmp_path):
    st = _stores(tmp_path)
    rid = _houder(st).id
    migrate_records(st.records)
    hi = _inbox(st)
    hi.sync_runner_gates(st.records.all())
    iid = _pending_voor(hi, rid)[0]["id"]

    r = decide_runner_activatie(hi, st.records, iid, "approved", reason="ja")
    assert r["ok"] and r["poort_weg"] is True
    assert _runner(st.records.get(rid))[0] is True
    assert hi.get(iid)["status"] == "approved"


def test_nee_laat_het_dna_staan_en_start_niets(tmp_path):
    """Een weigering gaat over DRAAIEN, niet over bezit. Wie het gereedschap ook weg wil, gebruikt
    `afslanken.skill_intrekken` — dat zet de intrek-guard, en de seed respecteert die."""
    st = _stores(tmp_path)
    rid = _houder(st).id
    migrate_records(st.records)
    hi = _inbox(st)
    hi.sync_runner_gates(st.records.all())
    iid = _pending_voor(hi, rid)[0]["id"]

    r = decide_runner_activatie(hi, st.records, iid, "rejected", reason="nee")
    assert r["ok"] and r["poort_weg"] is False
    rec = st.records.get(rid)
    for s in MATERIAAL:
        assert s in rec.definition.skills, s                 # DNA ongemoeid
    assert _runner(rec)[0] is False                          # en nog steeds geen thread


def test_een_nee_komt_niet_terug_als_nieuwe_vraag(tmp_path):
    """Dedup op role_id ongeacht status — anders staat morgen dezelfde vraag er weer."""
    st = _stores(tmp_path)
    rid = _houder(st).id
    migrate_records(st.records)
    hi = _inbox(st)
    hi.sync_runner_gates(st.records.all())
    decide_runner_activatie(hi, st.records, _pending_voor(hi, rid)[0]["id"], "rejected", reason="nee")
    assert hi.sync_runner_gates(st.records.all()) == 0
    assert _pending_voor(hi, rid) == []
    assert len(_poort_items(hi, rid)) == 1


def test_het_besluit_weigert_een_ander_type(tmp_path):
    st = _stores(tmp_path)
    hi = _inbox(st)
    iid = hi.add_verband("a", "b", "omdat")
    r = decide_runner_activatie(hi, st.records, iid, "approved")
    assert r["ok"] is False and "geen runner_activatie" in r["error"]


def test_het_besluit_weigert_een_onbekend_besluit(tmp_path):
    st = _stores(tmp_path)
    rid = _houder(st).id
    migrate_records(st.records)
    hi = _inbox(st)
    hi.sync_runner_gates(st.records.all())
    iid = _pending_voor(hi, rid)[0]["id"]
    assert decide_runner_activatie(hi, st.records, iid, "misschien")["ok"] is False


def test_het_item_gaat_dicht_ook_zonder_record(tmp_path):
    """Anders komt dezelfde onbeslisbare vraag morgen terug en groeit de rij die we leeghalen."""
    st = _stores(tmp_path)
    rid = _houder(st).id
    migrate_records(st.records)
    hi = _inbox(st)
    hi.sync_runner_gates(st.records.all())
    iid = _pending_voor(hi, rid)[0]["id"]

    leeg = SimpleNamespace(get=lambda _rid: None)
    r = decide_runner_activatie(hi, leeg, iid, "approved", reason="record weg")
    assert r["ok"] is True and r["poort_weg"] is False
    assert hi.get(iid)["status"] == "approved"


def test_het_item_leest_als_een_vraag_met_inhoud(tmp_path):
    """Een item dat op `subject` terugvalt toont een rol-id als samenvatting, en dat leest als "dit
    item heeft geen inhoud" — de fout die 78 items zeventig dagen onaangeroerd hielp houden."""
    st = _stores(tmp_path)
    rid = _houder(st).id
    migrate_records(st.records)
    hi = _inbox(st)
    hi.sync_runner_gates(st.records.all())
    item = _pending_voor(hi, rid)[0]

    samenvatting = goedkeuring.samenvatting(item)
    assert samenvatting != rid, "viel terug op subject: de reden wordt niet gevonden"
    assert "materiaal_kwartaal" in samenvatting
    assert goedkeuring.cli_regel(item, "approve").endswith(f"{item['id']}'")
