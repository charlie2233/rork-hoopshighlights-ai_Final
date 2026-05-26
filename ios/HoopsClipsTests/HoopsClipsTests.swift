//
//  HoopsClipsTests.swift
//  HoopsClipsTests
//
//  Created by Rork on February 25, 2026.
//

import Testing
import Foundation
import CoreML
import Vision
@testable import HoopsClips

struct HoopsClipsTests {

    // Test removed because it relies on local JSON files that were cleaned up
    // @Test func testModelPipelineWithLayupJson() async throws { ... }

    @Test func testHeuristicFallback() async {
        // Prepare a Clip that should trigger "Posterize" or "Dunk" via heuristics
        // Heuristic: maxPose > 0.7 && maxMotion > 0.6
        // If audioScore > 0.7 -> Dunk, else Posterize
        
        let startTime = 0.0
        let endTime = 3.0
        let clip = Clip(
            startTime: startTime,
            endTime: endTime,
            action: .unknown,
            confidence: 0.8,
            isKept: true,
            label: "Test Clip",
            audioScore: 0.8, // Should trigger Dunk
            visualScore: 0.8,
            motionScore: 0.8,
            combinedScore: 0.8
        )
        
        // Prepare FrameScores
        // We need frames within start/end time
        var frames: [FrameScore] = []
        for i in 0..<30 {
            let time = Double(i) * 0.1
            // High pose and motion scores
            let frame = FrameScore(
                timestamp: time,
                poseScore: 0.8,
                motionScore: 0.7,
                sceneScore: 0.5,
                poseCoverage: 0.8,
                brightness: 0.5,
                audioBurst: 0.8,
                observation: nil // No observation, so predictAction will return nil/fail
            )
            frames.append(frame)
        }
        
        let service = await VideoAnalysisService()
        
        // Call classifyActions (now internal)
        let classifiedClips = await service.classifyActions(clips: [clip], frameScores: frames)
        
        #expect(classifiedClips.count == 1)
        let result = classifiedClips.first!
        
        print("Classified Action: \(result.action.rawValue)")
        
        // Check if fallback worked
        // Should be .dunk because audioScore (0.8) > 0.7 and pose/motion are high
        #expect(result.action == .dunk)
        #expect(result.label == "Dunk")
        
        // Test another case: Made Shot
        // Heuristic: maxPose > 0.5 && avgMotion > 0.5 && duration > 4.0 -> Made Shot
        
        let longClip = Clip(
            startTime: 0.0,
            endTime: 5.0,
            action: .unknown,
            confidence: 0.6,
            isKept: true,
            label: "Test Long Clip",
            audioScore: 0.2,
            visualScore: 0.6,
            motionScore: 0.6,
            combinedScore: 0.6
        )
        
        var longFrames: [FrameScore] = []
        for i in 0..<50 {
            let time = Double(i) * 0.1
            let frame = FrameScore(
                timestamp: time,
                poseScore: 0.5,
                motionScore: 0.45,
                sceneScore: 0.5,
                poseCoverage: 0.5,
                brightness: 0.5,
                audioBurst: 0.2,
                observation: nil
            )
            longFrames.append(frame)
        }
        
        let classifiedLong = await service.classifyActions(clips: [longClip], frameScores: longFrames)
        let resultLong = classifiedLong.first!
        
        print("Classified Action Long: \(resultLong.action.rawValue)")
        #expect(resultLong.action == .madeShot)
    }

    @Test func testAdaptiveWeightsRebalance() {
        let base = AnalysisWeights(audio: 0.15, motion: 0.35, pose: 0.35, scene: 0.15)
        let tuned = AnalysisQualityTuning.adaptiveWeights(
            base: base,
            averagePoseCoverage: 0.20,
            averageBrightness: 0.20
        )

        let sum = tuned.audio + tuned.motion + tuned.pose + tuned.scene
        #expect(abs(sum - 1.0) < 0.0001)
        #expect(tuned.pose < base.pose)
        #expect(tuned.scene < base.scene)
        #expect(tuned.motion > base.motion)
    }

    @Test func testHysteresisSegmentationAvoidsFragmentation() {
        let points: [ScorePoint] = [
            .init(time: 0.0, score: 0.20),
            .init(time: 1.0, score: 0.62),
            .init(time: 2.0, score: 0.54),
            .init(time: 3.0, score: 0.51),
            .init(time: 4.0, score: 0.18),
            .init(time: 5.0, score: 0.64),
            .init(time: 6.0, score: 0.55),
            .init(time: 7.0, score: 0.12)
        ]

        let windows = AnalysisQualityTuning.segmentWithHysteresis(
            points: points,
            highThreshold: 0.60,
            lowThreshold: 0.50,
            minDuration: 1.5,
            maxDuration: 10.0,
            padding: 0.2,
            durationLimit: 8.0,
            mergeGap: 1.8
        )

        #expect(windows.count == 1)
        #expect(windows[0].peakScore >= 0.62)
    }

