"""Het dorp kan googelen, en leest meteen wat het vindt.

AANLEIDING: SerpAPI zat er drie keer in (competitor_discover, linkbuilding, claim_evidence), elke
keer vastgeklonken aan één doel. `haal_pagina` leest één pagina, maar alleen als je de URL al hebt.
Een vrije vraag aan het web kon niemand stellen.

Wat hieronder vastligt, in volgorde van belang:

1. **Zoeken én lezen.** Acht links teruggeven verplaatst het werk alleen maar. Eén aanroep levert
   een bevinding op, geen huiswerk.
2. **Fail-closed op de zoekopdracht.** Geen sleutel of een stukke API is een FOUT. Een lege lijst
   zou gelezen worden als "er staat niets over op het web", en dat is een dure verwisseling.
3. **Fail-soft op het lezen.** Eén paywall mag de andere zeven treffers niet meenemen.
4. **`no_data` ≠ storing.** Nul treffers van een werkende zoekmachine is een antwoord.
5. **Wie antwoordde staat erbij.** Twee motoren geven verschillende resultaten; zonder afzender is
   een uitkomst van vandaag niet te vergelijken met die van vorige week.
"""
from __future__ import annotations

from nooch_village import safe_fetch
from nooch_village.skills_impl.web_zoek import WebZoekSkill, _als_tekst

CTX = type("Ctx", (), {"settings": {"SERPAPI_API_KEY": "k"}})()

TREFFERS = [
    {"title": "Vegan shoes are growing", "link": "https://voorbeeld.example/groei",
     "snippet": "Sales of vegan footwear rose 30% in 2025."},
    {"title": "Plant-based leather", "link": "https://ander.example/leer",
     "snippet": "Mycelium and cactus are the two front-runners."},
    {"title": "Zonder fragment", "link": "https://derde.example/x"},
]


def _skill(treffers=None, *, tekst="De volledige pagina staat hier, met veel meer detail.",
           haal_fout=None):
    def _zoek(term, key, *, num=10, gl="", hl=""):
        _zoek.gezien = {"term": term, "key": key, "num": num, "gl": gl, "hl": hl}
        return list(TREFFERS if treffers is None else treffers)

    def _haal(url):
        if haal_fout is not None:
            raise haal_fout
        return {"url": url, "status": 200, "titel": "t", "tekst": tekst}

    s = WebZoekSkill(zoek=_zoek, haal=_haal)
    s._gezien = _zoek
    return s


# ── zoeken én lezen ──────────────────────────────────────────────────────────

def test_levert_treffers_met_url_domein_en_fragment():
    uit = _skill().run({"term": "vegan shoes growth"}, CTX)
    assert uit["ok"] is True and uit["aantal_treffers"] == 3
    eerste = uit["treffers"][0]
    assert eerste["url"] == "https://voorbeeld.example/groei"
    assert eerste["domein"] == "voorbeeld.example"
    assert eerste["fragment"].startswith("Sales of vegan footwear")


def test_leest_de_bovenste_paginas_ook(monkeypatch):
    """DE KERNTEST. Een lijst links verplaatst het werk naar de volgende checklist-ronde; de tekst
    beantwoordt de vraag nu. Daarom leest hij standaard de bovenste drie."""
    uit = _skill().run({"term": "t"}, CTX)
    assert uit["gelezen"] == 3
    assert all(t["gelezen"] and t["tekst"] for t in uit["treffers"][:3])
    assert "volledige pagina" in uit["treffers"][0]["tekst"]


def test_lees_nul_geeft_alleen_de_lijst():
    uit = _skill().run({"term": "t", "lees": 0}, CTX)
    assert uit["gelezen"] == 0
    assert all(t["tekst"] == "" for t in uit["treffers"])
    assert uit["treffers"][0]["fragment"]                 # het fragment blijft, dat kost niets


def test_lees_boven_het_maximum_wordt_afgetopt():
    """Elke gelezen pagina is een fetch en context; 'lees: 50' is geen zoekopdracht meer maar een
    crawl. De bovengrens staat in code zodat een payload hem niet kan omzeilen."""
    uit = _skill([{"title": f"n{i}", "link": f"https://x{i}.example/"} for i in range(20)]).run(
        {"term": "t", "lees": 50, "aantal": 20}, CTX)
    assert uit["gelezen"] == 5


def test_aantal_en_taalvoorkeur_gaan_mee_naar_de_zoekmachine():
    s = _skill()
    s.run({"term": "vegan schoenen", "aantal": 5, "land": "nl", "taal": "nl"}, CTX)
    assert s._gezien.gezien == {"term": "vegan schoenen", "key": "k", "num": 5,
                                "gl": "nl", "hl": "nl"}


