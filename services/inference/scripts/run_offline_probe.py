from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.datasets.runtime_training import build_runtime_training_bundle, run_offline_probe


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the offline probe over the runtime training bundle.")
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets" / "runtime_training",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not (args.bundle_dir / "manifest.json").exists():
        build_runtime_training_bundle(repo_root=args.repo_root, output_dir=args.bundle_dir)
    report = run_offline_probe(repo_root=args.repo_root, bundle_dir=args.bundle_dir)
    print(args.bundle_dir / "offline_probe_report.json")
    print(
        "eventFamily={event:.2f} outcome={outcome:.2f} shotSubtype={subtype:.2f} uncertainty={uncertainty:.2f}".format(
            event=report["eventFamily"]["accuracy"],
            outcome=report["outcome"]["accuracy"],
            subtype=report["shotSubtype"]["accuracy"],
            uncertainty=report["uncertaintyRate"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
