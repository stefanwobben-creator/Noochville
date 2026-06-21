from __future__ import annotations
import re

FORBIDDEN_IN_SALES: list[str] = ["plastic", "leer"]


def find_forbidden_words(text: str, words: list[str]) -> list[str]:
    found = []
    for word in words:
        if re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            found.append(word)
    return found