# ── fail-closed op de zoekopdracht ───────────────────────────────────────────

def test_zonder_sleutel_een_fout_en_geen_lege_lijst(monkeypatch):
    """Een lege uitkomst zou hier gelezen worden als 'er staat niets over op het web'. Dat is de
    duurste verwisseling die deze skill kan maken, dus hij faalt zichtbaar, met beide sleutelnamen
    erin zodat je weet wat je moet zetten."""
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    leeg = type("Ctx", (), {"settings": {}})()
    uit = _skill().run({"term": "t"}, leeg)
    assert "error" in uit
    assert "SERPAPI_API_KEY" in uit["error"] and "BRAVE_API_KEY" in uit["error"]
    assert "treffers" not in uit


def test_stukke_zoekmachine_is_een_fout():
    def _stuk(*a, **k):
        raise RuntimeError("429 rate limited")
    uit = WebZoekSkill(zoek=_stuk).run({"term": "t"}, CTX)
    assert "error" in uit and "429" in uit["error"]


def test_term_is_verplicht():
    assert "error" in _skill().run({}, CTX)
    assert "error" in _skill().run({"term": "   "}, CTX)


def test_vraag_mag_ook_als_de_planner_die_naam_gebruikt():
    """`zoekstrategie` levert stappen met `term`; een vrij plan schrijft soms `vraag`. Allebei
    accepteren is één regel en scheelt een stap die op een sleutelnaam sterft."""
    uit = _skill().run({"vraag": "vegan shoes"}, CTX)
    assert uit["ok"] is True and uit["term"] == "vegan shoes"


# ── fail-soft op het lezen ───────────────────────────────────────────────────

def test_een_pagina_die_niet_meewerkt_kost_alleen_zijn_eigen_regel():
    uit = _skill(haal_fout=safe_fetch.FetchMislukt("403 Forbidden")).run({"term": "t"}, CTX)
    assert uit["ok"] is True and uit["aantal_treffers"] == 3      # de treffers staan er nog
    assert uit["gelezen"] == 0
    assert "403" in uit["treffers"][0]["reden"]                   # mét uitleg, niet stil leeg


def test_een_geweigerde_url_ook():
    uit = _skill(haal_fout=safe_fetch.FetchGeweigerd("privé-adres")).run({"term": "t"}, CTX)
    assert uit["ok"] is True and "geweigerd" in uit["treffers"][0]["reden"]


def test_javascript_only_pagina_krijgt_een_reden_en_geen_lege_tekst():
    uit = _skill(tekst="   ").run({"term": "t"}, CTX)
    assert uit["treffers"][0]["gelezen"] is False
    assert "JavaScript" in uit["treffers"][0]["reden"]


def test_onverwachte_fout_bij_lezen_breekt_de_zoekopdracht_niet():
    uit = _skill(haal_fout=ValueError("iets raars")).run({"term": "t"}, CTX)
    assert uit["ok"] is True and "ValueError" in uit["treffers"][0]["reden"]


# ── no_data ≠ storing ────────────────────────────────────────────────────────

def test_nul_treffers_is_een_antwoord_geen_fout():
    uit = _skill([]).run({"term": "asdkjhasd"}, CTX)
    assert uit["ok"] is True and uit["no_data"] is True
    assert "error" not in uit
    assert "asdkjhasd" in uit["reason"]


def test_een_treffer_zonder_url_telt_niet_mee():
    uit = _skill([{"title": "x", "link": "  "}, TREFFERS[0]]).run({"term": "t"}, CTX)
    assert uit["aantal_treffers"] == 1


# ── de wall-tekst ────────────────────────────────────────────────────────────

def test_de_wall_tekst_noemt_de_term_en_de_bronnen():
    t = _skill().run({"term": "vegan shoes"}, CTX)["text"]
    assert "vegan shoes" in t
    assert "voorbeeld.example" in t
    assert "Sales of vegan footwear" in t


def test_de_wall_tekst_toont_fragmenten_en_niet_de_hele_pagina():
    """De wall is om te lezen; de paginatekst is om mee te werken. Zou de hele tekst erin staan, dan
    is de deliverable een muur en scrollt een mens er langs zonder hem te lezen."""
    t = _skill(tekst="X" * 3000).run({"term": "t"}, CTX)["text"]
    assert "XXXXXXXXXX" not in t


