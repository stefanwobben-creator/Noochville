"""GovernanceExamples — een VERTROUWELIJKE referentiebank van echte Holacracy-rollen.

Geparsed uit governance-exports van bestaande organisaties (GlassFrog/Holaspirit). Per rol
bewaren we alleen het skelet: archetype (geanonimiseerd, geen bedrijfsnaam), cirkel, rolnaam,
purpose, accountabilities en domeinen. Projecten en persoonsnamen worden bewust NIET bewaard.

Doel: few-shot-grounding bij het formuleren van governance (een voorstel verwoorden, kiezen
nieuw-vs-uitbreiden, een accountability/purpose Holacracy-correct schrijven). De Facilitator/
Secretaris-rollen bestaan al in het dorp; dit voedt alleen de FORMULERING.

HARDE GRENS — vertrouwelijk:
  Deze store leeft uitsluitend lokaal in data/ (gitignored) en mag NOOIT in een publiek pad
  belanden: niet in de kennisgraaf (notes), niet in keyword-voorstellen, niet in gepubliceerde
  content of Field Notes. Alleen de governance-formuleer-calls lezen eruit. Daarom is dit een
  eigen store, los van NotesStore/Library, en wordt hij niet door cockpit.gather() ingeladen.
"""
from __future__ import annotations
import os, re
from nooch_village.util import atomic_write_json, read_json


# De canonieke Holacracy-regels voor formulering (bron: holacracy.org). Worden als instructie
# meegegeven aan de LLM-calls die accountabilities/projecten verwoorden.
ACCOUNTABILITY_RULES = (
    "Holacracy-formuleerregels:\n"
    "- Een ACCOUNTABILITY begint ALTIJD met een werkwoord dat een doorlopende activiteit "
    "beschrijft. In het Nederlands de -en-vorm vooraan: 'Faciliteren van...', 'Ontwikkelen "
    "en beheren van...', 'Bewaken van...', 'Vastleggen van...'. (In het Engels een werkwoord "
    "op -ing.)\n"
    "- Het is een doorlopend aandachtsgebied, GEEN eenmalige taak en GEEN project.\n"
    "- Het kent geen autoriteit toe en claimt geen exclusiviteit (dat zijn domeinen/policies).\n"
    "- Kort en helder; geen lange waslijst hyper-gedetailleerde punten.\n"
    "- Een PROJECT is juist een AFGERONDE uitkomst, als voltooide toestand: 'Reviews zichtbaar "
    "op elke productpagina', 'Nieuw logo ontworpen'."
)

_STOP = {"van", "de", "het", "en", "een", "voor", "in", "op", "te", "met", "of", "the",
         "and", "of", "to", "for", "a", "is", "naar", "bij", "aan", "die", "dat", "der"}

# Footer-/ruisregels uit de PDF-export die we niet als content willen.
_NOISE = re.compile(
    r"^\s*(\d+|\(.*\)|.*\d{4}-\d{2}-\d{2}.*UTC.*|Purpose|Domeinen|Verantwoordelijkheden|"
    r"Projecten|Beleid|Policies)\s*$", re.IGNORECASE)


def _tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-zà-ÿ]{3,}", (text or "").lower()) if w not in _STOP}


class GovernanceExamples:
    """Vertrouwelijke, read-mostly referentiebank van rol-skeletten."""

    def __init__(self, path: str):
        self.path = path
        self._roles: list[dict] = read_json(path, [], expect=list)

    def all(self) -> list[dict]:
        return list(self._roles)

    def count(self) -> int:
        return len(self._roles)

    def replace(self, roles: list[dict]) -> None:
        """Vervang de hele bank (na een (her)ingestie). Atomic write."""
        self._roles = list(roles)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        atomic_write_json(self.path, self._roles)

    def search(self, query: str, k: int = 3) -> list[dict]:
        """De k meest verwante rollen op woord-overlap (rol + purpose + accountabilities).
        Puur lexicaal, geen LLM — goedkoop en deterministisch."""
        q = _tokens(query)
        if not q or not self._roles:
            return self._roles[:k]
        scored = []
        for r in self._roles:
            blob = " ".join([r.get("role", ""), r.get("purpose", ""),
                             " ".join(r.get("accountabilities", []))])
            overlap = len(q & _tokens(blob))
            if overlap:
                scored.append((overlap, r))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:k]]


