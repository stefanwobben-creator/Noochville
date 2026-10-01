"""De materiaal-compositie (BOM) van de Nooch-schoen, aangeleverd door de founder.

Dit is de DOMEIN-input voor de belofte-graaf: waar de schoen fysiek van gemaakt is. De
belofte-graaf zelf kent deze data niet; compositie.ontleed_bom zet 'm om in constituenten
en de BelofteStore bewaart de groeiende graaf. Voor een ander product of een dienst komt
de snede uit een andere bron; alleen deze constante is schoen-specifiek.
"""
from __future__ import annotations

SCHOEN_BELOFTE_ID = "nooch_schoen_duurzaam"
SCHOEN_BELOFTE = "De Nooch-schoen is volledig duurzaam en vegan te maken."

# Bill of Materials, tab-gescheiden (Legenda-kolom · Part · Material · Comment · Weight (g) ·
# Supplier). 'Or ...' in het commentaar zijn kandidaat-alternatieven; vrije opmerkingen zijn checks.
#
# WEIGHT EN SUPPLIER (1 oktober 2026, BOM-scherm). Gram per component en de leverancier waar dit
# onderdeel vandaan komt. LEEG TOT DE FOUNDER ZE INVULT, en dat is bewust: het prototype had
# illustratieve cijfers, en een verzonnen gewicht dat er echt uitziet is erger dan een leeg vak —
# het BOM-scherm toont een leeg vak als "nog open". De kolommen worden op KOPNAAM gelezen
# (`compositie._kolommen`), dus de volgorde hier mag veranderen zonder dat de parser meebuigt.
# Leverancier = de TITEL van zijn wiki-pagina; daar staat de prijs (`prijs_per_kg`).
NOOCH_SCHOEN_BOM = (
    "Legenda\t\tPart\tMaterial\tComment\tWeight (g)\tSupplier\n"
    "Done\t\tOutsole\tPliant\t\t\t\n"
    "Please check\t\tToeguard\tHyphaLite\t\t\t\n"
    "Please fill inn\t\tVamp\tHyphaLite\t< Or hemp fabric, Or organic cotton fabric\t\t\n"
    "\t\tEyestay\tHyphaLite\t\t\t\n"
    "\t\tTongue\tHyphaLite\t\t\t\n"
    "\t\tHeel counter\tHyphaLite\t\t\t\n"
    "\t\tHeel tab\tHyphaLite\t\t\t\n"
    "\t\tSide logo arch\tHyphaLite\t\t\t\n"
    "\t\tPadding\tLTA - Jersey-CO Gea Flex 1003 mm 6.0\t\t\t\n"
    "\t\tInternal heel counter\tHelios Yellow Line\t\t\t\n"
    "\t\tInternal toe guard\tBIOREL\t\t\t\n"
    "\t\tStrobel sock/(Baseboard)\tFull Green FG S20\t\t\t\n"
    "\t\tInsole\tJersey Co - Gea Flex mm 8.0\t\t\t\n"
    "\t\tLining\tHyphalite Lining\t< Or organic cotton\t\t\n"
    "\t\tLaces\tOrganic cotton laces\t\t\t\n"
    "\t\tTongue label\tOrganic Cotton Tape\t\t\t\n"
    "\t\tOutsole stitch\tCotton thread\t< Might be linen thread, please check.\t\t\n"
    "\t\tUpper stitch\tCotton thread\t\t\t\n"
    "\t\tInk / print\tVegan Soy Based Ink\t\t\t\n"
    "\t\tGlue / cement\tWaterbased Latex based Glue\t\t\t\n"
    "\t\tLace tips\tCellulose Film\t\t\t\n"
    "\t\tEyestay Reinforcement\tBIOREL (?)\t\t\t\n"
    "\t\tHeel Embroidery\tCotton Thread\t\t\t\n"
)
