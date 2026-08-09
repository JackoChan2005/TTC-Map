"""Single source of configuration.

Replaces node-api/env.config plus the gitignored .env.local override that only
existed so the Node server could locate a Python interpreter to spawn. With one
process there is nothing to spawn, so PYTHON_BIN, PYTHON_SYNC_*, RT_DATABASE_PATH,
JSON_SOURCE and CKAN_FETCH_RESOURCE are all gone.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root: src/ttcmap/config.py -> src/ttcmap -> src -> repo
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000

    # Data locations. Relative paths resolve against the repo root.
    data_dir: Path = Path("data")
    db_path: Path = Path("data/ttc.db")
    shared_dir: Path = Path("shared")
    led_maps_dir: Path = Path("hardware/led-maps")
    web_dir: Path = Path("web")

    # Toronto Open Data (CKAN) — one package id for both the version check and
    # the download; the Node and Python halves used to disagree on this.
    ckan_base_url: str = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
    gtfs_package_id: str = "merged-gtfs-ttc-routes-and-schedules"
    # The GTFS feed changes every few weeks, so this is how often we *check*
    # CKAN's metadata_modified, not how often we rebuild.
    gtfs_check_interval_s: int = 6 * 60 * 60

    # NTAS realtime feed
    ntas_base_url: str = "https://ntas.ttc.ca/api/ntas/get-next-train-time/"
    ntas_poll_s: int = 30
    ntas_arriving_min: int = 1
    ntas_concurrency: int = 10
    ntas_timeout_s: float = 5.0
    # deadline for a whole poll across every platform, so an unresponsive feed
    # cannot block the recorder for longer than one cycle
    ntas_poll_timeout_s: float = 25.0
    snapshot_max_age_s: float = 90.0

    # auto | schedule | ntas
    map_source: str = "auto"

    def _resolve(self, value: Path) -> Path:
        return value if value.is_absolute() else REPO_ROOT / value

    @property
    def data_path(self) -> Path:
        return self._resolve(self.data_dir)

    @property
    def database_path(self) -> Path:
        return self._resolve(self.db_path)

    @property
    def shared_path(self) -> Path:
        return self._resolve(self.shared_dir)

    @property
    def led_maps_path(self) -> Path:
        return self._resolve(self.led_maps_dir)

    @property
    def web_path(self) -> Path:
        return self._resolve(self.web_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
