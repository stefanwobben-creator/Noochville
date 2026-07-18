"""Inwoners (persona's) — het karakter los van de rol.

Een rol is het *wat* (capaciteit: purpose, accountabilities, skills/rugzak). Een inwoner is het
*wie* (personality: naam, MBTI, vrije instructies). The Source maakt inwoners aan en koppelt ze
aan rollen (Record.persona_id). Skills horen bij de rol, niet bij de inwoner — het karakter is
draagbaar, het gereedschap hoort bij de stoel. Zie docs/ONTWERP_inwoners.md.

NB: de naam `Inhabitant` is in code al de levende rol-agent (inhabitant.py). Daarom heet de
karakter-entiteit hier `Persona`. Naar de gebruiker toe heet het "inwoner".
"""
from __future__ import annotations
import os
import uuid
from dataclasses import dataclass, asdict, field, fields

from nooch_village.util import atomic_write_json, read_json

# Veelgebruikte MBTI-typen (validatie is licht: vrije tekst mag, maar we normaliseren naar hoofdletters).
_MBTI = {
    "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP",
}


@dataclass
class Persona:
    """Een inwoner: een herbruikbaar karakter dat een rol kan vervullen.

    HARDE SCHEIDSLIJN — hier staat NOOIT mandaat-taal in. Purpose, accountabilities en domeinen
    horen bij de ROL en wijzigen alleen via governance (G0-G4). Zou de persona ze ook dragen,
    dan zijn er twee waarheden en is de poort een wassen neus. Wat hier woont is de drager:
    karakter, capaciteit, gereedschap en modelvoorkeur — dat reist mee bij een zetelwissel.

    Alle velden na `instructions` zijn optioneel toegevoegd; een oude personas.json zonder die
    sleutels laadt ongewijzigd (dataclass-defaults)."""
    id: str
    name: str
    mbti: str = ""
    instructions: str = ""        # vrije personality-/specifieke instructies
    skills: list[str] = field(default_factory=list)
    # Rugzakje: wat deze AI-inwoner intrinsiek kan. Anders dan bij mensen (waar het gereedschap
    # bij de rol hoort) is de capaciteit van een AI eigen aan de agent. Een AI mag nooit buiten
    # dit rugzakje opereren; een autonome taak op een accountability kiest uit deze lijst.
    # LET OP (2026-07): dit veld is in deze fase METADATA voor het dossier en de pakket-export.
    # De UITVOERING (`Inhabitant.use_skill`) draait onveranderd op de rol-DNA-skills. Skills-bij-
    # persona als uitvoeringsmodel raakt Reconciler, gates en tests en is een eigen brief waard.
    avatar: str = ""              # emoji; puur weergave
    prompt_extra: str = ""        # extra instructie, achter `instructions` in de preamble
    tools: list[dict] = field(default_factory=list)    # [{label, desc, href}] — het UI-manifest
    llm: dict = field(default_factory=dict)            # {"default": "...", "per_taak": {...}}
    kind: str = "ai"              # "ai" | "motor" — een motor (Facilitator) heeft geen LLM-blok


def persona_prompt(p: Persona | dict | None) -> str:
    """Bouw de persona-preamble voor de LLM. Leeg als er geen inwoner is (neutrale stem).
    Het karakter kleurt TOON en aanpak, niet WAT de rol inhoudelijk kan."""
    if p is None:
        return ""
    name = p.get("name", "") if isinstance(p, dict) else p.name
    mbti = p.get("mbti", "") if isinstance(p, dict) else p.mbti
    instr = p.get("instructions", "") if isinstance(p, dict) else p.instructions
    extra = (p.get("prompt_extra", "") if isinstance(p, dict) else getattr(p, "prompt_extra", "")) or ""
    if not (name or mbti or instr or extra.strip()):
        return ""
    wie = name or "deze inwoner"
    kop = f"Je bent {wie}" + (f" ({mbti})" if mbti else "") + "."
    staart = (f" {instr.strip()}" if instr.strip() else "")
    # prompt_extra komt ACHTER de instructies, op een eigen regel: de mens kan zo een scherpe
    # werkafspraak toevoegen zonder de karakterbeschrijving te herschrijven.
    aanvulling = f"\n{extra.strip()}" if extra.strip() else ""
    return (kop + staart +
            " Laat je karakter doorklinken in toon en aanpak, niet in wat je inhoudelijk kunt."
            + aanvulling)


