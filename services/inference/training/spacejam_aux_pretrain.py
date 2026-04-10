from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from services.inference.app.runtime_models.temporal_event_detector import load_temporal_event_detector_bundle
from services.inference.training.temporal_event_detector import (
    evaluate_temporal_event_detector_bundle,
    load_temporal_event_detector_examples,
)


SPACEJAM_AUX_PRETRAIN_SCHEMA_VERSION = "spacejam-aux-pretrain-v1"
SPACEJAM_AUX_FEATURE_FLAG = "spacejam_aux_pretrain_v1"
DEFAULT_SPACEJAM_SOURCE_DOMAIN = "spacejam:clip"
DEFAULT_SPACEJAM_SOURCE_DATASET = "SpaceJam"
DEFAULT_SPACEJAM_SOURCE_SET = "spacejam_aux_clip_v1"
DEFAULT_SPACEJAM_LABEL_MAP = {
    "shoot": "shot_candidate_aux",
    "no action": "coarse_non_event_aux",
}
SUPPORTED_AUXILIARY_LABELS = ("shot_candidate_aux", "coarse_non_event_aux")
DEFAULT_BUNDLE_PATH = Path("services/inference/models/temporal_event_detector_v1.json")


@dataclass(frozen=True)
class SpaceJamAuxClipExample:
    clip_id: str
    split: str
    raw_label: str
    auxiliary_label: str
    source_ref: str | None
    resolved_source_path: str | None
    video_available: bool
    source_domain: str = DEFAULT_SPACEJAM_SOURCE_DOMAIN
    source_dataset: str = DEFAULT_SPACEJAM_SOURCE_DATASET
    source_set: str = DEFAULT_SPACEJAM_SOURCE_SET
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class SpaceJamAuxImportResult:
    examples: list[SpaceJamAuxClipExample]
    mapped_label_counts: dict[str, int]
    skipped_label_counts: dict[str, int]
    skipped_joint_rows: int
    total_rows: int

    def to_summary(self) -> dict[str, Any]:
        return {
            "schemaVersion": SPACEJAM_AUX_PRETRAIN_SCHEMA_VERSION,
            "totalRows": self.total_rows,
            "mappedRows": len(self.examples),
            "mappedLabelCounts": self.mapped_label_counts,
            "skippedLabelCounts": self.skipped_label_counts,
            "skippedJointRows": self.skipped_joint_rows,
            "videoAvailableRows": sum(1 for example in self.examples if example.video_available),
            "splitCounts": _distribution(example.split for example in self.examples),
        }


@dataclass(frozen=True)
class SpaceJamAuxPretrainConfig:
    schema_version: str
    feature_flag: str
    enabled: bool
    manifest_path: str
    clip_root: str | None
    source_domain: str
    source_dataset: str
    source_set: str
    ignore_joints: bool
    drop_unmapped: bool
    label_map: dict[str, str]
    max_examples: int | None
    pretraining: dict[str, Any]
    fine_tune: dict[str, Any]
    abort_conditions: dict[str, Any]


@dataclass(frozen=True)
class SpaceJamAuxExperimentResult:
    status: str
    recommendation: str
    reason: str
    config: SpaceJamAuxPretrainConfig
    baseline_metrics: dict[str, Any]
    after_metrics: dict[str, Any] | None
    spacejam_summary: dict[str, Any] | None

    def to_summary(self) -> dict[str, Any]:
        return {
            "schemaVersion": SPACEJAM_AUX_PRETRAIN_SCHEMA_VERSION,
            "status": self.status,
            "recommendation": self.recommendation,
            "reason": self.reason,
            "featureFlag": self.config.feature_flag,
            "baselineMetrics": self.baseline_metrics,
            "afterMetrics": self.after_metrics,
            "spacejamSummary": self.spacejam_summary,
            "abortConditions": self.config.abort_conditions,
        }


