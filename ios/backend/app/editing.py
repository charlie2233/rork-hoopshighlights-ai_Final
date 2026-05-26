from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

from pydantic import Field, ValidationError, field_validator, model_validator

from .models import APIModel, ClipTeamAttribution, TeamSelection, now_utc


PresetId = Literal[
    "personal_highlight",
    "full_game_highlight",
    "coach_review",
    "fast_break_mix",
    "best_five",
]
AspectRatio = Literal["9:16", "16:9", "source"]
PlanTier = Literal["free", "pro", "internal", "dev"]
TemplateId = Literal[
    "personal_highlight_v1",
    "full_game_highlight_v1",
    "coach_review_v1",
    "recruiting_reel_pro_v1",
    "cinematic_mixtape_pro_v1",
    "nba_recap_pro_v1",
    "team_highlight_pro_v1",
]
StoryRole = Literal["opener", "peak", "filler", "closer"]
ShotTrackingFrameRole = Literal[
    "start",
    "preEvent",
    "release",
    "shotArcEarly",
    "eventCenter",
    "outcome",
    "shotArcLate",
    "rimApproach",
    "rim",
    "rimEntry",
    "belowRim",
    "postOutcome",
    "finish",
    "midAction",
    "defenseSetup",
    "challenge",
    "possessionChange",
    "recovery",
    "defenseOutcome",
]
UserPromptStyleIntent = Literal[
    "more_hype",
    "nba_recap",
    "defense_focus",
    "vertical_mixtape",
    "recruiting_reel",
    "coach_review",
    "clean_game_story",
    "shorter",
    "longer",
    "original_audio",
    "general_direction",
]
UserPromptFocusArea = Literal[
    "defense",
    "finishes",
    "shooting",
    "transition",
    "team_story",
    "player_showcase",
    "clarity",
    "game_flow",
    "energy",
]
UserPromptTone = Literal["hype", "broadcast_clean", "coach_clean", "cinematic", "formal", "balanced"]
UserPromptPacing = Literal["fast", "balanced", "cinematic", "chronological", "coach_review"]
UserPromptEffectIntensity = Literal["low", "medium", "high"]
UserPromptAudioPreference = Literal["music_forward", "game_audio", "balanced"]
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
MIN_GPT_HIGHLIGHT_SCORE = 0.55
MIN_GPT_WATCHABILITY_SCORE = 0.5
MIN_SHOT_CONTEXT_LEAD_IN_SECONDS = 0.9
MIN_SHOT_CONTEXT_FOLLOW_THROUGH_SECONDS = 0.6
TARGET_SHOT_CONTEXT_LEAD_IN_SECONDS = 1.6
TARGET_SHOT_CONTEXT_FOLLOW_THROUGH_SECONDS = 1.0
MIN_SHOT_LIKE_CLIP_SECONDS = 3.0
MIN_NON_SHOT_PLANNING_SCORE = 0.5
MIN_NON_SHOT_WATCHABILITY_SCORE = 0.42
MIN_GENERIC_HIGHLIGHT_PLANNING_SCORE = 0.62
MIN_GENERIC_HIGHLIGHT_WATCHABILITY_SCORE = 0.5
MIN_NATIVE_OUTCOME_CONFLICT_CONFIDENCE = 0.65
GPT_NON_SCORING_DEFENSIVE_OUTCOMES = {"steal", "forced_turnover", "defensive_stop"}
GPT_SHOT_RESULT_OUTCOMES = {"made", "missed", "blocked"}
SHOT_TRACKING_RELEASE_ROLES = {"preEvent", "release", "eventCenter"}
SHOT_TRACKING_BALL_FLIGHT_ROLES = {
    "release",
    "shotArcEarly",
    "eventCenter",
    "outcome",
    "shotArcLate",
    "rimApproach",
    "rim",
    "rimEntry",
    "belowRim",
    "postOutcome",
    "finish",
}
SHOT_TRACKING_RESULT_ROLES = {"outcome", "shotArcLate", "rimApproach", "rim", "rimEntry", "belowRim", "postOutcome", "finish"}
SHOT_TRACKING_RIM_ENTRY_APPROACH_ROLES = {"release", "shotArcEarly", "eventCenter", "shotArcLate", "rimApproach"}
SHOT_TRACKING_RIM_ENTRY_FRAME_ROLES = {"outcome", "shotArcLate", "rim", "rimEntry", "finish"}
SHOT_TRACKING_RIM_ENTRY_FOLLOW_THROUGH_ROLES = {"belowRim", "postOutcome", "finish"}
SHOT_TRACKING_RICH_RELEASE_ROLES = {"release"}
SHOT_TRACKING_RICH_ARC_ROLES = {"shotArcEarly", "shotArcLate"}
SHOT_TRACKING_RICH_RESULT_ROLES = {"outcome", "shotArcLate", "rimApproach", "rim", "rimEntry", "belowRim", "postOutcome"}
SHOT_TRACKING_RICH_RIM_ROLES = {"rimApproach", "rim", "rimEntry", "belowRim", "postOutcome"}
DEFENSIVE_TRACKING_EVENT_ROLES = {"challenge", "possessionChange", "recovery", "defenseOutcome"}
DEFENSIVE_TRACKING_RESULT_ROLES = {"possessionChange", "recovery", "defenseOutcome", "finish"}
TEMPLATE_MIN_CLIP_TOLERANCE = 0.85
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


class PlanTierPolicy(APIModel):
    planTier: PlanTier
    displayName: str
    maxRenderSeconds: int = Field(gt=0, le=600)
    maxDailyRenders: int = Field(gt=0, le=500)
    maxActiveRenders: int = Field(gt=0, le=20)
    maxRevisionsPerEdit: int = Field(ge=0, le=100)
    maxOutputResolution: Literal["720p", "1080p"]
    watermarkRequired: bool
    outroRequired: bool
    premiumTemplatesAllowed: bool
    maxSourceVideoSeconds: int = Field(gt=0, le=7200)
    renderRetentionDays: int = Field(gt=0, le=365)
    failedRenderRetentionDays: int = Field(gt=0, le=90)
    staleRenderTimeoutSeconds: int = Field(gt=0, le=7200)
    maxRenderRetries: int = Field(ge=0, le=5)


PLAN_TIER_POLICY_REGISTRY: Dict[str, PlanTierPolicy] = {
    "free": PlanTierPolicy(
        planTier="free",
        displayName="Free",
        maxRenderSeconds=45,
        maxDailyRenders=3,
        maxActiveRenders=1,
        maxRevisionsPerEdit=3,
        maxOutputResolution="720p",
        watermarkRequired=True,
        outroRequired=True,
        premiumTemplatesAllowed=False,
        maxSourceVideoSeconds=600,
        renderRetentionDays=14,
        failedRenderRetentionDays=7,
        staleRenderTimeoutSeconds=900,
        maxRenderRetries=1,
    ),
    "pro": PlanTierPolicy(
        planTier="pro",
        displayName="Pro",
        maxRenderSeconds=180,
        maxDailyRenders=25,
        maxActiveRenders=2,
        maxRevisionsPerEdit=10,
        maxOutputResolution="1080p",
        watermarkRequired=False,
        outroRequired=False,
        premiumTemplatesAllowed=True,
        maxSourceVideoSeconds=1800,
        renderRetentionDays=60,
        failedRenderRetentionDays=14,
        staleRenderTimeoutSeconds=1500,
        maxRenderRetries=2,
    ),
    "internal": PlanTierPolicy(
        planTier="internal",
        displayName="Internal",
        maxRenderSeconds=300,
        maxDailyRenders=100,
        maxActiveRenders=4,
        maxRevisionsPerEdit=25,
        maxOutputResolution="1080p",
        watermarkRequired=False,
        outroRequired=False,
        premiumTemplatesAllowed=True,
        maxSourceVideoSeconds=3600,
        renderRetentionDays=7,
        failedRenderRetentionDays=3,
        staleRenderTimeoutSeconds=1800,
        maxRenderRetries=3,
    ),
    "dev": PlanTierPolicy(
        planTier="dev",
        displayName="Development",
        maxRenderSeconds=300,
        maxDailyRenders=500,
        maxActiveRenders=8,
        maxRevisionsPerEdit=50,
        maxOutputResolution="1080p",
        watermarkRequired=False,
        outroRequired=False,
        premiumTemplatesAllowed=True,
        maxSourceVideoSeconds=7200,
        renderRetentionDays=3,
        failedRenderRetentionDays=3,
        staleRenderTimeoutSeconds=1800,
        maxRenderRetries=0,
    ),
}


class AIEditFeatureFlags(APIModel):
    aiEditEnabled: bool = True
    aiEditLiveRenderEnabled: bool = True
    aiEditRevisionEnabled: bool = True
    aiEditTemplatePackEnabled: bool = True
    aiEditMaxDailyRenders: Optional[int] = None
    aiEditFreeWatermarkRequired: bool = True
    aiEditProExportsEnabled: bool = False
    aiClipGptEditorEnabled: bool = False
    aiClipGptPlanEditEnabled: bool = False
    aiClipGptRevisionEnabled: bool = False
    gptHighlightRerankerEnabled: bool = False


def get_plan_tier_policy(plan_tier: str) -> PlanTierPolicy:
    return PLAN_TIER_POLICY_REGISTRY.get(plan_tier, PLAN_TIER_POLICY_REGISTRY["free"])


def policy_summary_for_client(plan_tier: str) -> Dict[str, object]:
    policy = get_plan_tier_policy(plan_tier)
    return {
        "planTier": policy.planTier,
        "displayName": policy.displayName,
        "maxRenderSeconds": policy.maxRenderSeconds,
        "maxDailyRenders": policy.maxDailyRenders,
        "maxActiveRenders": policy.maxActiveRenders,
        "maxRevisionsPerEdit": policy.maxRevisionsPerEdit,
        "maxOutputResolution": policy.maxOutputResolution,
        "watermarkRequired": policy.watermarkRequired,
        "outroRequired": policy.outroRequired,
        "premiumTemplatesAllowed": policy.premiumTemplatesAllowed,
        "maxSourceVideoSeconds": policy.maxSourceVideoSeconds,
        "renderRetentionDays": policy.renderRetentionDays,
        "failedRenderRetentionDays": policy.failedRenderRetentionDays,
        "staleRenderTimeoutSeconds": policy.staleRenderTimeoutSeconds,
        "maxRenderRetries": policy.maxRenderRetries,
    }


def default_ai_edit_feature_flags() -> AIEditFeatureFlags:
    return AIEditFeatureFlags()


class NativeShotSignals(APIModel):
    isShotLike: bool = False
    leadInSeconds: float = Field(default=0.0, ge=0.0)
    followThroughSeconds: float = Field(default=0.0, ge=0.0)
    setupContextScore: float = Field(default=0.0, ge=0.0, le=1.0)
    outcomeContextScore: float = Field(default=0.0, ge=0.0, le=1.0)
    eventCenterQuality: float = Field(default=0.0, ge=0.0, le=1.0)
    contextQualityScore: float = Field(default=0.0, ge=0.0, le=1.0)
    timingWindowOk: bool = False
    outcome: Literal["made", "missed", "blocked", "uncertain", "not_shot"] = "uncertain"
    outcomeConfidence: float = Field(default=0.0, ge=0.0, le=1.0)


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
    nativeShotSignals: Optional[NativeShotSignals] = None
    teamAttribution: Optional[ClipTeamAttribution] = None
    captionHint: Optional[str] = Field(default=None, max_length=MAX_CAPTION_LENGTH)
    gptHighlightScore: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    gptWatchabilityScore: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    gptReason: Optional[str] = Field(default=None, max_length=180)
    suggestedSlowMotion: Optional[bool] = None
    suggestedSlowMotionCenter: Optional[float] = Field(default=None, ge=0.0)
    suggestedCaptionMoment: Optional[float] = Field(default=None, ge=0.0)
    suggestedCropFocus: Optional[str] = Field(default=None, max_length=80)
    suggestedExtendBeforeSeconds: float = Field(default=0.0, ge=0.0, le=3.0)
    suggestedExtendAfterSeconds: float = Field(default=0.0, ge=0.0, le=3.0)
    gptStoryOrderIndex: Optional[int] = Field(default=None, ge=0)
    gptStoryRole: Optional[StoryRole] = None
    rerankSource: Optional[str] = Field(default=None, max_length=80)

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
        if self.gptHighlightScore is not None:
            base = self.combinedScore if self.combinedScore is not None else (
                (self.confidence * 0.25)
                + (self.excitement * 0.3)
                + (self.watchability * 0.2)
                + (self.motionScore * 0.15)
                + (self.audioPeak * 0.1)
            )
            watchability = self.gptWatchabilityScore if self.gptWatchabilityScore is not None else self.watchability
            return round((self.gptHighlightScore * 0.58) + (watchability * 0.22) + (base * 0.2), 4)
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
    premiumOnly: bool = False

    @model_validator(mode="after")
    def validate_defaults(self) -> "TemplatePack":
        if self.defaultAspectRatio not in self.allowedAspectRatios:
            raise ValueError("defaultAspectRatio must be allowed by the template")
        if not self.targetDurations:
            raise ValueError("TemplatePack must expose at least one target duration")
        return self


AgentCropFocus = Literal["center_action", "ball", "rim", "shooter", "team", "source"]


class AgentSelectionRules(APIModel):
    prefer: List[str] = Field(default_factory=list, max_length=20)
    prioritize: List[str] = Field(default_factory=list, max_length=12)


class AgentRejectionRules(APIModel):
    reject: List[str] = Field(default_factory=list, max_length=20)


class AgentOrderingRules(APIModel):
    strategy: str = Field(min_length=1, max_length=80)
    opener: str = Field(min_length=1, max_length=80)
    peak: str = Field(min_length=1, max_length=80)
    closer: str = Field(min_length=1, max_length=80)


