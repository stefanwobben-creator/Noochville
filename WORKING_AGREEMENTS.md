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
- Server-staat is niet uit de repo af te leiden: `/opt/noochville/.env` en
  `LLM_LADDER` op prod kunnen vendors/keys bevatten die de repo niet kent. Bij
  deploy-adviezen ('deploy niet nodig', 'activeren kan later') eerst de
  server-staat opvragen of aangeleverd krijgen; nooit vanaf de repo concluderen
  dat config inactief is.
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
- Prep-idempotentie-guard is titel-gebaseerd: `prepare_project` slaat alleen over als er al een
  checklist met de eigen titel `"Uitvoerplan"` bestaat (`_project_checklist`). Een mens-checklist met
  een ANDERE titel voorkomt de prep-checklist dus niet — een puls kan er een tweede `"Uitvoerplan"`
  naast zetten (bestaande items blijven wel intact; prep overschrijft nooit). Workaround: een
  mens-checklist die de prep moet vervangen `"Uitvoerplan"` noemen. Structurele fix (guard op de
  aanwezigheid van élke checklist, niet alleen die titel) is een eigen scope.
  **Urgentie verhoogd (skill-aanbod-scope):** het stille skill-aanbod bij checklist-toevoeging biedt
  bewust alleen aan op de `"Uitvoerplan"`-checklist, juist omdat alleen die door de daemon wordt
  uitgevoerd. Zolang de title-guard bestaat, blijft een item in een anders-getitelde mens-checklist
  onaangeboden én onuitgevoerd — dat maakt de structurele-fix-scope nu urgenter.
- Mention-ontwerp: v1 bestaat (09-07). Een `@persona` op de project-wall laat die
  persona eenmalig meedenken — het antwoord ontstaat synchroon in het **cockpit-proces**
  (`_reply_to_mentions` → `_ai_reply`), als een gesprek. Bewust licht: geen daemon,
  geen inbox-job, cap op `mention_reply_limit`, fail-closed. Open punt versmald tot de
  **zware variant**: een mention als **inbox-job in de daemon**, voor wanneer een mention
  wérk moet worden (een toegewezen taak die áf moet) in plaats van een reactie. Dat is de
  postbus-route (Inbox + matchmaker), niet de wall — pas bouwen als de behoefte er is.
- Policy-body-cap (4000 tekens) kapt STIL af: `AttachmentStore.add`/`update`
  doen `body.strip()[:4000]` zonder waarschuwing. Gevolg gezien (09-07): de
  Tone-of-Voice-policy én de Design-System-policy stonden op exact 4000 en
  waren onopgemerkt afgekapt (ToV miste de Contrast-Principle-check + de 5e
  position statement; Design System is nog afgekapt — apart besluit). Minimale
  fix later: bij overschrijding WEIGEREN of WAARSCHUWEN i.p.v. stil trunceren;
  overweeg de cap te verhogen. Tot dan: lange policies splitsen (zoals ToV →
  Tone of Voice + Position Statements) en na opslaan de body-lengte checken.
- Note-artefacten hebben een JSON-body (max 4000 tekens in `attachments.json`),
  géén `.md`-bestand. De wall-outcome-`note` weigert nu bewust bij >4000 i.p.v.
  te trunceren. Wens: een echt `.md`-artefact bij de rol voor afgeronde kennis
  (bestand op schijf i.p.v. JSON-body). Eigen scope.
- DONE→ACTIEF wist `outcome` (in `reopen()`) en de dagpuls voltooit een compleet
  ge-vinkte checklist meteen opnieuw met een vals `project_completed`-event. De
  wall-outcome-`action` beschermt hiertegen door de VOLGORDE (eerst het open
  checklist-item toevoegen, dán `reopen()`, zodat de checklist incompleet is).
  Een structurele guard in `reopen()` of de puls (geen re-complete zonder nieuw
  werk) is een eigen scope.
- SPA-shell (shellSwap + cleanup-registry + guard-test) ligt klaar op branch
  `feature/callbar-shell-primitive`, PR #175, groen. Opgepakt worden zodra
  paginanavigatie zelf een spanning wordt. Niet gemerged: de call bar-spanning is
  opgelost via de iframe (#173), en de shell laat de bar afhankelijk van correcte
  cleanup per content-script (het cleanup-contract moet per shell-genoot-pagina kloppen).
- Call bar reconnect (~1s) bij elke paginanavigatie (node-links, breadcrumbs,
  "navigeren tussen projecten") én bij `wo_close`. Bewust geaccepteerd: de spanning
  is klein bij ~4 gebruikers en korte calls. Oplossing ligt klaar: #175 (SPA-shell)
  + 1a (link-interceptor). Bouwen zodra het knelt.
