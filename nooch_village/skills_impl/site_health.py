from __future__ import annotations
import re, requests
from nooch_village.skills import Skill


class SiteHealthSkill(Skill):
    name = "site_health"
    cost = "free"
    description = "Checkt of een site live is en haalt de paginatitel op (echte HTTP GET)."

    def run(self, payload: dict, context) -> dict:
        url = payload.get("url", "https://nooch.earth")
        r = requests.get(url, timeout=10, headers={"User-Agent": "NoochVillage/0.1"})
        title = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.I | re.S)
        if m:
            title = m.group(1).strip()[:120]
        return {"url": url, "status_code": r.status_code, "ok": r.ok,
                "title": title, "bytes": len(r.content)}
