from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from pydantic import Field, model_validator

from .models import APIModel, now_utc


PresetId = Literal[
    "personal_highlight",
    "full_game_highlight",
    "coach_review",
    "fast_break_mix",
    "best_five",
]
AspectRatio = Literal["9:16", "16:9", "source"]
PlanTier = Literal["free", "pro"]
RevisionCommand = Literal[
    "make_shorter",
    "make_longer",
    "make_more_hype",
    "make_nba_style",
    "make_personal",
    "remove_weak_clips",
    "add_more_slow_motion",
    "use_original_audio",
    "export_vertical",
    "export_widescreen",
    "reduce_captions",
    "show_more_full_play_context",
]


EDIT_PLAN_VERSION = "edit-plan-v1"
RENDER_MODE = "cloud_ffmpeg"
MIN_PLAN_CLIP_SECONDS = 2.0
MAX_CAPTION_LENGTH = 24
MAX_DURATION_OVERRUN_SECONDS = 6.0

LICENSED_MUSIC_TRACKS = {
    "hype_01",
    "hype_02",
    "cinematic_01",
    "clean_01",
    "none",
}


class EditCandidateClip(APIModel):
    id: str = Field(min_length=1, max_length=80)
    start: float = Field(ge=0.0)
    end: float = Field(gt=0.0)
    eventCenter: float = Field(ge=0.0)
    label: str = Field(default="Highlight", min_length=1, max_length=80)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    excitement: float = Field(default=0.0, ge=0.0, le=1.0)
    watchability: float = Field(default=0.0, ge=0.0, le=1.0)
    motionScore: float = Field(default=0.0, ge=0.0, le=1.0)
    audioPeak: float = Field(default=0.0, ge=0.0, le=1.0)
    combinedScore: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    duplicateGroup: Optional[str] = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def validate_bounds(self) -> "EditCandidateClip":
        if self.end <= self.start:
            raise ValueError("clip end must be after start")
        if not self.start <= self.eventCenter <= self.end:
            raise ValueError("eventCenter must be inside clip bounds")
        return self

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def planning_score(self) -> float:
        if self.combinedScore is not None:
            return self.combinedScore
        return round(
            (self.confidence * 0.25)
            + (self.excitement * 0.3)
            + (self.watchability * 0.2)
            + (self.motionScore * 0.15)
            + (self.audioPeak * 0.1),
            4,
        )


class EditPreset(APIModel):
    presetId: PresetId
    displayName: str
    defaultAspectRatio: AspectRatio
    durationOptions: List[int]
    ordering: str
    pacing: str
    clipLengthRangeSeconds: Tuple[float, float]
    musicTrackId: str
    gameAudioVolume: float = Field(ge=0.0, le=1.0)
    captionStyle: str
    slowMotionIntensity: str
    themeId: str
    effects: List[str]
    outroTemplateId: str


class EditTheme(APIModel):
    themeId: str
    displayName: str
    captionStyle: str
    colorway: str


