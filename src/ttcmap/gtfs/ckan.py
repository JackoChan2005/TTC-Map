"""Toronto Open Data (CKAN) client.

Replaces two separate clients that disagreed about which identifier named the
GTFS package: API/src/load.py used the slug, node-api/src/sync/fetchJson.js the
UUID. One package id now serves both the version check and the download.
"""

import logging
from pathlib import Path
from zipfile import ZipFile

import httpx

from ttcmap.config import get_settings

log = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT_S = 300.0
METADATA_TIMEOUT_S = 30.0


def get_package_metadata() -> dict:
    """Fetch package_show for the configured GTFS package."""
    settings = get_settings()
    url = f"{settings.ckan_base_url}/api/3/action/package_show"

    response = httpx.get(
        url, params={"id": settings.gtfs_package_id}, timeout=METADATA_TIMEOUT_S
    )
    response.raise_for_status()
    payload = response.json()

    if not payload.get("success") or not payload.get("result"):
        raise RuntimeError(f"Unexpected CKAN package_show response for {settings.gtfs_package_id}")

    return payload["result"]


def get_feed_version() -> str | None:
    """The feed's metadata_modified timestamp — the change marker we compare against."""
    return get_package_metadata().get("metadata_modified")


def _pick_zip_resource(package: dict) -> dict:
    for resource in package.get("resources", []):
        if not resource.get("datastore_active") and resource.get("url"):
            return resource
    raise RuntimeError("No downloadable GTFS resource found in the CKAN package")


def download_and_extract(package: dict | None = None) -> Path:
    """Download the GTFS zip and extract its .txt members. Returns the extract dir."""
    settings = get_settings()
    package = package or get_package_metadata()
    resource = _pick_zip_resource(package)

    extract_dir = settings.data_path / "gtfs"
    extract_dir.mkdir(parents=True, exist_ok=True)
    zip_path = settings.data_path / "gtfs.zip"

    log.info("Downloading GTFS feed from %s", resource["url"])
    with httpx.stream(
        "GET", resource["url"], timeout=DOWNLOAD_TIMEOUT_S, follow_redirects=True
    ) as response:
        response.raise_for_status()
        with open(zip_path, "wb") as handle:
            for chunk in response.iter_bytes(chunk_size=1 << 16):
                handle.write(chunk)

    log.info("Extracting %s", zip_path)
    with ZipFile(zip_path) as archive:
        members = [m for m in archive.infolist() if m.filename.endswith(".txt")]
        for member in members:
            # flatten: some feeds nest the .txt files inside a folder
            member.filename = Path(member.filename).name
            archive.extract(member, extract_dir)

    log.info("Extracted %d GTFS files to %s", len(members), extract_dir)
    zip_path.unlink(missing_ok=True)
    return extract_dir
