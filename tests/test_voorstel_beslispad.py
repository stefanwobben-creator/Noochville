"""Het beslispad van een `voorstel`-item: zien wat je tekent, en tekenen wat er gebeurt.

Twee bugs die tijdens het tekenen van de lexicon-annotatie boven kwamen, allebei stil:

  `inbox show` printte alleen de kop. Het hele voorstel — wat, waarom, bewijs, de schrijfactie —
  zat in `context.voorstel` en had geen tak in `_print_item_full`. De founder tekende op een titel.

  `inbox approve` viel in het vangnet: item dicht, melding "goedgekeurd", geen schrijfactie. Het
  record zei aangenomen terwijl de bron ongewijzigd was tot iemand het zich herinnerde. Dezelfde
  klasse als luna, `library` vs `bibliotheek` en `required_payload`: declaratie zonder handhaving,
  met een stille fallback ertussen.

Deze tests bevriezen beide fixes, plus het vangnet dat de klasse afsluit in plaats van alleen dit
ene geval: een type ZONDER eigen tak dumpt zijn context, zodat blind tekenen niet terug kan komen.
"""
from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout

import pytest

from nooch_village.human_inbox import HumanInbox
from nooch_village.lexicon import Lexicon
from nooch_village import voorstel_mutatie as vm
from nooch_village.inbox.__main__ import _print_item_full


# ── De Lexicon-primitief ────────────────────────────────────────────────────

def _lex(tmp_path):
    lex = Lexicon(str(tmp_path / "lexicon.json"))
    lex.add_concept("conscious_consumer", {"nl": "bewuste consument", "en": "conscious consumer"},
                    status="approved", rationale="Missie-aligned SEO-term.",
                    evidence={"bron": "seed"}, by="Librarian")
    return lex


def test_annoteer_laat_alles_behalve_de_rationale_staan(tmp_path):
    """De reden dat deze methode bestaat: `add_concept` overschrijft het concept volledig, dus
    één vergeten veld wist stilletjes wat een ander vastlegde."""
    lex = _lex(tmp_path)
    voor = dict(lex.concept("conscious_consumer"))
    assert lex.annoteer("conscious_consumer", "SCOPE: SEO-doelwit, nooit in klantcontent.")
    na = lex.concept("conscious_consumer")
    assert na["words"] == voor["words"]
    assert na["status"] == "approved" and na["evidence"] == voor["evidence"]
    assert na["by"] == voor["by"]
    assert na["rationale"].startswith("Missie-aligned SEO-term.")
    assert "SCOPE:" in na["rationale"]


def test_annoteer_is_idempotent_en_meldt_dat(tmp_path):
    lex = _lex(tmp_path)
    regel = "SCOPE: SEO-doelwit, nooit in klantcontent."
    assert lex.annoteer("conscious_consumer", regel) is True
    assert lex.annoteer("conscious_consumer", regel) is False   # stond er al → niets geschreven
    assert lex.concept("conscious_consumer")["rationale"].count("SCOPE:") == 1


def test_annoteer_op_onbekend_concept_schrijft_niets(tmp_path):
    lex = _lex(tmp_path)
    assert lex.annoteer("bestaat_niet", "iets") is False
    assert "bestaat_niet" not in lex.all()


# ── De uitvoerder ───────────────────────────────────────────────────────────

def test_voer_uit_schrijft_de_annotatie(tmp_path):
    _lex(tmp_path)
    ok, bericht = vm.voer_uit({"soort": "lexicon_rationale", "concept_id": "conscious_consumer",
                               "regel": "SCOPE: nooit in klantcontent."}, str(tmp_path))
    assert ok and "geannoteerd" in bericht
    assert "SCOPE:" in Lexicon(str(tmp_path / "lexicon.json")).concept("conscious_consumer")["rationale"]