PRESET_REGISTRY: Dict[str, EditPreset] = {
    "personal_highlight": EditPreset(
        presetId="personal_highlight",
        displayName="Personal Highlight",
        defaultAspectRatio="9:16",
        durationOptions=[15, 30, 45],
        ordering="best_first",
        pacing="fast",
        clipLengthRangeSeconds=(4.5, 6.5),
        musicTrackId="hype_01",
        gameAudioVolume=0.25,
        captionStyle="bold_hype",
        slowMotionIntensity="high",
        themeId="hype_black_gold",
        effects=["punch_zoom", "speed_ramp", "impact_flash"],
        outroTemplateId="free_hoopclips_outro",
    ),
    "full_game_highlight": EditPreset(
        presetId="full_game_highlight",
        displayName="Full Game Highlight",
        defaultAspectRatio="16:9",
        durationOptions=[60, 90, 120],
        ordering="chronological_with_best_moments_boosted",
        pacing="medium",
        clipLengthRangeSeconds=(5.5, 8.0),
        musicTrackId="cinematic_01",
        gameAudioVolume=0.55,
        captionStyle="clean_scorebug",
        slowMotionIntensity="low_medium",
        themeId="nba_clean",
        effects=["clean_cut", "subtle_replay", "lower_third"],
        outroTemplateId="standard_hoopclips_outro",
    ),
    "coach_review": EditPreset(
        presetId="coach_review",
        displayName="Coach Review",
        defaultAspectRatio="source",
        durationOptions=[60, 120, 180],
        ordering="chronological",
        pacing="slow",
        clipLengthRangeSeconds=(6.0, 10.0),
        musicTrackId="none",
        gameAudioVolume=1.0,
        captionStyle="plain",
        slowMotionIntensity="manual_only",
        themeId="coach_simple",
        effects=[],
        outroTemplateId="minimal_hoopclips_outro",
    ),
    "fast_break_mix": EditPreset(
        presetId="fast_break_mix",
        displayName="Fast Break Mix",
        defaultAspectRatio="9:16",
        durationOptions=[15, 30],
        ordering="best_first",
        pacing="very_fast",
        clipLengthRangeSeconds=(3.5, 5.5),
        musicTrackId="hype_02",
        gameAudioVolume=0.2,
        captionStyle="bold_hype",
        slowMotionIntensity="medium",
        themeId="hype_black_gold",
        effects=["punch_zoom", "speed_ramp"],
        outroTemplateId="free_hoopclips_outro",
    ),
    "best_five": EditPreset(
        presetId="best_five",
        displayName="Best Five",
        defaultAspectRatio="9:16",
        durationOptions=[30, 45],
        ordering="best_first",
        pacing="fast",
        clipLengthRangeSeconds=(4.5, 7.0),
        musicTrackId="clean_01",
        gameAudioVolume=0.3,
        captionStyle="bold_hype",
        slowMotionIntensity="medium",
        themeId="hype_black_gold",
        effects=["punch_zoom", "impact_flash"],
        outroTemplateId="free_hoopclips_outro",
    ),
}

THEME_REGISTRY: Dict[str, EditTheme] = {
    "hype_black_gold": EditTheme(
        themeId="hype_black_gold",
        displayName="Hype Black Gold",
        captionStyle="bold_hype",
        colorway="black_gold",
    ),
    "nba_clean": EditTheme(
        themeId="nba_clean",
        displayName="NBA Clean",
        captionStyle="clean_scorebug",
        colorway="navy_white",
    ),
    "coach_simple": EditTheme(
        themeId="coach_simple",
        displayName="Coach Simple",
        captionStyle="plain",
        colorway="graphite",
    ),
}


class CreateEditJobRequest(APIModel):
    videoId: str = Field(min_length=1, max_length=120)
    analysisJobId: str = Field(min_length=1, max_length=120)
    installId: str = Field(min_length=8, max_length=128)
    preset: PresetId = "personal_highlight"
    theme: Optional[str] = Field(default=None, max_length=80)
    targetDurationSeconds: int = Field(gt=0, le=180)
    aspectRatio: Optional[AspectRatio] = None
    planTier: PlanTier = "free"
    clips: List[EditCandidateClip] = Field(min_length=1, max_length=30)


class EditUserIntent(APIModel):
    preset: PresetId
    targetDurationSeconds: int
    aspectRatio: Optional[AspectRatio]
    planTier: PlanTier


class EditClipPoolSummary(APIModel):
    clipCount: int
    totalCandidateDuration: float
    topLabels: List[str]
    duplicateGroups: int


class EditContext(APIModel):
    videoId: str
    analysisJobId: str
    userIntent: EditUserIntent
    clipPoolSummary: EditClipPoolSummary
    clips: List[EditCandidateClip]
    availablePresets: List[str]
    availableThemes: List[str]
    availableMusicTracks: List[str]


class ReviseEditJobRequest(APIModel):
    command: RevisionCommand
    targetDurationSeconds: Optional[int] = Field(default=None, gt=0, le=180)
    aspectRatio: Optional[AspectRatio] = None


class EditPlanAudio(APIModel):
    mode: str
    musicTrackId: str
    musicVolume: float = Field(ge=0.0, le=1.0)
    gameAudioVolume: float = Field(ge=0.0, le=1.0)


