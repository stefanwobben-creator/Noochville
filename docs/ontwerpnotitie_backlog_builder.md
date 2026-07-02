# Ontwerpnotitie — Backlog Builder

Status: vastgelegd ontwerp, klaar voor de bouwronde. Leidende mockup: `docs/backlog_builder_screen.html`.

## Doel
Van ruw idee tot een geprioriteerd project, in twee rollen. De **inbrenger** (iedereen) tilt via een
chat met Walter een ruw idee op tot een heldere story. De **verwerker** (de rolvervuller die het domein
beheert) prioriteert, bepaalt de volgende stap, en zet het door naar het projectenbord.

## Model (canoniek)
- Eén scherm: links de chat (inbrengen), rechts de backlog (verwerken). Ze delen één bron.
- Een backlog-item ("story") heeft: titel, spanning, uitkomst, wie-baat, missie-pijler, bijlagen,
  impact, inspanning, rol (eigenaar op het bord), status, steun (stemmen), notitie/dispositie.
- **Rol = de eigenaar-rol = bij wie het als project op het bord landt.**
- Koppeling met het projectenbord: vanaf status **geprioriteerd** leeft het item ook als project
  (toekomst) op het bord, met doel- en werkpakket-koppeling zoals in `ontwerpnotitie_doelen.md`.

## De inbreng-flow (chat met Walter)
1. Ruw idee (één zin).
2. **Dedup-check:** Walter kent de backlog. Lijkt het sterk op een bestaand item, dan benoemt hij dat
   en biedt samenvoegen aan (stem +1 op het bestaande item, geen dubbele kaart).
3. **Domein-check:** raakt het idee Walters eigen domein (website), dan past hij zijn kennis toe en
   stelt domein-specifieke vragen. Raakt het een ander domein, dan verwerkt hij het niet zelf maar
   routeert met "bespreken met [rol]" en die rol als eigenaar.
4. **Vormgeven:** spanning (waarom nu), uitkomst (wanneer klaar), wie-baat, en de **missie-pijler**.
   Bij de pijler staat ook "Raakt de missie niet direct"; dan blijft de pijler leeg en krijgt het item
   de "toets missie"-vlag voor de verwerker (nooit een pijler forceren).
5. **Interpretatie:** Walter zet de ruwe woorden om in een heldere story, trouw aan wat gezegd is.
6. **Inbrengen:** het item landt rechts als **ingebracht**. De inbrenger kiest NIET klein-genoeg of
   prototype; die inschatting heeft hij niet, dat is de verwerker.

Bijlagen: de inbrenger kan altijd een link of screenshot toevoegen (📎), essentieel bij visuele ideeën.

## De verwerker-kant
- Alleen de **rolvervuller die het domein beheert** mag de backlog bewerken. Anderen zien mee (read-only)
  maar kunnen wel inbrengen via de chat.
- Scoren: **impact** (1-5) en **inspanning** (1-5) → prioriteit = impact ÷ inspanning (hoog = eerst).
- **Waarden-poort:** een item zonder missie-pijler kan niet doorgezet worden ("toets missie").
- **Dispositie (de keuze van de verwerker):**
  - Klein genoeg → prioriteren en **→ op bord** (status geprioriteerd = toekomst-project).
  - Verduidelijken → terug voor meer uitwerking of bespreken.
  - **Prototype eerst → ✦ prompt:** genereert een kant-en-klare prompt voor de voorkeurs-AI (onze eigen
    prototype-first-werkwijze ingebakken).
- Rol (eigenaar) toewijzen.

## Status-lifecycle (met bord-koppeling)
`ingebracht → verduidelijkt → geprioriteerd → actief → doen` (plus `geparkeerd`).
Bord-badge: geprioriteerd = "bord: toekomst", actief = "bord: actief", doen = "bord: doen".

## Rol-rechten (authz)
- Inbrengen via de chat: **iedereen-ingelogd**.
- Backlog bewerken (scoren, prioriteren, dispositie, doorzetten): **rolvervuller van de domein-rol of
  Circle Lead**. Fail-closed: guest mag alles (auth uit), ingelogde-onbekende geweigerd.

## Datamodel
`data/backlog.json` via een lichte `BacklogStore` (vorm zoals `ProjectLedger`): id, titel, spanning,
uitkomst, wie_baat, missie_pijler, bijlagen[], impact, inspanning, rol, status, steun, dispositie,
doel_id/werkpakket (bij doorzetten), created_at. Additief; maakt bestand aan als het ontbreekt.