class AgentCaptionRules(APIModel):
    density: Literal["minimal", "clean", "medium", "medium_high", "high"]
    tone: str = Field(min_length=1, max_length=80)
    examples: List[str] = Field(default_factory=list, max_length=12)
    maxCaptionLength: int = Field(default=MAX_CAPTION_LENGTH, gt=0, le=MAX_CAPTION_LENGTH)


class AgentEffectRules(APIModel):
    slowMotionIntensity: str = Field(min_length=1, max_length=40)
    punchZoom: bool = False
    speedRamp: bool = False
    lowerThird: bool = False
    maxSlowMoMoments: int = Field(ge=0, le=12)


class AgentAudioRules(APIModel):
    musicProfile: str = Field(min_length=1, max_length=80)
    gameAudioVolume: float = Field(ge=0.0, le=1.0)
    musicVolume: float = Field(ge=0.0, le=1.0)


class AgentTargetDurationRules(APIModel):
    defaultAspectRatio: AspectRatio
    targetDurations: List[int] = Field(min_length=1, max_length=8)
    minClipDuration: float = Field(ge=MIN_PLAN_CLIP_SECONDS, le=20.0)
    maxClipDuration: float = Field(ge=MIN_PLAN_CLIP_SECONDS, le=20.0)

    @model_validator(mode="after")
    def validate_clip_window(self) -> "AgentTargetDurationRules":
        if self.maxClipDuration < self.minClipDuration:
            raise ValueError("maxClipDuration must be >= minClipDuration")
        return self


class AgentCropRules(APIModel):
    defaultFocus: AgentCropFocus = "center_action"
    allowedFocus: List[AgentCropFocus] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_default_focus(self) -> "AgentCropRules":
        if self.defaultFocus not in self.allowedFocus:
            raise ValueError("defaultFocus must be present in allowedFocus")
        return self


class AgentStoryRules(APIModel):
    storyArc: str = Field(min_length=1, max_length=80)
    notes: List[str] = Field(default_factory=list, max_length=12)


class AgentTemplateCookbook(APIModel):
    templateId: TemplateId
    agentStyleIntent: str = Field(min_length=1, max_length=240)
    selectionRules: AgentSelectionRules
    rejectionRules: AgentRejectionRules
    orderingRules: AgentOrderingRules
    captionRules: AgentCaptionRules
    effectRules: AgentEffectRules
    audioRules: AgentAudioRules
    targetDurationRules: AgentTargetDurationRules
    cropRules: AgentCropRules
    storyRules: AgentStoryRules
    planTier: PlanTier
    enabledForFree: bool
    enabledForPro: bool
    enabledForInternal: bool


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
    "recruiting_reel_pro_v1": TemplatePack(
        templateId="recruiting_reel_pro_v1",
        presetId="personal_highlight",
        displayName="Recruiting Reel Pro",
        description="Player-focused recruiting story with clean hype captions, longer context, and Pro clean export rules.",
        bestFor="coaches, scouts, player profiles",
        defaultAspectRatio="9:16",
        allowedAspectRatios=["9:16", "16:9"],
        targetDurations=[45, 60, 90, 120],
        ordering="best_first",
        pacing="medium_fast",
        clipLength=ClipLengthProfile(minSeconds=4.5, targetSeconds=6.5, maxSeconds=8.5),
        themeId="recruiting_clean",
        captionStyle=CaptionStyle(styleId="recruiting_clean_hype", displayName="Recruiting Clean Hype", density="hype", fontColor="white", boxColor="black@0.52", defaultFontSize=44),
        audioProfile=AudioProfile(profileId="recruiting_clean", mode="music_plus_game_audio", musicTrackId="clean_01", musicVolume=0.58, gameAudioVolume=0.48),
        effectProfile=EffectProfile(profileId="recruiting_focus", slowMotionIntensity="medium", allowedEffects=["clean_cut", "slow_motion", "punch_zoom"], maxSlowMotionClips=5),
        outroProfile=OutroProfile(profileId="pro_clean_no_outro", assetId="recruiting_reel_pro_outro_v1", durationSeconds=0.0, requiredForFree=False),
        watermarkProfile=WatermarkProfile(profileId="pro_clean_no_watermark", assetId="hoopclips_pro_clean_mark_v1", position="bottom_right", requiredForFree=False, displayText="HoopClips Pro"),
        assets=[
            TemplateAsset(assetId="hoopclips_pro_clean_mark_v1", role="watermark", path="services/editing/templates/recruiting_reel_pro/assets/watermark.json", contentType="application/json"),
            TemplateAsset(assetId="recruiting_reel_pro_title_v1", role="title_card", path="services/editing/templates/recruiting_reel_pro/assets/title_card.json", contentType="application/json"),
            TemplateAsset(assetId="recruiting_reel_pro_outro_v1", role="outro", path="services/editing/templates/recruiting_reel_pro/assets/outro_clean.json", contentType="application/json"),
        ],
        premiumOnly=True,
    ),
    "cinematic_mixtape_pro_v1": TemplatePack(
        templateId="cinematic_mixtape_pro_v1",
        presetId="personal_highlight",
        displayName="Cinematic Mixtape Pro",
        description="Premium social mixtape with stronger cinematic pacing, bold moments, and clean Pro export rules.",
        bestFor="polished Instagram, TikTok, player mixtapes",
        defaultAspectRatio="9:16",
        allowedAspectRatios=["9:16", "16:9"],
        targetDurations=[30, 45, 60, 90],
        ordering="best_first",
        pacing="fast_cinematic",
        clipLength=ClipLengthProfile(minSeconds=3.5, targetSeconds=5.5, maxSeconds=7.5),
        themeId="cinematic_mixtape",
        captionStyle=CaptionStyle(styleId="cinematic_hype", displayName="Cinematic Hype", density="hype", fontColor="white", boxColor="black@0.58", defaultFontSize=50),
        audioProfile=AudioProfile(profileId="cinematic_mixtape", mode="music_plus_game_audio", musicTrackId="cinematic_01", musicVolume=0.82, gameAudioVolume=0.28),
        effectProfile=EffectProfile(profileId="cinematic_mixtape_effects", slowMotionIntensity="high", allowedEffects=["punch_zoom", "speed_ramp", "slow_motion"], maxSlowMotionClips=6),
        outroProfile=OutroProfile(profileId="pro_clean_no_outro", assetId="cinematic_mixtape_pro_outro_v1", durationSeconds=0.0, requiredForFree=False),
        watermarkProfile=WatermarkProfile(profileId="pro_clean_no_watermark", assetId="hoopclips_pro_clean_mark_v1", position="bottom_right", requiredForFree=False, displayText="HoopClips Pro"),
        assets=[
            TemplateAsset(assetId="hoopclips_pro_clean_mark_v1", role="watermark", path="services/editing/templates/cinematic_mixtape_pro/assets/watermark.json", contentType="application/json"),
            TemplateAsset(assetId="cinematic_mixtape_pro_title_v1", role="title_card", path="services/editing/templates/cinematic_mixtape_pro/assets/title_card.json", contentType="application/json"),
            TemplateAsset(assetId="cinematic_mixtape_pro_outro_v1", role="outro", path="services/editing/templates/cinematic_mixtape_pro/assets/outro_clean.json", contentType="application/json"),
        ],
        premiumOnly=True,
    ),
    "nba_recap_pro_v1": TemplatePack(
        templateId="nba_recap_pro_v1",
        presetId="full_game_highlight",
        displayName="NBA Recap Pro",
        description="Broadcast-inspired game recap with clean scorebug captions, game-flow order, and Pro clean export rules.",
        bestFor="team recaps, YouTube, broadcast-style game stories",
        defaultAspectRatio="16:9",
        allowedAspectRatios=["16:9", "9:16"],
        targetDurations=[90, 120, 180],
        ordering="chronological_with_best_moments_boosted",
        pacing="medium_broadcast",
        clipLength=ClipLengthProfile(minSeconds=5.5, targetSeconds=7.5, maxSeconds=9.5),
        themeId="broadcast_recap",
        captionStyle=CaptionStyle(styleId="broadcast_scorebug", displayName="Broadcast Scorebug", density="clean", fontColor="white", boxColor="black@0.45", defaultFontSize=38),
        audioProfile=AudioProfile(profileId="broadcast_recap", mode="music_plus_game_audio", musicTrackId="cinematic_01", musicVolume=0.36, gameAudioVolume=0.72),
        effectProfile=EffectProfile(profileId="broadcast_recap_effects", slowMotionIntensity="low_medium", allowedEffects=["clean_cut", "subtle_replay", "lower_third", "slow_motion"], maxSlowMotionClips=4),
        outroProfile=OutroProfile(profileId="pro_clean_no_outro", assetId="nba_recap_pro_outro_v1", durationSeconds=0.0, requiredForFree=False),
        watermarkProfile=WatermarkProfile(profileId="pro_clean_no_watermark", assetId="hoopclips_pro_clean_mark_v1", position="bottom_right", requiredForFree=False, displayText="HoopClips Pro"),
        assets=[
            TemplateAsset(assetId="hoopclips_pro_clean_mark_v1", role="watermark", path="services/editing/templates/nba_recap_pro/assets/watermark.json", contentType="application/json"),
            TemplateAsset(assetId="nba_recap_pro_title_v1", role="title_card", path="services/editing/templates/nba_recap_pro/assets/title_card.json", contentType="application/json"),
            TemplateAsset(assetId="nba_recap_pro_outro_v1", role="outro", path="services/editing/templates/nba_recap_pro/assets/outro_clean.json", contentType="application/json"),
            TemplateAsset(assetId="nba_recap_pro_lower_third_v1", role="lower_third", path="services/editing/templates/nba_recap_pro/assets/lower_third.json", contentType="application/json"),
        ],
        premiumOnly=True,
    ),
    "team_highlight_pro_v1": TemplatePack(
        templateId="team_highlight_pro_v1",
        presetId="full_game_highlight",
        displayName="Team Highlight Pro",
        description="Team-first highlight package with balanced game flow, clean captions, and longer Pro export rules.",
        bestFor="parents, teams, season moments",
        defaultAspectRatio="16:9",
        allowedAspectRatios=["16:9", "9:16"],
        targetDurations=[90, 120, 180],
        ordering="chronological_with_best_moments_boosted",
        pacing="medium_team",
        clipLength=ClipLengthProfile(minSeconds=5.0, targetSeconds=7.0, maxSeconds=9.0),
        themeId="team_package",
        captionStyle=CaptionStyle(styleId="team_clean", displayName="Team Clean", density="clean", fontColor="white", boxColor="black@0.42", defaultFontSize=38),
        audioProfile=AudioProfile(profileId="team_package", mode="music_plus_game_audio", musicTrackId="clean_01", musicVolume=0.42, gameAudioVolume=0.68),
        effectProfile=EffectProfile(profileId="team_package_effects", slowMotionIntensity="medium", allowedEffects=["clean_cut", "subtle_replay", "lower_third", "slow_motion"], maxSlowMotionClips=5),
        outroProfile=OutroProfile(profileId="pro_clean_no_outro", assetId="team_highlight_pro_outro_v1", durationSeconds=0.0, requiredForFree=False),
        watermarkProfile=WatermarkProfile(profileId="pro_clean_no_watermark", assetId="hoopclips_pro_clean_mark_v1", position="bottom_right", requiredForFree=False, displayText="HoopClips Pro"),
        assets=[
            TemplateAsset(assetId="hoopclips_pro_clean_mark_v1", role="watermark", path="services/editing/templates/team_highlight_pro/assets/watermark.json", contentType="application/json"),
            TemplateAsset(assetId="team_highlight_pro_title_v1", role="title_card", path="services/editing/templates/team_highlight_pro/assets/title_card.json", contentType="application/json"),
            TemplateAsset(assetId="team_highlight_pro_outro_v1", role="outro", path="services/editing/templates/team_highlight_pro/assets/outro_clean.json", contentType="application/json"),
            TemplateAsset(assetId="team_highlight_pro_lower_third_v1", role="lower_third", path="services/editing/templates/team_highlight_pro/assets/lower_third.json", contentType="application/json"),
        ],
        premiumOnly=True,
    ),
}


TEMPLATE_BY_PRESET: Dict[str, str] = {
    "personal_highlight": "personal_highlight_v1",
    "full_game_highlight": "full_game_highlight_v1",
    "coach_review": "coach_review_v1",
    "fast_break_mix": "personal_highlight_v1",
    "best_five": "personal_highlight_v1",
}

AGENT_COOKBOOK_DIR = REPO_ROOT / "services" / "editing" / "templates" / "agent_cookbook"


