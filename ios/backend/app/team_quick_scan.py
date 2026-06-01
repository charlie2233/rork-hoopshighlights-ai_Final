from __future__ import annotations

from dataclasses import dataclass, replace
import base64
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings
from .models import ClipTeamAttribution, CloudClip, TeamOption, clamp
from .team_identity import clean_text, color_labeled_team_name, resolve_jersey_color, team_key


ResponseClient = Callable[[Dict[str, Any], str, str, float], Dict[str, Any]]
TEAM_QUICK_SCAN_CONFIDENT_ATTRIBUTION = 0.85
TEAM_QUICK_SCAN_UNVERIFIED_ATTRIBUTION_MAX_CONFIDENCE = TEAM_QUICK_SCAN_CONFIDENT_ATTRIBUTION - 0.01
TEAM_QUICK_SCAN_MIN_CONFIDENT_EVIDENCE_FRAME_REFS = 2
TEAM_QUICK_SCAN_MIN_CONFIDENT_EVIDENCE_ROLE_GROUPS = 2
TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS = 220
TEAM_QUICK_SCAN_MAX_FRAMES_PER_CANDIDATE = 8
TEAM_QUICK_SCAN_COMPACT_FRAMES_PER_CANDIDATE = 3
TEAM_QUICK_SCAN_RICH_CANDIDATE_CLIPS = 160
TEAM_QUICK_SCAN_DEFAULT_TOTAL_CLIP_FRAMES = 1760
TEAM_QUICK_SCAN_MAX_TOTAL_CLIP_FRAMES = 2200
TEAM_QUICK_SCAN_PRESCAN_MAX_CANDIDATE_CLIPS = 12
TEAM_QUICK_SCAN_PRESCAN_RICH_CANDIDATE_CLIPS = 8
TEAM_QUICK_SCAN_PRESCAN_FRAMES_PER_CANDIDATE = 4
TEAM_QUICK_SCAN_PRESCAN_MAX_TOTAL_CLIP_FRAMES = 56
TEAM_QUICK_SCAN_PRESCAN_MIN_TIMEOUT_SECONDS = 60.0
TEAM_QUICK_SCAN_SCORING_OWNERSHIP_ROLES = {"ballhandlersetup", "prerelease", "release"}
TEAM_QUICK_SCAN_BLOCK_ACTION_ROLES = {"challenge", "balldeflection"}
TEAM_QUICK_SCAN_POSSESSION_CHANGE_ACTION_ROLES = {
    "balldeflection",
    "possessionchange",
    "ballcontrolchange",
}
TEAM_QUICK_SCAN_DEFENSIVE_STOP_ACTION_ROLES = {
    "challenge",
    "possessionpressure",
    "possessionchange",
    "ballcontrolchange",
}


@dataclass(frozen=True)
class QuickScanFrame:
    frame_ref: str
    role: str
    time_seconds: float
    data_url: str
    clip_ref: Optional[str] = None


def apply_team_quick_scan(
    source_path: Path,
    duration_seconds: float,
    clips: Sequence[CloudClip],
    settings: Settings,
    response_client: Optional[ResponseClient] = None,
) -> tuple[list[CloudClip], list[TeamOption], bool]:
    if not getattr(settings, "team_quick_scan_enabled", False):
        return list(clips), [], False
    api_key = getattr(settings, "team_quick_scan_api_key", None)
    if not api_key:
        return list(clips), [], False
    if not source_path.is_file():
        return list(clips), [], False

    frames = _extract_quick_scan_frames(source_path, duration_seconds, clips, settings)
    if not frames:
        return list(clips), [], False

    payload = _build_openai_payload(duration_seconds, clips, frames, settings)
    try:
        client = response_client or _default_responses_client
        response_payload = client(
            payload,
            api_key,
            getattr(settings, "team_quick_scan_endpoint", "https://api.openai.com/v1/responses"),
            float(getattr(settings, "team_quick_scan_timeout_seconds", 24.0)),
        )
        output = json.loads(_extract_output_text(response_payload))
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError):
        return list(clips), [], False

    teams, attributions = _parse_quick_scan_output(
        output,
        settings,
        _evidence_frame_refs_by_clip(frames),
        _evidence_frame_roles_by_clip(frames),
        {f"clip_{index}": clip.label for index, clip in enumerate(clips)},
    )
    scanned: list[CloudClip] = []
    for index, clip in enumerate(clips):
        attribution = attributions.get(f"clip_{index}")
        scanned.append(clip.model_copy(update={"teamAttribution": attribution}) if attribution is not None else clip)
    return scanned, teams, bool(teams or attributions)