class EditPlanEffect(APIModel):
    type: str
    at: Optional[float] = None
    sourceStart: Optional[float] = None
    sourceEnd: Optional[float] = None
    speed: Optional[float] = Field(default=None, gt=0.0)
    strength: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class EditPlanClip(APIModel):
    clipId: str
    sourceStart: float = Field(ge=0.0)
    sourceEnd: float = Field(gt=0.0)
    eventCenter: float = Field(ge=0.0)
    timelineStart: float = Field(ge=0.0)
    timelineEnd: float = Field(gt=0.0)
    label: str
    caption: str = Field(max_length=MAX_CAPTION_LENGTH)
    cropMode: str
    effects: List[EditPlanEffect] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_clip_bounds(self) -> "EditPlanClip":
        if self.sourceEnd <= self.sourceStart:
            raise ValueError("sourceEnd must be after sourceStart")
        if self.timelineEnd <= self.timelineStart:
            raise ValueError("timelineEnd must be after timelineStart")
        if not self.sourceStart <= self.eventCenter <= self.sourceEnd:
            raise ValueError("eventCenter must be inside source bounds")
        return self

    @property
    def timeline_duration(self) -> float:
        return self.timelineEnd - self.timelineStart


class TimedTemplate(APIModel):
    enabled: bool
    durationSeconds: float = Field(ge=0.0)
    templateId: str


class EditPlanWatermark(APIModel):
    enabled: bool
    position: str


class EditPlan(APIModel):
    version: str = EDIT_PLAN_VERSION
    editJobId: str
    videoId: str
    analysisJobId: str
    preset: PresetId
    theme: str
    targetDurationSeconds: int
    aspectRatio: AspectRatio
    renderMode: str = RENDER_MODE
    audio: EditPlanAudio
    clips: List[EditPlanClip]
    intro: TimedTemplate
    outro: TimedTemplate
    watermark: EditPlanWatermark


class EditPlanValidationIssue(APIModel):
    field: str
    code: str
    message: str


class EditJobResponse(APIModel):
    editJobId: str
    videoId: str
    analysisJobId: str
    status: str
    preset: PresetId
    targetDurationSeconds: int
    aspectRatio: AspectRatio
    clipCount: int
    validationErrors: List[EditPlanValidationIssue]


class EditPlanResponse(APIModel):
    editJobId: str
    status: str
    plan: EditPlan
    validationErrors: List[EditPlanValidationIssue]


@dataclass
class StoredEditJob:
    edit_job_id: str
    install_id: str
    request: CreateEditJobRequest
    plan: EditPlan
    status: str
    created_at: datetime
    updated_at: datetime
    validation_errors: List[EditPlanValidationIssue]

    def to_response(self) -> EditJobResponse:
        return EditJobResponse(
            editJobId=self.edit_job_id,
            videoId=self.request.videoId,
            analysisJobId=self.request.analysisJobId,
            status=self.status,
            preset=self.plan.preset,
            targetDurationSeconds=self.plan.targetDurationSeconds,
            aspectRatio=self.plan.aspectRatio,
            clipCount=len(self.plan.clips),
            validationErrors=self.validation_errors,
        )

    def to_plan_response(self) -> EditPlanResponse:
        return EditPlanResponse(
            editJobId=self.edit_job_id,
            status=self.status,
            plan=self.plan,
            validationErrors=self.validation_errors,
        )


def summarize_clip_pool(clips: Sequence[EditCandidateClip]) -> Dict[str, object]:
    labels: Dict[str, int] = {}
    duplicate_groups = set()
    for clip in clips:
        labels[clip.label] = labels.get(clip.label, 0) + 1
        if clip.duplicateGroup:
            duplicate_groups.add(clip.duplicateGroup)
    return {
        "clipCount": len(clips),
        "totalCandidateDuration": round(sum(clip.duration for clip in clips), 2),
        "topLabels": [label for label, _ in sorted(labels.items(), key=lambda item: item[1], reverse=True)[:5]],
        "duplicateGroups": len(duplicate_groups),
    }


