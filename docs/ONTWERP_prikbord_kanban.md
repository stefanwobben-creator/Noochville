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

1. **Datamodel** — `future` als default, het 3-velden-DoD-contract, project-`links`, WIP-instelling,
   en de prikbord-store (verzoek/uitkomst, status, tag, links). + één handmatig gevulde keten als bewijs.
2. **Autonome pull-loop** in de puls — claim + WIP-bij-elke-activering + ancestor-guard + spaced
   repetition + fallback naar mens.
3. **Cockpit** — prikbord-weergave + projectgraaf + stuwmeer-per-rol + WIP-knoppen.
4. **Discovery-rollen bedraden** — Harry/Trends/Scout → uitkomsten → Librarian-review.

Reproduceerbaarheid: `python tools/prikbord_sim.py` (de dynamiek-stresstest).
