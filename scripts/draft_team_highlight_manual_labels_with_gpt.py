#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

REPO_ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[1]
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from scripts.build_launch_team_accuracy_report import manifest_case_entry
from scripts.build_team_highlight_eval_payload import extract_analysis_result, load_json, number_or_none, string_or_none


FORBIDDEN_KEYS = {
    "downloadUrl",
    "presignedUrl",
    "resultObjectKey",
    "sourceObjectKey",
    "sourceUrl",
    "uploadHeaders",
    "uploadUrl",
}

ALLOWED_EVENT_TYPES = {
    "made_shot",
    "missed_shot",
    "three_pointer",
    "layup",
    "dunk",
    "fast_break",
    "block",
    "steal",
    "forced_turnover",
    "defensive_stop",
    "rebound",
    "assist",
    "boring",
    "bad_window",
    "not_basketball",
    "unclear",
}

ALLOWED_OUTCOMES = {
    "made",
    "missed",
    "blocked",
    "steal",
    "forced_turnover",
    "defensive_stop",
    "not_shot",
    "not_highlight",
    "bad_window",
    "not_basketball",
    "unclear",
}

ALLOWED_TEAM_IDS = {"team_black", "team_white", "opponent", "unclear", "not_applicable"}


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    video_paths = parse_video_paths(args.video or [])
    default_video_path = Path(args.video_path).expanduser().resolve() if args.video_path else None
    request_payload = build_openai_draft_request(
        manifest=load_json(manifest_path),
        manifest_dir=manifest_path.parent,
        video_paths=video_paths,
        default_video_path=default_video_path,
        model=args.model or default_model(),
        frames_per_clip=clamp_int(args.frames_per_clip, 3, 8),
        frame_width=clamp_int(args.frame_width, 256, 1280),
        jpeg_quality=clamp_int(args.jpeg_quality, 2, 12),
        case_filter=set(args.case or []),
    )
    if args.context_output:
        write_json(Path(args.context_output), scrub_images_for_context_output(request_payload))

    if args.mock_response:
        response_payload = load_json(Path(args.mock_response))
    else:
        api_key = os.getenv("HOOPS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Set HOOPS_OPENAI_API_KEY or OPENAI_API_KEY to draft labels with GPT.")
        response_payload = call_openai_responses(
            request_payload,
            api_key=api_key,
            endpoint=args.endpoint,
            timeout_seconds=args.timeout_seconds,
        )

    decisions = parse_decisions_response(response_payload)
    bundle = build_draft_bundle(request_payload["metadata"]["labelCases"], decisions)
    output_path = Path(args.output).resolve()
    write_json(output_path, bundle)
    if args.json:
        print(
            json.dumps(
                {
                    "output": str(output_path),
                    "caseCount": len(bundle["cases"]),
                    "clipCount": sum(len(case.get("clips", [])) for case in bundle["cases"]),
                    "source": bundle["source"],
                    "humanReviewRequired": True,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"wrote {output_path}")
        print("human review is still required before launch accuracy evidence can count")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Use GPT vision to draft HoopClips team/highlight manual labels from existing candidate clips and "
            "sampled keyframes only. The output keeps needsLabel=true so human review remains mandatory."
        )
    )
    parser.add_argument("--manifest", required=True, help="Team-highlight accuracy manifest JSON.")
    parser.add_argument("--output", required=True, help="Write a draft team_highlight_manual_labels_bundle.json here.")
    parser.add_argument("--video-path", help="Default local source video path for every case in the manifest.")
    parser.add_argument("--video", action="append", help="Map one video id to a local file path as videoId=/absolute/path.mp4.")
    parser.add_argument("--case", action="append", help="Optional caseId filter. Repeat to draft a subset.")
    parser.add_argument("--model", default=default_model(), help="OpenAI vision-capable model. Defaults from env or gpt-4.1.")
    parser.add_argument("--endpoint", default=os.getenv("HOOPS_OPENAI_RESPONSES_ENDPOINT", "https://api.openai.com/v1/responses"))
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("HOOPS_TEAM_LABEL_DRAFT_TIMEOUT_SECONDS", "90")))
    parser.add_argument("--frames-per-clip", type=int, default=int(os.getenv("HOOPS_TEAM_LABEL_DRAFT_FRAMES_PER_CLIP", "5")))
    parser.add_argument("--frame-width", type=int, default=int(os.getenv("HOOPS_TEAM_LABEL_DRAFT_FRAME_WIDTH", "768")))
    parser.add_argument("--jpeg-quality", type=int, default=int(os.getenv("HOOPS_TEAM_LABEL_DRAFT_JPEG_QUALITY", "5")))
    parser.add_argument("--context-output", help="Optional debug context JSON with image data redacted.")
    parser.add_argument("--mock-response", help="Use a saved OpenAI/structured response JSON instead of calling the API.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output metadata.")
    return parser.parse_args()


