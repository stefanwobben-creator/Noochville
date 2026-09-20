"""Eén lookup bepaalt de memo-ontvanger én de landing van het project dat eruit volgt.

WAAROM ÉÉN: zou de memo naar de ene rol gaan en het project naar de andere, dan kan "één persoon
oordeelt én bezit" alleen per toeval kloppen, en breekt het stil zodra de org verschuift.

WAAROM GEEN VASTE ID: `creator_of_shoes` is vandaag het antwoord, niet de regel. Rolvervulling en
rol-eigenaarschap veranderen; een bevroren id wijst dan stil naar de verkeerde plek.

WAT ER OP 20 SEPTEMBER 2026 VERANDERDE (pijplijn stap 5). De ladder had een tweede trede: hield
niemand het domein, dan matchte `classificeer` de tekst tegen de accountabilities en DAT werd het
adres. Een model dat een ontvanger aanwijst wijst werk toe, en dat is de grens uit CLAUDE.md ("AI
is instrument, geen rol"). De trede is weg; het modeloordeel reist mee als `voorstel_regel` — een
zin in het bericht, die niets verplaatst. `test_het_modelvoorstel_is_nooit_het_adres` is de guard.
"""
from __future__ import annotations

import types

import pytest

from nooch_village import triage_rol


def _dm_teksten(st_of_dd, rol_of_persoon=None):
    """Alle DM-teksten in een dorp, of die van één rol/persoon.

    Sinds B2 (20 sept 2026) landt een melding als DM bij de mens in plaats van als rij in
    `NotifStore`. De routering — wie het krijgt — is ongewijzigd; alleen de plek is verhuisd."""
    from nooch_village import channels, signaal
    st = st_of_dd
    if isinstance(st_of_dd, str):
        st = signaal._MiniStores(st_of_dd)
    if rol_of_persoon is None:
        return [e.get("text") or "" for k in st.channels.bestaande()
                if channels.soort_van(k) == channels.DM for e in st.channels.trail(k)]
    wie, _ = signaal.ontvangers(st, "role", rol_of_persoon)
    if not wie:
        wie = [rol_of_persoon]
    return [e.get("text") or "" for p in wie for k in st.channels.kanalen_van(p)
            for e in st.channels.trail(k)]

@pytest.fixture
def dorp(monkeypatch):
    """Een dorp waarin ik per test bepaal wie welk domein houdt en wie welke rol vervult.

    `eigenaar` is de VERKLARING (wie houdt het domein) en `match` is wat het MODEL ervan vindt.
    Ze staan bewust los van elkaar: precies daarin zit het verschil dat deze tests bewaken."""
    staat = {"eigenaar": "", "match": "", "mensen": {}, "lead": {}}

    monkeypatch.setattr(triage_rol, "domein_eigenaar",
                        lambda st, domein: {"rol": staat["eigenaar"],
                                            "grond": (f"houdt het domein {domein!r}"
                                                      if staat["eigenaar"] else "geen eigenaar")})
    monkeypatch.setattr(triage_rol, "classificeer",
                        lambda tekst, records, **kw: {"rol": staat["match"],
                                                      "grond": "gematcht door de secretary"})
    import nooch_village.cockpit2 as c
    monkeypatch.setattr(c, "mens_vervullers", lambda st, rol: staat["mensen"].get(rol, []))
    monkeypatch.setattr(c, "_circle_lead_van", lambda st, rol: staat["lead"].get(rol, ""))
    return staat


def _st():
    return types.SimpleNamespace(records=object())


def test_de_bemande_domein_eigenaar_krijgt_het_werk(dorp):
    """Het adres is een governance-feit: deze rol HOUDT dit domein."""
    dorp["eigenaar"] = "creator_of_shoes"
    dorp["mensen"] = {"creator_of_shoes": ["lotte"]}
    uit = triage_rol.menselijke_eigenaar(_st(), "sample aanvragen bij X", domein="Materials")
    assert uit["rol"] == "creator_of_shoes" and uit["mens"] == "lotte"
    assert uit["via"] == ""                               # geen omleiding nodig
    assert uit["voorstel_regel"] == ""                    # niets te voorstellen: het is verklaard


