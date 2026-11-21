# backend/tests/test_run.py — run.py's startup checks (packages and frontend build)
import importlib.util
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("run_script", ROOT / "run.py")
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)


def write_pyproject(path: Path, deps: list[str]) -> Path:
    body = ", ".join(f'"{d}"' for d in deps)
    path.write_text(f'[project]\nname = "x"\nversion = "0"\ndependencies = [{body}]\n', encoding="utf-8")
    return path


def test_installed_requirements_are_not_reported(tmp_path):
    pyproject = write_pyproject(tmp_path / "pyproject.toml", ["pytest>=1", "uvicorn[standard]>=0.1"])
    assert run.missing_requirements(pyproject) == []


def test_missing_package_and_wrong_pin_are_reported(tmp_path):
    pyproject = write_pyproject(tmp_path / "pyproject.toml",
                                ["no-such-package-gt>=1", "pytest==0.0.1", "python-multipart>=0.0.1"])
    assert run.missing_requirements(pyproject) == ["no-such-package-gt>=1", "pytest==0.0.1"]


def touch(path: Path, age: float = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    t = time.time() - age
    os.utime(path, (t, t))
    return path


def test_frontend_build_missing_or_older_than_sources(tmp_path):
    fe = tmp_path / "frontend"
    touch(fe / "src" / "routes" / "+page.svelte", age=100)
    assert run.frontend_stale(fe)                               # no build yet
    touch(fe / "build" / "index.html", age=50)
    assert not run.frontend_stale(fe)                           # build newer than every source
    touch(fe / "src" / "lib" / "New.svelte")                    # e.g. a git pull brought a new file
    assert run.frontend_stale(fe)


def test_config_files_count_and_node_modules_are_ignored(tmp_path):
    fe = tmp_path / "frontend"
    touch(fe / "build" / "index.html", age=50)
    touch(fe / "node_modules" / "pkg" / "index.js")             # never a reason to rebuild
    assert not run.frontend_stale(fe)
    touch(fe / "package.json")
    assert run.frontend_stale(fe)


def test_npm_install_needed_when_lock_changes(tmp_path):
    fe = tmp_path / "frontend"
    touch(fe / "package-lock.json", age=100)
    assert run.npm_install_needed(fe)                           # no node_modules
    touch(fe / "node_modules" / ".package-lock.json", age=50)
    assert not run.npm_install_needed(fe)
    touch(fe / "package-lock.json")
    assert run.npm_install_needed(fe)
