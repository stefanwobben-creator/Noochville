# Alle 42 DM-kanalen op productie, per rij te beoordelen (21 september 2026)

Read-only inventarisatie. **Er is niets aangeraakt, niets verwijderd, niets gearchiveerd.**

Gemeten op prod (`/opt/noochville/data/channels.json`) als `nooch`. Een DM-kanaal heet
`dm:<a>|<b>`: één helft is de MENS die het leest, de andere is de AFZENDER. Die afzender bepaalt
alles — hij is een rol-id, een persona, een persoonsnaam of een los label, en daaraan zie je of er
nog iets achter zit.

**De extra toets die ik erbij heb gedaan**, want "oud" is geen bewijs van "dood": voor elk
afzender-label heb ik in de code gezocht of er nog een pad is dat dat label PRODUCEERT. Een kanaal
met oude berichten maar een levende afzender is geen dood kanaal — het is een stil kanaal. Twee
labels bleken zo alsnog levend die op leeftijd dood leken (`claims-checker` is de default-afzender
van `claims_board.bericht_aan_rol`; `village` komt uit `weekmemo.AFZENDER`).

Kolom **oordeel**: `dood` = afzender bestaat niet meer én niets produceert hem nog · `live` =
er komt nog verkeer uit · `twijfel` = jouw beslissing, met de reden erbij.

---

## A · Dood — afzender bestaat niet meer, niets produceert hem nog (13)

| # | afzender | soort | ber. | laatst | laatste bericht | oordeel |
|---|---|---|---:|---:|---|---|
| 1 | `Candy Cotton` | persona-NAAM | 1 | 63d | Dorpsoverleg: 23/23 belofte-onderdelen onbekend | dood |
| 2 | `Lara the Librarian` | persona-NAAM | 1 | 63d | Dorpsoverleg: 3 woordoordelen wachten sinds… | dood |
| 3 | `Noochie` | persona-NAAM | 1 | 63d | Dorpsoverleg: bulletin 13 dagen stil… | dood |
| 4 | `Sid the Science Kid` | persona-NAAM | 1 | 63d | Dorpsoverleg: 30 projecten, 14 blocked… | dood |
| 5 | `Walter Website` | persona-NAAM | 2 | 63d | Dorpsoverleg: 4 trendbronnen dood sinds 5 juli | dood |
| 6 | `Village Update Coördinator` | los label | 1 | 60d | ⤴ escalatie: Ontbrekende verantwoordelijke… | dood |
| 7 | `dialoog` | los label | 9 | 36d | @Noochie Wat wil je dat ik hier onderzoek? | dood |
| 8 | `dialoog` | los label | 1 | 65d | @Wytse Valkema dit zijn vragen aan leveranciers | dood |
| 9 | `dialoog` | los label | 1 | 67d | @Marketing Lead in dit rapport staan een aantal… | dood |
| 10 | `dialoog` | los label | 2 | 68d | @Scientist kan je een concreet advies uitbrengen | dood |
| 11 | `founder-flow` | los label | 7 | 41d | [rol compliance onbemand] Bank the evidence… | dood |
| 12 | `een rol` | los label | 5 | 34d | ⤴ beslissing gevraagd: **Situatie:** De website… | dood |
| 13 | `zelfsturende rol elastan-alternatieven` | los label | 1 | 59d | ⤴ escalatie: Geen enkel geïdentificeerd alternatief | dood |

De vijf persona-NAAM-kanalen zijn het geval dat jij noemde: de afzender is de NAAM van een persona
in plaats van zijn id — een vorm die nergens meer wordt geschreven. Alle vijf dragen hetzelfde
"Dorpsoverleg"-bericht van 63 dagen geleden.

`een rol` en `zelfsturende rol elastan-alternatieven` zijn geen labels maar **ingevulde
placeholdertekst**: iets heeft ooit een beschrijving als afzender-id gebruikt.

## B · Live — er komt nog verkeer uit deze afzender (10)

| # | afzender | soort | ber. | laatst | wie produceert hem nog |
|---|---|---|---:|---:|---|
| 14 | `village` | los label | 1 | 0d | `weekmemo.AFZENDER` — de weekmemo van gisteren |
| 15 | `dorp` | los label | 4 | 2d | `village.py` |
| 16 | `claims-checker` | los label | 42 | 6d | default-afzender van `claims_board.bericht_aan_rol` |
| 17 | `claims-checker` | los label | 4 | 6d | idem (tweede mens) |
| 18 | `pulse_watchdog` | los label | 2 | 21d | `dagcyclus.py` |
| 19 | `zelf` | los label | 20 | 12d | `cockpit2.py` |
| 20 | `mother_earth__nooch__strategic_lead_founder_steward` | rol-actief | 32 | 1d | levende rol |
| 21 | `mother_earth__nooch__compliance` | rol-actief | 1 | 6d | levende rol |
| 22 | `mother_earth__nooch__financial_controller` | rol-actief | 7 | 11d | levende rol |
| 23 | `mother_earth__nooch__website_developer` | rol-actief | 6 | 14d | levende rol |

