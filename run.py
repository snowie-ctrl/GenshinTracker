"""Start GenshinTracker on http://127.0.0.1:<port>.  Usage: python run.py [--no-build]"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))


def ensure_frontend_built() -> None:
    if (ROOT / "frontend" / "build" / "index.html").exists():
        return
    npm = shutil.which("npm")
    if npm is None:
        print("Frontend is not built and npm was not found. Install Node.js (LTS), then run:\n"
              "  cd frontend; npm install; npm run build")
        return
    subprocess.run([npm, "install"], cwd=ROOT / "frontend", check=True)
    subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true", help="skip building the frontend")
    args = parser.parse_args()

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
