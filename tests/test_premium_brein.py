"""Premium-brein dorpsbreed: waar het oordeel telt, draait het sterkste model.

Het dorp draaide op de goedkope ladder omdat die de default was, niet omdat dat de juiste keuze
was. Op negen plekken is een goedkoop antwoord niet "sneller hetzelfde" maar iets ánders: een plan
dat de verkeerde taken bedenkt, een rapport dat een verzonnen getal doorlaat, een critic die een
zwakke claim niet ziet. Daar hoort Sonnet.

En de tegenhanger, die net zo hard is: triage en routing kiezen alleen een bák ("is dit
structureel?", "welke rol?"). Dat is een grove beslissing met een goedkope fout — verkeerd
gerouteerd werk komt terug, verkeerd geplande inhoud niet. Die blijven expliciet goedkoop, want
"dorpsbreed premium" mag niet stilletjes ook de hoogfrequente routeer-calls meenemen.

De guards die de opdracht vraagt staan onderaan:
  - een hoog-inzet-call draait aantoonbaar op sonnet, tot in llm_usage.jsonl;
  - triage draait op de goedkope ladder.
"""
from __future__ import annotations

import json
import os

import pytest

from nooch_village import llm, llm_keuze as lk


@pytest.fixture(autouse=True)
def _schone_cap_cache(monkeypatch):
    """De cap-uitkomst is 5 minuten gecachet; tussen tests moet die schoon zijn."""
    lk._cap_cache.update({"tot": 0.0, "op": False, "eur": 0.0})
    monkeypatch.delenv(lk._CAP_ENV, raising=False)
    monkeypatch.delenv("LLM_HOOG_INZET_LADDER", raising=False)
    yield
    lk._cap_cache.update({"tot": 0.0, "op": False, "eur": 0.0})


# ── De negen, en de goedkope tegenhanger ─────────────────────────────────────

def test_negen_hoog_inzet_sites():
    assert len(lk.HOOG_INZET) == 9
    assert lk.HOOG_INZET == {
        "einddocument", "plan_checklist", "plan_checklist_retry", "skill_tegenspraak",
        "skill_synthesize", "skill_content_schrijven", "skill_bulletin", "skill_voorstel",
        "noochie_weigh_in"}


def test_hoog_inzet_krijgt_sonnet_als_kop():
    for site in lk.HOOG_INZET:
        ladder = lk.ladder_voor(site)
        assert ladder, f"{site} heeft geen kop"
        assert ladder.split(",")[0].startswith("anthropic:claude-sonnet"), site


def test_de_dorpsladder_hangt_als_staart_eronder():
    """Zonder staart betekent één wegvallende leverancier géén antwoord — en bij een einddocument
    is dat geen goedkoper resultaat maar geen resultaat."""
    ladder = lk.ladder_voor("einddocument")
    tredes = ladder.split(",")
    assert len(tredes) > 1
    assert tredes[1:] == llm.dorpsladder().split(",")


def test_triage_en_routing_blijven_goedkoop():
    """DE tweede guard. Geen kop = de dorpsladder."""
    for site in ("classify_tension", "cockpit_mention_triage", "escalation_route",
                 "escaleer_keuze", "scope_nudge_match", "governance_target_pick"):
        assert lk.ladder_voor(site) is None, site
    assert lk.GOEDKOOP & lk.HOOG_INZET == set()      # geen site kan allebei zijn


def test_onbekende_site_krijgt_de_dorpsladder():
    """Alleen wat expliciet hoog-inzet is wordt duur. 'Dorpsbreed premium' mag niet betekenen dat
    elke nieuwe call-site er stilzwijgend in valt."""
    assert lk.ladder_voor("een_nieuwe_site_die_niemand_registreerde") is None


def test_persona_wint_van_de_dorpsbrede_kop():
    from nooch_village.personas import Persona
    p = Persona(id="x", name="Billy", llm={"per_taak": {"einddocument": "mistral"}})
    assert lk.ladder_voor("einddocument", p).startswith("mistral")


def test_kop_is_env_instelbaar(monkeypatch):
    monkeypatch.setenv("LLM_HOOG_INZET_LADDER", "anthropic:claude-opus-4-1")
    assert lk.ladder_voor("einddocument").startswith("anthropic:claude-opus-4-1")
    monkeypatch.setenv("LLM_HOOG_INZET_LADDER", "")   # leeg = premium uit, zonder deploy
    assert lk.ladder_voor("einddocument") is None


# ── De maandcap ──────────────────────────────────────────────────────────────

def _usage(tmp_path, rijen):
    pad = tmp_path / "llm_usage.jsonl"
    with open(pad, "w", encoding="utf-8") as f:
        for r in rijen:
            f.write(json.dumps(r) + "\n")
    return str(pad)