def load_spacejam_aux_pretrain_config(path: Path) -> SpaceJamAuxPretrainConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema_version = str(payload.get("schemaVersion") or SPACEJAM_AUX_PRETRAIN_SCHEMA_VERSION)
    if schema_version != SPACEJAM_AUX_PRETRAIN_SCHEMA_VERSION:
        raise ValueError(f"Unsupported SpaceJam aux-pretrain config schema: {schema_version}")
    label_map = {
        _normalize_label(key): str(value)
        for key, value in dict(payload.get("spacejam", {}).get("labelMap") or DEFAULT_SPACEJAM_LABEL_MAP).items()
        if value is not None
    }
    return SpaceJamAuxPretrainConfig(
        schema_version=schema_version,
        feature_flag=str(payload.get("featureFlag") or SPACEJAM_AUX_FEATURE_FLAG),
        enabled=bool(payload.get("enabled", False)),
        manifest_path=str(payload.get("spacejam", {}).get("manifestPath") or ""),
        clip_root=_optional_text(payload.get("spacejam", {}).get("clipRoot")),
        source_domain=str(payload.get("spacejam", {}).get("sourceDomain") or DEFAULT_SPACEJAM_SOURCE_DOMAIN),
        source_dataset=str(payload.get("spacejam", {}).get("sourceDataset") or DEFAULT_SPACEJAM_SOURCE_DATASET),
        source_set=str(payload.get("spacejam", {}).get("sourceSet") or DEFAULT_SPACEJAM_SOURCE_SET),
        ignore_joints=bool(payload.get("spacejam", {}).get("ignoreJoints", True)),
        drop_unmapped=bool(payload.get("spacejam", {}).get("dropUnmapped", True)),
        label_map=label_map,
        max_examples=_optional_int(payload.get("spacejam", {}).get("maxExamples")),
        pretraining=dict(payload.get("pretraining") or {}),
        fine_tune=dict(payload.get("fineTune") or {}),
        abort_conditions=dict(payload.get("abortConditions") or {}),
    )


def load_spacejam_clip_examples(
    manifest_path: Path,
    *,
    clip_root: Path | None = None,
    source_domain: str = DEFAULT_SPACEJAM_SOURCE_DOMAIN,
    source_dataset: str = DEFAULT_SPACEJAM_SOURCE_DATASET,
    source_set: str = DEFAULT_SPACEJAM_SOURCE_SET,
    ignore_joints: bool = True,
    drop_unmapped: bool = True,
    label_map: Mapping[str, str] | None = None,
    max_examples: int | None = None,
) -> SpaceJamAuxImportResult:
    payload_rows = _load_spacejam_rows(manifest_path)
    mapped_rows: list[SpaceJamAuxClipExample] = []
    mapped_label_counts: dict[str, int] = {}
    skipped_label_counts: dict[str, int] = {}
    skipped_joint_rows = 0
    normalized_map = {
        _normalize_label(key): str(value)
        for key, value in dict(label_map or DEFAULT_SPACEJAM_LABEL_MAP).items()
    }

    for row in payload_rows:
        modality = _resolve_modality(row)
        if ignore_joints and modality == "joint":
            skipped_joint_rows += 1
            continue
        raw_label = _first_text(row, "label", "action", "class", "className", "category", "activity")
        mapped_label = normalized_map.get(_normalize_label(raw_label or ""))
        if mapped_label is None:
            if drop_unmapped:
                skipped_label = raw_label or "null"
                skipped_label_counts[skipped_label] = skipped_label_counts.get(skipped_label, 0) + 1
                continue
            mapped_label = "unmapped"
        if mapped_label not in SUPPORTED_AUXILIARY_LABELS:
            raise ValueError(f"Unsupported auxiliary label mapping: {mapped_label}")
        source_ref = _first_text(
            row,
            "clipPath",
            "clip_path",
            "sourceRef",
            "source_ref",
            "path",
            "videoPath",
            "video_path",
            "file",
            "filename",
        )
        resolved_source_path = _resolve_clip_path(source_ref, clip_root)
        clip_id = _first_text(row, "clipId", "clip_id", "id", "name") or _derive_clip_id(source_ref, raw_label)
        split = _first_text(row, "split") or _stable_split(clip_id)
        mapped_rows.append(
            SpaceJamAuxClipExample(
                clip_id=clip_id,
                split=split,
                raw_label=raw_label or "unknown",
                auxiliary_label=mapped_label,
                source_ref=source_ref,
                resolved_source_path=resolved_source_path,
                video_available=bool(resolved_source_path and Path(resolved_source_path).exists()),
                source_domain=source_domain,
                source_dataset=source_dataset,
                source_set=source_set,
                metadata=dict(row),
            )
        )
        mapped_label_counts[mapped_label] = mapped_label_counts.get(mapped_label, 0) + 1
        if max_examples is not None and len(mapped_rows) >= max_examples:
            break

    return SpaceJamAuxImportResult(
        examples=mapped_rows,
        mapped_label_counts=dict(sorted(mapped_label_counts.items())),
        skipped_label_counts=dict(sorted(skipped_label_counts.items())),
        skipped_joint_rows=skipped_joint_rows,
        total_rows=len(payload_rows),
    )


