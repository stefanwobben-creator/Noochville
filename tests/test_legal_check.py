"""De legal-bron van de weekmemo, en de bedrading aan de dagcadans.

Twee dingen die in dezelfde beurt zijn gebouwd en om dezelfde reden bij elkaar horen: de radar werd
een swipefile die niemand dagelijks leest, en voor één van de vier feeds is dat niet goed genoeg.
Een wetswijziging over duurzaamheidsclaims is geen trend maar een deadline.

DIT BESTAND TOETSTE TOT 20 SEPTEMBER 2026 `check()`: de dagelijkse ronde die per vers signaal één
item in de human inbox zette. Die is opgeheven — niet omdat hij fout was, maar omdat hij DUBBEL
was geworden naast de weekmemo. Dezelfde bron, dezelfde mens, twee uitgangen; dat is de vorm
waarin twee beelden uit elkaar gaan lopen zonder dat iets zich meldt.

Wat er van die tests overbleef staat hieronder op `verzamel()`, want dáár leven de garanties nu:
alleen de Legal-feed, het venster als argument van de AANROEP, de cap, en fail-closed (geen model,
een leeg antwoord of een fout = geen signaal; liever een gemiste melding dan een verzonnen
juridisch alarm). Wat verviel is wat alleen over het inbox-item ging: de dedup op de artikel-link.
Die rol vervult nu het boek van de memo (`weekmemo.voorgelegd`), en dat is precies de winst —
één plek die bijhoudt wat al is voorgelegd, voor alle vijf de bronnen.
"""
from __future__ import annotations

import time

from nooch_village import legal_signaal as ls
from nooch_village.radar_store import RadarStore

NU = 1_800_000_000.0


def _iso(ts: float) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(ts, datetime.UTC).isoformat().replace("+00:00", "Z")


def _radar(tmp_path, signalen):
    """De tijd zetten via `published_at`, niet via `at`: dat is het veld dat de ingest zelf
    meegeeft en dat `tijdstip()` als eerste leest. Rechtstreeks in `_data` prikken werkt niet —
    de JsonStore herlaadt onder het slot, en dan is de prik weg."""
    r = RadarStore(str(tmp_path / "radar.json"))
    for s in signalen:
        r.add(role="r", feed=s.get("feed", ls.FEED), kind="signaal",
              content=s["content"], rationale="", source=s.get("source", "eu-nieuws.eu"),
              link=s["link"], published_at=s.get("published_at", _iso(s.get("at", NU))))
    return r


# ── 4. de puls-bedrading ─────────────────────────────────────────────────────
def test_beide_taken_hangen_aan_dag_begint_en_in_de_juiste_volgorde():
    """Eerst ophalen, dan beoordelen — anders ziet de memo pas volgende week wat vanochtend kwam.

    De tweede helft was `_veilig_legal_check`; sinds 20 september is dat de weekmemo, die dezelfde
    feed als een van zijn vijf bronnen leest."""
    bron = open("nooch_village/village.py", encoding="utf-8").read()
    i = bron.index('self.bus.subscribe("dag_begint", lambda e: self._veilig_radar_ingest())')
    j = bron.index('self.bus.subscribe("dag_begint", lambda e: self._veilig_weekmemo())')
    assert i < j


def test_de_dagelijkse_legal_uitgang_is_echt_weg():
    """DE GUARD BIJ HET BESLUIT. Eén bron, één uitgang. Komt `check` ooit terug naast de memo, dan
    krijgt dezelfde mens hetzelfde signaal weer twee keer — en dan is de vraag welke van de twee
    hij gelooft als ze verschillen."""
    assert not hasattr(ls, "check")
    from nooch_village.human_inbox import HumanInbox
    assert not hasattr(HumanInbox, "add_legal_signaal")
    # DE CODE, NIET DE UITLEG: het comment in `village.py` noemt `_veilig_legal_check` juist als
    # wat er wég is (zelfde vorm als `test_notify_rol_is_niet_meer_hardwired_op_de_founder`).
    code = "\n".join(r for r in open("nooch_village/village.py", encoding="utf-8")
                     if not r.strip().startswith("#"))
    assert "_veilig_legal_check" not in code


def test_de_bestaande_inbox_items_blijven_af_te_handelen():
    """De SCHRIJVER is weg, de LEZER blijft. Op productie liggen items van dit type; een type dat
    `goedkeuring` niet meer kent is werk dat niemand kan sluiten."""
    from nooch_village.goedkeuring import TYPES
    assert "legal_signaal" in TYPES


def test_de_ingest_hangt_niet_meer_aan_een_losse_cron():
    """De crontab-regel op de server moet bij het deployen weg; de code zegt dat er ook bij, zodat
    wie dit later leest niet hoeft te raden waarom het twee keer draaide."""
    bron = open("nooch_village/village.py", encoding="utf-8").read()
    assert "30 6 * * *" in bron and "tweemaal per dag" in bron