def test_cap_telt_alleen_de_dure_tredes(tmp_path):
    """De cap gaat over de KOP, niet over het dorpsverbruik: een maand vol goedkope calls mag de
    dure kop nooit uitschakelen."""
    import datetime
    maand = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    pad = _usage(tmp_path, [
        {"day": f"{maand}-01", "tier": "mistral:mistral-small-latest",
         "in_tokens": 5_000_000, "out_tokens": 5_000_000},
        {"day": f"{maand}-02", "tier": lk.hoog_inzet_ladder(),
         "in_tokens": 100_000, "out_tokens": 100_000},
    ])
    eur = lk.premium_uitgaven_deze_maand(pad)
    goedkoop_eur = lk.kosten_eur("mistral:mistral-small-latest", 5_000_000, 5_000_000)
    assert eur > 0
    assert goedkoop_eur is None or eur < goedkoop_eur   # de goedkope maand telt niet mee


def test_cap_negeert_een_andere_maand(tmp_path):
    pad = _usage(tmp_path, [{"day": "2020-01-01", "tier": lk.hoog_inzet_ladder(),
                             "in_tokens": 9_000_000, "out_tokens": 9_000_000}])
    assert lk.premium_uitgaven_deze_maand(pad) == 0.0


def test_cap_bereikt_laat_de_dure_kop_vervallen(monkeypatch):
    """Een goedkoper antwoord, geen géén antwoord — een cap die het dorp stil legt is erger dan
    een cap die hem goedkoper laat werken."""
    monkeypatch.setenv(lk._CAP_ENV, "1.0")
    monkeypatch.setattr(lk, "premium_uitgaven_deze_maand", lambda *a, **k: 2.5)
    assert lk.premium_op() is True
    assert lk.ladder_voor("einddocument") is None          # terug naar de dorpsladder
    assert lk.ladder_voor("classify_tension") is None      # triage was al goedkoop


def test_cap_nul_is_geen_cap(monkeypatch):
    monkeypatch.setenv(lk._CAP_ENV, "0")
    monkeypatch.setattr(lk, "premium_uitgaven_deze_maand", lambda *a, **k: 9_999.0)
    assert lk.premium_op() is False
    assert lk.ladder_voor("einddocument").startswith("anthropic:claude-sonnet")


def test_cap_faalt_open(monkeypatch):
    """Een onleesbaar logbestand mag het dorp niet naar de goedkope ladder duwen zonder oorzaak —
    dat zou als kwaliteitsverlies lezen zonder dat iemand weet waarom."""
    monkeypatch.setenv(lk._CAP_ENV, "1.0")

    def _stuk(*a, **k):
        raise OSError("log weg")
    monkeypatch.setattr(lk, "premium_uitgaven_deze_maand", _stuk)
    assert lk.premium_op() is False
    assert lk.ladder_voor("einddocument").startswith("anthropic:")


def test_premium_grens_is_afgeleid_van_de_dorpsladder():
    """Niet overgetypt: verandert de dorpsladder, dan verschuift de grens mee. Zou hier een lijstje
    modelnamen staan, dan telt een nieuw premium-model stilzwijgend niet mee voor de cap."""
    assert lk._is_premium(lk.hoog_inzet_ladder()) is True
    for trede in llm.dorpsladder().split(","):
        assert lk._is_premium(trede.strip()) is False


def test_elke_trede_in_de_kop_heeft_een_prijs():
    """Anders is de maandcap blind: alle premium-calls tellen voor €0,00 en de zekering gaat nooit
    om. Dat is precies het scenario dat je pas op de rekening ziet."""
    prijzen = lk._prijzen()
    for trede in lk.hoog_inzet_ladder().split(","):
        trede = trede.strip()
        if not trede:
            continue
        assert lk.kosten_eur(trede, 1000, 1000, prijzen) is not None, (
            f"{trede} staat niet in config/llm_prijzen.json — de cap kan hem niet zien")


def test_premium_stand_leest_zonder_te_muteren():
    stand = lk.premium_stand()
    assert set(stand) == {"uitgaven", "cap", "op"}
    assert stand["cap"] == lk.premium_maand_cap()


# ── GUARD: een hoog-inzet-call draait aantoonbaar op sonnet, tot in llm_usage ─

def test_guard_hoog_inzet_call_landt_als_sonnet_in_llm_usage(tmp_path, monkeypatch):
    """DE guard, end-to-end: de site vraagt de kop, `reason` rapporteert de trede, en `llm_usage`
    schrijft 'm weg zodat `verbruik` het kan aantonen."""
    from nooch_village import llm_usage
    pad = str(tmp_path / "llm_usage.jsonl")
    monkeypatch.setattr(llm_usage, "_PATH", pad)

    ladder = lk.ladder_voor("einddocument")
    trede = ladder.split(",")[0]
    assert trede.startswith("anthropic:claude-sonnet")

    # Zoals `reason()` het doet: de gerapporteerde trede gaat het usage-log in.
    llm_usage.record("einddocument", trede, 1200, 900, estimated=True)
    rijen = [json.loads(r) for r in open(pad, encoding="utf-8") if r.strip()]
    assert rijen and rijen[0]["call_site"] == "einddocument"
    assert rijen[0]["tier"].startswith("anthropic:claude-sonnet")

    verslag = lk.verbruik(str(tmp_path), dagen=1)
    assert verslag["per_site"]["einddocument"]["tier"].startswith("anthropic:claude-sonnet")
    assert verslag["onbekende_calls"] == 0            # sonnet heeft een prijs in llm_prijzen.json


