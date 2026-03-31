from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.inference.datasets.dataset_bridge import (
    import_external_basketball_dataset,
    load_records,
    write_imported_rows,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import BARD, E-BARD, SportsMOT, or TrackID3x3 basketball annotations into the canonical hierarchical schema.")
    parser.add_argument("--input", required=True, help="Input .json or .jsonl file containing source annotations.")
    parser.add_argument("--output", required=True, help="Output .json file for canonical rows.")
    parser.add_argument(
        "--source-kind",
        required=True,
        choices=("bard-event", "ebard-detection", "sportsmot-tracking", "trackid3x3-tracking"),
        help="Source adapter to use.",
    )
    parser.add_argument(
        "--source-domain",
        default=None,
        help="Optional canonical sourceDomain tag override. Defaults to the adapter's standard source domain.",
    )
    parser.add_argument(
        "--source-dataset",
        default=None,
        help="Optional source dataset tag override. Defaults to BARD or E-BARD.",
    )
    parser.add_argument(
        "--summary",
        default=None,
        help="Optional path to write an import summary JSON file.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    records = load_records(input_path)
    result = import_external_basketball_dataset(
        records,
        source_kind=args.source_kind,
        source_domain=args.source_domain,
        source_dataset=args.source_dataset,
    )
    write_imported_rows(output_path, result.rows)
    if args.summary:
        summary_path = Path(args.summary)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(result.to_summary(), indent=2, sort_keys=True), encoding="utf-8")
        print(summary_path)
    print(output_path)
    print(json.dumps(result.to_summary(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
