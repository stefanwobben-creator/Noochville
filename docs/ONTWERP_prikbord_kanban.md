# Ontwerp: het prikbord-dorp (Kanban + project-marktplaats)

Status: vastgelegd ijkpunt na dialoog + Monte-Carlo (tools/prikbord_sim.py). Nog te bouwen.
Idee in één zin: *it takes a village to raise a CEO* — rollen werken autonoom samen via een gedeeld
prikbord; de mens stuurt met lichte oordelen en een aan/uit-knop, en springt alleen in waar de echte
wereld geraakt wordt.

## 1. Kernmodel

Een **prikbord** (persistent, zichtbaar) naast de bestaande in-memory EventBus. Rollen hangen er twee
soorten briefjes op en halen eruit wat bij hun accountabilities/skills past (PULL, geen push):

- **Verzoek** — "ik heb hulp nodig bij X" (van rol Y, met done-criterium).
- **Uitkomst** — "ik heb dit resultaat: Z" (consumeerbaar door een andere rol of een curator).

De bus blijft het zenuwstelsel (real-time seintje "nieuw briefje"); het prikbord is het gedeelde
geheugen (blijft bestaan, jij ziet het, pull-baar door de tijd heen).

## 2. Kanban-statussen (vervangt los 'queued')

| Status | Betekenis |
|--------|-----------|
| `future` | Backlog. **Standaard.** Er gebeurt niets tot activering. |
| `active` | In uitvoering (telt mee voor WIP). |
| `waiting` | Gestokt, mét gestructureerde behoefte (*wat* nodig, *van welke rol*). |
| `done` | Afgerond → archief. |

**Master-switch:** de status van de **cluster-root** is de aan/uit-knop voor het hele gelinkte
cluster. Root op `future` = de keten staat stil; op `active` = de keten komt in beweging.

## 3. Prioritering & WIP

- **Prioritering:** een rol pakt het hoogst-scorende project dat hij kan doen. Score = business-case
  (effect × zekerheid ÷ inspanning) + voor discovery "meest achterstallig" (spaced repetition).
- **WIP-limiet:** max N `active`, instelbaar **per rol én bord-breed**. Jouw tempo-knop.
- **Claim/slot:** eerste rol die claimt is eigenaar (dedup, geen dubbel werk).

## 4. Het project-contract (definition of done)

Elk project/verzoek draagt naast de scope drie velden, zodat een rol weet wanneer hij klaar is:

1. **Uitkomst** — één zin, het concrete resultaat.
2. **Klaar wanneer** — een *checkbaar* criterium, inclusief de lege/nee-uitkomst.
3. **Gaat naar** — wie de uitkomst consumeert (rol, bord, of mens bij escalatie).

**Runtime self-check** per werkcyclus (de rol toetst output tegen "klaar wanneer"):
- voldaan → rol **stelt Done voor** (mens bevestigt; een rol sluit zichzelf nooit af) → uitkomst naar "gaat naar";
- niet voldaan, iets van buiten nodig → **waiting** + verzoek-briefje;
- niet voldaan, kan zelf door → blijft active.
Een **lege uitkomst is ook af** (0 keywords gevonden = afgerond).

## 5. Twee mens-aanrakingen

- **Focus-inbox** — lichte oordelen. Bijv. de Librarian stelt heuristisch voor; jij approve/disapprove
  + comment. (Deze fase: Librarian = heuristiek-voorstel, mens beslist.)
- **Projectbord** — echte-wereld-taken (bv. "mail de leverancier") landen hier; jij stuurt via comments.

Al het tussenliggende agent-werk loopt zónder jouw akkoord.

## 6. Projectgraaf

Projecten krijgen `links` naar verwante projecten (zoals de notes-store touwtjes legt). Een gelinkte
keten = één doorlopend gesprek tussen agents over hetzelfde onderwerp; de cockpit toont die keten.

## 7. Guardrails (gevalideerd met de Monte-Carlo)

| Guardrail | Waarom (sim-bevinding) |
|-----------|------------------------|
| **WIP toetsen bij ÉLKE activering** (ook hervatten uit waiting) | Zonder: WIP lekt (12 overtredingen, max actief 4 i.p.v. 3). Met: 0. |
| **Acyclische dependencies + ancestor-guard** | Circulaire verzoeken zonder guard → 60% verspild rondpompen (381 vs 239 projecten). |
| **Fallback naar de mens** voor onclaimbare briefjes | Een uitvallende rol legt het dorp niet plat (0 deadlocks), werk escaleert netjes. |
| **Stuwmeer per rol/tag zichtbaar** | Bij rol-uitval zwelt de mens-rij (→16); jij moet zien wáár het stokt om te herstaffen/herprioriteren. |
| **Omkeerbaarheidspoort** (bestaat al) | Onomkeerbare/echte-wereld-stap → mens; rest autonoom. |
| **Dedup op briefjes** | Geen dubbele verzoeken/uitkomsten. |

De mens blijft de bottleneck-by-design: houd mens-stappen schaars en de mens-rij prominent.

## 8. Rol-accountabilities (discovery als voorbeeld van het patroon)

- **Harry_Hemp** → seed words (lange-termijn-trendblik).
- **Trends** → related zoekwoorden per seed (+ huidige keywords); spaced repetition over de seeds;
  door de seeds heen → verzoek aan Harry voor nieuwe seeds, ondertussen oudste seed opnieuw.
- **Concurrent_scout** → zoekwoorden van concurrenten.
- **Librarian** → reviewt/cureert elke binnenkomende uitkomst (staande accountability).

Discovery is dus geen los project maar een staande accountability, uitgevoerd in afgebakende
projecten (één seed → één deliverable) waarvan de uitkomst automatisch de review-lus in gaat.

