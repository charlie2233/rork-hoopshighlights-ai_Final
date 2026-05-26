from __future__ import annotations

from array import array
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter
import json
import math
import shutil
import subprocess
import tempfile
import wave
from typing import List, Optional, Sequence, Tuple

from .classifier import classify_window, maybe_relabel_with_gemini
from .config import Settings
from .external_providers import detect_with_optional_external_provider, rerank_with_optional_external_provider
from .models import CandidateWindow, CloudAnalysisResult, CloudClip, CloudDiagnostics, CloudNativeShotSignals, PipelineError, StoredJob, clamp


NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS = 2.0
NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS = 1.25
NATIVE_SHOT_SIGNAL_MIN_DURATION_SECONDS = 3.0
HYBRID_OVERLAP_DEDUPE_RATIO = 0.55
VISUAL_EVENT_SAMPLE_FPS = 2.0
VISUAL_EVENT_FRAME_WIDTH = 64
VISUAL_EVENT_FRAME_HEIGHT = 36
VISUAL_EVENT_MIN_SCORE = 0.46
VISUAL_EVENT_MIN_VISUAL_SCORE = 0.28
VISUAL_EVENT_MIN_GAP_SECONDS = 1.4
VISUAL_EVENT_MAX_BOUNDARIES = 24
VISUAL_EVENT_SEQUENCE_GAP_SECONDS = 1.1
VISUAL_EVENT_CONTEXT_SECONDS = 1.25
VisualFrameSignal = Tuple[float, float, float, float]


@dataclass(frozen=True)
class VisualEventFrame:
    time_seconds: float
    score: float
    visual_score: float
    full_motion: float
    upper_motion: float
    center_motion: float
    audio_score: float


def run_analysis(job: StoredJob, settings: Settings, source_path: Path) -> CloudAnalysisResult:
    started_at = perf_counter()
    if not source_path.exists():
        raise PipelineError("upload_missing", "The uploaded video could not be found.")

    if job.file_size_bytes > settings.max_file_size_bytes:
        raise PipelineError("file_too_large", "Videos larger than 500 MB are not supported in cloud analysis v1.")

    duration_seconds = _probe_duration(source_path, fallback=job.duration_seconds)
    if duration_seconds > settings.max_duration_seconds:
        raise PipelineError("unsupported_duration", "Videos longer than 30 minutes are not supported in cloud analysis right now.")

    provider_tags: list[str] = []
    external_clips, detection_provider = detect_with_optional_external_provider(
        source_path=source_path,
        duration_seconds=duration_seconds,
        settings=settings,
    )

    if detection_provider and settings.detection_provider == "hoopcut":
        provider_tags.append(detection_provider)
        clips = external_clips[: settings.max_returned_clips]
        candidate_segments = len(external_clips)
    else:
        native_clips, native_candidate_segments = _run_native_candidate_detection(source_path, duration_seconds, settings)
        if detection_provider:
            provider_tags.append(detection_provider)
            clips = _merge_hybrid_detection_clips(
                external_clips=external_clips,
                native_clips=native_clips,
                clip_limit=settings.max_returned_clips,
            )
            candidate_segments = len(external_clips) + native_candidate_segments
        else:
            clips = native_clips
            candidate_segments = native_candidate_segments

    clips = _normalize_analysis_clips(clips, duration_seconds, settings)

    clips, ranking_provider = rerank_with_optional_external_provider(
        clips=clips,
        source_path=source_path,
        settings=settings,
    )
    if ranking_provider:
        provider_tags.append(ranking_provider)

    clips, used_gemini = maybe_relabel_with_gemini(clips, settings.use_gemini_relabeling)

    elapsed_ms = int((perf_counter() - started_at) * 1000)
    model_version = settings.backend_model_version
    if provider_tags:
        model_version = "{base}+{providers}".format(
            base=model_version,
            providers="+".join(provider_tags),
        )
    diagnostics = CloudDiagnostics(
        processingMs=max(elapsed_ms, 1),
        backendModelVersion=model_version,
        usedVideoIntelligence=False,
        usedGeminiRelabeling=used_gemini,
        candidateSegments=candidate_segments,
        finalSegments=len(clips),
    )

    return CloudAnalysisResult(
        clipCount=len(clips),
        clips=clips,
        diagnostics=diagnostics,
    )