(#24 `mother_earth__nooch__creator_of_shoes`, rol-actief, 1 ber., 25d — ook live.)

## C · Twijfel — jouw beslissing (18)

### C1 · Afzender is een PERSOONSNAAM of e-mailadres in plaats van een id (3) — je vroeg hier expliciet naar

| # | afzender | ber. | laatst | laatste bericht | waarom twijfel |
|---|---|---:|---:|---|---|
| 25 | `Stefan Wobben` | 2 | 19d | "Klaar: ⚠️ Capaciteit ontbreekt bij een rol: …" | ziet eruit als een systeemmelding die jouw NAAM als afzender kreeg |
| 26 | `Stefan Wobben` | 2 | 58d | "Check dit https://www.deweekvanrijssen.nl/…" | dit leest als een **echt bericht van jou aan iemand** — geen systeemruis |
| 27 | `stefan@nooch.earth` | 1 | 22d | "⚠️ Capaciteit ontbreekt bij mother_earth__no…" | systeemmelding met je e-mailadres als afzender-id |

Niets in de code produceert deze drie vormen nog. Rij 26 is het geval waar opruimen echt iets zou
weggooien: er staat inhoud in die een mens heeft getypt.

### C2 · Rol bestaat nog, maar slaapt of is gearchiveerd (10)

| # | afzender | soort | ber. | laatst | waarom twijfel |
|---|---|---|---:|---:|---|
| 28 | `compliance` | gearchiveerd | 69 | 11d | 69 berichten werkgeschiedenis |
| 29 | `harry_hemp` | gearchiveerd | 43 | 7d | idem, 43 berichten |
| 30 | `librarian` | gearchiveerd | 22 | 7d | |
| 31 | `website_watcher` | gearchiveerd | 19 | 4d | nog verkeer van 4 dagen geleden |
| 32 | `concurrent_scout` | gearchiveerd | 17 | 7d | |
| 33 | `…noochville__copywriter` | gearchiveerd | 11 | 11d | |
| 34 | `the_source` | gearchiveerd | 5 | 12d | |
| 35 | `harry_hemp` (tweede mens) | gearchiveerd | 2 | 15d | |
| 36 | `noochie` | slaapt | 3 | 9d | rol slaapt, kan wakker worden |
| 37 | `facilitator` | slaapt | 2 | 53d | idem |

Deze tien zijn géén ruis: het is de werkgeschiedenis van rollen die zijn opgeheven of slapen. Mijn
voorstel zou **archiveren** zijn (uit de lijst, niet uit de data) en niet verwijderen — precies de
lijn van de radar-archivering. Maar het is jouw besluit.

### C3 · Afzender bestaat niet meer, maar de inhoud is menselijk werk (5)

| # | afzender | ber. | laatst | laatste bericht |
|---|---|---:|---:|---|
| 38 | `werkoverleg-correctie` | 3 | 23d | "send message that we can meetup in Portugal" |
| 39 | `werkoverleg-correctie` (tweede mens) | 3 | 23d | "reply to complaint e-mail" |
| 40 | `afslank-opruiming` | 5 | 20d | "[noochie heeft geen vervuller] Verify full c…" |
| 41 | *(self-DM)* `dc5685eb2074` | 5 | 9d | "Hi Logan, Thank you for the update. I…" |
| 42 | `c732a5d82d84` | 5 | 12d | "Inform Bernardo about new material…" |

41 en 42 zijn **echte gesprekken tussen mensen** — die horen wat mij betreft sowieso te blijven; ze
staan hier alleen omdat ze in dezelfde bak zitten. 38 en 39 dragen taken die iemand heeft
ingetypt; de afzender is een correctie-script dat niet meer bestaat.

---

## Wat ik voorstel (maar niet doe zonder jouw regel per rij)

- **A (13)**: archiveren. Geen enkele draagt inhoud die iemand mist; drie ervan dragen wél een
  escalatie die ooit aan een mens gericht was, dus archiveren en niet wissen.
- **B (10)**: laten staan, dit is levend verkeer.
- **C1 (3)**: rij 26 sowieso houden (jouw eigen bericht). 25 en 27 zijn systeemmeldingen met een
  verkeerde afzender-id; die zou ik archiveren.
- **C2 (10)**: archiveren, niet wissen — het is geschiedenis van opgeheven rollen.
- **C3 (5)**: 41 en 42 houden. 38, 39 en 40 archiveren.

Zet per rij neer wat je wilt (`houden` / `archiveren` / `wissen`) en ik voer het uit met dezelfde
discipline als pijplijnstap 6: fingerprint vooraf, droge run, veldvergelijking achteraf, snapshot.
