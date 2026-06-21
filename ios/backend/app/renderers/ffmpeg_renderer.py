from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import subprocess
from typing import Dict, List, Optional, Sequence, Tuple

from ..editing import CaptionStyle, EditPlan, EditPlanClip, get_template_pack
from ..models import APIError


RENDERER_VERSION = "ffmpeg-renderer-v1.3"
BRANDED_OUTRO_BACKGROUND = "0xf97316"
BRANDED_OUTRO_ACCENT = "0xfff7ed"
BRANDED_OUTRO_SHADOW = "0x07111f"
RENDER_SLOW_MOTION_SEGMENTS = False


def ffmpeg_diagnostics(ffmpeg_binary: Optional[str] = None, ffprobe_binary: Optional[str] = None) -> Dict[str, object]:
    ffmpeg = ffmpeg_binary or os.getenv("HOOPS_FFMPEG_BINARY", "ffmpeg")
    ffprobe = ffprobe_binary or os.getenv("HOOPS_FFPROBE_BINARY", "ffprobe")
    ffmpeg_available, ffmpeg_version = _version_probe(ffmpeg)
    ffprobe_available, ffprobe_version = _version_probe(ffprobe)
    return {
        "renderer": "cloud_ffmpeg",
        "rendererVersion": RENDERER_VERSION,
        "ffmpegAvailable": ffmpeg_available,
        "ffprobeAvailable": ffprobe_available,
        "drawtextAvailable": _drawtext_probe(ffmpeg) if ffmpeg_available else False,
        "ffmpegVersion": ffmpeg_version,
        "ffprobeVersion": ffprobe_version,
    }


def _version_probe(binary: str) -> Tuple[bool, Optional[str]]:
    try:
        result = subprocess.run([binary, "-version"], check=True, capture_output=True, text=True, timeout=5)
    except Exception:
        return False, None
    return True, (result.stdout.splitlines() or [None])[0]


def _drawtext_probe(ffmpeg_binary: str) -> bool:
    try:
        result = subprocess.run([ffmpeg_binary, "-hide_banner", "-filters"], check=True, capture_output=True, text=True, timeout=5)
    except Exception:
        return False
    return " drawtext " in result.stdout or " drawtext" in result.stdout


@dataclass(frozen=True)
class FfmpegRenderResult:
    output_path: Path
    duration_seconds: float
    render_log: Dict[str, object]


