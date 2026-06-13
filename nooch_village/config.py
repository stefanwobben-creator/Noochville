from __future__ import annotations
import os, configparser
from dataclasses import dataclass


@dataclass
class Context:
    """De rugzak (dependency injection). Skills lezen hier hun settings/secrets uit."""
    settings: dict
    data_dir: str
    library: object = None


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
    return Context(settings=settings, data_dir=data_dir)