@pytest.mark.parametrize("mutatie,fragment", [
    (None, "geen mutatie"),
    ({"soort": "onbekend"}, "onbekende mutatie-soort"),
    ({"soort": "lexicon_rationale", "concept_id": "x"}, "mist: regel"),
    ({"soort": "lexicon_rationale", "concept_id": "weg", "regel": "r"}, "bestaat niet"),
])
def test_voer_uit_faalt_closed_en_zegt_waarom(tmp_path, mutatie, fragment):
    """Elke faalweg geeft False. De aanroeper mag het item dan niet sluiten — dat is precies het
    verschil tussen 'aangenomen' en 'aangenomen maar er is niets gebeurd'."""
    _lex(tmp_path)
    ok, bericht = vm.voer_uit(mutatie, str(tmp_path))
    assert ok is False and fragment in bericht


# ── show: zien wat je tekent ────────────────────────────────────────────────

def _toon(item) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        _print_item_full(item)
    return buf.getvalue()


def _voorstel_item(tmp_path, **kw):
    ib = HumanInbox(str(tmp_path / "human_inbox.json"))
    iid = ib.add_voorstel("lexicon:conscious_consumer:scope", "WAT\nAnnoteer het concept.\n\n"
                          "WAAROM\nApproved in het lexicon, never-write in COPYCHECK-001.",
                          by="librarian-domein", origin="COPYCHECK-001 v5", **kw)
    return ib, ib.get(iid)


def test_show_print_het_hele_voorstel(tmp_path):
    """De bug: alleen kop. De payload zat in context.voorstel en bleef onzichtbaar."""
    _, item = _voorstel_item(tmp_path)
    uit = _toon(item)
    assert "Annoteer het concept." in uit
    assert "never-write in COPYCHECK-001" in uit
    assert "librarian-domein" in uit and "COPYCHECK-001 v5" in uit


def test_show_zegt_vooraf_of_approve_iets_uitvoert(tmp_path):
    """Vóór het tekenen moet zichtbaar zijn of er een schrijfactie volgt of niet."""
    _, zonder = _voorstel_item(tmp_path)
    assert "er wordt niets geschreven" in _toon(zonder)

    _, met = _voorstel_item(tmp_path / "b", mutatie={
        "soort": "lexicon_rationale", "concept_id": "conscious_consumer", "regel": "SCOPE: x"})
    uit = _toon(met)
    assert "conscious_consumer" in uit and "rationale aanvullen" in uit


def test_onbekend_type_dumpt_zijn_context_in_plaats_van_niets(tmp_path):
    """Het vangnet dat de KLASSE afsluit: een type zonder eigen tak toont zijn context, zodat er
    nooit meer op een kale titel getekend wordt."""
    item = {"id": "x", "type": "iets_nieuws", "subject": "s", "status": "pending",
            "created_at": 0, "context": {"kern": "dit moet zichtbaar zijn"}}
    assert "dit moet zichtbaar zijn" in _toon(item)


# ── approve: tekenen wat er gebeurt ─────────────────────────────────────────

def _cli(monkeypatch, tmp_path, argv):
    """Draai de CLI met data_dir op tmp_path."""
    from nooch_village.inbox import __main__ as m
    monkeypatch.setattr(m, "_data_dir", lambda: str(tmp_path))
    buf = io.StringIO()
    code = 0
    with redirect_stdout(buf):
        try:
            m.main(argv)
        except SystemExit as e:
            code = e.code or 0
    return code, buf.getvalue()


def test_approve_met_mutatie_voert_hem_echt_uit(monkeypatch, tmp_path):
    _lex(tmp_path)
    ib, item = _voorstel_item(tmp_path, mutatie={
        "soort": "lexicon_rationale", "concept_id": "conscious_consumer",
        "regel": "SCOPE: SEO-doelwit, nooit in klantcontent."})
    code, uit = _cli(monkeypatch, tmp_path, ["approve", item["id"], "akkoord"])
    assert code == 0 and "UITGEVOERD" in uit
    # De bron is echt gewijzigd, niet alleen het item.
    lex = Lexicon(str(tmp_path / "lexicon.json"))
    assert "SCOPE:" in lex.concept("conscious_consumer")["rationale"]
    assert HumanInbox(str(tmp_path / "human_inbox.json")).get(item["id"])["status"] == "approved"


