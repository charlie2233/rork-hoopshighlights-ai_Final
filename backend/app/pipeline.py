from __future__ import annotations

from array import array
from pathlib import Path
from statistics import mean
from time import perf_counter
import json
import math
import shutil
import subprocess
import tempfile
import wave

from .classifier import classify_window, maybe_relabel_with_gemini
from .config import Settings
from .models import CandidateWindow, CloudAnalysisResult, CloudDiagnostics, PipelineError, StoredJob, clamp


def run_analysis(job: StoredJob, settings: Settings) -> CloudAnalysisResult:
    started_at = perf_counter()
    source_path = Path(job.storage_path or "")
    if not source_path.exists():
        raise PipelineError("upload_missing", "The uploaded video could not be found.")

    if job.file_size_bytes > settings.max_file_size_bytes:
        raise PipelineError("file_too_large", "Videos larger than 500 MB are not supported in cloud analysis v1.")

    duration_seconds = _probe_duration(source_path, fallback=job.duration_seconds)
    if duration_seconds > settings.max_duration_seconds:
        raise PipelineError("unsupported_duration", "Videos longer than 10 minutes are not supported in cloud analysis v1.")

    shot_boundaries = _detect_shot_boundaries(source_path)
    audio_profile = _extract_audio_profile(source_path, duration_seconds)
    windows = _build_candidate_windows(
        duration_seconds=duration_seconds,
        audio_profile=audio_profile,
        shot_boundaries=shot_boundaries,
        settings=settings,
    )

    if not windows:
        windows = [_fallback_window(duration_seconds, audio_profile, settings)]

    clips = [classify_window(window) for window in windows[: settings.max_returned_clips]]
    clips, used_gemini = maybe_relabel_with_gemini(clips, settings.use_gemini_relabeling)

    elapsed_ms = int((perf_counter() - started_at) * 1000)
    diagnostics = CloudDiagnostics(
        processingMs=max(elapsed_ms, 1),
        backendModelVersion=settings.backend_model_version,
        usedVideoIntelligence=False,
        usedGeminiRelabeling=used_gemini,
        candidateSegments=len(windows),
        finalSegments=len(clips),
    )

    return CloudAnalysisResult(
        clipCount=len(clips),
        clips=clips,
        diagnostics=diagnostics,
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


def _detect_shot_boundaries(path: Path) -> list[float]:
    # Google Video Intelligence is not invoked in the local scaffold. This hook
    # keeps the pipeline shape stable so the storage/store contract stays the same
    # when the Cloud Run service is later wired to GCP managed services.
    _ = path
    return []


def _extract_audio_profile(path: Path, duration_seconds: float) -> list[float]:
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
    peaks: list[float] = []
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
    audio_profile: list[float],
    shot_boundaries: list[float],
    settings: Settings,
) -> list[CandidateWindow]:
    window_span = min(max(4.5, settings.min_clip_duration_seconds + 1.5), settings.max_clip_duration_seconds)
    stride = 1.5
    windows: list[CandidateWindow] = []

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
        transition_boost = 0.14 if any(abs(boundary - center) <= 1.2 for boundary in shot_boundaries) else 0.0

        motion_score = clamp((audio_score * 0.65) + (volatility * 1.1) + (transition_boost * 0.75), 0.0, 1.0)
        visual_score = clamp((audio_mean * 0.45) + (max(center_bias, 0.0) * 0.25) + transition_boost, 0.0, 1.0)
        combined_score = clamp((audio_score * 0.42) + (motion_score * 0.34) + (visual_score * 0.24), 0.0, 1.0)

        windows.append(
            CandidateWindow(
                start_time=time_cursor,
                end_time=end_time,
                peak_time=center,
                audio_score=audio_score,
                visual_score=visual_score,
                motion_score=motion_score,
                combined_score=combined_score,
            )
        )

        time_cursor += stride

    segmented = _segment_with_hysteresis(windows, settings)
    if segmented:
        return segmented

    return sorted(windows, key=lambda item: item.combined_score, reverse=True)[: min(3, len(windows))]


def _segment_with_hysteresis(windows: list[CandidateWindow], settings: Settings) -> list[CandidateWindow]:
    high_threshold = 0.66
    low_threshold = 0.48
    active: list[CandidateWindow] = []
    merged: list[CandidateWindow] = []

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


def _collapse_windows(group: list[CandidateWindow], settings: Settings) -> CandidateWindow:
    start_time = max(group[0].start_time - settings.clip_padding_seconds, 0.0)
    end_time = min(group[-1].end_time + settings.clip_padding_seconds, group[-1].end_time + settings.clip_padding_seconds)
    duration = end_time - start_time

    if duration < settings.min_clip_duration_seconds:
        end_time = start_time + settings.min_clip_duration_seconds
    if end_time - start_time > settings.max_clip_duration_seconds:
        end_time = start_time + settings.max_clip_duration_seconds

    peak_window = max(group, key=lambda item: item.combined_score)
    return CandidateWindow(
        start_time=start_time,
        end_time=end_time,
        peak_time=peak_window.peak_time,
        audio_score=max(item.audio_score for item in group),
        visual_score=mean(item.visual_score for item in group),
        motion_score=max(item.motion_score for item in group),
        combined_score=max(item.combined_score for item in group),
    )


def _fallback_window(duration_seconds: float, audio_profile: list[float], settings: Settings) -> CandidateWindow:
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
