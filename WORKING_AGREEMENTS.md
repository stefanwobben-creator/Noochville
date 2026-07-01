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
