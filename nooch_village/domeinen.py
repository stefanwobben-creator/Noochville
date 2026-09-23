"""De domeinstructuur van de wiki: elf vaste bakjes en één classificatietabel.

WAAROM DIT EEN EIGEN MODULE IS. `render_wiki_index` groepeerde al per domein, maar
`Attachment.domain` werd alleen gevuld voor policies: 110 van de 121 artefacten op prod hadden er
geen en vielen samen in één "No domain yet"-bak. De structuur bestond op het scherm, niet in de
data. Wat hier staat is de ontbrekende helft, en hij staat op ÉÉN plek omdat de index, de pagina
en het backfill-commando hem alle drie lezen.

WAT DE VORM BEPAALDE, gemeten op de echte productiedata en niet bedacht:

  Afleiden uit de ROL werkt niet. `mother_earth__nooch` is de hele onderneming, dus zijn purpose
  is de missie en zijn bakje wordt "Visie". Elke rol eronder zou dat erven — inclusief
  `creator_of_shoes` met zijn veertien materiaalnotities. Doorgerekend gaf die regel voor vier
  van de acht twijfelgevallen een slechter antwoord dan geen regel.

  Afleiden uit het DOMEIN werkt wel. De vier policies van diezelfde cirkel dragen `Money`,
  `Decision Making`, `WIP` en `Stance`, en landen daarmee vanzelf in drie verschillende bakjes.
  Dat is precies wat één bakje per rol niet kan, en het is de reden dat de tabel hieronder over
  domeinen gaat en niet over rollen.

AFLEIDEN, NIET OPSLAAN. Het bakje wordt bij het LEZEN bepaald en nergens bewaard — dezelfde regel
als bij `wiki.grond_status`: een vergelijking, geen stempel. Verandert een classificatie, dan
verschuiven alle pagina's mee zonder migratie en zonder dat er ergens een verouderde kopie
achterblijft. Alleen een handmatige verplaatsing wordt opgeslagen, en dat blijkt zeldzaam: drie
van de 121 pagina's.

DIE OVERRIDE LEEFT IN `meta` EN NIET IN `domain`. Het veld `domain` betekent "het
governance-domein waar dit bij hoort" en die betekenis blijft één ding. Zou de override daar
landen, dan stond er na verloop van tijd een mengsel van governance-domeinen (`Money`) en
bakje-sleutels (`sales-marketing`) in hetzelfde veld — het patroon dat in dit project al eerder
uiteen is gelopen. `meta` is bovendien waar de feiten ook wonen, dus het reist mee in versies,
erven en `/context`.
"""
from __future__ import annotations

#: De elf bakjes, sleutel → weergavenaam, IN KETENVOLGORDE. De volgorde is inhoudelijk: de
#: zijbalk leest van product naar klant en daarna de ondersteunende functies. Daarom geen
#: alfabetische sortering, en daarom staat `overig` achteraan — een restbak hoort nooit bovenaan.
BAKJES: tuple[tuple[str, str], ...] = (
    ("shoe-development",       "Shoe development"),
    ("sourcing-productie",     "Sourcing & productie"),
    ("fulfillment",            "Fulfillment"),
    ("sales-marketing",        "Sales & marketing"),
    ("service",                "Service"),
    ("finance",                "Finance"),
    ("hr-organisatie",         "HR & organisatie"),
    ("compliance-legal",       "Compliance & legal"),
    ("visie-missie-strategie", "Visie, missie, strategie & waarden"),
    ("tech-platform",          "Tech & platform"),
    ("overig",                 "Overig"),
)

_LABELS = dict(BAKJES)
OVERIG = "overig"

#: De achttien domeinen die in de productiedata voorkomen, elk in precies één bakje. Waar het
#: besluit tegen de eerste intuïtie inging staat de reden erbij — anders draait iemand het terug.
DOMEIN_BAKJE: dict[str, str] = {
    # ── werkproces en governance ──
    "Decision Making":                      "hr-organisatie",
    "WIP":                                  "hr-organisatie",
    "All governance records of the Circle":  "hr-organisatie",
    # ── geld ──
    "Money":                                "finance",
    # ── waar het merk staat ──
    "Stance":                               "visie-missie-strategie",
    "Position statements":                  "visie-missie-strategie",
    # NIET sales-marketing: merkpositionering gaat over waar we staan, zelfde categorie als
    # Stance. Uitdragen is marketing, vastleggen niet.
    "Brand positioning":                    "visie-missie-strategie",
    # ── product ──
    # NIET sourcing: `Materials` gaat over materiaalKEUZE en -kennis voor productontwikkeling.
    # Sourcing & productie is "bij wie kopen we in, hoe produceren we".
    "Materials":                            "shoe-development",
    # De methode zelf is geen ketenstap; de inhoud (bio-materialen, patenten) dient wél het
    # ontwikkelen van producten.
    "onderzoeksmethode":                    "shoe-development",
    # ── platform ──
    "Nooch.earth":                          "tech-platform",
    # NIET merkidentiteit: het designsysteem is de componentlaag van de website.
    "Design system":                        "tech-platform",
    # ── claims ──
    "claims":                               "compliance-legal",
    "claim-verification":                   "compliance-legal",
    "claims-database":                      "compliance-legal",
    # ── markt en taal ──
    "concurrentiebeeld":                    "sales-marketing",
    "Tone of voice":                        "sales-marketing",
    "Copycheck":                            "sales-marketing",
    # Taalbeheer/infrastructuur, geen inhoudsdomein — vandaar de restbak en niet content.
    "bibliotheek":                          OVERIG,
}

