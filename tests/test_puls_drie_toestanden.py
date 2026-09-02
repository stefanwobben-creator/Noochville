"""Een puls die niets voortbrengt, zegt WAAROM — per skill, met de reden.

DE LES DIE DIT AFVANGT (2 sep 2026): `_run_pulse_skills` had één kale `continue` voor zowel
'overgeslagen door zijn eigen ritme' als 'nooit gedraaid, geen grant'. Op het scherm werden dat
dezelfde nul. Twee onderzoekers verklaarden die nul anderhalf uur lang verkeerd — eerst als dode
LLM-ladder, daarna als stille drop — terwijl het gewoon een maandelijkse skill was die deze maand
al gemeten had. Een onwaarneembare nul verbergt niet alleen een bug, hij fabriceert verklaringen.
"""
from __future__ import annotations

import logging

import pytest


class _Skill:
    def __init__(self, uitslag):
        self.uitslag = uitslag


def _bewoner(monkeypatch, tmp_path, *, grants, uitslagen):
    from nooch_village.inhabitant import Inhabitant
    inh = object.__new__(Inhabitant)
    inh.id = "compliance"
    inh.log = logging.getLogger("test.puls")
    inh.capabilities = lambda: list(grants)
    inh._periodieke_skills = lambda: ["regulation_watch", "claims_site_scan", "verweesde_skill"]
    inh.use_skill = lambda naam, payload: uitslagen.get(naam)
    inh._notify_founder = lambda *a, **k: None

    class _Ctx:
        data_dir = str(tmp_path)
    inh.context = _Ctx()
    return inh


@pytest.fixture
def gaten(monkeypatch):
    """Vang de means-gaps op in plaats van ze naar de HumanInbox te schrijven."""
    gevangen = []
    import nooch_village.human_inbox as hi

    def _add(self, gap_key, description, *, role_id="", sensed_by=""):
        gevangen.append((gap_key, description, role_id))
        return "x"
    monkeypatch.setattr(hi.HumanInbox, "add_means_gap", _add)
    monkeypatch.setattr(hi.HumanInbox, "__init__", lambda self, path: None)
    return gevangen


def test_de_drie_toestanden_zijn_uit_elkaar_te_houden(caplog, tmp_path, monkeypatch, gaten):
    inh = _bewoner(monkeypatch, tmp_path,
                   grants=["regulation_watch", "claims_site_scan"],
                   uitslagen={"regulation_watch": {"ok": True, "skipped": True,
                                                   "reden": "deze maand al gemeten"},
                              "claims_site_scan": {"ok": True}})
    with caplog.at_level(logging.INFO):
        telling = inh._run_pulse_skills(None)

    assert telling == {"gedraaid": 1, "overgeslagen": 1, "geen_grant": 1, "gemeld": 0, "fout": 0}
    tekst = caplog.text
    assert "overgeslagen — deze maand al gemeten" in tekst          # 1: ritme, mét reden
    assert "gedraaid — niets gevonden" in tekst                     # 2: draaide, vond niets
    # 3 wordt hier alleen GETELD; het signaal hoort op dorpsniveau (zie onder).
    assert "1 niet van deze rol" in tekst


def test_de_rol_lus_meldt_NOOIT_een_capaciteitsgat(tmp_path, monkeypatch, gaten):
    """GEVONDEN IN DE DROGE RUN, VÓÓR APPLY. Eerst meldde de rol-lus per rol een capaciteitsgat als
    de rol de skill niet had. Op prod is dat 31 rollen × 2 pulse-skills = 62 meldingen per puls,
    voor de normaalste zaak van de wereld: de Copywriter hoort geen claims-scan te draaien. Dat is
    de 135-vastgelopen-projecten-fout opnieuw.

    'Ik heb deze skill niet' is rust en wordt alleen geteld. Het echte gat — niemand heeft hem —
    weet een rol niet over zichzelf; dat toetst het dorp."""
    inh = _bewoner(monkeypatch, tmp_path,
                   grants=["regulation_watch", "claims_site_scan"],
                   uitslagen={"regulation_watch": {"ok": True, "skipped": True, "reden": "r"},
                              "claims_site_scan": {"ok": True}})
    telling = inh._run_pulse_skills(None)
    assert telling["geen_grant"] == 1                       # geteld
    assert gaten == []                                      # en verder stil


