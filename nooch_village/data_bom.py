"""De materiaal-compositie (BOM) van de Nooch-schoen, aangeleverd door de founder.

Dit is de DOMEIN-input voor de belofte-graaf: waar de schoen fysiek van gemaakt is. De
belofte-graaf zelf kent deze data niet; compositie.ontleed_bom zet 'm om in constituenten
en de BelofteStore bewaart de groeiende graaf. Voor een ander product of een dienst komt
de snede uit een andere bron; alleen deze constante is schoen-specifiek.
"""
from __future__ import annotations

SCHOEN_BELOFTE_ID = "nooch_schoen_duurzaam"
SCHOEN_BELOFTE = "De Nooch-schoen is volledig duurzaam en vegan te maken."

# Bill of Materials, tab-gescheiden (Legenda-kolom · Part · Material · Comment · Weight (g)).
# 'Or ...' in het commentaar zijn kandidaat-alternatieven; vrije opmerkingen zijn checks.
#
# WEIGHT (1 oktober 2026, BOM-scherm). Gram per component. LEEG TOT DE FOUNDER HEM INVULT, en dat is bewust: het prototype had
# illustratieve cijfers, en een verzonnen gewicht dat er echt uitziet is erger dan een leeg vak —
# het BOM-scherm toont een leeg vak als "nog open". De kolommen worden op KOPNAAM gelezen
# (`compositie._kolommen`), dus de volgorde hier mag veranderen zonder dat de parser meebuigt.
# DE LEVERANCIER STAAT HIER NIET (meer). Hij stond hier als `Supplier`-kolom en is op 2 oktober 2026
# verhuisd naar een bewerkbare store per materiaal (`bom_leveranciers.py`, te zetten op `/bom`):
# een hardcoded bron die alleen met een code-aanpassing verandert, is geen plek voor een koppeling
# die een mens beheert.
NOOCH_SCHOEN_BOM = (
    "Legenda\t\tPart\tMaterial\tComment\tWeight (g)\n"
    "Done\t\tOutsole\tPliant\t\t\n"
    "Please check\t\tToeguard\tHyphaLite\t\t\n"
    "Please fill inn\t\tVamp\tHyphaLite\t< Or hemp fabric, Or organic cotton fabric\t\n"
    "\t\tEyestay\tHyphaLite\t\t\n"
    "\t\tTongue\tHyphaLite\t\t\n"
    "\t\tHeel counter\tHyphaLite\t\t\n"
    "\t\tHeel tab\tHyphaLite\t\t\n"
    "\t\tSide logo arch\tHyphaLite\t\t\n"
    "\t\tPadding\tLTA - Jersey-CO Gea Flex 1003 mm 6.0\t\t\n"
    "\t\tInternal heel counter\tHelios Yellow Line\t\t\n"
    "\t\tInternal toe guard\tBIOREL\t\t\n"
    "\t\tStrobel sock/(Baseboard)\tFull Green FG S20\t\t\n"
    "\t\tInsole\tJersey Co - Gea Flex mm 8.0\t\t\n"
    "\t\tLining\tHyphalite Lining\t< Or organic cotton\t\n"
    "\t\tLaces\tOrganic cotton laces\t\t\n"
    "\t\tTongue label\tOrganic Cotton Tape\t\t\n"
    "\t\tOutsole stitch\tCotton thread\t< Might be linen thread, please check.\t\n"
    "\t\tUpper stitch\tCotton thread\t\t\n"
    "\t\tInk / print\tVegan Soy Based Ink\t\t\n"
    "\t\tGlue / cement\tWaterbased Latex based Glue\t\t\n"
    "\t\tLace tips\tCellulose Film\t\t\n"
    "\t\tEyestay Reinforcement\tBIOREL (?)\t\t\n"
    "\t\tHeel Embroidery\tCotton Thread\t\t\n"
)


# MODELLEN (BOM Stuk 4, 2 oktober 2026). Een model is een schoen met één MASTER-stuklijst; varianten
# (kleur) zijn afwijkingen daarop en wonen niet hier maar in `bom_varianten` (welke er
# bestaan) en `bom_materialen` (wat ze anders doen). De sleutel is een slug in Shopify-stijl; de naam
# is wat het scherm toont. Een tweede model krijgt hier zijn eigen regel en zijn eigen stuklijst.
#
# GEEN WIKI-PAGINATYPE VOOR EEN SCHOEN (besluit Stefan): `/bom` is de schoenpagina. Een tweede plek
# met dezelfde informatie zou uit de pas gaan lopen.
#
# TWEE MODELLEN, NIET ÉÉN MET HOOGTE ALS VARIANT (besluit Stefan, 2 oktober 2026). "269 Hi" en
# "269 Lo" zijn elk een model met een eigen basislijst; hun KLEUREN zijn de varianten (5 onder Hi,
# 10 onder Lo). Zo heeft elk model — ook een toekomstige Runner of Barefoot — dezelfde diepte:
# model → kleurvariant, zonder uitzondering voor de '269.
#
# DE STUKLIJST HIERBOVEN IS 269 LO. 269 Hi heeft nog geen eigen lijst; hij BEGINT bij dezelfde
# (een verwijzing, geen kopie — `basis_van` zegt het erbij) en zijn afwijkingen (de Hemp-upper,
# andere gewichten) staan als model-afwijkingen op `/bom`. Komt er een echte Hi-lijst, dan krijgt
# hij hier zijn eigen constante en vervalt `basis_van`.
STANDAARD_MODEL = "269-lo"
MODELLEN = {
    "269-lo": {"naam": "269 Lo", "master": NOOCH_SCHOEN_BOM},
    "269-hi": {"naam": "269 Hi", "master": NOOCH_SCHOEN_BOM, "basis_van": "269-lo"},
}

#: De maat waarop de gewichten in een stuklijst gelden (EU, industriestandaard). Er wordt NIET
#: geschaald naar andere maten: één percentage per maat klopt niet (lengte, omtrek en hoogte
#: graderen elk anders, per onderdeel). Maatafhankelijk verbruik komt bij de materiaalplanning,
#: per onderdeel — besluit Stefan, 2 oktober 2026.
REFERENTIEMAAT = 42
