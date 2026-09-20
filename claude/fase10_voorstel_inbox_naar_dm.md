# Herzien voorstel — de inbox wordt DM, en de verwerkingsstate vervalt

**Datum:** 20 september 2026 · **Status:** voorstel, niets gebouwd, niets gedeployed
**Aanleiding:** Stefan — *"alles wat tot dusver in de inbox is gekomen kon ik niet echt veel mee,
dus dat werkte sowieso niet, dus ook niet om te houden — als er iets gesignaleerd is kan het gewoon
naar een DM en dan is de mens verantwoordelijk."* Dit trekt de eerdere harde eis op het bewaren van
de verwerkingsstate in, en daarmee vervalt `role:<record_id>`.

---

## 1. Drie cijfers uit je opdracht kloppen niet

Alle drie gemeten op prod vanmorgen, en alle drie veranderen ze een routeringsregel.

### a. "33 rijen met entry_id (@-vermeldingen)"

Dat zijn twee verschillende verzamelingen die elkaar nauwelijks raken:

| | aantal |
|---|---:|
| persoon-gerichte rijen | **33** — waarvan er **3** een `entry_id` dragen |
| rijen mét `entry_id` | **24** — waarvan er **21 rol-gericht** zijn |

Routeren op `entry_id` levert dus een heel andere verdeling dan je bedoelde.
**Voorstel: `target_type` beslist.** Is het doel een persoon → DM naar die persoon (33 rijen, alle
drie de doelen bestaan nog: Stefan, Wytse, Lotte). Is het doel een rol → de regel voor de 338.
`entry_id` doet niet mee aan routering.

### b. "de vijf gearchiveerde rollen → DM naar Stefan, voor alle rijen van die rol"

Die vijf dragen samen **19 rijen**, niet meer — alle rijen op die rollen zijn toevallig ook de
open rijen:

```
librarian 8 · harry_hemp 5 · copywriter 2 · compliance 2 · concurrent_scout 2
```

Maar er zijn **twee andere gearchiveerde rollen** die je niet noemde, en die samen **85 rijen**
dragen — ruim vier keer zoveel:

| rol | rijen | staat | mens-vervuller |
|---|---:|---|---|
| `mother_earth__nooch__noochville__circle_lead` | 49 | gearchiveerd | **Stefan Wobben** |
| `the_source` | 36 | gearchiveerd | **Stefan Wobben** |

Ze zijn gearchiveerd maar nog wél aan een mens toegewezen. De uitkomst is hier toevallig hetzelfde
(Stefan), maar de regel moet expliciet zijn: **gearchiveerd-met-vervuller volgt de vervulling;
alleen gearchiveerd-zónder-vervuller valt terug op Stefan.** Anders hangt het van de volgorde van
twee checks af waar 85 berichten landen.

### c. "DM naar de huidige vervuller" — drie rollen hebben er twee

| rol | rijen | vervullers |
|---|---:|---|
| `mother_earth__nooch` | 7 | Lotte Mulder **én** Stefan Wobben |
| `mother_earth__nooch__circle_lead` | 2 | Lotte Mulder **én** Stefan Wobben |
| `mother_earth__circle_lead` | 2 | Stefan Wobben **én** Lotte Mulder |

**11 rijen zonder eenduidige ontvanger.** Drie mogelijkheden, ik kies niet:
naar beiden (dan staat hetzelfde bericht twee keer), naar de eerste in de lijst (willekeur), of
naar Stefan als tiebreak. **Jouw woord nodig.**

---

## 2. Het echte ontwerpprobleem: een DM heeft twee mensen nodig

Dit is niet hetzelfde bezwaar als in fase 8 — dat ging over de state. Dit is structureel.

Een DM-kanaal is `dm:<a>|<b>` met twee **persoon-id's**, gesorteerd. Bij de 338 rol-rijen is de
afzender vrijwel nooit een persoon:

```
by is een PERSOON:   5
by is iets anders: 333
   compliance 69 · claims-checker 46 · harry_hemp 45 · strategic_lead 30
   librarian 22 · website_watcher 19 · concurrent_scout 17 · copywriter 11 · …
```

Zet je die in `dm:compliance|<stefan>`, dan krijg je een kanaal met een antwoordveld waar niemand
aan de andere kant zit. Dat is letterlijk het dead-letter-patroon dat in dit dorp al eens is
vastgelegd: *een AI-rol leest geen berichten, dus werk bij een AI-rol krijgen = een project maken,
geen bericht sturen.* Een antwoordveld dat niets bereikt is erger dan geen antwoordveld.

### Twee vormen, met mijn voorkeur