def _load_agent_template_cookbooks() -> Dict[str, AgentTemplateCookbook]:
    registry: Dict[str, AgentTemplateCookbook] = {}
    if not AGENT_COOKBOOK_DIR.exists():
        return registry
    for path in sorted(AGENT_COOKBOOK_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        cookbook = AgentTemplateCookbook(**payload)
        registry[cookbook.templateId] = cookbook
    return registry


AGENT_TEMPLATE_COOKBOOK_REGISTRY: Dict[str, AgentTemplateCookbook] = _load_agent_template_cookbooks()


def get_agent_template_cookbook(template_id: Optional[str]) -> AgentTemplateCookbook:
    template = get_template_pack(template_id)
    cookbook = AGENT_TEMPLATE_COOKBOOK_REGISTRY.get(template.templateId)
    if cookbook is not None:
        return cookbook
    return AgentTemplateCookbook(
        templateId=template.templateId,
        agentStyleIntent=template.description,
        selectionRules=AgentSelectionRules(prefer=[template.bestFor], prioritize=[template.ordering]),
        rejectionRules=AgentRejectionRules(reject=["unclear outcome", "dead ball", "duplicate moments"]),
        orderingRules=AgentOrderingRules(strategy=template.ordering, opener="highest_confidence_clip", peak="highest_highlight_score", closer="strong_clear_outcome"),
        captionRules=AgentCaptionRules(density="clean", tone=template.captionStyle.displayName, examples=[]),
        effectRules=AgentEffectRules(
            slowMotionIntensity=template.effectProfile.slowMotionIntensity,
            punchZoom="punch_zoom" in template.effectProfile.allowedEffects,
            speedRamp="speed_ramp" in template.effectProfile.allowedEffects,
            lowerThird="lower_third" in template.effectProfile.allowedEffects,
            maxSlowMoMoments=template.effectProfile.maxSlowMotionClips,
        ),
        audioRules=AgentAudioRules(
            musicProfile=template.audioProfile.profileId,
            gameAudioVolume=template.audioProfile.gameAudioVolume,
            musicVolume=template.audioProfile.musicVolume,
        ),
        targetDurationRules=AgentTargetDurationRules(
            defaultAspectRatio=template.defaultAspectRatio,
            targetDurations=template.targetDurations,
            minClipDuration=template.clipLength.minSeconds,
            maxClipDuration=template.clipLength.maxSeconds,
        ),
        cropRules=AgentCropRules(defaultFocus="center_action", allowedFocus=["center_action", "ball", "rim", "shooter", "team", "source"]),
        storyRules=AgentStoryRules(storyArc=template.ordering, notes=[template.description]),
        planTier="pro" if template.premiumOnly else "free",
        enabledForFree=not template.premiumOnly,
        enabledForPro=True,
        enabledForInternal=True,
    )


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
    "recruiting_clean": EditTheme(
        themeId="recruiting_clean",
        displayName="Recruiting Clean",
        captionStyle="recruiting_clean_hype",
        colorway="black_gold_clean",
    ),
    "cinematic_mixtape": EditTheme(
        themeId="cinematic_mixtape",
        displayName="Cinematic Mixtape",
        captionStyle="cinematic_hype",
        colorway="midnight_gold",
    ),
    "broadcast_recap": EditTheme(
        themeId="broadcast_recap",
        displayName="Broadcast Recap",
        captionStyle="broadcast_scorebug",
        colorway="navy_gold",
    ),
    "team_package": EditTheme(
        themeId="team_package",
        displayName="Team Package",
        captionStyle="team_clean",
        colorway="graphite_gold",
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
    revenueCatAppUserID: Optional[str] = Field(default=None, min_length=1, max_length=160)
    userPrompt: Optional[str] = Field(default=None, max_length=240)
    teamSelection: Optional[TeamSelection] = None
    clips: List[EditCandidateClip] = Field(min_length=1, max_length=30)
    gptRerankSummary: Optional["GPTHighlightRerankSummary"] = None

    @field_validator("userPrompt")
    @classmethod
    def sanitize_user_prompt(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = " ".join(value.strip().split())
        if not trimmed:
            return None
        lowered = trimmed.lower()
        forbidden_markers = (
            "http://",
            "https://",
            "x-amz-",
            "ffmpeg",
            "ffprobe",
            "avfoundation",
            "shell command",
            "bash ",
            "sh -c",
            "python -c",
            "python3 -c",
            "subprocess",
            "os.system",
            "sourceobjectkey",
            "downloadurl",
            "renderlogobjectkey",
            "uploads/",
            "renders/",
            "edits/",
        )
        if any(marker in lowered for marker in forbidden_markers):
            raise ValueError("userPrompt must not contain render commands, URLs, presigned URL markers, or storage keys.")
        return trimmed


class GPTHighlightSuggestedEdit(APIModel):
    slowMotion: bool = False
    slowMotionCenter: Optional[float] = Field(default=None, ge=0.0)
    captionMoment: Optional[float] = Field(default=None, ge=0.0)
    cropFocus: str = Field(default="center_action", max_length=80)
    extendBeforeSeconds: float = Field(default=0.0, ge=0.0, le=3.0)
    extendAfterSeconds: float = Field(default=0.0, ge=0.0, le=3.0)


class GPTHighlightQualitySignals(APIModel):
    setupVisible: bool
    releaseVisible: bool
    shotArcVisible: bool
    eventVisible: bool
    outcomeVisible: bool
    rimResultVisible: bool
    ballPathVisible: bool
    playerControlVisible: bool
    cleanCamera: bool
    fullPlayContext: bool
    reason: str = Field(min_length=1, max_length=160)


class GPTShotResultEvidence(APIModel):
    releaseToRimContinuity: Literal["continuous", "partial", "missing"]
    rimResultEvidence: Literal["made_visible", "clear_miss", "blocked", "unclear"]
    outcomeConfidence: float = Field(ge=0.0, le=1.0)
    rimEntrySequence: Literal["visible_entry", "visible_miss", "blocked", "unclear"] = "unclear"
    ballApproachFrameRole: Optional[ShotTrackingFrameRole] = None
    rimEntryFrameRole: Optional[ShotTrackingFrameRole] = None
    ballBelowRimOrNetFrameRole: Optional[ShotTrackingFrameRole] = None
    rimEntrySequenceConfidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=160)


class GPTShotTrackingEvidence(APIModel):
    ballVisibleFrameRoles: List[ShotTrackingFrameRole] = Field(default_factory=list, max_length=10)
    rimVisibleFrameRoles: List[ShotTrackingFrameRole] = Field(default_factory=list, max_length=10)
    releaseFrameRole: Optional[ShotTrackingFrameRole] = None
    resultFrameRole: Optional[ShotTrackingFrameRole] = None
    ballEntersRimFrameRole: Optional[ShotTrackingFrameRole] = None
    netOrRimReactionVisible: bool = False
    trajectoryContinuity: Literal["continuous", "partial", "missing"] = "missing"
    reason: str = Field(default="No frame-role shot tracking evidence supplied.", min_length=1, max_length=180)


class GPTHighlightClipDecision(APIModel):
    clipId: str = Field(min_length=1, max_length=80)
    keep: bool
    rejectReason: Optional[str] = Field(default=None, max_length=160)
    highlightScore: float = Field(ge=0.0, le=1.0)
    watchabilityScore: float = Field(ge=0.0, le=1.0)
    basketballEvent: str = Field(min_length=1, max_length=80)
    outcome: Literal["made", "missed", "blocked", "steal", "forced_turnover", "defensive_stop", "unclear", "not_basketball"]
    caption: str = Field(max_length=MAX_CAPTION_LENGTH)
    reason: str = Field(min_length=1, max_length=180)
    storyRole: StoryRole = "filler"
    qualitySignals: GPTHighlightQualitySignals
    shotResultEvidence: GPTShotResultEvidence = Field(
        default_factory=lambda: GPTShotResultEvidence(
            releaseToRimContinuity="missing",
            rimResultEvidence="unclear",
            outcomeConfidence=0.0,
            reason="No explicit shot result evidence supplied.",
        )
    )
    shotTrackingEvidence: GPTShotTrackingEvidence = Field(default_factory=GPTShotTrackingEvidence)
    suggestedEdit: GPTHighlightSuggestedEdit


class GPTPlanEditCaption(APIModel):
    clipId: str = Field(min_length=1, max_length=80)
    caption: str = Field(max_length=MAX_CAPTION_LENGTH)
    captionMoment: Optional[float] = Field(default=None, ge=0.0)


class GPTPlanEditSlowMotionMoment(APIModel):
    clipId: str = Field(min_length=1, max_length=80)
    center: float = Field(ge=0.0)
    speed: float = Field(default=0.55, ge=0.5, le=1.0)


class GPTPlanEdit(APIModel):
    orderedClipIds: List[str] = Field(default_factory=list, max_length=30)
    pacing: Literal["fast", "balanced", "cinematic", "chronological", "coach_review"] = "balanced"
    captions: List[GPTPlanEditCaption] = Field(default_factory=list, max_length=30)
    slowMotionMoments: List[GPTPlanEditSlowMotionMoment] = Field(default_factory=list, max_length=30)
    summary: Optional[str] = Field(default=None, max_length=240)


class GPTHighlightRerankSummary(APIModel):
    status: Literal["disabled", "applied", "fallback"]
    model: Optional[str] = Field(default=None, max_length=120)
    sampledClipCount: int = Field(default=0, ge=0)
    sampledFrameCount: int = Field(default=0, ge=0)
    returnedDecisionCount: int = Field(default=0, ge=0)
    keptClipIds: List[str] = Field(default_factory=list, max_length=30)
    rejectedClipIds: List[str] = Field(default_factory=list, max_length=30)
    rejectedReasonCounts: Dict[str, int] = Field(default_factory=dict)
    storyOrderClipIds: List[str] = Field(default_factory=list, max_length=30)
    planEditApplied: bool = False
    fallbackReason: Optional[str] = Field(default=None, max_length=120)


class EditUserPromptIntent(APIModel):
    source: Literal["user_prompt"] = "user_prompt"
    styleIntents: List[UserPromptStyleIntent] = Field(default_factory=list, max_length=8)
    focusAreas: List[UserPromptFocusArea] = Field(default_factory=list, max_length=8)
    tone: Optional[UserPromptTone] = None
    pacing: Optional[UserPromptPacing] = None
    requestedAspectRatio: Optional[AspectRatio] = None
    requestedDurationSeconds: Optional[int] = Field(default=None, gt=0, le=180)
    templateHint: Optional[TemplateId] = None
    effectIntensity: Optional[UserPromptEffectIntensity] = None
    audioPreference: Optional[UserPromptAudioPreference] = None
    structuredSummary: List[str] = Field(default_factory=list, max_length=12)


def derive_user_prompt_intent(user_prompt: Optional[str], plan_tier: PlanTier = "free") -> Optional[EditUserPromptIntent]:
    if not user_prompt:
        return None

    text = user_prompt.strip().lower()
    if not text:
        return None

    style_intents: List[UserPromptStyleIntent] = []
    focus_areas: List[UserPromptFocusArea] = []
    structured_summary: List[str] = []
    tone: Optional[UserPromptTone] = None
    pacing: Optional[UserPromptPacing] = None
    requested_aspect_ratio: Optional[AspectRatio] = None
    requested_duration_seconds: Optional[int] = None
    template_hint: Optional[TemplateId] = None
    effect_intensity: Optional[UserPromptEffectIntensity] = None
    audio_preference: Optional[UserPromptAudioPreference] = None

    def add_unique(items: List[Any], value: Any) -> None:
        if value not in items:
            items.append(value)

    def allow_template(template_id: TemplateId) -> Optional[TemplateId]:
        template = TEMPLATE_PACK_REGISTRY.get(template_id)
        if template is None:
            return None
        if template.premiumOnly and not get_plan_tier_policy(plan_tier).premiumTemplatesAllowed:
            return None
        return template_id

    duration_match = re.search(r"\b(15|30|45|60|90|120|180)\s*(?:s|sec|secs|second|seconds)\b", text)
    if duration_match:
        requested_duration_seconds = int(duration_match.group(1))
        structured_summary.append(f"target_duration_{requested_duration_seconds}s")

    if any(term in text for term in ("9:16", "vertical", "portrait", "tiktok", "reel", "shorts")):
        requested_aspect_ratio = "9:16"
        add_unique(style_intents, "vertical_mixtape")
        structured_summary.append("vertical_format")
    if any(term in text for term in ("16:9", "widescreen", "youtube", "landscape")):
        requested_aspect_ratio = "16:9"
        structured_summary.append("widescreen_format")

    if any(term in text for term in ("nba", "broadcast", "recap")):
        add_unique(style_intents, "nba_recap")
        add_unique(focus_areas, "game_flow")
        tone = tone or "broadcast_clean"
        pacing = pacing or "chronological"
        template_hint = template_hint or allow_template("nba_recap_pro_v1")
        structured_summary.append("nba_recap_style")
    if any(term in text for term in ("hype", "more energy", "energy", "intense", "viral")):
        add_unique(style_intents, "more_hype")
        add_unique(focus_areas, "energy")
        tone = "hype"
        pacing = pacing or "fast"
        effect_intensity = "high"
        structured_summary.append("increase_hype")
    if any(term in text for term in ("defense", "defence", "block", "steal", "stop", "lockdown", "contest")):
        add_unique(style_intents, "defense_focus")
        add_unique(focus_areas, "defense")
        tone = tone or "hype"
        structured_summary.append("defense_focus")
    if any(term in text for term in ("mixtape", "cinematic", "cold", "built different", "vibe")):
        add_unique(style_intents, "vertical_mixtape")
        add_unique(focus_areas, "energy")
        tone = "cinematic" if "cinematic" in text else (tone or "hype")
        pacing = pacing or "cinematic"
        effect_intensity = "high"
        template_hint = template_hint or allow_template("cinematic_mixtape_pro_v1")
        structured_summary.append("mixtape_style")
    if any(term in text for term in ("recruit", "showcase", "send to coach", "college coach")):
        add_unique(style_intents, "recruiting_reel")
        add_unique(focus_areas, "player_showcase")
        add_unique(focus_areas, "clarity")
        tone = "formal"
        pacing = pacing or "balanced"
        template_hint = template_hint or allow_template("recruiting_reel_pro_v1")
        structured_summary.append("recruiting_showcase")
    if any(term in text for term in ("coach review", "film review", "coach tape", "breakdown")):
        add_unique(style_intents, "coach_review")
        add_unique(focus_areas, "clarity")
        add_unique(focus_areas, "game_flow")
        tone = "coach_clean"
        pacing = "coach_review"
        effect_intensity = "low"
        template_hint = template_hint or "coach_review_v1"
        structured_summary.append("coach_review")
    if any(term in text for term in ("clean story", "game story", "story", "flow", "chronological")):
        add_unique(style_intents, "clean_game_story")
        add_unique(focus_areas, "game_flow")
        tone = tone or "balanced"
        pacing = "chronological"
        structured_summary.append("clean_game_story")
    if any(term in text for term in ("shorter", "trim", "tight")):
        add_unique(style_intents, "shorter")
        pacing = pacing or "fast"
        structured_summary.append("shorter_edit")
    if any(term in text for term in ("longer", "more context", "full play", "show the play")):
        add_unique(style_intents, "longer")
        add_unique(focus_areas, "game_flow")
        structured_summary.append("more_context")
    if any(term in text for term in ("original audio", "game audio", "court audio")):
        add_unique(style_intents, "original_audio")
        audio_preference = "game_audio"
        structured_summary.append("game_audio_priority")
    if any(term in text for term in ("music", "beat", "song")) and audio_preference is None:
        audio_preference = "music_forward"
        structured_summary.append("music_forward")
    if any(term in text for term in ("finish", "layup", "dunk", "rim")):
        add_unique(focus_areas, "finishes")
    if any(term in text for term in ("shoot", "shot", "jumper", "three", "3pt", "corner")):
        add_unique(focus_areas, "shooting")
    if any(term in text for term in ("fast break", "transition")):
        add_unique(focus_areas, "transition")
    if any(term in text for term in ("team", "everyone", "balanced players")):
        add_unique(focus_areas, "team_story")
        template_hint = template_hint or allow_template("team_highlight_pro_v1")

    if not style_intents and not focus_areas and not structured_summary:
        add_unique(style_intents, "general_direction")
        structured_summary.append("general_editor_direction")

    return EditUserPromptIntent(
        styleIntents=style_intents,
        focusAreas=focus_areas,
        tone=tone,
        pacing=pacing,
        requestedAspectRatio=requested_aspect_ratio,
        requestedDurationSeconds=requested_duration_seconds,
        templateHint=template_hint,
        effectIntensity=effect_intensity,
        audioPreference=audio_preference,
        structuredSummary=structured_summary,
    )


class EditUserIntent(APIModel):
    preset: PresetId
    templateId: Optional[TemplateId] = None
    targetDurationSeconds: int
    aspectRatio: Optional[AspectRatio]
    planTier: PlanTier
    userPromptIntent: Optional[EditUserPromptIntent] = None


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
    captionMoment: Optional[float] = Field(default=None, ge=0.0)
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
        if self.captionMoment is not None and not self.sourceStart <= self.captionMoment <= self.sourceEnd:
            raise ValueError("captionMoment must be inside source bounds")
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
    supported_caption_styles = {
        "bold_hype",
        "clean_scorebug",
        "plain",
        "recruiting_clean_hype",
        "cinematic_hype",
        "broadcast_scorebug",
        "team_clean",
    }
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


class AgentTemplateCookbookValidator:
    @classmethod
    def validate(cls, cookbook: AgentTemplateCookbook) -> List[EditPlanValidationIssue]:
        errors: List[EditPlanValidationIssue] = []

        def add(field: str, code: str, message: str) -> None:
            errors.append(EditPlanValidationIssue(field=field, code=code, message=message))

        template = TEMPLATE_PACK_REGISTRY.get(cookbook.templateId)
        if template is None:
            add("templateId", "missing_template_pack", "Cookbook references an unknown TemplatePack.")
            return errors

        if template.premiumOnly and cookbook.enabledForFree:
            add("enabledForFree", "premium_cookbook_unlocked_for_free", "Premium cookbook templates must be locked for Free.")
        if not template.premiumOnly and not cookbook.enabledForFree:
            add("enabledForFree", "free_template_locked", "Base cookbook templates must remain available for Free.")
        if template.premiumOnly and cookbook.planTier == "free":
            add("planTier", "premium_cookbook_free_tier", "Premium cookbook templates must not declare Free as their primary tier.")
        if not cookbook.enabledForPro or not cookbook.enabledForInternal:
            add("planTier", "cookbook_not_available_to_paid_or_internal", "Cookbook templates must be available to Pro and internal plans.")

        if cookbook.targetDurationRules.defaultAspectRatio not in template.allowedAspectRatios:
            add("targetDurationRules.defaultAspectRatio", "invalid_aspect_ratio", "Cookbook default aspect ratio must be allowed by the TemplatePack.")
        unsupported_durations = set(cookbook.targetDurationRules.targetDurations) - set(template.targetDurations)
        if unsupported_durations:
            add("targetDurationRules.targetDurations", "unsupported_target_duration", "Cookbook target durations must be supported by the TemplatePack.")
        if cookbook.targetDurationRules.minClipDuration < template.clipLength.minSeconds:
            add("targetDurationRules.minClipDuration", "clip_duration_too_short", "Cookbook minimum clip duration must respect TemplatePack bounds.")
        if cookbook.targetDurationRules.maxClipDuration > template.clipLength.maxSeconds:
            add("targetDurationRules.maxClipDuration", "clip_duration_too_long", "Cookbook maximum clip duration must respect TemplatePack bounds.")

        if template.captionStyle.styleId not in TemplatePackValidator.supported_caption_styles:
            add("captionRules", "unsupported_caption_style", "Cookbook must map to a renderer-supported caption style.")
        for index, example in enumerate(cookbook.captionRules.examples):
            if len(example) > cookbook.captionRules.maxCaptionLength:
                add(f"captionRules.examples[{index}]", "caption_too_long", "Cookbook caption examples must fit the backend caption limit.")

        if cookbook.effectRules.punchZoom and "punch_zoom" not in template.effectProfile.allowedEffects:
            add("effectRules.punchZoom", "unsupported_effect", "Cookbook requested punch zoom but TemplatePack does not allow it.")
        if cookbook.effectRules.speedRamp and "speed_ramp" not in template.effectProfile.allowedEffects:
            add("effectRules.speedRamp", "unsupported_effect", "Cookbook requested speed ramp but TemplatePack does not allow it.")
        if cookbook.effectRules.lowerThird and "lower_third" not in template.effectProfile.allowedEffects:
            add("effectRules.lowerThird", "unsupported_effect", "Cookbook requested lower-third treatment but TemplatePack does not allow it.")
        if cookbook.effectRules.maxSlowMoMoments > template.effectProfile.maxSlowMotionClips:
            add("effectRules.maxSlowMoMoments", "too_many_slow_mo_moments", "Cookbook slow-motion cap must not exceed TemplatePack render policy.")

        if cookbook.audioRules.musicProfile != template.audioProfile.profileId:
            add("audioRules.musicProfile", "audio_profile_mismatch", "Cookbook audio profile must match the TemplatePack audio profile.")
        if cookbook.audioRules.gameAudioVolume != template.audioProfile.gameAudioVolume:
            add("audioRules.gameAudioVolume", "audio_volume_mismatch", "Cookbook game audio volume must match TemplatePack defaults.")
        if cookbook.audioRules.musicVolume != template.audioProfile.musicVolume:
            add("audioRules.musicVolume", "audio_volume_mismatch", "Cookbook music volume must match TemplatePack defaults.")

        return errors


def validate_agent_template_cookbook(cookbook: AgentTemplateCookbook) -> List[EditPlanValidationIssue]:
    return AgentTemplateCookbookValidator.validate(cookbook)


def validate_agent_template_cookbook_registry() -> Dict[str, List[EditPlanValidationIssue]]:
    validation: Dict[str, List[EditPlanValidationIssue]] = {
        template_id: validate_agent_template_cookbook(cookbook)
        for template_id, cookbook in AGENT_TEMPLATE_COOKBOOK_REGISTRY.items()
    }
    for template_id in TEMPLATE_PACK_REGISTRY:
        if template_id not in AGENT_TEMPLATE_COOKBOOK_REGISTRY:
            validation[template_id] = [
                EditPlanValidationIssue(
                    field="templateId",
                    code="missing_agent_cookbook",
                    message="Every TemplatePack must have a matching AgentTemplateCookbook.",
                )
            ]
    for template_id in AGENT_TEMPLATE_COOKBOOK_REGISTRY:
        if template_id not in TEMPLATE_PACK_REGISTRY:
            validation.setdefault(template_id, []).append(
                EditPlanValidationIssue(
                    field="templateId",
                    code="orphan_agent_cookbook",
                    message="AgentTemplateCookbook must match a TemplatePack.",
                )
            )
    return validation


class EditJobResponse(APIModel):
    editJobId: str
    videoId: str
    analysisJobId: str
    status: str
    preset: PresetId
    templateId: Optional[TemplateId] = None
    planTier: PlanTier
    policy: Dict[str, object]
    targetDurationSeconds: int
    aspectRatio: AspectRatio
    clipCount: int
    validationErrors: List[EditPlanValidationIssue]


class EditPlanResponse(APIModel):
    editJobId: str
    status: str
    plan: EditPlan
    planTier: PlanTier
    policy: Dict[str, object]
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
            planTier=self.request.planTier,
            policy=policy_summary_for_client(self.request.planTier),
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
            planTier=self.request.planTier,
            policy=policy_summary_for_client(self.request.planTier),
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


def _team_key(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = " ".join(value.strip().lower().split())
    return normalized or None


def _team_selection_payload(team_selection: Optional[TeamSelection]) -> Dict[str, object]:
    if team_selection is None:
        return {
            "mode": "all",
            "teamId": None,
            "label": None,
            "colorLabel": None,
            "confidenceThreshold": 0.85,
            "includeUncertain": True,
        }
    return team_selection.model_dump(mode="json")


def team_attribution_status(
    clip: EditCandidateClip,
    team_selection: Optional[TeamSelection],
) -> Literal["all", "matched", "opponent", "uncertain"]:
    if team_selection is None or team_selection.mode == "all":
        return "all"
    attribution = clip.teamAttribution
    if attribution is None:
        return "uncertain"
    if attribution.confidence < team_selection.confidenceThreshold:
        return "uncertain"

    selected_team_id = _team_key(team_selection.teamId)
    selected_color = _team_key(team_selection.colorLabel)
    clip_team_id = _team_key(attribution.teamId)
    clip_color = _team_key(attribution.colorLabel)
    if selected_team_id and clip_team_id and selected_team_id == clip_team_id:
        return "matched"
    if selected_color and clip_color and selected_color == clip_color:
        return "matched"
    return "opponent"


def filter_clips_for_team_selection(
    clips: Sequence[EditCandidateClip],
    team_selection: Optional[TeamSelection],
) -> List[EditCandidateClip]:
    if team_selection is None or team_selection.mode == "all":
        return list(clips)
    filtered: List[EditCandidateClip] = []
    for clip in clips:
        status = team_attribution_status(clip, team_selection)
        if status == "matched" or (status == "uncertain" and team_selection.includeUncertain):
            filtered.append(clip)
    return filtered


def _clip_pool_summary_payload(clip_pool_summary: object) -> Dict[str, object]:
    if isinstance(clip_pool_summary, EditClipPoolSummary):
        return clip_pool_summary.model_dump(mode="json")
    if isinstance(clip_pool_summary, dict):
        return {
            "clipCount": int(clip_pool_summary.get("clipCount", 0)),
            "totalCandidateDuration": float(clip_pool_summary.get("totalCandidateDuration", 0.0)),
            "topLabels": list(clip_pool_summary.get("topLabels", []))[:5],
            "duplicateGroups": int(clip_pool_summary.get("duplicateGroups", 0)),
        }
    return {"clipCount": 0, "totalCandidateDuration": 0.0, "topLabels": [], "duplicateGroups": 0}


def _compact_agent_candidate_clip(
    clip: EditCandidateClip,
    team_selection: Optional[TeamSelection] = None,
) -> Dict[str, object]:
    return {
        "clipId": clip.id,
        "start": round(clip.start, 3),
        "end": round(clip.end, 3),
        "duration": round(clip.duration, 3),
        "eventCenter": round(clip.eventCenter, 3),
        "existingLabel": clip.label,
        "confidence": clip.confidence,
        "motionScore": clip.motionScore,
        "audioPeak": clip.audioPeak,
        "watchabilityScore": clip.watchability,
        "duplicateGroup": clip.duplicateGroup,
        "teamAttribution": clip.teamAttribution.model_dump(mode="json") if clip.teamAttribution is not None else None,
        "teamAttributionStatus": team_attribution_status(clip, team_selection),
        "nativeShotSignals": native_shot_signals_for_clip(clip).model_dump(mode="json"),
    }


def build_agent_editing_context(
    templateId: Optional[str],
    clipPoolSummary: object,
    candidateClips: Sequence[EditCandidateClip],
    teamSelection: Optional[TeamSelection] = None,
) -> Dict[str, object]:
    template = get_template_pack(templateId)
    cookbook = get_agent_template_cookbook(template.templateId)
    filtered_candidates = filter_clips_for_team_selection(candidateClips, teamSelection)
    return {
        "templateId": template.templateId,
        "agentStyleIntent": cookbook.agentStyleIntent,
        "planTier": cookbook.planTier,
        "enabledForFree": cookbook.enabledForFree,
        "enabledForPro": cookbook.enabledForPro,
        "enabledForInternal": cookbook.enabledForInternal,
        "templateCookbookRules": {
            "selectionRules": cookbook.selectionRules.model_dump(mode="json"),
            "rejectionRules": cookbook.rejectionRules.model_dump(mode="json"),
            "orderingRules": cookbook.orderingRules.model_dump(mode="json"),
            "captionRules": cookbook.captionRules.model_dump(mode="json"),
            "effectRules": cookbook.effectRules.model_dump(mode="json"),
            "audioRules": cookbook.audioRules.model_dump(mode="json"),
            "targetDurationRules": cookbook.targetDurationRules.model_dump(mode="json"),
            "cropRules": cookbook.cropRules.model_dump(mode="json"),
            "storyRules": cookbook.storyRules.model_dump(mode="json"),
        },
        "rendererTemplateDefaults": {
            "displayName": template.displayName,
            "defaultAspectRatio": template.defaultAspectRatio,
            "allowedAspectRatios": template.allowedAspectRatios,
            "targetDurations": template.targetDurations,
            "captionStyle": template.captionStyle.styleId,
            "captionDensity": template.captionStyle.density,
            "allowedEffects": template.effectProfile.allowedEffects,
            "maxSlowMotionClips": template.effectProfile.maxSlowMotionClips,
            "slowMotionIntensity": template.effectProfile.slowMotionIntensity,
            "audioProfile": template.audioProfile.profileId,
            "clipLength": {
                "minSeconds": template.clipLength.minSeconds,
                "targetSeconds": template.clipLength.targetSeconds,
                "maxSeconds": template.clipLength.maxSeconds,
            },
            "premiumOnly": template.premiumOnly,
        },
        "teamTargeting": _team_selection_payload(teamSelection),
        "clipPoolSummary": _clip_pool_summary_payload(clipPoolSummary),
        "candidateClips": [_compact_agent_candidate_clip(clip, teamSelection) for clip in rank_clips(filtered_candidates)[:30]],
    }


def build_edit_context(request: CreateEditJobRequest) -> EditContext:
    team_filtered_clips = filter_clips_for_team_selection(request.clips, request.teamSelection)
    return EditContext(
        videoId=request.videoId,
        analysisJobId=request.analysisJobId,
        userIntent=EditUserIntent(
            preset=request.preset,
            templateId=request.templateId,
            targetDurationSeconds=request.targetDurationSeconds,
            aspectRatio=request.aspectRatio,
            planTier=request.planTier,
            userPromptIntent=derive_user_prompt_intent(request.userPrompt, request.planTier),
        ),
        clipPoolSummary=EditClipPoolSummary(**summarize_clip_pool(team_filtered_clips)),
        clips=team_filtered_clips,
        availablePresets=list(PRESET_REGISTRY.keys()),
        availableTemplates=list(TEMPLATE_PACK_REGISTRY.keys()),
        availableThemes=list(THEME_REGISTRY.keys()),
        availableMusicTracks=sorted(LICENSED_MUSIC_TRACKS),
    )


def rank_clips(clips: Sequence[EditCandidateClip]) -> List[EditCandidateClip]:
    return sorted(
        clips,
        key=lambda clip: (
            1 if is_plan_quality_eligible_clip(clip) else 0,
            clip_context_quality_score(clip),
            clip.planning_score,
            clip.watchability,
            clip.excitement,
            -clip.start,
        ),
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
        if current is None or _duplicate_choice_key(clip) > _duplicate_choice_key(current):
            best_by_group[clip.duplicateGroup] = clip
    unique.extend(best_by_group.values())
    return rank_clips(unique)


def order_by_gpt_story_order(clips: Sequence[EditCandidateClip]) -> List[EditCandidateClip]:
    ordered = [clip for clip in clips if clip.gptStoryOrderIndex is not None]
    if not ordered:
        role_order = {"opener": 0, "peak": 1, "filler": 2, "closer": 3}
        role_tagged = [clip for clip in clips if clip.gptStoryRole is not None]
        if role_tagged:
            return sorted(
                clips,
                key=lambda clip: (role_order.get(clip.gptStoryRole or "filler", 2), -clip.planning_score, clip.start),
            )
        return list(clips)
    unordered = [clip for clip in clips if clip.gptStoryOrderIndex is None]
    ordered.sort(key=lambda clip: (clip.gptStoryOrderIndex or 0, -clip.planning_score, clip.start))
    return ordered + unordered


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
    ranked_candidates = [clip for clip in remove_duplicate_moments(clips) if is_plan_quality_eligible_clip(clip)]
    selection_order = ranked_candidates
    if not preset.ordering.startswith("chronological"):
        story_ordered = [clip for clip in order_by_gpt_story_order(ranked_candidates) if clip.gptStoryOrderIndex is not None]
        if story_ordered:
            anchored: List[EditCandidateClip] = [story_ordered[0]]
            if len(story_ordered) > 1:
                anchored.append(story_ordered[-1])
            anchored_ids = {clip.id for clip in anchored}
            selection_order = (
                anchored
                + [clip for clip in story_ordered[1:-1] if clip.id not in anchored_ids]
                + [clip for clip in ranked_candidates if clip.gptStoryOrderIndex is None and clip.id not in anchored_ids]
            )

    for clip in selection_order:
        if duration_so_far >= target_seconds:
            break
        selected.append(clip)
        duration_so_far += min(max_clip_seconds, clip.duration)

    if preset.ordering.startswith("chronological"):
        selected.sort(key=lambda clip: clip.start)
    else:
        selected = order_by_gpt_story_order(selected)

    return selected


def fit_to_duration(clips: Sequence[EditCandidateClip], target_seconds: float, preset: EditPreset) -> List[EditCandidateClip]:
    return select_best_clips(clips, target_seconds, preset)


def is_shot_like_clip(clip: EditCandidateClip) -> bool:
    normalized = clip.label.strip().lower()
    return any(
        token in normalized
        for token in ("shot", "bucket", "basket", "layup", "dunk", "finish", "jumper", "three", "3pt")
    )


def native_shot_signals_for_clip(clip: EditCandidateClip) -> NativeShotSignals:
    is_shot_like = is_shot_like_clip(clip)
    lead_in = round(max(0.0, clip.eventCenter - clip.start), 3)
    follow_through = round(max(0.0, clip.end - clip.eventCenter), 3)
    setup_context_score = min(1.0, lead_in / TARGET_SHOT_CONTEXT_LEAD_IN_SECONDS) if is_shot_like else 0.0
    outcome_context_score = min(1.0, follow_through / TARGET_SHOT_CONTEXT_FOLLOW_THROUGH_SECONDS) if is_shot_like else 0.0
    if is_shot_like:
        duration_score = min(1.0, clip.duration / max(4.5, TARGET_SHOT_CONTEXT_LEAD_IN_SECONDS + TARGET_SHOT_CONTEXT_FOLLOW_THROUGH_SECONDS))
        if lead_in <= 0.0 or follow_through <= 0.0:
            balance_score = 0.0
        else:
            balance_score = min(lead_in, follow_through) / max(lead_in, follow_through)
        event_center_quality = (
            (setup_context_score * 0.34)
            + (outcome_context_score * 0.28)
            + (duration_score * 0.2)
            + (balance_score * 0.18)
        )
        timing_window_ok = clip.duration >= MIN_SHOT_LIKE_CLIP_SECONDS and has_minimum_shot_context(clip)
    else:
        event_center_quality = 0.0
        timing_window_ok = clip.duration >= MIN_PLAN_CLIP_SECONDS

    outcome, outcome_confidence = _native_outcome_hint_for_clip(clip, is_shot_like)
    incoming = clip.nativeShotSignals
    if incoming is not None and incoming.outcome in {"uncertain", "not_shot"}:
        outcome = incoming.outcome
        outcome_confidence = min(incoming.outcomeConfidence, clip.confidence)
    elif incoming is not None and incoming.outcome not in {"uncertain", "not_shot"}:
        outcome = incoming.outcome
        outcome_confidence = min(1.0, max(outcome_confidence, min(incoming.outcomeConfidence, clip.confidence)))

    return NativeShotSignals(
        isShotLike=is_shot_like,
        leadInSeconds=lead_in,
        followThroughSeconds=follow_through,
        setupContextScore=round(setup_context_score, 4),
        outcomeContextScore=round(outcome_context_score, 4),
        eventCenterQuality=round(max(0.0, min(1.0, event_center_quality)), 4),
        contextQualityScore=clip_context_quality_score(clip),
        timingWindowOk=timing_window_ok,
        outcome=outcome,
        outcomeConfidence=round(outcome_confidence, 4),
    )


def _native_outcome_hint_for_clip(clip: EditCandidateClip, is_shot_like: bool) -> tuple[str, float]:
    if not is_shot_like:
        return "not_shot", 1.0

    normalized = clip.label.strip().lower()
    if "block" in normalized:
        return "blocked", min(1.0, clip.confidence)
    if "miss" in normalized:
        return "missed", min(1.0, clip.confidence * 0.85)
    if any(token in normalized for token in ("made", "bucket", "basket", "dunk")):
        return "made", min(1.0, clip.confidence * 0.9)
    if any(token in normalized for token in ("attempt", "layup", "finish")):
        return "uncertain", 0.0
    return "uncertain", 0.0


def has_minimum_shot_context(clip: EditCandidateClip) -> bool:
    lead_in = max(0.0, clip.eventCenter - clip.start)
    follow_through = max(0.0, clip.end - clip.eventCenter)
    return lead_in >= MIN_SHOT_CONTEXT_LEAD_IN_SECONDS and follow_through >= MIN_SHOT_CONTEXT_FOLLOW_THROUGH_SECONDS


def clip_context_quality_score(clip: EditCandidateClip) -> float:
    if clip.duration < MIN_PLAN_CLIP_SECONDS:
        return 0.0
    if not is_shot_like_clip(clip):
        return non_shot_clip_quality_score(clip)

    lead_in = max(0.0, clip.eventCenter - clip.start)
    follow_through = max(0.0, clip.end - clip.eventCenter)
    if clip.duration < MIN_SHOT_LIKE_CLIP_SECONDS:
        duration_score = max(0.0, clip.duration / MIN_SHOT_LIKE_CLIP_SECONDS) * 0.55
    else:
        duration_score = min(1.0, clip.duration / 4.5)
    lead_score = min(1.0, lead_in / TARGET_SHOT_CONTEXT_LEAD_IN_SECONDS)
    follow_score = min(1.0, follow_through / TARGET_SHOT_CONTEXT_FOLLOW_THROUGH_SECONDS)
    if lead_in <= 0.0 or follow_through <= 0.0:
        balance_score = 0.0
    else:
        balance_score = min(lead_in, follow_through) / max(lead_in, follow_through)

    score = (lead_score * 0.38) + (follow_score * 0.28) + (duration_score * 0.22) + (balance_score * 0.12)
    return round(max(0.0, min(1.0, score)), 4)


def non_shot_clip_quality_score(clip: EditCandidateClip) -> float:
    if clip.duration < MIN_PLAN_CLIP_SECONDS:
        return 0.0
    duration_score = min(1.0, clip.duration / 4.5)
    watchability_score = max(clip.watchability, clip.motionScore)
    activity_score = max(clip.excitement, clip.audioPeak)
    score = (
        (clip.planning_score * 0.42)
        + (watchability_score * 0.3)
        + (activity_score * 0.13)
        + (duration_score * 0.15)
    )
    if is_generic_filler_clip(clip):
        score *= 0.82
    return round(max(0.0, min(1.0, score)), 4)


def is_generic_filler_clip(clip: EditCandidateClip) -> bool:
    normalized = clip.label.strip().lower()
    return normalized in {"highlight", "clip", "play", "moment"} or normalized.endswith(" highlight")


def has_minimum_non_shot_quality(clip: EditCandidateClip) -> bool:
    if is_generic_filler_clip(clip):
        planning_threshold = MIN_GENERIC_HIGHLIGHT_PLANNING_SCORE
        watchability_threshold = MIN_GENERIC_HIGHLIGHT_WATCHABILITY_SCORE
    else:
        planning_threshold = MIN_NON_SHOT_PLANNING_SCORE
        watchability_threshold = MIN_NON_SHOT_WATCHABILITY_SCORE
    return (
        clip.planning_score >= planning_threshold
        and max(clip.watchability, clip.motionScore) >= watchability_threshold
    )


def is_plan_quality_eligible_clip(clip: EditCandidateClip) -> bool:
    if clip.duration < MIN_PLAN_CLIP_SECONDS:
        return False
    if not is_shot_like_clip(clip):
        return has_minimum_non_shot_quality(clip)
    if native_shot_signals_for_clip(clip).outcome == "not_shot":
        return False
    if clip.duration < MIN_SHOT_LIKE_CLIP_SECONDS:
        return False
    if not has_minimum_shot_context(clip):
        return False
    return True


def _duplicate_choice_key(clip: EditCandidateClip) -> Tuple[int, float, float, float, float, float]:
    return (
        1 if is_plan_quality_eligible_clip(clip) else 0,
        clip_context_quality_score(clip),
        clip.planning_score,
        clip.watchability,
        clip.excitement,
        -clip.start,
    )


def _caption_for(label: str, preset: EditPreset) -> str:
    normalized = label.strip().lower()
    if preset.captionStyle == "plain":
        return label[:MAX_CAPTION_LENGTH]
    if "fast" in normalized:
        return "FAST BREAK"
    if "dunk" in normalized:
        return "BIG FINISH"
    if "defense" in normalized or "block" in normalized:
        return "LOCKDOWN"
    if "attempt" in normalized and any(token in normalized for token in ("shot", "jumper", "three", "3pt", "layup")):
        return "GOOD LOOK"
    if "shot" in normalized or "bucket" in normalized:
        return "BUCKET"
    if "layup" in normalized:
        return "TOUGH TAKE"
    return label.upper()[:MAX_CAPTION_LENGTH]


def _caption_for_clip(clip: EditCandidateClip, preset: EditPreset) -> str:
    if clip.captionHint:
        return clip.captionHint[:MAX_CAPTION_LENGTH]
    if is_shot_like_clip(clip):
        signals = native_shot_signals_for_clip(clip)
        if signals.outcome in {"uncertain", "not_shot"} and _shot_label_overclaims_outcome(clip.label):
            return "GOOD LOOK"
        if signals.outcome == "missed":
            return "GOOD LOOK"
        if signals.outcome == "blocked":
            return "LOCKDOWN"
    return _caption_for(clip.label, preset)


def _shot_label_overclaims_outcome(label: str) -> bool:
    normalized = label.strip().lower()
    return any(token in normalized for token in ("made", "bucket", "basket", "shot", "jumper", "attempt", "dunk", "finish"))


def add_caption(label: str, preset: EditPreset) -> str:
    return _caption_for(label, preset)


def _effects_for(clip: EditCandidateClip, source_start: float, source_end: float, preset: EditPreset) -> List[EditPlanEffect]:
    effects: List[EditPlanEffect] = []
    event_center = min(max(clip.eventCenter, source_start), source_end)

    if "punch_zoom" in preset.effects:
        effects.append(EditPlanEffect(type="punch_zoom", at=event_center, strength=0.18))

    if preset.slowMotionIntensity in {"high", "medium", "low_medium"}:
        slow_center = event_center
        if clip.suggestedSlowMotion and clip.suggestedSlowMotionCenter is not None:
            slow_center = min(max(clip.suggestedSlowMotionCenter, source_start), source_end)
        half_window = 0.6 if preset.slowMotionIntensity == "high" else 0.45
        slow_start = max(source_start, slow_center - half_window)
        slow_end = min(source_end, slow_center + half_window)
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

    if clip.suggestedSlowMotion and not any(effect.type == "slow_motion" for effect in effects):
        suggested_center = clip.suggestedSlowMotionCenter if clip.suggestedSlowMotionCenter is not None else event_center
        slow_center = min(max(suggested_center, source_start), source_end)
        slow_start = max(source_start, slow_center - 0.55)
        slow_end = min(source_end, slow_center + 0.55)
        if slow_end - slow_start >= 0.5:
            effects.append(
                EditPlanEffect(
                    type="slow_motion",
                    sourceStart=round(slow_start, 3),
                    sourceEnd=round(slow_end, 3),
                    speed=0.55,
                )
            )

    return effects


def add_slow_motion(clip: EditCandidateClip, source_start: float, source_end: float, preset: EditPreset) -> List[EditPlanEffect]:
    return [effect for effect in _effects_for(clip, source_start, source_end, preset) if effect.type == "slow_motion"]


def _source_window_start_for_clip(clip: EditCandidateClip, source_duration: float) -> float:
    extend_before = clip.suggestedExtendBeforeSeconds or 0.0
    extend_after = clip.suggestedExtendAfterSeconds or 0.0
    extension_bias = (extend_after - extend_before) * 0.5
    source_start = clip.eventCenter - (source_duration / 2.0) + extension_bias
    source_start = max(clip.start, min(source_start, clip.end - source_duration))
    return _clamp_source_window_start_for_clip_context(clip, source_start, source_duration)


def _clamp_source_window_start_for_clip_context(
    clip: EditCandidateClip,
    source_start: float,
    source_duration: float,
) -> float:
    lower_bound = clip.start
    upper_bound = clip.end - source_duration
    if upper_bound < lower_bound:
        return lower_bound
    if not is_shot_like_clip(clip):
        return max(lower_bound, min(source_start, upper_bound))

    contextual_lower_bound = max(
        lower_bound,
        clip.eventCenter + MIN_SHOT_CONTEXT_FOLLOW_THROUGH_SECONDS - source_duration,
    )
    contextual_upper_bound = min(
        upper_bound,
        clip.eventCenter - MIN_SHOT_CONTEXT_LEAD_IN_SECONDS,
    )
    if contextual_lower_bound <= contextual_upper_bound:
        return max(contextual_lower_bound, min(source_start, contextual_upper_bound))
    return max(lower_bound, min(source_start, upper_bound))


def build_edit_plan(request: CreateEditJobRequest, edit_job_id: str) -> EditPlan:
    context = build_edit_context(request)
    preset = PRESET_REGISTRY[request.preset]
    template = get_template_pack_for_plan(preset.presetId, request.templateId or preset.templateId)
    policy = get_plan_tier_policy(request.planTier)
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
    target_duration = min(choose_template_target_length(request.targetDurationSeconds, template), policy.maxRenderSeconds)
    aspect_ratio = request.aspectRatio or template.defaultAspectRatio
    theme = choose_theme(preset, request.theme)
    intro_duration = 1.2 if preset.presetId != "coach_review" else 0.0
    outro_duration = template.outroProfile.durationSeconds if policy.outroRequired else min(0.8, template.outroProfile.durationSeconds)
    outro_enabled = outro_duration > 0
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
        minimum_source_duration = max(MIN_PLAN_CLIP_SECONDS, min_clip_seconds * TEMPLATE_MIN_CLIP_TOLERANCE)
        if source_duration < minimum_source_duration:
            continue
        source_start = _source_window_start_for_clip(clip, source_duration)
        source_end = source_start + source_duration
        if source_end > clip.end:
            source_end = clip.end
            source_start = max(clip.start, source_end - source_duration)
        timeline_end = timeline_start + (source_end - source_start)
        caption_moment = None
        if clip.suggestedCaptionMoment is not None:
            caption_moment = round(min(max(clip.suggestedCaptionMoment, source_start), source_end), 3)
        plan_clips.append(
            EditPlanClip(
                clipId=clip.id,
                sourceStart=round(source_start, 3),
                sourceEnd=round(source_end, 3),
                eventCenter=round(clip.eventCenter, 3),
                timelineStart=round(timeline_start, 3),
                timelineEnd=round(timeline_end, 3),
                label=clip.label,
                caption=_caption_for_clip(clip, preset),
                captionMoment=caption_moment,
                cropMode=(clip.suggestedCropFocus or "center_action") if aspect_ratio != "source" else "source",
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
            enabled=outro_enabled,
            durationSeconds=outro_duration,
            templateId=template.outroProfile.assetId if outro_enabled else "none",
            assetId=template.outroProfile.assetId if outro_enabled else None,
        ),
        watermark=EditPlanWatermark(
            enabled=policy.watermarkRequired,
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
    policy = get_plan_tier_policy(plan_tier)

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
        if template.premiumOnly and not policy.premiumTemplatesAllowed:
            add("templateId", "premium_template_required", "Selected template requires HoopClips Pro.")
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
        if policy.watermarkRequired and template.watermarkProfile.requiredForFree and not plan.watermark.enabled:
            add("watermark.enabled", "missing_free_watermark", "Selected template requires the free-user watermark.")
        if policy.watermarkRequired and template.watermarkProfile.requiredForFree and plan.watermark.assetId != template.watermarkProfile.assetId:
            add("watermark.assetId", "missing_free_watermark_asset", "Selected template requires its registered free-user watermark asset.")
        if policy.outroRequired and template.outroProfile.requiredForFree and not plan.outro.enabled:
            add("outro.enabled", "missing_free_outro", "Selected template requires the free-user outro.")
        if policy.outroRequired and template.outroProfile.requiredForFree and plan.outro.assetId != template.outroProfile.assetId:
            add("outro.assetId", "missing_free_outro_asset", "Selected template requires its registered free-user outro asset.")
    if plan.targetDurationSeconds > policy.maxRenderSeconds:
        add("targetDurationSeconds", "render_duration_limit", "EditPlan exceeds the plan tier render duration limit.")
    if source_clips:
        max_source_end = max(clip.end for clip in source_clips)
        if max_source_end > policy.maxSourceVideoSeconds:
            add("sourceClips", "source_duration_limit", "Source video exceeds the plan tier source duration limit.")
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
        minimum_template_clip_seconds = max(MIN_PLAN_CLIP_SECONDS, template.clipLength.minSeconds * TEMPLATE_MIN_CLIP_TOLERANCE)
        if clip.sourceEnd - clip.sourceStart < MIN_PLAN_CLIP_SECONDS:
            add(f"{field_prefix}.source", "clip_too_short", "Clip is shorter than the minimum render duration.")
        if clip.sourceEnd - clip.sourceStart < minimum_template_clip_seconds:
            add(f"{field_prefix}.source", "template_clip_too_short", "Clip is shorter than the selected template minimum.")
        if is_shot_like_clip(source):
            lead_in = clip.eventCenter - clip.sourceStart
            follow_through = clip.sourceEnd - clip.eventCenter
            if lead_in < MIN_SHOT_CONTEXT_LEAD_IN_SECONDS:
                add(f"{field_prefix}.source", "shot_context_missing_setup", "Shot clip starts too close to the basketball event.")
            if follow_through < MIN_SHOT_CONTEXT_FOLLOW_THROUGH_SECONDS:
                add(f"{field_prefix}.source", "shot_context_missing_outcome", "Shot clip ends before enough outcome context is visible.")
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
    if planned_duration > policy.maxRenderSeconds + MAX_DURATION_OVERRUN_SECONDS:
        add("renderCost", "render_cost_limit", "EditPlan exceeds the plan tier render cost limit.")

    if policy.watermarkRequired:
        if not plan.watermark.enabled:
            add("watermark.enabled", "missing_free_watermark", "Free plans must include the Hoopclips watermark.")
        if plan.watermark.position not in {"bottom_right", "bottom_left", "top_right", "top_left"}:
            add("watermark.position", "invalid_watermark_position", "Watermark position is not supported.")
    if policy.outroRequired:
        if not plan.outro.enabled:
            add("outro.enabled", "missing_free_outro", "Free plans must include the Hoopclips outro.")
        if plan.outro.durationSeconds <= 0:
            add("outro.durationSeconds", "missing_free_outro", "Free plans must include a non-empty Hoopclips outro.")

    return errors


def apply_gpt_highlight_rerank(
    request: CreateEditJobRequest,
    decisions: Sequence[GPTHighlightClipDecision],
    model: Optional[str],
    sampled_clip_count: int,
    sampled_frame_count: int,
    story_order: Optional[Sequence[str]] = None,
    plan_edit: Optional[GPTPlanEdit] = None,
    sampled_frame_roles_by_clip: Optional[Mapping[str, Sequence[str]]] = None,
) -> CreateEditJobRequest:
    source_clips = filter_clips_for_team_selection(request.clips, request.teamSelection)
    source_by_id = {clip.id: clip for clip in source_clips}
    valid_decisions: Dict[str, GPTHighlightClipDecision] = {
        decision.clipId: decision for decision in decisions if decision.clipId in source_by_id
    }
    valid_story_order: List[str] = []
    seen_story_ids = set()
    requested_story_order = plan_edit.orderedClipIds if plan_edit and plan_edit.orderedClipIds else list(story_order or [])
    for clip_id in requested_story_order:
        decision = valid_decisions.get(clip_id)
        if clip_id in source_by_id and decision is not None and decision.keep and clip_id not in seen_story_ids:
            valid_story_order.append(clip_id)
            seen_story_ids.add(clip_id)
    story_index_by_id = {clip_id: index for index, clip_id in enumerate(valid_story_order)}
    if plan_edit is not None and _contains_forbidden_gpt_generated_content(plan_edit.model_dump()):
        plan_edit = None
    plan_captions_by_id = {item.clipId: item for item in plan_edit.captions} if plan_edit else {}
    plan_slow_motion_by_id = {item.clipId: item for item in plan_edit.slowMotionMoments} if plan_edit else {}
    applied_plan_caption_clip_ids: set[str] = set()
    applied_plan_slow_motion_clip_ids: set[str] = set()

    if not valid_decisions:
        fallback_clips = rank_clips([clip for clip in source_clips if is_plan_quality_eligible_clip(clip)])
        fallback_clip_ids = {clip.id for clip in fallback_clips}
        rejected_clip_ids = [clip.id for clip in request.clips if clip.id not in fallback_clip_ids]
        rejected_reason_counts = {}
        if rejected_clip_ids:
            rejected_reason_counts["candidate_missing_minimum_quality_context"] = len(rejected_clip_ids)
        summary = GPTHighlightRerankSummary(
            status="fallback",
            model=model,
            sampledClipCount=sampled_clip_count,
            sampledFrameCount=sampled_frame_count,
            returnedDecisionCount=len(decisions),
            keptClipIds=[clip.id for clip in fallback_clips[:30]],
            rejectedClipIds=rejected_clip_ids[:30],
            rejectedReasonCounts=rejected_reason_counts,
            fallbackReason="no_valid_decisions",
        )
        return request.model_copy(update={"clips": fallback_clips, "gptRerankSummary": summary})

    kept: List[EditCandidateClip] = []
    rejected_clip_ids: List[str] = []
    rejected_reason_counts: Dict[str, int] = {}
    missing_decision_clip_ids: List[str] = []
    for clip in request.clips:
        decision = valid_decisions.get(clip.id)
        if decision is None:
            missing_decision_clip_ids.append(clip.id)
            continue
        sampled_frame_roles = sampled_frame_roles_by_clip.get(clip.id) if sampled_frame_roles_by_clip is not None else None
        rejection_reason = _gpt_decision_rejection_reason(decision, clip, sampled_frame_roles)
        if rejection_reason is not None:
            rejected_clip_ids.append(clip.id)
            _increment_reason_count(rejected_reason_counts, rejection_reason)
            continue
        event_label = decision.basketballEvent.strip() or clip.label
        if decision.outcome != "unclear" and decision.outcome != "not_basketball":
            event_label = f"{event_label} ({decision.outcome})"
        suggested = decision.suggestedEdit
        plan_caption = plan_captions_by_id.get(clip.id)
        plan_slow_motion = plan_slow_motion_by_id.get(clip.id)
        caption = plan_caption.caption if plan_caption is not None else decision.caption
        caption_moment = plan_caption.captionMoment if plan_caption is not None else suggested.captionMoment
        if plan_caption is not None:
            applied_plan_caption_clip_ids.add(clip.id)
        if plan_slow_motion is not None:
            applied_plan_slow_motion_clip_ids.add(clip.id)
        suggested_slow_motion_center = _clamp_optional_clip_second(
            plan_slow_motion.center if plan_slow_motion is not None else suggested.slowMotionCenter,
            clip,
        )
        suggested_caption_moment = _clamp_optional_clip_second(caption_moment, clip)
        updated = clip.model_copy(
            update={
                "label": event_label[:80],
                "captionHint": caption[:MAX_CAPTION_LENGTH],
                "combinedScore": round((clip.planning_score * 0.25) + (decision.highlightScore * 0.55) + (decision.watchabilityScore * 0.2), 4),
                "gptHighlightScore": decision.highlightScore,
                "gptWatchabilityScore": decision.watchabilityScore,
                "gptReason": decision.reason,
                "suggestedSlowMotion": bool(suggested.slowMotion or plan_slow_motion is not None),
                "suggestedSlowMotionCenter": suggested_slow_motion_center,
                "suggestedCaptionMoment": suggested_caption_moment,
                "suggestedCropFocus": suggested.cropFocus,
                "suggestedExtendBeforeSeconds": suggested.extendBeforeSeconds,
                "suggestedExtendAfterSeconds": suggested.extendAfterSeconds,
                "gptStoryOrderIndex": story_index_by_id.get(clip.id),
                "gptStoryRole": decision.storyRole,
                "rerankSource": "gpt_highlight_reranker",
            }
        )
        kept.append(updated)

    if not kept:
        if missing_decision_clip_ids:
            _increment_reason_count(rejected_reason_counts, "missing_gpt_decision", len(missing_decision_clip_ids))
        summary = GPTHighlightRerankSummary(
            status="applied",
            model=model,
            sampledClipCount=sampled_clip_count,
            sampledFrameCount=sampled_frame_count,
            returnedDecisionCount=len(valid_decisions),
            keptClipIds=[],
            rejectedClipIds=(rejected_clip_ids + missing_decision_clip_ids)[:30],
            rejectedReasonCounts=rejected_reason_counts,
            fallbackReason="all_clips_rejected",
            storyOrderClipIds=[],
            planEditApplied=False,
        )
        return request.model_copy(update={"clips": [], "gptRerankSummary": summary})

    deduped, duplicate_dropped_ids = _dedupe_gpt_kept_moments(kept)
    if duplicate_dropped_ids:
        rejected_clip_ids.extend(duplicate_dropped_ids)
        _increment_reason_count(rejected_reason_counts, "duplicate_moment", len(duplicate_dropped_ids))
    if missing_decision_clip_ids:
        _increment_reason_count(rejected_reason_counts, "missing_gpt_decision", len(missing_decision_clip_ids))
    reranked = order_by_gpt_story_order(rank_clips(deduped))
    reranked_clip_ids = {clip.id for clip in reranked}
    applied_story_order = [clip_id for clip_id in valid_story_order if clip_id in reranked_clip_ids]
    plan_edit_applied = bool(
        plan_edit
        and (
            applied_story_order
            or (applied_plan_caption_clip_ids & reranked_clip_ids)
            or (applied_plan_slow_motion_clip_ids & reranked_clip_ids)
        )
    )
    summary = GPTHighlightRerankSummary(
        status="applied",
        model=model,
        sampledClipCount=sampled_clip_count,
        sampledFrameCount=sampled_frame_count,
        returnedDecisionCount=len(valid_decisions),
        keptClipIds=[clip.id for clip in reranked if clip.id in valid_decisions],
        rejectedClipIds=(rejected_clip_ids + missing_decision_clip_ids)[:30],
        rejectedReasonCounts=rejected_reason_counts,
        storyOrderClipIds=applied_story_order,
        planEditApplied=plan_edit_applied,
    )
    return request.model_copy(update={"clips": reranked, "gptRerankSummary": summary})


def _increment_reason_count(counts: Dict[str, int], reason: str, amount: int = 1) -> None:
    counts[reason] = counts.get(reason, 0) + amount


def _dedupe_gpt_kept_moments(clips: Sequence[EditCandidateClip]) -> Tuple[List[EditCandidateClip], List[str]]:
    kept_by_group: Dict[str, EditCandidateClip] = {}
    candidates: List[EditCandidateClip] = []
    dropped_ids: List[str] = []
    for clip in rank_clips(clips):
        if not clip.duplicateGroup:
            candidates.append(clip)
            continue
        current = kept_by_group.get(clip.duplicateGroup)
        if current is None:
            kept_by_group[clip.duplicateGroup] = clip
            continue
        if _duplicate_choice_key(clip) > _duplicate_choice_key(current):
            dropped_ids.append(current.id)
            kept_by_group[clip.duplicateGroup] = clip
        else:
            dropped_ids.append(clip.id)
    candidates.extend(kept_by_group.values())

    deduped: List[EditCandidateClip] = []
    for clip in rank_clips(candidates):
        duplicate_index = next((index for index, existing in enumerate(deduped) if _clips_describe_same_moment(clip, existing)), None)
        if duplicate_index is None:
            deduped.append(clip)
            continue
        if _duplicate_choice_key(clip) > _duplicate_choice_key(deduped[duplicate_index]):
            dropped_ids.append(deduped[duplicate_index].id)
            deduped[duplicate_index] = clip
        else:
            dropped_ids.append(clip.id)

    return rank_clips(deduped), dropped_ids


def _clips_describe_same_moment(left: EditCandidateClip, right: EditCandidateClip) -> bool:
    if left.duplicateGroup and left.duplicateGroup == right.duplicateGroup:
        return True
    overlap = _clip_overlap_ratio(left, right)
    if overlap >= 0.72:
        return True
    if abs(left.eventCenter - right.eventCenter) <= 1.0 and overlap >= 0.4:
        return True
    return False


def _clip_overlap_ratio(left: EditCandidateClip, right: EditCandidateClip) -> float:
    overlap = max(0.0, min(left.end, right.end) - max(left.start, right.start))
    if overlap <= 0.0:
        return 0.0
    shortest = min(max(left.duration, 0.001), max(right.duration, 0.001))
    return overlap / shortest


def _gpt_decision_rejection_reason(
    decision: GPTHighlightClipDecision,
    clip: EditCandidateClip,
    sampled_frame_roles: Optional[Sequence[str]] = None,
) -> Optional[str]:
    if _contains_forbidden_gpt_generated_content(decision.model_dump()):
        return "forbidden_gpt_output_content"
    if not decision.keep:
        if decision.rejectReason:
            return decision.rejectReason
        if decision.outcome in {"unclear", "not_basketball"}:
            return "unclear_or_non_basketball_outcome"
        return "gpt_rejected"
    if clip.duration < MIN_PLAN_CLIP_SECONDS:
        return "clip_too_short"
    if not is_plan_quality_eligible_clip(clip):
        return "candidate_missing_minimum_quality_context"
    if decision.highlightScore < MIN_GPT_HIGHLIGHT_SCORE:
        return "low_highlight_score"
    if decision.watchabilityScore < MIN_GPT_WATCHABILITY_SCORE:
        return "low_watchability_score"
    if decision.outcome in {"unclear", "not_basketball"}:
        return "unclear_or_non_basketball_outcome"
    if not _source_supports_gpt_outcome_claim(decision, clip):
        return "gpt_outcome_unsupported_by_source"
    if _gpt_outcome_conflicts_with_native_signal(decision, clip):
        return "gpt_outcome_conflicts_with_native_signal"

    signals = decision.qualitySignals
    tracking_evidence = decision.shotTrackingEvidence
    if not signals.eventVisible or not signals.outcomeVisible or not signals.cleanCamera:
        return "unclear_event_or_outcome"
    if not signals.fullPlayContext or not signals.setupVisible:
        return "missing_setup_context"
    if decision.outcome in {"made", "missed"} and not signals.releaseVisible:
        return "missing_shot_release"
    if decision.outcome in {"made", "missed"} and not signals.shotArcVisible:
        return "missing_shot_arc"
    if decision.outcome in {"made", "missed"} and not signals.rimResultVisible:
        return "missing_rim_result"
    if decision.outcome == "made" and not signals.ballPathVisible:
        return "missing_made_shot_ball_path"
    if decision.outcome == "missed" and not signals.ballPathVisible:
        return "missing_missed_shot_ball_path"
    if decision.outcome in GPT_NON_SCORING_DEFENSIVE_OUTCOMES:
        if sampled_frame_roles is not None:
            defensive_role_rejection = _defensive_sampled_tracking_rejection_reason(tracking_evidence, sampled_frame_roles)
            if defensive_role_rejection is not None:
                return defensive_role_rejection
        if not signals.playerControlVisible:
            return "missing_defensive_player_control"
        if not signals.ballPathVisible:
            return "missing_defensive_ball_control"
        if not has_minimum_non_shot_quality(clip):
            return "low_defensive_clip_quality"
        return None
    if not signals.playerControlVisible and decision.outcome in {"made", "missed"}:
        return "missing_player_control"
    result_evidence = decision.shotResultEvidence
    if decision.outcome in {"made", "missed"} and result_evidence.releaseToRimContinuity == "missing":
        return "missing_release_to_rim_continuity"
    if decision.outcome == "made":
        if result_evidence.rimResultEvidence != "made_visible":
            return "made_outcome_not_visible"
        if result_evidence.outcomeConfidence < 0.72:
            return "low_shot_result_confidence"
        if result_evidence.rimEntrySequence != "visible_entry":
            return "made_rim_entry_sequence_not_visible"
        if result_evidence.rimEntrySequenceConfidence < 0.72:
            return "low_rim_entry_sequence_confidence"
        if result_evidence.ballApproachFrameRole not in SHOT_TRACKING_RIM_ENTRY_APPROACH_ROLES:
            return "missing_rim_entry_approach_frame"
        if result_evidence.rimEntryFrameRole not in SHOT_TRACKING_RIM_ENTRY_FRAME_ROLES:
            return "missing_rim_entry_frame"
    if decision.outcome == "missed":
        if result_evidence.rimResultEvidence != "clear_miss":
            return "miss_outcome_not_visible"
        if result_evidence.outcomeConfidence < 0.65:
            return "low_shot_result_confidence"
    if decision.outcome == "blocked":
        if sampled_frame_roles is not None:
            blocked_role_rejection = _blocked_sampled_tracking_rejection_reason(tracking_evidence, sampled_frame_roles)
            if blocked_role_rejection is not None:
                return blocked_role_rejection
        if result_evidence.rimResultEvidence != "blocked":
            return "blocked_outcome_not_visible"
        if result_evidence.outcomeConfidence < 0.65:
            return "low_shot_result_confidence"
    ball_roles = set(tracking_evidence.ballVisibleFrameRoles)
    rim_roles = set(tracking_evidence.rimVisibleFrameRoles)
    if decision.outcome in {"made", "missed"} and sampled_frame_roles is not None:
        unsampled_roles = _unsampled_gpt_tracking_roles(tracking_evidence, sampled_frame_roles)
        unsampled_roles |= _unsampled_gpt_result_roles(result_evidence, sampled_frame_roles)
        if unsampled_roles:
            return "gpt_cited_unsampled_frame_role"
        rich_role_rejection_reason = _rich_sampled_tracking_rejection_reason(tracking_evidence, sampled_frame_roles)
        if rich_role_rejection_reason is not None:
            return rich_role_rejection_reason
        rich_result_rejection_reason = _rich_sampled_result_rejection_reason(result_evidence, sampled_frame_roles)
        if rich_result_rejection_reason is not None:
            return rich_result_rejection_reason
    if decision.outcome in {"made", "missed"}:
        if tracking_evidence.releaseFrameRole not in SHOT_TRACKING_RELEASE_ROLES:
            return "missing_tracking_release_frame"
        if tracking_evidence.resultFrameRole not in SHOT_TRACKING_RESULT_ROLES:
            return "missing_tracking_result_frame"
        if len(ball_roles & SHOT_TRACKING_BALL_FLIGHT_ROLES) < 2:
            return "insufficient_ball_tracking_frames"
        if not (rim_roles & SHOT_TRACKING_RESULT_ROLES):
            return "missing_rim_tracking_frame"
        if tracking_evidence.trajectoryContinuity == "missing":
            return "missing_shot_tracking_trajectory"
    if decision.outcome == "made":
        if tracking_evidence.trajectoryContinuity != "continuous":
            return "incomplete_made_shot_tracking"
        if tracking_evidence.ballEntersRimFrameRole not in SHOT_TRACKING_RESULT_ROLES:
            return "missing_made_shot_entry_frame"
        if result_evidence.ballBelowRimOrNetFrameRole not in SHOT_TRACKING_RIM_ENTRY_FOLLOW_THROUGH_ROLES:
            return "missing_rim_entry_followthrough_frame"
    return None


def _unsampled_gpt_tracking_roles(
    tracking_evidence: GPTShotTrackingEvidence,
    sampled_frame_roles: Sequence[str],
) -> set[str]:
    sampled_roles = set(sampled_frame_roles)
    cited_roles = set(tracking_evidence.ballVisibleFrameRoles) | set(tracking_evidence.rimVisibleFrameRoles)
    optional_roles = (
        tracking_evidence.releaseFrameRole,
        tracking_evidence.resultFrameRole,
        tracking_evidence.ballEntersRimFrameRole,
    )
    cited_roles.update(role for role in optional_roles if role is not None)
    return cited_roles - sampled_roles


def _defensive_sampled_tracking_rejection_reason(
    tracking_evidence: GPTShotTrackingEvidence,
    sampled_frame_roles: Sequence[str],
) -> Optional[str]:
    sampled_roles = set(sampled_frame_roles)
    cited_roles = set(tracking_evidence.ballVisibleFrameRoles)
    for role in (tracking_evidence.resultFrameRole, tracking_evidence.ballEntersRimFrameRole):
        if role is not None:
            cited_roles.add(role)
    unsampled_roles = (cited_roles & DEFENSIVE_TRACKING_EVENT_ROLES) - sampled_roles
    if unsampled_roles:
        return "gpt_cited_unsampled_frame_role"
    if "possessionChange" in sampled_roles and "possessionChange" not in cited_roles:
        return "missing_defensive_possession_change_frame"
    if sampled_roles & {"recovery", "defenseOutcome"} and not (cited_roles & DEFENSIVE_TRACKING_RESULT_ROLES):
        return "missing_defensive_outcome_frame"
    return None


def _blocked_sampled_tracking_rejection_reason(
    tracking_evidence: GPTShotTrackingEvidence,
    sampled_frame_roles: Sequence[str],
) -> Optional[str]:
    sampled_roles = set(sampled_frame_roles)
    cited_roles = set(tracking_evidence.ballVisibleFrameRoles)
    for role in (tracking_evidence.resultFrameRole, tracking_evidence.ballEntersRimFrameRole):
        if role is not None:
            cited_roles.add(role)
    unsampled_roles = (cited_roles & DEFENSIVE_TRACKING_EVENT_ROLES) - sampled_roles
    if unsampled_roles:
        return "gpt_cited_unsampled_frame_role"
    if "challenge" in sampled_roles and "challenge" not in cited_roles:
        return "missing_block_challenge_frame"
    if sampled_roles & {"recovery", "defenseOutcome"} and not (cited_roles & {"recovery", "defenseOutcome", "finish"}):
        return "missing_block_outcome_frame"
    return None


def _unsampled_gpt_result_roles(
    result_evidence: GPTShotResultEvidence,
    sampled_frame_roles: Sequence[str],
) -> set[str]:
    sampled_roles = set(sampled_frame_roles)
    cited_roles = {
        role
        for role in (
            result_evidence.ballApproachFrameRole,
            result_evidence.rimEntryFrameRole,
            result_evidence.ballBelowRimOrNetFrameRole,
        )
        if role is not None
    }
    return cited_roles - sampled_roles


def _rich_sampled_tracking_rejection_reason(
    tracking_evidence: GPTShotTrackingEvidence,
    sampled_frame_roles: Sequence[str],
) -> Optional[str]:
    sampled_roles = set(sampled_frame_roles)
    ball_roles = set(tracking_evidence.ballVisibleFrameRoles)
    rim_roles = set(tracking_evidence.rimVisibleFrameRoles)

    if sampled_roles & SHOT_TRACKING_RICH_RELEASE_ROLES and tracking_evidence.releaseFrameRole not in SHOT_TRACKING_RICH_RELEASE_ROLES:
        return "gpt_ignored_sampled_release_frame"
    if sampled_roles & SHOT_TRACKING_RICH_ARC_ROLES and not (ball_roles & SHOT_TRACKING_RICH_ARC_ROLES):
        return "gpt_missing_sampled_arc_tracking"
    if sampled_roles & SHOT_TRACKING_RICH_RESULT_ROLES and tracking_evidence.resultFrameRole not in SHOT_TRACKING_RICH_RESULT_ROLES:
        return "gpt_ignored_sampled_result_frame"
    if "rimEntry" in sampled_roles and tracking_evidence.ballEntersRimFrameRole != "rimEntry":
        return "gpt_ignored_sampled_ball_entry_frame"
    if sampled_roles & SHOT_TRACKING_RICH_RIM_ROLES and not (rim_roles & SHOT_TRACKING_RICH_RIM_ROLES):
        return "gpt_missing_sampled_rim_tracking"
    return None


def _rich_sampled_result_rejection_reason(
    result_evidence: GPTShotResultEvidence,
    sampled_frame_roles: Sequence[str],
) -> Optional[str]:
    sampled_roles = set(sampled_frame_roles)
    if result_evidence.rimEntrySequence != "visible_entry":
        return None
    if "rimApproach" in sampled_roles and result_evidence.ballApproachFrameRole != "rimApproach":
        return "gpt_ignored_sampled_rim_approach_frame"
    if "rimEntry" in sampled_roles and result_evidence.rimEntryFrameRole != "rimEntry":
        return "gpt_ignored_sampled_rim_entry_frame"
    if "belowRim" in sampled_roles and result_evidence.ballBelowRimOrNetFrameRole != "belowRim":
        return "gpt_ignored_sampled_below_rim_frame"
    if sampled_roles & SHOT_TRACKING_RICH_RESULT_ROLES and result_evidence.rimEntryFrameRole not in SHOT_TRACKING_RICH_RESULT_ROLES:
        return "gpt_ignored_sampled_rim_entry_frame"
    if sampled_roles & {"postOutcome"} and result_evidence.ballBelowRimOrNetFrameRole not in {"postOutcome", "finish"}:
        return "gpt_ignored_sampled_post_entry_frame"
    return None


def _gpt_outcome_conflicts_with_native_signal(decision: GPTHighlightClipDecision, clip: EditCandidateClip) -> bool:
    if decision.outcome not in GPT_SHOT_RESULT_OUTCOMES:
        return False

    native_signals = native_shot_signals_for_clip(clip)
    if native_signals.outcome not in GPT_SHOT_RESULT_OUTCOMES:
        return False
    if native_signals.outcomeConfidence < MIN_NATIVE_OUTCOME_CONFLICT_CONFIDENCE:
        return False
    return native_signals.outcome != decision.outcome


def _source_supports_gpt_outcome_claim(decision: GPTHighlightClipDecision, clip: EditCandidateClip) -> bool:
    if decision.outcome in GPT_NON_SCORING_DEFENSIVE_OUTCOMES:
        if is_shot_like_clip(clip):
            return False
        if not has_minimum_non_shot_quality(clip):
            return False

        normalized_label = clip.label.strip().lower()
        defensive_label = any(
            token in normalized_label
            for token in ("defense", "defensive", "steal", "strip", "turnover", "forced", "stop", "pressure", "lockdown")
        )
        if defensive_label:
            return True
        if not is_generic_filler_clip(clip):
            return max(clip.watchability, clip.motionScore) >= 0.55 and clip.confidence >= 0.55
        return max(clip.watchability, clip.motionScore) >= 0.72 and clip.confidence >= 0.65 and clip.planning_score >= 0.7

    if decision.outcome not in GPT_SHOT_RESULT_OUTCOMES:
        return True
    if is_shot_like_clip(clip):
        return True

    normalized_label = clip.label.strip().lower()
    if decision.outcome in {"made", "missed"} and normalized_label in {"defense", "defensive stop", "block", "steal"}:
        return False
    if not is_generic_filler_clip(clip):
        return True

    return (
        max(clip.watchability, clip.motionScore) >= 0.72
        and clip.confidence >= 0.65
        and clip.planning_score >= 0.7
    )


def _clamp_optional_clip_second(value: Optional[float], clip: EditCandidateClip) -> Optional[float]:
    if value is None:
        return None
    return round(min(max(value, clip.start), clip.end), 3)


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
    policy = get_plan_tier_policy(plan_tier)
    data["templateId"] = template.templateId
    data["captionStyle"] = template.captionStyle.styleId
    data["targetDurationSeconds"] = min(int(data["targetDurationSeconds"]), policy.maxRenderSeconds)
    if data.get("aspectRatio") not in template.allowedAspectRatios:
        data["aspectRatio"] = template.defaultAspectRatio
    if not data.get("theme") or data["theme"] not in THEME_REGISTRY:
        data["theme"] = template.themeId
    if policy.watermarkRequired:
        data["watermark"]["enabled"] = True
        data["watermark"]["position"] = data["watermark"].get("position") or template.watermarkProfile.position
        data["watermark"]["assetId"] = template.watermarkProfile.assetId
    if policy.outroRequired:
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
    current_template = get_template_pack_for_plan(job.plan.preset, job.plan.templateId)
    premium_templates_allowed = get_plan_tier_policy(job.request.planTier).premiumTemplatesAllowed

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

    if command in {"make_more_hype", "add_more_slow_motion"} and not current_template.premiumOnly:
        request_data["preset"] = "personal_highlight"
        request_data["templateId"] = "personal_highlight_v1"
        request_data["aspectRatio"] = revision.aspectRatio or request_data.get("aspectRatio") or "9:16"
    elif command == "make_personal":
        request_data["preset"] = "personal_highlight"
        request_data["templateId"] = "personal_highlight_v1"
        request_data["aspectRatio"] = revision.aspectRatio or request_data.get("aspectRatio") or "9:16"
    elif command == "make_nba_style":
        request_data["preset"] = "full_game_highlight"
        request_data["templateId"] = "nba_recap_pro_v1" if premium_templates_allowed else "full_game_highlight_v1"
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
        revised_template = get_template_pack_for_plan(revised.plan.preset, revised.plan.templateId)
        data["theme"] = revised_template.themeId
        data["templateId"] = revised_template.templateId
        data["captionStyle"] = revised_template.captionStyle.styleId
        data["aspectRatio"] = revised_template.defaultAspectRatio if not revised_template.premiumOnly else data["aspectRatio"]
        data["audio"] = {
            "mode": "music_plus_game_audio",
            "musicTrackId": data.get("audio", {}).get("musicTrackId") if revised_template.premiumOnly else "hype_02",
            "musicVolume": min(0.9, float(data.get("audio", {}).get("musicVolume", revised_template.audioProfile.musicVolume)) + 0.08),
            "gameAudioVolume": max(0.2, float(data.get("audio", {}).get("gameAudioVolume", revised_template.audioProfile.gameAudioVolume)) - 0.04),
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
        nba_template = get_template_pack_for_plan("full_game_highlight", data.get("templateId"))
        data["theme"] = nba_template.themeId
        data["templateId"] = nba_template.templateId
        data["captionStyle"] = nba_template.captionStyle.styleId
        data["aspectRatio"] = "16:9"
        data["audio"] = {
            "mode": nba_template.audioProfile.mode,
            "musicTrackId": nba_template.audioProfile.musicTrackId,
            "musicVolume": nba_template.audioProfile.musicVolume,
            "gameAudioVolume": nba_template.audioProfile.gameAudioVolume,
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


FORBIDDEN_GPT_PATCH_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bffmpeg\b",
        r"\bffprobe\b",
        r"\bavfoundation\b",
        r"\blocal_avfoundation\b",
        r"\brender\s+locally\b",
        r"\blocal\s+render(?:ing)?\b",
        r"\bon[-\s]?device\s+(?:edit(?:ing)?|render(?:ing)?|export)\b",
        r"\bshell\s+command\b",
        r"\bbash\s+-?[a-z]*\b",
        r"\bsh\s+-c\b",
        r"\bpython3?\s+-c\b",
        r"\bcurl\s+",
        r"\bsubprocess\b",
        r"\bos\.system\b",
        r"\bhttps?://",
        r"\bfile://",
        r"\bdata:video/",
        r"\bs3://",
        r"\bgs://",
        r"\br2://",
        r"\bpresigned\b",
        r"\bdownloadUrl\b",
        r"\bsourceObjectKey\b",
        r"\boutputObjectKey\b",
        r"\brenderLogObjectKey\b",
        r"\brenderStorage\b",
        r"\b(?:aws|r2)[_-]?(?:access|secret|token|credential|signature)",
        r"\bx-amz-(?:signature|credential|security-token)\b",
        r"\b(?:uploads|renders|render_logs)/[A-Za-z0-9._~/-]+",
        r"\.mp4\b",
    ]
]


def _contains_forbidden_gpt_generated_content(value: Any) -> bool:
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in FORBIDDEN_GPT_PATCH_PATTERNS)
    if isinstance(value, dict):
        return any(_contains_forbidden_gpt_generated_content(item) for pair in value.items() for item in pair)
    if isinstance(value, list):
        return any(_contains_forbidden_gpt_generated_content(item) for item in value)
    return False


def _contains_forbidden_gpt_patch_content(value: Any) -> bool:
    return _contains_forbidden_gpt_generated_content(value)


def apply_edit_plan_patch(plan: EditPlan, patch: EditPlanPatch) -> EditPlan:
    if _contains_forbidden_gpt_patch_content(patch.model_dump()):
        raise ValueError("EditPlanPatch must not contain render commands, local-render instructions, URLs, or storage keys.")
    data = plan.model_dump()
    for operation in patch.operations:
        _apply_pointer_operation(data, operation)
    return EditPlan(**data)


def validate_edit_plan_patch(
    plan: EditPlan,
    patch: EditPlanPatch,
    source_clips: Sequence[EditCandidateClip],
    plan_tier: PlanTier,
) -> Tuple[Optional[EditPlan], List[EditPlanValidationIssue]]:
    try:
        patched = repair_edit_plan(apply_edit_plan_patch(plan, patch), plan_tier)
    except (TypeError, ValueError, ValidationError) as error:
        return None, [
            EditPlanValidationIssue(
                field="patch",
                code="invalid_gpt_patch",
                message=str(error),
            )
        ]
    errors = validate_edit_plan(patched, source_clips, plan_tier)
    policy = get_plan_tier_policy(plan_tier)
    if estimate_render_cost(patched)["plannedDurationSeconds"] > policy.maxRenderSeconds + MAX_DURATION_OVERRUN_SECONDS:
        errors.append(
            EditPlanValidationIssue(
                field="renderCost",
                code="render_cost_too_high",
                message="Patched EditPlan exceeds the configured render cost limit.",
            )
        )
    return patched, errors


def build_revision_response(
    job: StoredEditJob,
    revision: ReviseEditJobRequest,
    revision_id: str,
    proposed_patch: Optional[EditPlanPatch] = None,
) -> Tuple[StoredEditJob, EditRevisionResponse]:
    if proposed_patch is not None:
        patched_plan, errors = validate_edit_plan_patch(job.plan, proposed_patch, job.request.clips, job.request.planTier)
        if patched_plan is None:
            patched_plan = job.plan
        revised = StoredEditJob(
            edit_job_id=job.edit_job_id,
            install_id=job.install_id,
            request=job.request,
            plan=patched_plan,
            status="plan_ready" if not errors else "failed",
            created_at=job.created_at,
            updated_at=now_utc(),
            validation_errors=errors,
        )
        response = EditRevisionResponse(
            revisionId=revision_id,
            editJobId=job.edit_job_id,
            basePlanId=job.edit_job_id,
            newPlanId=f"{job.edit_job_id}:{revision_id}",
            command=revision.command,
            status="revision_ready" if not errors else "revision_failed",
            patch=proposed_patch,
            revisedPlan=patched_plan,
            validationResult=EditRevisionValidationResult(valid=not errors, errors=errors),
            requiresRerender=True,
        )
        return revised, response

    revised = _build_revised_edit_job(job, revision)
    patch = build_edit_plan_patch(job, revision, revised.plan)
    patched_plan, errors = validate_edit_plan_patch(job.plan, patch, revised.request.clips, revised.request.planTier)
    if patched_plan is None:
        patched_plan = revised.plan
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