def test_de_puls_sluit_af_met_een_telling(caplog, tmp_path, monkeypatch, gaten):
    """Zonder deze regel is 'geen notificaties vandaag' niet te onderscheiden van 'de puls draaide
    niet' — en dan verzint de lezer een verklaring."""
    inh = _bewoner(monkeypatch, tmp_path, grants=["claims_site_scan"],
                   uitslagen={"claims_site_scan": {"ok": True}})
    with caplog.at_level(logging.INFO):
        inh._run_pulse_skills(None)
    assert "pulsbalans compliance:" in caplog.text
    assert "1 gedraaid (0 gemeld)" in caplog.text
    assert "2 niet van deze rol" in caplog.text


def test_een_vondst_telt_apart_van_het_draaien(caplog, tmp_path, monkeypatch, gaten):
    inh = _bewoner(monkeypatch, tmp_path, grants=["claims_site_scan"],
                   uitslagen={"claims_site_scan": {"ok": True, "headsup": "📜 1 punt"}})
    with caplog.at_level(logging.INFO):
        telling = inh._run_pulse_skills(None)
    assert telling["gedraaid"] == 1 and telling["gemeld"] == 1
    assert "gedraaid — 📜 1 punt" in caplog.text


def test_een_niet_dict_uitslag_is_een_fout_geen_stilte(caplog, tmp_path, monkeypatch, gaten):
    """Stond eerst in dezelfde kale `continue` als 'overgeslagen'. Een skill die None teruggeeft is
    kapot, niet rustig."""
    inh = _bewoner(monkeypatch, tmp_path, grants=["claims_site_scan"],
                   uitslagen={"claims_site_scan": None})
    with caplog.at_level(logging.INFO):
        telling = inh._run_pulse_skills(None)
    assert telling["fout"] == 1
    assert "gaf geen uitslag terug" in caplog.text


# ── de derde toestand, waar hij wél thuishoort: op dorpsniveau ────────────────────────────────

class _Def:
    def __init__(self, skills):
        self.skills = skills


class _Rec:
    def __init__(self, skills, *, slaapt=False, archived=False):
        self.definition = _Def(skills)
        self.slaapt = slaapt
        self.archived = archived


def _dorp(monkeypatch, tmp_path, records, *, pulse_skills="claims_site_scan,regulation_watch"):
    from nooch_village.village import Village
    v = object.__new__(Village)

    class _Recs:
        def all(self):
            return records
    v.records = _Recs()

    class _Ctx:
        settings = {"pulse_skills": pulse_skills}
        data_dir = str(tmp_path)
    v.context = _Ctx()

    gevangen = []

    class _HI:
        def add_means_gap(self, gap_key, description, *, role_id="", sensed_by=""):
            gevangen.append((gap_key, description))
            return "x"
    v.human_inbox = _HI()
    return v, gevangen


def test_alles_belegd_is_geen_gat(tmp_path, monkeypatch, caplog):
    v, gevangen = _dorp(monkeypatch, tmp_path,
                        [_Rec(["claims_site_scan", "regulation_watch"]), _Rec(["projectverzoek"])])
    with caplog.at_level(logging.INFO):
        assert v._meld_verweesde_pulse_skills() == []
    assert gevangen == []
    assert "elke skill heeft minstens \u00e9\u00e9n rol" in caplog.text


def test_een_skill_die_niemand_heeft_is_wel_een_gat(tmp_path, monkeypatch):
    v, gevangen = _dorp(monkeypatch, tmp_path, [_Rec(["claims_site_scan"])])
    assert v._meld_verweesde_pulse_skills() == ["regulation_watch"]
    assert len(gevangen) == 1
    assert gevangen[0][0] == "pulse_skill:regulation_watch"
    assert "geen enkele levende rol" in gevangen[0][1]


def test_een_slapende_rol_draagt_geen_capaciteit(tmp_path, monkeypatch):
    """Een slapende rol staat nog in de records met al zijn skills. Hem meetellen zou een echt gat
    verbergen: de skill lijkt belegd terwijl er niemand draait."""
    v, gevangen = _dorp(monkeypatch, tmp_path,
                        [_Rec(["claims_site_scan"]),
                         _Rec(["regulation_watch"], slaapt=True)])
    assert v._meld_verweesde_pulse_skills() == ["regulation_watch"]
