# CONTEXT.md — productcontext & harde eisen

De "waarom" achter de bouw. Kort houden. Commerciële cijfers (pricing, ARR, DCF, deal-structuur)
horen NIET hier maar in het businessplan; dit bestand bevat alleen wat een bouwkeuze stuurt.

## Wat we bouwen
Een zelfontwikkeld **GlassFrog-alternatief**: Holacracy-governance plus tactical/project-management,
met een betere interface. GlassFrog-pariteit is de norm (de gouden standaard waar we tegen ijken).

## Differentiator
Geïntegreerde **AI-governance en spanningschecks** die cirkels direct tijd besparen. Hier blijven
investeren; dit is waarom een klant overstapt, niet alleen de prijs.

## Fase
Nu: **pilot ("Vliegtest") bij Nooch** (5 gebruikers) als eerste social proof. Daarna commerciële
migratie van bestaande, warme GlassFrog-relaties in West-Europa (NL/BE/DE/UK/FR).

## Harde eisen die er nog NIET zijn (nu is het een PoC)
Voor een echte klant-uitrol moeten deze er komen, in deze volgorde van belang:
- **Multi-tenant + data-isolatie**: meerdere organisaties naast elkaar, strikt gescheiden.
- **Auth / login**: nu draait alles zonder authenticatie op één server.
- **GDPR/AVG-proof hosting**: enterprise-hosting in de EU.

## Schaal
Eén organisatie kan **groot** zijn (een warme relatie telt ~441 gebruikers). Datamodel, queries en
rendering moeten daartegen kunnen; niet ontwerpen alsof een cirkel altijd klein is.

## Grens
`STATE.md` = waar de bouw staat (bouw-geheugen). Dit bestand = waarom + randvoorwaarden.
Houd ze gescheiden: geen commerciële prognoses in de repo, geen bouwstatus hier.