def team_quick_prescan_settings(settings: Settings) -> Settings:
    """Use a smaller real GPT vision budget for the interactive team picker."""
    return replace(
        settings,
        team_quick_scan_timeout_seconds=max(
            float(getattr(settings, "team_quick_scan_timeout_seconds", 24.0)),
            TEAM_QUICK_SCAN_PRESCAN_MIN_TIMEOUT_SECONDS,
        ),
        team_quick_scan_max_candidate_clips=min(
            int(getattr(settings, "team_quick_scan_max_candidate_clips", TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS)),
            TEAM_QUICK_SCAN_PRESCAN_MAX_CANDIDATE_CLIPS,
        ),
        team_quick_scan_rich_candidate_clips=min(
            int(getattr(settings, "team_quick_scan_rich_candidate_clips", TEAM_QUICK_SCAN_RICH_CANDIDATE_CLIPS)),
            TEAM_QUICK_SCAN_PRESCAN_RICH_CANDIDATE_CLIPS,
        ),
        team_quick_scan_clip_frames_per_clip=min(
            int(getattr(settings, "team_quick_scan_clip_frames_per_clip", TEAM_QUICK_SCAN_MAX_FRAMES_PER_CANDIDATE)),
            TEAM_QUICK_SCAN_PRESCAN_FRAMES_PER_CANDIDATE,
        ),
        team_quick_scan_max_total_clip_frames=min(
            int(getattr(settings, "team_quick_scan_max_total_clip_frames", TEAM_QUICK_SCAN_DEFAULT_TOTAL_CLIP_FRAMES)),
            TEAM_QUICK_SCAN_PRESCAN_MAX_TOTAL_CLIP_FRAMES,
        ),
    )


def _build_openai_payload(
    duration_seconds: float,
    clips: Sequence[CloudClip],
    frames: Sequence[QuickScanFrame],
    settings: Settings,
) -> Dict[str, Any]:
    candidate_clip_limit = _max_quick_scan_candidate_clips(settings, len(clips))
    candidate_clips = list(clips[:candidate_clip_limit])
    context = {
        "task": "Detect basketball teams by jersey color and attribute each candidate clip to the team controlling the highlight moment.",
        "rules": {
            "noFullVideo": True,
            "useOnlySampledFrames": True,
            "teamIdentity": "Use jersey color labels such as black, white, red, blue, green, yellow, gray, orange, purple, or mixed. Do not rely on scoreboard text alone.",
            "selectedTeamAccuracyTarget": TEAM_QUICK_SCAN_CONFIDENT_ATTRIBUTION,
            "uncertainPolicy": "If ball control, defender, or jersey color is unclear, return lower confidence instead of guessing. The backend keeps uncertain clips for review.",
            "highlightOwnership": "For made shots, ownership is the shooter/finisher team. For blocks, steals, defensive stops, or forced turnovers, ownership is the defender who made the play.",
            "scoringFrameRoles": "For scoring clips, ballHandlerSetup, preRelease, release, and shotArc show the offensive player/team; rimApproach and rimResult show the outcome; followThrough/finishContext show the finisher after the play.",
            "defensiveFrameRoles": "For defensive clips, defenseSetup and preChallenge/prePossessionChange show the defender before the event, challenge/ballDeflection or possessionChange/ballControlChange shows the defensive action, and recovery/defenseOutcome/finishContext show the result.",
            "frameBudgetPolicy": "Higher-ranked candidates may include up to eight role frames; later candidates may include a compact three-frame ownership set. Use every supplied role for confidence.",
            "evidencePolicy": "Every clip attribution must cite evidenceFrameRefs from that clip. Use confidence >=0.85 only when at least two cited frames from different play phases clearly show jersey color and ownership.",
        },
        "durationSeconds": round(duration_seconds, 3),
        "candidateClips": [
            {
                "clipRef": f"clip_{index}",
                "start": round(clip.startTime, 3),
                "end": round(clip.endTime, 3),
                "eventCenter": round(clip.eventCenter, 3) if clip.eventCenter is not None else None,
                "duration": round(max(0.0, clip.endTime - clip.startTime), 3),
                "label": clip.label,
                "action": clip.action,
                "confidence": clip.confidence,
                "motionScore": clip.motionScore,
                "visualScore": clip.visualScore,
                "audioScore": clip.audioScore,
                "combinedScore": clip.combinedScore,
            }
            for index, clip in enumerate(candidate_clips)
        ],
    }
    content: list[dict[str, Any]] = [{"type": "input_text", "text": json.dumps(context, separators=(",", ":"))}]
    for frame in frames:
        frame_context = {
            "frameRef": frame.frame_ref,
            "role": frame.role,
            "time": round(frame.time_seconds, 3),
            "clipRef": frame.clip_ref,
        }
        content.append({"type": "input_text", "text": json.dumps(frame_context, separators=(",", ":"))})
        content.append({"type": "input_image", "image_url": frame.data_url, "detail": "high"})

    return {
        "model": getattr(settings, "team_quick_scan_model", "gpt-4.1"),
        "store": False,
        "instructions": (
            "You are HoopClips Team Quick Scan. Identify the teams in sampled basketball frames by visible jersey color, "
            "then assign each candidate clip to the team responsible for the highlight moment. Use confidence >=0.85 only "
            "when team ownership is visually clear. Use lower confidence for occlusion, camera blur, mixed jerseys, or ambiguous possession. "
            "For scoring frame roles, use ballHandlerSetup, preRelease, release, and shotArc to judge the shooter/finisher team, then rimApproach/rimResult/followThrough/finishContext to confirm the play. "
            "Blocks, steals, defensive stops, and forced turnovers belong to the defending player who made the play. "
            "For defensive frame roles, use defenseSetup plus preChallenge/prePossessionChange, challenge/ballDeflection or possessionChange/ballControlChange, and recovery/defenseOutcome/finishContext to judge the defender's team. "
            "For each clip attribution, include evidenceFrameRefs that exactly match supplied frameRef values for that clip; high-confidence ownership requires at least two cited frames from different phases such as setup/action/outcome. "
            "Use only supplied frames and candidate clip refs. Do not output prose, commands, file paths, URLs, storage keys, or FFmpeg instructions. "
            "Return strict JSON only."
        ),
        "input": [{"role": "user", "content": content}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "hoopclips_team_quick_scan",
                "strict": True,
                "schema": _response_schema(candidate_clip_limit),
            }
        },
        "max_output_tokens": int(getattr(settings, "team_quick_scan_max_output_tokens", 12000)),
    }


