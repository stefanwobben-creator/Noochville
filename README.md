# NoochVillage (werkende kern)

Een event-driven dorp van autonome inwoners (rollen) met echte skills. Dit is de
gereduceerde, *draaiende* kern: de coördinatie-architectuur plus drie echte skills.
Geen simulatie, geen mock: de skills doen echt I/O.

## Wat er in zit

- **EventBus** (het marktplein): broadcast van feiten, geinjecteerd, geen global singleton.
- **Inbox** per inwoner: toegewezen werk dat af moet. Interface, dus later vervangbaar door Redis/SQS.
- **Inhabitant** (leaf, een rol per inwoner) en **Circle** (composite): van buiten een rol, van binnen een dorp. Het dorp zelf is de wortelcirkel, dus een subcirkel nest later gratis.
- **Matchmaker**: routeert "wie kan dit?" naar de inbox van een capabele inwoner.
- **Governance**: `Records` (de waarheid) + `Secretary` (records bijhouden, geen veto) + `Reconciler` (bouwt het levende dorp uit de records, herlaadt DNA bij wijziging).
- **Skills**: `SiteHealthSkill` (echte GET), `BudgetSkill` (echte mutatie op disk), `PlausibleSkill` (echte Plausible API).

## Draaien op je MacBook

```bash
cd noochville
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m nooch_village.village        # voert de demo uit met echte skills
```

Voor de Plausible-skill: kopieer `.env.example` naar `.env` en vul je key in.
Zonder key faalt die skill bewust "closed" (geen mock), de rest draait gewoon door.

## De demo bewijst (wat de live run liet zien)

1. `site_health` doet een echte GET op nooch.earth (status 200, echte paginatitel).
2. `plausible_stats` doet de echte API-call en faalt closed zonder key.
3. `budget_adjust` faalt eerst, want analyst heeft die skill nog niet.
4. Een governance-voorstel kent analyst de budget-skill toe terwijl hij draait (DNA -> v2).
5. `budget_adjust` schrijft daarna een echte mutatie naar `data/budget.json`.
6. Een inwoner senst een spanning op het marktplein.

Alle resultaten gaan naar `data/system_log.jsonl` (audit-trail).

## Een nieuwe skill toevoegen (het echte uitbreidpunt)

```python
from nooch_village.skills import Skill

class TrendsSkill(Skill):
    name = "google_trends"
    description = "Analyseert Google Trends via pytrends."
    def run(self, payload, context):
        from pytrends.request import TrendReq
        ...
        return {"keyword": payload["keyword"], "interest": ...}
```

Registreer hem in `village.py` en geef een inwoner de capability via governance.
Je oude `trends_analyst.py`, `trustpilot_agent.py`, `get_gsc_data.py` en `repository.py`
porteer je zo een voor een naar `Skill`-klassen: de echte logica zit er al in, alleen
de basisklasse en de dode mock eruit.

## Pad naar web + mensen in het dorp

Geen architectuurwijziging nodig, alleen adapters op bestaande naden:
- **Web**: vervang de in-memory `EventBus` door een netwerk-bus (WebSocket/SSE) en de
  `Inbox` door een server-backed queue. Beide zitten al achter een interface.
- **Mens in het dorp**: een mens is gewoon een `Inhabitant` waarvan de "skill" een mens is.
  Een `HumanProxy`-inwoner zet de taak in een UI en wacht op het antwoord-event. Voor de
  rest van het dorp niet te onderscheiden van een agent.

---

## De groei-puls (nieuw)

Elke ochtend wekt de `TimeKeeper` de `GrowthAnalyst`. Die haalt zelf echte data op
(Plausible-verkeer + Google Trends), duidt die tegen je missie en schrijft een
**Field Note** in `data/output/field_note_<datum>.md`. Daalt het verkeer fors, dan
senst hij een spanning.

Draaien:

```bash
python -m nooch_village.village          # demo: snelle hartslag, toont de note
python -m nooch_village.village once      # één echte puls en stoppen (voor cron)
python -m nooch_village.village run       # blijft draaien, puls 1x per echte dag
```

Elke ochtend automatisch via cron (bijv. 07:30):

```bash
crontab -e
# voeg toe (pas het pad aan):
30 7 * * *  cd /pad/naar/noochville && ./venv/bin/python -m nooch_village.village once
```

Keywords voor Trends pas je aan in `config/keywords.txt` (één per regel).
Zonder Plausible-key of LLM-key draait de puls gewoon door en valt de note terug
op een deterministische samenvatting.