# ── De verzamelaar (pijplijn stap 2, 20 sept 2026) ──────────────────────────
#
# `verzamel()` is `check()` zonder de aflevering: hij geeft `weekmemo.Signaal`-objecten terug en
# schrijft niets. Dat is de scheiding die de pijplijn aanbrengt — een verzamelaar WAARNEEMT, de
# memo bepaalt wat de lezer ziet, en de mens bepaalt wat er gebeurt.
#
# Wat hieronder NIET opnieuw wordt getoetst: de beoordeling zelf. Die zit in `beoordeel` en heeft
# zijn eigen tests hierboven; `verzamel` gebruikt precies dezelfde functie, dus hem hier nog eens
# toetsen zou dezelfde belofte op twee plekken vastleggen.

def test_verzamel_levert_signalen_en_schrijft_niets(tmp_path):
    _radar(tmp_path, [{"content": "EU scherpt regels voor groene claims aan",
                       "link": "https://eu-nieuws.eu/a", "at": NU - 3600}])
    voor = (tmp_path / "radar.json").read_bytes()
    uit = ls.verzamel(str(tmp_path), nu=NU,
                      reason_fn=lambda p, **k: "RELEVANT: check onze claimpagina")
    assert len(uit) == 1
    s = uit[0]
    assert s.bron == "legal"
    assert "groene claims" in s.tekst                       # de tekst is die van de BRON
    assert s.vindplaats == "https://eu-nieuws.eu/a"
    assert s.gevonden_op > 0
    assert s.extra["reden"].startswith("check onze claimpagina")   # wat het MODEL toevoegde
    # Side-effect-free: dit is de eigenschap waar stap 7 een ratchet op zet.
    assert (tmp_path / "radar.json").read_bytes() == voor
    assert not (tmp_path / "human_inbox.json").exists()


def test_verzamel_is_fail_closed_bij_een_storing(tmp_path):
    """Dezelfde posture als `check`: geen model of een fout levert GEEN signaal, nooit een gok.
    Een vals juridisch alarm ondermijnt de echte."""
    _radar(tmp_path, [{"content": "EU scherpt regels aan", "link": "https://eu-nieuws.eu/a",
                       "at": NU - 3600}])

    def _stuk(prompt, **kw):
        raise RuntimeError("geen krediet")

    assert ls.verzamel(str(tmp_path), nu=NU, reason_fn=_stuk) == []
    assert ls.verzamel(str(tmp_path), nu=NU, reason_fn=lambda p, **k: "NO") == []


def test_verzamel_kijkt_terug_tot_sinds_en_niet_tot_36_uur(tmp_path):
    """Het venster is een eigenschap van de AANROEP geworden. `check` kijkt 36 uur terug (een
    dagpuls), de weekmemo een week — en dat verschil hoort niet in de bron te zitten."""
    _radar(tmp_path, [{"content": "verse wetswijziging over groene claims",
                       "link": "https://eu-nieuws.eu/vers", "at": NU - 3600},
                      {"content": "oudere wetswijziging over groene claims",
                       "link": "https://eu-nieuws.eu/oud", "at": NU - 5 * 86400}])
    ja = lambda p, **k: "RELEVANT: iets"                     # noqa: E731
    week = ls.verzamel(str(tmp_path), nu=NU, sinds=NU - 7 * 86400, reason_fn=ja)
    dag = ls.verzamel(str(tmp_path), nu=NU, sinds=NU - 36 * 3600, reason_fn=ja)
    assert len(week) == 2 and len(dag) == 1
    assert dag[0].vindplaats.endswith("/vers")


def test_verzamel_leest_alleen_de_legal_feed(tmp_path):
    _radar(tmp_path, [{"content": "iets juridisch", "link": "https://a", "at": NU - 3600},
                      {"content": "een nieuw materiaal", "link": "https://b", "at": NU - 3600,
                       "feed": "Material Innovation"}])
    uit = ls.verzamel(str(tmp_path), nu=NU, reason_fn=lambda p, **k: "RELEVANT: iets")
    assert [s.vindplaats for s in uit] == ["https://a"]


def test_de_cap_begrenst_de_rekening_per_ronde(tmp_path):
    """Stond op `check` (per puls) en hoort net zo goed bij `verzamel`: één modelaanroep per
    signaal, dus zonder cap bepaalt een drukke nieuwsweek de rekening."""
    _radar(tmp_path, [{"content": f"Wetsvoorstel {i} over groene claims",
                       "link": f"https://eu-nieuws.eu/{i}", "at": NU - 3600} for i in range(10)])
    gezien = []
    ls.verzamel(str(tmp_path), nu=NU, sinds=NU - 7 * 86400, cap=3,
                reason_fn=lambda p, **k: gezien.append(p) or "NO")
    assert len(gezien) == 3


def test_de_drempel_staat_op_de_bron():
    """Stap 2's kernkeuze: de drempel hoort bij de bron en niet bij de pijplijn. Staat hij hier
    niet, dan moet de memo hem raden — en dan is hij impliciet, precies wat we opheffen."""
    from nooch_village.weekmemo import DREMPELS
    assert ls.DREMPEL == "fail-closed" and ls.DREMPEL in DREMPELS