## 9. Bouw in brokken (klein & toetsbaar)

1. ✅ **Datamodel** — `future` als default, het 3-velden-DoD-contract, project-`links`, WIP-instelling,
   en de prikbord-store (verzoek/uitkomst, status, tag, links). + één handmatig gevulde keten als bewijs.
   (`pinboard.py`, `projects.py` create/link/neighbors/wait_for, `tests/test_pinboard_kanban.py`)
2. ✅ **Autonome pull-loop** (`board_loop.activate_pulse`) — WIP-bij-elke-activering + master-switch +
   resume + fallback naar mens + prioritering op business-value. (`tests/test_board_loop.py`)
3. ✅ **Cockpit** — `/prikbord`: WIP-meter, vier Kanban-kolommen, cluster master-switch, stuwmeer-
   per-rol, briefjes. (`cockpit.render_prikbord`, `tests/test_prikbord_view.py`)
4. ✅ **Discovery-rollen bedraden** (`discovery_board.py`) — afgebakende projecten (één seed → één
   deliverable) onder de discovery-cluster-root, board-gedreven, uitkomst → briefje + Librarian-
   review, spaced repetition, seeds-op → verzoek aan Harry. CLI: `python -m nooch_village.village
   discovery [aan]`. (`tests/test_discovery_board.py`)

5. ✅ **De puls bedraad** (`board_loop.run_board_pulse`) — de scheduler hing tot 28 juli 2026 aan
   niets: `activate_pulse` werd nergens aangeroepen. Hij hangt nu aan de BESTAANDE dagcadans
   (`dag_begint` → `Village._on_board_pulse`), plus `python -m nooch_village.village board_pulse`
   voor een handmatige of cron-run. Geen tweede timer. (`tests/test_board_pulse_wiring.py`)

Reproduceerbaarheid: `python tools/prikbord_sim.py` (de dynamiek-stresstest).

## 10. De puls: wie is beschikbaar, en waar zie je hem

`available_role_ids(records, data_dir, unmanned=...)` levert de bemenste, beschikbare rol-ids:
een niet-gearchiveerde ROL (geen cirkel — die heeft geen handen), niet onbemand volgens de
Reconciler, met minstens één vervuller volgens `Assignments.fillers_of` (die telt de toegewezen
lijst plus legacy `held_by`/`persona_id` mee). **Mens-vervulde rollen tellen mee als beschikbaar**:
anders zou guardrail 3 hun future-leden wegzetten als "rol is onbemand", wat feitelijk onwaar is en
alleen ruis oplevert. Alleen een rol zónder énige vervuller escaleert naar de mens.

De WIP-limieten komen uit `config/strategy.json` (`read_wip` → `{board, roles}`) — de tempo-knop
van de mens, niet van het dorp.

Elke puls is op drie plekken zichtbaar: een systeem-regel in de feed van het geraakte project, een
regel in `data/board_pulse.jsonl` (**ook bij 0/0/0** — stilte hoort een waarneming te zijn, geen
afwezigheid), en een `board_pulse_completed`-event op de bus → `system_log.jsonl`.

**Wat de puls bewust NIET doet:** een standalone/root-project (`parent` leeg) activeren. Dat blijft
mens-gestuurd. Gevolg per 28 juli 2026: op productie heeft geen enkel project een `parent`, dus de
puls beweegt daar nog niets. Dat is geen storing maar een lege invoerkant — de scheduler wacht op
cluster-projecten (zoals `discovery_board.py` ze maakt).

## 11. Signaal → projectvoorstel (hefboom 2, `project_proposals.py`)

Het dorp mag voorstellen; de mens beslist. Een voorstel komt **nooit** vanzelf op het actieve bord.

**Bronnen.** (1) Radar-signalen met status `goedgekeurd` die nog geen voorstel opleverden — het
approve is de relevantie-poort die al gepasseerd is, dit is de lichtere tweede vraag *verdient dit
een project?*. (2) Kroniek-gaten: de `leeg`-lijst uit `evidence_ledger.interpret()` per lopend
onderwerp. Bron 2 staat **default uit** (`project_proposals_kroniek = 1` zet 'm aan): anders dan een
radar-item is een kennisgat door niemand op relevantie beoordeeld, en ruis is duur.

**Status `proposed`.** Buiten élke autonome lus: `activate_pulse` kijkt naar future/blocked,
`_tend_projects` naar future/queued/running, `project_worker._eligible` naar queued/running. Het is
ook een standalone project (`parent` leeg), wat het al buiten de puls houdt — maar de garantie is
expliciet gemaakt en bevroren in `tests/test_proposed_veiligheid.py`, niet impliciet gelaten.

**Drie ruis-remmers.** *Dedup*: elke bron-referentie die ooit een voorstel opleverde staat in de
overlay `data/project_proposals.json`, ongeacht de afloop — ook een afgewezen (en dus verwijderd)
voorstel komt niet terug. *Cap*: max `project_proposals_cap` (default 10) openstaande voorstellen;
zit de baan vol, dan wordt gelogd wát is overgeslagen — nooit stil afkappen. *Formulering*:
`wizard.sharpen_outcome` maakt er één Holacracy-uitkomst in de verleden tijd van, in het Engels.

**De mens-poort** zit in de cockpit, op de projecten-tab van de rol: de baan *💡 Proposals — awaiting
your judgement*, met per voorstel `accept` (→ root-project in TOEKOMST, normale flow, de mens
activeert zelf) en `reject` (→ weg én onthouden). Handmatig draaien:
`python -m nooch_village.village propose_projects`; in de daemon draait één ronde per `dag_begint`,
naast (en na) de bord-puls uit §10.
