"""ProjectDocStore — het levende einddocument per project.

Eén markdown-document per project op schijf (`data/project_docs/<pid>.md`), **update-in-place**
(geen cap, geen versie-explosie). Anders dan de deliverable-sidecars (write-once) is dit een levend
document dat elke synthese-pass overschrijft.

**Twee schrijvers, cross-proces:** de daemon-synthese (persona-stem) én de cockpit-edit-route (mens
redigeert bij review) schrijven allebei. Daarom is de single-writer-aanname vervallen en schrijft
`write()` ATOMISCH (temp-bestand + `os.replace`) zodat nooit een half bestand leesbaar is. Er is
bewust GEEN locking en GEEN merge: bij een gelijktijdige schrijf **wint de laatste schrijver** — dat
is acceptabel voor v1 (de AI schrijft het hele document; mens-edits zijn input voor de volgende pass).

`data/project_docs/` valt onder het bestaande `tar czf … data/`-backup-ritueel.
"""
from __future__ import annotations

import logging
import os
import tempfile

log = logging.getLogger("village.project_docs")


class ProjectDocStore:
    def __init__(self, base_dir: str):
        self.dir = os.path.join(base_dir, "project_docs")

    def _path(self, pid: str) -> str:
        return os.path.join(self.dir, f"{pid}.md")

    def read(self, pid: str) -> str:
        """Het huidige document, of "" als er nog geen is. Leesfout → fail-loud logregel + ""."""
        try:
            with open(self._path(pid), encoding="utf-8") as fh:
                return fh.read()
        except FileNotFoundError:
            return ""
        except OSError as e:
            log.warning("DOC_READ_FAIL: %s onleesbaar: %s", self._path(pid), e)
            return ""

    def write(self, pid: str, md: str) -> None:
        """Overschrijf het document atomisch (temp + os.replace) — nooit een half bestand leesbaar.
        Write-write-race (daemon-synthese ↔ cockpit-edit): laatste schrijver wint (v1, geen merge)."""
        os.makedirs(self.dir, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(md or "")
            os.replace(tmp, self._path(pid))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def delete_for(self, pid: str) -> bool:
        """Cascade bij DEFINITIEVE project-delete. Geeft True als er een document verwijderd is."""
        try:
            os.remove(self._path(pid))
            return True
        except FileNotFoundError:
            return False
        except OSError as e:
            log.warning("DOC_DELETE_FAIL: %s niet verwijderd: %s", self._path(pid), e)
            return False
