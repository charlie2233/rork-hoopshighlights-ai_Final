#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "services" / "editing"))
sys.path.insert(0, str(REPO_ROOT / "ios" / "backend"))

from editing_app.config import get_settings  # noqa: E402
from editing_app.render_state import DurableRenderStateStore  # noqa: E402
from editing_app.render_storage import RenderStorage  # noqa: E402
from editing_app.retention_cleanup import format_cleanup_report, run_cleanup  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or execute HoopClips render artifact retention cleanup.")
    parser.add_argument("--execute", action="store_true", help="Delete expired eligible artifacts. Omit for dry-run.")
    parser.add_argument("--upload-root", type=Path, default=None, help="Local render storage root override.")
    parser.add_argument("--render-storage-provider", choices=["local", "r2"], default=None, help="Storage provider override.")
    parser.add_argument("--now", default=None, help="ISO timestamp used as cleanup cutoff. Defaults to current UTC time.")
    parser.add_argument(
        "--retention-class",
        action="append",
        default=None,
        help="Only include this retention class. Can be passed multiple times.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_settings = get_settings()
    overrides = {}
    if args.upload_root is not None:
        overrides["upload_root"] = args.upload_root
    if args.render_storage_provider is not None:
        overrides["render_storage_provider"] = args.render_storage_provider
    settings = replace(base_settings, **overrides) if overrides else base_settings
    storage = RenderStorage(settings)
    store = DurableRenderStateStore(storage)
    now = datetime.fromisoformat(args.now).astimezone(timezone.utc) if args.now else None
    report = run_cleanup(
        storage,
        store,
        execute=args.execute,
        now=now,
        allowed_retention_classes=set(args.retention_class or []) or None,
    )
    print(format_cleanup_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
