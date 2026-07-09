# Werkafspraken NoochVille

Afspraken die we onderweg hebben verdiend, niet verzonnen. De volgende
sessie opent hiermee.

## Pulsen
- Een puls draait standaard via `once-sandbox` (tegen een wegwerp-kopie
  van data/). Commando: `./venv/bin/python -m nooch_village.village once-sandbox`
- `once` tegen `data/` is de bewuste uitzondering, nooit de gewoonte.
- Een puls is GEEN verificatiemiddel. Wil je checken of een wijziging
  klopt, doe dat met een test of een read-only inspectie, niet met een puls.
- De sandbox isoleert je data, niet je credentials: een sandbox-puls doet
  echte externe calls (Plausible, Google News, straks Shopify). Bewuste grens.
- `--keep` laat de wegwerp-kopie staan zodat je de output kunt inzien;
  ruim die tmp-map daarna zelf op.

## Werkwijze met Claude Code
- Eén scope per opdracht. Geen bundels van vijf wijzigingen.
- Altijd de diff tonen voordat er iets wordt opgeslagen.
- Vóór elke commit die `dispatch`, gedeelde helpers of andere breed
  gebruikte code raakt: draai de **volledige** testsuite
  (`./venv/bin/python -m pytest tests/`), niet alleen het geraakte
  testbestand. Reden: de authz-gates op `dispatch` braken cross-file
  tests die bij een enkel-bestand-run onzichtbaar bleven — en zo gepusht
  werden. Enkel-bestand-run is prima tijdens het bouwen; de volle suite
  is de poort vóór de commit.
- Pablo (de chat) checkt tussen elke stap; Stefan plakt terug wat Claude
  Code rapporteert.
- Niets naar de server tot Stefan lokaal akkoord is. `push_data.sh`
  overschrijft de server.
- Draai altijd met `./venv/bin/python` of een geactiveerde venv, niet
  systeem-`python3` (mist requests e.d.).
- Server-data is source of truth. Lokale data-wijzigingen worden NIET
  via push_data.sh blind naar de server gestuurd. De volgorde is altijd:
  (1) server-staat ophalen, (2) lokaal-server diff tonen, (3) per
  wijziging expliciet akkoord vragen, (4) bij akkoord overschrijven,
  (5) bij geen akkoord lokale wijziging verwijderen. Code-deploys volgen
  een eigen pad (git pull op de server) en zijn los hiervan.
- Bij handmatige server-commando's als root: altijd daarna
  `chown -R nooch:nooch /opt/noochville/data` draaien, anders kan de
  service de bestanden niet lezen.
- Tests die data-afhankelijke renders testen (bijv. shopify-tegels) moeten
  zelf hun testdata zaaien in hun tmp-map. Nooit leunen op bestanden in de
  repo-root `data/` — die zijn gitignored en bestaan niet in CI.
- Elke nieuwe `dispatch`-tak krijgt een `# AUTHZ: <keuze> — <waarom>`-label uit
  de vier vaste opties. Volledige regel + helpers in CLAUDE.md ("Autorisatie —
  elke nieuwe dispatch-tak"). Geen tak zonder bewuste autorisatiekeuze.

## Open aandachtspunten
- LLM-advies-stappen lezen je strategie/beleid nog niet: ze gaven al
  off-strategy output (Google Ads terwijl Nooch geen advertising voert;
  een VERDICT dat zichzelf goedkeurt "op de missie"). Vóór live gebruik
  inbouwen dat advies tegen je beleid getoetst wordt.
- Puls-output (notes.json, output/) is nog niet zichtbaar in cockpit2
  (leest attachments.json). De transparantie-brug bestaat nog niet.
- Lokaal en server-governance divergeren. Verzoenen vóór de eerstvolgende deploy.
- CSS-default-details: de globale details{}-regel in cockpit.py:504
  geeft elke <details> een card-uiterlijk. Negen plekken in de
  cockpit erven dit wrapper-kader (waaronder .m-add "+Link" en
  .tile-info), vijf plekken overschrijven het al ad-hoc. Symptoom:
  visueel dubbel kader rond pill-buttons en info-iconen.
  Structurele fix: globale details{}-default kaal maken, expliciete
  .box-details introduceren voor echte cards. Niet ad-hoc oplappen.
- Autorisatie-laag ontbreekt: elke ingelogde gebruiker mag nu alles
  in de cockpit. Drie samenhangende stappen ontbreken: (a) de
  sessie-gebruiker doorgeven aan dispatch, (b) een leadlink-check
  (is filler van {circle}__circle_lead), (c) een patroon voor
  "actie X mag door Y, anders 403". Eerste use case die dit
  blokkeert: afwezig-status op de members-tab (puur informatief,
  member zelf + leadlink). Niet ad-hoc bouwen — eerst het patroon.
- Werkoverleg-presence draagt gedrag (taken pauzeren), is
  session-scoped en niet bruikbaar als algemene aan/afwezig-status.
  Voor een standalone "afwezig"-status op de members-tab een apart
  veld nodig. Keuze: per cirkel+persoon (data/availability.json) of
  per persoon (in people.json).
- Deliverable-notes in `p["log"]` hebben geen id (alleen `add_feed_entry`
  heeft er een). Consumenten verwijzen daarom op `project_id` en lezen de
  wall integraal. Zodra een consument één specifieke note moet aanwijzen:
  het id-patroon van `add_feed_entry` overnemen voor `add_role_message`.
- `project_completed` dekt alleen autonome afronding (via
  `Inhabitant._claim_run_complete`); mens-DONE via `cockpit2._act_proj_done`
  is een apart proces en bereikt de in-memory bus niet. Heroverwegen bij de
  netwerk-bus-naad.
- Stale-daemon-les (09-07): een daemon die een deploy-restart mist draait stil
  door op een oude build (de nachtpuls draaide op een build van de vorige avond
  en viel niet door naar de werkende LLM-trede). Bij rare nachtelijke output
  eerst `pid` + starttijd van het proces matchen met de laatste deploy vóór je
  de code verdenkt. Kandidaat-micro-scope: git-hash + processtart loggen bij
  `dag_begint`.
- Micro-scope open: `reason()` in `llm.py` splitst "geen antwoord (geen sleutel
  of leeg)" nog niet in geen-sleutel / lege-respons / weggevangen-exceptie (de
  `_try_*` vangen auth/timeout weg als `None`). Bemoeilijkte de diagnose van
  09-07; een fijnere uitsplitsing zou de laddertoestand direct leesbaar maken.
- Mention-ontwerp: v1 bestaat (09-07). Een `@persona` op de project-wall laat die
  persona eenmalig meedenken — het antwoord ontstaat synchroon in het **cockpit-proces**
  (`_reply_to_mentions` → `_ai_reply`), als een gesprek. Bewust licht: geen daemon,
  geen inbox-job, cap op `mention_reply_limit`, fail-closed. Open punt versmald tot de
  **zware variant**: een mention als **inbox-job in de daemon**, voor wanneer een mention
  wérk moet worden (een toegewezen taak die áf moet) in plaats van een reactie. Dat is de
  postbus-route (Inbox + matchmaker), niet de wall — pas bouwen als de behoefte er is.
