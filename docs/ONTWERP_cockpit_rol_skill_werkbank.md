# NoochVille: Ontwerpnotitie — Cockpit als rol/skill-werkbank (2026-06-18)

*Blauwdruk, geen implementatie. Vastgelegd zodat de volgende sessie hierop bouwt en niet op herinnering. Bouw niets van dit document zonder eerst `docs/STATE.md` en `CLAUDE.md` te lezen en de spelregels te respecteren (mens-gated activatie, diff vóór commit, spine blijft dom, records = de waarheid).*

---

## Waarom deze upgrade

Het doel is tijdwinst, niet een fancy dashboard. De inhoudelijke meerwaarde van het dorp zit straks in het maken en uitbreiden van rollen en skills. De cockpit moet dat goedkoop maken, en als bijvangst de operationele triage.

Nu is Stefan zelf de observability-laag: `system_log` grep-pen, `governance_records.json` met de hand lezen, `inbox list` draaien, cleanup via JSON-bewerking. Dat vreet het 10-uur-budget. Drie gaten:

1. Geen plat zicht op de roster. `python -m nooch_village.village roster` toont records met source-legende, maar verspreid over de terminal, niet naast de inbox en het proces.
2. Rol/skill-werk is een meerstaps-loop (roles.py, skill schrijven, registreren, amend via een losse one-liner of CLI-handler die een hele Village opspint, gate-uitkomst aflezen, record-versie checken). Foutgevoelig en attention-zwaar.
3. Triage is JSON-bewerking. Werkbaar voor MVP, expliciet niet schaalbaar (STATE.md).

---

## Grondslag: de cockpit is de mens-kant van de auth-grens

Het dorp kent al een geauthenticeerd lokaal oppervlak (inbox/CLI) waar de mens approvals doet. De cockpit voegt zich daarbij. Hij is mens-gereedschap, geen nieuwe actor in het dorp.

Twee activiteiten, scherp gescheiden, want ze verdienen verschillende frictie:

- **Authoring**: Stefan ontwerpt of breidt bewust een rol of skill-toekenning uit. Hier is lage frictie júist goed, want het nadenken heeft al plaatsgevonden.
- **Reviewing**: een gesenst voorstel (means_gap, C-suggestie, activatie) goedkeuren. Review-dan-submit: de fit-check blijft een bewuste stap, geen auto-klik. Dit is het patroon "AI stelt plausibel-maar-soms-fout voor, de mens/gate fit-check is de feature".

---

## Twee harde grenzen (die dit veilig maken in plaats van roekeloos)

1. **Alles via de gate.** De cockpit stelt een `amend_role`/`add_role` samen en stuurt die door `Village.submit_proposal` → G0-G4 → Secretary adopt, net als de inbox-CLI (proposer: `human-cli`). Hij patcht nooit `governance_records.json` rechtstreeks. Een browser-knop die regelrecht een store schrijft is sneller te bouwen en is precies de val: dan ontstaat een tweede mutatie-bron die gate, dedup en provenance omzeilt. De cockpit is een dunne client over het bestaande commando-oppervlak (HARDE REGEL 3: records = waarheid, reload, geen state buiten het record).

2. **Skills zijn code.** De cockpit kent een bestaande skill toe en benoemt een ontbrekende, maar mint nooit een skill vanuit een knop. Een nieuwe skill is een module in `skills_impl/` plus registry-entry plus per-edit review (HARDE REGEL 5 en 10, born-versus-activated). De cockpit toont "rol X mist skill Y" en stuurt naar de means-gap. Verwacht geen skills-minten vanuit het scherm.

---

## De auth-grens, concreet (niet overbouwen)

- Lokaal, single-user: bind uitsluitend op `127.0.0.1`, weiger een niet-lokale host. Geen OAuth-circus zolang het jouw machine is.
- **Step 1 (read-only) heeft geen schrijfpad**: `POST` geeft `405`, alleen `GET /` wordt geserveerd. De grens is dan triviaal: alleen lezen, alleen localhost.
- **Step 2 en verder (write)**: elke schrijfactie loopt via het bestaande gevalideerde commando-pad. De AI-kant (Noochie, inhabitants) krijgt via de cockpit nul schrijfhefboom. De firewall blijft heel.