def _response_schema(max_clip_attributions: int = 40) -> Dict[str, Any]:
    max_clip_attributions = max(1, min(int(max_clip_attributions), TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS))
    nullable_string = {"anyOf": [{"type": "string", "maxLength": 80}, {"type": "null"}]}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "teams": {
                "type": "array",
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "teamId": {"type": "string", "maxLength": 80},
                        "label": {"type": "string", "maxLength": 80},
                        "colorLabel": nullable_string,
                        "primaryColorHex": nullable_string,
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": "string", "maxLength": 180},
                    },
                    "required": ["teamId", "label", "colorLabel", "primaryColorHex", "confidence", "reason"],
                },
            },
            "clipAttributions": {
                "type": "array",
                "maxItems": max_clip_attributions,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "clipRef": {"type": "string", "pattern": "^clip_[0-9]+$"},
                        "teamId": nullable_string,
                        "label": nullable_string,
                        "colorLabel": nullable_string,
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": "string", "maxLength": 180},
                        "evidenceFrameRefs": {
                            "type": "array",
                            "maxItems": 8,
                            "items": {"type": "string", "maxLength": 120},
                        },
                    },
                    "required": ["clipRef", "teamId", "label", "colorLabel", "confidence", "reason", "evidenceFrameRefs"],
                },
            },
        },
        "required": ["teams", "clipAttributions"],
    }


