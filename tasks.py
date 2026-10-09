"""The task runner. It works on Windows, macOS and Linux. (Windows has no make. The Makefile only
calls this file.)

Usage: python tasks.py install | dev | build | run | test | eval [--cache] [--script NAME] [--runs N]"""

import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
NPM = "npm.cmd" if os.name == "nt" else "npm"
SERVER = ["-m", "uvicorn", "backend.app.main:app", "--port", "8000"]


def run(*command: str, cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def install() -> None:
    if not VENV_PYTHON.exists():
        venv.create(ROOT / ".venv", with_pip=True)
    run(str(VENV_PYTHON), "-m", "pip", "install", "-r", "requirements.txt")
    run(NPM, "install", cwd=WEB)


def dev() -> None:
    """Run the backend on :8000 (it reloads when the code changes) and Vite on :5173.
    Vite sends /api and /ws to :8000."""
    backend = subprocess.Popen([str(VENV_PYTHON), *SERVER, "--reload"], cwd=ROOT)
    frontend = subprocess.Popen([NPM, "run", "dev"], cwd=WEB)
    try:
        backend.wait()
    finally:  # Ctrl+C, or a uvicorn stop (for example, the port is in use), stops both
        stop(frontend)
        stop(backend)


def stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":  # terminate() stops only npm.cmd on Windows. Vite would continue to run.
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True)
    else:
        process.terminate()


def build() -> None:
    run(NPM, "run", "build", cwd=WEB)


def serve() -> None:
    """Run one process. FastAPI serves the built frontend at http://localhost:8000."""
    run(str(VENV_PYTHON), *SERVER)


def test() -> None:
    run(str(VENV_PYTHON), "-m", "pytest", "-q")


def evaluate(*args: str) -> None:
    run(str(VENV_PYTHON), "-m", "eval.run", *args)


TASKS = {"install": install, "dev": dev, "build": build, "run": serve, "test": test, "eval": evaluate}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in TASKS:
        sys.exit(__doc__)
    try:
        TASKS[sys.argv[1]](*sys.argv[2:])
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
    except KeyboardInterrupt:
        pass
