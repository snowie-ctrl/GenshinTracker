"""Start GenshinTracker on http://127.0.0.1:<port>.  Usage: python run.py [--no-build] [--no-install]

Before starting, it installs missing Python packages (from backend/pyproject.toml) and rebuilds the
frontend when its sources are newer than the build, so the app runs straight after a `git pull`."""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
sys.path.insert(0, str(BACKEND))

REQUIREMENT_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(.*)$")
FRONTEND_SOURCES = ("src", "static")
FRONTEND_CONFIGS = ("package.json", "package-lock.json", "svelte.config.js", "vite.config.ts", "tsconfig.json")


def missing_requirements(pyproject: Path) -> list[str]:
    """Requirements that are not installed, or whose exact `==` pin doesn't match what is installed."""
    deps = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["dependencies"]
    missing = []
    for req in deps:
        m = REQUIREMENT_RE.match(req)
        if m is None:
            continue
        name, spec = m.group(1), m.group(2).strip()
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            missing.append(req)
            continue
        if spec.startswith("==") and "," not in spec and installed != spec[2:].strip():
            missing.append(req)
    return missing


def ensure_backend_packages() -> None:
    missing = missing_requirements(BACKEND / "pyproject.toml")
    if not missing:
        return
    print(f"Installing Python packages: {', '.join(missing)}")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(BACKEND)], check=True)


def _newest_mtime(paths) -> float:
    newest = 0.0
    for p in paths:
        if p.is_file():
            newest = max(newest, p.stat().st_mtime)
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    newest = max(newest, f.stat().st_mtime)
    return newest


def frontend_stale(frontend: Path) -> bool:
    """True when there is no build, or a source or config file changed after the last build."""
    index = frontend / "build" / "index.html"
    if not index.exists():
        return True
    sources = [frontend / d for d in FRONTEND_SOURCES] + [frontend / f for f in FRONTEND_CONFIGS]
    return _newest_mtime(sources) > index.stat().st_mtime


def npm_install_needed(frontend: Path) -> bool:
    """True when node_modules is missing or older than package-lock.json (npm stamps it on install)."""
    stamp = frontend / "node_modules" / ".package-lock.json"
    lock = frontend / "package-lock.json"
    if not stamp.exists():
        return True
    return lock.exists() and lock.stat().st_mtime > stamp.stat().st_mtime


def ensure_frontend_built() -> None:
    if not frontend_stale(FRONTEND):
        return
    npm = shutil.which("npm")
    if npm is None:
        print("The frontend needs building and npm was not found. Install Node.js (LTS), then run:\n"
              "  cd frontend; npm install; npm run build")
        return
    if npm_install_needed(FRONTEND):
        subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=FRONTEND, check=True)
    print("Building the frontend...")
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true", help="skip rebuilding the frontend")
    parser.add_argument("--no-install", action="store_true", help="skip installing missing Python packages")
    args = parser.parse_args()
    if not args.no_install:
        ensure_backend_packages()

    from dotenv import dotenv_values

    from app.config import DEFAULT_PORT, default_paths

    env = dotenv_values(default_paths().env_file) if default_paths().env_file.exists() else {}
    port = int(os.environ.get("PORT") or env.get("PORT") or DEFAULT_PORT)
    if not args.no_build:
        ensure_frontend_built()

    import uvicorn

    print(f"GenshinTracker running at http://127.0.0.1:{port}")
    uvicorn.run("app.main:create_app", factory=True, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