def test_wall_tekst_van_een_treffer_zonder_fragment_valt_terug_op_iets_zinnigs():
    regels = _als_tekst("t", [{"titel": "T", "url": "https://a.example/", "domein": "a.example",
                               "fragment": "", "tekst": "x", "gelezen": True, "reden": ""}],
                        "serpapi")
    assert "read in full" in regels


# ── twee motoren, één vorm ───────────────────────────────────────────────────

def _ctx(**settings):
    return type("Ctx", (), {"settings": dict(settings)})()


BEIDE = {"SERPAPI_API_KEY": "s", "BRAVE_API_KEY": "b"}


def _motor_skill(*, faalt=(), leeg=()):
    """Een skill met echte motorkeuze, maar zonder netwerk. `faalt` is een set motornamen die een
    fout gooien; de rest levert TREFFERS."""
    gezien = []

    def _zoek(term, key, *, num=10, gl="", hl=""):
        motor = {"s": "serpapi", "b": "brave"}[key]
        gezien.append(motor)
        if motor in faalt:
            raise RuntimeError(f"{motor} is stuk")
        return [] if motor in leeg else list(TREFFERS)

    s = WebZoekSkill(zoek=_zoek, haal=lambda url: {"tekst": "pagina", "url": url})
    s.gezien = gezien
    return s


def test_de_uitkomst_zegt_welke_motor_antwoordde():
    """DE KERNTEST VAN DIT BLOK. Twee zoekmachines geven verschillende resultaten. Zonder afzender is
    een uitkomst van vandaag niet te vergelijken met die van vorige week, en dan is 'Brave vindt meer'
    een gevoel in plaats van een meting."""
    uit = _motor_skill().run({"term": "t"}, _ctx(**BEIDE))
    assert uit["bron"] == "serpapi"
    assert "via serpapi" in uit["text"]


def test_auto_neemt_serpapi_als_die_een_sleutel_heeft():
    s = _motor_skill()
    s.run({"term": "t"}, _ctx(**BEIDE))
    assert s.gezien == ["serpapi"]                        # Brave is niet eens geprobeerd


def test_auto_pakt_brave_als_serpapi_geen_sleutel_heeft():
    s = _motor_skill()
    uit = s.run({"term": "t"}, _ctx(BRAVE_API_KEY="b"))
    assert uit["bron"] == "brave" and s.gezien == ["brave"]


def test_auto_valt_terug_als_de_eerste_motor_stuk_is():
    """SerpAPI's gratis plan is 250 zoekopdrachten per maand. Opraken is een reëel scenario, en dan
    is een maand zonder onderzoek een duurdere uitkomst dan een maand met Brave-resultaten."""
    s = _motor_skill(faalt={"serpapi"})
    uit = s.run({"term": "t"}, _ctx(**BEIDE))
    assert uit["ok"] is True and uit["bron"] == "brave"
    assert s.gezien == ["serpapi", "brave"]


def test_terugvallen_gebeurt_niet_stil():
    """Een uitkomst die er goed uitziet terwijl de eerste motor zonder credits zat, is precies het
    soort stilte waar je een maand later achterkomt."""
    uit = _motor_skill(faalt={"serpapi"}).run({"term": "t"}, _ctx(**BEIDE))
    assert uit["teruggevallen_van"] == ["serpapi: RuntimeError: serpapi is stuk"]


def test_zonder_terugval_geen_ruis_in_de_uitvoer():
    assert "teruggevallen_van" not in _motor_skill().run({"term": "t"}, _ctx(**BEIDE))


def test_beide_motoren_stuk_is_een_fout_met_allebei_de_redenen():
    uit = _motor_skill(faalt={"serpapi", "brave"}).run({"term": "t"}, _ctx(**BEIDE))
    assert "error" in uit
    assert "serpapi is stuk" in uit["error"] and "brave is stuk" in uit["error"]


def test_een_expliciete_keuze_valt_niet_terug():
    """DE TWEEDE KERNTEST. Vraag je om Brave, dan wil je Brave weten, niet stiekem Google. Zou hij
    hier terugvallen, dan kun je de twee motoren nooit tegen elkaar meten."""
    s = _motor_skill(faalt={"brave"})
    uit = s.run({"term": "t"}, _ctx(web_zoek_bron="brave", **BEIDE))
    assert "error" in uit and s.gezien == ["brave"]


def test_een_expliciete_keuze_wordt_gevolgd_ook_als_de_ander_er_is():
    s = _motor_skill()
    uit = s.run({"term": "t"}, _ctx(web_zoek_bron="brave", **BEIDE))
    assert uit["bron"] == "brave" and s.gezien == ["brave"]


