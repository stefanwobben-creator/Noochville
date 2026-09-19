"""De dagelijkse legal-check en de verhuizing van de radar-ingest naar de dagcadans (19 sept 2026).

Twee dingen die in dezelfde beurt zijn gebouwd en om dezelfde reden bij elkaar horen: de radar werd
een swipefile die niemand dagelijks leest, en voor één van de vier feeds is dat niet goed genoeg.
Een wetswijziging over duurzaamheidsclaims is geen trend maar een deadline.

Wat hier vastligt:
  1. alleen de Legal-feed wordt gelezen, alleen binnen het venster, en met een cap;
  2. NEE levert niets op, en elke storing levert ook niets op (fail-closed — liever een gemiste
     melding dan een verzonnen juridisch alarm);
  3. dedup op de artikel-LINK, niet op de kop: drie uitgevers over dezelfde wet mogen drie
     meldingen zijn, hetzelfde artikel twee keer is er één;
  4. beide taken hangen echt aan `dag_begint`, en in die volgorde.
"""
from __future__ import annotations

import time

from nooch_village.human_inbox import HumanInbox
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


def _inbox(tmp_path):
    return HumanInbox(str(tmp_path / "human_inbox.json"))


# ── 1. selectie: feed, venster, cap ──────────────────────────────────────────
def test_alleen_de_legal_feed_wordt_gelezen(tmp_path):
    _radar(tmp_path, [
        {"content": "EU tightens green claims rules", "link": "https://a.eu/1", "at": NU},
        {"content": "Mycelium leather scales up", "link": "https://b.eu/2", "at": NU,
         "feed": "Material Innovation"},
    ])
    gezien = []
    def fake(prompt, **kw):
        gezien.append(prompt)
        return "RELEVANT: check our claim wording"
    ls.check(str(tmp_path), _inbox(tmp_path), nu=NU, reason_fn=fake)
    assert len(gezien) == 1 and "green claims" in gezien[0]


def test_een_oud_signaal_valt_buiten_het_venster(tmp_path):
    _radar(tmp_path, [{"content": "Oude wetswijziging", "link": "https://a.eu/oud",
                       "at": NU - 48 * 3600}])
    aangeroepen = []
    ls.check(str(tmp_path), _inbox(tmp_path), nu=NU,
             reason_fn=lambda p, **k: aangeroepen.append(p) or "RELEVANT: x")
    assert aangeroepen == []


def test_een_signaal_zonder_bruikbare_tijd_telt_niet_als_vers(tmp_path):
    """'Misschien vers' is hier geen grond — anders wordt elke herstart een melding-storm.
    Een onleesbare publicatiedatum valt terug op `at`, en dat is in deze test de echte klok,
    ruim vóór het venster rond NU."""
    _radar(tmp_path, [{"content": "Zonder tijd", "link": "https://a.eu/x", "published_at": "ooit"}])
    assert ls.check(str(tmp_path), _inbox(tmp_path), nu=NU,
                    reason_fn=lambda p, **k: "RELEVANT: x") == []


def test_de_cap_begrenst_de_rekening_per_puls(tmp_path):
    _radar(tmp_path, [{"content": f"Wetsvoorstel {i}", "link": f"https://a.eu/{i}", "at": NU}
                      for i in range(10)])
    n = []
    ls.check(str(tmp_path), _inbox(tmp_path), nu=NU, cap=3,
             reason_fn=lambda p, **k: n.append(p) or "NO")
    assert len(n) == 3


# ── 2. fail-closed ───────────────────────────────────────────────────────────
def test_nee_levert_geen_item(tmp_path):
    _radar(tmp_path, [{"content": "Schoenenmerk haalt funding op", "link": "https://a.eu/1", "at": NU}])
    inbox = _inbox(tmp_path)
    assert ls.check(str(tmp_path), inbox, nu=NU, reason_fn=lambda p, **k: "NO") == []
    assert inbox.pending() == []


