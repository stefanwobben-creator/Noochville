# UX-patronen — het contract voor cockpit 2

Eén bron voor de interactie-principes, naast het design system (tokens/atomen). Net als de
token-poort: schending = STOP en eerst hier vastleggen. Elke nieuwe of gewijzigde view moet deze
patronen volgen, zodat alle schermen consistent aanvoelen. Onderbouwd met Nielsen's 10 heuristieken
en gedragspsychologie (Fitts, Hick, affordance, Gestalt, persuasion, von Restorff, peak-end).

## 1. Destructief scheiden van frequent (Fitts + Gestalt similarity + error prevention)
- Een verwijder-/wis-actie staat NOOIT pal naast een veelgebruikte actie, en draagt nooit een
  glyph die op een naburige actie lijkt (geen ✗ "geen check" naast ✕ "verwijderen").
- Destructief = `.dellink` of `.btn no`, visueel apart gezet (`.row-danger`-gap rechts), niet
  tussen de primaire acties.
- Toegepast: checklist-regel (rapporteer-✓/✗ los van verwijder-✕).

## 2. Onomkeerbare/finale acties: bevestigen + eigen gewicht (error prevention)
- Elke onomkeerbare of finale actie krijgt `data-confirm="<vraag>"`. Een globale handler
  (Noochie-chrome) onderschept de submit en vraagt bevestiging.
- Toegepast: "Sluit overleg" (werkoverleg verwerken + sluiten), project verwijderen.

## 3. Voortgang tonen (visibility of system status)
- Meerstaps-flows tonen welke stappen af zijn (✓), welke huidig is, welke nog komen.
- Toegepast: werkoverleg-stapnav (bezochte stappen krijgen ✓).

## 4. Lezen versus bewerken scheiden (aesthetic-minimalist)
- In een overleg-ronde is lezen/afvinken primair; bewerk-affordances (toevoegen, ✕) zijn secundair
  en mogen niet concurreren met de hoofdtaak. Herhaalde uitleg-paragrafen weglaten in-context.
- Richtlijn: per scherm één duidelijke primaire actie.

## 5. Progressive disclosure bij meerdere keuzes (Hick's law)
- Toon niet alle invoervelden van alle opties tegelijk. Kies eerst het type, toon dan het veld.
- Toegepast: spanning-triage (info / project / roloverleg / niet nodig als uitklap-opties).

## 6. Gelijkwaardige keuzes tenzij bewust gestuurd (persuasion / anchoring)
- Geef opties geen primary-kleur als je niet bewust naar die keuze wilt sturen. Triage-uitkomsten
  zijn neutraal; alleen een bewust gewenste default mag groen zijn.

## 7. Leeg ≠ nul (visibility / match real world)
- Een waarde van 0 wordt anders getoond dan "geen data". `_num`/`_render_form`: None → "geen data"
  (gedimd), 0 → "0".
- Bij een vorm/dimensie-mismatch valt de render terug op een zinnige vorm i.p.v. "geen data".

## 8. Bevestiging van autosave (visibility)
- Velden die direct opslaan (onchange) geven een korte terugkoppeling (msg-banner of toast),
  zodat de mens weet dat het bewaard is.

## 9. Accelerators + bulk voor het normale geval (flexibility/efficiency)
- Veelvoorkomende batch-acties krijgen een snelkoppeling. Toetsenbordnavigatie heeft een zichtbare
  selectie.
- Toegepast: check-in "Allen aanwezig"; ↑/↓ + v/x met zichtbare rij-selectie.

## 10. Snelle invoer i.p.v. trage dropdowns (Fitts + visibility)
- Een korte schaal (0-10) is een segmented control, geen dropdown: sneller én toont de verdeling.
  Lopend gemiddelde direct zichtbaar (feedback).
- Toegepast: check-out.

## 11. Eén patroon per taak (consistency & standards)
- Dezelfde taak heeft overal dezelfde UI. Geen tweede manier om hetzelfde te doen.
- Aandachtspunt: project toevoegen (inline quickadd vs modal) → naar één patroon brengen.

## 12. Oriëntatie behouden in modals (visibility / user control)
- Een actie binnen een modal mag de gebruiker niet stuurloos naar een ander scherm gooien;
  bied altijd een weg terug naar de plek waar men was.

## 13. Taal: mens, geen jargon (match real world, NL)
- Geen systeem-placeholders in de UI ("n.t.b. (uit secretaris-note)"), geen losse Engelse term
  waar NL helderder is ("Nevermind" → "Niet nodig").

## 14. Context-anker + voorvullen (recognition over recall)
- Toon waar de gebruiker mee bezig is bovenaan (bijv. de spanning-titel), en vul voor de hand
  liggende waarden voor (de indiener als "rol die voelt").