def _parse_quick_scan_output(
    output: object,
    settings: Settings,
    evidence_frame_refs_by_clip: Optional[dict[str, set[str]]] = None,
    evidence_frame_roles_by_clip: Optional[dict[str, dict[str, str]]] = None,
    labels_by_clip_ref: Optional[dict[str, str]] = None,
) -> tuple[list[TeamOption], dict[str, ClipTeamAttribution]]:
    if not isinstance(output, dict):
        return [], {}
    min_team_confidence = float(getattr(settings, "team_quick_scan_min_team_confidence", 0.55))

    teams: list[TeamOption] = []
    seen_team_ids: set[str] = set()
    for item in output.get("teams", []):
        if not isinstance(item, dict):
            continue
        confidence = clamp(_coerce_float(item.get("confidence"), 0.0), 0.0, 1.0)
        if confidence < min_team_confidence:
            continue
        raw_label = clean_text(item.get("label"))
        color_label = resolve_jersey_color(item.get("colorLabel"), raw_label, item.get("teamId"))
        if color_label is None:
            continue
        label = color_labeled_team_name(color_label, raw_label)
        raw_team_id = _clean_team_id(item.get("teamId"))
        raw_team_id_color = resolve_jersey_color(raw_team_id)
        team_id = raw_team_id if raw_team_id_color == color_label else _team_id_from_label(color_label)
        if not team_id or team_id in seen_team_ids:
            continue
        seen_team_ids.add(team_id)
        team = TeamOption(
            teamId=team_id,
            label=label,
            colorLabel=color_label,
            primaryColorHex=_clean_hex_color(item.get("primaryColorHex")),
            confidence=round(confidence, 4),
            source="quick_scan",
        )
        teams.append(team)

    team_confidence_by_key = _team_confidence_by_key(teams)
    team_aliases_by_key = _team_aliases_by_key(output.get("teams", []), teams)
    attributions: dict[str, ClipTeamAttribution] = {}
    for item in output.get("clipAttributions", []):
        if not isinstance(item, dict):
            continue
        clip_ref = clean_text(item.get("clipRef"))
        if clip_ref is None or not re.fullmatch(r"clip_[0-9]+", clip_ref):
            continue
        confidence = clamp(_coerce_float(item.get("confidence"), 0.0), 0.0, 1.0)
        raw_label = clean_text(item.get("label"))
        color_label = resolve_jersey_color(item.get("colorLabel"), raw_label, item.get("teamId"))
        matched_team = _matching_team_alias(item, team_aliases_by_key)
        if matched_team is not None and (color_label is None or color_label == matched_team.colorLabel):
            team_id = matched_team.teamId
            label = matched_team.label
            color_label = matched_team.colorLabel
        else:
            label = color_labeled_team_name(color_label, raw_label) if color_label else raw_label
            raw_team_id = _clean_team_id(item.get("teamId"))
            raw_team_id_color = resolve_jersey_color(raw_team_id)
            team_id = (
                raw_team_id
                if raw_team_id and (color_label is None or raw_team_id_color == color_label)
                else (_team_id_from_label(color_label) if color_label else raw_team_id)
            )
        if team_id is None and label is None and color_label is None:
            continue
        evidence_frame_refs = _valid_evidence_frame_refs(item.get("evidenceFrameRefs"), evidence_frame_refs_by_clip, clip_ref)
        evidence_role_groups = _evidence_role_groups_for_refs(evidence_frame_refs, evidence_frame_roles_by_clip, clip_ref)
        if (
            len(evidence_frame_refs) < TEAM_QUICK_SCAN_MIN_CONFIDENT_EVIDENCE_FRAME_REFS
            or len(evidence_role_groups) < TEAM_QUICK_SCAN_MIN_CONFIDENT_EVIDENCE_ROLE_GROUPS
            or not _has_confident_ownership_evidence(
                labels_by_clip_ref.get(clip_ref) if labels_by_clip_ref is not None else None,
                evidence_frame_refs,
                evidence_frame_roles_by_clip,
                clip_ref,
            )
        ):
            confidence = min(confidence, TEAM_QUICK_SCAN_UNVERIFIED_ATTRIBUTION_MAX_CONFIDENCE)
        confidence = _cap_attribution_confidence_by_detected_team(
            confidence,
            team_id=team_id,
            color_label=color_label,
            label=label,
            team_confidence_by_key=team_confidence_by_key,
        )
        attributions[clip_ref] = ClipTeamAttribution(
            teamId=team_id,
            label=label,
            colorLabel=color_label,
            confidence=round(confidence, 4),
            source="gpt_frame_review",
            evidenceFrameRefs=evidence_frame_refs,
            evidenceRoleGroups=evidence_role_groups,
        )
    return teams, attributions


def _evidence_frame_refs_by_clip(frames: Sequence[QuickScanFrame]) -> dict[str, set[str]]:
    refs_by_clip: dict[str, set[str]] = {}
    for frame in frames:
        if frame.clip_ref is None:
            continue
        refs_by_clip.setdefault(frame.clip_ref, set()).add(frame.frame_ref)
    return refs_by_clip


def _evidence_frame_roles_by_clip(frames: Sequence[QuickScanFrame]) -> dict[str, dict[str, str]]:
    roles_by_clip: dict[str, dict[str, str]] = {}
    for frame in frames:
        if frame.clip_ref is None:
            continue
        roles_by_clip.setdefault(frame.clip_ref, {})[frame.frame_ref] = frame.role
    return roles_by_clip


def _valid_evidence_frame_refs(
    value: object,
    evidence_frame_refs_by_clip: Optional[dict[str, set[str]]],
    clip_ref: str,
) -> list[str]:
    if not isinstance(value, list):
        return []
    allowed_refs = evidence_frame_refs_by_clip.get(clip_ref, set()) if evidence_frame_refs_by_clip is not None else None
    valid_refs: list[str] = []
    seen: set[str] = set()
    for item in value:
        frame_ref = clean_text(item)
        if frame_ref is None or frame_ref in seen:
            continue
        if allowed_refs is not None and frame_ref not in allowed_refs:
            continue
        seen.add(frame_ref)
        valid_refs.append(frame_ref)
    return valid_refs


def _has_confident_evidence_role_diversity(
    evidence_frame_refs: Sequence[str],
    evidence_frame_roles_by_clip: Optional[dict[str, dict[str, str]]],
    clip_ref: str,
) -> bool:
    if evidence_frame_roles_by_clip is None:
        return True
    return len(_evidence_role_groups_for_refs(evidence_frame_refs, evidence_frame_roles_by_clip, clip_ref)) >= TEAM_QUICK_SCAN_MIN_CONFIDENT_EVIDENCE_ROLE_GROUPS


