"""De domeinstructuur van de wiki: elf vaste bakjes, één classificatietabel (23 september 2026).

WAAROM DIT BESTAAT. `render_wiki_index` groepeert al per domein, maar `Attachment.domain` werd
alleen gevuld voor policies — 110 van de 121 artefacten op prod hadden er dus geen, en vielen
allemaal in één "No domain yet"-bak. De structuur bestond op het scherm, niet in de data.

WAT ER GEMETEN IS VOORDAT DIT GEBOUWD WERD, en waarom het de vorm bepaalt:

  - Afleiden uit de ROL werkt niet. De operationele cirkel is de hele onderneming, dus zijn
    bakje wordt "Visie", en elke rol eronder zou dat erven — `creator_of_shoes` met zijn 14
    materiaalnotities incluis. Gemeten, niet bedacht.
  - Afleiden uit het DOMEIN werkt wel. De vier policies van de cirkel dragen `Money`,
    `Decision Making`, `WIP` en `Stance` en landen daarmee vanzelf in drie verschillende bakjes —
    precies wat één bakje per rol niet kon.
  - Er zijn 18 domeinen in de echte data, en na de beslisronde met Stefan zijn ze alle 18
    eenduidig geclassificeerd.

DE PRECEDENTIEREGEL (besluit Stefan). Van specifiek naar algemeen, en de eerste die iets oplevert
wint:

    0. een handmatige override op de pagina zelf   (`meta["domein"]`)
    1. het eigen `domain` van het artefact          (policies hebben dat)
    2. het domein van de eigenaar-rol
    3. de rol zelf
    4. het bakje van de omvattende cirkel

AFLEIDEN, NIET OPSLAAN (variant C). Het bakje wordt bij het LEZEN bepaald en nergens bewaard —
zelfde regel als `wiki.grond_status`: een vergelijking, geen stempel. Verandert de classificatie,
dan verschuiven alle pagina's mee zonder migratie. Alleen een handmatige verplaatsing wordt
opgeslagen, en dat gebeurt zelden: 3 van de 121 pagina's op prod.

De override leeft in `meta` en NIET in `domain`. Dat veld betekent "het governance-domein waar dit
bij hoort" en die betekenis blijft één ding; er zou anders na een backfill een mengsel van
governance-domeinen (`Money`) en bakje-sleutels (`sales-marketing`) in één veld staan.
"""
from __future__ import annotations

import pytest

from nooch_village import domeinen


class _Nep:
    """Genoeg van een Attachment om de regel te voeden."""

    def __init__(self, anchor="", domain="", meta=None, aid="X-001"):
        self.id, self.anchor, self.domain, self.meta = aid, anchor, domain, dict(meta or {})


class _NepRol:
    def __init__(self, rid, domains=(), parent=None, circle=False):
        self.id, self.parent = rid, parent
        self.definition = type("D", (), {"domains": list(domains)})()
        # `org.is_circle` leest `rec.type`, niet een eigen vlag — een nepcirkel met alleen
        # `_circle=True` werd dus als gewone rol gezien en stap 4 werd nooit bereikt.
        self.type = "circle" if circle else "role"
        self.archived = False


def _records(*rollen):
    return list(rollen)


# ── 1. De elf bakjes ─────────────────────────────────────────────────────────
def test_er_zijn_elf_bakjes_in_een_vaste_volgorde():
    """De volgorde IS de waardeketen en hoort dus niet alfabetisch te zijn: de zijbalk leest van
    ontwerp naar klant. Overig staat achteraan, want een restbak hoort nooit bovenaan."""
    sleutels = [s for s, _ in domeinen.BAKJES]
    assert sleutels == [
        "shoe-development", "sourcing-productie", "fulfillment", "sales-marketing", "service",
        "finance", "hr-organisatie", "compliance-legal", "visie-missie-strategie",
        "tech-platform", "overig"]


