from __future__ import annotations
import json, os, configparser
from dataclasses import dataclass, field


@dataclass
class Context:
    """De rugzak (dependency injection). Skills lezen hier hun settings/secrets uit."""
    settings: dict
    data_dir: str
    library: object = None
    competitors: object = None  # gedeelde CompetitorBrands-store: confirmed concurrenten,
                                # leesbaar voor élke rol (KE/SerpAPI-analyses)
    records: object = None   # read-only verwijzing naar Records, voor Facilitator/Gate
    strategy: dict = field(default_factory=dict)  # geladen uit config/strategy.json
    copy_rules: str = ""  # geladen uit config/copy_rules.md — de basis voor alle copy


def load_context(base_dir: str) -> Context:
    settings: dict = {}
    ini = os.path.join(base_dir, "config", "settings.ini")
    if os.path.exists(ini):
        cp = configparser.ConfigParser()
        cp.read(ini)
        # cp.sections() slaat [DEFAULT] over; lees defaults apart
        for k, v in cp.defaults().items():
            settings[k] = v
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

    copy_rules: str = ""
    copy_rules_path = os.path.join(base_dir, "config", "copy_rules.md")
    if os.path.exists(copy_rules_path):
        with open(copy_rules_path, encoding="utf-8") as f:
            copy_rules = f.read()

    return Context(settings=settings, data_dir=data_dir,
                   strategy=strategy, copy_rules=copy_rules)
