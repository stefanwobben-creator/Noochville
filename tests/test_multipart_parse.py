"""_parse_multipart is byte-exact: de content-bytes komen ongewijzigd terug, alleen de multipart-framing
(leidende CRLF ná de boundary, één afsluitende CRLF vóór de volgende) wordt verwijderd. Regressie op de
oude bug waarbij `.strip(b"\\r\\n")` de laatste byte(s) van elk binair bestand wegknipte.
"""
from __future__ import annotations

from nooch_village.cockpit2_util import _parse_multipart

BOUNDARY = "----WebKitFormBoundaryXYZ"


def _build(parts):
    """parts = lijst van (name, value_bytes, filename|None, ctype|None) → ruwe multipart-body (bytes)."""
    delim = ("--" + BOUNDARY).encode()
    out = []
    for name, value, filename, ctype in parts:
        h = f'Content-Disposition: form-data; name="{name}"'
        if filename:
            h += f'; filename="{filename}"'
        blk = h.encode() + b"\r\n"
        if ctype:
            blk += f"Content-Type: {ctype}".encode() + b"\r\n"
        blk += b"\r\n" + value
        out.append(delim + b"\r\n" + blk + b"\r\n")
    return b"".join(out) + delim + b"--\r\n"


def test_binaire_content_byte_exact():
    # bewust met trailing \n, trailing \r\n, én binaire bytes — die MOGEN niet weggeknipt worden
    pdf = b"%PDF-1.4\n\xff\xd8\xff\x00rommel\r\n%%EOF\n"     # eindigt op \n
    crlf = b"regel1\r\nregel2\r\n"                            # eindigt op \r\n
    nonl = b"geen-eind-newline"                              # geen trailing newline
    body = _build([
        ("csrf", b"TOK", None, None),
        ("file", pdf, "Aanvraag_STCB_2026-1_Nooch_BV.pdf", "application/pdf"),
        ("blob2", crlf, "a.txt", "text/plain"),
        ("blob3", nonl, "b.bin", "application/octet-stream"),
    ])
    fields, files = _parse_multipart(body, BOUNDARY)
    assert fields["csrf"] == "TOK"
    assert files["file"][0] == "Aanvraag_STCB_2026-1_Nooch_BV.pdf"
    assert files["file"][1] == pdf                           # byte-exact, incl. de trailing \n
    assert files["blob2"][1] == crlf                         # trailing \r\n van de content behouden
    assert files["blob3"][1] == nonl


def test_veld_zonder_bestand_blijft_tekst():
    body = _build([("action", b"attach_file", None, None), ("pid", b"abc123", None, None)])
    fields, files = _parse_multipart(body, BOUNDARY)
    assert fields == {"action": "attach_file", "pid": "abc123"} and files == {}


def test_leeg_bestand():
    body = _build([("file", b"", "leeg.pdf", "application/pdf")])
    _, files = _parse_multipart(body, BOUNDARY)
    assert files["file"] == ("leeg.pdf", b"")