**A — één DM per (ontvanger × afzendende rol), zonder antwoordveld.**
`dm:compliance|<stefan>` bestaat, Stefan ziet hem in zijn kanalenlijst, de 69 compliance-signalen
staan op één hoop. Het antwoordveld verdwijnt zodra de tegenpartij géén persoon is — één regel,
en hij is waar: je kunt niet antwoorden aan iets dat niet leest.
*Voordeel:* de signalen blijven gegroepeerd per bron, wat het teruglezen makkelijk maakt.
*Nadeel:* Stefan krijgt er ~8 kanalen bij die alleen historie bevatten.

**B — één kanaal per ontvanger, alles bij elkaar.**
Alles wat ooit aan jouw rollen is gesignaleerd in één stroom, met de afzender als regel-label.
*Voordeel:* één plek, geen kanaal-inflatie.
*Nadeel:* 201 + 49 + 36 = 286 berichten van zeven jaar bronnen door elkaar in Stefans lijst, en de
kanaalsoort `dm:<p>|<p>` (jij met jezelf) is een vreemd begrip in het datamodel.

**Mijn voorkeur: A.** Hij past in het bestaande model zonder een nieuw begrip, houdt de bron
zichtbaar, en het ontbrekende antwoordveld is een eerlijke mededeling in plaats van een belofte.

---

## 3. Wat van `a8aed27` en `3f261c7` overblijft

| onderdeel | oordeel |
|---|---|
| `plaats_notificatie()` — id-als-id, `at` uit de notificatie | **blijft**, met het `verwerking`-blok eruit |
| de migratiemodule: droogloop/apply, idempotent, rapport | **blijft**, de guard telt voortaan berichten en niet oordelen |
| `village notif_migratie [--apply]` | **blijft** |
| de droogloop-rapportage (geen ná-kolom bij dry-run) | **blijft** — die fout is echt en blijft gelden |
| `channels.ROLE` + `role_kanaal()` | **weg** |
| `VERWERKING_VELDEN` / `VERWERKING_OVERSLAAN` | **weg** |
| `werk_verwerking_bij()` | **weg** |
| `hersync()` | **weg** — bestond alleen om een state machine te spiegelen |
| `open_uit_kanalen()` | **weg** |
| `cockpit2._inbox_items()` + de `items=`-parameters | **weg** — `/inbox` wordt niet omgebouwd maar opgeheven |
| **stap 2 als geheel** | **vervalt** |

Netto: van de twee commits blijft ongeveer de helft van `notif_migratie.py` staan, plus één methode
op `ChannelStore`. Stap 2 was werk voor een scherm dat nu verdwijnt. Dat is jammer maar het is de
goedkope helft van het alternatief: had ik stap 2 en 3 in één keer gedaan, dan was `/inbox` nu weg
geweest en stond er een halve state machine in de kanalen.

**Eén ding uit stap 2 wil ik expliciet redden**: de bevinding dat de view **zeventien** velden
leest terwijl ik er twaalf kopieerde. In het nieuwe ontwerp verdwijnen die velden allemaal, dus het
probleem is weg — maar de les (een handgekozen veldenlijst is een tweede plek om iets te vergeten)
staat in het log en hoort daar te blijven.

---

## 4. Het herziene plan

Twee stappen in plaats van drie, omdat er geen tussenvorm meer te bewaken is.

**Stap A — migreren (schrijven, niets verwijderen).**
371 rijen → DM-berichten. Guard: 371 in, 371 uit, 0 verloren, en per bestemming een telling die je
kunt nalopen. Idempotent, droogloop eerst. `NotifStore` en `/inbox` blijven staan.

**Stap B — opruimen.** `NotifStore`, `/inbox`, `/inbox/verwerk`, de lade-chrome en de
verwerk-pagina eruit: 13 methodes, 46 aanroepen, 18 bronbestanden, 37 testbestanden.

Dit blijft een deploy-moment waard tussen A en B — niet om productie-ervaring met een state
machine op te doen (die is er niet meer), maar omdat je na A wilt kunnen kijken of de 371 berichten
leesbaar zijn aangekomen vóór de bron verdwijnt.

---

## 5. Wat ik van je nodig heb

1. **Vorm A of B** uit §2 — één DM per (ontvanger × afzendende rol) zonder antwoordveld, of één
   stroom per ontvanger.
2. **De 11 rijen op rollen met twee vervullers**: naar beiden, of naar Stefan als tiebreak?
3. **Bevestiging van de regel** uit §1b: gearchiveerd-mét-vervuller volgt de vervulling, alleen
   gearchiveerd-zónder-vervuller valt terug op Stefan. Dat bepaalt waar 85 berichten landen.
4. **Bevestiging dat `target_type` routeert** en niet `entry_id` (§1a).