def build_edit_context(request: CreateEditJobRequest) -> EditContext:
    return EditContext(
        videoId=request.videoId,
        analysisJobId=request.analysisJobId,
        userIntent=EditUserIntent(
            preset=request.preset,
            targetDurationSeconds=request.targetDurationSeconds,
            aspectRatio=request.aspectRatio,
            planTier=request.planTier,
        ),
        clipPoolSummary=EditClipPoolSummary(**summarize_clip_pool(request.clips)),
        clips=request.clips,
        availablePresets=list(PRESET_REGISTRY.keys()),
        availableThemes=list(THEME_REGISTRY.keys()),
        availableMusicTracks=sorted(LICENSED_MUSIC_TRACKS),
    )


def rank_clips(clips: Sequence[EditCandidateClip]) -> List[EditCandidateClip]:
    return sorted(
        clips,
        key=lambda clip: (clip.planning_score, clip.watchability, clip.excitement, -clip.start),
        reverse=True,
    )


def remove_duplicate_moments(clips: Sequence[EditCandidateClip]) -> List[EditCandidateClip]:
    best_by_group: Dict[str, EditCandidateClip] = {}
    unique: List[EditCandidateClip] = []
    for clip in rank_clips(clips):
        if not clip.duplicateGroup:
            unique.append(clip)
            continue
        current = best_by_group.get(clip.duplicateGroup)
        if current is None or clip.planning_score > current.planning_score:
            best_by_group[clip.duplicateGroup] = clip
    unique.extend(best_by_group.values())
    return rank_clips(unique)


def balance_clip_variety(clips: Sequence[EditCandidateClip], limit: int) -> List[EditCandidateClip]:
    chosen: List[EditCandidateClip] = []
    seen_labels = set()
    ranked = rank_clips(clips)
    for clip in ranked:
        if clip.label not in seen_labels:
            chosen.append(clip)
            seen_labels.add(clip.label)
        if len(chosen) >= limit:
            return chosen
    for clip in ranked:
        if clip not in chosen:
            chosen.append(clip)
        if len(chosen) >= limit:
            break
    return chosen


def choose_target_length(requested_seconds: int, preset: EditPreset) -> int:
    minimum = min(preset.durationOptions)
    maximum = max(preset.durationOptions)
    return max(minimum, min(maximum, requested_seconds))


def choose_theme(preset: EditPreset, requested_theme: Optional[str]) -> str:
    if requested_theme and requested_theme in THEME_REGISTRY:
        return requested_theme
    return preset.themeId


def select_best_clips(
    clips: Sequence[EditCandidateClip],
    target_seconds: float,
    preset: EditPreset,
) -> List[EditCandidateClip]:
    selected: List[EditCandidateClip] = []
    duration_so_far = 0.0
    _, max_clip_seconds = preset.clipLengthRangeSeconds

    for clip in remove_duplicate_moments(clips):
        if duration_so_far >= target_seconds:
            break
        if clip.duration < MIN_PLAN_CLIP_SECONDS:
            continue
        selected.append(clip)
        duration_so_far += min(max_clip_seconds, clip.duration)

    if preset.ordering.startswith("chronological"):
        selected.sort(key=lambda clip: clip.start)

    return selected


def fit_to_duration(clips: Sequence[EditCandidateClip], target_seconds: float, preset: EditPreset) -> List[EditCandidateClip]:
    return select_best_clips(clips, target_seconds, preset)


def _caption_for(label: str, preset: EditPreset) -> str:
    normalized = label.strip().lower()
    if preset.captionStyle == "plain":
        return label[:MAX_CAPTION_LENGTH]
    if "fast" in normalized:
        return "FAST BREAK"
    if "dunk" in normalized:
        return "BIG FINISH"
    if "shot" in normalized or "bucket" in normalized:
        return "BUCKET"
    if "defense" in normalized or "block" in normalized:
        return "LOCKDOWN"
    if "layup" in normalized:
        return "TOUGH TAKE"
    return label.upper()[:MAX_CAPTION_LENGTH]


def add_caption(label: str, preset: EditPreset) -> str:
    return _caption_for(label, preset)


