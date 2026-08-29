"""Een embedding-sleutel is een IDENTITEIT, geen geheugenadres.

`kennis_context._rangschik` sleutelde tot 29 aug 2026 op `str(id(o))`. Dat adres verschilt per proces
én per aanroep, dus de index kon per definitie nooit raak zijn: élk item werd bij élke raadpleging
opnieuw geëmbed, en elke nieuwe afval-sleutel bleef permanent staan.

Gemeten gevolg op prod, vlak vóór de fix:

| index | grootte | ids | waarvan adres | levende items | cache-treffers |
|---|---|---|---|---|---|
| kennisbank_embeddings.json | 189 MB | 4464 | 4464 (100%) |  31 |   0 (0%) |
| radar_embeddings.json      | 287 MB | 6781 | 6357 (94%)  | 105 |  66 (63%) |

De 63% bij radar kwam van `radar_clusters`, die dezelfde index wél op echte ids sleutelt — het bewijs
dat de index zelf gezond was en alleen de sleutel niet.

Dit bestand houdt drie dingen dicht: de sleutel is stabiel, ontbreekt hij dan gaan we lexicaal
(fail-closed, niets in de index schrijven), en niemand sleutelt ooit nog op `id()`.
"""
from __future__ import annotations

import pathlib
import re

from nooch_village import kennis_context as kc

ROOT = pathlib.Path(__file__).resolve().parents[1] / "nooch_village"


# ── 1. De sleutel is stabiel ────────────────────────────────────────────────

def _vang_sleutels(monkeypatch) -> list:
    """Onderschept wat er als id de embedding-laag in gaat."""
    gezien: list[str] = []

    def _nep(zoektekst, items, index_path, tekst_fn, **kw):
        gezien.extend(i["id"] for i in items)
        return None                                     # → lexicale terugval, geen echte API
    monkeypatch.setattr("nooch_village.kennis_embeddings.rank_semantisch", _nep)
    return gezien


def test_de_sleutel_is_de_record_id_niet_het_adres(monkeypatch, tmp_path):
    gezien = _vang_sleutels(monkeypatch)
    docs = [({"id": "kb_abc"}, "barefoot schoenen"), ({"id": "kb_def"}, "mycelium leer")]
    kc._rangschik("barefoot", docs, 5, index="x.json", data_dir=str(tmp_path),
                  sleutel_fn=lambda i: i.get("id"))
    assert gezien == ["kb_abc", "kb_def"]
    assert not any(re.fullmatch(r"\d{9,}", s) for s in gezien), "geheugenadres als sleutel"


def test_dezelfde_items_geven_twee_keer_dezelfde_sleutels(monkeypatch, tmp_path):
    """DE KERN. Een sleutel die per aanroep verandert is geen sleutel — dan mist de cache altijd."""
    gezien = _vang_sleutels(monkeypatch)
    for _ in range(2):
        docs = [({"id": "kb_abc"}, "barefoot schoenen")]   # verse objecten, ander adres
        kc._rangschik("barefoot", docs, 5, index="x.json", data_dir=str(tmp_path),
                      sleutel_fn=lambda i: i.get("id"))
    assert gezien == ["kb_abc", "kb_abc"]


def test_de_treffers_worden_terugvertaald_naar_de_echte_objecten(monkeypatch, tmp_path):
    """De sleutel is een omweg; wat de aanroeper terugkrijgt moet het oorspronkelijke item zijn."""
    a, b = {"id": "kb_a"}, {"id": "kb_b"}
    monkeypatch.setattr("nooch_village.kennis_embeddings.rank_semantisch",
                        lambda *a_, **k: [{"id": "kb_b"}])
    hits, modus = kc._rangschik("x", [(a, "t1"), (b, "t2")], 5, index="x.json",
                                data_dir=str(tmp_path), sleutel_fn=lambda i: i.get("id"))
    assert hits == [b] and hits[0] is b
    assert modus == "semantisch"