def few_shot_block(store: GovernanceExamples | None, query: str, k: int = 3) -> str:
    """Een compact few-shot-blok van echte rollen voor in een prompt. Leeg ('') als er geen
    store/voorbeelden zijn (fail-closed: de call werkt dan gewoon zonder grounding)."""
    if store is None or store.count() == 0:
        return ""
    rows = store.search(query, k)
    if not rows:
        return ""
    out = ["Voorbeelden uit vergelijkbare organisaties (ter inspiratie voor de formulering, "
           "niet letterlijk overnemen):"]
    for r in rows:
        accs = r.get("accountabilities", [])[:3]
        acc_txt = "; ".join(accs)
        out.append(f"- [{r.get('archetype','org')}] rol '{r.get('role','')}' — doel: "
                   f"{r.get('purpose','')}" + (f" | accountabilities: {acc_txt}" if acc_txt else ""))
    return "\n".join(out)


# ── parser ────────────────────────────────────────────────────────────────────

_BLOCK_RE = re.compile(r"(?:^|\n)(?P<name>[^\n]{1,80})\nPurpose\n", re.MULTILINE)


def _clean_lines(blok: str) -> list[str]:
    """Maak van een sectie-blok nette accountability-regels: voeg vervolgregels (kleine letter)
    samen met de vorige, en gooi footer-/ruisregels weg. Een nieuwe accountability begint met
    een hoofdletter (Faciliteren, Ontwikkelen, ...)."""
    items: list[str] = []
    for raw in blok.splitlines():
        line = raw.strip()
        if not line or _NOISE.match(line):
            continue
        if "geen verantwoordelijkheden" in line.lower() or "geen domein" in line.lower():
            continue
        if items and (line[0].islower() or line[0] in ",.;)"):
            items[-1] = (items[-1] + " " + line).strip()   # vervolgregel
        else:
            items.append(line)
    # opschonen: losse leestekens en lege
    return [re.sub(r"\s+", " ", it).strip(" .") for it in items if len(it.strip(" .")) > 2]


def parse_governance_text(text: str, archetype: str) -> list[dict]:
    """Parse de platte tekst van een governance-export tot rol-skeletten. Drop projecten en
    persoonsnamen (die staan in de Projecten-sectie, die we niet meenemen). Dedup identieke
    rollen (de constitutionele kernrollen herhalen per cirkel)."""
    roles: list[dict] = []
    seen: set = set()
    matches = list(_BLOCK_RE.finditer(text))
    for i, m in enumerate(matches):
        name = m.group("name").strip()
        if not name or _NOISE.match(name):
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        # purpose = alles tot 'Domeinen' (of 'Verantwoordelijkheden')
        pm = re.search(r"(.*?)\n(Domeinen|Verantwoordelijkheden)\b", body, re.DOTALL)
        purpose = (pm.group(1).strip() if pm else "").replace("\n", " ").strip()
        if "geen purpose" in purpose.lower():
            purpose = ""
        # accountabilities = tussen 'Verantwoordelijkheden' en 'Projecten'/'Beleid'/eind
        am = re.search(r"Verantwoordelijkheden\n(.*?)(?:\nProjecten|\nBeleid|\Z)", body, re.DOTALL)
        accs = _clean_lines(am.group(1)) if am else []
        # domeinen = tussen 'Domeinen' en 'Verantwoordelijkheden'
        dm = re.search(r"Domeinen\n(.*?)(?:\nVerantwoordelijkheden|\Z)", body, re.DOTALL)
        doms = _clean_lines(dm.group(1)) if dm else []
        if not purpose and not accs:
            continue                                   # leeg skelet → overslaan
        key = (name.lower(), purpose.lower(), tuple(a.lower() for a in accs[:3]))
        if key in seen:
            continue
        seen.add(key)
        roles.append({"archetype": archetype, "role": name, "purpose": purpose,
                      "accountabilities": accs[:8], "domains": doms[:5]})
    return roles


def parse_governance_pdf(path: str, archetype: str, max_pages: int | None = None) -> list[dict]:
    """Lees een governance-PDF en parse naar rol-skeletten. Vereist pypdf."""
    from pypdf import PdfReader
    r = PdfReader(path)
    pages = range(len(r.pages) if max_pages is None else min(max_pages, len(r.pages)))
    text = "\n".join((r.pages[i].extract_text() or "") for i in pages)
    return parse_governance_text(text, archetype)