def _effects_for(clip: EditCandidateClip, source_start: float, source_end: float, preset: EditPreset) -> List[EditPlanEffect]:
    effects: List[EditPlanEffect] = []
    event_center = min(max(clip.eventCenter, source_start), source_end)

    if "punch_zoom" in preset.effects:
        effects.append(EditPlanEffect(type="punch_zoom", at=event_center, strength=0.18))

    if preset.slowMotionIntensity in {"high", "medium", "low_medium"}:
        half_window = 0.6 if preset.slowMotionIntensity == "high" else 0.45
        slow_start = max(source_start, event_center - half_window)
        slow_end = min(source_end, event_center + half_window)
        if slow_end - slow_start >= 0.5:
            speed = 0.5 if preset.slowMotionIntensity == "high" else 0.65
            effects.append(
                EditPlanEffect(
                    type="slow_motion",
                    sourceStart=round(slow_start, 3),
                    sourceEnd=round(slow_end, 3),
                    speed=speed,
                )
            )

    return effects


def add_slow_motion(clip: EditCandidateClip, source_start: float, source_end: float, preset: EditPreset) -> List[EditPlanEffect]:
    return [effect for effect in _effects_for(clip, source_start, source_end, preset) if effect.type == "slow_motion"]


def build_edit_plan(request: CreateEditJobRequest, edit_job_id: str) -> EditPlan:
    context = build_edit_context(request)
    preset = PRESET_REGISTRY[request.preset]
    target_duration = choose_target_length(request.targetDurationSeconds, preset)
    aspect_ratio = request.aspectRatio or preset.defaultAspectRatio
    theme = choose_theme(preset, request.theme)
    intro_duration = 1.2 if preset.presetId != "coach_review" else 0.0
    outro_duration = 2.0 if request.planTier == "free" else 0.8
    usable_duration = max(MIN_PLAN_CLIP_SECONDS, target_duration - intro_duration - outro_duration)
    selected = fit_to_duration(context.clips, usable_duration, preset)

    timeline_start = intro_duration
    plan_clips: List[EditPlanClip] = []
    min_clip_seconds, max_clip_seconds = preset.clipLengthRangeSeconds

    for clip in selected:
        remaining = max(0.0, target_duration - outro_duration - timeline_start)
        if remaining < MIN_PLAN_CLIP_SECONDS:
            break
        source_duration = min(max_clip_seconds, clip.duration, remaining)
        if source_duration < min(min_clip_seconds, MIN_PLAN_CLIP_SECONDS):
            continue
        source_start = max(clip.start, clip.eventCenter - (source_duration / 2.0))
        source_end = source_start + source_duration
        if source_end > clip.end:
            source_end = clip.end
            source_start = max(clip.start, source_end - source_duration)
        timeline_end = timeline_start + (source_end - source_start)
        plan_clips.append(
            EditPlanClip(
                clipId=clip.id,
                sourceStart=round(source_start, 3),
                sourceEnd=round(source_end, 3),
                eventCenter=round(clip.eventCenter, 3),
                timelineStart=round(timeline_start, 3),
                timelineEnd=round(timeline_end, 3),
                label=clip.label,
                caption=_caption_for(clip.label, preset),
                cropMode="center_action" if aspect_ratio != "source" else "source",
                effects=_effects_for(clip, source_start, source_end, preset),
            )
        )
        timeline_start = timeline_end

    return EditPlan(
        editJobId=edit_job_id,
        videoId=request.videoId,
        analysisJobId=request.analysisJobId,
        preset=preset.presetId,
        theme=theme,
        targetDurationSeconds=target_duration,
        aspectRatio=aspect_ratio,
        audio=EditPlanAudio(
            mode="original_audio" if preset.musicTrackId == "none" else "music_plus_game_audio",
            musicTrackId=preset.musicTrackId,
            musicVolume=0.0 if preset.musicTrackId == "none" else 0.82,
            gameAudioVolume=preset.gameAudioVolume,
        ),
        clips=plan_clips,
        intro=TimedTemplate(
            enabled=intro_duration > 0.0,
            durationSeconds=intro_duration,
            templateId="quick_flash_title" if intro_duration > 0.0 else "none",
        ),
        outro=TimedTemplate(
            enabled=True,
            durationSeconds=outro_duration,
            templateId=preset.outroTemplateId,
        ),
        watermark=EditPlanWatermark(
            enabled=request.planTier == "free",
            position="bottom_right",
        ),
    )


