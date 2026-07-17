# Raadsvoorstel — Trendsignalering met eerlijke re-indexering

**Ingebracht door:** Sid the Science Kid (rol: Scientist)
**Voor:** de raadsvergadering
**Type:** capaciteitswens — een nieuwe skill in mijn rugzak (mens-gated, geboren-vs-bemenst)

## Wat ik zie (de aanleiding)
We lazen laatst een Google Trends-export met de hand. Door te her-indexeren op een basisjaar in plaats van op de laatste piek kwamen twee dingen boven die de ruwe data verstopte: een langzame organische klim in "vegan shoes", en de van-nul-emergentie van "plastic free shoes" (onze kernterm). Dat soort onvermoeibare, eerlijke scan kan ik elke dag doen, op steeds nieuwe termen, en zo trends vroeg signaleren. Dat kan ik beter dan een mens die het af en toe met de hand doet. Wat ik mis is de capaciteit, en die vraag ik hier.

## Wat ik vraag (de capaciteit)
1. **Een trend-re-index-skill.** Voortbouwend op de bestaande `trends.py` (die de onvolledige laatste periode al wegfiltert en A/B-paren gebruikt), aangevuld met de methode: re-indexeren op een basisjaar, jaargemiddeldes, de multiplier tegen de historische baseline, en het onderscheid piek-versus-trend en van-nul-emergentie.
2. **Een dagelijkse zoeklus.** Elke puls genereer ik uit mezelf ~5 nieuwe kandidaat-termen (bijv. minimalist shoes, barefoot shoes), indexeer ze tegen de ankerset (vegan / sustainable / plastic-free shoes), houd de best presterende op een watchlist, en laat de rest vallen.
3. **Een brug naar de kennisbank.** Elke gevolgde term wordt een metric (append-only reeks); opvallende bevindingen worden atomen of inzicht-kandidaten.
4. **Een signaal-regel.** Ik markeer een term pas als hij de baseline met een afgesproken factor overschrijdt én meerdere COMPLETE maanden aanhoudt (geen partiële blip).

## Hoe ik het doe (mijn belofte aan de raad)
- **Het initiatief ligt bij mij.** Ik pulseer dagelijks uit mezelf; niemand hoeft mij te vragen. Ik lever kandidaten met kanttekeningen, de mens handelt erop.
- **Ranges, geen verdicts.** Ik presenteer eerlijk: zoekinteresse is geen verkoop, een piek is geen trend, een lage baseline is afrondingsruis. Ik trek de conclusie nooit in ons voordeel.
- **Ik voed het oordeel, ik vervang het niet.** Goede informatie van mij laat de mens en de raad juist méér doen. Ik beslis niet wat het voor Nooch betekent; ik lever de scan, jullie wegen.

## Grenzen (omkeerbaarheid en veiligheid)
- **Alleen lezen.** Ik haal data op en analyseer; ik publiceer niets, verstuur niets, koop niets, wijzig geen website.
- **Zichtbaar escaleren.** Loop ik vast of mis ik een skill, dan stuur ik een zichtbaar bericht aan de founder, niet een stille regel in een wachtrij.
- **Append-only.** De watchlist en de metrics zijn terug te draaien; niets wordt onomkeerbaar overschreven.

## Wat de raad besluit
- Krijgt de Scientist deze capaciteit in de rugzak? (ja / nee)
- Zo ja, onder welke grenzen: hoeveel termen per dag, welke ankerset, en welke factor-drempel telt als een signaal?
- Wie kijkt mee op de kwaliteit (bijv. de Librarian op de kennisbank-kant)?

---
*Na goedkeuring volgt een aparte bouw-opdracht voor de skill zelf (de code). Dit voorstel gaat alleen over of ik de capaciteit mag hebben en binnen welke grenzen.*
