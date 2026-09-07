import hashlib
import json
import sqlite3
import subprocess
import sys
import zipfile
from contextlib import contextmanager

import pytest
from filelock import FileLock, Timeout

from ttcmap.db import read_dataset
from ttcmap.gtfs import build, ckan, refresh
from ttcmap.gtfs.refresh_lock import refresh_lock


def test_failed_publish_rolls_back_tables_and_generation(rail_feed, monkeypatch):
    old = rail_feed.publish()
    rail_feed.frames["stop_times"].loc[0, "departure_time"] = "12:00:01"
    tables, new = rail_feed.prepare()
    original = build.connect

    @contextmanager
    def denied():
        with original() as conn:
            conn.set_authorizer(
                lambda action, name, *args: (
                    sqlite3.SQLITE_DENY
                    if action == sqlite3.SQLITE_DROP_TABLE and name == "SERVICE_DAYS"
                    else sqlite3.SQLITE_OK
                )
            )
            yield conn

    monkeypatch.setattr(build, "connect", denied)
    with pytest.raises(sqlite3.DatabaseError):
        build.publish_dataset(tables, new, "changed")
    with read_dataset() as dataset:
        assert dataset.generation == old["generation"]
        assert (
            dataset.conn.execute(
                "SELECT MIN(departing_time_sec) FROM SUBWAY_STOP_TIMES WHERE trip_id='t-1-0'"
            ).fetchone()[0]
            == 43200
        )
    monkeypatch.setattr(build, "connect", original)
    build.publish_dataset(tables, new, "changed")
    with read_dataset() as dataset:
        assert dataset.generation == new["generation"]


def test_read_transaction_pins_old_schedule_and_topology_during_publish(rail_feed):
    old = rail_feed.publish()
    rail_feed.frames["stop_times"].loc[0, "departure_time"] = "12:00:01"
    tables, new = rail_feed.prepare()
    with read_dataset() as reader:
        build.publish_dataset(tables, new, "changed")
        assert reader.generation == old["generation"]
        assert (
            json.loads(reader.conn.execute("SELECT payload FROM active_dataset").fetchone()[0])[
                "generation"
            ]
            == old["generation"]
        )
        assert (
            reader.conn.execute(
                "SELECT MIN(departing_time_sec) FROM SUBWAY_STOP_TIMES WHERE trip_id='t-1-0'"
            ).fetchone()[0]
            == 43200
        )
    with read_dataset() as reader:
        assert reader.generation == new["generation"]


def test_forced_repeated_build_has_no_duplicates(rail_feed):
    first = rail_feed.publish()
    second = rail_feed.publish()
    assert first["generation"] == second["generation"]
    with read_dataset() as dataset:
        assert dataset.conn.execute("SELECT COUNT(*) FROM SUBWAY_STOP_TIMES").fetchone()[0] == 30


@pytest.mark.parametrize(
    "members",
    [
        {"routes.txt": "a"},
        {"../routes.txt": "a"},
        {"a/routes.txt": "a", "b/routes.txt": "a"},
    ],
)
def test_bad_archives_rejected_without_inheriting_previous_files(tmp_path, members):
    z = tmp_path / "bad.zip"
    with zipfile.ZipFile(z, "w") as archive:
        for name, body in members.items():
            archive.writestr(name, body)
    with pytest.raises(ValueError):
        ckan.extract_zip(z, tmp_path)


def test_revision_upgrade_uses_verified_offline_cache(rail_feed, monkeypatch):
    z = rail_feed.data / "download.zip"
    with zipfile.ZipFile(z, "w") as archive:
        for name, frame in rail_feed.frames.items():
            archive.writestr(name + ".txt", frame.to_csv(index=False))
    checksum = hashlib.sha256(z.read_bytes()).hexdigest()
    cache_dir = rail_feed.data / "feeds"
    cache_dir.mkdir()
    z.replace(cache_dir / (checksum + ".zip"))
    tables, artifact = rail_feed.prepare()
    artifact["feedCache"] = {"sha256": checksum, "version": "fixture-version"}
    build.publish_dataset(tables, artifact, "fixture-version")
    with sqlite3.connect(rail_feed.settings.database_path) as conn:
        conn.execute("UPDATE active_dataset SET revision='old'")

    def offline():
        raise RuntimeError("offline")

    monkeypatch.setattr(ckan, "get_package_metadata", offline)
    result = refresh._refresh_sync(False)
    assert result.updated, result.message
    with read_dataset() as dataset:
        assert dataset.revision == build.IMPORTER_REVISION
    assert not refresh._refresh_sync(False).updated


def test_missing_offline_upgrade_input_reports_pending(rail_feed, monkeypatch):
    def offline():
        raise RuntimeError("offline")

    monkeypatch.setattr(ckan, "get_package_metadata", offline)
    result = refresh._refresh_sync(False)
    assert result.status == "error" and "migration pending" in result.message


def test_os_writer_lock_coordinates_processes_and_recovers(rail_feed):
    code = (
        "from filelock import FileLock; import sys,time; "
        "lock=FileLock(sys.argv[1]); lock.acquire(); "
        "print('locked',flush=True); time.sleep(30)"
    )
    lock_path = str(rail_feed.settings.database_path.resolve()) + ".refresh.lock"
    child = subprocess.Popen(
        [sys.executable, "-c", code, lock_path], stdout=subprocess.PIPE, text=True
    )
    try:
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(Timeout), refresh_lock():
            pass
    finally:
        child.terminate()
        child.wait(timeout=5)
        child.stdout.close()
    # Process termination and OS lock release need not be observed in the same tick.
    with FileLock(lock_path, timeout=2):
        pass