def _has_confident_ownership_evidence(
    label: Optional[str],
    evidence_frame_refs: Sequence[str],
    evidence_frame_roles_by_clip: Optional[dict[str, dict[str, str]]],
    clip_ref: str,
) -> bool:
    if evidence_frame_roles_by_clip is None:
        return True
    roles = {
        normalized
        for frame_ref in evidence_frame_refs
        if (normalized := clean_text(evidence_frame_roles_by_clip.get(clip_ref, {}).get(frame_ref))) is not None
    }
    role_keys = {role.lower() for role in roles}
    normalized_label = (label or "").strip().lower()
    if _is_scoring_or_shot_like_label(normalized_label) and not _is_block_like_label(normalized_label):
        return bool(role_keys & TEAM_QUICK_SCAN_SCORING_OWNERSHIP_ROLES)
    if _is_block_like_label(normalized_label):
        return bool(role_keys & TEAM_QUICK_SCAN_BLOCK_ACTION_ROLES)
    if _is_possession_change_defensive_label(normalized_label):
        return bool(role_keys & TEAM_QUICK_SCAN_POSSESSION_CHANGE_ACTION_ROLES)
    if _is_non_scoring_defensive_label(normalized_label):
        return bool(role_keys & TEAM_QUICK_SCAN_DEFENSIVE_STOP_ACTION_ROLES)
    return True


def _evidence_role_groups_for_refs(
    evidence_frame_refs: Sequence[str],
    evidence_frame_roles_by_clip: Optional[dict[str, dict[str, str]]],
    clip_ref: str,
) -> list[str]:
    if evidence_frame_roles_by_clip is None:
        return []
    roles_by_ref = evidence_frame_roles_by_clip.get(clip_ref, {})
    groups: list[str] = []
    seen: set[str] = set()
    for frame_ref in evidence_frame_refs:
        group = _team_evidence_role_group(roles_by_ref.get(frame_ref))
        if group is None or group in seen:
            continue
        seen.add(group)
        groups.append(group)
    return groups


def _team_evidence_role_group(role: object) -> Optional[str]:
    normalized = clean_text(role)
    if normalized is None:
        return None
    key = normalized.lower()
    if key in {
        "ballhandlersetup",
        "defensesetup",
        "startcontext",
        "prerelease",
        "prechallenge",
        "prepossessionchange",
        "possessionpressure",
    }:
        return "setup"
    if key in {
        "release",
        "shotarc",
        "rimapproach",
        "challenge",
        "balldeflection",
        "possessionchange",
        "ballcontrolchange",
        "eventcenter",
        "midaction",
    }:
        return "action"
    if key in {
        "rimresult",
        "followthrough",
        "finishcontext",
        "defenseoutcome",
        "recovery",
        "aftermath",
    }:
        return "outcome"
    return None


def _team_aliases_by_key(raw_teams: object, teams: Sequence[TeamOption]) -> dict[str, TeamOption]:
    aliases: dict[str, TeamOption] = {}
    if not isinstance(raw_teams, list):
        return aliases
    team_by_id = {team.teamId: team for team in teams}
    for item in raw_teams:
        if not isinstance(item, dict):
            continue
        color_label = resolve_jersey_color(item.get("colorLabel"), item.get("label"), item.get("teamId"))
        if color_label is None:
            continue
        raw_team_id = _clean_team_id(item.get("teamId"))
        raw_team_id_color = resolve_jersey_color(raw_team_id)
        team_id = raw_team_id if raw_team_id_color == color_label else _team_id_from_label(color_label)
        team = team_by_id.get(team_id or "")
        if team is None:
            continue
        for key in (
            team_key(item.get("teamId") if isinstance(item.get("teamId"), str) else None),
            team_key(item.get("label") if isinstance(item.get("label"), str) else None),
            team_key(item.get("colorLabel") if isinstance(item.get("colorLabel"), str) else None),
            team_key(team.teamId),
            team_key(team.label),
            team_key(team.colorLabel),
        ):
            if key is not None:
                aliases[key] = team
    return aliases


def _matching_team_alias(item: dict[str, object], aliases: dict[str, TeamOption]) -> Optional[TeamOption]:
    for key in (
        team_key(item.get("teamId") if isinstance(item.get("teamId"), str) else None),
        team_key(item.get("label") if isinstance(item.get("label"), str) else None),
        team_key(item.get("colorLabel") if isinstance(item.get("colorLabel"), str) else None),
    ):
        if key is not None and key in aliases:
            return aliases[key]
    return None


