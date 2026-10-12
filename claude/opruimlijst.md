# Opruimlijst

Kleine dingen die bij het werk boven kwamen en een eigen, kleine PR verdienen. Per punt: wat, waar,
en waarom het niet in de PR zat waarin het gevonden werd. Bijgewerkt 12 oktober 2026.

## Open

4. **nginx `upload_size.conf` in de repo.** De effectieve limiet (25 MB) staat alleen op de server:
   `/etc/nginx/conf.d/upload_size.conf` (9 juli). `deploy/nginx.conf` noemt 25M ook, maar wordt niet
   uitgerold en het actieve sitebestand wijkt af (certbot). Fix: het bestand in `deploy/` en een regel
   in de deploy-documentatie. Gevonden bij de kostenimport (Finance PR 3).

5. **Dubbele-factuurregel: waarschuwing in plaats van stil overslaan.** De kostenimport
   (`finance_kosten_import.beoordeel`) zet dezelfde leverancier, datum, totaal en regel als DUBBEL,
   ook bij een ander bestand. Bij de import van 2024 en eerder vielen zo twee echte Venema-facturen weg
   (81190 en 81192, zelfde dag en bedrag als 81191). Fix: bij een ander bestand een WAARSCHUWING (wel
   importeren), met een test op precies dit geval. Gevonden bij de controle van de imports.

## Gedaan

1. **Uitloglink** in het gebruikersblok van de zijbalk — opruim-PR (12 oktober 2026).
2. **`.ovl-x` binnen de eigen overlay** (bord-modal 2×, wizard; het werkoverleg deed het al) — opruim-PR,
   met een lokaas-test per overlay (`tests/test_opruim_1_3.py`).
3. **Weesprojecten-melding toont de titel** (`scope`) in plaats van het id — opruim-PR.
6. **Kaarten verplaatsen op een touchscreen.** Slepen werkt bewust niet op touch (`NV.bord` negeert
   `pointerType === "touch"`: een sleepgebaar zou het scrollen blokkeren). Verplaatsen kan via de kaart
   aantikken → statuskeuze in de rail van het project. Het commentaar in `nooch.js` beweerde nog "de
   knop/dropdown op de kaart zelf"; dat klopt sinds de compacte kaart (B2) niet meer en is bijgewerkt —
   opruim-PR. Open vraag voor later: een snellere statuswissel op touch (bijv. lang indrukken → menu).

## Elders bijgehouden

- Privé-projecten: `claude/backlog_prive_projecten_11okt.md`.
