"""Eén memo van Noochie aan de founder, op afroep — de toets van de pijp.

Aanleiding (11 september 2026). Stefan zag nooit iets van Noochie en dacht aan de verkeerde inbox.
Gemeten: er wás geen inbox. Het dagbulletin ging naar schijf en naar een logger, en verder nergens.

Wat hier vastligt:

1. De memo komt via de bestaande founder-route (`_notify_founder` → `("role", FOUNDER_ROLE_ID)`)
   met afzender `noochie` en de tekst ONGEWIJZIGD. Die laatste is de scherpe: `NotifStore.add`
   stuurt een item zonder type door een herschrijf-poort die niet-menselijke tekst met een goedkoop
   model herformuleert. Voor een memo is dat verminking onder Noochie's naam.
2. Zonder LLM-antwoord: geen memo en geen bezorging. Nooit een sjabloon alsof zij hem schreef.
3. De invoer is rauw (tellingen, titels), niet eerdere LLM-tekst.
4. Precies één LLM-call, op de hoog-inzet-site.
"""
from __future__ import annotations

from unittest import mock

from nooch_village import cockpit2, noochie_memo
from nooch_village.human_inbox import FOUNDER_ROLE_ID

MEMO = ("## Wat ik zie\n- 20 open claims, 11 rood\n\n## Wat ik zou doen\n- eerst de header\n\n"
        "## Wat ik niet weet\n- de omzet van deze week")


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _founder_items(dd):
    return cockpit2._Stores(dd).notif.for_targets([("role", FOUNDER_ROLE_ID)])


# ── verzamelen ───────────────────────────────────────────────────────────────

def test_verzamelen_is_rauw_en_faalt_per_bron(tmp_path):
    dd, st = _st(tmp_path)
    f = noochie_memo.verzamel(st, dd)
    assert set(f) >= {"datum", "projecten", "claims", "events", "gereedschap", "werkoverleg_backlog"}
    assert f["claims"]["werklijst"] == 20 and f["claims"]["open"] == 20    # de seed-database
    assert f["projecten"]["totaal"] == 0                                    # de fixture heeft er geen
    assert f["events"]["regels"] == 0                                       # geen log in de fixture


def test_de_prompt_bevat_de_feiten_en_geen_eerdere_llm_tekst(tmp_path):
    dd, st = _st(tmp_path)
    p = noochie_memo.prompt_voor(noochie_memo.verzamel(st, dd))
    assert "FEITEN (JSON)" in p and '"werklijst": 20' in p
    assert "field_note" not in p.lower() and "bulletin" not in p.lower()


# ── fail-closed ──────────────────────────────────────────────────────────────

def test_zonder_llm_geen_memo_en_niets_bezorgd(tmp_path):
    dd, st = _st(tmp_path)
    with mock.patch("nooch_village.llm.reason", return_value=None):
        r = noochie_memo.memo(st, dd, apply=True)
    assert r["ok"] is False and r["tekst"] is None and r["bezorgd"] is False
    assert "geen LLM-antwoord" in r["reden"]
    assert _founder_items(dd) == []


def test_dry_run_schrijft_wel_maar_bezorgt_niet(tmp_path):
    dd, st = _st(tmp_path)
    with mock.patch("nooch_village.llm.reason", return_value=MEMO):
        r = noochie_memo.memo(st, dd, apply=False)
    assert r["ok"] and r["tekst"] == MEMO and r["bezorgd"] is False
    assert _founder_items(dd) == []


# ── bezorgen ─────────────────────────────────────────────────────────────────

def test_de_memo_landt_bij_de_founder_van_noochie_en_ongewijzigd(tmp_path):
    dd, st = _st(tmp_path)
    with mock.patch("nooch_village.llm.reason", return_value=MEMO):
        r = noochie_memo.memo(st, dd, apply=True)
    assert r["ok"] and r["bezorgd"]
    items = _founder_items(dd)
    assert len(items) == 1
    it = items[0]
    assert it["by"] == noochie_memo.AFZENDER
    assert it["tekst"] == MEMO, "de herschrijf-poort heeft de memo aangeraakt"
    assert it.get("type") == noochie_memo.TYPE


def test_precies_een_llm_call_op_de_hoog_inzet_site(tmp_path):
    """De herschrijf-poort in `NotifStore.add` zou een TWEEDE call doen (escalation_route) als het
    item zonder type binnenkwam. Eén call, en het is de onze."""
    dd, st = _st(tmp_path)
    with mock.patch("nooch_village.llm.reason", return_value=MEMO) as m:
        noochie_memo.memo(st, dd, apply=True)
    sites = [c.kwargs.get("call_site") for c in m.call_args_list]
    assert sites == [noochie_memo.CALL_SITE], sites


def test_de_memo_site_is_hoog_inzet():
    from nooch_village.llm_keuze import HOOG_INZET, ladder_voor
    assert noochie_memo.CALL_SITE in HOOG_INZET
    ladder = ladder_voor(noochie_memo.CALL_SITE) or ""
    assert ladder.startswith("anthropic:claude-sonnet"), ladder


def test_notify_founder_zonder_extra_blijft_identiek(tmp_path):
    """De elf bestaande aanroepers geven geen `extra` mee; voor hen mag niets veranderen —
    inclusief dat hun item wél langs de poort gaat (die typeert een rauwe signalering)."""
    from nooch_village.human_inbox import _notify_founder
    dd, st = _st(tmp_path)
    inbox = f"{dd}/human_inbox.json"
    with mock.patch("nooch_village.notifications._door_de_poort", return_value={}) as poort:
        _notify_founder(inbox, by="dorp", snippet="rauwe signalering")
        assert poort.called, "zonder type hoort een item langs de poort te gaan"
        poort.reset_mock()
        _notify_founder(inbox, by="noochie", snippet=MEMO, extra={"type": noochie_memo.TYPE})
        assert not poort.called, "met een type hoort een item de poort over te slaan"


def test_projecttitels_komen_uit_scope_zoals_op_het_bord(tmp_path):
    """Mijn eerste versie las `title`; op de echte data gaf dat zestien lege titels. De kaarttitel
    is `scope`, en `_scope_text` is de ene plek die dat afleidt — hier dus ook."""
    dd, st = _st(tmp_path)
    rol = "mother_earth__nooch__website_developer"
    lopend = st.projects.create(rol, "Website Re-Design Done", "human", status="queued")
    st.projects.start(lopend)
    vast = st.projects.create(rol, "Black and White 269 samples made", "human", status="queued")
    st.projects.start(vast)
    st.projects.block(vast, on_role="mother_earth__nooch__creator_of_shoes")
    f = noochie_memo.verzamel(cockpit2._Stores(dd), dd)
    assert [r["titel"] for r in f["projecten"]["lopend"]] == ["Website Re-Design Done"]
    vastgelopen = f["projecten"]["vastgelopen"]
    assert [r["titel"] for r in vastgelopen] == ["Black and White 269 samples made"]
    assert "creator_of_shoes" in vastgelopen[0].get("wacht_op", "")   # waar hij op wacht reist mee
