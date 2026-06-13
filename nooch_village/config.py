from __future__ import annotations
import json, os, configparser
from dataclasses import dataclass, field


@dataclass
class Context:
    """De rugzak (dependency injection). Skills lezen hier hun settings/secrets uit."""
    settings: dict
    data_dir: str
    library: object = None
    records: object = None   # read-only verwijzing naar Records, voor Facilitator/Gate
    strategy: dict = field(default_factory=dict)  # geladen uit config/strategy.json


def load_context(base_dir: str) -> Context:
    settings: dict = {}
    ini = os.path.join(base_dir, "config", "settings.ini")
    if os.path.exists(ini):
        cp = configparser.ConfigParser()
        cp.read(ini)
        for section in cp.sections():
            for k, v in cp.items(section):
                settings[k] = v
    env = os.path.join(base_dir, ".env")
    if os.path.exists(env):
        for line in open(env):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                settings[k.strip()] = v.strip()
                os.environ.setdefault(k.strip(), v.strip())
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    strategy: dict = {}
    strategy_path = os.path.join(base_dir, "config", "strategy.json")
    if os.path.exists(strategy_path):
        with open(strategy_path) as f:
            raw = json.load(f)
        strategy = {k: v for k, v in raw.items() if not k.startswith("_")}

    return Context(settings=settings, data_dir=data_dir, strategy=strategy)
