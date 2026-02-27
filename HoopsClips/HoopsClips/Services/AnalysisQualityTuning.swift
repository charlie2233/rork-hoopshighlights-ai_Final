import Foundation

struct AnalysisWeights: Sendable, Equatable {
    var audio: Double
    var motion: Double
    var pose: Double
    var scene: Double

    static let zero = AnalysisWeights(audio: 0, motion: 0, pose: 0, scene: 0)
}

struct ScorePoint: Sendable, Equatable {
    var time: Double
    var score: Double
}

struct SegmentedClipWindow: Sendable, Equatable {
    var start: Double
    var end: Double
    var peakScore: Double
    var meanScore: Double
}

struct PredictionVote: Sendable, Equatable {
    var label: String
    var confidence: Double
    var recencyWeight: Double
}

enum AnalysisQualityTuning {
    static func normalized(_ weights: AnalysisWeights) -> AnalysisWeights {
        let clamped = AnalysisWeights(
            audio: max(0, weights.audio),
            motion: max(0, weights.motion),
            pose: max(0, weights.pose),
            scene: max(0, weights.scene)
        )
        let sum = clamped.audio + clamped.motion + clamped.pose + clamped.scene
        guard sum > 0 else { return AnalysisWeights(audio: 0.25, motion: 0.25, pose: 0.25, scene: 0.25) }
        return AnalysisWeights(
            audio: clamped.audio / sum,
            motion: clamped.motion / sum,
            pose: clamped.pose / sum,
            scene: clamped.scene / sum
        )
    }

    static func adaptiveWeights(
        base: AnalysisWeights,
        averagePoseCoverage: Double,
        averageBrightness: Double
    ) -> AnalysisWeights {
        var tuned = normalized(base)

        if averagePoseCoverage < 0.45 {
            let poseFactor = max(0.60, averagePoseCoverage / 0.45)
            let originalPose = tuned.pose
            tuned.pose *= poseFactor
            let releasedWeight = max(0, originalPose - tuned.pose)
            tuned.motion += releasedWeight * 0.70
            tuned.audio += releasedWeight * 0.30
        }

        if averageBrightness < 0.35 {
            let sceneFactor = max(0.55, averageBrightness / 0.35)
            let originalScene = tuned.scene
            tuned.scene *= sceneFactor
            let releasedWeight = max(0, originalScene - tuned.scene)
            tuned.motion += releasedWeight * 0.50
            tuned.audio += releasedWeight * 0.50
        }

        return normalized(tuned)
    }

    static func localAverage(values: [Double], center: Int, radius: Int) -> Double {
        guard !values.isEmpty else { return 0.0 }
        let lower = max(0, center - radius)
        let upper = min(values.count - 1, center + radius)
        guard lower <= upper else { return 0.0 }
        let slice = values[lower...upper]
        let sum = slice.reduce(0.0, +)
        return sum / Double(slice.count)
    }

    static func triangularSmooth(points: [ScorePoint], radius: Int) -> [ScorePoint] {
        guard points.count > 1 else { return points }
        let clampedRadius = max(1, radius)
        return points.enumerated().map { index, point in
            var weightedSum = 0.0
            var weightTotal = 0.0
            for offset in -clampedRadius...clampedRadius {
                let candidate = index + offset
                guard candidate >= 0 && candidate < points.count else { continue }
                let weight = Double(clampedRadius + 1 - abs(offset))
                weightedSum += points[candidate].score * weight
                weightTotal += weight
            }
            let smoothed = weightTotal > 0 ? weightedSum / weightTotal : point.score
            return ScorePoint(time: point.time, score: smoothed)
        }
    }

    static func segmentWithHysteresis(
        points: [ScorePoint],
        highThreshold: Double,
        lowThreshold: Double,
        minDuration: Double,
        maxDuration: Double,
        padding: Double,
        durationLimit: Double,
        mergeGap: Double
    ) -> [SegmentedClipWindow] {
        guard !points.isEmpty else { return [] }

        var windows: [SegmentedClipWindow] = []
        var inWindow = false
        var startIndex = 0
        var endIndex = 0
        var peak = 0.0
        var sum = 0.0
        var count = 0

        func closeWindow() {
            guard inWindow, startIndex < points.count, endIndex < points.count else { return }
            let rawStart = points[startIndex].time
            let rawEnd = points[endIndex].time
            var windowStart = max(0, rawStart - padding)
            var windowEnd = min(durationLimit, rawEnd + padding)
            if windowEnd < windowStart {
                swap(&windowStart, &windowEnd)
            }
            let maxBoundedEnd = min(windowStart + maxDuration, durationLimit)
            if windowEnd > maxBoundedEnd {
                windowEnd = maxBoundedEnd
            }
            let duration = windowEnd - windowStart
            guard duration >= minDuration else {
                inWindow = false
                return
            }
            let mean = count > 0 ? sum / Double(count) : peak
            windows.append(
                SegmentedClipWindow(
                    start: windowStart,
                    end: windowEnd,
                    peakScore: min(max(peak, 0), 1),
                    meanScore: min(max(mean, 0), 1)
                )
            )
            inWindow = false
        }

        for (index, point) in points.enumerated() {
            if !inWindow {
                if point.score >= highThreshold {
                    inWindow = true
                    startIndex = index
                    endIndex = index
                    peak = point.score
                    sum = point.score
                    count = 1
                }
                continue
            }

            if point.score >= lowThreshold {
                endIndex = index
                peak = max(peak, point.score)
                sum += point.score
                count += 1
            } else {
                closeWindow()
            }
        }
        closeWindow()

        guard windows.count > 1 else { return windows }

        let sorted = windows.sorted { $0.start < $1.start }
        var merged: [SegmentedClipWindow] = [sorted[0]]
        for window in sorted.dropFirst() {
            guard var last = merged.last else {
                merged.append(window)
                continue
            }
            if window.start <= last.end + mergeGap {
                let mergedDuration = max(window.end, last.end) - min(window.start, last.start)
                let boundedEnd = min(min(window.start, last.start) + maxDuration, durationLimit)
                last.start = min(window.start, last.start)
                last.end = min(max(window.end, last.end), boundedEnd)
                last.peakScore = max(last.peakScore, window.peakScore)
                let mergedMean = (last.meanScore + window.meanScore) / 2.0
                last.meanScore = mergedDuration > 0 ? mergedMean : last.meanScore
                merged[merged.count - 1] = last
            } else {
                merged.append(window)
            }
        }
        return merged
    }

    static func weightedWinningLabel(
        votes: [PredictionVote],
        minCount: Int,
        minMargin: Double
    ) -> String? {
        guard !votes.isEmpty else { return nil }
        var weightedScores: [String: Double] = [:]
        var counts: [String: Int] = [:]

        for vote in votes where vote.confidence > 0 {
            let recency = max(0.6, vote.recencyWeight)
            let score = vote.confidence * recency
            weightedScores[vote.label, default: 0] += score
            counts[vote.label, default: 0] += 1
        }

        let ranked = weightedScores.sorted { $0.value > $1.value }
        guard let top = ranked.first else { return nil }
        guard (counts[top.key] ?? 0) >= minCount else { return nil }

        let runnerUpScore = ranked.count > 1 ? ranked[1].value : 0.0
        let margin = top.value > 0 ? (top.value - runnerUpScore) / top.value : 0.0
        guard margin >= minMargin else { return nil }

        return top.key
    }
}