def validate_edit_plan(
    plan: EditPlan,
    source_clips: Sequence[EditCandidateClip],
    plan_tier: PlanTier,
) -> List[EditPlanValidationIssue]:
    errors: List[EditPlanValidationIssue] = []
    source_by_id = {clip.id: clip for clip in source_clips}

    def add(field: str, code: str, message: str) -> None:
        errors.append(EditPlanValidationIssue(field=field, code=code, message=message))

    if plan.version != EDIT_PLAN_VERSION:
        add("version", "invalid_version", "EditPlan version is not supported.")
    if plan.renderMode != RENDER_MODE:
        add("renderMode", "invalid_render_mode", "Only cloud_ffmpeg render mode is supported.")
    if plan.theme not in THEME_REGISTRY:
        add("theme", "invalid_theme", "EditPlan theme is not registered.")
    if plan.audio.musicTrackId not in LICENSED_MUSIC_TRACKS:
        add("audio.musicTrackId", "unlicensed_music", "Music track is not licensed or available.")
    if not plan.clips:
        add("clips", "empty_clip_list", "EditPlan must include at least one clip.")

    seen_clip_ids = set()
    for index, clip in enumerate(plan.clips):
        field_prefix = f"clips[{index}]"
        if clip.clipId in seen_clip_ids:
            add(f"{field_prefix}.clipId", "duplicate_clip", "Duplicate clip IDs are not allowed.")
        seen_clip_ids.add(clip.clipId)

        source = source_by_id.get(clip.clipId)
        if source is None:
            add(f"{field_prefix}.clipId", "unknown_clip", "Clip ID was not in EditContext.")
            continue
        if clip.sourceStart < source.start or clip.sourceEnd > source.end:
            add(f"{field_prefix}.source", "source_bounds_invalid", "Clip source bounds exceed source clip bounds.")
        if clip.sourceEnd - clip.sourceStart < MIN_PLAN_CLIP_SECONDS:
            add(f"{field_prefix}.source", "clip_too_short", "Clip is shorter than the minimum render duration.")
        if len(clip.caption) > MAX_CAPTION_LENGTH:
            add(f"{field_prefix}.caption", "caption_too_long", "Caption is too long for the selected template.")
        for effect_index, effect in enumerate(clip.effects):
            if effect.type == "slow_motion":
                if effect.sourceStart is None or effect.sourceEnd is None:
                    add(f"{field_prefix}.effects[{effect_index}]", "slow_motion_missing_bounds", "Slow motion requires source bounds.")
                elif effect.sourceStart < clip.sourceStart or effect.sourceEnd > clip.sourceEnd or effect.sourceEnd <= effect.sourceStart:
                    add(f"{field_prefix}.effects[{effect_index}]", "slow_motion_out_of_bounds", "Slow motion range must stay inside clip source bounds.")

    planned_duration = plan.intro.durationSeconds + plan.outro.durationSeconds + sum(clip.timeline_duration for clip in plan.clips)
    if planned_duration > plan.targetDurationSeconds + MAX_DURATION_OVERRUN_SECONDS:
        add("targetDurationSeconds", "duration_too_long", "EditPlan duration exceeds target tolerance.")

    if plan_tier == "free":
        if not plan.watermark.enabled:
            add("watermark.enabled", "missing_free_watermark", "Free plans must include the Hoopclips watermark.")
        if not plan.outro.enabled:
            add("outro.enabled", "missing_free_outro", "Free plans must include the Hoopclips outro.")

    return errors


def add_outro_watermark(plan: EditPlan, plan_tier: PlanTier) -> EditPlan:
    return repair_edit_plan(plan, plan_tier)


def estimate_render_cost(plan: EditPlan) -> Dict[str, float]:
    planned_duration = plan.intro.durationSeconds + plan.outro.durationSeconds + sum(clip.timeline_duration for clip in plan.clips)
    effect_count = sum(len(clip.effects) for clip in plan.clips)
    complexity_units = round(planned_duration * (1.0 + (effect_count * 0.08)), 3)
    return {
        "plannedDurationSeconds": round(planned_duration, 3),
        "effectCount": float(effect_count),
        "complexityUnits": complexity_units,
    }