class FfmpegRenderer:
    def __init__(self, ffmpeg_binary: Optional[str] = None, ffprobe_binary: Optional[str] = None) -> None:
        self._ffmpeg = ffmpeg_binary or os.getenv("HOOPS_FFMPEG_BINARY", "ffmpeg")
        self._ffprobe = ffprobe_binary or os.getenv("HOOPS_FFPROBE_BINARY", "ffprobe")
        self._has_drawtext = self._detect_drawtext()

    def render(self, plan: EditPlan, source_path: Path, work_dir: Path) -> FfmpegRenderResult:
        if not source_path.exists() or source_path.stat().st_size <= 0:
            raise APIError(400, "source_missing", "Source video object was not found.")
        work_dir.mkdir(parents=True, exist_ok=True)

        width, height = self._target_dimensions(plan.aspectRatio)
        template = get_template_pack(plan.templateId)
        segment_paths: List[Path] = []
        commands: List[List[str]] = []
        source_has_audio = self._source_has_audio(source_path)

        for clip_index, clip in enumerate(plan.clips):
            for part_index, part in enumerate(self._split_clip_for_slow_motion(clip)):
                if part[1] - part[0] <= 0.05:
                    continue
                segment_path = work_dir / f"segment_{clip_index:03d}_{part_index:02d}.mp4"
                command = self._segment_command(
                    source_path=source_path,
                    output_path=segment_path,
                    clip=clip,
                    start=part[0],
                    end=part[1],
                    speed=part[2],
                    width=width,
                    height=height,
                    caption_style=template.captionStyle,
                    watermark_text=template.watermarkProfile.displayText,
                    source_has_audio=source_has_audio,
                    watermark_enabled=plan.watermark.enabled,
                )
                self._run(command)
                commands.append(command)
                segment_paths.append(segment_path)

        if plan.outro.enabled and plan.outro.durationSeconds > 0:
            outro_path = work_dir / "outro.mp4"
            command = self._outro_command(outro_path, plan.outro.durationSeconds, width, height, template.displayName)
            self._run(command)
            commands.append(command)
            segment_paths.append(outro_path)

        if not segment_paths:
            raise APIError(400, "empty_render_plan", "EditPlan did not produce renderable segments.")

        concat_path = work_dir / "concat.mp4"
        concat_command = self._concat_command(segment_paths, concat_path)
        self._run(concat_command)
        commands.append(concat_command)

        final_path = work_dir / "final.mp4"
        music_path = resolve_music_track_path(plan.audio.musicTrackId)
        final_command = self._final_audio_command(
            concat_path=concat_path,
            output_path=final_path,
            music_path=music_path,
            music_volume=plan.audio.musicVolume,
            game_audio_volume=plan.audio.gameAudioVolume,
        )
        self._run(final_command)
        commands.append(final_command)

        duration = self._probe_duration(final_path)
        template_signature = {
            "templateId": template.templateId,
            "templateVersion": _template_version(template.templateId),
            "displayName": template.displayName,
            "aspectRatio": plan.aspectRatio,
            "captionStyle": template.captionStyle.styleId,
            "captionDensity": template.captionStyle.density,
            "effectProfile": template.effectProfile.profileId,
            "slowMotionIntensity": template.effectProfile.slowMotionIntensity,
            "audioProfile": template.audioProfile.profileId,
            "musicTrackId": template.audioProfile.musicTrackId,
            "outroProfile": template.outroProfile.profileId,
            "watermarkProfile": template.watermarkProfile.profileId,
            "premiumOnly": template.premiumOnly,
        }
        return FfmpegRenderResult(
            output_path=final_path,
            duration_seconds=duration,
            render_log={
                "renderer": "cloud_ffmpeg",
                "rendererVersion": RENDERER_VERSION,
                "source": str(source_path),
                "output": str(final_path),
                "aspectRatio": plan.aspectRatio,
                "templateId": plan.templateId,
                "captionStyle": template.captionStyle.styleId,
                "templateSignature": template_signature,
                "outroBackground": "branded_court_orange",
                "outroVisualStyle": "bright_end_card_no_black_slate",
                "watermarkAssetId": plan.watermark.assetId or template.watermarkProfile.assetId,
                "outroAssetId": plan.outro.assetId or template.outroProfile.assetId,
                "clipCount": len(plan.clips),
                "segmentCount": len(segment_paths),
                "slowMotionSegmentsRendered": RENDER_SLOW_MOTION_SEGMENTS,
                "durationSeconds": duration,
                "commands": [self._redact_command(command) for command in commands],
            },
        )

    def _segment_command(
        self,
        source_path: Path,
        output_path: Path,
        clip: EditPlanClip,
        start: float,
        end: float,
        speed: float,
        width: int,
        height: int,
        caption_style: CaptionStyle,
        watermark_text: str,
        source_has_audio: bool,
        watermark_enabled: bool,
    ) -> List[str]:
        duration = max(0.05, (end - start) / speed)
        video_filters = [
            f"trim=start={start:.3f}:end={end:.3f}",
            f"setpts=(PTS-STARTPTS)/{speed:.6f}",
            f"scale={width}:{height}:force_original_aspect_ratio=increase",
            self._crop_filter(width, height, clip.cropMode),
            "setsar=1",
            "fps=30",
            "format=yuv420p",
        ]
        if clip.caption:
            video_filters.append(self._caption_overlay_filter(clip.caption, width, height, caption_style))
        if watermark_enabled:
            video_filters.append(self._text_overlay_filter(watermark_text, width, height, x="w-text_w-28", y="h-text_h-24", size=28))

        if source_has_audio:
            audio_filter = f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS"
            if speed != 1.0:
                audio_filter += f",atempo={self._atempo(speed)}"
            audio_filter += "[a]"
            filter_complex = "[0:v]" + ",".join(video_filters) + "[v];" + audio_filter
            return [
                self._ffmpeg,
                "-y",
                "-i",
                str(source_path),
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-t",
                f"{duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(output_path),
            ]

        filter_complex = "[0:v]" + ",".join(video_filters) + "[v];[1:a]atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[a]".format(duration=duration)
        return [
            self._ffmpeg,
            "-y",
            "-i",
            str(source_path),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    def _outro_command(self, output_path: Path, duration: float, width: int, height: int, template_name: str) -> List[str]:
        vf = ",".join(
            [
                f"drawbox=x=0:y=0:w=iw:h=18:color={BRANDED_OUTRO_ACCENT}@0.85:t=fill",
                f"drawbox=x=0:y=h-18:w=iw:h=18:color={BRANDED_OUTRO_ACCENT}@0.85:t=fill",
                f"drawbox=x=(w*0.12):y=(h*0.58):w=(w*0.76):h=8:color={BRANDED_OUTRO_ACCENT}@0.65:t=fill",
                self._outro_text_filter("HoopClips", width, height, y="(h-text_h)/2-42", size=64),
                self._outro_text_filter(template_name, width, height, y="(h-text_h)/2+38", size=30),
                "format=yuv420p",
            ]
        )
        return [
            self._ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={BRANDED_OUTRO_BACKGROUND}:s={width}x{height}:d={duration:.3f}:r=30",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-vf",
            vf,
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    def _concat_command(self, segment_paths: Sequence[Path], output_path: Path) -> List[str]:
        list_path = output_path.parent / "concat.txt"
        list_path.write_text("".join(f"file {shlex.quote(str(path))}\n" for path in segment_paths), encoding="utf-8")
        return [
            self._ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    def _final_audio_command(
        self,
        concat_path: Path,
        output_path: Path,
        music_path: Optional[Path],
        music_volume: float,
        game_audio_volume: float,
    ) -> List[str]:
        if music_path is not None and music_path.exists():
            return [
                self._ffmpeg,
                "-y",
                "-i",
                str(concat_path),
                "-stream_loop",
                "-1",
                "-i",
                str(music_path),
                "-filter_complex",
                "[0:a]volume={game:.3f}[game];[1:a]volume={music:.3f}[music];[game][music]amix=inputs=2:duration=first:dropout_transition=0[a]".format(
                    game=game_audio_volume,
                    music=music_volume,
                ),
                "-map",
                "0:v",
                "-map",
                "[a]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        return [
            self._ffmpeg,
            "-y",
            "-i",
            str(concat_path),
            "-filter:a",
            f"volume={game_audio_volume:.3f}",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    def _split_clip_for_slow_motion(self, clip: EditPlanClip) -> List[Tuple[float, float, float]]:
        if not RENDER_SLOW_MOTION_SEGMENTS:
            return [(clip.sourceStart, clip.sourceEnd, 1.0)]

        slow_ranges = [
            (effect.sourceStart, effect.sourceEnd, effect.speed or 1.0)
            for effect in clip.effects
            if effect.type == "slow_motion" and effect.sourceStart is not None and effect.sourceEnd is not None and effect.sourceEnd > effect.sourceStart
        ]
        if not slow_ranges:
            return [(clip.sourceStart, clip.sourceEnd, 1.0)]

        parts: List[Tuple[float, float, float]] = []
        cursor = clip.sourceStart
        for slow_start, slow_end, speed in sorted(slow_ranges):
            bounded_start = max(clip.sourceStart, min(slow_start, clip.sourceEnd))
            bounded_end = max(clip.sourceStart, min(slow_end, clip.sourceEnd))
            if cursor < bounded_start:
                parts.append((cursor, bounded_start, 1.0))
            if bounded_start < bounded_end:
                parts.append((bounded_start, bounded_end, speed))
            cursor = max(cursor, bounded_end)
        if cursor < clip.sourceEnd:
            parts.append((cursor, clip.sourceEnd, 1.0))
        return parts

    def _caption_overlay_filter(self, text: str, width: int, height: int, caption_style: CaptionStyle) -> str:
        y_position = "h-(text_h*3)"
        if caption_style.density == "clean":
            y_position = "h-(text_h*2.4)"
        elif caption_style.density == "minimal":
            y_position = "h-(text_h*2.1)"
        return self._text_overlay_filter(
            text,
            width,
            height,
            y=y_position,
            size=caption_style.defaultFontSize,
            fontcolor=caption_style.fontColor,
            boxcolor=caption_style.boxColor,
        )

    def _text_overlay_filter(
        self,
        text: str,
        width: int,
        height: int,
        x: str = "(w-text_w)/2",
        y: str = "h-(text_h*3)",
        size: int = 44,
        fontcolor: str = "white",
        boxcolor: str = "black@0.55",
    ) -> str:
        if not self._has_drawtext:
            if x == "w-text_w-28":
                return "drawbox=x=w-210:y=h-72:w=180:h=44:color=black@0.55:t=fill"
            if y.startswith("(h-text_h)/2"):
                return "drawbox=x=(w-500)/2:y=(h-120)/2:w=500:h=120:color=black@0.70:t=fill"
            return "drawbox=x=(w-520)/2:y=h-150:w=520:h=84:color=black@0.55:t=fill"
        _ = width, height
        escaped = self._escape_drawtext(text)
        return "drawtext=text='{text}':fontcolor={fontcolor}:fontsize={size}:box=1:boxcolor={boxcolor}:boxborderw=18:x={x}:y={y}".format(
            text=escaped,
            fontcolor=fontcolor,
            size=size,
            boxcolor=boxcolor,
            x=x,
            y=y,
        )

    def _drawtext_filter(
        self,
        text: str,
        width: int,
        height: int,
        x: str = "(w-text_w)/2",
        y: str = "h-(text_h*3)",
        size: int = 44,
    ) -> str:
        return self._text_overlay_filter(text, width, height, x=x, y=y, size=size)

    def _outro_text_filter(
        self,
        text: str,
        width: int,
        height: int,
        x: str = "(w-text_w)/2",
        y: str = "h-(text_h*3)",
        size: int = 44,
    ) -> str:
        if not self._has_drawtext:
            _ = text, width, height, x, y, size
            return "drawbox=x=(w-560)/2:y=(h-130)/2:w=560:h=130:color=white@0.18:t=fill"
        _ = width, height
        escaped = self._escape_drawtext(text)
        return (
            "drawtext=text='{text}':fontcolor=white:fontsize={size}:"
            "shadowcolor={shadow}:shadowx=4:shadowy=4:x={x}:y={y}"
        ).format(
            text=escaped,
            size=size,
            shadow=BRANDED_OUTRO_SHADOW,
            x=x,
            y=y,
        )

    def _target_dimensions(self, aspect_ratio: str) -> Tuple[int, int]:
        if aspect_ratio == "9:16":
            return 720, 1280
        return 1280, 720

    def _crop_filter(self, width: int, height: int, crop_mode: str) -> str:
        x, y = _crop_focus_expression(crop_mode)
        return f"crop={width}:{height}:{x}:{y}"

    def _source_has_audio(self, source_path: Path) -> bool:
        command = [
            self._ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "json",
            str(source_path),
        ]
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            payload = json.loads(result.stdout or "{}")
            return bool(payload.get("streams"))
        except Exception:
            return False

    def _detect_drawtext(self) -> bool:
        return _drawtext_probe(self._ffmpeg)

    def _probe_duration(self, path: Path) -> float:
        command = [
            self._ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return round(float(result.stdout.strip()), 3)

    def _run(self, command: List[str]) -> None:
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as error:
            raise APIError(500, "ffmpeg_missing", "FFmpeg is not installed or not on PATH.") from error
        except subprocess.CalledProcessError as error:
            stderr = (error.stderr or "").strip()[-1200:]
            raise APIError(500, "ffmpeg_render_failed", f"FFmpeg render command failed. {stderr}") from error

    def _escape_drawtext(self, text: str) -> str:
        return text.replace("\\", "\\\\").replace(":", "\\:").replace(",", "\\,").replace("'", "\\'").replace("%", "\\%").replace("\n", " ")

    def _atempo(self, speed: float) -> str:
        return f"{max(0.5, min(2.0, speed)):.6f}"

    def _redact_command(self, command: List[str]) -> str:
        return " ".join(shlex.quote(part) for part in command)


def _crop_focus_expression(crop_mode: str) -> Tuple[str, str]:
    normalized = crop_mode.strip().lower()
    if normalized == "rim":
        return "(iw-ow)*0.50", "(ih-oh)*0.28"
    if normalized == "ball":
        return "(iw-ow)*0.50", "(ih-oh)*0.42"
    if normalized == "shooter":
        return "(iw-ow)*0.42", "(ih-oh)*0.54"
    return "(iw-ow)/2", "(ih-oh)/2"


def resolve_music_track_path(track_id: str) -> Optional[Path]:
    if track_id == "none":
        return None
    mapping = {
        "hype_01": "real_the_rush.m4a",
        "hype_02": "fast_break.m4a",
        "cinematic_01": "real_atmospheric_drive.m4a",
        "clean_01": "real_lofi_court.m4a",
    }
    filename = mapping.get(track_id)
    if not filename:
        return None
    repo_root = Path(__file__).resolve().parents[4]
    candidates = [
        repo_root / "ios/HoopsClips/HoopsClips/Resources/Audio" / filename,
        repo_root / "ios/HoopsClips/Resources/Audio" / filename,
    ]
    return next((path for path in candidates if path.exists()), None)


def _template_version(template_id: str) -> str:
    parts = template_id.rsplit("_", 1)
    if len(parts) == 2 and parts[1].startswith("v"):
        return parts[1]
    return "v1"
