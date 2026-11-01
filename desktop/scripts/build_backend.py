from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


DESKTOP_DIR = Path(__file__).resolve().parents[1]     # desktop/
ROOT = DESKTOP_DIR.parent                             # 项目根目录
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
DIST = DESKTOP_DIR / "dist-backend"
BUILD = DESKTOP_DIR / "build-backend"
SPEC = DESKTOP_DIR / "course-platform-backend.spec"


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    if SPEC.exists():
        SPEC.unlink()

    separator = ";" if sys.platform.startswith("win") else ":"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "course-platform-backend",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD),
        "--add-data",
        f"{FRONTEND_DIR}{separator}frontend",
        str(BACKEND_DIR / "app.py"),
    ]
    subprocess.run(command, cwd=DESKTOP_DIR, check=True)
    executable = DIST / ("course-platform-backend.exe" if sys.platform.startswith("win") else "course-platform-backend")
    if not executable.exists():
        raise SystemExit(f"Backend executable was not created: {executable}")
    print(executable)


if __name__ == "__main__":
    main()