def repair_edit_plan(plan: EditPlan, plan_tier: PlanTier) -> EditPlan:
    data = plan.model_dump()
    if plan_tier == "free":
        data["watermark"]["enabled"] = True
        data["watermark"]["position"] = data["watermark"].get("position") or "bottom_right"
        data["outro"]["enabled"] = True
        if data["outro"]["durationSeconds"] <= 0:
            data["outro"]["durationSeconds"] = 2.0
        if not data["outro"]["templateId"] or data["outro"]["templateId"] == "none":
            data["outro"]["templateId"] = "free_hoopclips_outro"

    for clip in data["clips"]:
        clip["caption"] = (clip.get("caption") or "")[:MAX_CAPTION_LENGTH]
        deduped_effects = []
        for effect in clip.get("effects", []):
            if effect.get("type") == "slow_motion":
                source_start = max(clip["sourceStart"], effect.get("sourceStart") or clip["sourceStart"])
                source_end = min(clip["sourceEnd"], effect.get("sourceEnd") or clip["sourceEnd"])
                if source_end <= source_start:
                    continue
                effect["sourceStart"] = round(source_start, 3)
                effect["sourceEnd"] = round(source_end, 3)
            deduped_effects.append(effect)
        clip["effects"] = deduped_effects

    return EditPlan(**data)


def build_edit_job(request: CreateEditJobRequest, edit_job_id: str) -> StoredEditJob:
    plan = build_edit_plan(request, edit_job_id)
    plan = repair_edit_plan(plan, request.planTier)
    errors = validate_edit_plan(plan, request.clips, request.planTier)
    return StoredEditJob(
        edit_job_id=edit_job_id,
        install_id=request.installId,
        request=request,
        plan=plan,
        status="plan_ready" if not errors else "failed",
        created_at=now_utc(),
        updated_at=now_utc(),
        validation_errors=errors,
    )


def revise_edit_job(job: StoredEditJob, revision: ReviseEditJobRequest) -> StoredEditJob:
    request_data = job.request.model_dump()
    command = revision.command

    if revision.targetDurationSeconds is not None:
        request_data["targetDurationSeconds"] = revision.targetDurationSeconds
    elif command == "make_shorter":
        request_data["targetDurationSeconds"] = max(15, job.plan.targetDurationSeconds - 15)
    elif command == "make_longer":
        request_data["targetDurationSeconds"] = min(180, job.plan.targetDurationSeconds + 15)

    if revision.aspectRatio is not None:
        request_data["aspectRatio"] = revision.aspectRatio
    elif command == "export_vertical":
        request_data["aspectRatio"] = "9:16"
    elif command == "export_widescreen":
        request_data["aspectRatio"] = "16:9"

    if command in {"make_more_hype", "make_personal", "add_more_slow_motion"}:
        request_data["preset"] = "personal_highlight"
    elif command == "make_nba_style":
        request_data["preset"] = "full_game_highlight"
    elif command == "show_more_full_play_context":
        request_data["preset"] = "coach_review"

    revised_request = CreateEditJobRequest(**request_data)
    revised = build_edit_job(revised_request, job.edit_job_id)

    if command == "use_original_audio":
        data = revised.plan.model_dump()
        data["audio"] = {
            "mode": "original_audio",
            "musicTrackId": "none",
            "musicVolume": 0.0,
            "gameAudioVolume": 1.0,
        }
        revised.plan = repair_edit_plan(EditPlan(**data), revised.request.planTier)
        revised.validation_errors = validate_edit_plan(revised.plan, revised.request.clips, revised.request.planTier)
        revised.status = "plan_ready" if not revised.validation_errors else "failed"

    if command == "reduce_captions":
        data = revised.plan.model_dump()
        for index, clip in enumerate(data["clips"]):
            if index % 2 == 1:
                clip["caption"] = ""
        revised.plan = repair_edit_plan(EditPlan(**data), revised.request.planTier)
        revised.validation_errors = validate_edit_plan(revised.plan, revised.request.clips, revised.request.planTier)
        revised.status = "plan_ready" if not revised.validation_errors else "failed"

    return StoredEditJob(
        edit_job_id=job.edit_job_id,
        install_id=job.install_id,
        request=revised.request,
        plan=revised.plan,
        status=revised.status,
        created_at=job.created_at,
        updated_at=now_utc(),
        validation_errors=revised.validation_errors,
    )