def test_approve_zonder_mutatie_meldt_dat_er_niets_is_uitgevoerd(monkeypatch, tmp_path):
    """De kale succesmelding was de bug. Vastleggen mag, doen-alsof niet."""
    _lex(tmp_path)
    ib, item = _voorstel_item(tmp_path)
    code, uit = _cli(monkeypatch, tmp_path, ["approve", item["id"], "akkoord"])
    assert code == 0
    assert "NIET UITGEVOERD" in uit and "handmatige stap" in uit
    assert HumanInbox(str(tmp_path / "human_inbox.json")).get(item["id"])["status"] == "approved"


def test_mislukte_uitvoering_laat_het_item_pending(monkeypatch, tmp_path):
    """Anders komt 'approved' in de boeken terwijl de bron ongewijzigd is — exact de toestand
    waar deze hele fix over gaat."""
    _lex(tmp_path)
    ib, item = _voorstel_item(tmp_path, mutatie={
        "soort": "lexicon_rationale", "concept_id": "bestaat_niet", "regel": "x"})
    code, uit = _cli(monkeypatch, tmp_path, ["approve", item["id"], "akkoord"])
    assert code == 1 and "Uitvoering mislukt" in uit and "blijft pending" in uit
    assert HumanInbox(str(tmp_path / "human_inbox.json")).get(item["id"])["status"] == "pending"


def test_geen_enkel_approve_pad_meldt_stil_succes():
    """Guard op de klasse: elke tak in approve die een item sluit zonder schrijfactie moet dat
    zeggen. Zonder deze guard sluipt de kale succesmelding bij een volgend type terug."""
    src = open("nooch_village/inbox/__main__.py", encoding="utf-8").read()
    tak = src.split("elif cmd == \"approve\"", 1)[1].split("elif cmd ==", 1)[0]
    vangnet = tak.split("        else:", 1)[1]
    assert "niets uitgevoerd" in vangnet.lower(), (
        "de vangnet-tak van approve sluit een item zonder te melden dat er niets is uitgevoerd")


# ── Een domein toekennen loopt langs de echte governance-poort ──────────────

def test_rol_domein_gaat_via_g0_g4_en_niet_via_een_record_edit(monkeypatch):
    """Een domein toewijzen is een structuurwijziging. De botsingscheck van G1 hoort erbij: houdt
    een ander die al, dan moet dit struikelen in plaats van stilletjes een tweede eigenaar maken."""
    gezien = {}

    def _nep(voorstel):
        gezien["kind"] = voorstel.change.kind.value
        gezien["rol"] = voorstel.change.role_id
        gezien["domeinen"] = list(voorstel.change.add_domains)
        return {"status": "aangenomen"}

    import nooch_village.role_proposals as rp
    monkeypatch.setattr(rp, "_submit_proposal_sync", _nep)
    ok, bericht = vm.voer_uit({"soort": "rol_domein", "rol_id": "harry_hemp",
                               "domeinen": ["onderzoeksmethode"], "tension": "t",
                               "trigger_example": "e", "rationale": "r"}, "/tmp")
    assert ok and "aangenomen" in bericht
    assert gezien == {"kind": "amend_role", "rol": "harry_hemp",
                      "domeinen": ["onderzoeksmethode"]}


def test_een_geweigerd_governance_voorstel_sluit_het_item_niet(monkeypatch):
    """De poort heeft iets te zeggen (bijvoorbeeld een domein-botsing) en dat hoort zichtbaar."""
    import nooch_village.role_proposals as rp
    monkeypatch.setattr(rp, "_submit_proposal_sync",
                        lambda v: {"status": "geëscaleerd", "gate": "G1",
                                   "reason": "domein botst met librarian"})
    ok, bericht = vm.voer_uit({"soort": "rol_domein", "rol_id": "x", "domeinen": ["bibliotheek"],
                               "tension": "t", "trigger_example": "e", "rationale": "r"}, "/tmp")
    assert ok is False and "G1" in bericht and "botst" in bericht


def test_de_beschrijving_zegt_dat_het_langs_governance_gaat():
    tekst = vm.beschrijf({"soort": "rol_domein", "rol_id": "harry_hemp",
                          "domeinen": ["onderzoeksmethode"]})
    assert "amend_role" in tekst and "G0-G4" in tekst
