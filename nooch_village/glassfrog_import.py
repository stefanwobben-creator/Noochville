"""GlassFrog-import — een org-structuur (cirkels, rollen, mensen, bezetting) inladen in de stores.

`import_org(org, records, people, assignments)` is het migratie-pad: het zet een org-dict om in
governance-records (geboren), mensen (people-store) en bezetting (assignments — bemenst). Hetzelfde
mechanisme gebruiken we straks voor OVM/Obelink/FindYour.

`nooch_poc_org()` is de echte Nooch-structuur uit de GlassFrog-export (twee geneste cirkels:
Mother Earth > Nooch), als deterministische fixture voor de PoC. De definitieve converter leest
straks de GlassFrog-API/JSON; deze fixture is onze geverifieerde bron voor nu.
"""
from __future__ import annotations
import re

from nooch_village.models import Record, RecordType, RoleDefinition


def _slug(s: str) -> str:
    return re.sub(r"\W+", "_", (s or "").strip().lower()).strip("_")[:48] or "x"


def import_org(org: dict, records, people, assignments) -> dict:
    """Zet een org-dict om in records (cirkels+rollen), mensen en bezetting. Cirkels worden
    parent-before-child verwerkt zodat nesting klopt. Geeft een telling terug."""
    name_to_id: dict[str, str] = {}
    created = {"circles": 0, "roles": 0, "fillers": 0}

    def _fill(anchor_id: str, names) -> None:
        for fn in names or []:
            person = people.add(fn)
            if assignments.assign(anchor_id, "person", person.id):
                created["fillers"] += 1

    # Cirkels: herhaal tot stabiel (ouder moet bestaan voor kind).
    pending = list(org.get("circles", []))
    progressed = True
    while pending and progressed:
        progressed, still = False, []
        for c in pending:
            pname = c.get("parent")
            if pname is None:
                pid = None
            elif pname in name_to_id:
                pid = name_to_id[pname]
            else:
                still.append(c)
                continue
            cid = _slug(c["name"]) if pid is None else f"{pid}__{_slug(c['name'])}"
            records.put(Record(
                id=cid, type=RecordType.CIRCLE, parent=pid,
                definition=RoleDefinition(
                    purpose=c.get("purpose", ""),
                    accountabilities=list(c.get("accountabilities", [])),
                    domains=list(c.get("domains", [])),
                    name=c["name"]),
                members=[], source="seed"))
            name_to_id[c["name"]] = cid
            created["circles"] += 1
            progressed = True
            _fill(cid, c.get("fillers"))
        pending = still

    # Rollen: ouder-cirkel moet bestaan.
    for r in org.get("roles", []):
        pid = name_to_id.get(r.get("parent"))
        if pid is None:
            continue
        rid = f"{pid}__{_slug(r['name'])}"
        records.put(Record(
            id=rid, type=RecordType.ROLE, parent=pid,
            definition=RoleDefinition(
                purpose=r.get("purpose", ""),
                accountabilities=list(r.get("accountabilities", [])),
                domains=list(r.get("domains", [])),
                name=r["name"]),
            source="seed"))
        created["roles"] += 1
        _fill(rid, r.get("fillers"))

    # members-lijst van elke cirkel = zijn directe kinderen.
    allrecs = records.all()
    for c in allrecs:
        if c.type == RecordType.CIRCLE:
            c.members = [x.id for x in allrecs if x.parent == c.id]
    records.save()
    created["people"] = len(people.all())
    return created


# ── De echte Nooch-structuur (GlassFrog-export 2026-06-27), geverifieerde fixture ──

_FAC_ACCS = [
    "Facilitating the Circle's regular Tactical Meetings",
    "Facilitating the Circle's Governance Process",
    "Triggering new elections for the Circle's elected Roles after each election term expires",
    "Auditing a Sub-Circle's meetings and records on request and declaring a Process Breakdown if one is discovered",
]
_SEC_ACCS = [
    "Scheduling regular Tactical Meetings for the Circle",
    "Capturing and publishing Tactical Meeting outputs",
    "Scheduling Governance Meetings for the Circle",
    "Capturing and publishing the outputs of the Circle's Governance Process",
    "Interpreting the Constitution and anything under its authority upon request",
]
_ME_PURPOSE = ("To support and protect all forms of life through sustainable and responsible "
               "management of natural resources.")
