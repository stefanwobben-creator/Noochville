"""De materiaal-compositie (BOM) van de Nooch-schoen, aangeleverd door de founder.

Dit is de DOMEIN-input voor de belofte-graaf: waar de schoen fysiek van gemaakt is. De
belofte-graaf zelf kent deze data niet; compositie.ontleed_bom zet 'm om in constituenten
en de BelofteStore bewaart de groeiende graaf. Voor een ander product of een dienst komt
de snede uit een andere bron; alleen deze constante is schoen-specifiek.
"""
from __future__ import annotations

SCHOEN_BELOFTE_ID = "nooch_schoen_duurzaam"
SCHOEN_BELOFTE = "De Nooch-schoen is volledig duurzaam en vegan te maken."

# Bill of Materials, tab-gescheiden (Legenda-kolom · Part · Material · Comment).
# 'Or ...' in het commentaar zijn kandidaat-alternatieven; vrije opmerkingen zijn checks.
NOOCH_SCHOEN_BOM = (
    "Legenda\t\tPart\tMaterial\tComment\n"
    "Done\t\tOutsole\tPliant\t\n"
    "Please check\t\tToeguard\tHyphaLite\t\n"
    "Please fill inn\t\tVamp\tHyphaLite\t< Or hemp fabric, Or organic cotton fabric\n"
    "\t\tEyestay\tHyphaLite\t\n"
    "\t\tTongue\tHyphaLite\t\n"
    "\t\tHeel counter\tHyphaLite\t\n"
    "\t\tHeel tab\tHyphaLite\t\n"
    "\t\tSide logo arch\tHyphaLite\t\n"
    "\t\tPadding\tLTA - Jersey-CO Gea Flex 1003 mm 6.0\t\n"
    "\t\tInternal heel counter\tHelios Yellow Line\t\n"
    "\t\tInternal toe guard\tBIOREL\t\n"
    "\t\tStrobel sock/(Baseboard)\tFull Green FG S20\t\n"
    "\t\tInsole\tJersey Co - Gea Flex mm 8.0\t\n"
    "\t\tLining\tHyphalite Lining\t< Or organic cotton\n"
    "\t\tLaces\tOrganic cotton laces\t\n"
    "\t\tTongue label\tOrganic Cotton Tape\t\n"
    "\t\tOutsole stitch\tCotton thread\t< Might be linen thread, please check.\n"
    "\t\tUpper stitch\tCotton thread\t\n"
    "\t\tInk / print\tVegan Soy Based Ink\t\n"
    "\t\tGlue / cement\tWaterbased Latex based Glue\t\n"
    "\t\tLace tips\tCellulose Film\t\n"
    "\t\tEyestay Reinforcement\tBIOREL (?)\t\n"
    "\t\tHeel Embroidery\tCotton Thread\t\n"
)
