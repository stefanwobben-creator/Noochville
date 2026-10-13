# Backlog: privé-projecten (geparkeerd 11 oktober 2026)

**Besluit Stefan, 11 oktober 2026:** privé-projecten zijn voorlopig geparkeerd. De optie "Only for
this circle" is nooit gebruikt (0 van 458 projecten). De server weigert de vlag bij aanmaken en zetten
(`cockpit2.PRIVE_UIT`), ook bij een handmatig POST-verzoek; het vinkje in het werkoverleg en de knop in
de projectrail zijn weg.

**Wat blijft staan:** de leesregels uit #726 (`views/messages.py`: `mag_project_lezen`,
`mag_project_dict_lezen`, `project_lezer`), de guard `tests/test_prive_projecten_guard.py` en de
datavlag `private` op een project. Terugzetten = `PRIVE_UIT` weghalen en de twee UI-plekken herstellen.

## De vijf open punten (de tweede PR, vervallen)

Besluiten van 11 oktober, uitgewerkt en getest maar niet gepusht. Het werk staat ALLEEN LOKAAL op
Stefans Mac (niet in git): als patch `claude/backlog_prive_projecten_2_werk_11okt.patch` en als
`git stash` ("prive-projecten-2 (vervallen 11 okt …)"), 10 bestanden met tests per punt met een lid en
een niet-lid. Bij het parkeren faalde nog één toets, de taal-ratchet: eerst die oplossen.

1. **Noochie-memo**: privé-projecten nooit in de memo, ook niet als activiteit per rol (de memo is niet
   per gebruiker).
2. **Daemon-meldingen** over een privé-project alleen naar leden van de cirkel: `naar_mens` (vastgelopen
   stappen) geeft geen melding en geen terugval als de ontvanger geen lid is; weesprojecten staan zonder
   titel in de human inbox; een privé-wees wordt niet automatisch herrouteerd. Helpers
   `rol_mag_project_lezen` en `ontvanger_mag_project_lezen`.
3. **`conclusie_naar_wiki`** weigert een privé-project met een duidelijke melding.
4. **Door mensen geschreven berichten**: niets doen. Systeemberichten met een titel vallen onder 2.
5. **`weten_we_dit_al`** vergelijkt alleen met projecten die de vragende rol mag lezen
   (`draaistaat.huidige_aanroeper`).

Daarna: de guard-lijst zonder OPEN-regels, met een toets die dat zo houdt.

## Bij terugkeer van privéprojecten bewust beslissen

- **Goals-voortgang op /goals en /today telt privéprojecten mee** (13 oktober 2026). `doelen.voortgang`
  rekent elk project van een doel mee, ook een privé-project; er worden geen titels getoond (staat zo op
  de privé-guardlijst: `views/doelen.py:render_goals`, `views/today.py:_doelen`). Bij terugkeer van
  privéprojecten bewust beslissen of de voortgang dan per kijker moet verschillen.

## Bijvangst

De weesprojecten-melding in de human inbox leest `p.get("title")`, maar projecten hebben `scope`, geen
`title`: er staat nu het project-id in plaats van de titel. Los van privé; een kleine fix.