def _team_confidence_by_key(teams: Sequence[TeamOption]) -> dict[str, float]:
    confidence_by_key: dict[str, float] = {}
    for team in teams:
        for key in (team_key(team.teamId), team_key(team.colorLabel), team_key(team.label)):
            if key is None:
                continue
            confidence_by_key[key] = max(confidence_by_key.get(key, 0.0), team.confidence)
    return confidence_by_key


def _cap_attribution_confidence_by_detected_team(
    confidence: float,
    *,
    team_id: Optional[str],
    color_label: Optional[str],
    label: Optional[str],
    team_confidence_by_key: dict[str, float],
) -> float:
    matched_team_confidence = max(
        (
            team_confidence_by_key[key]
            for key in (team_key(team_id), team_key(color_label), team_key(label))
            if key is not None and key in team_confidence_by_key
        ),
        default=None,
    )
    if matched_team_confidence is None:
        return min(confidence, TEAM_QUICK_SCAN_UNVERIFIED_ATTRIBUTION_MAX_CONFIDENCE)
    return min(confidence, matched_team_confidence)


def _extract_quick_scan_frames(
    source_path: Path,
    duration_seconds: float,
    clips: Sequence[CloudClip],
    settings: Settings,
) -> list[QuickScanFrame]:
    frames: list[QuickScanFrame] = []
    for index, time_seconds in enumerate(_video_sample_times(duration_seconds, int(getattr(settings, "team_quick_scan_video_frame_count", 8)))):
        data_url = _extract_frame_data_url(source_path, time_seconds, settings)
        if data_url:
            frames.append(QuickScanFrame(frame_ref=f"video_{index}", role="videoContext", time_seconds=time_seconds, data_url=data_url))

    frames_per_clip = _quick_scan_frames_per_clip(settings)
    candidate_clip_limit = _max_quick_scan_candidate_clips(settings, len(clips))
    rich_candidate_limit = _rich_quick_scan_candidate_clip_limit(settings, candidate_clip_limit, frames_per_clip)
    max_total_clip_frames = _max_quick_scan_total_clip_frames(settings)
    clip_frame_count = 0
    for index, clip in enumerate(clips[:candidate_clip_limit]):
        per_clip_frame_count = _quick_scan_frames_for_candidate_index(index, frames_per_clip, rich_candidate_limit)
        remaining_clip_frames = max_total_clip_frames - clip_frame_count
        if remaining_clip_frames <= 0:
            break
        for role, time_seconds in _clip_sample_times(clip, min(per_clip_frame_count, remaining_clip_frames)):
            data_url = _extract_frame_data_url(source_path, time_seconds, settings)
            if data_url:
                frame_ref = f"clip_{index}_{role}"
                frames.append(
                    QuickScanFrame(
                        frame_ref=frame_ref,
                        role=role,
                        time_seconds=time_seconds,
                        data_url=data_url,
                        clip_ref=f"clip_{index}",
                    )
                )
                clip_frame_count += 1
    return frames


def _max_quick_scan_candidate_clips(settings: Settings, clip_count: int | None = None) -> int:
    configured = int(getattr(settings, "team_quick_scan_max_candidate_clips", TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS))
    bounded = max(1, min(configured, TEAM_QUICK_SCAN_MAX_CANDIDATE_CLIPS))
    if clip_count is None:
        return bounded
    return max(1, min(bounded, max(1, int(clip_count))))


def _quick_scan_frames_per_clip(settings: Settings) -> int:
    configured = int(getattr(settings, "team_quick_scan_clip_frames_per_clip", TEAM_QUICK_SCAN_MAX_FRAMES_PER_CANDIDATE))
    return max(1, min(configured, TEAM_QUICK_SCAN_MAX_FRAMES_PER_CANDIDATE))


def _max_quick_scan_total_clip_frames(settings: Settings) -> int:
    configured = int(getattr(settings, "team_quick_scan_max_total_clip_frames", TEAM_QUICK_SCAN_DEFAULT_TOTAL_CLIP_FRAMES))
    return max(1, min(configured, TEAM_QUICK_SCAN_MAX_TOTAL_CLIP_FRAMES))


def _rich_quick_scan_candidate_clip_limit(settings: Settings, candidate_clip_limit: int, frames_per_clip: int) -> int:
    configured = int(getattr(settings, "team_quick_scan_rich_candidate_clips", TEAM_QUICK_SCAN_RICH_CANDIDATE_CLIPS))
    configured = max(0, min(configured, candidate_clip_limit))
    compact_frames = _compact_quick_scan_frames_per_clip(frames_per_clip)
    if frames_per_clip <= compact_frames:
        return candidate_clip_limit

    max_total_clip_frames = _max_quick_scan_total_clip_frames(settings)
    available_extra_frames = max_total_clip_frames - (candidate_clip_limit * compact_frames)
    if available_extra_frames <= 0:
        return 0
    max_rich_by_budget = available_extra_frames // max(frames_per_clip - compact_frames, 1)
    return max(0, min(configured, max_rich_by_budget))


