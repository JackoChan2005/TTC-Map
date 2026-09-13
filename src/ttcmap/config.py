"""Application settings, loaded from the environment and .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000

    # Relative data paths resolve against the repository root.
    data_dir: Path = Path("data")
    db_path: Path = Path("data/ttc.db")
    shared_dir: Path = Path("shared")
    led_maps_dir: Path = Path("hardware/led-maps")
    web_dir: Path = Path("web")

    ckan_base_url: str = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
    gtfs_package_id: str = "merged-gtfs-ttc-routes-and-schedules"
    # Check metadata at this interval; rebuild only when needed.
    gtfs_check_interval_s: int = 6 * 60 * 60

    ntas_base_url: str = "https://ntas.ttc.ca/api/ntas/get-next-train-time/"
    ntas_poll_s: int = 30
    # Minimum arrival window; the recorder extends it for longer segments.
    ntas_arriving_min: int = 5
    ntas_concurrency: int = 10
    ntas_timeout_s: float = 5.0
    # Bound the whole poll so feed timeouts cannot stall the recorder.
    ntas_poll_timeout_s: float = 25.0
    snapshot_max_age_s: float = 90.0

    ntas_enabled_lines: set[str] = {"1", "2", "4"}
    ntas_min_coverage_by_line: dict[str, float] = {"1": 0.5, "2": 0.5, "4": 0.5, "5": 0.9}

    @model_validator(mode="after")
    def validate_ntas(self):
        if not self.ntas_enabled_lines <= {"1", "2", "4", "5"}:
            raise ValueError("NTAS supports configured lines 1, 2, 4, 5 only")
        if not self.ntas_enabled_lines <= self.ntas_min_coverage_by_line.keys():
            raise ValueError("Every enabled NTAS line needs a coverage threshold")
        if any(not 0 < v <= 1 for v in self.ntas_min_coverage_by_line.values()):
            raise ValueError("NTAS coverage thresholds must be in (0, 1]")
        if (
            min(
                self.ntas_concurrency,
                self.ntas_poll_s,
                self.ntas_timeout_s,
                self.ntas_poll_timeout_s,
                self.snapshot_max_age_s,
            )
            <= 0
        ):
            raise ValueError("NTAS polling limits must be positive")
        return self

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
