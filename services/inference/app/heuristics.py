from __future__ import annotations

import math
from dataclasses import dataclass

from .interfaces import CandidateProposer, EventInferencer, Reranker, VideoFeatures
from .models import ActionPrediction, CandidateWindow, EventPrediction, RankedClip


@dataclass
class HeuristicCandidateProposer(CandidateProposer):
    window_seconds: float = 4.5
    stride_seconds: float = 1.5

    def propose(self, features: VideoFeatures) -> list[CandidateWindow]:
        duration = max(features.duration_seconds, 1.0)
        if features.frame_energy_profile:
            return self._from_energy_profile(features)

        windows: list[CandidateWindow] = []
        cursor = 0.0
        index = 0
        while cursor < duration:
            end = min(duration, cursor + self.window_seconds)
            score = 0.45 + 0.05 * math.sin(index)
            windows.append(
                CandidateWindow(
                    candidateId=f"candidate-{index + 1}",
                    startTime=round(cursor, 3),
                    endTime=round(end, 3),
                    score=min(max(score, 0.0), 1.0),
                    source="heuristic",
                    reason="evenly_spaced_bootstrap",
                    metadata={"feature_source": "fallback"},
                )
            )
            cursor += self.stride_seconds
            index += 1
        return windows[:8]

    def _from_energy_profile(self, features: VideoFeatures) -> list[CandidateWindow]:
        duration = max(features.duration_seconds, 1.0)
        frame_count = len(features.frame_energy_profile)
        windows: list[CandidateWindow] = []
        for index, score in enumerate(features.frame_energy_profile):
            if score < 0.25:
                continue
            center = duration * (index / max(frame_count - 1, 1))
            start = max(0.0, center - (self.window_seconds / 2.0))
            end = min(duration, start + self.window_seconds)
            windows.append(
                CandidateWindow(
                    candidateId=f"candidate-{index + 1}",
                    startTime=round(start, 3),
                    endTime=round(end, 3),
                    score=min(max(score, 0.0), 1.0),
                    source="energy_profile",
                    reason="frame_energy_peak",
                    metadata={"energy": score},
                )
            )
        if not windows:
            return self.propose(VideoFeatures(
                source_path=features.source_path,
                duration_seconds=features.duration_seconds,
                fps=features.fps,
                frame_count=features.frame_count,
                metadata=features.metadata,
            ))
        windows.sort(key=lambda item: item.score, reverse=True)
        return windows[:8]


@dataclass
class HeuristicEventInferencer(EventInferencer):
    def infer(self, candidate: CandidateWindow, action: ActionPrediction, features: VideoFeatures) -> EventPrediction:
        label = (action.canonicalLabel or action.label).lower()
        if "dunk" in label:
            event_type, shot_type, make_miss = "finish_at_rim", "dunk", "made"
        elif "layup" in label:
            event_type, shot_type, make_miss = "finish_at_rim", "layup", "made"
        elif "jumper" in label or "three" in label or "shot" in label:
            event_type, shot_type, make_miss = "perimeter_shot", "jumper", "made"
        elif "block" in label:
            event_type, shot_type, make_miss = "defensive_play", "block", "n/a"
        elif "steal" in label:
            event_type, shot_type, make_miss = "defensive_play", "steal", "n/a"
        elif "fast break" in label:
            event_type, shot_type, make_miss = "transition_play", "fast_break", "made"
        elif "miss" in label:
            event_type, shot_type, make_miss = "scoring_play", "jumper", "miss"
        else:
            event_type, shot_type, make_miss = "scoring_play", "jumper", "made"

        rank_score = min(max((candidate.score * 0.45) + (action.confidence * 0.55), 0.0), 1.0)
        should_enable_slow_motion = "dunk" in label
        return EventPrediction(
            eventType=event_type,
            shotType=shot_type,
            makeMiss=make_miss,
            confidence=min(max(action.confidence, 0.0), 1.0),
            rankScore=rank_score,
            shouldAutoKeep=rank_score >= 0.55,
            shouldEnableSlowMotion=should_enable_slow_motion,
            metadata={
                "source_duration": features.duration_seconds,
                "candidate_source": candidate.source,
                "action_label": action.label,
                "canonical_action_label": action.canonicalLabel or action.label,
            },
        )


@dataclass
class ConfidenceReranker(Reranker):
    def rerank(self, clips: list[RankedClip]) -> list[RankedClip]:
        ranked = sorted(clips, key=lambda item: (item.rankScore, item.confidence), reverse=True)
        return [clip.model_copy(update={"metadata": {**clip.metadata, "reranked": True}}) for clip in ranked]