# ── 2. Fail-closed: geen stabiele sleutel → lexicaal, index onaangeroerd ─────

def test_zonder_sleutel_fn_gaat_hij_lexicaal(monkeypatch, tmp_path):
    """Een aanroeper die het argument vergeet mag de index niet vervuilen. Dit is precies hoe de
    oude bug ontstond, dus het moet onmogelijk zijn hem per ongeluk te herhalen."""
    gezien = _vang_sleutels(monkeypatch)
    _, modus = kc._rangschik("barefoot", [({"id": "kb_a"}, "barefoot schoenen")], 5,
                             index="x.json", data_dir=str(tmp_path))
    assert modus == "lexicaal"
    assert gezien == [], "semantische weg toch ingeslagen zonder stabiele sleutel"


def test_een_item_zonder_id_zet_alles_op_lexicaal(monkeypatch, tmp_path):
    """Niet 'sla dat ene item over': dan is de ranglijst stil bevooroordeeld richting wat toevallig
    een id had. Alles of niets."""
    gezien = _vang_sleutels(monkeypatch)
    docs = [({"id": "kb_a"}, "barefoot"), ({"id": ""}, "mycelium")]
    _, modus = kc._rangschik("barefoot", docs, 5, index="x.json", data_dir=str(tmp_path),
                             sleutel_fn=lambda i: i.get("id"))
    assert modus == "lexicaal" and gezien == []


def test_dubbele_ids_zetten_alles_op_lexicaal(monkeypatch, tmp_path):
    """Twee items onder één sleutel betekent dat de één de vector van de ander krijgt."""
    gezien = _vang_sleutels(monkeypatch)
    docs = [({"id": "zelfde"}, "barefoot"), ({"id": "zelfde"}, "mycelium")]
    _, modus = kc._rangschik("barefoot", docs, 5, index="x.json", data_dir=str(tmp_path),
                             sleutel_fn=lambda i: i.get("id"))
    assert modus == "lexicaal" and gezien == []


def test_de_bronnen_geven_hun_sleutel_ook_echt_mee(monkeypatch, tmp_path):
    """Het gaat niet om de helper maar om de aanroepers: _inzichten en _signalen zijn de twee die
    een index gebruiken, en dus de twee die het fout konden hebben."""
    import inspect
    bron = inspect.getsource(kc)
    for fn in ("_inzichten", "_signalen"):
        blok = bron.split(f"def {fn}(")[1].split("\n\n\ndef ")[0]
        assert "sleutel_fn=" in blok, f"{fn} geeft geen stabiele sleutel mee"


# ── 3. De ratchet: nooit meer op id() sleutelen ─────────────────────────────

def test_niemand_sleutelt_op_een_geheugenadres():
    """`str(id(...))` als sleutel kost quota en levert per definitie nooit een treffer op.

    Bewust een scan over ALLE modules: de fout is niet te vangen met een unit-test op één functie,
    want hij kan in élke nieuwe aanroeper opnieuw ontstaan — en hij faalt stil (alles blijft werken,
    het is alleen duurder en trager). Commentaar en docstrings tellen niet mee, anders zou dit
    bestand zijn eigen uitleg over de bug als bug aanwijzen."""
    import io
    import tokenize

    fout = []
    for f in sorted(ROOT.rglob("*.py")):
        try:
            with open(f, "rb") as fh:
                tokens = list(tokenize.tokenize(fh.readline))
        except (tokenize.TokenError, SyntaxError):        # noqa: PERF203 — kapot bestand ≠ deze bug
            continue
        # Alleen echte CODE: geen commentaar, geen string-inhoud (dus ook geen docstrings).
        code = " ".join(t.string for t in tokens
                        if t.type not in (tokenize.COMMENT, tokenize.STRING, tokenize.NL,
                                          tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT))
        for m in re.finditer(r"str \( id \(", code):
            fout.append(f"{f.relative_to(ROOT)}: ...{code[max(0, m.start() - 60):m.end() + 40]}...")
    assert fout == [], ("een embedding- of cachesleutel afgeleid van `id()` is een geheugenadres: "
                        "per proces anders, dus de cache mist altijd en de index groeit eindeloos. "
                        "Gebruik de record-id.\n" + "\n".join(fout))