def default_model() -> str:
    return os.getenv("HOOPS_TEAM_LABEL_DRAFT_MODEL") or os.getenv("HOOPS_AI_CLIP_GPT_MODEL") or "gpt-4.1"


def parse_video_paths(values: list[str]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--video must use videoId=/absolute/path.mp4")
        video_id, raw_path = value.split("=", 1)
        video_id = video_id.strip()
        if not video_id:
            raise ValueError("--video is missing a video id.")
        mapping[video_id] = Path(raw_path).expanduser().resolve()
    return mapping


def build_openai_draft_request(
    *,
    manifest: dict[str, Any],
    manifest_dir: Path,
    video_paths: dict[str, Path],
    default_video_path: Path | None,
    model: str,
    frames_per_clip: int,
    frame_width: int,
    jpeg_quality: int,
    case_filter: set[str],
) -> dict[str, Any]:
    entries = manifest.get("cases")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifest must contain a non-empty cases array.")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise ValueError("ffmpeg is required to extract review keyframes.")

    label_cases: list[dict[str, Any]] = []
    compact_cases: list[dict[str, Any]] = []
    image_items: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="hoopclips-label-draft-") as temp_dir:
        temp_root = Path(temp_dir)
        for index, raw_entry in enumerate(entries):
            if not isinstance(raw_entry, dict):
                raise ValueError(f"Manifest case {index} must be an object.")
            entry = manifest_case_entry(raw_entry, index, manifest_dir)
            analysis = load_json(entry.analysis_path)
            labels = load_json(entry.labels_path)
            result = extract_analysis_result(analysis)
            case_id = entry.case_id or string_or_none(labels.get("caseId")) or f"case_{index + 1}"
            if case_filter and case_id not in case_filter:
                continue
            video_id = (
                string_or_none(raw_entry.get("videoId"))
                or string_or_none(labels.get("videoId"))
                or string_or_none(result.get("videoId"))
                or case_id
            )
            video_path = video_paths.get(video_id) or default_video_path
            if video_path is None:
                raise ValueError(f"Missing source video path for videoId {video_id!r}. Use --video-path or --video {video_id}=...")
            if not video_path.exists():
                raise ValueError(f"Source video path is missing for videoId {video_id!r}.")
            case_payload, compact_case, case_images = prepare_case_for_gpt(
                case_id=case_id,
                raw_entry=raw_entry,
                labels=labels,
                analysis_result=result,
                video_path=video_path,
                temp_root=temp_root,
                ffmpeg=ffmpeg,
                frames_per_clip=frames_per_clip,
                frame_width=frame_width,
                jpeg_quality=jpeg_quality,
            )
            label_cases.append(case_payload)
            compact_cases.append(compact_case)
            image_items.extend(case_images)

    if not compact_cases:
        raise ValueError("No manifest cases matched the requested filter.")

    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": json.dumps(
                {
                    "task": "Draft HoopClips launch-review labels for existing candidate clips only. Do not mark labels as human-reviewed.",
                    "rules": {
                        "useOnlySuppliedClipIds": True,
                        "doNotInferFromFullVideo": True,
                        "fullVideoNotProvided": True,
                        "keepHumanReviewRequired": True,
                        "blocksStealsDefensiveStopsCanBeHighlights": True,
                        "uncertainAllowedWhenNotClear": True,
                        "eventTypes": sorted(ALLOWED_EVENT_TYPES),
                        "outcomes": sorted(ALLOWED_OUTCOMES),
                        "teamIds": sorted(ALLOWED_TEAM_IDS),
                    },
                    "cases": compact_cases,
                },
                separators=(",", ":"),
            ),
        }
    ]
    for item in image_items:
        content.append({"type": "input_text", "text": item["label"]})
        content.append({"type": "input_image", "image_url": item["dataUrl"], "detail": "high"})

    return {
        "model": model,
        "store": False,
        "instructions": (
            "You are HoopClips Label Draft Assistant. Draft labels for a human reviewer using only the supplied "
            "candidate clip metadata and sampled keyframes. Never claim human review is complete. Never output "
            "file paths, URLs, storage keys, FFmpeg commands, shell commands, or secrets. Use unclear when the "
            "team, event, or outcome is not visible. Selected-team clips should use the visible team when clear; "
            "opponent clips should be marked with the opponent team only if the supplied options allow it."
        ),
        "input": [{"role": "user", "content": content}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "hoopclips_team_label_draft",
                "strict": True,
                "schema": response_schema(),
            }
        },
        "max_output_tokens": 12000,
        "metadata": {"labelCases": label_cases},
    }