def collect_phase4h_baseline_metrics(
    repo_root: Path,
    *,
    bundle_path: Path | None = None,
) -> dict[str, Any]:
    resolved_bundle_path = bundle_path or (repo_root / DEFAULT_BUNDLE_PATH)
    bundle = load_temporal_event_detector_bundle(resolved_bundle_path)
    examples = load_temporal_event_detector_examples(repo_root)
    metrics = evaluate_temporal_event_detector_bundle(bundle, examples)
    flat_label_distribution = dict(metrics.get("flatLabelDistribution") or {})
    total_rows = max(sum(int(value) for value in flat_label_distribution.values()), 1)
    dominant_flat_label_share = round(max((int(value) for value in flat_label_distribution.values()), default=0) / total_rows, 4)
    proposal_outcome_calibration = dict(metrics.get("proposalConditionedOutcomeCalibration") or {})
    return {
        "proposalAcceptanceRate": _round_or_none(metrics.get("proposalAcceptanceRate")),
        "familyGateOpenRate": _round_or_none(metrics.get("familyGateOpenRate")),
        "shotHeadInvocationRate": _round_or_none(metrics.get("shotHeadInvocationRate")),
        "dominantFlatLabelShare": dominant_flat_label_share,
        "flatLabelDistribution": flat_label_distribution,
        "rawEventFamilyOtherRate": _round_or_none(metrics.get("otherDominance")),
        "uncertaintyRate": _round_or_none(metrics.get("uncertaintyRate")),
        "acceptedShotOutcomeAccuracy": _round_or_none(metrics.get("acceptedShotProposalOutcomeAccuracy")),
        "brierScore": _round_or_none(metrics.get("eventnessBrier")),
        "eceLite": _round_or_none(proposal_outcome_calibration.get("expectedCalibrationError")),
        "highlightDominance": _round_or_none(metrics.get("highlightDominance")),
        "missVsMadeConfusion": int(metrics.get("missVsMadeConfusion") or 0),
    }


def run_spacejam_aux_pretrain_experiment(
    repo_root: Path,
    *,
    config_path: Path,
    baseline_metrics: Mapping[str, Any] | None = None,
) -> SpaceJamAuxExperimentResult:
    config = load_spacejam_aux_pretrain_config(config_path)
    baseline = dict(baseline_metrics or collect_phase4h_baseline_metrics(repo_root))
    manifest_path = _resolve_repo_path(repo_root, config.manifest_path)
    clip_root = _resolve_repo_path(repo_root, config.clip_root) if config.clip_root else None

    if not config.enabled:
        return SpaceJamAuxExperimentResult(
            status="disabled",
            recommendation="revise",
            reason="SpaceJam auxiliary pretraining is disabled in the experiment config.",
            config=config,
            baseline_metrics=baseline,
            after_metrics=None,
            spacejam_summary=None,
        )
    if manifest_path is None or not manifest_path.exists():
        return SpaceJamAuxExperimentResult(
            status="blocked_missing_spacejam_manifest",
            recommendation="revise",
            reason="The configured SpaceJam manifest is not present locally, so the auxiliary-pretraining run was not started.",
            config=config,
            baseline_metrics=baseline,
            after_metrics=None,
            spacejam_summary=None,
        )

    imported = load_spacejam_clip_examples(
        manifest_path,
        clip_root=clip_root,
        source_domain=config.source_domain,
        source_dataset=config.source_dataset,
        source_set=config.source_set,
        ignore_joints=config.ignore_joints,
        drop_unmapped=config.drop_unmapped,
        label_map=config.label_map,
        max_examples=config.max_examples,
    )
    summary = imported.to_summary()
    if not imported.examples:
        return SpaceJamAuxExperimentResult(
            status="blocked_no_mapped_examples",
            recommendation="revise",
            reason="SpaceJam rows were found, but none survived the conservative Shoot/No Action mapping.",
            config=config,
            baseline_metrics=baseline,
            after_metrics=None,
            spacejam_summary=summary,
        )
    if not any(example.video_available for example in imported.examples):
        return SpaceJamAuxExperimentResult(
            status="blocked_missing_spacejam_clips",
            recommendation="revise",
            reason="SpaceJam annotations loaded, but no local clip paths resolved for clip-modality auxiliary pretraining.",
            config=config,
            baseline_metrics=baseline,
            after_metrics=None,
            spacejam_summary=summary,
        )

    return SpaceJamAuxExperimentResult(
        status="ready_for_aux_pretraining",
        recommendation="revise",
        reason=(
            "The dataset adapter and guardrails are configured, but this branch intentionally stops short of injecting "
            "auxiliary-pretrained weights into the mainline detector or rollout path."
        ),
        config=config,
        baseline_metrics=baseline,
        after_metrics=None,
        spacejam_summary=summary,
    )


