from __future__ import annotations

import sys
from pathlib import Path


def ensure_ios_backend_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    ios_backend = repo_root / "ios" / "backend"
    if not ios_backend.exists():
        return
    ios_backend_path = str(ios_backend)
    if ios_backend_path not in sys.path:
        sys.path.insert(0, ios_backend_path)