def test_elk_bakje_heeft_een_weergavenaam():
    for sleutel, label in domeinen.BAKJES:
        assert label and label != sleutel
        assert domeinen.label(sleutel) == label


def test_een_onbekend_bakje_valt_terug_op_overig():
    """Fail-soft op het SCHERM: een sleutel die niet bestaat mag geen lege kop opleveren."""
    assert domeinen.label("bestaat-niet") == domeinen.label("overig")


# ── 2. De classificatietabel ─────────────────────────────────────────────────
def test_elk_geclassificeerd_domein_wijst_naar_een_bestaand_bakje():
    geldig = {s for s, _ in domeinen.BAKJES}
    for dom, bak in domeinen.DOMEIN_BAKJE.items():
        assert bak in geldig, f"{dom!r} wijst naar onbekend bakje {bak!r}"


@pytest.mark.parametrize("dom,bak", [
    ("Money", "finance"),
    ("Decision Making", "hr-organisatie"),
    ("WIP", "hr-organisatie"),
    ("All governance records of the Circle", "hr-organisatie"),
    ("Stance", "visie-missie-strategie"),
    ("Brand positioning", "visie-missie-strategie"),      # besluit: waar we staan, niet marketing
    ("Position statements", "visie-missie-strategie"),
    ("Materials", "shoe-development"),                    # besluit: materiaalKEUZE, niet inkoop
    ("onderzoeksmethode", "shoe-development"),
    ("Design system", "tech-platform"),                   # besluit: componentlaag, niet merk
    ("Nooch.earth", "tech-platform"),
    ("claims", "compliance-legal"),
    ("claim-verification", "compliance-legal"),
    ("claims-database", "compliance-legal"),
    ("concurrentiebeeld", "sales-marketing"),
    ("Tone of voice", "sales-marketing"),
    ("Copycheck", "sales-marketing"),
    ("bibliotheek", "overig"),                            # besluit: taalbeheer, geen inhoudsdomein
])
def test_de_achttien_domeinen_van_de_echte_data(dom, bak):
    """Deze achttien staan in de productiedata. Verandert er één van bakje, dan is dat een
    besluit en hoort deze toets te vallen."""
    assert domeinen.DOMEIN_BAKJE[dom] == bak


def test_de_tabel_dekt_precies_de_domeinen_die_besloten_zijn():
    assert len(domeinen.DOMEIN_BAKJE) == 18


def test_een_onbekend_domein_belandt_in_overig_en_niet_in_een_gok():
    a = _Nep(domain="Een Gloednieuw Domein")
    bak, _ = domeinen.bakje_van(a, _records())
    assert bak == "overig"


# ── 3. De precedentieregel, stap voor stap ───────────────────────────────────
def test_stap_1_het_eigen_domein_van_een_policy_wint():
    rol = _NepRol("r", domains=["Materials"])
    a = _Nep(anchor="r", domain="Money")
    bak, waarom = domeinen.bakje_van(a, _records(rol))
    assert bak == "finance", "het eigen domein hoort te winnen van dat van de rol"
    assert "Money" in waarom


def test_stap_2_anders_het_domein_van_de_eigenaar_rol():
    rol = _NepRol("r", domains=["concurrentiebeeld"])
    bak, waarom = domeinen.bakje_van(_Nep(anchor="r"), _records(rol))
    assert bak == "sales-marketing"
    assert "concurrentiebeeld" in waarom


def test_stap_3_anders_de_rol_zelf():
    """Alleen voor rollen ZONDER domein. Op prod zijn dat er drie met pagina's."""
    rol = _NepRol("mother_earth__nooch__financial_controller")
    bak, waarom = domeinen.bakje_van(_Nep(anchor=rol.id), _records(rol))
    assert bak == "finance"
    assert "rol" in waarom.lower()


