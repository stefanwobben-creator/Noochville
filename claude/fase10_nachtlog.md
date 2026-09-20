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

## 04:05 — groep B: `/middelen`, `/rolefillers`, `/site-audit`

**Wat.** Drie routes aan `_NU_ROUTES` toegevoegd. `/middelen` en `/rolefillers` draaiden op
**dezelfde `overview.py`** als `/node`, `/person` en `/admin`, die er al in stonden — dezelfde
rendercode zag er dus anders uit afhankelijk van de URL. Dat was een gat in de lijst, geen besluit.
`/site-audit` was in fase 7 aangeraakt (taalresten) en viel daardoor ten onrechte buiten fase 9.

**Niet alleen de route.** Ik heb eerst `site_audit.py` gemeten vóór ik de route toevoegde — anders
herhaal ik de wizard-fout (body-klasse zonder markup-dekking). Eén open klasse: `.seg`, met een
`--radius-pill`. Meteen meegenomen.

**Een test met een eigen vorm.** `test_routes_van_dezelfde_view_zitten_allemaal_in_de_nu_scope`
leest route→view uit de vindkaart en eist dat een view die één route in de scope heeft, ze
allemaal in de scope heeft. Zo valt een volgende splitsing vanzelf op. `cockpit2.py` is
uitgezonderd met reden: dat is de dispatcher en geen view — die "rendert" ook `/login` en `/file`,
en dát die buiten de scope vallen is juist het besluit.

**Een bestaande test moest mee.** `test_de_geparkeerde_schermen_staan_er_bewust_niet_in` (fase 9)
noemde `/site-audit` als geparkeerd. Die regel is weggehaald mét de reden erbij in de docstring,
niet stilzwijgend — een stille wijziging daar is over een jaar onverklaarbaar.

`docs/ARCHITECTUUR.md` gaf geen diff: er zijn geen nieuwe routes of dispatch-acties, alleen een
uitbreiding van een bestaande lijst.

Suite: 4.057 passed, 1 failed (de bekende), 1 xfailed.

## 04:25 — groep C: `roloverleg.py` en `werkoverleg.py`