def _run_native_candidate_detection(
    source_path: Path,
    duration_seconds: float,
    settings: Settings,
) -> tuple[list[CloudClip], int]:
    audio_profile = _extract_audio_profile(source_path, duration_seconds)
    shot_boundaries = _detect_shot_boundaries(source_path, duration_seconds, audio_profile)
    windows = _build_candidate_windows(
        duration_seconds=duration_seconds,
        audio_profile=audio_profile,
        shot_boundaries=shot_boundaries,
        settings=settings,
    )

    if not windows:
        windows = [_fallback_window(duration_seconds, audio_profile, settings)]

    clips = [classify_window(window) for window in windows[: settings.max_returned_clips]]
    return clips, len(windows)


def _normalize_analysis_clips(
    clips: Sequence[CloudClip],
    duration_seconds: float,
    settings: Settings,
) -> list[CloudClip]:
    normalized: list[CloudClip] = []
    for clip in clips:
        normalized_clip = _normalize_clip_for_analysis_context(clip, duration_seconds, settings)
        if normalized_clip is not None:
            normalized.append(normalized_clip)
    return normalized[: settings.max_returned_clips]


def _normalize_clip_for_analysis_context(
    clip: CloudClip,
    duration_seconds: float,
    settings: Settings,
) -> CloudClip | None:
    start = clamp(clip.startTime, 0.0, duration_seconds)
    end = clamp(clip.endTime, 0.0, duration_seconds)
    if end <= start:
        return None

    event_center = clip.eventCenter
    if event_center is not None:
        event_center = clamp(event_center, 0.0, duration_seconds)

    normalized = clip.model_copy(
        update={
            "startTime": round(start, 3),
            "endTime": round(end, 3),
            "eventCenter": round(event_center, 3) if event_center is not None else None,
        }
    )
    if _is_shot_like_label(normalized.label):
        normalized = _expand_shot_clip_for_analysis_context(normalized, duration_seconds, settings)
        if normalized is None:
            return None
        if _analysis_clip_context_score(normalized) < 0.45:
            return None
        auto_keep_allowed = _analysis_clip_auto_keep_allowed(normalized)
        return normalized.model_copy(
            update={
                "shouldAutoKeep": normalized.shouldAutoKeep and auto_keep_allowed,
                "shouldEnableSlowMotion": normalized.shouldEnableSlowMotion and auto_keep_allowed,
                "nativeShotSignals": _native_shot_signals_for_analysis_clip(normalized),
            }
        )

    if normalized.endTime - normalized.startTime < settings.min_clip_duration_seconds:
        return None
    if normalized.endTime - normalized.startTime > settings.max_clip_duration_seconds:
        normalized = normalized.model_copy(
            update={"endTime": round(min(duration_seconds, normalized.startTime + settings.max_clip_duration_seconds), 3)}
        )
    auto_keep_allowed = _analysis_clip_auto_keep_allowed(normalized)
    return normalized.model_copy(
        update={
            "shouldAutoKeep": normalized.shouldAutoKeep and auto_keep_allowed,
            "shouldEnableSlowMotion": normalized.shouldEnableSlowMotion and auto_keep_allowed,
            "nativeShotSignals": _native_shot_signals_for_analysis_clip(normalized),
        }
    )


