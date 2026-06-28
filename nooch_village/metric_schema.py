"""Indicator-grondslag als gevalideerd schema (Pydantic v2).

Een indicator is INFORMATIE, geen doel (Goodhart). Het schema legt twee dingen vast:

1. de GRONDSLAG (GAAP/IRIS-idee: zonder vaste definitie geen vergelijkbaarheid):
   wat telt mee (definitie), eenheid, richting (hoger/lager = beter), drempel;
2. het MEETMOMENT: hoe vaak gemeten (cadans) en hoe een waarde geldt (meettype):
   - snapshot   = stand op het meetmoment (bijv. voorraad nu)
   - venster     = som/gemiddelde over een terugrollend venster (bijv. bezoekers 7d)
   - cumulatief = oplopend totaal sinds een startpunt (bijv. paren verkocht dit jaar)

CLAUDE.md: dataclasses voor interne modellen, Pydantic mag voor ingest-data. Een KPI-definitie
die uit een formulier of agent binnenkomt is ingest; de store bewaart daarna een gewone dict.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

CADANS = ("continu", "uur", "dag", "week", "maand", "kwartaal", "jaar", "ad-hoc")
MEETTYPE = ("snapshot", "venster", "cumulatief")
# meetwijze = HOE een waarde tot stand komt; bepaalt of handmatig invoeren mag:
#   systeem   = automatisch uit een bron/berekening → géén handmatige invoer (integriteit)
#   handmatig = je voert de waarde zelf in
#   enquete   = resultaat van een enquête (handmatig ingevoerd, maar apart gelabeld)
MEETWIJZE = ("systeem", "handmatig", "enquete")
MEETWIJZE_LABEL = {"systeem": "systeem", "handmatig": "handmatig", "enquete": "enquête"}

CADANS_LABEL = {"continu": "continu", "uur": "per uur", "dag": "per dag", "week": "per week",
                "maand": "per maand", "kwartaal": "per kwartaal", "jaar": "per jaar",
                "ad-hoc": "ad-hoc"}
MEETTYPE_LABEL = {"snapshot": "momentopname", "venster": "over een venster",
                  "cumulatief": "cumulatief"}


class IndicatorDefinition(BaseModel):
    """De grondslag + het meetmoment van één indicator. Tolerant: normaliseert i.p.v. te weigeren,
    behalve een lege naam (dan faalt validatie en wordt de KPI niet aangemaakt)."""

    name: str = Field(min_length=1)
    unit: str = ""
    definition: str = ""
    source: str = ""
    direction: Literal["up", "down", ""] = ""
    threshold: Optional[float] = None
    cadence: Literal["continu", "uur", "dag", "week", "maand", "kwartaal", "jaar", "ad-hoc"] = "ad-hoc"
    meettype: Literal["snapshot", "venster", "cumulatief"] = "snapshot"
    window: str = ""  # bijv. "7d" wanneer meettype = venster
    meetwijze: Literal["systeem", "handmatig", "enquete"] = "handmatig"

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v):
        return (str(v or "").strip())[:120]

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, v):
        return (str(v or "").strip())[:24]

    @field_validator("definition", mode="before")
    @classmethod
    def _def(cls, v):
        return (str(v or "").strip())[:300]

    @field_validator("source", "window", mode="before")
    @classmethod
    def _short(cls, v):
        return (str(v or "").strip())[:24]

    @field_validator("direction", mode="before")
    @classmethod
    def _dir(cls, v):
        return v if v in ("up", "down") else ""

    @field_validator("threshold", mode="before")
    @classmethod
    def _thr(cls, v):
        import math
        s = str(v if v is not None else "").strip()
        if s in ("", "None"):
            return None
        try:
            f = float(s)
        except ValueError:
            return None
        return f if math.isfinite(f) else None

    @field_validator("cadence", mode="before")
    @classmethod
    def _cad(cls, v):
        return v if v in CADANS else "ad-hoc"

    @field_validator("meettype", mode="before")
    @classmethod
    def _mt(cls, v):
        return v if v in MEETTYPE else "snapshot"

    @field_validator("meetwijze", mode="before")
    @classmethod
    def _mw(cls, v):
        return v if v in MEETWIJZE else "handmatig"


SCHEMA_FIELDS = list(IndicatorDefinition.model_fields)  # volgorde = schema-definitie


def normalize(**kwargs) -> dict | None:
    """Valideer/normaliseer een indicator-definitie. Geeft een schone dict terug, of None
    als de definitie ongeldig is (lege naam)."""
    try:
        return IndicatorDefinition(**kwargs).model_dump()
    except ValidationError:
        return None
