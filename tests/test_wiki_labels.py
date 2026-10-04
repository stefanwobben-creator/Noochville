"""De statuslabels van een feit, zoals besloten op 4 oktober 2026 — op één plek (`wiki.LABEL`)."""
from __future__ import annotations

from nooch_village import wiki


def _bron(**grond):
    return {"tekst": "x", "grond": {"soort": "bron", "ref": "", "citaat": "een citaat van lengte",
                                    "url": "https://example.org", **grond}}


def test_de_vijf_bronstatussen_hebben_hun_besloten_label():
    assert wiki.grond_status(_bron(url=""))["label"] == "no source"
    assert wiki.grond_status(_bron())["label"] == "not yet checked"
    assert wiki.grond_status(_bron(check={"op": "2026-10-04", "gevonden": True}))["label"] == "verified"
    assert wiki.grond_status(_bron(check={"op": "2026-10-04", "gevonden": False}))["label"] == "changed — recheck"
    assert wiki.grond_status(_bron(check={"op": "2026-10-04", "gevonden": None,
                                          "reden": "not a web page"}))["label"] == "couldn't check"


def test_geen_oude_labels_meer_in_de_code():
    """"cited source — quote still present" en "source missing" waren de oude teksten op de pagina."""
    import inspect
    src = inspect.getsource(wiki.grond_status)
    for oud in ("source missing", "quote still present", "quote no longer found", '"not verified"'):
        assert oud not in src, oud