    @Test func testWeightedWinningLabelPrefersStrongSignal() {
        let votes: [PredictionVote] = [
            .init(label: "Dunk", confidence: 0.91, recencyWeight: 1.2),
            .init(label: "Dunk", confidence: 0.82, recencyWeight: 1.1),
            .init(label: "Layup", confidence: 0.40, recencyWeight: 1.0),
            .init(label: "Layup", confidence: 0.39, recencyWeight: 0.9),
            .init(label: "Layup", confidence: 0.36, recencyWeight: 0.8)
        ]

        let winner = AnalysisQualityTuning.weightedWinningLabel(
            votes: votes,
            minCount: 2,
            minMargin: 0.10
        )

        #expect(winner == "Dunk")
    }

    @Test func testSocialShortcutsCoverCommonShareTargets() {
        let shortcutIDs = Set(SocialAppSupport.defaultShortcuts.map(\.id))

        #expect(shortcutIDs.isSuperset(of: [
            "instagram",
            "tiktok",
            "youtube",
            "snapchat",
            "whatsapp",
            "facebook",
            "x"
        ]))
    }

    @Test func testEditorShortcutsCoverCommonEditingTargets() {
        let shortcutIDs = Set(EditorAppSupport.defaultShortcuts.map(\.id))

        #expect(shortcutIDs.isSuperset(of: [
            "adobe",
            "capcut",
            "imovie",
            "vn",
            "lumafusion",
            "splice",
            "final-cut-camera"
        ]))
    }

    @Test func testCloudEditPresetsExposeExpectedAspectRatiosAndDurations() {
        #expect(CloudEditPreset.personalHighlight.aspectRatio == .vertical)
        #expect(CloudEditPreset.personalHighlight.durationOptions == [15, 30, 45])
        #expect(CloudEditPreset.fullGameHighlight.aspectRatio == .widescreen)
        #expect(CloudEditPreset.fullGameHighlight.durationOptions == [60, 90, 120])
        #expect(CloudEditPreset.coachReview.aspectRatio == .widescreen)
        #expect(CloudEditPreset.coachReview.durationOptions == [60, 120, 180])
    }

    @Test func testCloudEditPolicySummaryExposesFreemiumCopy() {
        let free = CloudEditPolicySummary.freeDefault
        let pro = CloudEditPolicySummary.proDefault

        #expect(free.planTier.isFree)
        #expect(!pro.planTier.isFree)
        #expect(free.queueTitle == "Standard render queue")
        #expect(pro.queueTitle == "Priority render")
        #expect(free.brandingSummary.contains("watermark/outro"))
        #expect(pro.brandingSummary.contains("Clean export"))
        #expect(free.planLimitRows.contains("720p max export"))
        #expect(free.maxDailyRenders == 3)
        #expect(free.planLimitRows.contains("3 AI edits/day"))
        #expect(AppConstants.cloudAnalysisDailyQuota == 3)
        #expect(pro.planLimitRows.contains("1080p max export"))
        #expect(free.retentionSummary == "Videos stored for 14 days")
        #expect(pro.retentionSummary == "Videos stored for 60 days")
    }

    @Test @MainActor func testCloudEditRequestEncodesOptionalUserPrompt() throws {
        let nativeSignals = NativeShotSignals(
            isShotLike: true,
            leadInSeconds: 2.5,
            followThroughSeconds: 1.5,
            setupContextScore: 1.0,
            outcomeContextScore: 1.0,
            eventCenterQuality: 0.92,
            contextQualityScore: 0.9,
            timingWindowOk: true,
            outcome: "made",
            outcomeConfidence: 0.8
        )
        let request = CreateCloudEditJobRequest(
            videoId: "video_123",
            analysisJobId: "analysis_123",
            installId: "install-123",
            sourceObjectKey: "uploads/source.mp4",
            preset: CloudEditPreset.personalHighlight.rawValue,
            templateId: CloudEditPreset.personalHighlight.templateID,
            targetDurationSeconds: 30,
            aspectRatio: .vertical,
            planTier: .free,
            revenueCatAppUserID: nil,
            userPrompt: "Make it more hype and focus on defense.",
            clips: [
                CloudEditCandidateClip(
                    id: "clip_1",
                    start: 0,
                    end: 6,
                    eventCenter: 3,
                    label: "Fast Break",
                    confidence: 0.9,
                    excitement: 0.9,
                    watchability: 0.88,
                    motionScore: 0.87,
                    audioPeak: 0.5,
                    combinedScore: 0.9,
                    duplicateGroup: nil,
                    nativeShotSignals: nativeSignals
                )
            ]
        )

        let data = try JSONEncoder().encode(request)
        let payload = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])

        #expect(payload["userPrompt"] as? String == "Make it more hype and focus on defense.")
        #expect(payload["sourceObjectKey"] as? String == "uploads/source.mp4")
        let clips = try #require(payload["clips"] as? [[String: Any]])
        let encodedSignals = try #require(clips.first?["nativeShotSignals"] as? [String: Any])
        #expect(encodedSignals["outcome"] as? String == "made")
        #expect(encodedSignals["timingWindowOk"] as? Bool == true)
    }

    @Test @MainActor func testCloudEditRequestSendsStrongestCandidatesBeforeThirtyClipCap() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        var clips: [Clip] = []
        for index in 0..<31 {
            let isStrongCandidate = index == 30
            let startTime = Double(index * 10)
            clips.append(
                Clip(
                    startTime: startTime,
                    endTime: startTime + 6,
                    action: .madeShot,
                    confidence: isStrongCandidate ? 0.98 : 0.42,
                    isKept: true,
                    label: "Made Shot",
                    audioScore: isStrongCandidate ? 0.92 : 0.1,
                    visualScore: isStrongCandidate ? 0.95 : 0.2,
                    motionScore: isStrongCandidate ? 0.95 : 0.2,
                    combinedScore: isStrongCandidate ? 0.99 : 0.15,
                    detectionMethod: .cloud
                )
            )
        }
        viewModel.analysisService.clips = clips

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )
        let candidateStarts = request.clips.map(\.start)

        #expect(request.clips.count == 30)
        #expect(candidateStarts.contains(300.0))
        #expect(!candidateStarts.contains(290.0))
    }

    @Test func testCloudEditCandidateRankingPrefersCompleteShotContextOverLatePreBasketWindow() {
        let preBasketOnly = Clip(
            startTime: 10.0,
            endTime: 16.0,
            eventCenter: 10.1,
            action: .madeShot,
            confidence: 0.99,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.95,
            visualScore: 0.95,
            motionScore: 0.95,
            combinedScore: 0.99,
            detectionMethod: .cloud
        )
        let completeShot = Clip(
            startTime: 20.0,
            endTime: 26.0,
            eventCenter: 23.0,
            action: .madeShot,
            confidence: 0.78,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.55,
            visualScore: 0.7,
            motionScore: 0.72,
            combinedScore: 0.72,
            detectionMethod: .cloud
        )

        let ranked = HighlightsViewModel.rankedCloudEditCandidateClips(
            from: [preBasketOnly, completeShot],
            limit: 1
        )

        #expect(ranked.first?.startTime == 20.0)
    }

    @Test func testCloudEditProTemplatesAreRealAndDistinct() {
        let templates = CloudEditProTemplate.allCases
        let identifiers = templates.map(\.accessibilityIdentifier)

        #expect(templates.count == 4)
        #expect(Set(identifiers).count == templates.count)
        #expect(templates.map(\.title).contains("Recruiting Reel Pro"))
        #expect(templates.map(\.title).contains("Cinematic Mixtape Pro"))
        #expect(templates.map(\.title).contains("NBA Recap Pro"))
        #expect(templates.map(\.title).contains("Team Highlight Pro"))
        #expect(templates.allSatisfy { $0.accessibilityIdentifier.hasPrefix("export.aiEdit.proTemplate.") })
        #expect(identifiers.contains("export.aiEdit.proTemplate.recruitingReel"))
        #expect(identifiers.contains("export.aiEdit.proTemplate.cinematicMixtape"))
        #expect(identifiers.contains("export.aiEdit.proTemplate.nbaRecap"))
        #expect(identifiers.contains("export.aiEdit.proTemplate.teamHighlight"))
        #expect(CloudEditProTemplate.recruitingReelPro.templateID == "recruiting_reel_pro_v1")
        #expect(CloudEditProTemplate.cinematicMixtapePro.templateID == "cinematic_mixtape_pro_v1")
        #expect(CloudEditProTemplate.nbaRecapPro.preset == .fullGameHighlight)
        #expect(CloudEditProTemplate.teamHighlightPro.durationOptions == [90, 120, 180])
    }

    @Test func testCloudEditProUXFlagsDefaultToVisibleButNonPaymentUX() {
        let flags = CloudEditProUXFlags.safeDefault

        #expect(flags.proUpsellEnabled)
        #expect(flags.proTemplatesEnabled)
        #expect(flags.priorityQueueEnabled)
        #expect(flags.cloudLockerEnabled)
    }

    @Test @MainActor func testCloudEditVersionFlagsDecodeLiveRenderKillSwitch() throws {
        let payload = """
        {
          "service": "hoopclips-editing",
          "backendModelVersion": "editing-cloud-v1",
          "gitSha": "test-sha",
          "featureFlags": {
            "aiEditEnabled": true,
            "aiEditLiveRenderEnabled": false,
            "aiEditRevisionEnabled": true,
            "aiEditTemplatePackEnabled": true,
            "aiEditMaxDailyRenders": 3,
            "aiEditFreeWatermarkRequired": true,
            "aiEditProExportsEnabled": false,
            "gptHighlightRerankerEnabled": true
          }
        }
        """.data(using: .utf8)!

        let response = try JSONDecoder().decode(CloudEditVersionResponse.self, from: payload)

        #expect(response.service == "hoopclips-editing")
        #expect(response.featureFlags?.allowsEditPlanning == true)
        #expect(response.featureFlags?.allowsLiveRendering == false)
        #expect(response.featureFlags?.allowsRevisions == true)
        #expect(response.featureFlags?.allowsTemplatePacks == true)
        #expect(response.featureFlags?.aiEditMaxDailyRenders == 3)
        #expect(response.featureFlags?.gptHighlightRerankerEnabled == true)
    }

    @Test func testCloudEditKillSwitchErrorsHaveFriendlyMessages() {
        #expect(CloudEditError.friendlyBackendMessage(code: "ai_edit_disabled", fallback: "fallback").contains("paused"))
        let liveRenderDisabled = CloudEditError.friendlyBackendMessage(code: "ai_edit_live_render_disabled", fallback: "fallback")
        #expect(liveRenderDisabled.contains("temporarily paused"))
        #expect(liveRenderDisabled.contains("cloud"))
        #expect(!liveRenderDisabled.localizedCaseInsensitiveContains("local render"))
        #expect(!liveRenderDisabled.localizedCaseInsensitiveContains("fallback"))
        #expect(CloudEditError.friendlyBackendMessage(code: "ai_edit_revision_disabled", fallback: "fallback").contains("revisions"))
        #expect(CloudEditError.friendlyBackendMessage(code: "ai_edit_template_pack_disabled", fallback: "fallback").contains("Template packs"))
    }

    @Test func testBundledMusicTracksHaveUniqueFilenames() {
        let filenames = MusicTrack.allCases.compactMap(\.filename)

        #expect(MusicTrack.allCases.count >= 17)
        #expect(filenames.count == Set(filenames).count)
        #expect(filenames.contains("arena_bounce.m4a"))
        #expect(filenames.contains("fast_break.m4a"))
        #expect(filenames.contains("halftime_funk.m4a"))
        #expect(filenames.contains("clutch_time.m4a"))
        #expect(filenames.contains("real_lofi_court.m4a"))
        #expect(filenames.contains("real_upbeat_warmup.m4a"))
        #expect(filenames.contains("real_the_rush.m4a"))
        #expect(filenames.contains("real_hiphop_theme.m4a"))
        #expect(filenames.contains("real_atmospheric_drive.m4a"))
        #expect(filenames.contains("retro_arcade.m4a"))
        #expect(filenames.contains("victory_lap.m4a"))

        for filename in filenames {
            let splitName = (filename as NSString).deletingPathExtension
            let splitExtension = (filename as NSString).pathExtension
            let resourceURL = Bundle.main.url(forResource: filename, withExtension: nil)
                ?? Bundle.main.url(forResource: filename, withExtension: nil, subdirectory: "Resources/Audio")
                ?? Bundle.main.url(forResource: splitName, withExtension: splitExtension)
                ?? Bundle.main.url(forResource: splitName, withExtension: splitExtension, subdirectory: "Resources/Audio")

            #expect(resourceURL != nil, "Missing bundled audio resource: \(filename)")
        }
    }

    @Test func testCloudClipMappingPreservesCloudMetadata() {
        let nativeSignals = NativeShotSignals(
            isShotLike: true,
            leadInSeconds: 2.7,
            followThroughSeconds: 1.8,
            setupContextScore: 1.0,
            outcomeContextScore: 1.0,
            eventCenterQuality: 0.96,
            contextQualityScore: 0.94,
            timingWindowOk: true,
            outcome: "made",
            outcomeConfidence: 0.82
        )
        let cloudClip = CloudClip(
            startTime: 12.5,
            endTime: 17.0,
            eventCenter: 15.2,
            confidence: 0.91,
            label: "Dunk",
            action: "Dunk",
            audioScore: 0.8,
            visualScore: 0.7,
            motionScore: 0.9,
            combinedScore: 0.86,
            detectionMethod: "Cloud",
            shouldAutoKeep: true,
            shouldEnableSlowMotion: true,
            nativeShotSignals: nativeSignals
        )

        let mapped = cloudClip.makeClip()

        #expect(mapped.action == .dunk)
        #expect(mapped.detectionMethod == .cloud)
        #expect(mapped.isKept)
        #expect(mapped.isSlowMotionEnabled)
        #expect(abs(mapped.duration - 4.5) < 0.001)
        #expect(mapped.eventCenter == 15.2)
        #expect(mapped.nativeShotSignals == nativeSignals)
    }

    @Test func testCloudJobResponseDecodesNestedResults() throws {
        let payload = """
        {
          "jobId": "job-123",
          "status": "succeeded",
          "progress": 1.0,
          "stage": "Finalizing clips",
          "errorCode": null,
          "errorMessage": null,
          "analysisVersion": "v1",
          "results": {
            "clipCount": 1,
            "clips": [
              {
                "startTime": 1.2,
                "endTime": 4.6,
                "eventCenter": 3.8,
                "confidence": 0.88,
                "label": "Three Pointer",
                "action": "Three Pointer",
                "audioScore": 0.7,
                "visualScore": 0.6,
                "motionScore": 0.65,
                "combinedScore": 0.74,
                "detectionMethod": "cloud",
                "shouldAutoKeep": true,
                "shouldEnableSlowMotion": false
              }
            ],
            "diagnostics": {
              "processingMs": 18250,
              "backendModelVersion": "cloud-v1",
              "usedVideoIntelligence": false,
              "usedGeminiRelabeling": false,
              "candidateSegments": 4,
              "finalSegments": 1
            }
          }
        }
        """

        let decoder = JSONDecoder()
        let response = try decoder.decode(CloudAnalysisJobResponse.self, from: Data(payload.utf8))

        #expect(response.status == "succeeded")
        #expect(response.results?.clipCount == 1)
        #expect(response.results?.clips.first?.label == "Three Pointer")
        #expect(response.results?.clips.first?.eventCenter == 3.8)
        #expect(response.results?.diagnostics.backendModelVersion == "cloud-v1")
    }

    @Test @MainActor func testCloudEditRenderStatusDecodesAIWorkTimelineAndReceipt() throws {
        let payload = """
        {
          "editJobId": "edit_123",
          "revisionId": "rev_456",
          "renderJobId": "render_789",
          "renderer": "cloud_ffmpeg",
          "rendererVersion": "ffmpeg-renderer-v1",
          "planVersion": "edit-plan-v1",
          "status": "rendered",
          "outputObjectKey": "edits/edit_123/render_jobs/render_789/final.mp4",
          "renderLogObjectKey": "edits/edit_123/render_jobs/render_789/render_log.json",
          "durationSeconds": 15.4,
          "aspectRatio": "9:16",
          "traceId": "trace_123",
          "failureReason": null,
          "validationErrors": [],
          "planTier": "free",
          "policy": {
            "planTier": "free",
            "displayName": "Free",
            "maxRenderSeconds": 45,
            "maxDailyRenders": 3,
            "maxActiveRenders": 1,
            "maxRevisionsPerEdit": 3,
            "maxOutputResolution": "720p",
            "watermarkRequired": true,
            "outroRequired": true,
            "premiumTemplatesAllowed": false,
            "renderRetentionDays": 14
          },
          "retryCount": 0,
          "outputBytes": 123456,
          "retentionMetadata": {
            "expiresAt": "2026-05-31T00:00:00Z",
            "retentionClass": "free_final_render",
            "deleteEligible": true,
            "planTier": "free",
            "editJobId": "edit_123",
            "renderJobId": "render_789",
            "templateId": "personal_highlight_v1",
            "outputBytes": 123456,
            "durationSeconds": 15.4
          },
          "workTimeline": {
            "editJobId": "edit_123",
            "revisionId": "rev_456",
            "renderJobId": "render_789",
            "status": "rendered",
            "generatedAt": "2026-05-16T00:00:00Z",
            "steps": [
              {
                "stepId": "selecting_best_clips",
                "title": "Selecting strongest clips",
                "detail": "Selected 2 clips from 3 candidates.",
                "status": "complete",
                "startedAt": null,
                "completedAt": null
              }
            ]
          },
          "workReceipt": {
            "editJobId": "edit_123",
            "revisionId": "rev_456",
            "renderJobId": "render_789",
            "selectedClipCount": 2,
            "candidateClipCount": 3,
            "templateId": "personal_highlight_v1",
            "templateName": "Personal Highlight",
            "slowMotionMomentCount": 1,
            "outputDurationSeconds": 15.4,
            "outputResolution": "720p",
            "aspectRatio": "9:16",
            "watermarkIncluded": true,
            "outroIncluded": true,
            "storageExpiresAt": "2026-05-31T00:00:00Z",
            "planTier": "free",
            "priorityQueue": false,
            "summaryRows": [
              "Selected 2 clips from 3 candidates.",
              "Applied Personal Highlight template."
            ]
          }
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let response = try decoder.decode(CloudEditRenderStatusResponse.self, from: Data(payload.utf8))

        #expect(response.status == .rendered)
        #expect(response.workTimeline?.steps.first?.stepId == "selecting_best_clips")
        #expect(response.workTimeline?.steps.first?.status == .complete)
        #expect(response.workReceipt?.selectedClipCount == 2)
        #expect(response.workReceipt?.templateName == "Personal Highlight")
        #expect(response.workReceipt?.summaryRows.count == 2)
    }

    @Test func testAudioFallbackSplitsContinuousSignalIntoBoundedClips() async {
        let service = await VideoAnalysisService()
        let peaks = [Double](repeating: 1.0, count: 600)

        let clips = await service.buildAudioOnlyClips(audioPeaks: peaks, duration: 60.0)

        #expect(!clips.isEmpty)
        #expect(clips.count > 1)
        #expect(clips.allSatisfy { $0.duration <= AnalysisSettings().maxClipDuration + 0.001 })
        #expect(clips.allSatisfy { $0.endTime <= 60.0 && $0.startTime >= 0.0 })
    }

    @Test func testAudioFallbackCentersSingleBurst() async {
        let service = await VideoAnalysisService()
        var peaks = [Double](repeating: 0.0, count: 300)
        peaks[120] = 1.0
        peaks[121] = 0.8

        let clips = await service.buildAudioOnlyClips(audioPeaks: peaks, duration: 30.0)

        #expect(clips.count == 1)
        #expect(clips[0].duration <= AnalysisSettings().maxClipDuration + 0.001)
        #expect(abs(clips[0].startTime - 9.0) < 1.0)
        #expect(abs(clips[0].endTime - 15.0) < 1.0)
    }

    @Test func testAudioFallbackSeparatesSparseBursts() async {
        let service = await VideoAnalysisService()
        var peaks = [Double](repeating: 0.0, count: 600)
        peaks[50] = 1.0
        peaks[250] = 0.95
        peaks[450] = 0.9

        let clips = await service.buildAudioOnlyClips(audioPeaks: peaks, duration: 60.0)

        #expect(clips.count == 3)
        #expect(clips[0].startTime < clips[1].startTime)
        #expect(clips[1].startTime < clips[2].startTime)
        #expect(clips.allSatisfy { $0.duration <= AnalysisSettings().maxClipDuration + 0.001 })
    }

    @Test func testNormalizeOverlongHeuristicClipSplitsIt() async {
        let service = await VideoAnalysisService()
        let original = Clip(
            startTime: 0.0,
            endTime: 60.0,
            confidence: 0.78,
            isKept: true,
            label: "Action",
            audioScore: 0.8,
            visualScore: 0.2,
            motionScore: 0.3,
            combinedScore: 0.7,
            detectionMethod: .heuristic
        )

        let normalized = await service.normalizeDetectedClips([original], duration: 60.0)

        #expect(!normalized.isEmpty)
        #expect(normalized.count <= 3)
        #expect(normalized.allSatisfy { $0.duration <= AnalysisSettings().maxClipDuration + 0.001 })
        #expect(normalized.allSatisfy { $0.endTime - $0.startTime < 60.0 })
    }

    @Test func testNormalizeOverlongCloudClipSplitsIt() async {
        let service = await VideoAnalysisService()
        let original = Clip(
            startTime: 2.0,
            endTime: 58.0,
            action: .dunk,
            confidence: 0.91,
            isKept: true,
            label: "Dunk",
            audioScore: 0.8,
            visualScore: 0.7,
            motionScore: 0.9,
            combinedScore: 0.88,
            detectionMethod: .cloud
        )

        let normalized = await service.normalizeDetectedClips([original], duration: 60.0)

        #expect(!normalized.isEmpty)
        #expect(normalized.allSatisfy { $0.detectionMethod == .cloud })
        #expect(normalized.allSatisfy { $0.duration <= AnalysisSettings().maxClipDuration + 0.001 })
    }

    @Test func testNormalizeOverlongCloudClipCentersSplitOnEventCenter() async throws {
        let service = await VideoAnalysisService()
        let original = Clip(
            startTime: 2.0,
            endTime: 58.0,
            eventCenter: 45.0,
            action: .madeShot,
            confidence: 0.91,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.8,
            visualScore: 0.7,
            motionScore: 0.9,
            combinedScore: 0.88,
            detectionMethod: .cloud
        )

        let normalized = await service.normalizeDetectedClips([original], duration: 60.0)
        let eventClip = try #require(normalized.first)
        let eventCenter = try #require(eventClip.eventCenter)

        #expect(normalized.count == 1)
        #expect(abs(eventCenter - 45.0) < 0.001)
        #expect(eventClip.startTime < eventCenter)
        #expect(eventClip.endTime > eventCenter)
        #expect(eventClip.duration <= AnalysisSettings().maxClipDuration + 0.001)
    }

    @Test func testNormalizeClampsEventCenterInsideClipBounds() async throws {
        let service = await VideoAnalysisService()
        let original = Clip(
            startTime: 10.0,
            endTime: 18.0,
            eventCenter: 30.0,
            action: .madeShot,
            confidence: 0.72,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.4,
            visualScore: 0.5,
            motionScore: 0.5,
            combinedScore: 0.6,
            detectionMethod: .cloud
        )

        let normalized = await service.normalizeDetectedClips([original], duration: 60.0)
        let center = try #require(normalized.first?.eventCenter)

        #expect(normalized.count == 1)
        #expect(abs(center - 18.0) < 0.001)
    }

    @Test func testNormalizeKeepsValidClipUntouched() async {
        let service = await VideoAnalysisService()
        let original = Clip(
            startTime: 10.0,
            endTime: 18.0,
            action: .madeShot,
            confidence: 0.72,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.4,
            visualScore: 0.5,
            motionScore: 0.5,
            combinedScore: 0.6,
            detectionMethod: .ml
        )

        let normalized = await service.normalizeDetectedClips([original], duration: 60.0)

        #expect(normalized.count == 1)
        #expect(abs(normalized[0].startTime - original.startTime) < 0.001)
        #expect(abs(normalized[0].endTime - original.endTime) < 0.001)
        #expect(normalized[0].detectionMethod == .ml)
    }

    @Test func testTargetHighlightDurationCapsDefaultAutoKeptClips() async {
        let service = await VideoAnalysisService()
        var settings = AnalysisSettings()
        settings.targetHighlightDuration = 18.0
        await service.updateSettings(settings)

        let result = CloudAnalysisResult(
            analysisJobId: "analysis_test",
            sourceObjectKey: "uploads/test/source.mp4",
            clipCount: 3,
            clips: [
                CloudClip(
                    startTime: 0.0,
                    endTime: 8.0,
                    eventCenter: nil,
                    confidence: 0.92,
                    label: "Dunk",
                    action: "Dunk",
                    audioScore: 0.9,
                    visualScore: 0.7,
                    motionScore: 0.8,
                    combinedScore: 0.9,
                    detectionMethod: "Cloud",
                    shouldAutoKeep: true,
                    shouldEnableSlowMotion: true
                ),
                CloudClip(
                    startTime: 12.0,
                    endTime: 20.0,
                    eventCenter: nil,
                    confidence: 0.88,
                    label: "Three Pointer",
                    action: "Three Pointer",
                    audioScore: 0.7,
                    visualScore: 0.6,
                    motionScore: 0.7,
                    combinedScore: 0.8,
                    detectionMethod: "Cloud",
                    shouldAutoKeep: true,
                    shouldEnableSlowMotion: false
                ),
                CloudClip(
                    startTime: 24.0,
                    endTime: 32.0,
                    eventCenter: nil,
                    confidence: 0.84,
                    label: "Made Shot",
                    action: "Made Shot",
                    audioScore: 0.6,
                    visualScore: 0.6,
                    motionScore: 0.6,
                    combinedScore: 0.7,
                    detectionMethod: "Cloud",
                    shouldAutoKeep: true,
                    shouldEnableSlowMotion: false
                )
            ],
            diagnostics: CloudDiagnostics(
                processingMs: 1200,
                backendModelVersion: "test",
                usedVideoIntelligence: false,
                usedGeminiRelabeling: false,
                candidateSegments: 3,
                finalSegments: 3
            )
        )

        await service.applyCloudAnalysis(result, duration: 60.0)
        let clips = await service.clips
        let kept = clips.filter(\.isKept)

        #expect(clips.count == 3)
        #expect(kept.count == 2)
        #expect(kept.reduce(0.0) { $0 + $1.duration } <= settings.targetHighlightDuration + 0.001)
    }

    @Test func testDefaultRedundantSuppressionPrefersHigherScoreWhenClipsOverlap() {
        let weaker = Clip(
            startTime: 10.8,
            endTime: 14.8,
            action: .dunk,
            confidence: 0.84,
            isKept: true,
            label: "Dunk B",
            combinedScore: 0.81
        )
        let stronger = Clip(
            startTime: 10.0,
            endTime: 14.0,
            action: .dunk,
            confidence: 0.92,
            isKept: true,
            label: "Dunk A",
            combinedScore: 0.93
        )

        let result = defaultRedundantClipSuppressedClips(from: [weaker, stronger])

        #expect(result.count == 2)
        #expect(!result[0].isKept)
        #expect(result[1].isKept)
        #expect(result[0].id == weaker.id)
        #expect(result[1].id == stronger.id)
    }

    @Test func testDefaultRedundantSuppressionClustersMatchingActionsNearInTime() {
        let stronger = Clip(
            startTime: 20.0,
            endTime: 21.2,
            action: .block,
            confidence: 0.88,
            isKept: true,
            label: "Block A",
            combinedScore: 0.86
        )
        let weaker = Clip(
            startTime: 21.6,
            endTime: 22.8,
            action: .block,
            confidence: 0.79,
            isKept: true,
            label: "Block B",
            combinedScore: 0.74
        )

        let result = defaultRedundantClipSuppressedClips(from: [stronger, weaker])

        #expect(result[0].isKept)
        #expect(!result[1].isKept)
    }

    @Test func testDefaultRedundantSuppressionKeepsDifferentActionsWhenOnlyTimeIsClose() {
        let dunk = Clip(
            startTime: 30.0,
            endTime: 31.2,
            action: .dunk,
            confidence: 0.9,
            isKept: true,
            label: "Dunk",
            combinedScore: 0.9
        )
        let block = Clip(
            startTime: 31.0,
            endTime: 32.2,
            action: .block,
            confidence: 0.87,
            isKept: true,
            label: "Block",
            combinedScore: 0.82
        )

        let result = defaultRedundantClipSuppressedClips(from: [dunk, block])

        #expect(result[0].isKept)
        #expect(result[1].isKept)
    }

    @Test func testSmartSlowMotionQualifiesHighConfidenceDunk() {
        let clip = Clip(
            startTime: 0.0,
            endTime: 4.2,
            action: .dunk,
            confidence: 0.82,
            isKept: true,
            label: "Dunk"
        )

        #expect(shouldApplyExportSlowMotion(to: clip, options: ExportPostProcessingOptions()))
    }

    @Test func testSmartSlowMotionRejectsLowConfidenceDunk() {
        let clip = Clip(
            startTime: 0.0,
            endTime: 4.2,
            action: .dunk,
            confidence: 0.71,
            isKept: true,
            label: "Dunk"
        )

        #expect(!shouldApplyExportSlowMotion(to: clip, options: ExportPostProcessingOptions()))
    }

    @Test func testManualSlowMotionStillAppliesWhenSmartSlowMotionIsDisabled() {
        let clip = Clip(
            startTime: 0.0,
            endTime: 2.5,
            action: .layup,
            confidence: 0.2,
            isKept: true,
            label: "Layup",
            isSlowMotionEnabled: true
        )
        let options = ExportPostProcessingOptions(enableAutoZoom: true, enableSmartSlowMotion: false)

        #expect(shouldApplyExportSlowMotion(to: clip, options: options))
    }

    @Test func testActionZoomScaleReturnsIdentityOutsideActiveWindow() {
        let scale = actionZoomScale(
            at: 0.0,
            segmentDuration: 4.0,
            action: .dunk,
            options: ExportPostProcessingOptions()
        )

        #expect(abs(scale - 1.0) < 0.0001)
    }

    @Test func testActionZoomScaleHitsMaxAtClipMidpoint() {
        let scale = actionZoomScale(
            at: 2.0,
            segmentDuration: 4.0,
            action: .dunk,
            options: ExportPostProcessingOptions()
        )

        #expect(abs(scale - 1.16) < 0.0001)
    }

    @Test func testActionZoomScaleReturnsToIdentityAtWindowBoundaries() {
        let startBoundaryScale = actionZoomScale(
            at: 1.4,
            segmentDuration: 4.0,
            action: .dunk,
            options: ExportPostProcessingOptions()
        )
        let endBoundaryScale = actionZoomScale(
            at: 2.6,
            segmentDuration: 4.0,
            action: .dunk,
            options: ExportPostProcessingOptions()
        )

        #expect(abs(startBoundaryScale - 1.0) < 0.0001)
        #expect(abs(endBoundaryScale - 1.0) < 0.0001)
    }

}
