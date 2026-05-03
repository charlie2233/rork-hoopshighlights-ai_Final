from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

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
TemplateId = Literal["personal_highlight_v1", "full_game_highlight_v1", "coach_review_v1"]
RevisionCommand = Literal[
    "make_shorter",
    "make_longer",
    "make_more_hype",
    "make_nba_style",
    "make_personal",
    "remove_weak_clips",
    "add_more_slow_motion",
    "use_original_audio",
    "switch_format_vertical",
    "switch_format_widescreen",
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
REPO_ROOT = Path(__file__).resolve().parents[3]

LICENSED_MUSIC_TRACKS = {
    "hype_01",
    "hype_02",
    "cinematic_01",
    "clean_01",
    "none",
}
SUPPORTED_TEMPLATE_EFFECTS = {
    "caption",
    "clean_cut",
    "impact_flash",
    "lower_third",
    "punch_zoom",
    "slow_motion",
    "speed_ramp",
    "subtle_replay",
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
    templateId: TemplateId
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


class TemplateAsset(APIModel):
    assetId: str = Field(min_length=1, max_length=80)
    role: Literal["watermark", "outro", "lower_third", "title_card", "icon"]
    path: str = Field(min_length=1, max_length=256)
    contentType: str = Field(min_length=1, max_length=80)
    required: bool = True


class CaptionStyle(APIModel):
    styleId: str = Field(min_length=1, max_length=80)
    displayName: str
    density: Literal["minimal", "clean", "hype"]
    fontColor: str
    boxColor: str
    defaultFontSize: int = Field(gt=0, le=96)


class AudioProfile(APIModel):
    profileId: str = Field(min_length=1, max_length=80)
    mode: str
    musicTrackId: str
    musicVolume: float = Field(ge=0.0, le=1.0)
    gameAudioVolume: float = Field(ge=0.0, le=1.0)


class EffectProfile(APIModel):
    profileId: str = Field(min_length=1, max_length=80)
    slowMotionIntensity: str
    allowedEffects: List[str] = Field(default_factory=list, max_length=12)
    maxSlowMotionClips: int = Field(ge=0, le=12)


class OutroProfile(APIModel):
    profileId: str = Field(min_length=1, max_length=80)
    assetId: str = Field(min_length=1, max_length=80)
    durationSeconds: float = Field(ge=0.0, le=8.0)
    requiredForFree: bool


class WatermarkProfile(APIModel):
    profileId: str = Field(min_length=1, max_length=80)
    assetId: str = Field(min_length=1, max_length=80)
    position: str
    requiredForFree: bool
    displayText: str = Field(min_length=1, max_length=40)


class ClipLengthProfile(APIModel):
    minSeconds: float = Field(ge=MIN_PLAN_CLIP_SECONDS, le=20.0)
    targetSeconds: float = Field(ge=MIN_PLAN_CLIP_SECONDS, le=20.0)
    maxSeconds: float = Field(ge=MIN_PLAN_CLIP_SECONDS, le=20.0)

    @model_validator(mode="after")
    def validate_order(self) -> "ClipLengthProfile":
        if not self.minSeconds <= self.targetSeconds <= self.maxSeconds:
            raise ValueError("clip length target must be between min and max")
        return self


class TemplatePack(APIModel):
    templateId: TemplateId
    presetId: PresetId
    displayName: str
    description: str
    bestFor: str
    defaultAspectRatio: AspectRatio
    allowedAspectRatios: List[AspectRatio]
    targetDurations: List[int]
    ordering: str
    pacing: str
    clipLength: ClipLengthProfile
    themeId: str
    captionStyle: CaptionStyle
    audioProfile: AudioProfile
    effectProfile: EffectProfile
    outroProfile: OutroProfile
    watermarkProfile: WatermarkProfile
    assets: List[TemplateAsset] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_defaults(self) -> "TemplatePack":
        if self.defaultAspectRatio not in self.allowedAspectRatios:
            raise ValueError("defaultAspectRatio must be allowed by the template")
        if not self.targetDurations:
            raise ValueError("TemplatePack must expose at least one target duration")
        return self


TEMPLATE_PACK_REGISTRY: Dict[str, TemplatePack] = {
    "personal_highlight_v1": TemplatePack(
        templateId="personal_highlight_v1",
        presetId="personal_highlight",
        displayName="Personal Highlight",
        description="Fast vertical hype reel with bold captions, slow motion, and music-forward pacing.",
        bestFor="TikTok, Instagram, recruiting reels",
        defaultAspectRatio="9:16",
        allowedAspectRatios=["9:16", "16:9"],
        targetDurations=[15, 30, 45],
        ordering="best_first",
        pacing="fast",
        clipLength=ClipLengthProfile(minSeconds=3.5, targetSeconds=5.5, maxSeconds=7.0),
        themeId="hype_black_gold",
        captionStyle=CaptionStyle(styleId="bold_hype", displayName="Bold Hype", density="hype", fontColor="white", boxColor="black@0.62", defaultFontSize=48),
        audioProfile=AudioProfile(profileId="hype", mode="music_plus_game_audio", musicTrackId="hype_01", musicVolume=0.82, gameAudioVolume=0.25),
        effectProfile=EffectProfile(profileId="hype_effects", slowMotionIntensity="high", allowedEffects=["punch_zoom", "speed_ramp", "slow_motion"], maxSlowMotionClips=4),
        outroProfile=OutroProfile(profileId="free_social_outro", assetId="personal_highlight_outro_free_v1", durationSeconds=2.0, requiredForFree=True),
        watermarkProfile=WatermarkProfile(profileId="hoopclips_corner_mark", assetId="hoopclips_app_icon_v1", position="bottom_right", requiredForFree=True, displayText="Hoopclips"),
        assets=[
            TemplateAsset(assetId="hoopclips_app_icon_v1", role="watermark", path="services/editing/templates/personal_highlight/assets/watermark.json", contentType="application/json"),
            TemplateAsset(assetId="personal_highlight_outro_free_v1", role="outro", path="services/editing/templates/personal_highlight/assets/outro_free.json", contentType="application/json"),
        ],
    ),
    "full_game_highlight_v1": TemplatePack(
        templateId="full_game_highlight_v1",
        presetId="full_game_highlight",
        displayName="Full Game Highlight",
        description="Clean widescreen game recap with chronological flow, subtle effects, and stronger game audio.",
        bestFor="recaps, YouTube, team sharing",
        defaultAspectRatio="16:9",
        allowedAspectRatios=["16:9", "9:16"],
        targetDurations=[60, 90, 120],
        ordering="chronological_with_best_moments_boosted",
        pacing="medium",
        clipLength=ClipLengthProfile(minSeconds=5.5, targetSeconds=6.5, maxSeconds=8.0),
        themeId="nba_clean",
        captionStyle=CaptionStyle(styleId="clean_scorebug", displayName="Clean Scorebug", density="clean", fontColor="white", boxColor="black@0.48", defaultFontSize=38),
        audioProfile=AudioProfile(profileId="game_recap", mode="music_plus_game_audio", musicTrackId="cinematic_01", musicVolume=0.45, gameAudioVolume=0.62),
        effectProfile=EffectProfile(profileId="subtle_recap", slowMotionIntensity="low_medium", allowedEffects=["clean_cut", "subtle_replay", "lower_third", "slow_motion"], maxSlowMotionClips=3),
        outroProfile=OutroProfile(profileId="standard_recap_outro", assetId="full_game_outro_v1", durationSeconds=2.0, requiredForFree=True),
        watermarkProfile=WatermarkProfile(profileId="hoopclips_clean_corner_mark", assetId="hoopclips_app_icon_v1", position="bottom_right", requiredForFree=True, displayText="Hoopclips"),
        assets=[
            TemplateAsset(assetId="hoopclips_app_icon_v1", role="watermark", path="services/editing/templates/full_game_highlight/assets/watermark.json", contentType="application/json"),
            TemplateAsset(assetId="full_game_outro_v1", role="outro", path="services/editing/templates/full_game_highlight/assets/outro_standard.json", contentType="application/json"),
            TemplateAsset(assetId="full_game_lower_third_v1", role="lower_third", path="services/editing/templates/full_game_highlight/assets/lower_third.json", contentType="application/json"),
        ],
    ),
    "coach_review_v1": TemplatePack(
        templateId="coach_review_v1",
        presetId="coach_review",
        displayName="Coach Review",
        description="Simple chronological film-review cut with original audio, minimal captions, and restrained effects.",
        bestFor="coaches, trainers, parent review",
        defaultAspectRatio="source",
        allowedAspectRatios=["source", "16:9"],
        targetDurations=[60, 120, 180],
        ordering="chronological",
        pacing="slow",
        clipLength=ClipLengthProfile(minSeconds=6.0, targetSeconds=8.0, maxSeconds=10.0),
        themeId="coach_simple",
        captionStyle=CaptionStyle(styleId="plain", displayName="Plain Labels", density="minimal", fontColor="white", boxColor="black@0.35", defaultFontSize=34),
        audioProfile=AudioProfile(profileId="original_audio", mode="original_audio", musicTrackId="none", musicVolume=0.0, gameAudioVolume=1.0),
        effectProfile=EffectProfile(profileId="minimal_review", slowMotionIntensity="manual_only", allowedEffects=["slow_motion"], maxSlowMotionClips=1),
        outroProfile=OutroProfile(profileId="minimal_review_outro", assetId="coach_review_outro_v1", durationSeconds=1.5, requiredForFree=True),
        watermarkProfile=WatermarkProfile(profileId="hoopclips_minimal_corner_mark", assetId="hoopclips_app_icon_v1", position="bottom_right", requiredForFree=True, displayText="Hoopclips"),
        assets=[
            TemplateAsset(assetId="hoopclips_app_icon_v1", role="watermark", path="services/editing/templates/coach_review/assets/watermark.json", contentType="application/json"),
            TemplateAsset(assetId="coach_review_outro_v1", role="outro", path="services/editing/templates/coach_review/assets/outro_minimal.json", contentType="application/json"),
        ],
    ),
}


TEMPLATE_BY_PRESET: Dict[str, str] = {
    template.presetId: template.templateId for template in TEMPLATE_PACK_REGISTRY.values()
}


def get_template_pack(template_id: Optional[str]) -> TemplatePack:
    resolved_id = template_id or "personal_highlight_v1"
    template = TEMPLATE_PACK_REGISTRY.get(resolved_id)
    if template is None:
        return TEMPLATE_PACK_REGISTRY["personal_highlight_v1"]
    return template


def get_template_pack_for_plan(preset_id: str, template_id: Optional[str] = None) -> TemplatePack:
    if template_id and template_id in TEMPLATE_PACK_REGISTRY:
        return TEMPLATE_PACK_REGISTRY[template_id]
    return TEMPLATE_PACK_REGISTRY[TEMPLATE_BY_PRESET.get(preset_id, "personal_highlight_v1")]


PRESET_REGISTRY: Dict[str, EditPreset] = {
    "personal_highlight": EditPreset(
        presetId="personal_highlight",
        templateId="personal_highlight_v1",
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
        templateId="full_game_highlight_v1",
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
        templateId="coach_review_v1",
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
        templateId="personal_highlight_v1",
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
        templateId="personal_highlight_v1",
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
    sourceObjectKey: Optional[str] = Field(default=None, max_length=512)
    preset: PresetId = "personal_highlight"
    templateId: Optional[TemplateId] = None
    theme: Optional[str] = Field(default=None, max_length=80)
    targetDurationSeconds: int = Field(gt=0, le=180)
    aspectRatio: Optional[AspectRatio] = None
    planTier: PlanTier = "free"
    clips: List[EditCandidateClip] = Field(min_length=1, max_length=30)


class EditUserIntent(APIModel):
    preset: PresetId
    templateId: Optional[TemplateId] = None
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
    availableTemplates: List[str]
    availableThemes: List[str]
    availableMusicTracks: List[str]


class ReviseEditJobRequest(APIModel):
    installId: Optional[str] = Field(default=None, min_length=8, max_length=128)
    command: RevisionCommand
    freeText: Optional[str] = Field(default=None, max_length=240)
    targetDurationSeconds: Optional[int] = Field(default=None, gt=0, le=180)
    aspectRatio: Optional[AspectRatio] = None


class EditPlanPatchOperation(APIModel):
    op: Literal["add", "remove", "replace"]
    path: str = Field(min_length=1, max_length=160)
    value: Optional[Any] = None
    reason: Optional[str] = Field(default=None, max_length=160)


class EditPlanPatch(APIModel):
    version: Literal["edit-plan-patch-v1"] = "edit-plan-patch-v1"
    baseEditPlanId: str
    revisionIntent: RevisionCommand
    summary: str = Field(max_length=320)
    operations: List[EditPlanPatchOperation] = Field(default_factory=list, max_length=80)
    requiresRerender: bool = True


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
    assetId: Optional[str] = None


class EditPlanWatermark(APIModel):
    enabled: bool
    position: str
    assetId: Optional[str] = None


class EditPlan(APIModel):
    version: str = EDIT_PLAN_VERSION
    editJobId: str
    videoId: str
    analysisJobId: str
    preset: PresetId
    templateId: Optional[TemplateId] = None
    theme: str
    captionStyle: Optional[str] = None
    targetDurationSeconds: int
    aspectRatio: AspectRatio
    renderMode: str = RENDER_MODE
    audio: EditPlanAudio
    clips: List[EditPlanClip]
    intro: TimedTemplate
    outro: TimedTemplate
    watermark: EditPlanWatermark

    @model_validator(mode="after")
    def apply_template_defaults(self) -> "EditPlan":
        template = get_template_pack_for_plan(self.preset, self.templateId)
        self.templateId = template.templateId
        if not self.captionStyle:
            self.captionStyle = template.captionStyle.styleId
        if not self.outro.assetId:
            self.outro.assetId = template.outroProfile.assetId
        if not self.watermark.assetId:
            self.watermark.assetId = template.watermarkProfile.assetId
        return self


class EditPlanValidationIssue(APIModel):
    field: str
    code: str
    message: str


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "ios").exists() and (parent / "services").exists():
            return parent
    return Path.cwd()


def _template_asset_exists(asset: TemplateAsset) -> bool:
    if asset.path.startswith("builtin:"):
        return True
    return (_repo_root() / asset.path).exists()


class TemplatePackValidator:
    supported_aspect_ratios = {"9:16", "16:9", "source"}
    supported_caption_styles = {"bold_hype", "clean_scorebug", "plain"}
    supported_effects = {"punch_zoom", "speed_ramp", "impact_flash", "clean_cut", "subtle_replay", "lower_third", "slow_motion"}
    supported_watermark_positions = {"bottom_right", "bottom_left", "top_right", "top_left"}

    @classmethod
    def validate(cls, template: TemplatePack) -> List[EditPlanValidationIssue]:
        errors: List[EditPlanValidationIssue] = []

        def add(field: str, code: str, message: str) -> None:
            errors.append(EditPlanValidationIssue(field=field, code=code, message=message))

        if template.themeId not in THEME_REGISTRY:
            add("themeId", "invalid_template_theme", "Template references an unknown theme.")
        if template.captionStyle.styleId not in cls.supported_caption_styles:
            add("captionStyle", "invalid_caption_style", "Template references an unsupported caption style.")
        if template.audioProfile.musicTrackId not in LICENSED_MUSIC_TRACKS:
            add("audioProfile.musicTrackId", "unlicensed_music", "Template music track is not licensed.")
        if template.defaultAspectRatio not in cls.supported_aspect_ratios:
            add("defaultAspectRatio", "invalid_aspect_ratio", "Template default aspect ratio is unsupported.")
        for index, aspect_ratio in enumerate(template.allowedAspectRatios):
            if aspect_ratio not in cls.supported_aspect_ratios:
                add(f"allowedAspectRatios[{index}]", "invalid_aspect_ratio", "Template allowed aspect ratio is unsupported.")
        if any(duration <= 0 or duration > 180 for duration in template.targetDurations):
            add("targetDurations", "invalid_target_duration", "Template target durations must be between 1 and 180 seconds.")
        for effect in template.effectProfile.allowedEffects:
            if effect not in cls.supported_effects:
                add("effectProfile.allowedEffects", "unsupported_effect", "Template requested an unsupported effect.")
        if template.watermarkProfile.position not in cls.supported_watermark_positions:
            add("watermarkProfile.position", "invalid_watermark_position", "Template watermark position is unsupported.")
        if template.watermarkProfile.requiredForFree and not template.watermarkProfile.assetId:
            add("watermarkProfile.assetId", "missing_free_watermark", "Free templates must define a watermark asset.")
        if template.outroProfile.requiredForFree and (not template.outroProfile.assetId or template.outroProfile.durationSeconds <= 0):
            add("outroProfile.assetId", "missing_free_outro", "Free templates must define a non-empty outro asset.")

        known_asset_ids = {asset.assetId for asset in template.assets}
        for asset_id, field, code in [
            (template.watermarkProfile.assetId, "watermarkProfile.assetId", "missing_free_watermark_asset"),
            (template.outroProfile.assetId, "outroProfile.assetId", "missing_free_outro_asset"),
        ]:
            if asset_id not in known_asset_ids:
                add(field, code, "Template required asset is not registered.")
        for index, asset in enumerate(template.assets):
            if asset.required and not _template_asset_exists(asset):
                add(f"assets[{index}].path", "template_asset_missing", "Template asset file does not exist.")

        return errors


def validate_template_pack(template: TemplatePack) -> List[EditPlanValidationIssue]:
    return TemplatePackValidator.validate(template)


def validate_template_registry() -> Dict[str, List[EditPlanValidationIssue]]:
    return {template_id: validate_template_pack(template) for template_id, template in TEMPLATE_PACK_REGISTRY.items()}


class EditJobResponse(APIModel):
    editJobId: str
    videoId: str
    analysisJobId: str
    status: str
    preset: PresetId
    templateId: Optional[TemplateId] = None
    targetDurationSeconds: int
    aspectRatio: AspectRatio
    clipCount: int
    validationErrors: List[EditPlanValidationIssue]


class EditPlanResponse(APIModel):
    editJobId: str
    status: str
    plan: EditPlan
    validationErrors: List[EditPlanValidationIssue]


class EditRevisionValidationResult(APIModel):
    valid: bool
    errors: List[EditPlanValidationIssue] = Field(default_factory=list)


class EditRevisionResponse(APIModel):
    revisionId: str
    editJobId: str
    basePlanId: str
    newPlanId: str
    command: RevisionCommand
    status: Literal["revision_ready", "revision_failed"]
    patch: EditPlanPatch
    revisedPlan: EditPlan
    validationResult: EditRevisionValidationResult
    requiresRerender: bool = True


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
            templateId=self.plan.templateId,
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
            templateId=request.templateId,
            targetDurationSeconds=request.targetDurationSeconds,
            aspectRatio=request.aspectRatio,
            planTier=request.planTier,
        ),
        clipPoolSummary=EditClipPoolSummary(**summarize_clip_pool(request.clips)),
        clips=request.clips,
        availablePresets=list(PRESET_REGISTRY.keys()),
        availableTemplates=list(TEMPLATE_PACK_REGISTRY.keys()),
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


def choose_template_target_length(requested_seconds: int, template: TemplatePack) -> int:
    minimum = min(template.targetDurations)
    maximum = max(template.targetDurations)
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
    template = get_template_pack_for_plan(preset.presetId, request.templateId or preset.templateId)
    preset = preset.model_copy(
        update={
            "defaultAspectRatio": template.defaultAspectRatio,
            "durationOptions": template.targetDurations,
            "ordering": template.ordering,
            "pacing": template.pacing,
            "clipLengthRangeSeconds": (template.clipLength.minSeconds, template.clipLength.maxSeconds),
            "musicTrackId": template.audioProfile.musicTrackId,
            "gameAudioVolume": template.audioProfile.gameAudioVolume,
            "captionStyle": template.captionStyle.styleId,
            "slowMotionIntensity": template.effectProfile.slowMotionIntensity,
            "themeId": template.themeId,
            "effects": [effect for effect in template.effectProfile.allowedEffects if effect != "slow_motion"],
            "outroTemplateId": template.outroProfile.assetId,
        }
    )
    target_duration = choose_template_target_length(request.targetDurationSeconds, template)
    aspect_ratio = request.aspectRatio or template.defaultAspectRatio
    theme = choose_theme(preset, request.theme)
    intro_duration = 1.2 if preset.presetId != "coach_review" else 0.0
    outro_duration = template.outroProfile.durationSeconds if request.planTier == "free" else min(0.8, template.outroProfile.durationSeconds)
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
        templateId=template.templateId,
        theme=theme,
        captionStyle=template.captionStyle.styleId,
        targetDurationSeconds=target_duration,
        aspectRatio=aspect_ratio,
        audio=EditPlanAudio(
            mode=template.audioProfile.mode,
            musicTrackId=template.audioProfile.musicTrackId,
            musicVolume=template.audioProfile.musicVolume,
            gameAudioVolume=template.audioProfile.gameAudioVolume,
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
            templateId=template.outroProfile.assetId,
            assetId=template.outroProfile.assetId,
        ),
        watermark=EditPlanWatermark(
            enabled=request.planTier == "free",
            position=template.watermarkProfile.position,
            assetId=template.watermarkProfile.assetId,
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
    template = TEMPLATE_PACK_REGISTRY.get(plan.templateId or "")
    if template is None:
        add("templateId", "invalid_template", "EditPlan template is not registered.")
        template = get_template_pack_for_plan(plan.preset, None)
    else:
        template_errors = validate_template_pack(template)
        for error in template_errors:
            add(f"template.{error.field}", error.code, error.message)
        if template.presetId != plan.preset and plan.preset not in {"fast_break_mix", "best_five"}:
            add("templateId", "template_preset_mismatch", "EditPlan template does not match the selected preset.")
        if plan.aspectRatio not in template.allowedAspectRatios:
            add("aspectRatio", "template_aspect_ratio_unsupported", "EditPlan aspect ratio is not supported by the selected template.")
        if plan.captionStyle and plan.captionStyle != template.captionStyle.styleId:
            add("captionStyle", "template_caption_style_mismatch", "EditPlan caption style does not match the selected template.")
        if plan.watermark.assetId and plan.watermark.assetId != template.watermarkProfile.assetId:
            add("watermark.assetId", "template_watermark_asset_mismatch", "EditPlan watermark asset does not match the selected template.")
        if plan.outro.assetId and plan.outro.assetId != template.outroProfile.assetId:
            add("outro.assetId", "template_outro_asset_mismatch", "EditPlan outro asset does not match the selected template.")
        if plan_tier == "free" and template.watermarkProfile.requiredForFree and not plan.watermark.enabled:
            add("watermark.enabled", "missing_free_watermark", "Selected template requires the free-user watermark.")
        if plan_tier == "free" and template.watermarkProfile.requiredForFree and plan.watermark.assetId != template.watermarkProfile.assetId:
            add("watermark.assetId", "missing_free_watermark_asset", "Selected template requires its registered free-user watermark asset.")
        if plan_tier == "free" and template.outroProfile.requiredForFree and not plan.outro.enabled:
            add("outro.enabled", "missing_free_outro", "Selected template requires the free-user outro.")
        if plan_tier == "free" and template.outroProfile.requiredForFree and plan.outro.assetId != template.outroProfile.assetId:
            add("outro.assetId", "missing_free_outro_asset", "Selected template requires its registered free-user outro asset.")
    if plan.audio.musicTrackId not in LICENSED_MUSIC_TRACKS:
        add("audio.musicTrackId", "unlicensed_music", "Music track is not licensed or available.")
    if plan.audio.musicTrackId == "none" and plan.audio.musicVolume > 0:
        add("audio.musicVolume", "invalid_music_volume", "musicVolume must be zero when no music track is selected.")
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
            if effect.type not in template.effectProfile.allowedEffects:
                add(f"{field_prefix}.effects[{effect_index}].type", "template_effect_unsupported", "Effect is not allowed by the selected template.")
            if effect.type == "slow_motion":
                if effect.sourceStart is None or effect.sourceEnd is None:
                    add(f"{field_prefix}.effects[{effect_index}]", "slow_motion_missing_bounds", "Slow motion requires source bounds.")
                elif effect.sourceStart < clip.sourceStart or effect.sourceEnd > clip.sourceEnd or effect.sourceEnd <= effect.sourceStart:
                    add(f"{field_prefix}.effects[{effect_index}]", "slow_motion_out_of_bounds", "Slow motion range must stay inside clip source bounds.")
                if effect.speed is not None and not 0.5 <= effect.speed <= 1.0:
                    add(f"{field_prefix}.effects[{effect_index}].speed", "invalid_slow_motion_speed", "Slow motion speed must be between 0.5x and 1.0x.")

    planned_duration = plan.intro.durationSeconds + plan.outro.durationSeconds + sum(clip.timeline_duration for clip in plan.clips)
    if planned_duration > plan.targetDurationSeconds + MAX_DURATION_OVERRUN_SECONDS:
        add("targetDurationSeconds", "duration_too_long", "EditPlan duration exceeds target tolerance.")

    if plan_tier == "free":
        if not plan.watermark.enabled:
            add("watermark.enabled", "missing_free_watermark", "Free plans must include the Hoopclips watermark.")
        if plan.watermark.position not in {"bottom_right", "bottom_left", "top_right", "top_left"}:
            add("watermark.position", "invalid_watermark_position", "Watermark position is not supported.")
        if not plan.outro.enabled:
            add("outro.enabled", "missing_free_outro", "Free plans must include the Hoopclips outro.")
        if plan.outro.durationSeconds <= 0:
            add("outro.durationSeconds", "missing_free_outro", "Free plans must include a non-empty Hoopclips outro.")

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
    template = get_template_pack_for_plan(plan.preset, plan.templateId)
    data["templateId"] = template.templateId
    data["captionStyle"] = template.captionStyle.styleId
    if data.get("aspectRatio") not in template.allowedAspectRatios:
        data["aspectRatio"] = template.defaultAspectRatio
    if not data.get("theme") or data["theme"] not in THEME_REGISTRY:
        data["theme"] = template.themeId
    if plan_tier == "free":
        data["watermark"]["enabled"] = True
        data["watermark"]["position"] = data["watermark"].get("position") or template.watermarkProfile.position
        data["watermark"]["assetId"] = template.watermarkProfile.assetId
        data["outro"]["enabled"] = True
        if data["outro"]["durationSeconds"] <= 0:
            data["outro"]["durationSeconds"] = template.outroProfile.durationSeconds
        if not data["outro"]["templateId"] or data["outro"]["templateId"] == "none":
            data["outro"]["templateId"] = template.outroProfile.assetId
        data["outro"]["assetId"] = template.outroProfile.assetId

    for clip in data["clips"]:
        clip["caption"] = (clip.get("caption") or "")[:MAX_CAPTION_LENGTH]
        deduped_effects = []
        for effect in clip.get("effects", []):
            if effect.get("type") not in template.effectProfile.allowedEffects:
                continue
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


SAFE_PATCH_PATHS = {
    "/targetDurationSeconds",
    "/aspectRatio",
    "/preset",
    "/templateId",
    "/theme",
    "/captionStyle",
    "/audio",
    "/clips",
    "/intro",
    "/outro",
    "/watermark",
}


def _revision_summary(command: RevisionCommand) -> str:
    return {
        "make_shorter": "Shorten the edit while keeping the strongest moments.",
        "make_longer": "Add more context and usable moments while preserving the edit style.",
        "make_more_hype": "Increase recruiting-reel energy with faster pacing, bold captions, and hype effects.",
        "make_nba_style": "Switch to a cleaner recap style with widescreen framing and more game audio.",
        "make_personal": "Switch back to a personal vertical highlight style.",
        "add_more_slow_motion": "Add safe slow-motion moments around play centers.",
        "remove_weak_clips": "Remove lower-scoring moments while preserving the strongest clips.",
        "use_original_audio": "Use original game audio without music.",
        "switch_format_vertical": "Switch the edit to vertical 9:16 framing.",
        "switch_format_widescreen": "Switch the edit to widescreen 16:9 framing.",
        "export_vertical": "Switch the edit to vertical 9:16 framing.",
        "export_widescreen": "Switch the edit to widescreen 16:9 framing.",
        "reduce_captions": "Reduce caption density.",
        "show_more_full_play_context": "Use a more chronological coach-review style with longer context.",
    }.get(command, "Revise the edit plan.")


def _clip_score_lookup(source_clips: Sequence[EditCandidateClip]) -> Dict[str, float]:
    return {clip.id: clip.planning_score for clip in source_clips}


def _retime_clips(clips: List[Dict[str, Any]], intro_seconds: float) -> List[Dict[str, Any]]:
    timeline_start = intro_seconds
    retimed: List[Dict[str, Any]] = []
    for clip in clips:
        source_duration = max(0.0, float(clip["sourceEnd"]) - float(clip["sourceStart"]))
        clip["timelineStart"] = round(timeline_start, 3)
        timeline_end = timeline_start + source_duration
        clip["timelineEnd"] = round(timeline_end, 3)
        timeline_start = timeline_end
        retimed.append(clip)
    return retimed


def _add_slow_motion_effect(clip: Dict[str, Any]) -> None:
    effects = list(clip.get("effects") or [])
    if any(effect.get("type") == "slow_motion" for effect in effects):
        return
    source_start = float(clip["sourceStart"])
    source_end = float(clip["sourceEnd"])
    event_center = min(max(float(clip["eventCenter"]), source_start), source_end)
    slow_start = max(source_start, event_center - 0.55)
    slow_end = min(source_end, event_center + 0.55)
    if slow_end - slow_start < 0.5:
        return
    effects.append(
        {
            "type": "slow_motion",
            "sourceStart": round(slow_start, 3),
            "sourceEnd": round(slow_end, 3),
            "speed": 0.5,
        }
    )
    clip["effects"] = effects


def _build_revised_edit_job(job: StoredEditJob, revision: ReviseEditJobRequest) -> StoredEditJob:
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
    elif command in {"export_vertical", "switch_format_vertical"}:
        request_data["aspectRatio"] = "9:16"
    elif command in {"export_widescreen", "switch_format_widescreen"}:
        request_data["aspectRatio"] = "16:9"

    if command in {"make_more_hype", "make_personal", "add_more_slow_motion"}:
        request_data["preset"] = "personal_highlight"
        request_data["templateId"] = "personal_highlight_v1"
        request_data["aspectRatio"] = revision.aspectRatio or request_data.get("aspectRatio") or "9:16"
    elif command == "make_nba_style":
        request_data["preset"] = "full_game_highlight"
        request_data["templateId"] = "full_game_highlight_v1"
        request_data["aspectRatio"] = "16:9"
    elif command == "show_more_full_play_context":
        request_data["preset"] = "coach_review"
        request_data["templateId"] = "coach_review_v1"

    revised_request = CreateEditJobRequest(**request_data)
    revised = build_edit_job(revised_request, job.edit_job_id)
    data = revised.plan.model_dump()

    if command == "use_original_audio":
        data["audio"] = {
            "mode": "original_audio",
            "musicTrackId": "none",
            "musicVolume": 0.0,
            "gameAudioVolume": 1.0,
        }

    if command == "make_more_hype":
        data["theme"] = "hype_black_gold"
        data["templateId"] = "personal_highlight_v1"
        data["captionStyle"] = "bold_hype"
        data["aspectRatio"] = "9:16"
        data["audio"] = {
            "mode": "music_plus_game_audio",
            "musicTrackId": "hype_02",
            "musicVolume": 0.88,
            "gameAudioVolume": 0.2,
        }
        scores = _clip_score_lookup(revised.request.clips)
        data["clips"] = sorted(data["clips"], key=lambda clip: scores.get(clip["clipId"], 0.0), reverse=True)
        for clip in data["clips"][:2]:
            caption = (clip.get("caption") or clip.get("label") or "HIGHLIGHT").upper()
            clip["caption"] = (caption.rstrip("!") + "!")[:MAX_CAPTION_LENGTH]
            punch_effects = [effect for effect in clip.get("effects", []) if effect.get("type") == "punch_zoom"]
            if punch_effects:
                punch_effects[0]["strength"] = 0.22
            else:
                clip.setdefault("effects", []).append(
                    {
                        "type": "punch_zoom",
                        "at": round(float(clip["eventCenter"]), 3),
                        "strength": 0.22,
                    }
                )
            _add_slow_motion_effect(clip)
        data["clips"] = _retime_clips(data["clips"], data["intro"]["durationSeconds"])

    if command == "make_nba_style":
        data["theme"] = "nba_clean"
        data["templateId"] = "full_game_highlight_v1"
        data["captionStyle"] = "clean_scorebug"
        data["aspectRatio"] = "16:9"
        data["audio"] = {
            "mode": "music_plus_game_audio",
            "musicTrackId": "cinematic_01",
            "musicVolume": 0.45,
            "gameAudioVolume": 0.62,
        }
        data["clips"] = sorted(data["clips"], key=lambda clip: clip["sourceStart"])
        for index, clip in enumerate(data["clips"]):
            clip["cropMode"] = "center_action"
            if index % 2 == 1:
                clip["caption"] = ""
            clip["effects"] = [effect for effect in clip.get("effects", []) if effect.get("type") != "punch_zoom"]
        data["clips"] = _retime_clips(data["clips"], data["intro"]["durationSeconds"])

    if command == "add_more_slow_motion":
        for clip in data["clips"][:4]:
            _add_slow_motion_effect(clip)

    if command == "remove_weak_clips" and len(data["clips"]) > 1:
        scores = _clip_score_lookup(revised.request.clips)
        weakest_index = min(range(len(data["clips"])), key=lambda index: scores.get(data["clips"][index]["clipId"], 0.0))
        data["clips"].pop(weakest_index)
        data["clips"] = _retime_clips(data["clips"], data["intro"]["durationSeconds"])

    if command == "reduce_captions":
        for index, clip in enumerate(data["clips"]):
            if index % 2 == 1:
                clip["caption"] = ""

    if command in {"export_vertical", "switch_format_vertical"}:
        data["aspectRatio"] = "9:16"
        for clip in data["clips"]:
            clip["cropMode"] = "center_action"

    if command in {"export_widescreen", "switch_format_widescreen"}:
        data["aspectRatio"] = "16:9"
        for clip in data["clips"]:
            clip["cropMode"] = "center_action"

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


def _diff_edit_plans(base: EditPlan, revised: EditPlan, command: RevisionCommand) -> List[EditPlanPatchOperation]:
    operations: List[EditPlanPatchOperation] = []
    base_data = base.model_dump()
    revised_data = revised.model_dump()
    for path in [
        "/targetDurationSeconds",
        "/aspectRatio",
        "/preset",
        "/templateId",
        "/theme",
        "/captionStyle",
        "/audio",
        "/clips",
        "/intro",
        "/outro",
        "/watermark",
    ]:
        key = path.removeprefix("/")
        if base_data.get(key) != revised_data.get(key):
            operations.append(
                EditPlanPatchOperation(
                    op="replace",
                    path=path,
                    value=revised_data[key],
                    reason=_revision_summary(command),
                )
            )
    return operations


def build_edit_plan_patch(job: StoredEditJob, revision: ReviseEditJobRequest, revised_plan: EditPlan) -> EditPlanPatch:
    return EditPlanPatch(
        baseEditPlanId=job.edit_job_id,
        revisionIntent=revision.command,
        summary=_revision_summary(revision.command),
        operations=_diff_edit_plans(job.plan, revised_plan, revision.command),
        requiresRerender=True,
    )


def _apply_pointer_operation(data: Dict[str, Any], operation: EditPlanPatchOperation) -> None:
    if operation.path not in SAFE_PATCH_PATHS:
        raise ValueError(f"Unsupported EditPlanPatch path: {operation.path}")
    key = operation.path.removeprefix("/")
    if operation.op == "remove":
        data.pop(key, None)
        return
    if operation.op in {"add", "replace"}:
        data[key] = operation.value
        return
    raise ValueError(f"Unsupported EditPlanPatch operation: {operation.op}")


def apply_edit_plan_patch(plan: EditPlan, patch: EditPlanPatch) -> EditPlan:
    data = plan.model_dump()
    for operation in patch.operations:
        _apply_pointer_operation(data, operation)
    return EditPlan(**data)


def build_revision_response(
    job: StoredEditJob,
    revision: ReviseEditJobRequest,
    revision_id: str,
) -> Tuple[StoredEditJob, EditRevisionResponse]:
    revised = _build_revised_edit_job(job, revision)
    patch = build_edit_plan_patch(job, revision, revised.plan)
    patched_plan = repair_edit_plan(apply_edit_plan_patch(job.plan, patch), revised.request.planTier)
    errors = validate_edit_plan(patched_plan, revised.request.clips, revised.request.planTier)
    if estimate_render_cost(patched_plan)["complexityUnits"] > 240:
        errors.append(
            EditPlanValidationIssue(
                field="renderCost",
                code="render_cost_too_high",
                message="Revised EditPlan exceeds the configured render cost limit.",
            )
        )
    revised.plan = patched_plan
    revised.validation_errors = errors
    revised.status = "plan_ready" if not errors else "failed"
    response = EditRevisionResponse(
        revisionId=revision_id,
        editJobId=job.edit_job_id,
        basePlanId=job.edit_job_id,
        newPlanId=f"{job.edit_job_id}:{revision_id}",
        command=revision.command,
        status="revision_ready" if not errors else "revision_failed",
        patch=patch,
        revisedPlan=patched_plan,
        validationResult=EditRevisionValidationResult(valid=not errors, errors=errors),
        requiresRerender=True,
    )
    return revised, response


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
    return _build_revised_edit_job(job, revision)
