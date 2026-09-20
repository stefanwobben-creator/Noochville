# Fase 10 — doorlopend werklog

Stefan is offline vanaf 20 september ~02:50. Mandaat: punt 2 (groep A, B, C) en punt 3 afmaken,
aparte commit per onderdeel, 3-5 structureel geschreven tests, volledige suite voor en na.
**Stoppen bij punt 1 en punt 4** — die vragen eerst een voorstel. **Niets deployen of mergen.**

Alles blijft op branch `fase1-dode-rolklassen`. Prod draait op `8ab787a` en wordt vannacht niet
aangeraakt.

---

## Uitgangspunt

| | |
|---|---|
| laatste commit | `88ae4a6` — punt 2 stap 2 (typografie) |
| suite | 4.053 passed, 1 failed (`test_plausible_zonder_sleutel`, faalt ook op kale main), 1 xfailed |
| green-dark-ratchet | 46 selectors zonder nu-tegenhanger, plafond 46 |

## Plan voor vannacht

1. groep A — `projects.py` (119 oude-look-uses)
2. groep A — `inbox.py` (76)
3. groep A — `overview.py` (47)
4. groep A — `wizard.py` (35)
5. groep B — `/site-audit`, `/middelen`, `/rolefillers` in de routelijst
6. groep C — `werkoverleg.py` + `roloverleg.py`
7. punt 3 — het dubbele Organization-paneel op Circle-pagina's

Daarna stoppen. Punt 1 en punt 4 blijven liggen tot Stefan er is.

---

## 03:05 — groep A, stap 1: `projects.py` (`/projects`, `/project`)

**Wat.** 51 klassen droegen nog de oude look. Niet op naam aangepakt maar per patroon: omhulsels
met 1px crème rand + 9px radius, scheidingslijnen, grijstinten uit een ander palet, en
accentkleuren zonder merkdekking.

**Een meting vooraf, geen aanname.** Voor ik paars en koraal neutraliseerde heb ik geteld of ze
überhaupt in de huisstijl voorkomen:

```
--coral   #FF6B5B      0 px (e-mail)      1 px (productpagina)   → geen merkkleur
--goal    #6A4FA0      0 px               5 px                   → geen merkkleur
ai-paars  #7A5BD1      0 px               0 px                   → geen merkkleur
--yellow  #FFCE2E     18 px             662 px                   → WEL aanwezig (de sterren)
```

Paars en koraal dus neutraal, geel blijft staan. `--nu-danger` (#EE4036) blijft bestaan hoewel hij
ook nagenoeg afwezig is (10 px): een foutkleur is functioneel nodig. Dat is een keuze en geen
meting, en staat daarom expliciet in het CSS-commentaar.

**Resultaat.** 102 open klasse-gebruiken → 8. Wat overblijft is vorm en geen kleur: `mform`
(`font-family:inherit`), `mdot` (een ronde stip van .55rem) en `car`.

**Bijvangst: de gedeelde blokken raakten meer dan één view.** Door `att-*`/`qadd-*`, de eyebrow en
deze patroonregels zakten ook views die ik nog niet had aangeraakt:

| view | was | nu |
|---|---:|---:|
| overview.py | 47 | 9 |
| vangst.py | 28 | 15 |
| doelen.py | 22 | 1 |
| wiki.py | 14 | 2 |
| messages.py | 4 | 1 |

**Tests.** Drie nieuwe, allemaal structureel:
1. `test_dekking_per_view_gaat_alleen_omlaag` — een plafond per view, zelfde vorm als
   `_STYLE_WHITELIST` en `_PREFIX_CEILING`.
2. `test_het_plafond_staat_niet_te_ruim` — een ratchet die tien boven de werkelijkheid staat
   bewaakt niets; zakt een view, dan moet het plafond in diezelfde commit mee.
3. `test_kleuren_zonder_merkdekking_worden_binnen_nu_geneutraliseerd` — met een `_NOG_TE_DOEN`-lijst
   van acht klassen die vannacht nog aan de beurt komen, en een assert dat die lijst niet te lang
   blijft staan.

Suite: 4.056 passed, 1 failed (de bekende), 1 xfailed.

## 03:25 — groep A, stap 2: `inbox.py` (`/inbox`, `/inbox/verwerk`)

**Wat.** 37 klassen. Anders dan bij `projects.py` zat het zwaartepunt hier niet op randen maar op
**groen als achtergrondvulling**: `--green-tint` achter de leesregel, de kop van de lade, de teller,
de swipe-hint. Dat is precies de kleur-alleen-signalering die fase 9 uit het bord haalde, alleen
dan in de lade.

Aanpak: vulling rustig, **vorm blijft dragen**. `.rdr-row` houdt zijn dashed outline — dát is het
signaal, niet de tint erachter. Verder drie pil-radiussen weg (`ibx-plus`, `ibx-hct`, `ibx-ct`) en
alle grijstinten naar één `--nu-muted`.

**Resultaat.** 50 open klasse-gebruiken → **0**.

**Weer raakten de gedeelde regels andere views**: `vangst.py` 15 → 2, `wiki.py` 2 → 0,
`doelen.py` 1 → 0, `overview.py` 9 → 6. Dat komt doordat `wo-oc`, `wo-ocd`, `gk`, `fsep`, `read`,
`done` en `c2-bar` in meerdere views voorkomen.

**Stand van de dekkings-ratchet:**

```
roloverleg.py 34 · wizard.py 24 · werkoverleg.py 13 · search.py 10 · projects.py 7
overview.py 6 · vangst.py 2 · messages.py 1 · inbox.py 0 · doelen.py 0 · wiki.py 0
```

Suite: 4.056 passed, 1 failed (de bekende), 1 xfailed.

## 03:45 — groep A, stap 3: `wizard.py`, `search.py`, `overview.py` → alle drie 0

**`wizard.py` (`/project/nieuw`) was de aanleiding van deze hele groep.** De route stond al in
`_NU_ROUTES`, maar de wizard rendert met een eigen `wz-*`-familie waarvan `nooch-ui.css` geen enkele
klasse aanstuurde. Elf klassen, waarvan drie met een **999px-pil** (`wz-btn`, `wz-chip`, `wz-badge`)
en één met een **box-shadow** (`wz-card`) — allebei dingen die in de referentie nul keer voorkomen.

**Een test ving een fout van mij.** Ik had `gs-group` en `gs-kind` (search.py) een eigen blok met
eyebrow-eigenschappen gegeven. `test_de_eyebrow_is_een_definitie_en_geen_twaalfde_naam` sloeg
daarop aan: ik was precies bezig het probleem te maken dat die stap een uur eerder oploste — een
twaalfde losse definitie in plaats van een verwijzing naar de ene. Nu staan ze in de gedeelde
selector-lijst. Achttien namen, één definitie.

Dat is de tweede keer vannacht dat een structurele test een gemiste plek vond (de eerste was
`.attcard`). Beide keren omdat de test op een patroon zoekt en niet op een naam.

**Stand van de dekkings-ratchet:**

```
roloverleg.py 33 · werkoverleg.py 13 · projects.py 7 · vangst.py 2 · messages.py 1
doelen.py 0 · inbox.py 0 · overview.py 0 · search.py 0 · wiki.py 0 · wizard.py 0
```

Wat rest is groep C (`roloverleg.py`, `werkoverleg.py` — nooit herbouwd) plus drie restjes.

Suite: 4.056 passed, 1 failed (de bekende), 1 xfailed.
