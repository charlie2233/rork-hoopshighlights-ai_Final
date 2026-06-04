#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_EXPECTED_FIELDS = ("teamId", "isHighlight", "eventType", "outcome")
REQUIRED_LABEL_FIELDS = ("needsLabel=false", "reviewedByHuman=true")


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    rows = build_review_queue(
        manifest_path=manifest_path,
        include_complete=args.include_complete,
        limit=args.limit,
    )
    markdown = render_markdown_queue(
        manifest_path=manifest_path,
        rows=rows,
        limit=args.limit,
        include_complete=args.include_complete,
    )
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    if args.json:
        print(
            json.dumps(
                {
                    "manifest": str(manifest_path),
                    "output": str(Path(args.output).expanduser().resolve()) if args.output else None,
                    "rowCount": len(rows),
                    "includeComplete": args.include_complete,
                    "limit": args.limit,
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export a human-review queue from a HoopClips team-highlight accuracy manifest. "
            "This is navigation help only; it does not analyze video or create launch evidence."
        )
    )
    parser.add_argument("--manifest", required=True, help="Team-highlight accuracy manifest JSON.")
    parser.add_argument("--output", help="Write Markdown queue here. Defaults to stdout.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum rows to include. 0 means all rows.")
    parser.add_argument(
        "--include-complete",
        action="store_true",
        help="Include clips that already satisfy all launch label requirements.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable output metadata.")
    return parser.parse_args()


def build_review_queue(*, manifest_path: Path, include_complete: bool, limit: int) -> list[dict[str, Any]]:
    manifest = load_json(manifest_path)
    rows: list[dict[str, Any]] = []
    for case in manifest_cases(manifest):
        labels_path = resolve_manifest_path(manifest_path, case.get("labels"))
        labels = load_json(labels_path)
        case_id = string_or_blank(labels.get("caseId") or case.get("caseId"))
        video_id = string_or_blank(labels.get("videoId") or case.get("videoId"))
        team_mode = string_or_blank(labels.get("teamMode") or case.get("teamMode"))
        selected_team = string_or_blank(labels.get("selectedTeamId") or case.get("selectedTeamId"))
        for clip in labels.get("clips", []):
            if not isinstance(clip, dict):
                continue
            missing = missing_launch_fields(clip)
            if missing and not include_complete:
                rows.append(
                    queue_row(
                        case_id=case_id,
                        video_id=video_id,
                        team_mode=team_mode,
                        selected_team=selected_team,
                        labels_path=labels_path,
                        clip=clip,
                        missing=missing,
                    )
                )
            elif include_complete:
                rows.append(
                    queue_row(
                        case_id=case_id,
                        video_id=video_id,
                        team_mode=team_mode,
                        selected_team=selected_team,
                        labels_path=labels_path,
                        clip=clip,
                        missing=missing,
                    )
                )
    if limit > 0:
        return rows[:limit]
    return rows


def manifest_cases(manifest: Any) -> list[dict[str, Any]]:
    if isinstance(manifest, dict):
        cases = manifest.get("cases")
    elif isinstance(manifest, list):
        cases = manifest
    else:
        cases = None
    if not isinstance(cases, list):
        raise ValueError("Manifest must be a case list or contain a cases array.")
    return [case for case in cases if isinstance(case, dict)]


def resolve_manifest_path(manifest_path: Path, raw_path: Any) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("Manifest case is missing a labels path.")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path.resolve()


def queue_row(
    *,
    case_id: str,
    video_id: str,
    team_mode: str,
    selected_team: str,
    labels_path: Path,
    clip: dict[str, Any],
    missing: list[str],
) -> dict[str, Any]:
    predicted = clip.get("predicted") if isinstance(clip.get("predicted"), dict) else {}
    return {
        "caseId": case_id,
        "videoId": video_id,
        "teamMode": team_mode,
        "selectedTeamId": selected_team,
        "labelsPath": str(labels_path),
        "labelId": string_or_blank(clip.get("labelId")),
        "predictionClipId": string_or_blank(clip.get("predictionClipId")),
        "window": clip_window(clip),
        "eventCenter": seconds_or_blank(predicted.get("eventCenter") or clip.get("eventCenter")),
        "predictedLabel": string_or_blank(predicted.get("label")),
        "predictedTeamId": string_or_blank(predicted.get("teamId")),
        "teamAttributionStatus": string_or_blank(predicted.get("teamAttributionStatus")),
        "predictedOutcome": string_or_blank(predicted.get("outcome")),
        "predictedKeep": predicted.get("keep") if isinstance(predicted.get("keep"), bool) else None,
        "predictionConfidence": number_or_blank(predicted.get("confidence")),
        "missingFields": missing,
    }


def missing_launch_fields(clip: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    expected = clip.get("expected") if isinstance(clip.get("expected"), dict) else {}
    for field in REQUIRED_EXPECTED_FIELDS:
        value = expected.get(field)
        if value is None or value == "":
            missing.append(f"expected.{field}")
    if clip.get("needsLabel") is not False:
        missing.append("needsLabel=false")
    if clip.get("reviewedByHuman") is not True:
        missing.append("reviewedByHuman=true")
    return missing


def clip_window(clip: dict[str, Any]) -> str:
    start = seconds_or_blank(clip.get("start"))
    end = seconds_or_blank(clip.get("end"))
    if start and end:
        return f"{start}-{end}"
    return start or end or ""


def render_markdown_queue(
    *,
    manifest_path: Path,
    rows: list[dict[str, Any]],
    limit: int,
    include_complete: bool,
) -> str:
    title = "# HoopClips Human Label Review Queue"
    lines = [
        title,
        "",
        "This file is reviewer navigation help only. It is not launch evidence, does not mark clips reviewed, and does not replace watching the source video.",
        "",
        "## Summary",
        "",
        f"- Manifest: `{manifest_path}`",
        f"- Queue rows shown: `{len(rows)}`",
        f"- Complete clips included: `{'yes' if include_complete else 'no'}`",
        f"- Row limit: `{'all' if limit <= 0 else limit}`",
        "",
        "Launch evidence still requires every clip to have `expected.teamId`, `expected.isHighlight`, `expected.eventType`, `expected.outcome`, `needsLabel=false`, and `reviewedByHuman=true` after a person watches the source video.",
        "",
        "## Queue",
        "",
    ]
    if not rows:
        lines.append("No rows matched the queue filters.")
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            "| # | case | label | window | predicted | team hint | missing launch fields |",
            "| - | - | - | - | - | - | - |",
        ]
    )
    for index, row in enumerate(rows, start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    markdown_cell(row["caseId"]),
                    markdown_cell(row["labelId"]),
                    markdown_cell(row["window"]),
                    markdown_cell(predicted_cell(row)),
                    markdown_cell(team_cell(row)),
                    markdown_cell(", ".join(row["missingFields"]) or "complete"),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("Use the review page for playback, keyboard shortcuts, progress checkpoints, and the final launch-ready label download.")
    return "\n".join(lines) + "\n"


def predicted_cell(row: dict[str, Any]) -> str:
    parts = []
    if row["predictedLabel"]:
        parts.append(row["predictedLabel"])
    if row["predictedOutcome"]:
        parts.append(f"outcome={row['predictedOutcome']}")
    if row["predictedKeep"] is not None:
        parts.append(f"keep={str(row['predictedKeep']).lower()}")
    if row["predictionConfidence"]:
        parts.append(f"confidence={row['predictionConfidence']}")
    return "; ".join(parts)


def team_cell(row: dict[str, Any]) -> str:
    parts = []
    if row["teamMode"]:
        parts.append(f"mode={row['teamMode']}")
    if row["selectedTeamId"]:
        parts.append(f"selected={row['selectedTeamId']}")
    if row["predictedTeamId"]:
        parts.append(f"predicted={row['predictedTeamId']}")
    if row["teamAttributionStatus"]:
        parts.append(f"status={row['teamAttributionStatus']}")
    return "; ".join(parts)


def markdown_cell(value: Any) -> str:
    text = string_or_blank(value)
    return text.replace("|", "\\|").replace("\n", " ")


def seconds_or_blank(value: Any) -> str:
    number = number_or_none(value)
    if number is None:
        return ""
    return f"{number:.2f}s"


def number_or_blank(value: Any) -> str:
    number = number_or_none(value)
    if number is None:
        return ""
    return f"{number:.4g}"


def number_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def string_or_blank(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(1)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
