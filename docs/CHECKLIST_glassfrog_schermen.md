# Checklist — GlassFrog-schermen → NoochVille cockpit

Alle schermen uit `Glassfrog.zip` doorgenomen en gemapt. Per scherm: waar het in de cockpit hoort,
de status, en de keuze (staat er al / kleine tweak / bouwen). Status-legenda:

- ✅ **staat al** in cockpit 2 (de GlassFrog-vorm, PoC)
- ⚙️ **bestaat al** in cockpit 1 (ander scherm, te integreren/porten)
- 🟡 **basis aanwezig** (opslag/datamodel werkt, UI nog te bouwen)
- 🔨 **bouwen** (nieuw)
- ➖ **n.v.t. voor ONCE** (bijv. abonnement-gating) — wel input voor ons prijsmodel

---

## 1. Cirkel- en rolpagina's (de kern)

| Scherm | Screenshot(s) | Waar in cockpit | Status | Toelichting |
|--------|---------------|-----------------|--------|-------------|
| Cirkel — Overview (purpose, strategie/kernwaarden, domeinen, accountabilities) | 01-00-28 (Mother Earth), 01-00-42, 01-01-03 | `/node` tab Overview | ✅ | Purpose/domeinen/accountabilities live. **Strategie/kernwaarden** nog grijs (🔨 per cirkel). |
| Cirkel — Roles (rollen + subcirkels) | 01-01-38, 01-02-01 | `/node` tab Roles | ✅ | Toont rollen + subcirkels uit de records. |
| Cirkel — Members (mensen) | 01-01-25 | `/node` tab Members | ✅ | Mensen uit people+assignments. |
| Rol — Overview (purpose, domeinen, accountabilities, role fillers) | 01-02-09, 01-02-18, 01-02-44 | `/node` (rol) tab Overview | ✅ | Inclusief meervoudige bezetting (mens + AI). |
| Org-kaart (cirkel-bubble-visualisatie, rechtsboven) | in alle cirkelpagina's | rechterkolom | 🟡→🔨 | Wij tonen een geneste **boom**; de bubble-SVG is een latere bouw. |
| Tab Notes | (tab in 01-0x reeks) | `/node` tab Notes | 🟡 | Attachment-store werkt; invoer-UI (zie "Add Reference") nog. Hier vouwen **concurrenten** in. |
| Tab Metrics | (tab) | `/node` tab Metrics | 🟡 | Store werkt; invoer + meeting-koppeling nog. Hier vouwt **zoekwoord-volume** in. |
| Tab Checklists | (tab) | `/node` tab Checklists | 🟡 | Store werkt; invoer + tactical-koppeling nog. |
| Tab Projects | (tab) | `/node` tab Projects | 🔨 | Projecten bestaan (cockpit 1 prikbord/ledger); koppeling per rol/cirkel + weergave nog. |
| Tab Policies | (tab) | `/node` tab Policies | 🔨 | Nu alleen harde policies op de anchor-cirkel; per cirkel nog. |
| Tab History | 01-02-26 | `/node` tab History | 🔨 | In GlassFrog premium ("Upgrade to view"). Wij hebben record-versies → goed te bouwen. |

## 2. Meetings

| Scherm | Screenshot(s) | Waar in cockpit | Status | Toelichting |
|--------|---------------|-----------------|--------|-------------|
| Governance meeting (roloverleg: rol bewerken, secretaris-check, consent) | 01.03.x reeks + (Governace.pdf) | `/roloverleg` (cockpit 1) | ⚙️ | Bestaat en is net verbouwd (brok 1-6). Te porten naar cockpit 2 + "Start Meeting"-knop. |
| Tactical meeting — Triage (spanning → Action/Project, rol + persoon, Next/Waiting) | 00-57-49 | `/tactical` (nieuw) | 🔨 | Het grootste gat. Geleide flow. |
| Tactical meeting — Project Updates / board | 00-59-29, 00-59-44 | `/tactical` | 🔨 | Projectstatus doorlopen; sluit aan op prikbord. |
| "Start Meeting"-knop (governance / tactical) | cirkelpagina's | `/node` header | 🟡 | Nu grijze knoppen in cockpit 2; koppelen aan de twee flows. |

## 3. Werk & instroom (app-breed)