class PersonaStore:
    """JSON-store voor inwoners (data/personas.json). Achter dezelfde bestand-interface als de
    andere stores; The Source cureert (add/update/remove), de rest leest."""

    def __init__(self, path: str):
        self.path = path
        self._items: dict[str, dict] = read_json(path, {})

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, self._items)

    def _lees(self, d: dict) -> Persona:
        """Persona uit een opgeslagen dict. Onbekende sleutels worden genegeerd in plaats van
        een TypeError te geven: een dossier uit een nieuwere versie mag een oude village niet
        laten klappen (pakket-import, zie village.inwoner_install)."""
        velden = {f.name for f in fields(Persona)}
        return Persona(**{k: v for k, v in d.items() if k in velden})

    def add(self, name: str, mbti: str = "", instructions: str = "",
            skills: list[str] | None = None) -> Persona:
        """Maak een nieuwe inwoner. Naam verplicht; MBTI wordt genormaliseerd naar hoofdletters."""
        name = (name or "").strip()
        if not name:
            raise ValueError("een inwoner heeft een naam nodig")
        mbti = (mbti or "").strip().upper()
        pid = uuid.uuid4().hex[:12]
        p = Persona(id=pid, name=name[:60], mbti=mbti[:8],
                    instructions=(instructions or "").strip()[:1000],
                    skills=[s.strip()[:80] for s in (skills or []) if s.strip()])
        self._items[pid] = asdict(p)
        self._save()
        return p

    def add_skill(self, pid: str, skill: str) -> Persona | None:
        """Voeg een skill toe aan het rugzakje van een AI-inwoner (idempotent op naam)."""
        d = self._items.get(pid)
        skill = (skill or "").strip()[:80]
        if d is None or not skill:
            return None
        lst = d.setdefault("skills", [])
        if skill not in lst:
            lst.append(skill)
            self._save()
        return self._lees(d)

    def remove_skill(self, pid: str, skill: str) -> Persona | None:
        d = self._items.get(pid)
        if d is None:
            return None
        lst = d.get("skills", [])
        if skill in lst:
            lst.remove(skill)
            self._save()
        return self._lees(d)

    def get(self, pid: str | None) -> Persona | None:
        if not pid:
            return None
        d = self._items.get(pid)
        return self._lees(d) if d else None

    def all(self) -> list[Persona]:
        return [self._lees(d) for d in sorted(self._items.values(), key=lambda x: x.get("name", ""))]

    def update(self, pid: str, *, name: str | None = None, mbti: str | None = None,
               instructions: str | None = None, avatar: str | None = None,
               prompt_extra: str | None = None, tools: list[dict] | None = None,
               llm: dict | None = None, skills: list[str] | None = None,
               kind: str | None = None) -> Persona | None:
        """Werk velden bij. Alleen wat je meegeeft verandert (None = ongemoeid), zodat een
        formulier dat één sectie bewerkt de rest van het dossier nooit wist."""
        d = self._items.get(pid)
        if d is None:
            return None
        if name is not None and name.strip():
            d["name"] = name.strip()[:60]
        if mbti is not None:
            d["mbti"] = mbti.strip().upper()[:8]
        if instructions is not None:
            d["instructions"] = instructions.strip()[:1000]
        if avatar is not None:
            d["avatar"] = avatar.strip()[:8]
        if prompt_extra is not None:
            d["prompt_extra"] = prompt_extra.strip()[:1000]
        if tools is not None:
            d["tools"] = [{"label": str(t.get("label", ""))[:80],
                           "desc": str(t.get("desc", ""))[:160],
                           "href": str(t.get("href", ""))[:160]}
                          for t in tools if isinstance(t, dict) and t.get("label")]
        if llm is not None:
            d["llm"] = {"default": str(llm.get("default", ""))[:80],
                        "per_taak": {str(k)[:80]: str(v)[:80]
                                     for k, v in (llm.get("per_taak") or {}).items() if v}}
        if skills is not None:
            d["skills"] = [s.strip()[:80] for s in skills if s.strip()]
        if kind is not None:
            d["kind"] = "motor" if kind == "motor" else "ai"
        self._save()
        return self._lees(d)

    def remove(self, pid: str) -> bool:
        if pid in self._items:
            del self._items[pid]
            self._save()
            return True
        return False
