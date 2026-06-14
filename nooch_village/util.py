"""Gedeelde hulpfuncties voor NoochVillage."""
from __future__ import annotations

import json
import os
import tempfile


def atomic_write_json(path: str, obj) -> None:
    """Schrijf obj als JSON naar path via een tijdelijk bestand in dezelfde map.

    Gebruikt os.replace() zodat een onderbreking (Ctrl-C, crash) het oude
    bestand intact laat — nooit een half geschreven toestandsbestand.
    """
    dir_ = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
