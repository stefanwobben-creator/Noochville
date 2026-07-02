# Shopify-context — winkel footwear-nooch.myshopify.com

Snapshot van de productcatalogus (44 producten), zodat het dorp weet wat er écht live staat.
Operationele context; de cijfers verschuiven, de structuur en de les niet.

## Kernbevinding (belangrijk)
De storefront toont in de praktijk **één** verkoopbare schoen. Van de hele catalogus is maar één
echt product Active (THE '269' GRIZZLY BEAR); vrijwel de hele '269'-lijn staat op **Draft** en de
rest is **Archived**. Draft = niet gepubliceerd op het Online Store-kanaal, dus het thema én Google
zien het niet. Dit verklaart de dode product/collectiepagina's (1-2 bezoekers) en de ~0 organische
zichtbaarheid: er valt weinig te vinden omdat er weinig gepubliceerd is.

Consequentie voor project 1 (SEO op productpagina's): **eerst publiceren, dan optimaliseren.** Je
kunt geen pagina's laten ranken die niet live staan.

## Statusverdeling (globaal)
- **Active (~1 echt):** THE '269' GRIZZLY BEAR. (Plus "Test attributie", een testproduct.)
- **Draft (~19):** alle andere '269'-colorways en -hoogtes: SPRING BLOOM, BLUE WHALE, HONEY DEW,
  RED ROBIN, TREE HUGGER, HI NATURAL, MONO DARK/LIGHT, HI MONO DARK/LIGHT, HI BLACK, HI OFF WHITE,
  BLACK, OFF WHITE, Free Scanning '269', en de oude "SOLD OUT!"-varianten (BLACK/WHITE, hi).
- **Archived (~23):** legacy-merch en tests — tees ("VOTE WITH YOUR FEET", "PLANT BASED BADASS",
  "LEATHER IS FOR LOSERS", "WEARING ANIMALS IS WEIRD"), totes, laces, gift cards, donations
  (€10 NO SWEAT, DONATE., Carbon Killer), pick-up/club-tickets, en testproducten (TEST PAYMENT,
  TEST PRODUCT, The '269' (Copy), Drinks with Lotte).

## Model-nuance (geen bug)
- **Made-to-order:** negatieve voorraad (bijv. -286 in stock) is normaal. Productieorder = pre-order,
  geen voorraadgok. Negatief = backorder/pre-sale, past bij het batch-model (start bij 500 orders).
- **Kernproduct = THE '269'**, één schoen in veel colorways en twee hoogtes (low/hi).

## Herkomst
Handmatige export uit Shopify Admin (productenlijst, 44 items). Nog niet via een skill ingelezen;
een leesbron toevoegen (zoals `shopify_sales` de API leest) is de logische vervolgstap zodat een
inwoner deze context automatisch kent.