**Wat.** Deze twee stonden al in `_NU_ROUTES` maar zijn in fase 7/8 nooit herbouwd: ze kregen de
body-klasse op grond van de fase-9-brief ("de governance- en tactical-meeting-modals krijgen
dezelfde visuele stijl"), niet op grond van een herbouw. Daarom lag hier meer werk dan elders.

**Eén inhoudelijke keuze, expliciet gemaakt.** `.is-new` en `.is-del` markeren wat er in een
voorstel verandert. `.is-del` deed dat al met een dashed rand — die draagt vorm. `.is-new` had
alléén een groene vulling. Die heeft er nu een rand bij, zodat ook daar de vorm het signaal draagt
en niet de tint. Dat is dezelfde regel als bij de bordkolommen in fase 9 en bij `.rdr-row` in de
inbox vannacht.

**Resultaat.** `roloverleg.py` 33 → 1, `werkoverleg.py` 13 → 0.

## Stand na groep A + B + C

```
projects.py 7 · messages.py 1 · roloverleg.py 1 · en acht views op 0
                                                            TOTAAL 9
green-dark-ratchet: 46 → 36 selectors zonder nu-tegenhanger
```

Van de **491 open klasse-gebruiken** waar deze fase mee begon staan er nog **9**. Wat er rest is
vorm en geen kleur: `mform` (`font-family:inherit`), `mdot` (een ronde stip), `car`, `pdisc`
(`background:none;border:none`). Die laat ik staan — er valt niets aan te herstylen.

`_NOG_TE_DOEN` in de kleurtest is van acht klassen terug naar één (`mdot`).

Suite: 4.057 passed, 1 failed (de bekende), 1 xfailed.

## 04:50 — punt 3: het dubbele Organization-paneel

**Wat.** De organisatieboom stond in de zijbalk links **én** in een `.c2-rail` rechts. Twee keer
dezelfde boom op één scherm. De rail is weg.

**Breder dan alleen Circle-pagina's, bewust.** De opdracht noemde Circle-pagina's, maar dezelfde
rail stond op **vijf** plekken: `overview.py` (2×: `/node` en `/person`), `skills.py`,
`site_audit.py` en `doelen.py`. Alleen `/node` opruimen laat vier schermen met dezelfde dubbeling
staan — en dat is precies hoe `/middelen` en `/rolefillers` ontstonden. Alle vijf dus, en
`doelen._rail()` is als dode functie verwijderd in plaats van met een `noqa` blijven staan.

### ⚠ Eén afwijking die je moet zien

Je zei twee dingen die elkaar hier net raken: *"de organisatieboom blijft in de linkerbalk staan
(ongewijzigd)"* en *"geen functionaliteit verdwijnt"*.

De rail deed namelijk **iets extra's** dat de zijbalk niet deed: hij klapte de huidige node open en
markeerde hem. De zijbalk riep `_tree_html(st, '')` aan — zonder huidige node. Verwijder ik de rail
zonder meer, dan verdwijnt die positie-aanduiding.

**Mijn keuze:** functionaliteit behouden. `_send` geeft nu het `id` uit de query door aan
`_tree_html` als het pad `/node` is. Gevolg: op een node-pagina klapt de zijbalk open en staat de
huidige node gemarkeerd — zie `claude/fase9_screenshots/circle-desktop.png`, waar "Nooch" neon
oplicht en de dertien rollen eronder staan.

De prijs is dat de zijbalk op node-pagina's dus **niet letterlijk ongewijzigd** blijft. Wil je dat
wél, dan is het één regel terug (`_tree_html(_st, "")`) en accepteer je dat de "waar ben ik"-markering
verdwijnt. Zeg maar welke van de twee.

**Tests.** Drie, structureel: geen enkele view rendert nog een `c2-rail` (op patroon, dus een zesde
die later opduikt valt ook op), de zijbalk markeert de huidige node, en de Roles-tab bestaat nog.

**Een bestaande test moest mee.** `test_nooch_roles_tab` controleerde dat "Organization" op de
node-pagina staat — dat kwam uit de rail. `render_node` levert die string nu terecht niet meer op;
de boom wordt pas in `_send` geïnjecteerd. De assert is omgedraaid mét de reden erbij: staat hij er
wél, dan is de dubbeling terug.

**Nog een observatie, niet aangeraakt.** De tab-labels (`Overview`, `Roles`, `Members`, …) staan in
onderkast terwijl de knoppen ernaast wél hoofdletters dragen. Zelfde open vraag als de
zijbalk-navigatie van eerder vannacht. Geen van beide stond in de vier typografiepunten, dus ik heb
ze laten staan.

Suite: 4.060 passed, 1 failed (de bekende), 1 xfailed.

---

# Punt 1 en punt 4 — inventarisatie gedaan, NIETS gebouwd

Je zei: stoppen en wachten zodra ik hier kom, want beide vragen eerst een voorstel. De briefs
vragen zelf óók om een inventarisatie vooraf ("doe eerst een korte inventarisatie", "onderzoek
eerst"), en dat is lezen, geen bouwen. Dus die heb ik gedaan zodat je 's ochtends meteen kunt
beslissen. **Er is voor punt 1 en 4 geen regel code gewijzigd.**

## Punt 1a — het zoek/filterveld: waarom het acuut is

Gemeten op prod:

```
projecten (niet-gearchiveerd)   442      ← evenveel projectkanalen in de lijst
  waarvan met minstens 1 bericht 385
cirkels                          20
cirkel- en DM-kanalen in gebruik   0      ← de laag staat sinds vannacht live
```

`views/messages.py` toont élk niet-gearchiveerd project als kanaal. Dat zijn er **442**. Dat is
geen lijst meer, dat is een muur — je bevinding klopt en het is erger dan "onhandig".

**Ik heb het veld niet gebouwd.** Je schreef eerder "bouw sowieso een zoek/filterveld", maar
vannacht "stop zodra je bij punt 1 komt". Die twee spreken elkaar tegen en ik ga daar niet zelf
tussen kiezen. Het is een klein, geïsoleerd stuk en kan er in één beurt in zodra je ja zegt.

## Punt 1b — een vierde kanaalsoort: het voorstel

**Wat er nu staat.** Drie soorten, één vorm. Het kanaal-id is `soort:doel`, en `doel` is altijd
het id van iets dat al bestaat:

| soort | id | opslag |
|---|---|---|
| `project` | `project:<pid>` | `ProjectLedger`, in `project["log"]` — 442 bestaande gesprekken |
| `circle` | `circle:<record_id>` | `data/channels.json` |
| `dm` | `dm:<a>\|<b>`, id's gesorteerd | `data/channels.json` |

Eén `ChannelStore` met twee achterkanten. `soort_van()` en `doel_van()` splitsen op de dubbele
punt; verder weet niemand welk soort hij aanspreekt.

**Wat een vierde soort breekt.** Alle drie de bestaande soorten *lenen* hun identiteit van iets
dat al bestaat. Een los kanaal heeft geen ouder — het is het eerste kanaal dat iemand moet
**aanmaken**, en dat bestaat nu nergens in het model. Drie vragen volgen daaruit:

**1. Waar komt het id vandaan?**

- **A — `topic:<id>` met een aparte namenlijst** (`data/channels.json` krijgt `"namen": {id: naam}`).
  Hernoemen raakt de trail niet, twee mensen kunnen niet per ongeluk hetzelfde kanaal maken onder
  een andere schrijfwijze. *Mijn voorkeur*, en om dezelfde reden waarom de DM-id gesorteerd is:
  identiteit mag niet aan een weergavestring hangen.
- **B — `topic:<slug>`, de naam ís het id.** Simpeler te lezen in een logregel, maar hernoemen
  verliest het gesprek en "Batch 4" / "batch-4" / "Batch-4" worden drie kanalen.

**2. Wie mag er een aanmaken?** Nu maakt niemand een kanaal: het bestaat omdat zijn onderwerp
bestaat. Drie opties: iedereen-ingelogd (zoals `_claims_gate` sinds fase 5), circle-member, of
Circle Lead. Het is een nieuwe dispatch-tak, dus CLAUDE.md eist hier sowieso een expliciet
AUTHZ-label.

**3. Dit draait een besluit van vier dagen terug om.** Bij fase 8 zei je letterlijk: *"Cirkelkanalen:
één per bestaande cirkel. Geen vrije onderwerp-kanalen zoals #batch-4."* Punt 1 vraagt nu precies
dat. Prima om van gedachten te veranderen — maar het hoort als correctie benoemd te worden en niet
stilzwijgend gebouwd, zoals je zelf bij de 338 notificaties zei.

**Verder nog:** `views/messages.py` groepeert nu in drie kopjes; er komt een vierde bij. En
`kanalen_van()` kent alleen DM's — voor losse kanalen is er geen "waar zit ik in", dus of iedereen
ziet alles, of er komt een lidmaatschap-begrip bij. Dat laatste is een tweede nieuw datamodel-begrip
en daar zou ik in deze ronde vanaf blijven.

## Punt 4 — het edit-formulier, zoals het nu werkt

**Het formulier** (`views/overview.py::_artefact_edit_form`): een `<details class='qadd'>` met
summary "edit", die openklapt naar een `<form method='post' action='/action'>`. Velden:

| veld | soort | opmerking |
|---|---|---|
| `csrf` | hidden | |
| `aid` | hidden | het artefact-id |
| `next` | hidden | waar je na opslaan landt; `/pagina` geeft zijn eigen permalink mee |
| `title` | tekst | |
| `body` | `md_editor()` | de markdown-editor |
| `url` | url | **alleen** als `kind == "tool"` |

Eén knop `Save` (`name=action value=artefact_edit`) en een ✕ die de `<details>` dichtklapt.

**Het opslaan** (`cockpit2._act_artefact_edit`): haalt het artefact op, draait **`_artefact_gate`
vóór de mutatie** (rolvervuller of Circle Lead; weigering = `Forbidden`), controleert de
bodylengte, en roept dan `st.att.update(...)` aan met `actor_id`, `actor_type="person"`,
`governance_ref` (`domain:<x>` als het artefact een domein heeft, anders `role:<anchor>`) en
`change_note="bewerkt"`. Daarna `artefacts.log_change(action="edit", ...)`.

Belangrijk detail: `update()` schrijft alleen wat je meegeeft — `title=(g("title") if "title" in
form else None)`. Een veld dat niet in het formulier zit, blijft ongemoeid. Dat is precies wat
inline bewerken nodig heeft: je kunt per veld opslaan zonder de rest te overschrijven.

**Wat je zei te behouden, en waar het zit:**
- dezelfde rechtencheck → `_artefact_gate(cur.anchor, username, st)`, ongewijzigd hergebruiken
- dezelfde version/change_note-opslag → `AttachmentStore.update` voegt een versie-entry toe met
  `change_note`; die moet dus blijven lopen via `update()` en niet via `set_meta()` (dat schrijft
  bewust zónder versie)

**De echte ontwerpvraag** is niet de techniek maar de change_note. Nu is er één opslagmoment per
bewerking en dus één versie-entry `"bewerkt"`. Bij inline bewerken per veld krijg je drie
versie-entries voor wat de gebruiker als één wijziging ervaart. Opties: per veld een eigen
change_note (`"titel bewerkt"`), of debouncen tot één entry per sessie. Dat moet je beslissen
vóórdat er 442 pagina's met een rommelige historie staan.

---

# Slot

**Niets gedeployed, niets gemerged.** Prod draait nog op `8ab787a`. Alle werk staat op
`fase1-dode-rolklassen`, niet gepusht.

## Wat er vannacht af is

| commit | wat |
|---|---|
| `7fa8492` | groep A — `projects.py` 102 → 8 |
| `3843cb2` | groep A — `inbox.py` 50 → 0 |
| `0d305a3` | groep A — `wizard.py`, `search.py`, `overview.py` → 0 |
| `5703b70` | groep B — `/middelen`, `/rolefillers`, `/site-audit` in de scope |
| `3cda4fe` | groep C — `roloverleg.py` 33 → 1, `werkoverleg.py` 13 → 0 |
| `506f9d6` | punt 3 — de dubbele organisatieboom weg |

Van **491** open klasse-gebruiken naar **9**, en die negen zijn vorm en geen kleur.
Suite: 4.060 passed, 1 failed (de bekende `test_plausible_zonder_sleutel`), 1 xfailed.

## Drie dingen waar ik je antwoord op wil

1. **De zijbalk op node-pagina's is niet letterlijk ongewijzigd** (punt 3). Functionaliteit
   behouden of de zijbalk met rust laten — één regel verschil.
2. **Het zoek/filterveld in Messages**: "bouw sowieso" van eerder tegen "stop bij punt 1" van
   vannacht. 442 kanalen in die lijst, dus het is urgent.
3. **Hoofdletters in de navigatie en de tabs.** De zijbalk (`Projects`, `Messages`, …) en de
   tabbladen (`Overview`, `Roles`, …) staan in onderkast terwijl de knoppen ernaast wél
   hoofdletters dragen. De referentie heeft `SHOP STORE MISSION CONTACT` in hoofdletters. Viel
   buiten de vier punten, dus ik heb het laten staan.

---

# Ochtendronde — na Stefans zes besluiten

## punt 1a — het zoek/filterveld in Messages

**Twee ingrepen, niet één.** Een zoekveld alleen lost het niet op: zonder zoekterm stonden er nog
steeds 442 regels in de lijst. Dus ook een cap op de projectgroep (`PROJECT_CAP = 25`), **op
volgorde van het laatste bericht**. Alfabetisch afkappen is willekeurig; op recentheid afkappen
laat precies zien waar het gesprek loopt. Cirkels (20) en DM's blijven altijd compleet.

**Het veld is een GET-formulier, geen JS-filter.** Drie redenen: hij werkt zonder scripts, de
uitkomst is deelbaar als URL, en er hoeven geen 442 regels naar de browser die je daarna verbergt.

**Een stille cap is een leugen**, dus het scherm zegt `25 of 37 · search for the rest`. Daar staat
ook een test op.

**Eén ding dat ik onderweg tegenkwam:** de voordeur-keuze ("open op iets dat gezegd is") gebruikte
`groepen`, en dat is ná het filteren. Daarmee zou je na een zoekopdracht op een ander kanaal landen
dan ervoor. Nu roept hij `_kanalen(st, ik, "")` apart aan voor het volledige veld. Er staat een
test op die precies dat vergelijkt.

Zeven tests, op gedrag geschreven en niet op opmaak: ze bouwen een dorp met meer kanalen dan de cap
en kijken wat er in en uit de lijst valt.

Suite: 4.067 passed, 1 failed (de bekende), 1 xfailed.

## besluit 3 — hoofdletters in zijbalk-navigatie en tabbladen

`PROJECTS · MESSAGES · WIKI · INBOX · CIRCLE · ADMIN` in de zijbalk, en
`OVERVIEW · ROLES · MEMBERS · GOALS · WIKI · PROJECTS · CHECKLISTS · METRICS` op de tabbalk.

De rolnamen in de organisatieboom blijven in normale schrijfwijze — dat is inhoud en geen
navigatie. Zelfde grens als bij de projectkaarten op het bord.

De test is structureel: verzamel élk blok in `nooch-ui.css` dat een navigerend element aanstuurt
(zijbalk, subnav, tabs, link-knoppen) en eis `text-transform: uppercase`. Een vijfde
navigatie-familie die later bijkomt valt daarmee ook op. `:hover`- en `.on`-varianten zijn
uitgezonderd; die erven het van de basisregel.

Suite: 4.068 passed, 1 failed (de bekende), 1 xfailed.

## punt 1b — het vierde kanaalsoort

Gebouwd volgens besluit 4 en 5: `topic:<id>` met de naam apart, iedereen-ingelogd mag er een
aanmaken, geen lidmaatschap-begrip.

**Twee eigenschappen dragen de hele keuze**, en daar staat elk een eigen test op:

1. **Het id is geen slug.** Er staat een assert dat "batch" níét in het kanaal-id voorkomt — anders
   is optie A alleen op papier gekozen. En: hernoemen laat de trail intact. Zonder
   `hernoem_topic()` koopt optie A niets, dus die methode is er ook.
2. **Aanmaken is idempotent op de genormaliseerde naam.** "Batch 4", "batch-4", "BATCH  4" en
   "Batch  4" geven allemaal hetzelfde kanaal. Dat was jouw expliciete argument voor optie A, dus
   het hoort in de code te staan en niet alleen in de bedoeling.

**Eén regel omgedraaid ten opzichte van projectkanalen.** Een leeg projectkanaal staat níét in de
lijst (een leeg project is geen gesprek maar een project). Een leeg topic-kanaal staat er **wel**:
een kanaal dat je net hebt aangemaakt en niet terugziet, lijkt mislukt.

**De herziening staat in de brief**, als blok boven punt 1, met de reden en de drie bijbehorende
keuzes. Niet stil uitgebreid.

`docs/ARCHITECTUUR.md` is geregenereerd — `topic_add` is een nieuwe dispatch-actie.

Acht tests. Suite: 4.076 passed, 1 failed (de bekende), 1 xfailed.

### ⚠ Eén ding uit je bericht herken ik niet

Je schreef bij de bouwvolgorde: *"dan pas punt 1b (het vierde kanaalsoort + **de inbox-migratie van
gisteravond**, met besluit 4 en 5 hierboven als antwoord)"*.

**Er is gisteravond geen inbox-migratie geweest.** Fase 8 heeft juist expliciet níét gemigreerd: de
338 rol-notificaties zijn ongewijzigd op `/inbox` blijven staan, `NotifStore` bestaat onveranderd
naast de kanaallaag, en jij gaf daar op 19 september akkoord op ("geen tweede partij voor een DM bij
333 van de 338; het read/processed/archived/outcome/poort-model is geen boolean"). Vannacht heb ik
`inbox.py` alleen **visueel** aangepakt — 50 klasse-gebruiken, nul gedragswijziging.

Ik heb hier dus niets aan gebouwd, omdat ik niet weet wat je bedoelt. Drie mogelijkheden: je
bedoelt de visuele inbox-stap van vannacht (die is af), je bedoelt dat de 338 nu alsnog naar kanalen
moeten (dat is een nieuw en groot besluit), of het komt uit een andere draad. Zeg welke.

## punt 4 — inline bewerken met de ene save-actie

**Wat níét verandert, en dat is het punt:** één formulier, één submit, één `artefact_edit`-actie,
één `update()`-aanroep, één versie-entry met `change_note="bewerkt"`. De poort (`_artefact_gate`)
staat nog steeds vóór de mutatie. Daar staan vier tests op, waarvan één structureel op de
volgorde in de bron — een poort ná de schrijfactie is geen poort.

**Wat wel verandert:** de opslaan-balk verschijnt pas als er echt iets getypt is
(`data-qadd-dirty`), en klikken op de tekst van een pagina opent het formulier (`data-qadd-open`).

**Drie keuzes die ik onderweg heb gemaakt:**

1. **De `<details>` blijft als drager.** Niet uit nostalgie: zonder JS is de "edit"-summary de
   enige ingang, en op een lijst met twintig artefacten wil je geen twintig openstaande
   tekstvakken. Op `/pagina` (één pagina) voelt het als inline; in een lijst blijft het opgevouwen.
2. **De balk is in de HTML zichtbaar en wordt pas dóór JS verborgen.** Andersom — `hidden` in de
   HTML — zou de opslaan-knop onbereikbaar maken zodra scripts uitstaan. Dan is "inline" een
   regressie en geen verbetering. Daar staat een test op.
3. **Klikken opent alleen voor wie mag bewerken.** `data-qadd-open` komt alleen op de pagina als
   `can_edit` waar is; anders belooft een tekstcursor iets wat de poort daarna weigert.

**Eén beperking die je moet weten:** wie het formulier opent, ziet de markdown-broncode en niet de
opgemaakte tekst — `md_editor` heeft een werkbalk maar geen live preview. Voor een korte notitie is
dat prima, voor een lange wiki-pagina minder. Een preview is een eigen stuk werk; zeg het als je
dat wilt.

**Geen nieuwe klasse-prefix-familie.** `_PREFIX_CEILING` staat op 65 en er wáren er 65. De nieuwe
namen zijn daarom `qadd-bar` binnen de bestaande `qadd-`-familie — wat ook eerlijk is, want het is
letterlijk hetzelfde component.

Zeven tests. Suite: 4.083 passed, 1 failed (de bekende), 1 xfailed.

## punt 4b — de voorbeeld-knop (optie 2)

Een 👁-knop aan het eind van de editor-werkbalk wisselt tussen het tekstvak en de opgemaakte
weergave. Nogmaals klikken (✎) gaat terug.

**De weergave komt van de server**, via een nieuw fragment-endpoint `/md-preview` dat gewoon `_md`
aanroept. Niet van een markdown-parser in JavaScript, en dat is de enige echte keuze hier: een
tweede renderer loopt uiteen zodra er één opmaakregel bij komt, en zou bovendien het escapen
opnieuw goed moeten doen. Er staat een structurele test op die eist dat er géén opmaak-syntax
(`**`, `~~`, `## `, `replace(/`) in de JS-functie voorkomt — het begin van een tweede renderer
valt daarmee op bij het schrijven.

Het opslagmodel is niet aangeraakt; ook daar staat een test op die de `/md-preview`-tak scant op
`_Stores(`, `.update(`, `.add(`.

Twee kleine keuzes: het endpoint eist csrf (hij schrijft niets, maar kaatst wel willekeurige tekst
terug — fail-closed, zelfde regel als de wizard-endpoints), en als de call faalt klapt het tekstvak
meteen terug open. Een leeg voorbeeldvak leest als "je tekst is weg", en dat is precies het moment
waarop iemand gaat plakken.

`docs/ARCHITECTUUR.md` geregenereerd — `/md-preview` is een nieuwe route.

Vijf tests. Suite: 4.088 passed, 1 failed (de bekende), 1 xfailed.

## inbox-migratie, stap 1 van 3 — schrijven naast NotifStore

**Niets verwijderd.** `NotifStore`, `/inbox` en `/inbox/verwerk` staan er ongewijzigd.

Nieuw: `channels.ROLE` + `role_kanaal()`, `ChannelStore.plaats_notificatie()`, de module
`notif_migratie.py` en het commando `village notif_migratie [--apply]` (droogloop by default).

**Getoetst op écht productiedata**, op een lokale kopie van `notifications.json`:

```
rol-gerichte notificaties : 338      persoon-gericht (blijft): 33
geschreven                : 338      kanalen                 : 17

veld           vóór      ná
outcome         185     185
poort            54      54
verwerkingen     83      83
read            259     259
processed       258     258
archived        225     225
done             33      33
deleted          52      52          ✓ tellingen kloppen
```

De harde eis haalt het dus: **185 outcomes en 54 poort-oordelen komen er exact doorheen.** De
kopie is na de test verwijderd.

**Drie dingen uit de bouw die het melden waard zijn:**

1. **Het id van de notificatie wordt het id van het bericht.** Daardoor is de migratie idempotent
   (tweede run schrijft 0) én blijft elk bericht terug te voeren op zijn bron zolang `NotifStore`
   er nog staat. Dat laatste is precies wat stap 1 bruikbaar maakt om te controleren.
2. **`at` komt uit de notificatie, niet van de klok.** Anders staat drie maanden gesprek op de dag
   van de migratie en is de volgorde weg.
3. **De negatieve test kostte me een ronde en leverde een inzicht op.** Ik brak de guard door een
   `poort`-veld uit een bericht te halen — en de guard bleef "klopt". Reden: elke schrijfmethode van
   `ChannelStore` herlaadt onder het slot (`JsonStore._WRITE_METHODS`), dus mijn mutatie in het
   geheugen werd bij de volgende schrijfactie weggegooid. Prettige eigenschap, maar een test die
   dat niet weet toetst niets. Staat nu als comment in de test.

**Eén echte bug die de prod-droogloop aan het licht bracht.** De droogloop printte óók de
ná-kolom, en die staat dan logischerwijs op nul: acht regels `← WIJKT AF` met eronder
`✓ tellingen kloppen`. Dat leest als van alles behalve als *"er is nog niets gebeurd"* — dezelfde
fout als de neutrale `▸` bij een no-op deploy die ooit een ronde kostte. Een droogloop toont nu
alleen de huidige telling plus `◌ droogloop — de ná-telling en de guard volgen bij --apply`.

**Wat opviel maar geen actie vraagt:** van de 17 rolkanalen horen er meerdere bij rollen die niet
meer leven — `the_source` (36 items), `mother_earth__nooch__noochville__circle_lead` (49),
`librarian` (8). Die hebben geen open items en vallen dus buiten de negentien, maar ze bevestigen
de vormkeuze: een opgeheven rol houdt gewoon zijn kanaal met historie erin, en er hoeft niemand
aangewezen te worden.

Tien tests. Suite: 4.098 passed, 1 failed (de bekende), 1 xfailed.

## inbox-migratie, stap 2 van 3 — `/inbox` leest uit de kanalen

`NotifStore` staat er nog en **blijft de schrijver**. Wat verandert is de LEZER: `/inbox` en de
lade halen hun rol-items nu uit `role:<id>`-kanalen.

**Eén plek die het bij elkaar houdt, niet dertien.** Zolang stap 3 niet is gezet, staat hetzelfde
feit op twee plekken — precies wat `reference, don't copy` normaal verbiedt. De volgorde lost dat
op: `hersync()` draait vlak vóór het lezen, in `_inbox_items`. Een inbox-actie hoeft zichzelf dus
niet te spiegelen en kan dat ook niet vergeten. Het alternatief — een sync-aanroep in elke
schrijf-tak — is dertien plekken die het allemaal moeten onthouden.

**Fail-open, bewust de andere kant op dan gebruikelijk.** Faalt de kanaal-lezing, dan valt de route
terug op `NotifStore`. Een lege inbox is hier het gevaarlijke antwoord: dan denkt iemand dat er geen
werk ligt. Liever de bron die sinds juni werkt dan een stil scherm. Test erop.

### Een echte fout in stap 1, gevonden door stap 2

Ik had `VERWERKING_VELDEN` als **handgekozen lijst van twaalf** gebouwd. Toen `/inbox` erop ging
lezen bleek de view er **zeventien** te gebruiken: `herkomst`, `pagina`, `voorstel`,
`triage_grond`, `triage_rol`, `triage_vorm` en `ok` stonden er niet bij. Met de oude lijst zouden
die velden stil leeg zijn geweest — en dat merk je pas als een scherm een half item toont.

Nu gaat **alles** mee, met een overslaan-lijst van drie (`id`, `at`, `tekst`, want die staan al op
het bericht zelf). Een handgekozen lijst is een tweede plek waar een veld vergeten kan worden.
`VERWERKING_VELDEN` bestaat nog, maar alleen als **telijst voor de guard** — daar wil je de
oordelen juist met naam en toenaam terugzien.

Dat is precies waarom je de drie stappen wilde: deze fout was in één grote commit pas na het
verwijderen van `NotifStore` opgevallen, en dan was er geen bron meer om uit te herstellen.

### Nog een testfout van mezelf

`archive_item` weigert wat nog niet verwerkt is (*"alleen wat verwerkt is mag weg"*). Mijn test
archiveerde direct en concludeerde dat de sync stuk was. De volgorde verwerken → archiveren is de
echte volgorde op het scherm; de test volgt hem nu.

Vier tests erbij (14 totaal in dit bestand). Suite: 4.102 passed, 1 failed (de bekende), 1 xfailed.

## HERONTWERP — de inbox wordt DM (vorm A)

Stefan trok de eis op het bewaren van de verwerkingsstate in. `role:<record_id>` vervalt, stap 2
vervalt, het worden twee stappen. Vorm A gekozen: één DM per (ontvanger × afzendende rol), zonder
antwoordveld als de tegenpartij geen persoon is.

**Weggegooid uit `a8aed27`/`3f261c7`:** `channels.ROLE`, `role_kanaal()`, `VERWERKING_VELDEN`,
`VERWERKING_OVERSLAAN`, `werk_verwerking_bij()`, `hersync()`, `open_uit_kanalen()`,
`cockpit2._inbox_items()` en de `items=`-parameters op beide inbox-views. **Behouden:**
`plaats_notificatie()` (id-als-id, `at` uit de notificatie), de droogloop/apply-vorm en de
rapportage-fix.

### Droogloop op echte prod-data

```
notificaties  371      geschreven 360      geparkeerd 11      DM-kanalen 41

routering:  vervuller 308 · persoon 33 · terugval 19 · meerdere-vervullers 11

geparkeerd (een mens moet kiezen):
   role:mother_earth__nooch               7
   role:mother_earth__nooch__circle_lead  2
   role:mother_earth__circle_lead         2
```

De verdeling klopt precies met wat ik in het voorstel voorspelde. De grootste kanalen:
`compliance ↔ Stefan` (68), `harry_hemp ↔ Stefan` (43), `claims-checker ↔ Stefan` (42).

**Van de 41 kanalen hebben er 39 een niet-persoon als tegenpartij** en dus geen antwoordveld.
Twee hebben twee echte mensen; daar blijft het veld staan.

### Eén ding dat de prod-droogloop aan het licht bracht

Er is **één echt zelf-kanaal**: `dm:<stefan>|<stefan>`, van notificaties waarvan de afzender
dezelfde mens is als de vervuller van de doelrol — jij die je eigen rol aanspreekt. Zonder aparte
regel heette dat "direct" (net als elk ander naamloos kanaal) én had het géén invoerveld, terwijl
het je eigen notitieblok is. Heet nu "Yourself" en mag antwoorden.

### De elf geparkeerde rijen

Drie rollen hebben Lotte **én** Stefan als vervuller. De migratie raadt niet: ze blijven in
`NotifStore` staan en worden in het rapport bij naam genoemd. De guard telt ze mee
(`360 + 11 = 371`), dus ze kunnen niet stil verdwijnen. Zodra Stefan kiest is het één extra run —
de migratie is idempotent.

Veertien tests. Suite: 4.102 passed, 1 failed (de bekende), 1 xfailed.

## stap B — begonnen, en bewust gestopt vóór de commit

Opdracht: B alvast bouwen, dan deployen. Ik heb B gesplitst in B1 (alles wat vanaf nu ontstaat gaat
als DM) en B2 (`NotifStore`, `/inbox`, `/inbox/verwerk` en de lade eruit), en B1 gebouwd. **B1 is
niet gecommit** — hij staat in de stash (`B1-writers-wip`). De reden staat hieronder.

### Wat er wél is gecommit: de gedeelde routering

`signaal.py` — één plek die bepaalt bij wie een melding landt, gebruikt door de migratie (371
bestaande rijen) én door alles wat vanaf nu ontstaat. Twee kopieën zouden betekenen dat dezelfde
rol-id vandaag bij Lotte landt en morgen bij Stefan zonder dat iets zich meldt.

Eén verschil staat er expliciet in, want het is een keuze: **bij meerdere vervullers parkeert de
migratie, maar gaat een nieuwe melding naar allemaal.** Historie hoort precies één plek te hebben
en een mens kiest welke; nieuw werk mag liever dubbel aankomen dan nergens.

### Waarom B1 niet gecommit is

De tien schrijfplekken omzetten werkte (`.notif.add` komt nul keer meer voor in `cockpit2.py`,
alles loopt via `_signaleer`). Maar de suite gaat daarmee van 1 naar **44 failures**, verdeeld over
twaalf testbestanden. Ze falen allemaal in dezelfde vorm:

```
items = st.notif.open_for_targets(...)
assert len(items) == 1      →  assert 0 == 1
```

Dat is geen bug maar de gedragswijziging zelf: die tests controleren dát er een inbox-item ontstaat.
Ze moeten controleren dat er een DM ontstaat. Mechanisch van vorm, maar **inhoudelijk niet**: elke
test legt vast wie wát krijgt, en dat is precies wat deze migratie verandert.

De werkafspraak is volledige suite groen vóór elke commit. Ik commit geen rode boom, en ik ga 44
tests die vastleggen wie welk bericht krijgt niet aan het eind van een lange beurt in één veeg
herschrijven — dat is hoe je een migratie krijgt die er goed uitziet en het niet is.

### Twee gedragsbesluiten die ik in B1 moest nemen, en die je moet zien

1. **`_settle_inbox(processed=True)` stuurt niets meer.** Vier van de vijf aanroepen zetten een
   item neer en markeerden het meteen als verwerkt — werk dat al gedaan was op het moment dat het
   verscheen. Zonder verwerkingsmodel is er geen plek meer voor "al gedaan", en een bericht over
   afgerond werk is geen bericht maar een log. Alleen `processed=False` (de mens moet er nog naar
   kijken) stuurt nog een DM.
2. **De `extra`-velden vervallen.** `type`, `rol`, `prive`, `opdrachtgever`, `bron_project`,
   `MENS_GETYPT`, `afronding`, `suggestie` — die droegen het inbox-scherm. Een DM heeft alleen
   tekst, afzender en tijd. `bron_project` is als `herkomst` bewaard gebleven, want dat is het enige
   veld dat het bericht zelf leesbaar houdt ("from project X"). De rest verdwijnt.

Besluit 1 verandert wat je nog te zien krijgt; besluit 2 verandert hoe een bericht eruitziet. Geen
van beide wilde ik stilzwijgend committen.

### Wat ik voorstel

B1 als eigen beurt, met de 44 tests erbij en per testbestand nagelopen wat het vastlegt. Daarna B2.
De stash staat klaar; niets is verloren.

## stap B1 — nieuwe signaleringen gaan als DM

Groen: 4.104 passed, 1 failed (de bekende), 1 xfailed. `NotifStore` staat er nog; opruimen is B2.

### De 11 geparkeerde rijen zijn weg als categorie

Per besluit gaan ze naar de terugval (de founder), net als de rijen van de opgeheven rollen. Het
onderscheid tussen migratie en nieuwe melding blijft wél staan en heeft een eigen test:
**historie → één ontvanger, nieuw werk → alle vervullers.** Nieuw werk mag dubbel aankomen,
historie hoeft dat niet.

### Drie dingen die B1 blootlegde, en die ik NIET heb omgezet

Van de tien schrijfplekken zijn er **acht** omgezet. Twee niet, en dat is geen restwerk maar een
grens die pas zichtbaar werd door het te proberen:

1. **Het pagina-voorstel** (`pagina_voorstel` → `verzoek_besluit`). Dat is geen signalering maar een
   **verzoek met een beslissing**: accepteren, weigeren, aanpassen — en `verzoek_besluit` leest het
   item terug op `nid`. Een DM heeft geen plek om "hier moet nog over beslist worden" te dragen.
2. **De werkoverleg-actie.** Toegewezen werk met een afrondknop: het komt terug via
   `_sluit_reden_terug` en `mark_done`, en de opdrachtgever krijgt bericht zodra het af is.

Samen waren die twee goed voor **25 van de 43 gebroken tests**. Dat is het bewijs dat ze een andere
soort zijn: de inbox was niet alleen een meldingenlijst, er zat een **besluitwachtrij** in.

3. **`spanning_ontstaat` heeft geen aanroeper meer.** De typeer- en bevinding-poort hing uitsluitend
   aan `NotifStore.add`. Van de acht omgezette paden draait hij nergens meer; hij leeft alleen nog
   op de twee paden hierboven. Een hele module die stilvalt zonder dat iets het zegt — precies waar
   `village._meld_verweesde_pulse_skills` voor bestaat, maar dan voor een poort.

**Dit verandert de opdracht voor B2.** "NotifStore verwijderen" kan niet zolang die besluitwachtrij
er nog op draait. Er zijn twee wegen, en dat is een keuze voor Stefan:
- de besluitwachtrij een eigen, kleine store geven (hij is klein: voorstellen + acties), of
- `NotifStore` laten staan voor uitsluitend die twee flows en alleen `/inbox` als scherm opheffen.

### Een bug die de tests aan het licht brachten

**Een gast die via "+ tension" iets noteerde, verloor het.** `signaal.ontvangers` gaf een lege
lijst voor een onbekend persoon, en `stuur` postte dan niets. Het oude pad zette het nog als item
op de pseudo-persoon "guest". Een genoteerde spanning die nergens aankomt is het ergste wat deze
laag kan doen: de schrijver denkt dat hij iets heeft vastgelegd. Nu valt een onbekende ontvanger
terug op de founder, met een test erop.

En één regressie die ik zelf introduceerde en die een bestaande test ving: **jezelf vermelden maakte
weer een gesprek met jezelf.** De oude code filterde de afzender eruit vóór de terugval-tak; mijn
omzetting deed dat erna. Het onderscheid "niets te doen" versus "geen mens om heen te sturen" was
er wél en ging bijna verloren.

### Wat er in de 44 tests is veranderd

Niet mechanisch vervangen. Per test nagelopen wat hij vastlegde:

- **Vier tests toetsten `status_of(...) == "verwerkt"`** — werk dat al gedaan was op het moment dat
  het verscheen. Die assertie is nu het spiegelbeeld: er gaat **geen** bericht naar de mens. Drie
  andere toetsen juist dat er wél een DM komt.
- **`test_spanning_gaat_ongetypeerd_de_bestaande_haak_in`** heet nu
  `test_een_gevangen_punt_gaat_ongewijzigd_naar_de_mens`: de haak draait niet meer (bevinding 3),
  maar wat de naam beloofde — andermans woorden niet herschrijven — geldt onverkort.
- **`test_een_rol_zonder_mens_valt_terug_op_de_wachtrij`** heet nu `..._valt_terug_op_een_mens`.
- **`MENS_GETYPT` is uit `_act_notif_add` gehaald**, met een assert dat hij er níét meer staat: het
  merk waarschuwt een poort die op dat pad niet meer draait, en een merk tegen een gevaar dat niet
  bestaat is ruis.
- Waar een telling op één stond terwijl de rol twee vervullers heeft, telt de test nu het **aantal
  vervullers** in plaats van een los getal — anders breekt hij zodra iemand het zaad aanpast, om de
  verkeerde reden.

### Twee bestanden die ik niet heb aangeraakt

`claude/implementatiebrief_opruiming_19sept.md` heeft 110 regels ongecommitte wijzigingen en
`claude/ux_voorstel_best_practices_20sept.md` is nieuw — allebei van Stefan, tijdens dit werk. Ik
laat ze staan; ze horen niet in een commit van mij. (De brief kondigt ook een **fase 11** aan over
UX-microinteracties; die heb ik niet opgepakt.)

## De migratie is uitgevoerd op productie

**20 september, 09:45–09:55.** Snapshot `backups/data_2026-09-20_0945.tgz` (100 MB, 2.070
bestanden), deploy naar `8ecf29a`, droogloop, en na akkoord `--apply`.

```
notificaties  371   geschreven 371   bestond al 0   geparkeerd 0   DM-kanalen 41
routering:    vervuller 308 · persoon 33 · terugval 30
berichten in de kanalen: 371  (+ 0 geparkeerd = 371)      ✓ alles verantwoord
```

Nagelopen ná het schrijven, op de echte store:

| controle | uitkomst |
|---|---|
| berichten in de 41 DM-kanalen | 371, allemaal `kind="notificatie"` |
| elke notificatie-id terug te vinden | **ja**, 0 kwijt |
| berichten met een lege tekst | **0** |
| tijdspanne | 30 juni 2026 – 19 september 2026 |
| `NotifStore` | **371 rijen, onaangeroerd** |

Per ontvanger: Stefan 351 · Lotte 14 · Matthijs 5 · Wytse 1.

De `terugval` is 30 en niet 19: de elf rijen op rollen met twee vervullers horen er sinds het
besluit van vanochtend bij. 19 + 11 = 30, en `geparkeerd` staat daarmee op 0.

Services actief, `/`, `/messages` en `/inbox` alle drie 303, geen fouten in de logs.

**`NotifStore` staat er nog** — dat is de hele opzet van twee stappen: de bron blijft naast de
kopie staan tot iemand heeft kunnen kijken of de 371 leesbaar zijn aangekomen.

## B2 — begonnen, en opnieuw bewust gestopt vóór de commit

Staat in de stash als `B2-wip`. De boom is groen en gelijk aan wat er op prod draait.

### Wat er af is (in de stash)

- de twee laatste `st.notif.add`-plekken om naar `_signaleer` — **`.notif.add` komt nergens meer voor**
- `_act_verzoek_besluit` (113 regels) en zijn registratie eruit, vindkaart bijgewerkt
- acht beslis-tests uit `test_wiki_verzoek.py` verwijderd, met de reden in het bestand
- drie routerings-tests in `test_inbox_flows.py` omgezet naar DM-assertions

### Een echte bug die dit blootlegde

**Het pagina-voorstel verloor zijn inhoud.** De DM droeg alleen het zinnetje *"voorstel voor pagina
HyphaLite: hier ontbreekt de herkomst"* — de voorgestelde tékst zat in `extra["pagina"]["body"]`,
dat het inbox-scherm uitklapte. Zonder dat scherm krijgt de ontvanger "iemand stelt iets voor"
zonder wát, en dat is geen suggestie maar een raadsel. Juist bij dit besluit telt dat: de afspraak
is dat de rolvervuller de pagina zélf aanpast als hij het ermee eens is, en daar heeft hij de tekst
plus de permalink voor nodig. `wiki.voorstel_velden` zet ze nu in het bericht.

Dat is precies het soort ding dat alleen zichtbaar wordt door te kijken wat de mens ontvangt.

### Waarom ik stop

Na die stappen staan er nog **acht** falende tests, en ze horen niet bij deze stap:

| test | hoort bij |
|---|---|
| `test_weigeren_houdt_zijn_eigen_woord` | de herschrijf-poort |
| `test_onbewerkt_doorzetten_telt_niet_als_mensgeschreven` | `MENS_GETYPT` |
| `test_bewerken_maakt_het_wel_jouw_tekst` | idem |
| `test_de_suggestie_annoteert_maar_verplaatst_niets` | de triage-band van het inbox-scherm |
| vier andere | `notif_outcome` — een inbox-actie die in B2b verdwijnt |

Ik hoopte op een knip waar B2a op zichzelf groen kan zijn. Die is er niet: de overgebleven
afnemers van `NotifStore` zijn de inbox-acties en de poort, en die vallen pas weg in B2b/B2d. Ze nú
herschrijven is werk voor een scherm dat over een stap verdwijnt.

De echte omvang van wat er nog ligt, gemeten:

```
views/inbox.py        1.182 regels   — levert ook `_at_doelen` aan checklists.py en cockpit2
notifications.py        428 regels
bevinding.py            453 regels   } de poort
zelf_verwerking.py      402 regels   }
spanning_ontstaat.py     59 regels   }
vier dispatch-acties: notif_outcome · notif_klaar · notif_archive · notif_delete
twee routes + de lade-chrome + `_person_targets` + `_person_role_options`
```

Dat is één aaneengesloten stuk, geen vier losse commits: haal je de acties weg zonder het scherm,
dan staat er een scherm met dode knoppen; haal je het scherm weg zonder `_at_doelen` te verhuizen,
dan breken de checklists.

**Mijn voorstel: B2 als eigen beurt, in één aaneengesloten verwijdering, met de suite als
leidraad.** De stash is het startpunt; niets is verloren. En de volgorde uit de scope blijft staan:
de poort (drie modules) gaat er als láátste uit, zodat een fout in de omzetting niet in dezelfde
commit zit als een dode-code-opruiming.