---

## Bouwvolgorde (decompositie, geen big-bang)

1. **Read-only roster + store-views** (records / inbox / projects-grootboek als proces-kolom). Pure `gather` + `render`, stdlib `http.server`, localhost. Geen Village, geen netwerk, geen nieuwe dependency. Goedkope basis, direct nuttig: je ziet de rollen plat met purpose, accountabilities, domeinen, skills, versie en source.
2. **Rol/skill-authoring**: formulier dat een `amend_role`/`add_role` samenstelt, valideert tegen de `SkillRegistry` (pre-submit, vangt spook-skills vóór adoptie, lost bestaande schuld op), en via de gate indient. Inclusief persona-velden (leesbare naam los van `role_id`, MBTI), die los je en passant op nu de rollen nog weinig zijn.
3. **Gesensede voorstellen review-dan-submit** in dezelfde view: means_gap → amend_role, C-suggesties ter inspectie, activaties green-light.
4. **Lichte triage als byproduct**: keyword-escalaties, cleanup-31, extract_terms-review via `library.curate()` en het bestaande apply-pad.

---

## Wat dit oplost van de bestaande ontwerpschuld

- "Triage via JSON-bewerking niet schaalbaar" → step 4.
- "Gate-check `add_skills` (spook-skill sneuvelt pas na adoptie)" → pre-submit-validatie in step 2.
- "Rol-metadata/persona-laag (leesbare naam + MBTI)" → velden in het authoring-formulier, step 2.
- "Lichtgewicht governance-CLI start een hele Village per submit" → blijft staan; cockpit-authoring deelt dat pad tot het governance-ritueel governance een Village-staat maakt. Niet vooruitbouwen.

---

## Verhouding tot het governance-ritueel (stap 1 in STATE.md)

- Cockpit-authoring is niet hetzelfde als het governance-ritueel (mens-als-rol, mens-getriggerd ritme, Secretary als agenda-gids). De cockpit hoeft daar niet op te wachten: hij gebruikt de bestaande `submit_proposal`-weg.
- Eén-klik-goedkeuren van zware gesensede governance-voorstellen wacht wél op, of valt samen met, het ritueel. Tot dan: review-dan-submit met bewuste fit-check.

---

## Principes die voor deze upgrade niet mogen driften

- Cockpit = mens-kant. Leest live, muteert alleen via het gevalideerde commando-pad. Nooit direct naar een store schrijven.
- Skills mint je niet vanuit de UI. Nieuwe skill = code plus per-edit review.
- Read-only blijft op localhost. Write-surface blijft op localhost én via de gate.
- Lelijk-functioneel boven mooi. Geen JS-framework, geen dependency erbij zolang stdlib volstaat.
- Inbox blijft zeldzaam en zwaar: alleen structurele beslissingen, geen operationele ruis.
- Niet vooruitbouwen: write pas na read, governance-één-klik pas met of na het ritueel.

---

## Open knoppen (genoteerd, niet beslist)

- Besloten: de cockpit wordt straks ook het werkoppervlak voor triage en approve. Dat maakt de auth-grens vanaf step 2 de kern van het ontwerp, geen nette bijzaak. Houd de write-pad-discipline daar hard.
- Persona-laag: leesbare naam plus MBTI als veld op `RoleDefinition` versus een aparte metadata-store. Te beslissen bij step 2.
- Toont de read-only roster spook-skills (skill op record maar niet in registry)? Dat vereist het bouwen van de registry (pull alle skill-imports, sommige met secrets/netwerk). Voor step 1 bewust niet. Kandidaat voor step 2, waar de registry toch geladen wordt.
- Live-refresh of auto-poll: bewust uitgesteld. Handmatig verversen volstaat, geen websockets.
