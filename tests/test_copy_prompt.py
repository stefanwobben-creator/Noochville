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
    def __init__(self, records, att, dd=""):
        self.records = records
        self.att = att
        self.dd = str(dd)
        # Zoals de echte _Stores: de compositie-config hoort erbij. De view bouwt hem bewust NIET
        # zelf — zie de opmerking in render_copy_prompt.
        from nooch_village.copy_stack import StackConfig
        self.copy_stack = StackConfig(os.path.join(self.dd or ".", "copy_stack.json"))


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
            body="We are the better option.\n\n**Voice**\n\nOne dominant voice.\n\n"
                 "* THINK: never thought about shoes like that\n"
                 "* LAUGH: dry observation\n\nIn a series: no two in a row.\n",
            domain="Tone of voice")
    att.add("nooch__email", "policy", title="Copy Check",
            body="**Smirk Check.** Does it raise an eyebrow?", domain="Tone of voice")
    return _NepStores(records, att, tmp_path)


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


# ── De pagina zelf ─────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_pagina_rendert_en_toont_de_prompt(dorp):
    html = cp.render_copy_prompt(dorp, rol="nooch__email", soort="email",
                                 brief="Welkomstmail voor batch 5")
    assert "Copy prompt" in html
    assert "cp-prompt" in html
    assert "Welkomstmail voor batch 5" in html
    assert "Stefan and Lotte" in html         # de uitleg bij de gekozen stem
    assert "cl-filter on" in html             # de actieve keuze in de picker


def test_zonder_rol_verschijnt_de_kiezer(dorp):
    """Niet meer "wiens policies draagt de prompt": de stack is samengesteld uit eigen bezit,
    erfenis en bewuste inclusies, dus die vraag heeft geen enkelvoudig antwoord meer."""
    html = cp.render_copy_prompt(dorp)
    assert "Who are you writing as?" in html
    assert "nooch__email" in html


def test_onbekende_rol_valt_terug_op_de_kiezer(dorp):
    assert "Who are you writing as?" in cp.render_copy_prompt(dorp, rol="bestaat_niet")


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
    prompt = cp.bouw_prompt(_ctx(dorp), soort="email", brief="Welkomstmail")
    blok = _output_blok(prompt)
    assert "Write two versions" in blok
    assert "VERSION A" in blok
    assert "VERSION B" in blok
    assert "VERSION C" not in blok


def test_beide_versie_instructies_hangen_aan_dezelfde_stem(dorp):
    """A en B moeten dezelfde stem delen, anders vergelijk je twee teksten die niets gemeen hebben.
    Dit hing eerst aan het register; dat is vervangen door doel × doelgroep × stem."""
    blok = _output_blok(cp.bouw_prompt(_ctx(dorp), soort="email"))
    assert "Stefan and Lotte" in blok                  # de stem staat in VERSION A
    assert "Same voice, same goal" in blok             # en B deelt hem expliciet


def test_zonder_stem_geen_kaal_gat_in_de_instructie(dorp):
    """Fail-soft: geen formaat gekozen mag geen zin opleveren die halverwege ophoudt."""
    blok = _output_blok(cp.bouw_prompt(_ctx(dorp)))
    assert "VERSION A —" in blok
    assert "the voice the policies describe" in blok


def test_de_grens_verwijst_naar_de_calibratietekst_niet_naar_het_model(dorp):
    """'Tegen de grens' mag geen vrijbrief zijn: de policy bepaalt hoe ver, niet het model."""
    blok = _output_blok(cp.bouw_prompt(_ctx(dorp), soort="email"))
    assert "calibration text named in the policies" in blok
    assert "not your own instinct" in blok
