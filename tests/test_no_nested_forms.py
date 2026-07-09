"""Regressie: het upload-form (class='filepost', multipart) mag NOOIT genest zitten in een ander <form>.
Geneste forms zijn ongeldige HTML → de browser dropt de inner form → de File wordt niet als multipart
verstuurd → uploads komen leeg binnen. Deze test bewaakt dat de projectdetail-render geen enkele geneste
<form> bevat.
"""
from __future__ import annotations

from html.parser import HTMLParser

from nooch_village import cockpit2
from nooch_village.views import projects as P

ROLE = "mother_earth__nooch__website_developer"


class _FormNesting(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.nested = []          # class-attributen van forms die BINNEN een ander form openen
        self.saw_filepost = False

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            cls = dict(attrs).get("class", "")
            if "filepost" in cls:
                self.saw_filepost = True
            if self.depth > 0:
                self.nested.append(cls)
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "form" and self.depth > 0:
            self.depth -= 1


def _frag(tmp_path, desc="x"):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    pid = st.projects.create(ROLE, "T", "human", description=desc)
    return cockpit2.render_project(cockpit2._Stores(dd), pid, csrf_token="TOK", fragment=True), pid


def test_geen_geneste_forms_in_projectdetail(tmp_path):
    frag, _ = _frag(tmp_path)
    parser = _FormNesting()
    parser.feed(frag)
    assert parser.saw_filepost, "upload-form (filepost) niet in de render — testopstelling klopt niet"
    assert parser.nested == [], f"geneste <form>(s) gevonden (ongeldige HTML): {parser.nested}"


def test_upload_form_niet_in_comp_form_en_plaatsen_via_form_attr(tmp_path):
    frag, pid = _frag(tmp_path)
    # de composer-form sluit vóór de toolbar-rij; Plaatsen submit 'm via form=
    assert f"id='cf-{pid}'" in frag
    assert f"form='cf-{pid}'" in frag and "value='proj_feed'" in frag
    # het filepost-form staat NA het sluiten van de comp-form (dus niet erin)
    i_close_composer = frag.index("</form>", frag.index("class='pf comp-form'"))
    assert frag.index("class='filepost'") > i_close_composer
