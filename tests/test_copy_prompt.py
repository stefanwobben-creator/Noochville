"""Copy Prompt Generator — de prompt moet de policies LEZEN, niet dragen.

De kern van deze view is een belofte: er staat geen policy-tekst in de code. Deze tests bewijzen
dat door de store te wijzigen en te eisen dat de prompt meebeweegt. Faalt een van deze tests, dan
is er ergens een kopie ontstaan (CLAUDE.md, reference-don't-copy).
"""
from __future__ import annotations

import os

import pytest

from nooch_village import artefacts
from nooch_village.attachments import AttachmentStore
from nooch_village.views import copy_prompt as cp


class _NepDefinitie:
    def __init__(self, naam, purpose="", domains=(), accountabilities=()):
        self.name = naam
        self.purpose = purpose
        self.domains = list(domains)
        self.accountabilities = list(accountabilities)


class _NepRecord:
    def __init__(self, rid, naam, parent=None, **kw):
        self.id = rid
        self.parent = parent
        self.definition = _NepDefinitie(naam, **kw)
        self.type = "role"


class _NepRecords:
    def __init__(self, items):
        self._items = {r.id: r for r in items}

    def get(self, rid):
        return self._items.get(rid)

    def all(self):
        return list(self._items.values())


class _NepStores:
    def __init__(self, records, att):
        self.records = records
        self.att = att


@pytest.fixture()
def dorp(tmp_path):
    """Eén cirkel met een kindrol; de policies hangen aan de rol."""
    records = _NepRecords([
        _NepRecord("nooch", "Nooch"),
        _NepRecord("nooch__email", "Community and Email", parent="nooch",
                   purpose="Build a strong community.", domains=["Tone of voice"],
                   accountabilities=["Writing email flows"]),
    ])
    att = AttachmentStore(os.path.join(str(tmp_path), "attachments.json"))
    att.add("nooch__email", "policy", title="Tone of Voice",
            body="We are the better option.\n\n**Register**\n\nOne dominant register.\n\n"
                 "* THINK: never thought about shoes like that\n"
                 "* LAUGH: dry observation\n\nIn a series: no two in a row.\n",
            domain="Tone of voice")
    att.add("nooch__email", "policy", title="Copy Check",
            body="**Smirk Check.** Does it raise an eyebrow?", domain="Tone of voice")
    return _NepStores(records, att)


def _ctx(dorp, rol="nooch__email"):
    return artefacts.serialize_context(rol, dorp.records, dorp.att)


# ── De prompt draagt de levende policy-tekst ────────────────────────────────────

@pytest.mark.smoke
def test_prompt_bevat_policy_body_letterlijk(dorp):
    prompt = cp.bouw_prompt(_ctx(dorp), soort="Email", brief="Welkomstmail")
    assert "We are the better option." in prompt
    assert "Smirk Check" in prompt
    assert "Welkomstmail" in prompt
    assert "Email" in prompt


def test_gewijzigde_policy_komt_gewijzigd_terug(dorp):
    pol = next(p for p in dorp.att.list("nooch__email", "policy") if p.title == "Tone of Voice")
    dorp.att.update(pol.id, body="Compleet andere tekst voor de stem.")
    prompt = cp.bouw_prompt(_ctx(dorp))
    assert "Compleet andere tekst voor de stem." in prompt
    assert "We are the better option." not in prompt


def test_gearchiveerde_policy_verdwijnt_uit_de_prompt(dorp):
    pol = next(p for p in dorp.att.list("nooch__email", "policy") if p.title == "Copy Check")
    dorp.att.archive(pol.id)
    prompt = cp.bouw_prompt(_ctx(dorp))
    assert "Smirk Check" not in prompt
    assert "POLICIES (1)" in prompt


def test_geerfde_policy_draagt_zijn_herkomst(dorp):
    dorp.att.add("nooch", "policy", title="Stance", body="Things are a mess.",
                 domain="Tone of voice", inherit=True)
    prompt = cp.bouw_prompt(_ctx(dorp))
    assert "Things are a mess." in prompt
    assert "via Nooch" in prompt


def test_rol_zonder_policies_zegt_dat_hardop(dorp):
    prompt = cp.bouw_prompt(_ctx(dorp, "nooch"))
    assert "POLICIES (0)" in prompt
    assert "no policies" in prompt


# ── De registers komen uit de policy, niet uit de code ─────────────────────────

