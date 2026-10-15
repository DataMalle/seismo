"""Konfiguration från miljövariabler (Streamlit-secrets läggs i miljön av app.py)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Obligatorisk konfiguration saknas."""


@dataclass(frozen=True)
class Settings:
    warehouse_id: str
    catalog: str = "workspace"
    schema_prefix: str = "seismo"

    @property
    def gold(self) -> str:
        return f"{self.catalog}.{self.schema_prefix}_gold"


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    if not env.get("DATABRICKS_WAREHOUSE_ID"):
        raise ConfigError("DATABRICKS_WAREHOUSE_ID")
    return Settings(
        warehouse_id=env["DATABRICKS_WAREHOUSE_ID"],
        catalog=env.get("CATALOG", "workspace"),
        schema_prefix=env.get("SCHEMA_PREFIX", "seismo"),
    )
