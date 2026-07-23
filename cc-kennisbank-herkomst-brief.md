# CC-opdracht: kennisbank-herkomst — bron/datum automatisch mee, signalen promoveren

**Voor:** Claude Code in de Noochville-repo, eigen branch (`kb-herkomst`), los van `inwoner-dossiers`.

**Doel in één zin:** wat de intake al weet (de geplakte URL, de geüploade PDF, de publicatiedatum) komt vanzelf als klikbare herkomst op elk kenniskaartje terecht, en een goedgekeurd radar-signaal is met één klik (of automatisch) te promoveren tot kenniskaartje — zodat het aparte "bronlink"-paneel de uitzondering wordt in plaats van de gewoonte.

## Waarom (de gevoelde spanning, letterlijk van de founder)

De items onder Signals & Insights zijn perfect: uitgeschreven, met datum en link naar de externe
bron. De kenniskaartjes hebben dat niet — terwijl we bij het invoeren de PDF of link al delen.
Nu lijkt het alsof die info nergens is opgeslagen, en moet de bron er per kaartje nóg een keer
handmatig bij (bronlink-paneel). En de kennisbank wordt juist rijk als signalen kaartjes worden.

## Wat er al staat (de velden bestaan, de piping ontbreekt)

- Atoom-model: `source`, `reference` (DOI/ISBN/URL), `source_date`, `created_at` — zie
  `kennisbank.py` (o.a. `_recency_weight` gebruikt `source_date` al).
- Intake: `kennisbank_sources.van_url/van_pdf/...` extraheert tekst; `kennisbank_intake` kent een
  `source_hint`; de prompt verbiedt nu expliciet de artikel-URL in `reference` (regel ~92).
- Handmatige reparatie bestaat: acties `kb_atoom_reference` (URL) en `kb_atoom_ref_pdf`
  (PDF-opslag + koppeling) in cockpit2 — hergebruik dát opslag-/koppelmechanisme.
- `IntakeCache` (kennisbank_intake, ~regel 220) onthoudt per intake-run `raw + source_hint →
  atom_ids` — de brug voor koppeling én backfill.
- Radar-items hebben `source`, `link`, `published_at` (`radar_store.py::add`).

## Taak 1 — Herkomst automatisch mee bij intake

- **URL-intake:** de geplakte URL wordt `reference` op ELK atoom uit die run — tenzij de
  LLM-extractie voor dat atoom al een eigen expliciete reference vond (DOI/ISBN uit de tekst);
  die wint. Pas de intake-prompt-regel aan die dit nu verbiedt.
- **PDF/bestand-intake:** sla het bestand op via hetzelfde mechanisme als `kb_atoom_ref_pdf` en
  koppel het als reference op alle atomen van de run. Eén opgeslagen kopie, meerdere kaartjes
  mogen ernaar wijzen. Idempotent bij her-intake (stable_id-dedupe bestaat al).
- **source_date:** laat de intake-LLM een publicatiedatum meegeven als die uit de tekst blijkt
  (ISO `YYYY-MM` of `YYYY-MM-DD`; onzeker → leeg laten, nooit gokken). Fail-soft: geen datum is
  prima, `created_at` is het vangnet.
- **Acceptatie:** plak een URL → alle nieuwe kaartjes tonen een klikbare bron; upload een PDF →
  idem met de PDF; niets handmatigs nodig.

## Taak 2 — Herkomst tonen op het kaartje

- Elk atoom in de bibliotheek (rechterkolom, detail, staging-review) toont: `source` ·
  datum (`source_date`, anders `created_at`, gelabeld "toegevoegd") · klikbare `reference`
  (URL → link; opgeslagen PDF → download/view; DOI → doi.org-link).
- Het bronlink-paneel blijft bestaan als correctie/aanvulling, maar krijgt een rustiger plek
  (alleen tonen als er nog géén reference is, of achter het bestaande uitklap-patroon).
- **Acceptatie:** het screenshot-scenario (EACB-kaartje) toont bron + datum + klikbare link
  zonder dat de mens iets extra's deed. Ratchet-tests (inline styles, labels) blijven groen.

## Taak 3 — Backfill: bestaande kaartjes hun herkomst teruggeven

- Loop de `IntakeCache`-entries langs: is de `source_hint` een URL en hebben de gekoppelde
  `atom_ids` nog geen reference → zet hem alsnog. Rapporteer aantallen (gezet / overgeslagen).
- Eénmalig CLI-commando (bv. `python -m nooch_village.village kb_backfill_herkomst`), dry-run
  eerst, backup van notes/kennisbank-bestanden vóór de echte run. Geen LLM nodig.
- **Acceptatie:** dry-run-output klopt; na de run tonen oude kaartjes waar mogelijk hun bron.

## Taak 4 — Signaal promoveren tot kenniskaartje

- Op elk GOEDGEKEURD radar-item (wachtrij-archief, /signals en de Tools-tab-weergave): knop
  **"→ kenniskaartje"**. Die maakt via het normale intake-pad één atoom aan met:
  content = signal-content (evt. door de intake-LLM geatomiseerd), `source` = signal.source,
  `reference` = signal.link, `source_date` = signal.published_at. Markeer het radar-item als
  gepromoveerd (chip + link naar het kaartje), zodat de knop niet twee keer vuurt.
- **Merge in plaats van duplicaat:** bestaat er al een atoom met hetzelfde `stable_id` (of
  dezelfde genormaliseerde reference), maak dan géén tweede kaartje maar koppel het signaal als
  extra herkomst/steun aan het bestaande atoom en meld dat in de banner ("samengevoegd met …").
- **Automatisch (optioneel, default UIT):** config-vlag `radar_auto_promote = 0|1`. Bij 1
  promoveert elke radar-goedkeuring meteen. Start mens-gated; de vlag is de opt-in zodra het
  vertrouwen er is.
- **Acceptatie:** promoveer het Ecolabel-signaal → kaartje met datum + EACB-bron + klikbare
  link; tweede keer promoveren → merge-melding, geen duplicaat; met de vlag aan gebeurt het
  bij approve vanzelf.

## Volgorde & werkwijze

1 → 2 → 3 → 4, per taak tests + volle suite groen. Let op de lopende branches: raak
`inwoner-dossiers`-bestanden niet aan; kennisbank-modules zijn recent verbouwd (staging/atomise),
dus lees eerst de actuele versies. Prod-data (notes/kennisbank/radar op de server) alleen via
de stores en met backup; de backfill is de enige bulk-schrijf en heeft een dry-run.

## Guardrails

- Nooit een reference overschrijven die een mens expliciet zette (expliciet > afgeleid).
- Datum nooit gokken: extractie of leeg.
- Promotie is mens-gated tot de vlag bewust aan gaat; merge boven duplicaat, altijd.
- Opgeslagen PDF's: één kopie per bestand, geen groei door her-intake; geen externe uploads.