# ── 4. De default die stil kapot kon gaan ───────────────────────────────────

def test_het_standaard_embedding_model_is_er_een_die_bestaat():
    """`text-embedding-004` is bij Google verdwenen (404 NOT_FOUND). `embed()` is fail-soft, dus een
    404 geeft None, de aanroeper valt lexicaal terug en alles blijft werken — zónder semantiek, voor
    altijd, zonder dat iemand het merkt. Prod ontsnapte er alleen aan door LLM_EMBED_MODEL in .env.

    Deze test kan niet bewijzen dat het model bestaat (dat is een netwerkfeit), wel dat we niet
    terugvallen op de dode naam."""
    import importlib
    import os

    from nooch_village import kennis_embeddings as ke
    was = os.environ.pop("LLM_EMBED_MODEL", None)
    try:
        importlib.reload(ke)
        assert ke._MODEL != "text-embedding-004"
        assert ke._MODEL == "gemini-embedding-001"
    finally:
        if was is not None:
            os.environ["LLM_EMBED_MODEL"] = was
        importlib.reload(ke)


# ── 5. Fail-soft mag de degradatie niet onzichtbaar maken ───────────────────

def _corpus(tmp_path, n=2):
    from nooch_village.kennisbank import KennisbankStore
    kb = KennisbankStore(str(tmp_path / "kennisbank.json"))
    return [kb.add(f"inzicht {i}", why="omdat") for i in range(n)]


def _sleutel(monkeypatch, aanwezig: bool):
    monkeypatch.setattr("nooch_village.kennis_embeddings._key",
                        lambda: "sleutel" if aanwezig else None)


def test_zonder_sleutel_is_semantiek_uit_en_dat_is_geen_storing(tmp_path, monkeypatch):
    """Onderscheid dat ertoe doet: bewust uit ≠ stil kapot. Zonder sleutel is lexicaal de bedoeling."""
    _corpus(tmp_path)
    _sleutel(monkeypatch, False)
    st = kc.semantiek_status(str(tmp_path))
    assert st["oordeel"] == "uit" and st["sleutel"] is False


def test_sleutel_maar_niets_geindexeerd_heet_STIL(tmp_path, monkeypatch):
    """DE TOESTAND DIE MAANDEN ONZICHTBAAR WAS. Het model bestond niet meer, `embed()` gaf netjes
    None, iedereen viel netjes lexicaal terug, en niets in het systeem zei er iets over."""
    _corpus(tmp_path)
    _sleutel(monkeypatch, True)
    st = kc.semantiek_status(str(tmp_path))
    assert st["oordeel"] == "stil"
    assert st["indexen"][0]["geindexeerd"] == 0 and st["indexen"][0]["levend"] == 2


def test_volledig_geindexeerd_heet_actief(tmp_path, monkeypatch):
    from nooch_village.kennis_embeddings import EmbeddingStore
    from nooch_village.kennisbank import KennisbankStore
    ids = _corpus(tmp_path)
    _sleutel(monkeypatch, True)
    st = EmbeddingStore(str(tmp_path / "kennisbank_embeddings.json"))
    for ins in KennisbankStore(str(tmp_path / "kennisbank.json")).all():
        st.upsert(str(ins["id"]), f"{ins.get('title','')} {ins.get('why','')}", [0.1, 0.2])
    st.save()
    uit = kc.semantiek_status(str(tmp_path))
    inz = next(i for i in uit["indexen"] if i["index"] == kc.INDEX_INZICHTEN)
    assert inz["oordeel"] == "actief" and inz["geindexeerd"] == len(ids)