def prepare_case_for_gpt(
    *,
    case_id: str,
    raw_entry: dict[str, Any],
    labels: dict[str, Any],
    analysis_result: dict[str, Any],
    video_path: Path,
    temp_root: Path,
    ffmpeg: str,
    frames_per_clip: int,
    frame_width: int,
    jpeg_quality: int,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    clips = [clip for clip in labels.get("clips", []) if isinstance(clip, dict)]
    if not clips:
        raise ValueError(f"Case {case_id} labels must contain at least one clip.")
    detected_teams = sanitize_for_prompt(labels.get("detectedTeams") or analysis_result.get("detectedTeams") or [])
    team_mode = string_or_none(raw_entry.get("teamMode") or labels.get("teamMode")) or "all"
    selected_team_id = string_or_none(raw_entry.get("selectedTeamId") or labels.get("selectedTeamId"))
    selected_color = string_or_none(raw_entry.get("selectedTeamColorLabel") or labels.get("selectedTeamColorLabel"))
    compact_clips: list[dict[str, Any]] = []
    image_items: list[dict[str, Any]] = []
    for clip_index, clip in enumerate(clips):
        predicted = clip.get("predicted") if isinstance(clip.get("predicted"), dict) else {}
        label_id = string_or_none(clip.get("labelId")) or f"label_{clip_index:03d}"
        prediction_clip_id = string_or_none(clip.get("predictionClipId") or clip.get("clipId")) or label_id
        start = number_or_none(clip.get("start")) or 0.0
        end = number_or_none(clip.get("end")) or start
        event_center = number_or_none(predicted.get("eventCenter")) or midpoint(start, end)
        frames = extract_clip_frames(
            video_path=video_path,
            temp_root=temp_root,
            ffmpeg=ffmpeg,
            case_id=case_id,
            label_id=label_id,
            start=start,
            end=end,
            event_center=event_center,
            frames_per_clip=frames_per_clip,
            frame_width=frame_width,
            jpeg_quality=jpeg_quality,
        )
        compact_clips.append(
            {
                "labelId": label_id,
                "predictionClipId": prediction_clip_id,
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(max(0.0, end - start), 3),
                "eventCenter": round(event_center, 3),
                "predicted": sanitize_for_prompt(
                    {
                        "label": predicted.get("label"),
                        "keep": predicted.get("keep"),
                        "outcome": predicted.get("outcome"),
                        "confidence": predicted.get("confidence"),
                        "teamId": predicted.get("teamId"),
                        "teamConfidence": predicted.get("teamConfidence"),
                        "teamAttributionStatus": predicted.get("teamAttributionStatus"),
                    }
                ),
                "sampledKeyframes": [{"role": frame["role"], "time": frame["time"]} for frame in frames],
            }
        )
        for frame in frames:
            image_items.append(
                {
                    "label": f"caseId={case_id}; labelId={label_id}; predictionClipId={prediction_clip_id}; frameRole={frame['role']}; time={frame['time']}",
                    "dataUrl": frame["dataUrl"],
                }
            )
    labels_payload = sanitize_for_bundle(labels)
    labels_payload["caseId"] = case_id
    return (
        labels_payload,
        {
            "caseId": case_id,
            "teamMode": team_mode,
            "selectedTeamId": selected_team_id,
            "selectedTeamColorLabel": selected_color,
            "detectedTeams": detected_teams,
            "clips": compact_clips,
        },
        image_items,
    )


def extract_clip_frames(
    *,
    video_path: Path,
    temp_root: Path,
    ffmpeg: str,
    case_id: str,
    label_id: str,
    start: float,
    end: float,
    event_center: float,
    frames_per_clip: int,
    frame_width: int,
    jpeg_quality: int,
) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for role, second in sample_times(start=start, end=end, event_center=event_center, frames_per_clip=frames_per_clip):
        frame_path = temp_root / f"{safe_id(case_id)}-{safe_id(label_id)}-{role}.jpg"
        if not extract_jpeg_frame(
            ffmpeg=ffmpeg,
            video_path=video_path,
            frame_path=frame_path,
            second=second,
            frame_width=frame_width,
            jpeg_quality=jpeg_quality,
        ):
            continue
        encoded = base64.b64encode(frame_path.read_bytes()).decode("ascii")
        frames.append({"role": role, "time": round(second, 3), "dataUrl": f"data:image/jpeg;base64,{encoded}"})
    return frames


def sample_times(*, start: float, end: float, event_center: float, frames_per_clip: int) -> list[tuple[str, float]]:
    safe_start = max(0.0, start)
    safe_end = max(safe_start, end)
    duration = max(0.001, safe_end - safe_start)
    center = min(max(event_center, safe_start), safe_end)
    times: list[tuple[str, float]] = [
        ("start", safe_start + min(0.15, duration * 0.1)),
        ("eventCenter", center),
        ("finish", max(safe_start, safe_end - min(0.15, duration * 0.1))),
    ]
    if frames_per_clip >= 4:
        times.append(("preEvent", max(safe_start, center - min(1.0, duration * 0.25))))
    if frames_per_clip >= 5:
        times.append(("postEvent", min(safe_end, center + min(1.0, duration * 0.25))))
    if frames_per_clip >= 6:
        times.append(("midAction", midpoint(safe_start, center)))
    if frames_per_clip >= 7:
        times.append(("outcome", midpoint(center, safe_end)))
    if frames_per_clip >= 8:
        times.append(("context", midpoint(safe_start, safe_end)))
    deduped: list[tuple[str, float]] = []
    seen: set[float] = set()
    for role, second in times:
        rounded = round(second, 2)
        if rounded in seen:
            continue
        seen.add(rounded)
        deduped.append((role, second))
    return deduped[:frames_per_clip]


def extract_jpeg_frame(*, ffmpeg: str, video_path: Path, frame_path: Path, second: float, frame_width: int, jpeg_quality: int) -> bool:
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{max(0.0, second):.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale='min({frame_width},iw)':-2",
        "-q:v",
        str(jpeg_quality),
        str(frame_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=8)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return frame_path.is_file() and frame_path.stat().st_size > 0


def call_openai_responses(payload: dict[str, Any], *, api_key: str, endpoint: str, timeout_seconds: float) -> dict[str, Any]:
    request_payload = {key: value for key, value in payload.items() if key != "metadata"}
    request = Request(
        endpoint,
        data=json.dumps(request_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "HoopClipsTeamLabelDraft/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_decisions_response(response_payload: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    output_text = response_payload.get("output_text")
    if not isinstance(output_text, str) or not output_text.strip():
        output_text = extract_output_text(response_payload)
    parsed = json.loads(output_text)
    cases = parsed.get("cases")
    if not isinstance(cases, list):
        raise ValueError("GPT draft response must contain cases array.")
    decisions: dict[str, dict[str, dict[str, Any]]] = {}
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = string_or_none(case.get("caseId"))
        if not case_id:
            raise ValueError("GPT draft case is missing caseId.")
        clips = case.get("clips")
        if not isinstance(clips, list):
            raise ValueError(f"GPT draft case {case_id} is missing clips array.")
        case_decisions: dict[str, dict[str, Any]] = {}
        for clip in clips:
            if not isinstance(clip, dict):
                continue
            label_id = string_or_none(clip.get("labelId"))
            if not label_id:
                raise ValueError(f"GPT draft case {case_id} has clip without labelId.")
            expected = clip.get("expected")
            if not isinstance(expected, dict):
                raise ValueError(f"GPT draft clip {label_id} expected must be an object.")
            decision = normalize_decision(clip)
            case_decisions[label_id] = decision
        decisions[case_id] = case_decisions
    return decisions


def normalize_decision(clip: dict[str, Any]) -> dict[str, Any]:
    expected = clip.get("expected") if isinstance(clip.get("expected"), dict) else {}
    team_id = string_or_none(expected.get("teamId")) or "unclear"
    event_type = string_or_none(expected.get("eventType")) or "unclear"
    outcome = string_or_none(expected.get("outcome")) or "unclear"
    if team_id not in ALLOWED_TEAM_IDS and not team_id.startswith("team_"):
        team_id = "unclear"
    if event_type not in ALLOWED_EVENT_TYPES:
        event_type = "unclear"
    if outcome not in ALLOWED_OUTCOMES:
        outcome = "unclear"
    return {
        "labelId": string_or_none(clip.get("labelId")),
        "predictionClipId": string_or_none(clip.get("predictionClipId")),
        "expected": {
            "teamId": team_id,
            "isHighlight": bool(expected.get("isHighlight")),
            "eventType": event_type,
            "outcome": outcome,
        },
        "confidence": number_or_none(clip.get("confidence")) or 0.0,
        "reason": string_or_none(clip.get("reason")) or "GPT draft; verify before launch evidence.",
        "uncertaintyTags": [str(item) for item in clip.get("uncertaintyTags", []) if isinstance(item, str)][:8],
    }


def build_draft_bundle(label_cases: list[dict[str, Any]], decisions: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for case in label_cases:
        case_id = string_or_none(case.get("caseId"))
        if not case_id:
            raise ValueError("Label case is missing caseId.")
        case_decisions = decisions.get(case_id)
        if case_decisions is None:
            raise ValueError(f"GPT draft response missing case {case_id}.")
        case_copy = json.loads(json.dumps(case))
        clips = [clip for clip in case_copy.get("clips", []) if isinstance(clip, dict)]
        for clip in clips:
            label_id = string_or_none(clip.get("labelId"))
            if not label_id:
                continue
            decision = case_decisions.get(label_id)
            if decision is None:
                raise ValueError(f"GPT draft response missing label {label_id} in case {case_id}.")
            prediction_clip_id = string_or_none(clip.get("predictionClipId"))
            decision_prediction_id = string_or_none(decision.get("predictionClipId"))
            if prediction_clip_id and decision_prediction_id and prediction_clip_id != decision_prediction_id:
                raise ValueError(f"GPT draft predictionClipId mismatch for {case_id}/{label_id}.")
            clip["needsLabel"] = True
            clip["expected"] = decision["expected"]
            clip["labelingNotes"] = draft_note(decision)
        cases.append(case_copy)
    return {
        "schemaVersion": "team-highlight-manual-label-bundle-v1",
        "source": "gpt_draft_requires_human_review",
        "humanReviewRequired": True,
        "cases": cases,
    }


def draft_note(decision: dict[str, Any]) -> str:
    tags = decision.get("uncertaintyTags") or []
    suffix = f" Uncertainty: {', '.join(tags)}." if tags else ""
    confidence = number_or_none(decision.get("confidence")) or 0.0
    return f"GPT draft only; verify manually before launch evidence. confidence={confidence:.2f}. {decision.get('reason')}{suffix}".strip()


def response_schema() -> dict[str, Any]:
    expected = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "teamId": {"type": "string"},
            "isHighlight": {"type": "boolean"},
            "eventType": {"type": "string", "enum": sorted(ALLOWED_EVENT_TYPES)},
            "outcome": {"type": "string", "enum": sorted(ALLOWED_OUTCOMES)},
        },
        "required": ["teamId", "isHighlight", "eventType", "outcome"],
    }
    clip = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "labelId": {"type": "string"},
            "predictionClipId": {"type": ["string", "null"]},
            "expected": expected,
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string", "maxLength": 260},
            "uncertaintyTags": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        },
        "required": ["labelId", "predictionClipId", "expected", "confidence", "reason", "uncertaintyTags"],
    }
    case = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "caseId": {"type": "string"},
            "clips": {"type": "array", "items": clip},
        },
        "required": ["caseId", "clips"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"cases": {"type": "array", "items": case}},
        "required": ["cases"],
    }


def extract_output_text(response_payload: dict[str, Any]) -> str:
    for item in response_payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            refusal = content.get("refusal")
            if isinstance(refusal, str) and refusal:
                raise ValueError("model_refusal")
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text
    raise ValueError("missing_output_text")


def sanitize_for_prompt(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): sanitize_for_prompt(item)
            for key, item in value.items()
            if str(key) not in FORBIDDEN_KEYS and not str(key).lower().endswith("url")
        }
    if isinstance(value, list):
        return [sanitize_for_prompt(item) for item in value]
    return value


def sanitize_for_bundle(value: Any) -> Any:
    return sanitize_for_prompt(value)


def scrub_images_for_context_output(payload: dict[str, Any]) -> dict[str, Any]:
    scrubbed = json.loads(json.dumps(payload))
    scrubbed.pop("metadata", None)
    for item in scrubbed.get("input", []):
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "input_image":
                content["image_url"] = "data:image/jpeg;base64,<redacted>"
    return scrubbed


def midpoint(a: float, b: float) -> float:
    return (a + b) / 2.0


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def safe_id(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)[:80]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