| Scherm | Screenshot(s) | Waar in cockpit | Status | Toelichting |
|--------|---------------|-----------------|--------|-------------|
| Inbox (spanningen, "Process") | 01.03.03 | top-nav Inbox | ⚙️ | = onze triage (cockpit 1). Porten naar cockpit 2-nav. |
| Workspace (mijn acties / next actions / waiting) | 01-04-33, 01-04-53, 01-05-06 | top-nav Workspace | 🔨 | Persoonlijke takenlijst over rollen heen. Deels uit projecten/acties. |
| Agenda Items | 01-05-25, 01-06-10 | top-nav Agenda | 🔨 | Verzamelplek agendapunten voor meetings. |
| Proposals (async voorstellen) | 01-06-18, 01-06-30 | top-nav Proposals | 🟡 | Roloverleg-agenda bestaat; async-voorstel-lijst als eigen scherm nog. |
| Add Reference / Note (rich-text + rol-keuze modal) | 01.05.49 | modal vanuit Notes-tab | 🔨 | Invoer-UI voor de Notes-store (rich text optioneel; plain eerst). |

## 4. Persoon & account

| Scherm | Screenshot(s) | Waar in cockpit | Status | Toelichting |
|--------|---------------|-----------------|--------|-------------|
| Persoonsprofiel — Roles (gegroepeerd per cirkel, met purpose/accountabilities) | 01-08-18, 01-08-28 | `/person` | 🟡 | Wij tonen "mijn rollen" (basis). Tweak: groeperen per cirkel + accountabilities tonen. |
| Persoon — tabs Projects/Checklists/Metrics | 01-08-18 (tabs) | `/person` | 🔨 | Persoonlijke roll-up over rollen. |
| Notifications | 01-08-38 | `/notifications` | 🔨 | Vereist eerst multi-user/web-ontsluiten; later. |
| Your Authority (beslis-helper: domein/policy/geld-check) | 01-09-00 | `/person` → Authority | 🔨 | Mooie Holacracy-feature; gebruikt domeinen/policies die we al hebben. |
| API (developer keys) | 01-09-16, 01.09.58 | admin | ➖/🔨 | Voor ONCE later; niet PoC-kritisch. |

## 5. Admin & organisatie

| Scherm | Screenshot(s) | Waar in cockpit | Status | Toelichting |
|--------|---------------|-----------------|--------|-------------|
| Organization Settings (naam, industrie, taal, tijdzone) | 01.07.06 | admin | 🔨 | Per-org config; sluit aan op "Nooch als config" (multi-tenant later). |
| Organization Members (mensen beheren) | 01.06.39–01.07.28 reeks | admin | 🟡 | People-store werkt; beheer-UI nog. |
| Checklists & Metrics (admin-overzicht) | (admin reeks) | admin | 🟡 | Store werkt; admin-UI nog. |
| Constitution / Membership Lists / Reports | 01-08-07 (nav) | `/org` | 🔨 | Constitution = statische doc; Reports = later. |
| Billing & Plans (Free/Premium, AI Assistant, Goals & Targets) | 01-08-07 | — | ➖ | Niet bouwen: dit is GlassFrog's abonnement. **Wel** input voor ónze ONCE-tiers + agent-upsell. |

## 6. Inzicht uit de billing-pagina (strategisch)

GlassFrog gate't als premium: History, integraties (Slack/Asana/Jira), SAML SSO, async proposals,
AI Assistant, Goals & Targets, onbeperkte projecten/notes. Dat is precies de scheidslijn voor ónze
twee producten: de **ONCE-base** (alles bezit je) en de **AI-laag** (abonnement). Goede bevestiging
van de strategie.

---

## Samenvatting van het werk

- **Staat al (✅) in cockpit 2:** cirkel-overview, roles, members, rol-overview met multi-fill,
  org-boom, persoonspagina (basis).
- **Basis aanwezig (🟡), UI te bouwen:** Notes, Metrics, Checklists (stores werken),
  Members-beheer, Proposals, persoonsprofiel-verrijking.
- **Bestaat in cockpit 1 (⚙️), te porten:** governance meeting (roloverleg), Inbox (triage).
- **Bouwen (🔨), grootste eerst:** Tactical meeting, Workspace, Projects-per-rol, Policies-per-cirkel,
  History, Your Authority, org-kaart-bubble, admin-schermen.
- **Niet doen (➖):** Billing (wel input voor prijsmodel), API (later).

**Volgorde-advies morgen:** 1) governance + inbox porten naar cockpit 2-nav (snelle winst, bestaat al),
2) Notes/Metrics invoer-UI (stores zijn er, maakt tabs "echt"), 3) Tactical meeting (grootste waarde),
4) Workspace + persoonsprofiel, 5) de rest.