def _compact_quick_scan_frames_per_clip(frames_per_clip: int) -> int:
    return min(frames_per_clip, TEAM_QUICK_SCAN_COMPACT_FRAMES_PER_CANDIDATE)


def _quick_scan_frames_for_candidate_index(index: int, frames_per_clip: int, rich_candidate_limit: int) -> int:
    if frames_per_clip <= TEAM_QUICK_SCAN_COMPACT_FRAMES_PER_CANDIDATE:
        return frames_per_clip
    if index < rich_candidate_limit:
        return frames_per_clip
    return _compact_quick_scan_frames_per_clip(frames_per_clip)


def _video_sample_times(duration_seconds: float, count: int) -> list[float]:
    duration = max(duration_seconds, 0.1)
    count = max(1, count)
    times = [duration * (index + 1) / (count + 1) for index in range(count)]
    return _dedupe_times(times, duration)


def _clip_sample_times(clip: CloudClip, count: int) -> list[tuple[str, float]]:
    start = min(clip.startTime, clip.endTime)
    end = max(clip.startTime, clip.endTime)
    duration = max(end - start, 0.001)
    event_center = clip.eventCenter if clip.eventCenter is not None else (start + end) / 2.0
    event_center = min(max(event_center, start), end)
    label = clip.label.strip().lower()
    if _is_block_like_label(label):
        if count >= 8:
            candidates = [
                ("defenseSetup", start + (duration * 0.08)),
                ("preChallenge", max(start, event_center - min(1.0, duration * 0.34))),
                ("challenge", max(start, event_center - min(0.22, duration * 0.08))),
                ("ballDeflection", event_center),
                ("defenseOutcome", min(end, event_center + min(0.28, duration * 0.1))),
                ("recovery", max(event_center, end - (duration * 0.18))),
                ("finishContext", end - (duration * 0.06)),
                ("aftermath", end - (duration * 0.01)),
            ]
        elif count > 4:
            candidates = [
                ("defenseSetup", start + (duration * 0.1)),
                ("preChallenge", max(start, event_center - min(0.8, duration * 0.28))),
                ("challenge", event_center),
                ("defenseOutcome", max(event_center, end - (duration * 0.12))),
                ("recovery", end - (duration * 0.06)),
                ("finishContext", end - (duration * 0.01)),
            ]
        else:
            candidates = [
                ("defenseSetup", start + (duration * 0.16)),
                ("challenge", event_center),
                ("defenseOutcome", max(event_center, end - (duration * 0.12))),
                ("recovery", end - (duration * 0.06)),
            ]
    elif _is_non_scoring_defensive_label(label):
        if count >= 8:
            candidates = [
                ("defenseSetup", start + (duration * 0.08)),
                ("prePossessionChange", max(start, event_center - min(1.0, duration * 0.34))),
                ("possessionPressure", max(start, event_center - min(0.22, duration * 0.08))),
                ("possessionChange", event_center),
                ("ballControlChange", min(end, event_center + min(0.28, duration * 0.1))),
                ("recovery", max(event_center, end - (duration * 0.18))),
                ("defenseOutcome", end - (duration * 0.06)),
                ("finishContext", end - (duration * 0.01)),
            ]
        elif count > 4:
            candidates = [
                ("defenseSetup", start + (duration * 0.1)),
                ("prePossessionChange", max(start, event_center - min(0.8, duration * 0.28))),
                ("possessionChange", event_center),
                ("recovery", max(event_center, end - (duration * 0.12))),
                ("defenseOutcome", end - (duration * 0.06)),
                ("finishContext", end - (duration * 0.01)),
            ]
        else:
            candidates = [
                ("defenseSetup", start + (duration * 0.16)),
                ("possessionChange", event_center),
                ("recovery", max(event_center, end - (duration * 0.12))),
                ("defenseOutcome", end - (duration * 0.06)),
            ]
    elif _is_scoring_or_shot_like_label(label):
        release_offset = min(0.85, duration * 0.28)
        follow_through_offset = min(0.75, duration * 0.2)
        if count >= 8:
            candidates = [
                ("ballHandlerSetup", start + (duration * 0.08)),
                ("preRelease", max(start, event_center - min(1.35, duration * 0.42))),
                ("release", max(start, event_center - release_offset)),
                ("shotArc", max(start, event_center - min(0.45, duration * 0.14))),
                ("rimApproach", max(start, event_center - min(0.22, duration * 0.08))),
                ("rimResult", event_center),
                ("followThrough", min(end, event_center + follow_through_offset)),
                ("finishContext", end - (duration * 0.01)),
            ]
        elif count > 4:
            candidates = [
                ("ballHandlerSetup", start + (duration * 0.1)),
                ("preRelease", max(start, event_center - min(1.35, duration * 0.42))),
                ("release", max(start, event_center - release_offset)),
                ("rimApproach", max(start, event_center - min(0.32, duration * 0.1))),
                ("rimResult", event_center),
                ("followThrough", min(end, event_center + follow_through_offset)),
            ]
        else:
            candidates = [
                ("ballHandlerSetup", start + (duration * 0.16)),
                ("release", max(start, event_center - min(1.05, duration * 0.35))),
                ("rimResult", event_center),
                ("followThrough", min(end, event_center + min(0.65, duration * 0.18))),
            ]
    else:
        candidates = [
            ("startContext", start + (duration * 0.18)),
            ("eventCenter", event_center),
            ("finishContext", end - (duration * 0.12)),
            ("midAction", (start + end) / 2.0),
        ]
    deduped: list[tuple[str, float]] = []
    for role, time_seconds in candidates:
        bounded = min(max(time_seconds, start), end)
        if all(abs(bounded - existing_time) >= 0.18 for _, existing_time in deduped):
            deduped.append((role, round(bounded, 3)))
        if len(deduped) >= max(1, count):
            break
    return deduped


