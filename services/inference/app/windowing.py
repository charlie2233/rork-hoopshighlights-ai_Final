from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .labels import aggregate_label_scores
from .models import LabelScore, RankedClip, RawLabelScore


WINDOW_POLICY_VERSION = "basketball-windowing-v1"
MIN_CLIP_DURATION_SECONDS = 3.5
TARGET_CLIP_DURATION_MIN_SECONDS = 4.5
TARGET_CLIP_DURATION_MAX_SECONDS = 7.0
SOFT_MAX_STANDARD_SECONDS = 8.0
SOFT_MAX_MULTIEVENT_SECONDS = 10.0
MERGE_GAP_SECONDS = 1.25


@dataclass(frozen=True)
class WindowPreset:
    pre_roll_seconds: float
    post_roll_seconds: float


DEFAULT_PRESETS: dict[str, WindowPreset] = {
    "dunk": WindowPreset(pre_roll_seconds=2.0, post_roll_seconds=2.5),
    "layup": WindowPreset(pre_roll_seconds=2.0, post_roll_seconds=2.5),
    "jumper": WindowPreset(pre_roll_seconds=2.5, post_roll_seconds=2.5),
    "block": WindowPreset(pre_roll_seconds=1.5, post_roll_seconds=3.0),
    "steal": WindowPreset(pre_roll_seconds=1.5, post_roll_seconds=3.0),
    "fast break": WindowPreset(pre_roll_seconds=3.0, post_roll_seconds=3.0),
    "miss": WindowPreset(pre_roll_seconds=2.5, post_roll_seconds=2.0),
}