#: Stap 3 van de regel, en met opzet KORT. Alleen rollen zonder eigen domein die artefacten
#: dragen; al het andere hoort via zijn domein te lopen. Groeit deze tabel, dan is dat een
#: signaal dat er domeinen ontbreken in governance, niet dat hier een regel bij moet.
ROL_BAKJE: dict[str, str] = {
    "mother_earth__nooch__financial_controller":     "finance",
    "mother_earth__nooch__supply_chain_coordinator": "sourcing-productie",
    "mother_earth__nooch__noochville__copywriter":   "sales-marketing",
}


def label(sleutel: str) -> str:
    """De weergavenaam. Een onbekende sleutel leest als Overig in plaats van als een lege kop."""
    return _LABELS.get(sleutel, _LABELS[OVERIG])


def bakjes_in_volgorde() -> list[tuple[str, str]]:
    """De bakjes zoals ze op het scherm horen te staan."""
    return list(BAKJES)


def _is_cirkel(rec) -> bool:
    from nooch_village import org
    return org.is_circle(rec)


def _domeinen_van(rec) -> list[str]:
    definitie = getattr(rec, "definition", None)
    return [d for d in (getattr(definitie, "domains", None) or []) if str(d).strip()]


def bakje_van(artefact, records) -> tuple[str, str]:
    """Het bakje van dit artefact, plus in één zin waaróm — die zin is voor het scherm en voor
    het backfill-commando, zodat een indeling navolgbaar is en niet uit de lucht komt.

    De precedentieregel, van specifiek naar algemeen; de eerste die iets oplevert wint:

        0. een handmatige override op de pagina zelf (`meta["domein"]`)
        1. het eigen `domain` van het artefact (policies dragen dat)
        2. het domein van de eigenaar-rol
        3. de rol zelf
        4. het bakje van de omvattende cirkel

    Botsen twee roldomeinen over verschillende bakjes, dan kiest deze functie BEWUST NIET. Op
    prod gebeurt dat bij drie pagina's, en in alle drie de gevallen zei de inhoud iets anders dan
    allebei de domeinen — "How we decide here" hoort bij besluitvorming, niet bij taalbeheer of
    bio-materialen. Een automatische keuze zou daar stil het verkeerde antwoord geven. Overig mét
    de reden is dan eerlijker: het is het signaal dat er een override hoort te komen.
    """
    # 0. override
    meta = getattr(artefact, "meta", None) or {}
    keuze = str(meta.get("domein") or "").strip()
    if keuze:
        if keuze in _LABELS:
            return keuze, f"override op de pagina ({label(keuze)})"
        # Fail-closed: een sleutel die niet bestaat mag de pagina niet uit de structuur tillen.

    # 1. het eigen domein
    eigen = str(getattr(artefact, "domain", "") or "").strip()
    if eigen:
        if eigen in DOMEIN_BAKJE:
            return DOMEIN_BAKJE[eigen], f"eigen domein {eigen!r}"
        return OVERIG, f"eigen domein {eigen!r} staat niet in de tabel"

    anchor = str(getattr(artefact, "anchor", "") or "")
    byid = {r.id: r for r in records}
    rec = byid.get(anchor)

    # 2. het domein van de eigenaar-rol
    if rec is not None:
        doms = _domeinen_van(rec)
        bekend = [d for d in doms if d in DOMEIN_BAKJE]
        bakjes = {DOMEIN_BAKJE[d] for d in bekend}
        if len(bakjes) == 1:
            return bakjes.pop(), f"domein van de rol ({', '.join(bekend)})"
        if len(bakjes) > 1:
            return OVERIG, (f"de domeinen van de rol botsen ({', '.join(sorted(bekend))}) — "
                            f"dit vraagt een override")

    # 3. de rol zelf
    if anchor in ROL_BAKJE:
        return ROL_BAKJE[anchor], "de rol zelf (heeft geen domein)"

    # 4. de omvattende cirkel
    huidig = rec
    while huidig is not None:
        ouder = byid.get(str(getattr(huidig, "parent", "") or ""))
        if ouder is None:
            break
        if _is_cirkel(ouder):
            for d in _domeinen_van(ouder):
                if d in DOMEIN_BAKJE:
                    return DOMEIN_BAKJE[d], f"domein van de cirkel {ouder.id} ({d})"
            if ouder.id in ROL_BAKJE:
                return ROL_BAKJE[ouder.id], f"de cirkel {ouder.id}"
            break
        huidig = ouder

    return OVERIG, "geen domein, geen rol-indeling en geen cirkel die uitsluitsel geeft"
