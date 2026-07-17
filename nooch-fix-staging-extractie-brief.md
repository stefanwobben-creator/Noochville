# Fix-brief: staging-layout kapot + URL/PDF-extractie levert rommel

**Voor:** Claude Code, op de layout-branch (`kennisbank-layout`). De intake + staging zijn gebouwd, maar twee dingen zijn stuk. Getoetst op prod met een Scientias.nl/Guardian-artikel en een Water Research-paper.

## Bug 1 — Staging-layout collapse
**Symptoom:** elke staging-kaart is tot ~1 teken breed geperst (tekst rendert verticaal, letter per regel). Groene bolletjes tussen de kaarten alsof ze in een rij naast elkaar staan. Dropdowns (onderwerp/provenance), "Bewaar" en "×" cascaderen diagonaal over het scherm. Onbruikbaar.
**Vermoedelijke oorzaak:** de staging-lijst is een horizontale flex-rij (of de kaarten hebben geen breedte), en/of tekst-children missen `min-width:0`, waardoor lange onbreekbare strings (URL-slugs) de kaart naar ~0 breedte duwen.
**Fix:**
- De staging is een **verticale stapel** kaarten op volle breedte (`flex-direction:column` of gewoon block; elke kaart `width:100%`).
- Kaart-indeling: checkbox + bewerkbare content (flex:1, `min-width:0`, `overflow-wrap:anywhere`) + bron/reference als één ingekorte regel + onderwerp-dropdown + provenance-dropdown + Bewaar + ×, netjes op één rij binnen de kaart. Geen absolute positionering, geen cascade.
- **Acceptatie:** de staging toont een leesbare verticale lijst; elke kaart volledig leesbaar, controls netjes uitgelijnd.

## Bug 2 — URL/PDF-extractie levert rommel
**Symptoom:** de bron-URL-slug ("voor-het-eerst-echt-aangetoond-ook-op-2000-meter") en complete referentielijsten (Jambeck et al., 2015; Geyer et al., 2020; ...) belanden als content; citatie-smeer per kaart; over-explosie in veel mini-kaartjes.
**Fix:**
- **URL-adapter doet echte hoofdtekst-extractie** (readability-stijl): strip navigatie, footer, gerelateerde-links, de literatuur/referentielijst en auteur-citatieblokken. Neem **geen** URL-slugs of linkteksten als content.
- **PDF idem:** een referentielijst / bibliografie is geen inhoud om te atomiseren; sla 'm over.
- **Bron/DOI hoort één keer in het reference-veld** (addendum B), niet in de content van elke kaart.
- **Atomiciteit-bovengrens** (addendum A) toepassen: een referentie- of citatielijst is geen N atomen. Zet een redelijke cap op atomen per document.
- **Acceptatie:** het microplastics-artikel levert een handvol schone atomen over de bevindingen (geen URL-slugs, geen auteur-citatielijsten), met bron "The Guardian via Scientias.nl" resp. "Water Research 303 (2026)" één keer in reference. Her-uploaden voegt niets dubbels toe.

## Guardrails
Append-only; design system; tests + volle suite groen; applies als user nooch, back-up, dry-run. Blijf op `kennisbank-layout` (dit is een fix op dat werk), aparte commit.
