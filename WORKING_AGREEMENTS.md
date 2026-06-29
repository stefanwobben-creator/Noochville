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
- Pablo (de chat) checkt tussen elke stap; Stefan plakt terug wat Claude
  Code rapporteert.
- Niets naar de server tot Stefan lokaal akkoord is. `push_data.sh`
  overschrijft de server.
- Draai altijd met `./venv/bin/python` of een geactiveerde venv, niet
  systeem-`python3` (mist requests e.d.).

## Open aandachtspunten
- LLM-advies-stappen lezen je strategie/beleid nog niet: ze gaven al
  off-strategy output (Google Ads terwijl Nooch geen advertising voert;
  een VERDICT dat zichzelf goedkeurt "op de missie"). Vóór live gebruik
  inbouwen dat advies tegen je beleid getoetst wordt.
- Puls-output (notes.json, output/) is nog niet zichtbaar in cockpit2
  (leest attachments.json). De transparantie-brug bestaat nog niet.
- Lokaal en server-governance divergeren. Verzoenen vóór de eerstvolgende deploy.