def render_spacejam_aux_experiment_report(result: SpaceJamAuxExperimentResult) -> str:
    lines = [
        "# SpaceJam Auxiliary Pretraining Experiment",
        "",
        f"- Status: `{result.status}`",
        f"- Recommendation: `{result.recommendation}`",
        f"- Reason: {result.reason}",
        f"- Feature flag / config gate: `{result.config.feature_flag}`",
        "",
        "## Scope",
        "",
        "- Training-path only. No runtime contract changes.",
        "- Clip modality only in v1. Joint rows remain ignored.",
        "- Conservative label mapping only: `Shoot -> shot_candidate_aux`, `No Action -> coarse_non_event_aux`.",
        "- Ambiguous SpaceJam classes stay unmapped by default.",
        "",
        "## Baseline Metrics",
        "",
    ]
    for key in (
        "proposalAcceptanceRate",
        "familyGateOpenRate",
        "shotHeadInvocationRate",
        "dominantFlatLabelShare",
        "rawEventFamilyOtherRate",
        "uncertaintyRate",
        "acceptedShotOutcomeAccuracy",
        "brierScore",
        "eceLite",
        "highlightDominance",
        "missVsMadeConfusion",
    ):
        lines.append(f"- {key}: `{result.baseline_metrics.get(key)}`")
    lines.append(f"- flatLabelDistribution: `{result.baseline_metrics.get('flatLabelDistribution')}`")
    lines.append("")
    if result.spacejam_summary is not None:
        lines.extend(
            [
                "## SpaceJam Import Summary",
                "",
                f"- totalRows: `{result.spacejam_summary.get('totalRows')}`",
                f"- mappedRows: `{result.spacejam_summary.get('mappedRows')}`",
                f"- mappedLabelCounts: `{result.spacejam_summary.get('mappedLabelCounts')}`",
                f"- skippedLabelCounts: `{result.spacejam_summary.get('skippedLabelCounts')}`",
                f"- skippedJointRows: `{result.spacejam_summary.get('skippedJointRows')}`",
                f"- videoAvailableRows: `{result.spacejam_summary.get('videoAvailableRows')}`",
                f"- splitCounts: `{result.spacejam_summary.get('splitCounts')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## After Metrics",
            "",
            "- No post-pretraining detector metrics were produced in this branch.",
            "- The auxiliary path stays isolated behind separate config until a real SpaceJam clip export is attached and evaluated offline.",
            "",
            "## Abort Criteria",
            "",
            f"- Configured abort conditions: `{result.config.abort_conditions}`",
            "- Abort immediately if calibration worsens, dominant flat-label share rises, family-gate open rate drops, or collapse behavior regresses.",
            "",
            "## Recommendation",
            "",
            "- `revise`",
            "- Keep the adapter and config scaffolding.",
            "- Do not route this branch into PR #2 or the Phase 4h rollout path.",
            "- Re-run only after a local SpaceJam clip manifest and clip files exist.",
            "",
        ]
    )
    return "\n".join(lines)


def _load_spacejam_rows(path: Path) -> list[Mapping[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        rows: list[Mapping[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(dict(json.loads(line)))
        return rows
    payload = json.loads(text)
    if isinstance(payload, list):
        return [dict(row) for row in payload]
    if isinstance(payload, dict):
        for key in ("records", "annotations", "examples", "clips", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [dict(row) for row in value]
    raise ValueError(f"Unsupported SpaceJam manifest format: {path}")


def _resolve_modality(row: Mapping[str, Any]) -> str:
    modality = _first_text(row, "modality", "sourceKind", "kind", "representation", "type")
    if modality:
        normalized = modality.strip().lower()
        if "joint" in normalized or normalized.endswith(".npy"):
            return "joint"
        if "clip" in normalized or normalized.endswith(".mp4"):
            return "clip"
    source_ref = _first_text(
        row,
        "clipPath",
        "clip_path",
        "sourceRef",
        "source_ref",
        "path",
        "videoPath",
        "video_path",
        "file",
        "filename",
    )
    if source_ref and source_ref.lower().endswith(".npy"):
        return "joint"
    return "clip"


def _resolve_clip_path(source_ref: str | None, clip_root: Path | None) -> str | None:
    if not source_ref:
        return None
    path = Path(source_ref)
    if path.is_absolute():
        return str(path)
    if clip_root is not None:
        return str((clip_root / source_ref).resolve())
    return str(path)


def _derive_clip_id(source_ref: str | None, raw_label: str | None) -> str:
    base = (source_ref or raw_label or "spacejam").strip()
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]
    stem = Path(source_ref).stem if source_ref else "spacejam"
    return f"{stem or 'spacejam'}-{digest}"


def _stable_split(clip_id: str) -> str:
    bucket = int(hashlib.sha1(clip_id.encode("utf-8")).hexdigest()[:8], 16) % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "val"
    return "test"


def _distribution(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))


def _first_text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _normalize_label(label: str) -> str:
    return " ".join(label.strip().lower().replace("_", " ").replace("-", " ").split())


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _resolve_repo_path(repo_root: Path, configured_path: str | None) -> Path | None:
    if not configured_path:
        return None
    candidate = Path(configured_path)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _round_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)