def test_stap_4_anders_de_omvattende_cirkel():
    cirkel = _NepRol("c", domains=["Money"], circle=True)
    rol = _NepRol("c__onbekend", parent="c")
    bak, waarom = domeinen.bakje_van(_Nep(anchor=rol.id), _records(cirkel, rol))
    assert bak == "finance"
    assert "cirkel" in waarom.lower()


def test_zonder_iets_bruikbaars_is_het_overig():
    bak, _ = domeinen.bakje_van(_Nep(anchor="nergens"), _records())
    assert bak == "overig"


# ── 4. De override (variant C) ───────────────────────────────────────────────
def test_een_override_wint_van_alles():
    """DE ENIGE OPGESLAGEN WAARDE. Drie van de 121 pagina's op prod hebben hem nodig, en alle
    drie omdat hun inhoud iets anders zegt dan hun domein."""
    rol = _NepRol("r", domains=["concurrentiebeeld"])
    a = _Nep(anchor="r", domain="Money", meta={"domein": "hr-organisatie"})
    bak, waarom = domeinen.bakje_van(a, _records(rol))
    assert bak == "hr-organisatie"
    assert "override" in waarom.lower()


def test_de_override_leeft_in_meta_en_niet_in_domain():
    """`domain` betekent "het governance-domein waar dit bij hoort". Zou de override daar landen,
    dan staan er twee soorten waarden in één veld — `Money` naast `sales-marketing` — en dat is
    precies het patroon dat in dit project al drie keer uiteen is gelopen."""
    import inspect
    bron = inspect.getsource(domeinen)
    assert 'meta' in bron and '"domein"' in bron


def test_een_override_naar_een_onbekend_bakje_wordt_genegeerd():
    """Fail-closed: een sleutel die niet bestaat mag de pagina niet uit de structuur tillen."""
    rol = _NepRol("r", domains=["concurrentiebeeld"])
    a = _Nep(anchor="r", meta={"domein": "bestaat-niet"})
    bak, _ = domeinen.bakje_van(a, _records(rol))
    assert bak == "sales-marketing", "een kapotte override hoort te worden overgeslagen"


# ── 5. Botsende domeinen op één rol ──────────────────────────────────────────
def test_twee_roldomeinen_in_hetzelfde_bakje_botsen_niet():
    rol = _NepRol("r", domains=["claims", "claims-database"])
    bak, _ = domeinen.bakje_van(_Nep(anchor="r"), _records(rol))
    assert bak == "compliance-legal"


def test_twee_roldomeinen_in_verschillende_bakjes_vragen_om_een_mens():
    """GEEN GENERIEKE REGEL (besluit Stefan). Op prod gebeurt dit bij twee rollen en drie
    pagina's, en in alle drie de gevallen zei de INHOUD iets anders dan allebei de domeinen —
    "How we decide here" hoort bij besluitvorming, niet bij taalbeheer of bio-materialen. Een
    automatische keuze zou daar stilletjes het verkeerde antwoord geven; dit is het signaal dat
    er een override hoort te komen."""
    rol = _NepRol("r", domains=["bibliotheek", "onderzoeksmethode"])
    bak, waarom = domeinen.bakje_van(_Nep(anchor="r"), _records(rol))
    assert bak == "overig"
    assert "botsen" in waarom.lower()
    assert "bibliotheek" in waarom and "onderzoeksmethode" in waarom


# ── 6. De tabel is de enige bron ─────────────────────────────────────────────
def test_er_staat_geen_tweede_bakjeslijst_in_de_views():
    """De index, de pagina en de backfill lezen allemaal hieruit. Een tweede lijst zou precies de
    fout herhalen die `_CORE_ROLE_NAMES` naast `_is_core_role` al maakt."""
    import pathlib
    wortel = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"
    for pad in (wortel / "views" / "wiki.py", wortel / "cockpit2.py"):
        bron = pad.read_text()
        assert "shoe-development" not in bron, f"{pad.name} draagt een eigen bakjeslijst"
