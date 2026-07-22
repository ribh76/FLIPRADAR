from pathlib import Path
import sys


def ensure_backend_path() -> None:
    project_root = Path(__file__).resolve().parents[1]
    backend_dir = project_root / "backend"
    backend_path = str(backend_dir)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