def _is_block_like_label(label: str) -> bool:
    tokens = _label_tokens(label)
    return bool(tokens & {"block", "blocked", "contest"})


def _is_non_scoring_defensive_label(label: str) -> bool:
    tokens = _label_tokens(label)
    if tokens & {"defense", "defensive", "steal", "strip", "pressure", "lockdown"}:
        return True
    if "turnover" in tokens and tokens & {"forced", "force", "defensive", "defense", "steal", "strip"}:
        return True
    return tokens == {"stop"} or "defensive stop" in label or "defense stop" in label


def _is_possession_change_defensive_label(label: str) -> bool:
    tokens = _label_tokens(label)
    if tokens & {"steal", "strip"}:
        return True
    return "turnover" in tokens and tokens & {"forced", "force", "defensive", "defense", "steal", "strip"}


def _is_scoring_or_shot_like_label(label: str) -> bool:
    return any(
        token in label
        for token in (
            "shot",
            "made",
            "make",
            "bucket",
            "basket",
            "layup",
            "dunk",
            "finish",
            "jumper",
            "three",
            "3pt",
        )
    )


def _label_tokens(label: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", label.lower()))


def _dedupe_times(times: Sequence[float], duration_seconds: float) -> list[float]:
    deduped: list[float] = []
    for time_seconds in times:
        bounded = round(min(max(time_seconds, 0.05), max(duration_seconds - 0.05, 0.05)), 3)
        if all(abs(bounded - existing) >= 0.25 for existing in deduped):
            deduped.append(bounded)
    return deduped


def _extract_frame_data_url(source_path: Path, time_seconds: float, settings: Settings) -> Optional[str]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None
    width = int(getattr(settings, "team_quick_scan_frame_width", 720))
    jpeg_quality = int(getattr(settings, "team_quick_scan_jpeg_quality", 4))
    max_bytes = int(getattr(settings, "team_quick_scan_max_image_bytes", 600_000))
    command = [
        ffmpeg,
        "-v",
        "error",
        "-ss",
        f"{max(time_seconds, 0.0):.3f}",
        "-i",
        str(source_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={width}:-2:flags=fast_bilinear",
        "-q:v",
        str(jpeg_quality),
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, check=True, timeout=12)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    image_bytes = completed.stdout or b""
    if not image_bytes or len(image_bytes) > max_bytes:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("ascii")


def _default_responses_client(payload: Dict[str, Any], api_key: str, endpoint: str, timeout_seconds: float) -> Dict[str, Any]:
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_output_text(response_payload: Dict[str, Any]) -> str:
    for item in response_payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                return content["text"]
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str):
        return output_text
    raise ValueError("OpenAI response did not include output text.")


def _clean_text(value: object, max_length: int = 80) -> Optional[str]:
    return clean_text(value, max_length=max_length)


def _clean_team_id(value: object) -> Optional[str]:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    slug = re.sub(r"[^a-z0-9_]+", "_", cleaned.lower()).strip("_")
    if not slug:
        return None
    if not slug.startswith("team_"):
        slug = "team_" + slug
    return slug[:80]


def _team_id_from_label(value: str) -> Optional[str]:
    return _clean_team_id(value)


def _clean_hex_color(value: object) -> Optional[str]:
    cleaned = _clean_text(value, max_length=16)
    if cleaned and re.fullmatch(r"#[0-9a-fA-F]{6}", cleaned):
        return cleaned.lower()
    return None


def _coerce_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