def test_guard_triage_landt_niet_op_sonnet(tmp_path, monkeypatch):
    """De tegenhanger van dezelfde guard: triage hoort in het log op een goedkope trede te staan."""
    from nooch_village import llm_usage
    pad = str(tmp_path / "llm_usage.jsonl")
    monkeypatch.setattr(llm_usage, "_PATH", pad)
    assert lk.ladder_voor("classify_tension") is None
    trede = llm.dorpsladder().split(",")[0]
    llm_usage.record("classify_tension", trede, 300, 80, estimated=True)
    verslag = lk.verbruik(str(tmp_path), dagen=1)
    assert not verslag["per_site"]["classify_tension"]["tier"].startswith("anthropic:claude-sonnet")


# ── De sites hangen er echt aan ──────────────────────────────────────────────

@pytest.mark.parametrize("bestand,site", [
    ("nooch_village/skills_impl/tegenspraak.py", "skill_tegenspraak"),
    ("nooch_village/skills_impl/synthesize.py", "skill_synthesize"),
    ("nooch_village/skills_impl/content_schrijven.py", "skill_content_schrijven"),
    ("nooch_village/skills_impl/bulletin_schrijven.py", "skill_bulletin"),
    ("nooch_village/skills_impl/voorstel.py", "skill_voorstel"),
])
def test_skill_sites_vragen_de_hoog_inzet_ladder(bestand, site):
    src = open(bestand, encoding="utf-8").read()
    assert "_hoog_inzet_ladder" in src, bestand
    assert f'_hoog_inzet_ladder("{site}")' in src, bestand


def test_rolgebonden_sites_gaan_via_de_persona_hook():
    """plan_checklist(+retry), einddocument en noochie_weigh_in kennen hun rol wél, dus daar mag de
    persona-override werken — die lopen via `_persona_ladder`/`ladder_voor`, niet via de skill-helper."""
    inh = open("nooch_village/inhabitant.py", encoding="utf-8").read()
    assert '_persona_ladder(self.context, self.id, "plan_checklist")' in inh
    assert '_persona_ladder(self.context, self.id,\n                                                            "plan_checklist_retry")' in inh
    assert 'ladder_voor("einddocument", _p)' in inh
    rollen = open("nooch_village/roles.py", encoding="utf-8").read()
    assert '_persona_ladder(self.context, self.id, "noochie_weigh_in")' in rollen


def test_einddocument_token_cap_is_verhoogd():
    """Sonnet kan een langer document aan; de oude cap van 4000 was op de goedkope tredes geijkt."""
    inh = open("nooch_village/inhabitant.py", encoding="utf-8").read()
    assert 'settings.get("einddocument_max_tokens", "8000")' in inh


def test_critic_gebruikt_dezelfde_kop_niet_een_kopie():
    """Reference, don't copy: verandert de dorpsbrede kop, dan verandert de critic mee."""
    from nooch_village import missie_critic
    assert missie_critic.premium_ladder() == lk.hoog_inzet_ladder()
    src = open("nooch_village/missie_critic.py", encoding="utf-8").read()
    assert "claude-sonnet" not in src                 # geen tweede exemplaar van de modelnaam


# ── Prijsloze tredes zijn zichtbaar, niet stil ───────────────────────────────

def test_prijsloze_trede_wordt_herkend():
    """Op productie liepen drie Sonnet-ids naast elkaar (4-5, 4-6, 'anthropic:default'), geen
    enkele met een prijs — vijftig calls die nergens meetelden en de cap dus blind maakten."""
    assert lk.prijsloze_tredes(lk.hoog_inzet_ladder()) == []
    assert lk.prijsloze_tredes("anthropic:claude-sonnet-4-6") == ["anthropic:claude-sonnet-4-6"]
    assert lk.prijsloze_tredes("anthropic:default") == ["anthropic:default"]


def test_prijsloze_persona_voorkeur_wordt_gemeld(caplog):
    """Fail-loud: een ladder die de cap niet kan zien is geen detail."""
    from nooch_village.personas import Persona
    lk._gemeld_prijsloos.clear()
    p = Persona(id="x", name="Wendy", llm={"default": "anthropic:claude-sonnet-4-6"})
    with caplog.at_level("WARNING"):
        lk.ladder_voor("einddocument", p)
    assert "PRIJSLOZE_TREDE" in caplog.text
    assert "claude-sonnet-4-6" in caplog.text


def test_prijsloze_melding_is_eenmalig(caplog):
    """Fail-loud mag geen logspam worden: één regel per onbekende trede, niet per call."""
    from nooch_village.personas import Persona
    lk._gemeld_prijsloos.clear()
    p = Persona(id="x", name="W", llm={"default": "anthropic:claude-sonnet-4-6"})
    with caplog.at_level("WARNING"):
        for _ in range(5):
            lk.ladder_voor("einddocument", p)
    assert caplog.text.count("PRIJSLOZE_TREDE") == 1