def test_de_dekking_wordt_berekend_niet_opgeslagen(tmp_path, monkeypatch):
    """Een VERGELIJKING, geen opgeslagen oordeel — zelfde regel als wiki.grond_status. Een nieuw
    inzicht verlaagt de dekking vanzelf; een bewaarde 'actief' zou blijven liegen."""
    from nooch_village.kennis_embeddings import EmbeddingStore
    from nooch_village.kennisbank import KennisbankStore
    _corpus(tmp_path, 1)
    _sleutel(monkeypatch, True)
    kb = KennisbankStore(str(tmp_path / "kennisbank.json"))
    st = EmbeddingStore(str(tmp_path / "kennisbank_embeddings.json"))
    for ins in kb.all():
        st.upsert(str(ins["id"]), f"{ins.get('title','')} {ins.get('why','')}", [0.1])
    st.save()
    assert kc.semantiek_status(str(tmp_path))["oordeel"] == "actief"
    kb.add("splinternieuw inzicht", why="net binnen")     # niet geïndexeerd
    assert kc.semantiek_status(str(tmp_path))["oordeel"] == "deels"


def test_een_terugval_met_sleutel_geeft_een_waarschuwing(tmp_path, monkeypatch, caplog):
    """Eén regel, de eerste keer per index per proces — zichtbaar zonder een stroom te worden."""
    import logging
    _corpus(tmp_path)
    _sleutel(monkeypatch, True)
    monkeypatch.setattr("nooch_village.kennis_embeddings.rank_semantisch", lambda *a, **k: None)
    kc._TERUGVAL_GEMELD.clear()
    with caplog.at_level(logging.WARNING, logger="village.kennis"):
        for _ in range(3):
            kc._rangschik("x", [({"id": "a"}, "t")], 5, index=kc.INDEX_INZICHTEN,
                          data_dir=str(tmp_path), sleutel_fn=lambda i: i.get("id"))
    waarschuwingen = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(waarschuwingen) == 1, "geen melding, of een stroom in plaats van een signaal"
    assert "SEMANTIEK NIET BESCHIKBAAR" in waarschuwingen[0].getMessage()
    kc._TERUGVAL_GEMELD.clear()


def test_zonder_sleutel_is_de_terugval_geen_waarschuwing(tmp_path, monkeypatch, caplog):
    import logging
    _corpus(tmp_path)
    _sleutel(monkeypatch, False)
    monkeypatch.setattr("nooch_village.kennis_embeddings.rank_semantisch", lambda *a, **k: None)
    kc._TERUGVAL_GEMELD.clear()
    with caplog.at_level(logging.INFO, logger="village.kennis"):
        kc._rangschik("x", [({"id": "a"}, "t")], 5, index=kc.INDEX_INZICHTEN,
                      data_dir=str(tmp_path), sleutel_fn=lambda i: i.get("id"))
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("semantiek uit" in r.getMessage() for r in caplog.records)
    kc._TERUGVAL_GEMELD.clear()


def test_het_opstartrapport_toont_de_dekking(tmp_path, monkeypatch):
    """Waar een mens het tegenkomt: het niet-blokkerende sleutel-rapport bij elke start van de
    daemon. Een rapport dat '✓ GEMINI_API_KEY' zegt terwijl er niets doorzoekbaar is op betekenis,
    vertelt de halve waarheid."""
    from types import SimpleNamespace

    from nooch_village.key_audit import audit_keys, format_key_report
    _corpus(tmp_path)
    _sleutel(monkeypatch, True)
    reg = SimpleNamespace(all=lambda: [])
    ctx = SimpleNamespace(settings={}, data_dir=str(tmp_path))
    tekst = format_key_report(audit_keys(reg, ctx, environ={}))
    assert "Semantische laag" in tekst
    assert "STIL" in tekst
    assert "0/2 geïndexeerd" in tekst
