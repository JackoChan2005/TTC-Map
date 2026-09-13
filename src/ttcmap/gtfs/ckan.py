"""Versioned GTFS downloads with isolated extraction and verified offline cache."""

import hashlib
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import httpx

from ttcmap.config import get_settings

REQUIRED = {"routes.txt", "trips.txt", "stops.txt", "stop_times.txt", "calendar.txt"}


def get_package_metadata() -> dict:
    settings = get_settings()
    response = httpx.get(
        settings.ckan_base_url + "/api/3/action/package_show",
        params={"id": settings.gtfs_package_id},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success") or not payload.get("result"):
        raise RuntimeError("Invalid CKAN package metadata")
    return payload["result"]


def _pick_zip_resource(package: dict) -> dict:
    candidates = [
        r
        for r in package.get("resources", [])
        if not r.get("datastore_active")
        and r.get("url")
        and (
            r.get("format", "").lower() == "zip" or r["url"].lower().split("?")[0].endswith(".zip")
        )
    ]
    if len(candidates) != 1:
        raise RuntimeError("Expected exactly one complete GTFS ZIP resource")
    return candidates[0]


def extract_zip(zip_path: Path, destination: Path) -> None:
    with ZipFile(zip_path) as archive:
        members = {}
        for member in archive.infolist():
            path = PurePosixPath(member.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsafe GTFS archive path")
            if not member.filename.endswith(".txt") or member.is_dir():
                continue
            if path.name in members:
                raise ValueError(f"Duplicate GTFS filename: {path.name}")
            members[path.name] = member
        if not REQUIRED <= members.keys():
            raise ValueError(f"Missing GTFS files: {sorted(REQUIRED - members.keys())}")
        if sum(m.file_size for m in members.values()) > 2_000_000_000:
            raise ValueError("GTFS archive exceeds extraction limit")
        for name, member in members.items():
            with archive.open(member) as source, (destination / name).open("wb") as out:
                import shutil

                shutil.copyfileobj(source, out)


@contextmanager
def feed_input(package: dict | None, cached: dict | None = None):
    root = get_settings().data_path
    root.mkdir(parents=True, exist_ok=True)
    feeds = root / "feeds"
    feeds.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="gtfs-", dir=root) as temporary:
        staging = Path(temporary)
        if package is not None:
            resource = _pick_zip_resource(package)
            download = staging / "feed.zip"
            digest = hashlib.sha256()
            with httpx.stream("GET", resource["url"], timeout=300, follow_redirects=True) as r:
                r.raise_for_status()
                with download.open("wb") as out:
                    for chunk in r.iter_bytes(65536):
                        digest.update(chunk)
                        out.write(chunk)
            checksum = digest.hexdigest()
            cached = {"sha256": checksum, "version": package.get("metadata_modified")}
            zip_path = feeds / (checksum + ".zip")
            download.replace(zip_path)
        else:
            checksum = (cached or {}).get("sha256", "")
            if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
                raise RuntimeError("No verified offline GTFS cache; migration pending")
            zip_path = feeds / (checksum + ".zip")
            if not zip_path.exists():
                raise RuntimeError("Offline GTFS cache missing")
            with zip_path.open("rb") as source:
                if hashlib.file_digest(source, "sha256").hexdigest() != checksum:
                    raise RuntimeError("Offline GTFS checksum mismatch")
        extract_zip(zip_path, staging)
        yield staging, cached