@dataclass(frozen=True)
class WindowedClipDraft:
    clipId: str
    sourceStartSeconds: float
    sourceEndSeconds: float
    label: str
    action: str
    canonicalLabel: str | None = None
    eventFamily: str | None = None
    eventSubtype: str | None = None
    shotSubtype: str | None = None
    outcome: str | None = None
    eventType: str = "play"
    shotType: str = "unknown"
    makeMiss: str = "unknown"
    confidence: float = 0.0
    resultConfidence: float = 0.0
    confidenceBeforeMapping: float | None = None
    confidenceAfterMapping: float | None = None
    eventFamilyConfidenceBeforeMapping: float | None = None
    eventFamilyConfidenceAfterMapping: float | None = None
    shotSubtypeConfidenceBeforeMapping: float | None = None
    shotSubtypeConfidenceAfterMapping: float | None = None
    outcomeConfidenceBeforeMapping: float | None = None
    outcomeConfidenceAfterMapping: float | None = None
    isUncertain: bool = False
    promptSetVersion: str | None = None
    audioScore: float = 0.0
    visualScore: float = 0.0
    motionScore: float = 0.0
    combinedScore: float = 0.0
    rankScore: float = 0.0
    detectionMethod: str = "model"
    shouldAutoKeep: bool = True
    shouldEnableSlowMotion: bool = False
    topLabels: list[LabelScore] = field(default_factory=list)
    comparisonTopLabels: list[LabelScore] = field(default_factory=list)
    rawTopLabels: list[RawLabelScore] = field(default_factory=list)
    comparisonRawTopLabels: list[RawLabelScore] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BasketballClipWindower:
    minimum_duration_seconds: float = MIN_CLIP_DURATION_SECONDS
    target_min_duration_seconds: float = TARGET_CLIP_DURATION_MIN_SECONDS
    target_max_duration_seconds: float = TARGET_CLIP_DURATION_MAX_SECONDS
    soft_max_duration_seconds: float = SOFT_MAX_STANDARD_SECONDS
    sequence_max_duration_seconds: float = SOFT_MAX_MULTIEVENT_SECONDS
    merge_gap_seconds: float = MERGE_GAP_SECONDS
    window_policy_version: str = WINDOW_POLICY_VERSION
    presets: dict[str, WindowPreset] | None = None

    def __post_init__(self) -> None:
        if self.presets is None:
            self.presets = dict(DEFAULT_PRESETS)

    def apply(self, clips: Sequence[WindowedClipDraft], source_duration_seconds: float) -> list[RankedClip]:
        if not clips:
            return []

        windowed = [
            self._window_draft(clip, source_duration_seconds)
            for clip in sorted(clips, key=lambda item: (self._event_center_seconds(item), item.sourceStartSeconds, item.sourceEndSeconds))
        ]

        merged: list[RankedClip] = []
        for clip in windowed:
            if merged and self._should_merge(merged[-1], clip):
                merged[-1] = self._merge_clips(merged[-1], clip)
            else:
                merged.append(clip)

        return merged

    def _window_draft(self, draft: WindowedClipDraft, source_duration_seconds: float) -> RankedClip:
        source_duration = max(float(source_duration_seconds), 0.0)
        event_center = self._event_center_seconds(draft)

        if source_duration <= self.minimum_duration_seconds and source_duration > 0:
            start_time = 0.0
            end_time = source_duration
        else:
            preset = self._preset_for_label(draft.label, draft.canonicalLabel)
            start_time = max(0.0, event_center - preset.pre_roll_seconds)
            end_time = min(source_duration, event_center + preset.post_roll_seconds)
            start_time, end_time = self._fit_window(
                start_time=start_time,
                end_time=end_time,
                event_center=event_center,
                source_duration=source_duration,
                label=draft.label,
                source_event_count=1,
            )

        clip_duration = max(0.0, end_time - start_time)
        return RankedClip(
            clipId=draft.clipId,
            startTime=round(start_time, 3),
            endTime=round(end_time, 3),
            clipDurationSeconds=round(clip_duration, 3),
            eventCenterSeconds=round(event_center, 3),
            preRollSeconds=round(max(event_center - start_time, 0.0), 3),
            postRollSeconds=round(max(end_time - event_center, 0.0), 3),
            windowPolicyVersion=self.window_policy_version,
            wasMerged=False,
            sourceEventCount=1,
            confidence=min(max(draft.confidence, 0.0), 1.0),
            resultConfidence=min(max(draft.resultConfidence, 0.0), 1.0),
            label=draft.label,
            action=draft.action,
            canonicalLabel=draft.canonicalLabel,
            eventFamily=draft.eventFamily,
            eventSubtype=draft.eventSubtype,
            shotSubtype=draft.shotSubtype,
            outcome=draft.outcome,
            eventType=draft.eventType,
            shotType=draft.shotType,
            makeMiss=draft.makeMiss,
            confidenceBeforeMapping=draft.confidenceBeforeMapping,
            confidenceAfterMapping=draft.confidenceAfterMapping,
            eventFamilyConfidenceBeforeMapping=draft.eventFamilyConfidenceBeforeMapping,
            eventFamilyConfidenceAfterMapping=draft.eventFamilyConfidenceAfterMapping,
            shotSubtypeConfidenceBeforeMapping=draft.shotSubtypeConfidenceBeforeMapping,
            shotSubtypeConfidenceAfterMapping=draft.shotSubtypeConfidenceAfterMapping,
            outcomeConfidenceBeforeMapping=draft.outcomeConfidenceBeforeMapping,
            outcomeConfidenceAfterMapping=draft.outcomeConfidenceAfterMapping,
            isUncertain=draft.isUncertain,
            promptSetVersion=draft.promptSetVersion,
            audioScore=min(max(draft.audioScore, 0.0), 1.0),
            visualScore=min(max(draft.visualScore, 0.0), 1.0),
            motionScore=min(max(draft.motionScore, 0.0), 1.0),
            combinedScore=min(max(draft.combinedScore, 0.0), 1.0),
            rankScore=min(max(draft.rankScore, 0.0), 1.0),
            detectionMethod=draft.detectionMethod,
            shouldAutoKeep=draft.shouldAutoKeep,
            shouldEnableSlowMotion=draft.shouldEnableSlowMotion,
            topLabels=list(draft.topLabels),
            comparisonTopLabels=list(draft.comparisonTopLabels),
            rawTopLabels=list(draft.rawTopLabels),
            comparisonRawTopLabels=list(draft.comparisonRawTopLabels),
            metadata={
                **dict(draft.metadata or {}),
                "event_center_seconds": round(event_center, 3),
                "window_policy_version": self.window_policy_version,
            },
        )

    def _fit_window(
        self,
        *,
        start_time: float,
        end_time: float,
        event_center: float,
        source_duration: float,
        label: str,
        source_event_count: int,
    ) -> tuple[float, float]:
        if source_duration <= 0:
            return 0.0, 0.0

        max_duration = min(self._max_duration_for_label(label, source_event_count), source_duration)
        start_time = max(0.0, min(start_time, source_duration))
        end_time = max(start_time, min(end_time, source_duration))

        start_time, end_time = self._expand_to_minimum(start_time, end_time, source_duration)
        start_time, end_time = self._expand_to_target_minimum(start_time, end_time, source_duration)

        current_duration = end_time - start_time
        if current_duration > max_duration:
            start_time, end_time = self._shrink_to_duration(
                start_time,
                end_time,
                event_center=event_center,
                target_duration=max_duration,
                source_duration=source_duration,
            )

        current_duration = end_time - start_time
        if current_duration < self.minimum_duration_seconds and source_duration > self.minimum_duration_seconds:
            start_time, end_time = self._expand_to_minimum(start_time, end_time, source_duration)

        return round(start_time, 3), round(end_time, 3)

    def _expand_to_minimum(self, start_time: float, end_time: float, source_duration: float) -> tuple[float, float]:
        minimum_duration = min(self.minimum_duration_seconds, source_duration)
        return self._expand_to_duration(start_time, end_time, minimum_duration, source_duration)

    def _expand_to_target_minimum(self, start_time: float, end_time: float, source_duration: float) -> tuple[float, float]:
        target_duration = min(self.target_min_duration_seconds, source_duration)
        if end_time - start_time >= target_duration:
            return start_time, end_time
        return self._expand_to_duration(start_time, end_time, target_duration, source_duration)

    def _expand_to_duration(
        self,
        start_time: float,
        end_time: float,
        target_duration: float,
        source_duration: float,
    ) -> tuple[float, float]:
        if source_duration <= 0 or target_duration <= 0:
            return start_time, end_time

        current_duration = max(end_time - start_time, 0.0)
        if current_duration >= target_duration:
            return start_time, end_time

        remaining = target_duration - current_duration
        left_available = max(start_time, 0.0)
        right_available = max(source_duration - end_time, 0.0)

        left_growth = min(left_available, remaining / 2.0)
        right_growth = min(right_available, remaining - left_growth)

        start_time -= left_growth
        end_time += right_growth
        remaining = target_duration - (end_time - start_time)

        if remaining > 0:
            extra_left = min(start_time, remaining)
            start_time -= extra_left
            remaining -= extra_left
            if remaining > 0:
                end_time = min(source_duration, end_time + remaining)

        return max(0.0, start_time), min(source_duration, end_time)

    def _shrink_to_duration(
        self,
        start_time: float,
        end_time: float,
        *,
        event_center: float,
        target_duration: float,
        source_duration: float,
    ) -> tuple[float, float]:
        target_duration = max(min(target_duration, source_duration), 0.0)
        if target_duration <= 0:
            return start_time, end_time

        current_duration = max(end_time - start_time, 0.0)
        if current_duration <= target_duration:
            return start_time, end_time

        half_window = target_duration / 2.0
        start_time = event_center - half_window
        end_time = event_center + half_window

        if start_time < 0.0:
            end_time = min(source_duration, end_time - start_time)
            start_time = 0.0
        if end_time > source_duration:
            start_time = max(0.0, start_time - (end_time - source_duration))
            end_time = source_duration

        current_duration = end_time - start_time
        if current_duration < target_duration and source_duration > current_duration:
            start_time, end_time = self._expand_to_duration(start_time, end_time, target_duration, source_duration)

        return max(0.0, round(start_time, 3)), min(source_duration, round(end_time, 3))

    def _should_merge(self, left: RankedClip, right: RankedClip) -> bool:
        gap_seconds = right.startTime - left.endTime
        if gap_seconds > self.merge_gap_seconds:
            return False

        merged_duration = max(left.endTime, right.endTime) - min(left.startTime, right.startTime)
        return merged_duration <= self._merged_max_duration(left, right)

    def _merge_clips(self, left: RankedClip, right: RankedClip) -> RankedClip:
        primary = left if (left.rankScore, left.resultConfidence, left.confidence) >= (right.rankScore, right.resultConfidence, right.confidence) else right
        merged_start = min(left.startTime, right.startTime)
        merged_end = max(left.endTime, right.endTime)
        source_event_count = max(int(left.sourceEventCount or 1), 1) + max(int(right.sourceEventCount or 1), 1)
        left_center = left.eventCenterSeconds if left.eventCenterSeconds is not None else self._event_center_from_bounds(left.startTime, left.endTime)
        right_center = right.eventCenterSeconds if right.eventCenterSeconds is not None else self._event_center_from_bounds(right.startTime, right.endTime)
        event_center = self._weighted_center(
            (
                (left_center, left.sourceEventCount or 1),
                (right_center, right.sourceEventCount or 1),
            )
        )

        top_labels = aggregate_label_scores(list(left.topLabels) + list(right.topLabels))
        comparison_top_labels = aggregate_label_scores(list(left.comparisonTopLabels) + list(right.comparisonTopLabels))
        raw_top_labels = _dedupe_raw_scores(list(left.rawTopLabels) + list(right.rawTopLabels))
        comparison_raw_top_labels = _dedupe_raw_scores(list(left.comparisonRawTopLabels) + list(right.comparisonRawTopLabels))

        return primary.model_copy(
            update={
                "startTime": round(merged_start, 3),
                "endTime": round(merged_end, 3),
                "clipDurationSeconds": round(merged_end - merged_start, 3),
                "eventCenterSeconds": round(event_center, 3),
                "preRollSeconds": round(max(event_center - merged_start, 0.0), 3),
                "postRollSeconds": round(max(merged_end - event_center, 0.0), 3),
                "windowPolicyVersion": self.window_policy_version,
                "wasMerged": True,
                "sourceEventCount": source_event_count,
                "eventFamily": primary.eventFamily,
                "eventSubtype": primary.eventSubtype,
                "shotSubtype": primary.shotSubtype,
                "outcome": primary.outcome,
                "confidenceBeforeMapping": max(left.confidenceBeforeMapping or 0.0, right.confidenceBeforeMapping or 0.0),
                "confidenceAfterMapping": max(left.confidenceAfterMapping or 0.0, right.confidenceAfterMapping or 0.0),
                "eventFamilyConfidenceBeforeMapping": max(left.eventFamilyConfidenceBeforeMapping or 0.0, right.eventFamilyConfidenceBeforeMapping or 0.0),
                "eventFamilyConfidenceAfterMapping": max(left.eventFamilyConfidenceAfterMapping or 0.0, right.eventFamilyConfidenceAfterMapping or 0.0),
                "shotSubtypeConfidenceBeforeMapping": max(left.shotSubtypeConfidenceBeforeMapping or 0.0, right.shotSubtypeConfidenceBeforeMapping or 0.0),
                "shotSubtypeConfidenceAfterMapping": max(left.shotSubtypeConfidenceAfterMapping or 0.0, right.shotSubtypeConfidenceAfterMapping or 0.0),
                "outcomeConfidenceBeforeMapping": max(left.outcomeConfidenceBeforeMapping or 0.0, right.outcomeConfidenceBeforeMapping or 0.0),
                "outcomeConfidenceAfterMapping": max(left.outcomeConfidenceAfterMapping or 0.0, right.outcomeConfidenceAfterMapping or 0.0),
                "isUncertain": left.isUncertain or right.isUncertain,
                "promptSetVersion": primary.promptSetVersion or left.promptSetVersion or right.promptSetVersion,
                "confidence": max(left.confidence, right.confidence),
                "resultConfidence": max(left.resultConfidence, right.resultConfidence),
                "rankScore": max(left.rankScore, right.rankScore),
                "audioScore": max(left.audioScore, right.audioScore),
                "visualScore": max(left.visualScore, right.visualScore),
                "motionScore": max(left.motionScore, right.motionScore),
                "combinedScore": max(left.combinedScore, right.combinedScore),
                "shouldAutoKeep": left.shouldAutoKeep or right.shouldAutoKeep,
                "shouldEnableSlowMotion": left.shouldEnableSlowMotion or right.shouldEnableSlowMotion,
                "topLabels": top_labels,
                "comparisonTopLabels": comparison_top_labels,
                "rawTopLabels": raw_top_labels,
                "comparisonRawTopLabels": comparison_raw_top_labels,
                "metadata": {
                    **dict(primary.metadata or {}),
                    "merged_event_labels": self._collect_labels((left, right)),
                    "source_event_ids": self._collect_clip_ids((left, right)),
                    "source_event_count": source_event_count,
                    "window_policy_version": self.window_policy_version,
                },
            }
        )

    def _preset_for_label(self, label: str, canonical_label: str | None = None) -> WindowPreset:
        presets = self.presets or DEFAULT_PRESETS
        normalized = self._normalize_label_key(canonical_label or label)
        return presets.get(normalized, presets["jumper"])

    def _max_duration_for_label(self, label: str, source_event_count: int) -> float:
        normalized = self._normalize_label_key(label)
        if normalized == "fast break" or source_event_count > 1:
            return self.sequence_max_duration_seconds
        return self.soft_max_duration_seconds

    @staticmethod
    def _event_center_from_bounds(start_time: float, end_time: float) -> float:
        return max((start_time + end_time) / 2.0, 0.0)

    def _event_center_seconds(self, draft: WindowedClipDraft) -> float:
        metadata = dict(draft.metadata or {})
        for key in ("event_center_seconds", "source_event_center_seconds"):
            if key in metadata and metadata[key] is not None:
                try:
                    return max(float(metadata[key]), 0.0)
                except (TypeError, ValueError):
                    pass
        if draft.sourceEndSeconds > draft.sourceStartSeconds:
            return max((draft.sourceStartSeconds + draft.sourceEndSeconds) / 2.0, 0.0)
        return max(draft.sourceStartSeconds, 0.0)

    def _merged_max_duration(self, left: RankedClip, right: RankedClip) -> float:
        label_keys = {
            self._normalize_label_key(left.canonicalLabel or left.label),
            self._normalize_label_key(right.canonicalLabel or right.label),
        }
        if "fast break" in label_keys:
            return self.sequence_max_duration_seconds

        event_count = max(int(left.sourceEventCount or 1), 1) + max(int(right.sourceEventCount or 1), 1)
        if event_count > 1:
            return self.sequence_max_duration_seconds
        return self.soft_max_duration_seconds

    @staticmethod
    def _weighted_center(points: Sequence[tuple[float, int]]) -> float:
        weighted_sum = 0.0
        weight_total = 0.0
        for center, weight in points:
            safe_weight = max(float(weight), 1.0)
            weighted_sum += center * safe_weight
            weight_total += safe_weight
        if weight_total <= 0:
            return 0.0
        return weighted_sum / weight_total

    @staticmethod
    def _collect_labels(clips: Iterable[RankedClip]) -> list[str]:
        values: list[str] = []
        for clip in clips:
            values.append(clip.canonicalLabel or clip.label)
        return values

    @staticmethod
    def _collect_clip_ids(clips: Iterable[RankedClip]) -> list[str]:
        return [clip.clipId for clip in clips]

    @staticmethod
    def _normalize_label_key(label: str) -> str:
        return label.strip().lower().replace("_", " ").replace("-", " ")


def window_and_merge_clips(clips: Sequence[WindowedClipDraft], *, source_duration_seconds: float) -> list[RankedClip]:
    return BasketballClipWindower().apply(clips, source_duration_seconds)


def _dedupe_raw_scores(scores: Sequence[RawLabelScore]) -> list[RawLabelScore]:
    best_by_key: dict[tuple[str, str | None], RawLabelScore] = {}
    for score in scores:
        key = (score.rawLabel, score.modelVersion)
        current = best_by_key.get(key)
        if current is None or score.confidence > current.confidence:
            best_by_key[key] = score
    return sorted(best_by_key.values(), key=lambda item: item.confidence, reverse=True)
