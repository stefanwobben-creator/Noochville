# Opruimlijst

Kleine dingen die bij het werk boven kwamen en een eigen, kleine PR verdienen. Per punt: wat, waar,
en waarom het niet in de PR zat waarin het gevonden werd. Bijgewerkt 12 oktober 2026.

## Open

1. **Uitloglink in het gebruikersblok van de zijbalk.** De route `/logout` bestaat
   (`cockpit2.py`, `path == "/logout"`), maar er is nergens in de UI een link naar. Plek: onderaan
   de zijbalk bij de initialen (`.c2-av`, `cockpit2_util._nav`). Gevonden bij B1 (#728): de header
   had hem ook niet, dus er was niets te verhuizen.

2. **`.ovl-x`-selectors scopen naar de eigen overlay.** De modal-JS pakt
   `document.querySelector('.ovl-x')` — het EERSTE sluitkruisje in het document — op vier plekken:
   `views/projects.py` (2×), `views/werkoverleg.py`, `views/wizard.py`. Elk element vóór die overlay
   met `.ovl-x` kaapt hun sluitknop. Het palet (B1) draagt die klasse daarom bewust niet
   (`tests/test_b1_palet.py` bewaakt dat). Fix: zoeken binnen de eigen overlay
   (`ovl.querySelector('.ovl-x')`).

3. **Weesprojecten-melding toont het id in plaats van de titel.** `village._meld_weesprojecten` leest
   `p.get("title")`, maar een project heeft `scope`, geen `title`; de human inbox toont dus het
   project-id. Fix: `scope` (zoals `afslank_wezen` al doet). Gevonden bij de privé-projecten-PR.

4. **nginx `upload_size.conf` in de repo.** De effectieve limiet (25 MB) staat alleen op de server:
   `/etc/nginx/conf.d/upload_size.conf` (9 juli). `deploy/nginx.conf` noemt 25M ook, maar wordt niet
   uitgerold en het actieve sitebestand wijkt af (certbot). Fix: het bestand in `deploy/` en een regel
   in de deploy-documentatie. Gevonden bij de kostenimport (Finance PR 3).

5. **Dubbele-factuurregel: waarschuwing in plaats van stil overslaan.** De kostenimport
   (`finance_kosten_import.beoordeel`) zet dezelfde leverancier, datum, totaal en regel als DUBBEL,
   ook bij een ander bestand. Bij de import van 2024 en eerder vielen zo twee echte Venema-facturen weg
   (81190 en 81192, zelfde dag en bedrag als 81191). Fix: bij een ander bestand een WAARSCHUWING (wel
   importeren), met een test op precies dit geval. Gevonden bij de controle van de imports.

## Elders bijgehouden

- Privé-projecten: `claude/backlog_prive_projecten_11okt.md`.