def test_een_typfout_in_de_setting_legt_het_onderzoek_niet_stil():
    """Weigeren op een onbekende waarde zou betekenen dat één verkeerd getypte setting alle
    onderzoek stopt, met een fout die niemand aan die setting koppelt."""
    uit = _motor_skill().run({"term": "t"}, _ctx(web_zoek_bron="gooogle", **BEIDE))
    assert uit["ok"] is True and uit["bron"] == "serpapi"


def test_nul_treffers_noemt_ook_de_motor():
    uit = _motor_skill(leeg={"serpapi"}).run({"term": "x"}, _ctx(SERPAPI_API_KEY="s"))
    assert uit["no_data"] is True and uit["bron"] == "serpapi"
    assert "serpapi" in uit["reason"]


def test_kleine_letters_in_de_sleutelnaam_werken_ook():
    """`competitor_discover` leest hoofdletters, `trend_reindex` kleine. Allebei accepteren scheelt
    een skill die zichtbaar faalt op een schrijfwijze."""
    uit = _motor_skill().run({"term": "t"}, _ctx(serpapi_api_key="s"))
    assert uit["ok"] is True and uit["bron"] == "serpapi"


# ── de brave-bron zelf ───────────────────────────────────────────────────────

def test_brave_levert_dezelfde_vorm_als_serpapi(monkeypatch):
    """Normaliseren hoort bij de bron, niet bij de skill: `web_zoek` mag niet hoeven weten welke
    motor er draaide."""
    from nooch_village import web_read

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"web": {"results": [
                {"title": "Vegan <strong>shoes</strong>", "url": "https://a.example/",
                 "description": "Sales rose <strong>30%</strong>."},
                {"title": "geen url", "url": ""},
            ]}}

    gezien = {}

    def _get(url, params=None, timeout=None, headers=None):
        gezien.update(url=url, params=params, headers=headers)
        return _Resp()

    import requests
    monkeypatch.setattr(requests, "get", _get)
    uit = web_read.brave_search("vegan shoes", "sleutel", num=5, gl="nl", hl="en")

    assert uit == [{"title": "Vegan shoes", "link": "https://a.example/",
                    "snippet": "Sales rose 30%."}]      # opmaak eruit, lege url eruit
    assert gezien["headers"]["X-Subscription-Token"] == "sleutel"
    assert gezien["params"] == {"q": "vegan shoes", "count": 5, "country": "nl",
                                "search_lang": "en"}


def test_brave_count_gaat_niet_boven_zijn_maximum(monkeypatch):
    from nooch_village import web_read

    gezien = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {}

    import requests
    monkeypatch.setattr(requests, "get",
                        lambda url, params=None, **k: (gezien.update(params), _Resp())[1])
    web_read.brave_search("t", "k", num=500)
    assert gezien["count"] == 20


# ── het dorp weet ervan ──────────────────────────────────────────────────────

def test_de_skill_is_geregistreerd():
    """Zonder registratie is een grant een lege verwijzing: de rol draagt dan een naam die nergens
    op wijst. Dezelfde fout als `synthesize_cards`, die wél een bestand heeft en geen registratie."""
    from nooch_village.registry_factory import build_skill_registry
    assert "web_zoek" in build_skill_registry().names()


def test_zit_in_de_rugzak_buiten():
    from nooch_village import rugzak
    assert rugzak.rugzak_van(rugzak.laad("."), "web_zoek") == "buiten"


def test_zoekstrategie_kan_hem_kiezen():
    """Een bron die de strategie niet kent, wordt bij het plannen weggefilterd — dan bestaat de skill
    wel maar bereikt Sid hem nooit."""
    from nooch_village.skills_impl.zoekstrategie import BRONNEN
    assert "web_zoek" in BRONNEN


def test_kost_credits_en_zegt_dat():
    """De planner leest `cost`. Staat er 'free', dan kiest hij deze skill voor iets wat
    `library_lookup` gratis weet, en dat merk je pas op de SerpAPI-rekening."""
    s = WebZoekSkill()
    assert s.cost == "credits" and s.side_effect_free is True


def test_leest_alleen():
    """Geen formulieren, geen POST, geen login — en het ophalen loopt via safe_fetch, dus met de
    SSRF-guardrail van de site-scan."""
    import inspect
    from nooch_village.skills_impl import web_zoek
    bron = inspect.getsource(web_zoek)
    assert "requests.post" not in bron and ".post(" not in bron
    assert "safe_fetch.haal_tekst_geduldig" in bron
