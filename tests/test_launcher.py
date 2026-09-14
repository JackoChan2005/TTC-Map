"""Exercise the Unix launcher without installing packages or starting a server."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Unix launcher tests")
LAUNCHER = Path(__file__).resolve().parents[1] / "start.command"


@pytest.mark.parametrize(
    ("args", "sync_exit", "run_exit", "expected_exit", "expected_args"),
    [
        ([], 0, 0, 0, ["serve"]),
        (["serve", "--port", "8001"], 0, 0, 0, ["serve", "--port", "8001"]),
        (["build-network", "--data-dir", "feed with spaces"], 0, 0, 0,
         ["build-network", "--data-dir", "feed with spaces"]),
        ([], 17, 0, 17, None),
        (["refresh"], 0, 23, 23, ["refresh"]),
    ],
)
def test_unix_launcher(tmp_path, args, sync_exit, run_exit, expected_exit, expected_args):
    checkout = tmp_path / "checkout with spaces"
    checkout.mkdir()
    launcher = checkout / "start.command"
    shutil.copyfile(LAUNCHER, launcher)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(
        '#!/bin/bash\n'
        'printf "%s\\n" "$PWD" "$@" >> "$CALL_LOG"\n'
        'if [ "$1" = sync ]; then exit "$SYNC_EXIT"; fi\n'
        'exit "$RUN_EXIT"\n'
    )
    uv.chmod(0o755)
    log = tmp_path / "calls.log"
    result = subprocess.run(
        ["/bin/bash", str(launcher), *args],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "CALL_LOG": str(log),
            "SYNC_EXIT": str(sync_exit),
            "RUN_EXIT": str(run_exit),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == expected_exit, result.stderr
    expected = [str(checkout), "sync", "--locked"]
    if expected_args is not None:
        expected += [str(checkout), "run", "--no-sync", "ttcmap", *expected_args]
    assert log.read_text().splitlines() == expected