def _expand_shot_clip_for_analysis_context(
    clip: CloudClip,
    duration_seconds: float,
    settings: Settings,
) -> CloudClip | None:
    if clip.eventCenter is None:
        return None

    event_center = clamp(clip.eventCenter, 0.0, duration_seconds)
    desired_start = min(clip.startTime, event_center - NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS)
    desired_end = max(clip.endTime, event_center + NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
    start = max(0.0, desired_start)
    end = min(duration_seconds, desired_end)

    min_duration = settings.min_clip_duration_seconds
    if end - start < min_duration:
        missing = min_duration - (end - start)
        start = max(0.0, start - (missing / 2.0))
        end = min(duration_seconds, end + (missing / 2.0))
        if end - start < min_duration:
            start = max(0.0, min(start, duration_seconds - min_duration))
            end = min(duration_seconds, start + min_duration)

    if end - start > settings.max_clip_duration_seconds:
        preferred_lead = min(
            settings.max_clip_duration_seconds - NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS,
            max(NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS, settings.max_clip_duration_seconds * 0.66),
        )
        start = max(0.0, event_center - preferred_lead)
        end = min(duration_seconds, start + settings.max_clip_duration_seconds)
        if end < event_center + NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS:
            end = min(duration_seconds, event_center + NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
            start = max(0.0, end - settings.max_clip_duration_seconds)

    if end <= start:
        return None

    lead_in = event_center - start
    follow_through = end - event_center
    if lead_in < NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS:
        return None
    if follow_through < NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS:
        return None
    if end - start < settings.min_clip_duration_seconds:
        return None

    return clip.model_copy(
        update={
            "startTime": round(start, 3),
            "endTime": round(end, 3),
            "eventCenter": round(event_center, 3),
        }
    )


def _analysis_clip_auto_keep_allowed(clip: CloudClip) -> bool:
    if clip.endTime - clip.startTime < 2.0:
        return False
    if clip.combinedScore < 0.55 or clip.confidence < 0.52:
        return False
    if _analysis_clip_context_score(clip) < 0.45:
        return False
    return True


def _analysis_clip_context_score(clip: CloudClip) -> float:
    return _hybrid_clip_context_score(clip)


def _native_shot_signals_for_analysis_clip(clip: CloudClip) -> CloudNativeShotSignals:
    is_shot_like = _is_shot_like_label(clip.label)
    duration = max(0.0, clip.endTime - clip.startTime)
    event_center = clip.eventCenter
    if event_center is None:
        lead_in = 0.0
        follow_through = 0.0
    else:
        bounded_center = min(max(event_center, clip.startTime), clip.endTime)
        lead_in = max(0.0, bounded_center - clip.startTime)
        follow_through = max(0.0, clip.endTime - bounded_center)

    if not is_shot_like:
        setup_context_score = 0.0
        outcome_context_score = 0.0
        event_center_quality = 0.0
        timing_window_ok = duration >= 2.0
    else:
        setup_context_score = min(1.0, lead_in / NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS)
        outcome_context_score = min(1.0, follow_through / NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
        duration_score = min(1.0, duration / max(4.5, NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS + NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS))
        if lead_in <= 0.0 or follow_through <= 0.0:
            balance_score = 0.0
        else:
            balance_score = min(lead_in, follow_through) / max(lead_in, follow_through)
        event_center_quality = (setup_context_score * 0.34) + (outcome_context_score * 0.28) + (duration_score * 0.2) + (balance_score * 0.18)
        timing_window_ok = (
            duration >= NATIVE_SHOT_SIGNAL_MIN_DURATION_SECONDS
            and lead_in >= NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS
            and follow_through >= NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS
        )

    outcome, outcome_confidence = _native_outcome_hint_for_label(clip.label, clip.confidence, is_shot_like)
    return CloudNativeShotSignals(
        isShotLike=is_shot_like,
        leadInSeconds=round(lead_in, 3),
        followThroughSeconds=round(follow_through, 3),
        setupContextScore=round(setup_context_score, 4),
        outcomeContextScore=round(outcome_context_score, 4),
        eventCenterQuality=round(max(0.0, min(1.0, event_center_quality)), 4),
        contextQualityScore=_analysis_clip_context_score(clip),
        timingWindowOk=timing_window_ok,
        outcome=outcome,
        outcomeConfidence=round(outcome_confidence, 4),
    )


def _native_outcome_hint_for_label(label: str, confidence: float, is_shot_like: bool) -> tuple[str, float]:
    if not is_shot_like:
        return "not_shot", 1.0

    normalized = label.strip().lower()
    if any(token in normalized for token in ("block", "blocked")):
        return "blocked", min(1.0, confidence)
    if any(token in normalized for token in ("miss", "missed")):
        return "missed", min(1.0, confidence * 0.85)
    if any(token in normalized for token in ("made", "bucket", "basket", "dunk", "finish")):
        return "made", min(1.0, confidence * 0.9)
    if "attempt" in normalized:
        return "uncertain", 0.0
    if "layup" in normalized:
        return "made", min(1.0, confidence * 0.72)
    return "uncertain", 0.0


def _merge_hybrid_detection_clips(
    *,
    external_clips: Sequence[CloudClip],
    native_clips: Sequence[CloudClip],
    clip_limit: int,
) -> list[CloudClip]:
    ranked = sorted([*external_clips, *native_clips], key=_hybrid_clip_quality_key, reverse=True)
    kept: list[CloudClip] = []
    for clip in ranked:
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(kept)
                if _clip_overlap_ratio(clip, existing) > HYBRID_OVERLAP_DEDUPE_RATIO
            ),
            None,
        )
        if duplicate_index is None:
            kept.append(clip)
            continue
        if _hybrid_clip_quality_key(clip) > _hybrid_clip_quality_key(kept[duplicate_index]):
            kept[duplicate_index] = clip

    kept.sort(key=_hybrid_clip_quality_key, reverse=True)
    return kept[:clip_limit]


def _hybrid_clip_quality_key(clip: CloudClip) -> tuple[float, float, float, float, float, float, float]:
    duration = max(0.0, clip.endTime - clip.startTime)
    return (
        1.0 if duration >= 2.0 else 0.0,
        _hybrid_clip_context_score(clip),
        1.0 if clip.shouldAutoKeep else 0.0,
        clip.combinedScore,
        clip.confidence,
        clip.visualScore,
        clip.motionScore,
    )


def _hybrid_clip_context_score(clip: CloudClip) -> float:
    duration = max(0.0, clip.endTime - clip.startTime)
    if duration < 2.0:
        return 0.0
    if not _is_shot_like_label(clip.label):
        return min(1.0, duration / 4.5)
    if clip.eventCenter is None:
        return 0.2

    event_center = min(max(clip.eventCenter, clip.startTime), clip.endTime)
    lead_in = max(0.0, event_center - clip.startTime)
    follow_through = max(0.0, clip.endTime - event_center)
    if lead_in <= 0.0 or follow_through <= 0.0:
        return 0.0

    lead_score = min(1.0, lead_in / NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS)
    follow_score = min(1.0, follow_through / NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
    duration_score = min(1.0, duration / 4.5)
    balance_score = min(lead_in, follow_through) / max(lead_in, follow_through)
    return round((lead_score * 0.36) + (follow_score * 0.28) + (duration_score * 0.22) + (balance_score * 0.14), 4)


def _clip_overlap_ratio(left: CloudClip, right: CloudClip) -> float:
    overlap = max(0.0, min(left.endTime, right.endTime) - max(left.startTime, right.startTime))
    if overlap <= 0.0:
        return 0.0
    shortest = min(max(left.endTime - left.startTime, 0.001), max(right.endTime - right.startTime, 0.001))
    return overlap / shortest


def _is_shot_like_label(label: str) -> bool:
    normalized = label.strip().lower()
    return any(
        token in normalized
        for token in ("shot", "bucket", "basket", "layup", "dunk", "finish", "jumper", "three", "3pt")
    )


def _probe_duration(path: Path, fallback: float) -> float:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return max(fallback, 1.0)

    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=True)
        payload = json.loads(completed.stdout or "{}")
        duration = float(payload.get("format", {}).get("duration", fallback))
        return max(duration, 1.0)
    except (OSError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError):
        return max(fallback, 1.0)


def _detect_shot_boundaries(
    path: Path,
    duration_seconds: Optional[float] = None,
    audio_profile: Optional[List[float]] = None,
) -> List[float]:
    duration = duration_seconds if duration_seconds is not None else _probe_duration(path, fallback=1.0)
    frame_signals = _extract_visual_frame_signals(path, duration)
    if not frame_signals:
        return []
    return _visual_event_boundaries_from_signals(
        frame_signals,
        audio_profile or [],
        duration_seconds=duration,
    )


def _extract_visual_frame_signals(path: Path, duration_seconds: float) -> List[VisualFrameSignal]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return []

    frame_size = VISUAL_EVENT_FRAME_WIDTH * VISUAL_EVENT_FRAME_HEIGHT * 3
    command = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(path),
        "-vf",
        "fps={fps},scale={width}:{height}:flags=fast_bilinear".format(
            fps=VISUAL_EVENT_SAMPLE_FPS,
            width=VISUAL_EVENT_FRAME_WIDTH,
            height=VISUAL_EVENT_FRAME_HEIGHT,
        ),
        "-an",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=True,
            timeout=max(15.0, min(120.0, duration_seconds * 0.12)),
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []

    raw = completed.stdout or b""
    frame_count = len(raw) // frame_size
    if frame_count < 2:
        return []

    signals: List[VisualFrameSignal] = []
    previous = raw[:frame_size]
    for index in range(1, frame_count):
        start = index * frame_size
        current = raw[start : start + frame_size]
        if len(current) < frame_size:
            break
        time_seconds = index / VISUAL_EVENT_SAMPLE_FPS
        full_motion = _region_motion_score(
            current,
            previous,
            VISUAL_EVENT_FRAME_WIDTH,
            VISUAL_EVENT_FRAME_HEIGHT,
            0,
            VISUAL_EVENT_FRAME_WIDTH,
            0,
            VISUAL_EVENT_FRAME_HEIGHT,
        )
        upper_motion = _region_motion_score(
            current,
            previous,
            VISUAL_EVENT_FRAME_WIDTH,
            VISUAL_EVENT_FRAME_HEIGHT,
            0,
            VISUAL_EVENT_FRAME_WIDTH,
            0,
            VISUAL_EVENT_FRAME_HEIGHT // 2,
        )
        center_motion = _region_motion_score(
            current,
            previous,
            VISUAL_EVENT_FRAME_WIDTH,
            VISUAL_EVENT_FRAME_HEIGHT,
            VISUAL_EVENT_FRAME_WIDTH // 4,
            (VISUAL_EVENT_FRAME_WIDTH * 3) // 4,
            0,
            VISUAL_EVENT_FRAME_HEIGHT,
        )
        signals.append((round(time_seconds, 3), full_motion, upper_motion, center_motion))
        previous = current

    return signals


def _region_motion_score(
    current: bytes,
    previous: bytes,
    width: int,
    height: int,
    x_start: int,
    x_end: int,
    y_start: int,
    y_end: int,
) -> float:
    x_start = max(0, min(x_start, width))
    x_end = max(x_start, min(x_end, width))
    y_start = max(0, min(y_start, height))
    y_end = max(y_start, min(y_end, height))
    total = 0
    count = 0
    for y in range(y_start, y_end):
        row_offset = y * width * 3
        for x in range(x_start, x_end):
            offset = row_offset + (x * 3)
            total += abs(current[offset] - previous[offset])
            total += abs(current[offset + 1] - previous[offset + 1])
            total += abs(current[offset + 2] - previous[offset + 2])
            count += 3
    if count == 0:
        return 0.0
    # Small scaled-frame deltas are meaningful for basketball action, so normalize
    # around a 16/255 mean channel difference instead of requiring scene-cut motion.
    return round(clamp((total / count) / 16.0, 0.0, 1.0), 4)


def _visual_event_boundaries_from_signals(
    frame_signals: Sequence[VisualFrameSignal],
    audio_profile: Sequence[float],
    *,
    duration_seconds: float,
) -> List[float]:
    if not frame_signals:
        return []

    scored_frames: List[VisualEventFrame] = []
    for time_seconds, full_motion, upper_motion, center_motion in frame_signals:
        visual_score = clamp(
            (upper_motion * 0.48) + (center_motion * 0.34) + (full_motion * 0.18),
            0.0,
            1.0,
        )
        audio_score = _audio_peak_near_time(audio_profile, time_seconds)
        edge_penalty = 1.0
        if time_seconds < 1.0 or time_seconds > max(duration_seconds - 0.75, 0.0):
            edge_penalty = 0.62
        score = clamp(((visual_score * 0.78) + (audio_score * 0.22)) * edge_penalty, 0.0, 1.0)
        scored_frames.append(
            VisualEventFrame(
                time_seconds=time_seconds,
                score=round(score, 4),
                visual_score=round(visual_score, 4),
                full_motion=full_motion,
                upper_motion=upper_motion,
                center_motion=center_motion,
                audio_score=audio_score,
            )
        )

    candidates = [
        frame
        for frame in scored_frames
        if frame.visual_score >= VISUAL_EVENT_MIN_VISUAL_SCORE
        and _outcome_aware_visual_event_score(frame, scored_frames) >= VISUAL_EVENT_MIN_SCORE
    ]
    clusters = _cluster_visual_event_frames(candidates)

    selected: List[tuple[float, float]] = []
    for cluster in clusters:
        best_frame = max(
            cluster,
            key=lambda frame: (
                _outcome_aware_visual_event_score(frame, scored_frames)
                + min(max(frame.time_seconds - cluster[0].time_seconds, 0.0) * 0.035, 0.055),
                frame.score,
                frame.time_seconds,
            ),
        )
        selected.append((best_frame.time_seconds, _outcome_aware_visual_event_score(best_frame, scored_frames)))

    selected.sort(key=lambda item: item[1], reverse=True)
    chosen: List[float] = []
    for time_seconds, _ in selected:
        if all(abs(time_seconds - existing) >= VISUAL_EVENT_MIN_GAP_SECONDS for existing in chosen):
            chosen.append(round(time_seconds, 3))
        if len(chosen) >= VISUAL_EVENT_MAX_BOUNDARIES:
            break

    return sorted(chosen)


def _cluster_visual_event_frames(frames: Sequence[VisualEventFrame]) -> List[List[VisualEventFrame]]:
    clusters: List[List[VisualEventFrame]] = []
    for frame in sorted(frames, key=lambda item: item.time_seconds):
        if not clusters or frame.time_seconds - clusters[-1][-1].time_seconds > VISUAL_EVENT_SEQUENCE_GAP_SECONDS:
            clusters.append([frame])
        else:
            clusters[-1].append(frame)
    return clusters


def _outcome_aware_visual_event_score(frame: VisualEventFrame, frames: Sequence[VisualEventFrame]) -> float:
    setup_score = max(
        (
            _shot_context_visual_score(candidate)
            for candidate in frames
            if frame.time_seconds - VISUAL_EVENT_CONTEXT_SECONDS <= candidate.time_seconds <= frame.time_seconds - 0.25
        ),
        default=0.0,
    )
    outcome_score = max(
        (
            _shot_context_visual_score(candidate)
            for candidate in frames
            if frame.time_seconds + 0.25 <= candidate.time_seconds <= frame.time_seconds + VISUAL_EVENT_CONTEXT_SECONDS
        ),
        default=0.0,
    )
    # A release-only spike should not beat the rim/result frame when the
    # surrounding frames show setup and follow-through. Setup carries the
    # strongest weight because it distinguishes a real shot sequence from a
    # random aftermath spike; outcome follow-through breaks close ties.
    context_bonus = min(
        (setup_score * 0.32) + (outcome_score * 0.04) + (min(setup_score, outcome_score) * 0.04),
        0.34,
    )
    return round(clamp(frame.score + context_bonus, 0.0, 1.0), 4)


def _shot_context_visual_score(frame: VisualEventFrame) -> float:
    return clamp((frame.upper_motion * 0.52) + (frame.center_motion * 0.34) + (frame.full_motion * 0.14), 0.0, 1.0)


def _audio_peak_near_time(audio_profile: Sequence[float], time_seconds: float) -> float:
    if not audio_profile:
        return 0.0
    center = max(int(time_seconds / 0.5), 0)
    start = max(center - 1, 0)
    end = min(center + 2, len(audio_profile))
    return clamp(max(audio_profile[start:end] or [0.0]), 0.0, 1.0)


def _extract_audio_profile(path: Path, duration_seconds: float) -> List[float]:
    bucket_count = max(int(math.ceil(duration_seconds / 0.5)), 1)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return [0.0] * bucket_count

    with tempfile.TemporaryDirectory(prefix="hoops-audio-") as temp_dir:
        wav_path = Path(temp_dir) / "audio.wav"
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(wav_path),
        ]
        try:
            subprocess.run(command, capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            return [0.0] * bucket_count

        try:
            with wave.open(str(wav_path), "rb") as wav_file:
                sample_rate = wav_file.getframerate() or 16000
                frames = wav_file.readframes(wav_file.getnframes())
        except (wave.Error, FileNotFoundError):
            return [0.0] * bucket_count

    samples = array("h")
    samples.frombytes(frames)
    if not samples:
        return [0.0] * bucket_count

    samples_per_bucket = max(int(sample_rate * 0.5), 1)
    peaks: List[float] = []
    for index in range(bucket_count):
        start = index * samples_per_bucket
        end = min(start + samples_per_bucket, len(samples))
        if start >= len(samples):
            peaks.append(0.0)
            continue
        bucket = samples[start:end]
        rms = math.sqrt(sum(sample * sample for sample in bucket) / max(len(bucket), 1))
        peaks.append(rms / 32768.0)

    maximum = max(peaks) or 1.0
    return [clamp(value / maximum, 0.0, 1.0) for value in peaks]


def _build_candidate_windows(
    duration_seconds: float,
    audio_profile: List[float],
    shot_boundaries: List[float],
    settings: Settings,
) -> List[CandidateWindow]:
    window_span = min(max(4.5, settings.min_clip_duration_seconds + 1.5), settings.max_clip_duration_seconds)
    stride = 1.5
    windows: List[CandidateWindow] = []

    time_cursor = 0.0
    while time_cursor < duration_seconds:
        end_time = min(duration_seconds, time_cursor + window_span)
        if end_time - time_cursor < settings.min_clip_duration_seconds:
            break

        bucket_start = max(int(time_cursor / 0.5), 0)
        bucket_end = max(int(math.ceil(end_time / 0.5)), bucket_start + 1)
        slice_values = audio_profile[bucket_start:bucket_end] or [0.0]

        audio_score = max(slice_values)
        audio_mean = mean(slice_values)
        volatility = max(audio_score - audio_mean, 0.0)
        center = (time_cursor + end_time) / 2.0
        center_bias = 1.0 - abs((center / max(duration_seconds, 1.0)) - 0.5) * 1.35
        shot_context_score, shot_event_time = _shot_context_score_for_window(
            start_time=time_cursor,
            end_time=end_time,
            center_time=center,
            shot_boundaries=shot_boundaries,
        )
        center_transition_boost = 0.14 if any(abs(boundary - center) <= 1.2 for boundary in shot_boundaries) else 0.0
        context_boost = 0.16 * shot_context_score

        motion_score = clamp(
            (audio_score * 0.65) + (volatility * 1.1) + (center_transition_boost * 0.75) + (context_boost * 0.55),
            0.0,
            1.0,
        )
        visual_score = clamp(
            (audio_mean * 0.45) + (max(center_bias, 0.0) * 0.25) + center_transition_boost + context_boost,
            0.0,
            1.0,
        )
        baseline_score = clamp((audio_score * 0.42) + (motion_score * 0.34) + (visual_score * 0.24), 0.0, 1.0)
        combined_score = clamp(baseline_score + (shot_context_score * 0.12), 0.0, 1.0)
        peak_time = shot_event_time if shot_event_time is not None and shot_context_score >= 0.45 else center

        windows.append(
            CandidateWindow(
                start_time=time_cursor,
                end_time=end_time,
                peak_time=peak_time,
                audio_score=audio_score,
                visual_score=visual_score,
                motion_score=motion_score,
                combined_score=combined_score,
                event_context_score=shot_context_score,
            )
        )

        time_cursor += stride

    segmented = _segment_with_hysteresis(windows, settings)
    if segmented:
        return segmented

    return sorted(windows, key=lambda item: item.combined_score, reverse=True)[: settings.max_returned_clips]


def _shot_context_score_for_window(
    *,
    start_time: float,
    end_time: float,
    center_time: float,
    shot_boundaries: List[float],
) -> tuple[float, float | None]:
    best_score = 0.0
    best_boundary: float | None = None
    duration = max(end_time - start_time, 0.001)
    half_duration = max(duration / 2.0, 0.001)

    for boundary in shot_boundaries:
        if boundary < start_time or boundary > end_time:
            continue

        lead_in = max(0.0, boundary - start_time)
        follow_through = max(0.0, end_time - boundary)
        if lead_in <= 0.0 or follow_through <= 0.0:
            continue
        if lead_in < NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS:
            continue
        if follow_through < NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS:
            continue

        lead_score = min(1.0, lead_in / NATIVE_SHOT_CONTEXT_TARGET_LEAD_SECONDS)
        follow_score = min(1.0, follow_through / NATIVE_SHOT_CONTEXT_TARGET_FOLLOW_THROUGH_SECONDS)
        balance_score = min(lead_in, follow_through) / max(lead_in, follow_through)
        center_score = 1.0 - min(abs(boundary - center_time) / half_duration, 1.0)
        score = (
            (lead_score * 0.34)
            + (follow_score * 0.3)
            + (balance_score * 0.18)
            + (center_score * 0.18)
        )
        if score > best_score:
            best_score = score
            best_boundary = boundary

    return round(clamp(best_score, 0.0, 1.0), 4), best_boundary


def _segment_with_hysteresis(windows: List[CandidateWindow], settings: Settings) -> List[CandidateWindow]:
    high_threshold = 0.66
    low_threshold = 0.48
    active: List[CandidateWindow] = []
    merged: List[CandidateWindow] = []

    for window in windows:
        if not active:
            if window.combined_score >= high_threshold:
                active = [window]
            continue

        if window.combined_score >= low_threshold:
            active.append(window)
            continue

        merged.append(_collapse_windows(active, settings))
        active = [window] if window.combined_score >= high_threshold else []

    if active:
        merged.append(_collapse_windows(active, settings))

    merged.sort(key=lambda item: item.combined_score, reverse=True)
    return merged[: settings.max_returned_clips]


def _collapse_windows(group: List[CandidateWindow], settings: Settings) -> CandidateWindow:
    peak_window = max(group, key=lambda item: (item.event_context_score, item.combined_score))
    anchor_window = peak_window if peak_window.event_context_score >= 0.45 else group[0]

    start_time = max(anchor_window.start_time - settings.clip_padding_seconds, 0.0)
    group_end = peak_window.end_time if peak_window.event_context_score >= 0.45 else group[-1].end_time
    padded_end = group_end + settings.clip_padding_seconds
    max_end = max(group_end, start_time + settings.max_clip_duration_seconds)
    end_time = min(padded_end, max_end)
    duration = end_time - start_time

    if duration < settings.min_clip_duration_seconds:
        end_time = start_time + settings.min_clip_duration_seconds
    if end_time - start_time > settings.max_clip_duration_seconds:
        end_time = start_time + settings.max_clip_duration_seconds

    return CandidateWindow(
        start_time=start_time,
        end_time=end_time,
        peak_time=peak_window.peak_time,
        audio_score=max(item.audio_score for item in group),
        visual_score=mean(item.visual_score for item in group),
        motion_score=max(item.motion_score for item in group),
        combined_score=max(item.combined_score for item in group),
        event_context_score=max(item.event_context_score for item in group),
    )


def _fallback_window(duration_seconds: float, audio_profile: List[float], settings: Settings) -> CandidateWindow:
    peak_index = max(range(len(audio_profile)), key=lambda index: audio_profile[index], default=0)
    center = min((peak_index * 0.5) + 1.0, max(duration_seconds - (settings.min_clip_duration_seconds / 2.0), 0.0))
    start_time = max(center - 1.6, 0.0)
    end_time = min(duration_seconds, start_time + 4.0)
    if end_time - start_time < settings.min_clip_duration_seconds:
        end_time = min(duration_seconds, start_time + settings.min_clip_duration_seconds)

    audio_score = audio_profile[peak_index] if audio_profile else 0.0
    visual_score = clamp(0.35 + (audio_score * 0.2), 0.0, 0.7)
    motion_score = clamp(0.38 + (audio_score * 0.25), 0.0, 0.75)
    combined_score = clamp(0.48 + (audio_score * 0.3), 0.0, 0.82)

    return CandidateWindow(
        start_time=start_time,
        end_time=end_time,
        peak_time=(start_time + end_time) / 2.0,
        audio_score=audio_score,
        visual_score=visual_score,
        motion_score=motion_score,
        combined_score=combined_score,
    )
