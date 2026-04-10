from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.inference.training.spacejam_aux_pretrain import (
    render_spacejam_aux_experiment_report,
    run_spacejam_aux_pretrain_experiment,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a guarded SpaceJam auxiliary-pretraining experiment report without touching the mainline rollout path."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "services" / "inference" / "configs" / "spacejam_aux_pretrain_v1.json",
        help="Path to the SpaceJam auxiliary-pretraining config JSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "services" / "inference" / "evals" / "spacejam_aux_pretrain_v1",
        help="Directory for the JSON and Markdown experiment report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    result = run_spacejam_aux_pretrain_experiment(REPO_ROOT, config_path=args.config)
    json_path = args.output_dir / "experiment_report.json"
    md_path = args.output_dir / "experiment_report.md"
    json_path.write_text(json.dumps(result.to_summary(), indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_spacejam_aux_experiment_report(result), encoding="utf-8")
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