_NOOCH_PURPOSE = ("Nooch transforms the shoe industry, step by step. Every movement with Nooch is "
                  "a step towards a better world for Mother Earth and her inhabitants.")


def nooch_poc_org() -> dict:
    """De echte Nooch-org als org-dict (twee geneste cirkels, 20 rollen, 6 mensen)."""
    return {
        "circles": [
            {"name": "Mother Earth", "parent": None, "purpose": _ME_PURPOSE, "fillers": []},
            {"name": "Nooch", "parent": "Mother Earth", "purpose": _NOOCH_PURPOSE,
             "fillers": ["Lotte Mulder", "Stefan Wobben"]},
        ],
        "roles": [
            # Mother Earth
            {"name": "Circle Lead", "parent": "Mother Earth", "purpose": _ME_PURPOSE, "fillers": []},
            {"name": "Facilitator", "parent": "Mother Earth",
             "purpose": "Circle governance and operational practices aligned with the Constitution.",
             "accountabilities": _FAC_ACCS, "fillers": []},
            {"name": "Secretary", "parent": "Mother Earth",
             "purpose": "Stabilize the Circle's constitutionally-required records and meetings.",
             "domains": ["All governance records of the Circle"],
             "accountabilities": _SEC_ACCS, "fillers": []},
            {"name": "Shareholder", "parent": "Mother Earth", "purpose": "Holding formal responsbility",
             "accountabilities": ["Assigning or removing circle lead for Nooch circle",
                                  "Defining company purpose and accountabilities",
                                  "Signing document for legal responsibility"],
             "fillers": ["Lotte Mulder", "Stefan Wobben"]},
            # Nooch
            {"name": "Brand & Visual Designer", "parent": "Nooch",
             "purpose": "Make Nooch visually consistent, clear and inspiring.",
             "accountabilities": ["Creating all visual assets (ads, socials, emails, packaging, etc.)",
                                  "Maintaining and evolving the Nooch visual identity",
                                  "Producing brand materials for marketing & community",
                                  "Providing visuals for website and product page",
                                  "Keeping all brand files organised and accessible"],
             "fillers": ["Lotte Mulder"]},
            {"name": "Carbon Footprint Improver", "parent": "Nooch",
             "purpose": "Minimizing the environmental impact of Nooch products through data-driven optimization.",
             "accountabilities": ["Maintaining comprehensive insight into the Carbon Footprint of all Nooch products.",
                                  "Identifying and executing opportunities to continuously lower the carbon footprint.",
                                  "Collaborating with other roles to balance sustainability with cost and speed."],
             "fillers": ["Lotte Mulder"]},
            {"name": "Circle Lead", "parent": "Nooch", "purpose": _NOOCH_PURPOSE,
             "fillers": ["Lotte Mulder", "Stefan Wobben"]},
            {"name": "Circle Rep", "parent": "Nooch",
             "purpose": "Tensions relevant to process in a broader Circle channeled out and resolved.",
             "accountabilities": ["Seeking to understand Tensions conveyed by Role Leads within the Circle",
                                  "Discerning Tensions appropriate to process within a broader Circle that holds the Circle",
                                  "Processing Tensions within a broader Circle to remove constraints on the Circle"],
             "fillers": []},
            {"name": "Community and Email", "parent": "Nooch",
             "purpose": "Build a strong and supportive Nooch community.",
             "accountabilities": ["Writing email flows & updates", "Managing customer communication",
                                  "Keeping community engaged and informed"],
             "fillers": ["Nina Wolter"]},
            {"name": "Creator of Shoes", "parent": "Nooch", "purpose": "Kick-ass Noochies",
             "accountabilities": ["Designing new shoe models & colorways",
                                  "Working with suppliers on materials and ways of working",
                                  "Reviewing product quality and samples",
                                  "Translating user feedback into next iterations"],
             "fillers": ["Lotte Mulder"]},
            {"name": "Facilitator", "parent": "Nooch",
             "purpose": "Circle governance and operational practices aligned with the Constitution.",
             "accountabilities": _FAC_ACCS, "fillers": ["Stefan Wobben"]},
            {"name": "Factory Development Specialist", "parent": "Nooch",
             "purpose": "Ensuring a world-class manufacturing partnership and seamless production execution.",
             "accountabilities": ["Maintaining frequent and proactive communication with the factory.",
                                  "Ensuring all new orders are placed accurately and according to specifications.",
                                  "Verifying that production is \"ready-to-go\" and on schedule.",
                                  "Cultivating and optimizing a high-trust, long-term relationship with the factory."],
             "fillers": []},
            {"name": "Financial Controller", "parent": "Nooch",
             "purpose": "Safeguarding the financial health and disciplined spending",
             "accountabilities": ["Designing and managing the operational budget.",
                                  "Monitoring expenditures to ensure alignment with financial targets.",
                                  "Providing financial clarity to other roles to support informed decision-making."],
             "fillers": ["Stefan Wobben"]},
            {"name": "Inmate in residence", "parent": "Nooch",
             "purpose": "Stunts that spread awareness around the power of what Nooch stands for",
             "accountabilities": ["Updating a prioritized list of ideas that gain attention",
                                  "Coordinating and execute stunts", "Informing press relations about stunts",
                                  "Generating bad-ass guerrilla stunt ideas",
                                  "Finding and recruiting incredible people to do stunts with",
                                  "Being arrested a couple times per year for the good cause"],
             "fillers": []},
            {"name": "Marketing Lead", "parent": "Nooch", "purpose": "Grow awareness and demand for Nooch.",
             "accountabilities": ["Planning and running marketing campaigns",
                                  "Tracking performance and sharing insights",
                                  "Managing paid & organic channels"],
             "fillers": ["Matthijs Boesten"]},
            {"name": "Mother Earth Steward", "parent": "Nooch", "purpose": "Guarding Mother Earth",
             "accountabilities": ["Raising awareness of planetary effects on business decisions",
                                  "Withholding consent on business decisions due to negative external planetary effects"],
             "fillers": ["Lotte Mulder", "Stefan Wobben"]},
            {"name": "Secretary", "parent": "Nooch",
             "purpose": "Stabilize the Circle's constitutionally-required records and meetings.",
             "domains": ["All governance records of the Circle"], "accountabilities": _SEC_ACCS, "fillers": []},
            {"name": "Strategic Lead & Founder Steward", "parent": "Nooch",
             "purpose": "Hold the long-term direction, protect the mission, and ensure Nooch grows in the right way.",
             "accountabilities": ["Shaping overall business strategy and priorities",
                                  "Telling the Nooch story (press, investors, community)",
                                  "Leading fundraising and financial strategy",
                                  "Guarding mission, values and long-term principles",
                                  "Representing Nooch externally with partners, media and stakeholders"],
             "fillers": ["Stefan Wobben"]},
            {"name": "Supply Chain Coordinator", "parent": "Nooch",
             "purpose": "Creating a transparent, efficient, and resilient flow of goods from source to destination.",
             "accountabilities": ["Maintaining full visibility into the supply chain (timelines, contacts, status, and costs).",
                                  "Ensuring all supply chain processes remain on track and meet quality standards.",
                                  "Keeping all relevant suppliers informed of needs and changes.",
                                  "Identifying and mitigating supply chain risks or bottlenecks at an early stage."],
             "fillers": ["Wytse Valkema"]},
            {"name": "Website Developer", "parent": "Nooch", "purpose": "High performing website",
             "domains": ["Nooch.earth"],
             "accountabilities": ["Building new features", "Optimzing website performance",
                                  "Fixing bugs", "Maintaining a backlog of issues"],
             "fillers": ["Stefan Wobben", "Dan Morgan"]},
        ],
    }