@pytest.mark.smoke
def test_registers_uit_policy_gelezen(dorp):
    items = cp._policy_items(_ctx(dorp))
    regs = cp.registers_uit_policies([a["body"] for a in items])
    assert [n for n, _ in regs] == ["THINK", "LAUGH"]
    assert dict(regs)["LAUGH"] == "dry observation"


def test_register_lijst_volgt_de_policy_wijziging(dorp):
    pol = next(p for p in dorp.att.list("nooch__email", "policy") if p.title == "Tone of Voice")
    dorp.att.update(pol.id, body="**Register**\n\n* ANNOY: the reader gets annoyed\n")
    items = cp._policy_items(_ctx(dorp))
    assert [n for n, _ in cp.registers_uit_policies([a["body"] for a in items])] == ["ANNOY"]


def test_do_en_dont_bullets_zijn_geen_registers():
    body = ("**Do**\n\n* We grow shoes: because oil is weird\n\n"
            "**Register**\n\n* THINK: huh\n\nIn a series: nope.\n\n"
            "**Don't**\n\n* Stop wearing plastic: too aggressive\n")
    assert cp.registers_uit_policies([body]) == [("THINK", "huh")]


def test_geen_registerblok_faalt_zacht():
    assert cp.registers_uit_policies(["Geen kop, geen bullets."]) == []


# ── De pagina zelf ─────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_pagina_rendert_en_toont_de_prompt(dorp):
    html = cp.render_copy_prompt(dorp, rol="nooch__email", soort="Email", register="LAUGH",
                                 brief="Welkomstmail voor batch 5")
    assert "Copy prompt" in html
    assert "cp-prompt" in html
    assert "Welkomstmail voor batch 5" in html
    assert "dry observation" in html          # de uitleg bij het gekozen register
    assert "cl-filter on" in html             # de actieve keuze in de picker


def test_zonder_rol_verschijnt_de_kiezer(dorp):
    html = cp.render_copy_prompt(dorp)
    assert "Whose policies" in html
    assert "nooch__email" in html


def test_onbekende_rol_valt_terug_op_de_kiezer(dorp):
    assert "Whose policies" in cp.render_copy_prompt(dorp, rol="bestaat_niet")


def test_geen_inline_styles_in_de_view(dorp):
    html = cp.render_copy_prompt(dorp, rol="nooch__email")
    assert "style=" not in html.replace(cp._KOPIEER_JS, "")


def test_route_is_bereikbaar():
    """De route hangt in do_GET en de view is geimporteerd in cockpit2."""
    from nooch_village import cockpit2
    assert cockpit2.render_copy_prompt is cp.render_copy_prompt
    bron = open(cockpit2.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert '"/copy-prompt"' in bron


# ── Het OUTPUT-contract vraagt twee versies, niet één en niet drie ─────────────

def _output_blok(prompt: str) -> str:
    return prompt.split("=== OUTPUT ===", 1)[1]


@pytest.mark.smoke
def test_prompt_vraagt_twee_versies(dorp):
    prompt = cp.bouw_prompt(_ctx(dorp), soort="Email", register="ANNOY", brief="Welkomstmail")
    blok = _output_blok(prompt)
    assert "Write two versions" in blok
    assert "VERSION A" in blok
    assert "VERSION B" in blok
    assert "VERSION C" not in blok


def test_beide_versie_instructies_noemen_het_gekozen_register(dorp):
    """Zonder de registernaam in béide instructies weet het model niet waarvan A de grens
    opzoekt en waarvan B de tegenpool is."""
    blok = _output_blok(cp.bouw_prompt(_ctx(dorp), register="ANNOY"))
    assert blok.count("ANNOY") >= 2


def test_zonder_register_geen_kaal_gat_in_de_instructie(dorp):
    """Fail-soft: geen register gekozen mag geen zin opleveren die halverwege ophoudt."""
    blok = _output_blok(cp.bouw_prompt(_ctx(dorp)))
    assert "VERSION A" in blok
    assert " — , at the limit" not in blok
    assert "the policy's dominant register" in blok


def test_checktabel_verbiedt_verzonnen_checks(dorp):
    """Het model vulde de tabel eerder aan met checks die in geen policy staan."""
    assert "Do not invent checks the policies do not name." in _output_blok(
        cp.bouw_prompt(_ctx(dorp)))


def test_de_grens_verwijst_naar_de_calibratietekst_niet_naar_het_model(dorp):
    """'Tegen de grens' mag geen vrijbrief zijn: de policy bepaalt hoe ver, niet het model."""
    blok = _output_blok(cp.bouw_prompt(_ctx(dorp), register="LAUGH"))
    assert "calibration text named in the policies" in blok
    assert "not your own instinct" in blok
