"""Inwoners (persona's): store (add/get/all/update/remove + persistentie) en de persona-preamble."""
from __future__ import annotations
import os
import tempfile

import pytest

from nooch_village.personas import Persona, PersonaStore, persona_prompt


def _store():
    return PersonaStore(os.path.join(tempfile.mkdtemp(), "personas.json"))


def test_add_get_normaliseert_mbti():
    s = _store()
    p = s.add("Sam", mbti="intj", instructions="droog en precies")
    assert p.name == "Sam" and p.mbti == "INTJ" and p.instructions == "droog en precies"
    assert s.get(p.id).name == "Sam"
    assert s.get(None) is None and s.get("zzz") is None


def test_naam_verplicht():
    s = _store()
    with pytest.raises(ValueError):
        s.add("  ")


def test_all_update_remove_en_persistentie():
    path = os.path.join(tempfile.mkdtemp(), "personas.json")
    s = PersonaStore(path)
    a = s.add("Bo", mbti="ENFP")
    b = s.add("An", mbti="ISTJ")
    assert [p.name for p in s.all()] == ["An", "Bo"]            # alfabetisch
    s.update(a.id, instructions="speels", mbti="enfp")
    assert s.get(a.id).instructions == "speels" and s.get(a.id).mbti == "ENFP"
    # overleeft herladen
    assert PersonaStore(path).get(b.id).name == "An"
    assert s.remove(a.id) is True and s.get(a.id) is None
    assert s.remove("weg") is False


def test_persona_prompt():
    assert persona_prompt(None) == ""
    assert persona_prompt(Persona(id="x", name="", mbti="", instructions="")) == ""
    pr = persona_prompt(Persona(id="x", name="Sam", mbti="INTJ", instructions="droog en kort"))
    assert "Sam" in pr and "INTJ" in pr and "droog en kort" in pr
    assert "toon en aanpak" in pr                               # kleurt stem, niet capaciteit
    # werkt ook met dict
    assert "Bo" in persona_prompt({"name": "Bo", "mbti": "", "instructions": ""})