---

## Walter — system-prompt (het LLM-instructieblok)

> Je bent **Walter Website**, de rol die de website-backlog van Nooch beheert. Je helpt iemand een ruw
> idee scherp te krijgen tot een heldere story die op de backlog kan. Je praat als Walter: warm,
> beknopt, nuchter, in de Nooch-stem. Geen uitroeptekens, geen em-dashes, geen hype. Eén vraag per keer.
>
> **Je taak:** zet een ruw, rommelig idee om in een story met de velden: titel, spanning (waarom nu),
> uitkomst (waaraan zie je dat het klaar is), wie-baat, missie-pijler.
>
> **Harde regels:**
> 1. **Trouw-grens.** Herformuleer alleen wat de inbrenger echt zei. Verzin geen scope, cijfers,
>    oorzaken of bedoelingen. Weet je een veld niet, stel één korte vraag, vul niets in wat niet gezegd
>    is. Doe je toch een aanname, benoem die expliciet ("Ik neem aan dat...").
> 2. **Domein.** Je kent je eigen domein (de website) en dat van de andere rollen (meegegeven in de
>    context). Raakt het idee vooral een ander domein, verwerk het dan NIET zelf. Zeg dat het bij die
>    rol hoort en bied aan het klaar te zetten als "bespreken met [rol]", met die rol als eigenaar.
> 3. **Dedup.** Je krijgt de huidige backlog mee. Lijkt het idee sterk op een bestaand item, benoem dat
>    item en vraag of het de spanning al oplost of samengevoegd moet worden. Maak nooit een dubbele kaart.
> 4. **Waarden-poort.** Koppel alleen een missie-pijler als het idee er duidelijk bij past. Past het
>    niet helder, zeg dan "raakt de missie niet direct" en laat de pijler leeg voor de verwerker.
>    Forceer nooit een pijler.
> 5. **Rol-grens.** Jij vormt en routeert. Je bepaalt NIET de prioriteit, of iets klein genoeg is, of er
>    eerst een prototype moet komen. Dat is de verwerker. Draag die keuzes niet aan de inbrenger op.
>
> **Werkwijze:** ontvang het ruwe idee → dedup-check → domein-check → als het jouw domein is, vraag
> gericht door (spanning, uitkomst, wie-baat, pijler) met website-specifieke scherpte (bug of
> verbetering, welke pagina of device) → vat samen in je eigen woorden, trouw aan wat gezegd is →
> bevestig kort → lever de story.
>
> **Output (JSON):**
> ```
> {
>   "actie": "story | routeren | samenvoegen | vraag",
>   "bericht": "<één korte zin in Walters stem voor de inbrenger>",
>   "story": {"titel","spanning","uitkomst","wie_baat","missie_pijler|null","bijlagen":[]},
>   "routeren_naar": "<rol>",          // alleen bij actie=routeren
>   "samenvoegen_met": "<backlog_id>", // alleen bij actie=samenvoegen
>   "vraag": "<één korte vraag>"       // alleen bij actie=vraag
> }
> ```

### Context die je bij elke aanroep meegeeft
- De huidige backlog-items (id, titel, spanning, status) — voor dedup.
- De domein/rol-definities en de rollenlijst — voor routering.
- De missie-pijlers — voor de waarden-poort.
- De Nooch tone-of-voice-regels — voor de stem.

Zonder deze context kan Walter niet dedupliceren of routeren; de kwaliteit van de interpretatie hangt
volledig aan deze instructie plus deze context.

---

## Bouwbrokken (klein, toetsbaar, branch per brok)
1. **BacklogStore** (`data/backlog.json`) + store. Tests. Additief.
2. **Inbreng-chat UI** (Walter) + LLM-koppeling met de system-prompt en context-injectie.
   Heuristische fallback (keyword-classificatie) als er geen LLM-key is, fail-closed.
3. **Dedup + domein-routing** (LLM, met heuristiek als vangnet).
4. **Verwerker-kant:** scoren, waarden-poort, disposities, ✦ prototype-prompt, statuswissel. Authz-poort.
5. **Koppeling projectenbord:** geprioriteerd → project (toekomst) met doel/werkpakket.
6. **Rol-rechten** conform de vier autorisatie-labels.

## Referentie
Leidende mockup: `docs/backlog_builder_screen.html`. Sluit aan op `ontwerpnotitie_doelen.md`
(project ↔ doel ↔ werkpakket) en `werkwijze_en_deploy.md` (prototype-first, additief deployen).
