#!/usr/bin/env python3
"""
Cross-platform setup launcher for TTC-Map.

Usage:
    python setup.py
"""

import os
import sys
import platform
import subprocess
import shutil


def detect_shell():
    """Return a string describing the current shell environment."""
    if os.name == "nt":
        parent = os.environ.get("ComSpec", "").lower()
        if "powershell" in parent:
            return "powershell"
        if "cmd.exe" in parent:
            return "cmd"
        # Git Bash / MSYS / MINGW
        if os.environ.get("MSYSTEM"):
            return "git-bash"
        return "windows-unknown"
    else:
        return os.environ.get("SHELL", "unknown")


def run_command(cmd):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    shell = detect_shell()
    system = platform.system().lower()

    print(f"Detected OS: {system}")
    print(f"Detected shell: {shell}")

    setup_dir = os.path.join(project_root, "setup")

    setup_sh = os.path.join(setup_dir, "setup.sh")
    setup_ps1 = os.path.join(setup_dir, "setup.ps1")


    # ─────────────────────────────────────────────
    # Windows
    # ─────────────────────────────────────────────
    if system == "windows":
        if shell in ("git-bash",):
            if not os.path.exists(setup_sh):
                sys.exit("setup.sh not found.")
            run_command(["bash", setup_sh])
        else:
            if not os.path.exists(setup_ps1):
                sys.exit("setup.ps1 not found.")
            run_command([
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                setup_ps1
            ])

    # ─────────────────────────────────────────────
    # macOS / Linux / WSL
    # ─────────────────────────────────────────────
    else:
        if not os.path.exists(setup_sh):
            sys.exit("setup.sh not found.")
        if not shutil.which("bash"):
            sys.exit("bash not found in PATH.")
        run_command(["bash", setup_sh])


if __name__ == "__main__":
    main()