def test_geen_model_of_een_fout_levert_geen_item(tmp_path):
    _radar(tmp_path, [{"content": "EU tightens green claims", "link": "https://a.eu/1", "at": NU}])
    def knalt(prompt, **kw):
        raise RuntimeError("geen sleutel")
    inbox = _inbox(tmp_path)
    assert ls.check(str(tmp_path), inbox, nu=NU, reason_fn=knalt) == []
    assert ls.check(str(tmp_path), inbox, nu=NU, reason_fn=lambda p, **k: None) == []
    assert ls.check(str(tmp_path), inbox, nu=NU, reason_fn=lambda p, **k: "") == []
    assert inbox.pending() == []


def test_een_treffer_draagt_de_reden_en_de_link(tmp_path):
    _radar(tmp_path, [{"content": "EU tightens green claims rules", "link": "https://a.eu/1",
                       "source": "fashionunited.com", "at": NU}])
    inbox = _inbox(tmp_path)
    ids = ls.check(str(tmp_path), inbox, nu=NU,
                   reason_fn=lambda p, **k: "RELEVANT: check the wording of our vegan claim")
    assert len(ids) == 1
    item = inbox.get(ids[0])
    assert item["type"] == "legal_signaal"
    ctx = item["context"]
    assert ctx["link"] == "https://a.eu/1" and ctx["bron"] == "fashionunited.com"
    assert "vegan claim" in ctx["reden"]


# ── 3. dedup op de link ──────────────────────────────────────────────────────
def test_hetzelfde_artikel_meldt_maar_een_keer(tmp_path):
    _radar(tmp_path, [{"content": "EU tightens green claims", "link": "https://a.eu/1", "at": NU}])
    inbox = _inbox(tmp_path)
    ja = lambda p, **k: "RELEVANT: x"
    eerste = ls.check(str(tmp_path), inbox, nu=NU, reason_fn=ja)
    tweede = ls.check(str(tmp_path), inbox, nu=NU, reason_fn=ja)
    assert len(eerste) == 1
    assert tweede == [] or tweede == eerste          # geen tweede item
    assert len([i for i in inbox.all() if i["type"] == "legal_signaal"]) == 1


def test_drie_bronnen_over_dezelfde_wet_zijn_drie_meldingen(tmp_path):
    """Dedup op de LINK, niet op de kop: dat drie uitgevers dit brengen is zelf informatie."""
    # De koppen verschillen, zoals bij drie uitgevers: de RadarStore dedupliceert zelf al op
    # (rol, soort, inhoud), dus drie identieke koppen zijn daar al één signaal.
    _radar(tmp_path, [{"content": f"EU tightens green claims, says {h}", "link": f"https://{h}/1",
                       "source": h, "at": NU} for h in ("a.eu", "b.eu", "c.eu")])
    inbox = _inbox(tmp_path)
    ids = ls.check(str(tmp_path), inbox, nu=NU, reason_fn=lambda p, **k: "RELEVANT: x")
    assert len(ids) == 3


# ── 4. de puls-bedrading ─────────────────────────────────────────────────────
def test_beide_taken_hangen_aan_dag_begint_en_in_de_juiste_volgorde():
    """Eerst ophalen, dan beoordelen — anders ziet de legal-check pas morgen wat vanochtend kwam."""
    bron = open("nooch_village/village.py", encoding="utf-8").read()
    i = bron.index('self.bus.subscribe("dag_begint", lambda e: self._veilig_radar_ingest())')
    j = bron.index('self.bus.subscribe("dag_begint", lambda e: self._veilig_legal_check())')
    assert i < j


def test_de_ingest_hangt_niet_meer_aan_een_losse_cron():
    """De crontab-regel op de server moet bij het deployen weg; de code zegt dat er ook bij, zodat
    wie dit later leest niet hoeft te raden waarom het twee keer draaide."""
    bron = open("nooch_village/village.py", encoding="utf-8").read()
    assert "30 6 * * *" in bron and "tweemaal per dag" in bron