def test_het_modelvoorstel_is_nooit_het_adres(dorp):
    """DE GUARD. Het model wijst een rol aan die bestaat, bemand is en perfect zou passen — en het
    bericht gaat er tóch niet heen. Een modeloordeel met organisatorisch effect hoort een
    mensbeslissing ervóór te hebben, niet erna als correctie."""
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    dorp["eigenaar"] = ""                                 # niemand houdt het domein
    dorp["match"] = "creator_of_shoes"                    # het model weet het zeker
    dorp["mensen"] = {"creator_of_shoes": ["lotte"], FOUNDER_ROLE_ID: ["stefan"]}
    uit = triage_rol.menselijke_eigenaar(_st(), "sample aanvragen bij X", domein="Materials")
    assert uit["rol"] == FOUNDER_ROLE_ID and uit["mens"] == "stefan"
    assert uit["voorstel"]["rol"] == "creator_of_shoes"   # het oordeel gaat niet verloren …
    assert "creator_of_shoes" in uit["voorstel_regel"]    # … het wordt een zin
    assert "niet toegewezen" in uit["voorstel_regel"]


def test_een_AI_VERVULDE_rol_is_een_dead_letter(dorp):
    """DE GUARD. Een persona leest de NotifStore nooit, dus een bericht daarheen valt stil.
    `bestemming()` hopt hier NIET — die vraagt of de rol kan UITVOEREN, en dat kan een persona.
    Wij vragen of er iemand LEEST, en dat is een andere vraag."""
    dorp["eigenaar"] = "harry_hemp"
    dorp["mensen"] = {"harry_hemp": [], "nooch_lead": ["stefan"]}   # AI-vervuld → geen mens
    dorp["lead"] = {"harry_hemp": "nooch_lead"}
    uit = triage_rol.menselijke_eigenaar(_st(), "sample aanvragen bij X", domein="Materials")
    assert uit["rol"] == "nooch_lead" and uit["mens"] == "stefan"
    assert "geen menselijke vervuller" in uit["via"]


def test_zonder_domein_eigenaar_gaat_het_naar_de_founder(dorp):
    """Niets verklaard = niet stil gokken. Het gaat naar het laatste adres dat altijd bestaat."""
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    dorp["eigenaar"] = ""
    dorp["match"] = ""
    dorp["mensen"] = {FOUNDER_ROLE_ID: ["stefan"]}
    uit = triage_rol.menselijke_eigenaar(_st(), "iets onherkenbaars")
    assert uit["rol"] == FOUNDER_ROLE_ID
    assert uit["via"].startswith("geen rol houdt dit domein")
    assert uit["voorstel_regel"] == ""                    # geen match = geen zin


def test_ook_de_lead_onbemand_valt_open_naar_de_founder(dorp):
    """Nooit stil laten vallen: er is altijd een laatste adres."""
    from nooch_village.human_inbox import FOUNDER_ROLE_ID
    dorp["eigenaar"] = "harry_hemp"
    dorp["mensen"] = {}
    dorp["lead"] = {"harry_hemp": "lege_lead"}
    uit = triage_rol.menselijke_eigenaar(_st(), "sample aanvragen bij X")
    assert uit["rol"] == FOUNDER_ROLE_ID
    assert "ook de Circle Lead is onbemand" in uit["via"]


def test_de_uitkomst_is_leesbaar_zonder_de_code_ernaast(dorp):
    """`via` en `waarom` zijn er voor de droge run: een bestemming zonder uitleg dwingt de lezer
    de code te openen om te zien of hij klopt."""
    dorp["eigenaar"] = "harry_hemp"
    dorp["mensen"] = {"nooch_lead": ["stefan"]}
    dorp["lead"] = {"harry_hemp": "nooch_lead"}
    uit = triage_rol.menselijke_eigenaar(_st(), "x", domein="Materials")
    assert uit["waarom"] == "houdt het domein 'Materials'"
    assert "harry_hemp" in uit["via"]


def test_notify_rol_is_niet_meer_hardwired_op_de_founder():
    """De enige meldweg van de pulslus stuurde élke headsup naar FOUNDER_ROLE_ID, ook als het werk
    aantoonbaar bij iemand anders hoorde."""
    import inspect
    from nooch_village.inhabitant import Inhabitant
    assert hasattr(Inhabitant, "_notify_rol")
    src = inspect.getsource(Inhabitant._notify_rol)
    # De CODE, niet de docstring: die noemt FOUNDER_ROLE_ID juist wel, als uitleg van wat er
    # veranderde. Een assertie over de hele bron zou de uitleg verbieden in plaats van de hardwire.
    code = src[src.index('"""', src.index('"""') + 3) + 3:]
    assert "FOUNDER_ROLE_ID" not in code              # de rol komt van de aanroeper
    # Was `NotifStore(pad).add("role", rol_id`. Sinds B2 loopt dit via `signaal.stuur_op_pad`,
    # maar het punt van deze test is onveranderd: de ROL is het adres, niet de founder.
    assert 'stuur_op_pad(self.context.data_dir, "role", rol_id' in src
