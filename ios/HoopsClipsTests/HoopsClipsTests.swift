//
//  HoopsClipsTests.swift
//  HoopsClipsTests
//
//  Created by Rork on February 25, 2026.
//

import Testing
import Foundation
import CoreGraphics
import CoreML
import Vision
import UniformTypeIdentifiers
@testable import HoopsClips

@Suite(.serialized)
struct HoopsClipsTests {

    // Test removed because it relies on local JSON files that were cleaned up
    // @Test func testModelPipelineWithLayupJson() async throws { ... }

    @Test func testVideoImportPolicyUsesFileBackedVideoTypesOnly() {
        #expect(VideoImportPolicy.usesFileBackedTransferOnly)
        #expect(VideoImportPolicy.supportedContentTypes == [
            .video,
            .movie,
            .mpeg4Movie,
            .quickTimeMovie
        ])
        #expect(!VideoImportPolicy.supportedContentTypes.contains(.data))
    }

    @Test func testVideoImportPolicyNormalizesPhotosTransferFileExtensions() {
        #expect(VideoImportPolicy.preferredImportedVideoFileExtension(sourceExtension: "", fallbackExtension: "mov") == "mov")
        #expect(VideoImportPolicy.preferredImportedVideoFileExtension(sourceExtension: ".MP4", fallbackExtension: "mov") == "mp4")
        #expect(VideoImportPolicy.preferredImportedVideoFileExtension(sourceExtension: "mov", fallbackExtension: "mp4") == "mov")
        #expect(VideoImportPolicy.preferredImportedVideoFileExtension(sourceExtension: "tmp", fallbackExtension: "mp4") == "mp4")
        #expect(VideoImportPolicy.preferredImportedVideoFileExtension(sourceExtension: "download", fallbackExtension: "mov") == "mov")
    }

    @Test func testVideoImportPreflightAcceptsLongerFourMinuteThirtyEditSource() throws {
        let summary = try VideoImportPolicy.evaluatePreflight(
            fileSizeBytes: 320 * 1024 * 1024,
            durationSeconds: 270,
            dimensions: CGSize(width: 3840, height: 2160),
            codecNames: ["hvc1"],
            availableCapacityBytes: 900 * 1024 * 1024,
            fileExtension: "mov"
        )

        #expect(summary.durationSeconds == 270)
        #expect(summary.dimensions == CGSize(width: 3840, height: 2160))
    }

    @Test func testVideoImportPreflightRejectsOversizedCloudUploadWithExactReason() {
        do {
            _ = try VideoImportPolicy.evaluatePreflight(
                fileSizeBytes: VideoImportPolicy.maxCloudUploadBytes + 1,
                durationSeconds: 60,
                dimensions: CGSize(width: 1920, height: 1080),
                codecNames: ["avc1"],
                availableCapacityBytes: 2 * 1024 * 1024 * 1024,
                fileExtension: "mp4"
            )
            Issue.record("Expected oversized import to fail.")
        } catch let error as VideoImportPreflightError {
            #expect(error.code == "file_too_large")
            #expect(error.userFacingMessage.contains(VideoImportPolicy.formattedBytes(VideoImportPolicy.maxCloudUploadBytes)))
        } catch {
            Issue.record("Unexpected error type: \(error)")
        }
    }

    @Test func testVideoImportPreflightRejectsInsufficientStorageWithExactReason() {
        let fileSizeBytes: Int64 = 100 * 1024 * 1024
        let availableBytes = fileSizeBytes + VideoImportPolicy.requiredScratchBytes - 1

        do {
            _ = try VideoImportPolicy.evaluatePreflight(
                fileSizeBytes: fileSizeBytes,
                durationSeconds: 60,
                dimensions: CGSize(width: 1920, height: 1080),
                codecNames: ["avc1"],
                availableCapacityBytes: availableBytes,
                fileExtension: "mp4"
            )
            Issue.record("Expected low-storage import to fail.")
        } catch let error as VideoImportPreflightError {
            #expect(error.code == "not_enough_storage")
            #expect(error.userFacingMessage.contains(VideoImportPolicy.formattedBytes(fileSizeBytes + VideoImportPolicy.requiredScratchBytes)))
        } catch {
            Issue.record("Unexpected error type: \(error)")
        }
    }

    @Test @MainActor func testSignOutClearsTransientVerificationState() {
        UserDefaults.standard.removeObject(forKey: "hoops_auth_user")
        let authService = AuthService(emailAuthClient: FirebaseEmailAuthClient(apiKey: ""))

        authService.signInAnonymously()
        authService.isLoading = true
        authService.errorMessage = "Old auth error"
        authService.emailVerificationCode = "123456"
        authService.phoneVerificationCode = "654321"
        authService.pendingEmailVerification = "old@example.com"
        authService.pendingPhoneVerification = "+15555550123"

        authService.signOut()

        #expect(!authService.isAuthenticated)
        #expect(authService.isLoading == false)
        #expect(authService.errorMessage == nil)
        #expect(authService.emailVerificationCode == nil)
        #expect(authService.phoneVerificationCode == nil)
        #expect(authService.pendingEmailVerification == nil)
        #expect(authService.pendingPhoneVerification == nil)
        #expect(UserDefaults.standard.data(forKey: "hoops_auth_user") == nil)
    }

    @Test @MainActor func testAuthBoundaryClearClearsVisibleVideoState() {
        let viewModel = HighlightsViewModel()
        viewModel.currentProjectID = UUID()
        viewModel.videoURL = URL(fileURLWithPath: "/tmp/account-boundary-source.mov")
        viewModel.videoDuration = 96
        viewModel.isVideoLoaded = true
        viewModel.cloudAnalysisJobID = "analysis_old_account"
        viewModel.cloudEditSourceObjectKey = "uploads/old-account/source.mp4"
        viewModel.cloudDetectedTeams = [
            CloudTeamOption(
                teamId: "team_old",
                label: "Old account team",
                colorLabel: "blue",
                primaryColorHex: "#0057FF",
                confidence: 0.94,
                source: "quick_scan"
            )
        ]
        viewModel.hasConfirmedHighlightTeamSelection = true
        viewModel.settings.highlightTeamSelection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_old",
            label: "Old account team",
            colorLabel: "blue"
        )
        viewModel.settings.opponentTeamName = "Old opponent"
        viewModel.analysisService.clips = [
            Clip(
                startTime: 8,
                endTime: 13,
                eventCenter: 10,
                action: .steal,
                confidence: 0.82,
                isKept: true,
                label: "Steal",
                audioScore: 0.5,
                visualScore: 0.74,
                motionScore: 0.78,
                combinedScore: 0.76
            )
        ]
        viewModel.exportService.exportedURL = URL(fileURLWithPath: "/tmp/old-account-export.mp4")

        viewModel.clearVisibleProjectForAuthenticationBoundary()

        #expect(viewModel.currentProjectID == nil)
        #expect(viewModel.videoURL == nil)
        #expect(viewModel.videoDuration == 0)
        #expect(viewModel.isVideoLoaded == false)
        #expect(viewModel.clips.isEmpty)
        #expect(viewModel.exportService.exportedURL == nil)
        #expect(viewModel.cloudAnalysisJobID == nil)
        #expect(viewModel.cloudEditSourceObjectKey == nil)
        #expect(viewModel.cloudDetectedTeams.isEmpty)
        #expect(viewModel.hasConfirmedHighlightTeamSelection == false)
        #expect(viewModel.settings.highlightTeamSelection.mode == .all)
        #expect(viewModel.settings.opponentTeamName == nil)
    }

    @Test @MainActor func testAuthenticatedCloudScopesUseSeparateStableInstallIDs() {
        let scopeA = "anonymous:account-a-\(UUID().uuidString)"
        let scopeB = "anonymous:account-b-\(UUID().uuidString)"
        let keyA = HighlightsViewModel.installIDDefaultsKey(forAuthScope: scopeA)
        let keyB = HighlightsViewModel.installIDDefaultsKey(forAuthScope: scopeB)
        UserDefaults.standard.removeObject(forKey: keyA)
        UserDefaults.standard.removeObject(forKey: keyB)
        defer {
            UserDefaults.standard.removeObject(forKey: keyA)
            UserDefaults.standard.removeObject(forKey: keyB)
        }

        let viewModel = HighlightsViewModel()
        let signedOutInstallID = viewModel.installID

        #expect(viewModel.applyAuthenticatedCloudScope(scopeA))
        let accountAInstallID = viewModel.installID
        #expect(!accountAInstallID.isEmpty)
        #expect(accountAInstallID != signedOutInstallID)

        #expect(!viewModel.applyAuthenticatedCloudScope(scopeA))
        #expect(viewModel.installID == accountAInstallID)

        #expect(viewModel.applyAuthenticatedCloudScope(scopeB))
        let accountBInstallID = viewModel.installID
        #expect(!accountBInstallID.isEmpty)
        #expect(accountBInstallID != accountAInstallID)

        #expect(viewModel.applyAuthenticatedCloudScope(scopeA))
        #expect(viewModel.installID == accountAInstallID)
    }

    @Test @MainActor func testDefaultLocalExportSettingsStayFreeAndCompatible() {
        let viewModel = HighlightsViewModel()
        let now = Date()
        let project = PersistedProjectRecord(
            title: "Test Game",
            sourceFilename: "game.mov",
            sourceRelativePath: "sources/game.mov",
            sourceDuration: 60,
            thumbnailRelativePath: "thumbs/game.jpg",
            createdAt: now,
            updatedAt: now,
            lastOpenedAt: now
        )

        #expect(viewModel.selectedTheme == .vibrant)
        #expect(!viewModel.selectedTheme.requiresPro)
        #expect(viewModel.selectedFormat == .mp4)
        #expect(project.selectedTheme == .vibrant)
        #expect(!project.selectedTheme.requiresPro)
        #expect(project.selectedFormat == .mp4)
    }

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
        #expect(CloudEditPreset.personalHighlight.durationOptions == [15, 30, 45, 60, 90, 120, 180, 270])
        #expect(CloudEditPreset.fullGameHighlight.aspectRatio == .widescreen)
        #expect(CloudEditPreset.fullGameHighlight.durationOptions == [60, 90, 120, 180, 240, 270])
        #expect(CloudEditPreset.coachReview.aspectRatio == .source)
        #expect(CloudEditPreset.coachReview.durationOptions == [60, 120, 180, 240, 270])
    }

    @Test func testAIEditLengthChoicesStartSimpleButKeepSelectedLongDurationVisible() {
        let visible = AIEditView.visibleDurationOptions(
            allowedOptions: CloudEditPreset.personalHighlight.durationOptions,
            selectedDuration: 270,
            showAllOptions: false
        )

        #expect(visible == [30, 60, 90, 120, 270])
    }

    @Test func testAIEditLengthChoicesCanRevealAllAllowedDurations() {
        let visible = AIEditView.visibleDurationOptions(
            allowedOptions: CloudEditPreset.personalHighlight.durationOptions,
            selectedDuration: 30,
            showAllOptions: true
        )

        #expect(visible == [15, 30, 45, 60, 90, 120, 180, 270])
    }

    @Test func testCloudEditUserIntentParsesRecapShapeAndDuration() {
        let intent = CloudEditUserIntent.parse("make it NBA recap, 30s vertical")

        #expect(intent.proTemplate == .nbaRecapPro)
        #expect(intent.preset == .fullGameHighlight)
        #expect(intent.aspectRatio == .vertical)
        #expect(intent.durationSeconds == 30)
    }

    @Test func testCloudEditUserIntentParsesCoachReviewSourceAndLongDuration() {
        let intent = CloudEditUserIntent.parse("coach review 4:30 source")

        #expect(intent.proTemplate == nil)
        #expect(intent.preset == .coachReview)
        #expect(intent.aspectRatio == .source)
        #expect(intent.durationSeconds == 270)
    }

    @Test func testCloudEditUserIntentParsesTeamReelPhraseFromPromptPlaceholder() {
        let intent = CloudEditUserIntent.parse("make a 4:30 team reel")

        #expect(intent.proTemplate == .teamHighlightPro)
        #expect(intent.preset == .fullGameHighlight)
        #expect(intent.aspectRatio == nil)
        #expect(intent.durationSeconds == 270)
    }

    @Test func testCloudEditUserIntentParsesCommonTeamVideoPhrases() {
        let phrases = [
            "team highlights",
            "team edit",
            "team video",
            "team mixtape"
        ]

        for phrase in phrases {
            let intent = CloudEditUserIntent.parse(phrase)
            #expect(intent.proTemplate == .teamHighlightPro)
            #expect(intent.preset == .fullGameHighlight)
        }
    }

    @Test func testCloudEditUserIntentKeepsAspectRatioOutOfDuration() {
        let intent = CloudEditUserIntent.parse("vertical 9:16 cinematic mixtape")

        #expect(intent.proTemplate == .cinematicMixtapePro)
        #expect(intent.preset == .personalHighlight)
        #expect(intent.aspectRatio == .vertical)
        #expect(intent.durationSeconds == nil)
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
        #expect(free.maxRenderSeconds == 270)
        #expect(free.maxDailyRenders == 3)
        #expect(free.planLimitRows.contains("3 AI edits/day"))
        #expect(AppConstants.cloudAnalysisDailyQuota == 3)
        #expect(pro.planLimitRows.contains("1080p max export"))
        #expect(free.retentionSummary == "Videos stored for 14 days")
        #expect(pro.retentionSummary == "Videos stored for 60 days")
    }

    @Test func testCloudEditStatusCopyUsesRealCloudJobLanguageWithoutFakeThinking() {
        let inProgressLabels = [
            CloudEditRenderState.renderRequested,
            .planning,
            .planReady,
            .created,
            .queued,
            .rendering
        ].map(\.displayLabel)

        #expect(inProgressLabels.allSatisfy { !$0.localizedCaseInsensitiveContains("AI is") })
        #expect(inProgressLabels.allSatisfy { !$0.localizedCaseInsensitiveContains("thinking") })
        #expect(inProgressLabels.allSatisfy { !$0.localizedCaseInsensitiveContains("ETA") })
        #expect(CloudEditRenderState.rendering.displayLabel == "Rendering in cloud")
        #expect(CloudEditRenderState.rendered.displayLabel == "Your reel is ready")
    }

    @Test func testCloudAnalysisProgressStageSanitizesFakeThinkingEtaAndSensitiveText() {
        let fallback = "Analyzing frames in cloud"
        let unsafeStages = [
            "AI is thinking about the best clips",
            "ETA 2 minutes",
            "Uploading https://storage.example.test/upload/source.mp4",
            "Reading uploads/job_123/source.mp4",
            "Using R2 bucket credentials",
            "Presigned URL ready"
        ]

        for stage in unsafeStages {
            #expect(CloudAnalysisService.safeProgressStage(stage, fallback: fallback) == fallback)
        }

        #expect(CloudAnalysisService.safeProgressStage("", fallback: fallback) == fallback)
        #expect(CloudAnalysisService.safeProgressStage("  Scanning jersey colors  ", fallback: fallback) == "Scanning jersey colors")
        #expect(CloudAnalysisService.safeProgressStage("Finding candidate clips", fallback: fallback) == "Finding candidate clips")
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
        let teamSelection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )
        let teamAttribution = ClipTeamAttribution(
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidence: 0.91,
            source: "quick_scan",
            evidenceFrameRefs: ["clip_1_release", "clip_1_result"],
            evidenceRoleGroups: ["action", "outcome"]
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
            teamSelection: teamSelection,
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
                    userReviewDecision: "kept",
                    nativeShotSignals: nativeSignals,
                    teamAttribution: teamAttribution,
                    teamAttributionStatus: "matched"
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
        let encodedTeamSelection = try #require(payload["teamSelection"] as? [String: Any])
        #expect(encodedTeamSelection["mode"] as? String == "team")
        #expect(encodedTeamSelection["teamId"] as? String == "team_dark")
        #expect(encodedTeamSelection["confidenceThreshold"] as? Double == 0.85)
        let encodedTeamAttribution = try #require(clips.first?["teamAttribution"] as? [String: Any])
        #expect(encodedTeamAttribution["teamId"] as? String == "team_dark")
        #expect(encodedTeamAttribution["confidence"] as? Double == 0.91)
        #expect(encodedTeamAttribution["evidenceFrameRefs"] as? [String] == ["clip_1_release", "clip_1_result"])
        #expect(encodedTeamAttribution["evidenceRoleGroups"] as? [String] == ["action", "outcome"])
        #expect(clips.first?["teamAttributionStatus"] as? String == "matched")
        #expect(clips.first?["userReviewDecision"] as? String == "kept")
    }

    @Test func testCloudEditDefaultPromptAddsAccuracyGuidanceWhenUserLeavesNoteEmpty() throws {
        let prompt = try #require(
            CloudEditUserPromptBuilder.effectivePrompt(
                userPrompt: "   ",
                teamSelection: .allTeams
            )
        )

        #expect(prompt.contains("Cover both teams."))
        #expect(prompt.contains("visible makes"))
        #expect(prompt.contains("blocks"))
        #expect(prompt.contains("steals"))
        #expect(prompt.contains("forced turnovers"))
        #expect(prompt.contains("Defense counts without a make."))
        #expect(prompt.contains("crowd/audio pops"))
        #expect(prompt.contains("verify visible outcome"))
        #expect(prompt.contains("Reject duplicate"))
        #expect(prompt.count <= CloudEditUserPromptBuilder.maxPromptCharacters)
    }

    @Test func testCloudEditDefaultPromptCarriesSelectedTeamFocus() throws {
        let selection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )
        let prompt = try #require(
            CloudEditUserPromptBuilder.effectivePrompt(
                userPrompt: nil,
                teamSelection: selection
            )
        )
        let summary = CloudEditUserPromptBuilder.defaultFocusSummary(teamSelection: selection)

        #expect(prompt.hasPrefix("Focus on Dark jerseys."))
        #expect(prompt.contains("Render selected-team matches"))
        #expect(prompt.contains("reject confident opponents"))
        #expect(prompt.contains("Keep uncertain clips reviewable."))
        #expect(summary.hasPrefix("Target: Dark jerseys."))
        #expect(summary.contains("Dark jerseys"))
        #expect(summary.contains("blocks"))
        #expect(summary.contains("steals"))
        #expect(summary.contains("defensive stops"))
        #expect(summary.contains("crowd/audio cues"))
        #expect(summary.contains("visual proof"))
        #expect(summary.contains("Uncertain clips stay reviewable."))
        #expect(summary.count <= CloudEditUserPromptBuilder.maxFocusSummaryCharacters)
    }

    @Test func testCloudEditDefaultFocusSummaryShowsAllTeamsTarget() {
        let summary = CloudEditUserPromptBuilder.defaultFocusSummary(teamSelection: .allTeams)

        #expect(summary.hasPrefix("Target: All teams."))
        #expect(summary.contains("made shots"))
        #expect(summary.contains("blocks"))
        #expect(summary.contains("steals"))
        #expect(summary.contains("defensive stops"))
        #expect(summary.contains("crowd/audio cues"))
        #expect(summary.contains("visual proof"))
        #expect(summary.contains("Uncertain clips stay reviewable."))
        #expect(summary.count <= CloudEditUserPromptBuilder.maxFocusSummaryCharacters)
    }

    @Test func testCloudEditDefaultFocusSummaryStaysCompactForLongTeamNames() {
        let selection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_long",
            label: "Eastside National Varsity Showcase Black Jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )

        let summary = CloudEditUserPromptBuilder.defaultFocusSummary(teamSelection: selection)

        #expect(summary.hasPrefix("Target: Eastside National Varsity Showcase..."))
        #expect(summary.contains("crowd/audio cues"))
        #expect(summary.contains("visual proof"))
        #expect(summary.count <= CloudEditUserPromptBuilder.maxFocusSummaryCharacters)
    }

    @Test func testCloudEditUserPromptBuilderPreservesUserInstruction() throws {
        let prompt = try #require(
            CloudEditUserPromptBuilder.effectivePrompt(
                userPrompt: "Make it a short defense reel.",
                teamSelection: .allTeams
            )
        )

        #expect(prompt.hasPrefix("Make it a short defense reel."))
        #expect(prompt.contains("Cover both teams."))
        #expect(prompt.contains("visible makes"))
        #expect(prompt.contains("blocks"))
        #expect(prompt.contains("steals"))
        #expect(prompt.contains("forced turnovers"))
        #expect(prompt.contains("Defense counts without a make."))
        #expect(prompt.contains("crowd/audio pops"))
        #expect(prompt.contains("verify visible outcome"))
        #expect(prompt.contains("Reject duplicate"))
        #expect(prompt.count <= CloudEditUserPromptBuilder.maxPromptCharacters)
    }

    @Test func testCloudEditUserPromptBuilderKeepsTeamGuardrailsWithTypedNote() throws {
        let selection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_light",
            label: "White jerseys",
            colorLabel: "white",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )
        let prompt = try #require(
            CloudEditUserPromptBuilder.effectivePrompt(
                userPrompt: "Make this a 4:30 team reel",
                teamSelection: selection
            )
        )

        #expect(prompt.hasPrefix("Make this a 4:30 team reel. Focus on White jerseys."))
        #expect(prompt.contains("reject confident opponents"))
        #expect(prompt.contains("defensive stops"))
        #expect(prompt.contains("Defense counts without a make."))
        #expect(prompt.contains("crowd/audio pops"))
        #expect(prompt.contains("verify visible outcome"))
        #expect(prompt.contains("Keep uncertain clips reviewable."))
        #expect(prompt.count <= CloudEditUserPromptBuilder.maxPromptCharacters)
    }

    @Test func testCloudEditUserPromptBuilderPreservesGuardrailsForLongUserNote() throws {
        let selection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_light",
            label: "White jerseys",
            colorLabel: "white",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )
        let longNote = Array(repeating: "please make a polished team reel with extra context", count: 8)
            .joined(separator: " ")

        let prompt = try #require(
            CloudEditUserPromptBuilder.effectivePrompt(
                userPrompt: longNote,
                teamSelection: selection
            )
        )

        #expect(prompt.hasPrefix("please make a polished"))
        #expect(prompt.contains("Focus on White jerseys."))
        #expect(prompt.contains("reject confident opponents"))
        #expect(prompt.contains("defensive stops"))
        #expect(prompt.contains("crowd/audio pops"))
        #expect(prompt.contains("verify visible outcome"))
        #expect(prompt.contains("Keep uncertain clips reviewable."))
        #expect(prompt.count <= CloudEditUserPromptBuilder.maxPromptCharacters)
    }

    @Test func testCloudAnalysisRequestEncodesPreAnalysisTeamChoice() throws {
        let request = CreateCloudAnalysisJobRequest(
            filename: "game.mp4",
            contentType: "video/mp4",
            fileSizeBytes: 1024,
            durationSeconds: 120,
            installId: "install-123",
            appVersion: "v1",
            analysisVersion: "v1",
            teamSelection: HighlightTeamSelection(
                mode: .team,
                teamId: "team_light",
                label: "Light jerseys",
                colorLabel: "white",
                confidenceThreshold: 0.85,
                includeUncertain: true
            )
        )

        let data = try JSONEncoder().encode(request)
        let payload = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let teamSelection = try #require(payload["teamSelection"] as? [String: Any])

        #expect(teamSelection["mode"] as? String == "team")
        #expect(teamSelection["label"] as? String == "Light jerseys")
        #expect(teamSelection["includeUncertain"] as? Bool == true)
    }

    @Test @MainActor func testCloudTeamScanPreparesJobThenStartSendsSelectedTeam() async throws {
        let tempURL = FileManager.default.temporaryDirectory.appending(path: "team-scan-\(UUID().uuidString).mp4")
        try Data("fake video".utf8).write(to: tempURL)
        defer { try? FileManager.default.removeItem(at: tempURL) }

        var startPayload: [String: Any]?
        var requestedPaths: [String] = []
        let service = CloudAnalysisService(session: makeCloudAnalysisSession { request in
            let url = try #require(request.url)
            requestedPaths.append("\(request.httpMethod ?? "GET") \(url.path)")

            if request.httpMethod == "POST", url.path == "/v1/analysis/jobs" {
                return try cloudAnalysisJSONResponse(for: request, body: """
                {
                  "jobId": "job_team_scan",
                  "uploadUrl": "https://analysis.hoopsclips.test/upload/job_team_scan",
                  "uploadMethod": "PUT",
                  "uploadHeaders": {},
                  "expiresAt": "2026-05-26T20:00:00Z",
                  "pollAfterSeconds": 1,
                  "quotaRemainingToday": 2,
                  "analysisMode": "cloud",
                  "sourceObjectKey": "uploads/job_team_scan/source.mp4",
                  "resultObjectKey": null
                }
                """)
            }

            if request.httpMethod == "PUT", url.path == "/upload/job_team_scan" {
                return try cloudAnalysisEmptyResponse(for: request, statusCode: 204)
            }

            if request.httpMethod == "POST", url.path == "/v1/analysis/jobs/job_team_scan/team-scan" {
                let payload = try cloudAnalysisJSONObject(from: try cloudAnalysisRequestBodyData(from: request))
                #expect(payload["installId"] as? String == "install-123456")
                return try cloudAnalysisJSONResponse(for: request, body: """
                {
                  "jobId": "job_team_scan",
                  "status": "scanned",
                  "detectedTeams": [
                    {"teamId": "team_dark", "label": "Dark jerseys", "colorLabel": "black", "primaryColorHex": "#111111", "confidence": 0.93, "source": "quick_scan"},
                    {"teamId": "team_light", "label": "Light jerseys", "colorLabel": "white", "primaryColorHex": "#ffffff", "confidence": 0.90, "source": "quick_scan"}
                  ]
                }
                """)
            }

            if request.httpMethod == "POST", url.path == "/v1/analysis/jobs/job_team_scan/start" {
                startPayload = try cloudAnalysisJSONObject(from: try cloudAnalysisRequestBodyData(from: request))
                return try cloudAnalysisJSONResponse(for: request, body: """
                {"jobId": "job_team_scan", "status": "queued"}
                """)
            }

            if request.httpMethod == "GET", url.path == "/v1/analysis/jobs/job_team_scan" {
                return try cloudAnalysisJSONResponse(for: request, body: """
                {
                  "jobId": "job_team_scan",
                  "status": "succeeded",
                  "progress": 1.0,
                  "stage": "Finalizing clips",
                  "errorCode": null,
                  "errorMessage": null,
                  "analysisVersion": "v1",
                  "sourceObjectKey": "uploads/job_team_scan/source.mp4",
                  "resultObjectKey": null,
                  "results": {
                    "analysisJobId": "job_team_scan",
                    "sourceObjectKey": "uploads/job_team_scan/source.mp4",
                    "clipCount": 0,
                    "clips": [],
                    "diagnostics": {
                      "processingMs": 1,
                      "backendModelVersion": "cloud-v1+team-scan",
                      "usedVideoIntelligence": false,
                      "usedGeminiRelabeling": false,
                      "candidateSegments": 0,
                      "finalSegments": 0
                    },
                    "detectedTeams": [
                      {"teamId": "team_dark", "label": "Dark jerseys", "colorLabel": "black", "primaryColorHex": "#111111", "confidence": 0.93, "source": "quick_scan"}
                    ],
                    "teamSelection": {
                      "mode": "team",
                      "teamId": "team_dark",
                      "label": "Dark jerseys",
                      "colorLabel": "black",
                      "confidenceThreshold": 0.85,
                      "includeUncertain": true
                    }
                  }
                }
                """)
            }

            throw CloudAnalysisError.invalidResponse
        })

        UserDefaults.standard.set("https://analysis.hoopsclips.test", forKey: "hoops.cloudAnalysisBaseURL")
        defer {
            UserDefaults.standard.removeObject(forKey: "hoops.cloudAnalysisBaseURL")
            CloudAnalysisMockURLProtocol.requestHandler = nil
        }

        let prepared = try await service.prepareTeamScan(
            url: tempURL,
            duration: 120,
            installID: "install-123456"
        ) { _, _ in }
        #expect(prepared.detectedTeams.map(\.teamId) == ["team_dark", "team_light"])

        let result = try await service.analyzePreparedVideo(
            prepared,
            teamSelection: HighlightTeamSelection(
                mode: .team,
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black"
            ),
            installID: "install-123456"
        ) { _, _ in }

        let encodedSelection = try #require(startPayload?["teamSelection"] as? [String: Any])
        #expect(encodedSelection["teamId"] as? String == "team_dark")
        #expect(encodedSelection["includeUncertain"] as? Bool == true)
        #expect(result.teamSelection?.teamId == "team_dark")
        #expect(requestedPaths.contains("POST /v1/analysis/jobs/job_team_scan/team-scan"))
        #expect(requestedPaths.contains("POST /v1/analysis/jobs/job_team_scan/start"))
    }

    @Test @MainActor func testCloudTeamScanAllTeamsChoiceStartsPreparedJobInAllTeamsMode() async throws {
        let tempURL = FileManager.default.temporaryDirectory.appending(path: "team-scan-all-\(UUID().uuidString).mp4")
        try Data("fake video".utf8).write(to: tempURL)
        defer { try? FileManager.default.removeItem(at: tempURL) }

        var startPayload: [String: Any]?
        var requestedPaths: [String] = []
        let service = CloudAnalysisService(session: makeCloudAnalysisSession { request in
            let url = try #require(request.url)
            requestedPaths.append("\(request.httpMethod ?? "GET") \(url.path)")

            if request.httpMethod == "POST", url.path == "/v1/analysis/jobs" {
                return try cloudAnalysisJSONResponse(for: request, body: """
                {
                  "jobId": "job_team_scan_all",
                  "uploadUrl": "https://analysis.hoopsclips.test/upload/job_team_scan_all",
                  "uploadMethod": "PUT",
                  "uploadHeaders": {},
                  "expiresAt": "2026-05-26T20:00:00Z",
                  "pollAfterSeconds": 1,
                  "quotaRemainingToday": 2,
                  "analysisMode": "cloud",
                  "sourceObjectKey": "uploads/job_team_scan_all/source.mp4",
                  "resultObjectKey": null
                }
                """)
            }

            if request.httpMethod == "PUT", url.path == "/upload/job_team_scan_all" {
                return try cloudAnalysisEmptyResponse(for: request, statusCode: 204)
            }

            if request.httpMethod == "POST", url.path == "/v1/analysis/jobs/job_team_scan_all/team-scan" {
                return try cloudAnalysisJSONResponse(for: request, body: """
                {
                  "jobId": "job_team_scan_all",
                  "status": "scanned",
                  "detectedTeams": [
                    {"teamId": "team_dark", "label": "Dark jerseys", "colorLabel": "black", "primaryColorHex": "#111111", "confidence": 0.93, "source": "quick_scan"},
                    {"teamId": "team_light", "label": "Light jerseys", "colorLabel": "white", "primaryColorHex": "#ffffff", "confidence": 0.90, "source": "quick_scan"}
                  ]
                }
                """)
            }

            if request.httpMethod == "POST", url.path == "/v1/analysis/jobs/job_team_scan_all/start" {
                startPayload = try cloudAnalysisJSONObject(from: try cloudAnalysisRequestBodyData(from: request))
                return try cloudAnalysisJSONResponse(for: request, body: """
                {"jobId": "job_team_scan_all", "status": "queued"}
                """)
            }

            if request.httpMethod == "GET", url.path == "/v1/analysis/jobs/job_team_scan_all" {
                return try cloudAnalysisJSONResponse(for: request, body: """
                {
                  "jobId": "job_team_scan_all",
                  "status": "succeeded",
                  "progress": 1.0,
                  "stage": "Finalizing clips",
                  "errorCode": null,
                  "errorMessage": null,
                  "analysisVersion": "v1",
                  "sourceObjectKey": "uploads/job_team_scan_all/source.mp4",
                  "resultObjectKey": null,
                  "results": {
                    "analysisJobId": "job_team_scan_all",
                    "sourceObjectKey": "uploads/job_team_scan_all/source.mp4",
                    "clipCount": 0,
                    "clips": [],
                    "diagnostics": {
                      "processingMs": 1,
                      "backendModelVersion": "cloud-v1+team-scan",
                      "usedVideoIntelligence": false,
                      "usedGeminiRelabeling": false,
                      "candidateSegments": 0,
                      "finalSegments": 0
                    },
                    "detectedTeams": [
                      {"teamId": "team_dark", "label": "Dark jerseys", "colorLabel": "black", "primaryColorHex": "#111111", "confidence": 0.93, "source": "quick_scan"},
                      {"teamId": "team_light", "label": "Light jerseys", "colorLabel": "white", "primaryColorHex": "#ffffff", "confidence": 0.90, "source": "quick_scan"}
                    ],
                    "teamSelection": {
                      "mode": "all",
                      "confidenceThreshold": 0.85,
                      "includeUncertain": true
                    }
                  }
                }
                """)
            }

            throw CloudAnalysisError.invalidResponse
        })

        UserDefaults.standard.set("https://analysis.hoopsclips.test", forKey: "hoops.cloudAnalysisBaseURL")
        defer {
            UserDefaults.standard.removeObject(forKey: "hoops.cloudAnalysisBaseURL")
            CloudAnalysisMockURLProtocol.requestHandler = nil
        }

        let prepared = try await service.prepareTeamScan(
            url: tempURL,
            duration: 120,
            installID: "install-123456"
        ) { _, _ in }
        #expect(prepared.detectedTeams.count == 2)

        let result = try await service.analyzePreparedVideo(
            prepared,
            teamSelection: .allTeams,
            installID: "install-123456"
        ) { _, _ in }

        let encodedSelection = try #require(startPayload?["teamSelection"] as? [String: Any])
        #expect(encodedSelection["mode"] as? String == "all")
        #expect(encodedSelection["teamId"] as? String == nil)
        #expect(result.teamSelection?.mode == .all)
        #expect(requestedPaths.contains("POST /v1/analysis/jobs/job_team_scan_all/team-scan"))
        #expect(requestedPaths.contains("POST /v1/analysis/jobs/job_team_scan_all/start"))
    }

    @Test func testHighlightTeamSelectionCodablePreservesPrimaryColorHex() throws {
        let selection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_blue",
            label: "Blue jerseys",
            colorLabel: "blue",
            primaryColorHex: "#0057FF"
        )

        let data = try JSONEncoder().encode(selection)
        let payload = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let decoded = try JSONDecoder().decode(HighlightTeamSelection.self, from: data)

        #expect(payload["primaryColorHex"] as? String == "#0057FF")
        #expect(decoded.primaryColorHex == "#0057FF")
        #expect(selection.accessibilityIdentifier == "analysis.teamTarget.choice.team-blue")
        #expect(HighlightTeamSelection.allTeams.accessibilityIdentifier == "analysis.teamTarget.choice.all")
    }

    @Test @MainActor func testTeamTargetChoicesRequireDetectedTeams() {
        let viewModel = HighlightsViewModel()

        let fallbackChoices = viewModel.availableHighlightTeamChoices
        #expect(fallbackChoices.map(\.mode) == [.all])
        #expect(fallbackChoices.map(\.accessibilityIdentifier) == ["analysis.teamTarget.choice.all"])
        #expect(viewModel.requiresHighlightTeamSelectionConfirmation == false)

        viewModel.cloudDetectedTeams = [
            CloudTeamOption(
                teamId: "team_blue",
                label: "Blue jerseys",
                colorLabel: "blue",
                primaryColorHex: "#0057FF",
                confidence: 0.94,
                source: "quick_scan"
            )
        ]

        let scannedChoices = viewModel.availableHighlightTeamChoices
        #expect(scannedChoices.map(\.selectionKey) == ["all", "team_blue"])
        #expect(scannedChoices.map(\.accessibilityIdentifier) == ["analysis.teamTarget.choice.all", "analysis.teamTarget.choice.team-blue"])
        #expect(scannedChoices[1].confidenceThreshold == 0.85)
        #expect(scannedChoices[1].includeUncertain)
        #expect(scannedChoices[1].primaryColorHex == "#0057FF")
        #expect(viewModel.requiresHighlightTeamSelectionConfirmation)

        viewModel.confirmHighlightTeamSelection(scannedChoices[1])
        #expect(viewModel.requiresHighlightTeamSelectionConfirmation == false)
        #expect(viewModel.settings.highlightTeamSelection.teamId == "team_blue")
    }

    @Test @MainActor func testTeamTargetCanUseCustomDisplayName() {
        let viewModel = HighlightsViewModel()
        viewModel.cloudDetectedTeams = [
            CloudTeamOption(
                teamId: "team_blue",
                label: "Blue jerseys",
                colorLabel: "blue",
                primaryColorHex: "#0057FF",
                confidence: 0.94,
                source: "quick_scan"
            )
        ]

        viewModel.confirmHighlightTeamSelection(viewModel.availableHighlightTeamChoices[1])
        viewModel.renameSelectedHighlightTeam("  Eastside 17U   Varsity  ")

        #expect(viewModel.settings.highlightTeamSelection.label == "Eastside 17U Varsity")
        #expect(viewModel.settings.customHighlightTeamNames["team_blue"] == "Eastside 17U Varsity")
        #expect(viewModel.availableHighlightTeamChoices[1].displayTitle == "Eastside 17U Varsity")

        viewModel.renameSelectedHighlightTeam("   ")

        #expect(viewModel.settings.highlightTeamSelection.label == "Blue jerseys")
        #expect(viewModel.settings.customHighlightTeamNames["team_blue"] == nil)
        #expect(viewModel.availableHighlightTeamChoices[1].displayTitle == "Blue jerseys")
    }

    @Test @MainActor func testOpponentTeamNameIsSanitizedAndClearable() {
        let viewModel = HighlightsViewModel()

        viewModel.renameOpponentTeam("  Westside   Prep  ")

        #expect(viewModel.settings.opponentTeamName == "Westside Prep")
        #expect(viewModel.opponentTeamNameDraft == "Westside Prep")

        viewModel.renameOpponentTeam("   ")

        #expect(viewModel.settings.opponentTeamName == nil)
        #expect(viewModel.opponentTeamNameDraft == "")
    }

    @Test func testAnalysisSettingsCodablePreservesOpponentName() throws {
        var settings = AnalysisSettings()
        settings.opponentTeamName = "Westside Prep"

        let data = try JSONEncoder().encode(settings)
        let decoded = try JSONDecoder().decode(AnalysisSettings.self, from: data)

        #expect(decoded.opponentTeamName == "Westside Prep")
    }

    @Test @MainActor func testTeamScanCancellationClearsInProgressState() async throws {
        let tempURL = FileManager.default.temporaryDirectory.appending(path: "team-scan-cancel-\(UUID().uuidString).mp4")
        try Data("fake video".utf8).write(to: tempURL)
        defer { try? FileManager.default.removeItem(at: tempURL) }

        let viewModel = HighlightsViewModel()
        viewModel.videoURL = tempURL
        viewModel.videoDuration = 120
        viewModel.isVideoLoaded = true
        viewModel.cloudAnalysisService = CloudAnalysisService(session: makeCloudAnalysisSession { _ in
            throw CancellationError()
        })

        UserDefaults.standard.set("https://analysis.hoopsclips.test", forKey: "hoops.cloudAnalysisBaseURL")
        defer {
            UserDefaults.standard.removeObject(forKey: "hoops.cloudAnalysisBaseURL")
            CloudAnalysisMockURLProtocol.requestHandler = nil
        }

        await viewModel.scanTeamsBeforeAnalysis()

        #expect(viewModel.isCloudTeamScanInProgress == false)
        #expect(viewModel.cloudDetectedTeams.isEmpty)
        #expect(viewModel.hasConfirmedHighlightTeamSelection == false)
        #expect(viewModel.cloudTeamScanStatusMessage == nil)
    }

    @Test @MainActor func testStartAnalysisRequiresConfirmedTeamChoiceAfterCloudScan() async throws {
        let tempURL = FileManager.default.temporaryDirectory.appending(path: "team-choice-required-\(UUID().uuidString).mp4")
        try Data("fake video".utf8).write(to: tempURL)
        defer { try? FileManager.default.removeItem(at: tempURL) }

        var requestCount = 0
        let viewModel = HighlightsViewModel()
        viewModel.videoURL = tempURL
        viewModel.videoDuration = 120
        viewModel.isVideoLoaded = true
        viewModel.cloudDetectedTeams = [
            CloudTeamOption(
                teamId: "team_blue",
                label: "Blue jerseys",
                colorLabel: "blue",
                primaryColorHex: "#0057FF",
                confidence: 0.94,
                source: "quick_scan"
            )
        ]
        viewModel.hasConfirmedHighlightTeamSelection = false
        viewModel.cloudAnalysisService = CloudAnalysisService(session: makeCloudAnalysisSession { _ in
            requestCount += 1
            throw CloudAnalysisError.invalidResponse
        })

        UserDefaults.standard.set("https://analysis.hoopsclips.test", forKey: "hoops.cloudAnalysisBaseURL")
        defer {
            UserDefaults.standard.removeObject(forKey: "hoops.cloudAnalysisBaseURL")
            CloudAnalysisMockURLProtocol.requestHandler = nil
        }

        await viewModel.startAnalysis()

        #expect(viewModel.requiresHighlightTeamSelectionConfirmation)
        #expect(viewModel.cloudTeamScanStatusMessage == "Choose a team before analysis")
        #expect(viewModel.analysisService.isAnalyzing == false)
        #expect(viewModel.cloudAnalysisJobID == nil)
        #expect(requestCount == 0)
    }

    @Test @MainActor func testPersistedProjectRecordStoresCloudTeamSelectionAndDiagnostics() throws {
        let now = Date(timeIntervalSince1970: 1_777_000_000)
        let project = PersistedProjectRecord(
            title: "Team Game",
            sourceFilename: "team-game.mov",
            sourceRelativePath: "projects/source.mov",
            sourceDuration: 64,
            thumbnailRelativePath: "projects/thumb.jpg",
            createdAt: now,
            updatedAt: now,
            lastOpenedAt: now,
            highlightTeamSelection: HighlightTeamSelection(
                mode: .team,
                teamId: "team_blue",
                label: "Blue jerseys",
                colorLabel: "blue",
                primaryColorHex: "#0057FF"
            ),
            opponentTeamName: "Westside Prep",
            cloudDetectedTeams: [
                CloudTeamOption(
                    teamId: "team_blue",
                    label: "Blue jerseys",
                    colorLabel: "blue",
                    primaryColorHex: "#0057FF",
                    confidence: 0.94,
                    source: "quick_scan"
                )
            ],
            cloudDiagnostics: CloudDiagnostics(
                processingMs: 42,
                backendModelVersion: "cloud-v1+team-scan",
                usedVideoIntelligence: false,
                usedGeminiRelabeling: false,
                candidateSegments: 12,
                finalSegments: 4,
                usedTeamQuickScan: true,
                preTeamFilterSegments: 12,
                teamMatchedCandidateSegments: 5,
                teamUncertainCandidateSegments: 2,
                teamOpponentFilteredSegments: 5,
                teamMatchedReviewSegments: 3,
                teamUncertainReviewSegments: 1,
                defensiveReviewSegments: 1,
                blockReviewSegments: 0,
                stealReviewSegments: 1,
                forcedTurnoverReviewSegments: 1,
                defensiveStopReviewSegments: 1
            )
        )
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let decoded = try decoder.decode(PersistedProjectRecord.self, from: try encoder.encode(project))

        #expect(decoded.highlightTeamSelection?.teamId == "team_blue")
        #expect(decoded.opponentTeamName == "Westside Prep")
        #expect(decoded.highlightTeamSelection?.primaryColorHex == "#0057FF")
        #expect(decoded.cloudDetectedTeams?.first?.label == "Blue jerseys")
        #expect(decoded.cloudDiagnostics?.forcedTurnoverReviewSegments == 1)
        #expect(decoded.cloudDiagnostics?.defensiveStopReviewSegments == 1)
        #expect(decoded.cloudDiagnostics?.teamUncertainReviewSegments == 1)
    }

    @Test func testProjectHistoryBadgesUsePlainUserVisibleLabels() {
        let now = Date(timeIntervalSince1970: 1_777_100_000)
        let project = PersistedProjectRecord(
            title: "Blue vs Gold",
            sourceFilename: "blue-gold.mov",
            sourceRelativePath: "projects/source.mov",
            sourceDuration: 64,
            thumbnailRelativePath: "projects/thumb.jpg",
            latestExportRelativePath: "projects/export.mp4",
            latestExportFilename: "blue-gold-edit.mp4",
            createdAt: now,
            updatedAt: now,
            lastOpenedAt: now,
            totalClipCount: 22,
            keptClipCount: 8
        )

        #expect(project.historyClipBadgeText == "8 kept")
        #expect(project.historyClipBadgeAccessibilityText == "8 kept clips out of 22 total clips")
        #expect(project.historyExportBadgeText == "Saved reel")
    }

    @Test func testHistoryProjectActionsUseShortReadableCopy() {
        let actionCopy = [
            HistoryProjectActionCopy.emptyPreviewHint,
            HistoryProjectActionCopy.openAvailableSubtitle,
            HistoryProjectActionCopy.openUnavailableSubtitle,
            HistoryProjectActionCopy.sourceAvailableSubtitle,
            HistoryProjectActionCopy.sourceMissingSubtitle,
            HistoryProjectActionCopy.exportAvailableSubtitle,
            HistoryProjectActionCopy.exportMissingSubtitle,
            HistoryProjectActionCopy.shareAvailableSubtitle,
            HistoryProjectActionCopy.deleteSubtitle,
        ]

        #expect(actionCopy.allSatisfy { !$0.contains("Latest Export") })
        #expect(actionCopy.allSatisfy { $0.count <= 32 })
        #expect(HistoryProjectActionCopy.shareAvailableSubtitle == "Use iOS share sheet")
        #expect(HistoryProjectActionCopy.openAvailableSubtitle == "Open in Player, Review, Export")
    }

    @Test @MainActor func testCloudEditRequestSendsFullBackendCandidatePoolAndReviewReserve() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        var clips: [Clip] = []
        let strongIndex = 269
        for index in 0..<280 {
            let isStrongCandidate = index == strongIndex
            let startTime = Double(index * 10)
            clips.append(
                Clip(
                    startTime: startTime,
                    endTime: startTime + 6,
                    eventCenter: startTime + 3,
                    action: .madeShot,
                    confidence: isStrongCandidate ? 0.98 : 0.72,
                    isKept: true,
                    label: "Made Shot",
                    audioScore: isStrongCandidate ? 0.92 : 0.2,
                    visualScore: isStrongCandidate ? 0.95 : 0.62,
                    motionScore: isStrongCandidate ? 0.95 : 0.62,
                    combinedScore: isStrongCandidate ? 0.99 : 0.62,
                    detectionMethod: .cloud
                )
            )
        }

        for index in 0..<90 {
            let startTime = 2_000.0 + Double(index * 8)
            clips.append(
                Clip(
                    startTime: startTime,
                    endTime: startTime + 5,
                    eventCenter: startTime + 2.4,
                    action: index.isMultiple(of: 2) ? .steal : .block,
                    confidence: 0.78,
                    isKept: false,
                    label: index.isMultiple(of: 2) ? "Possible Steal" : "Possible Block",
                    audioScore: 0.42,
                    visualScore: 0.72,
                    motionScore: 0.76,
                    combinedScore: 0.8,
                    detectionMethod: .cloud,
                    teamAttributionStatus: "uncertain"
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
        let reviewCandidateCount = request.clips.filter { $0.userReviewDecision == "unreviewed" }.count

        #expect(request.clips.count == HighlightsViewModel.cloudEditCandidateRequestLimit)
        #expect(candidateStarts.contains(Double(strongIndex * 10)))
        #expect(reviewCandidateCount == 90)
        #expect(candidateStarts.contains(2_000.0))
    }

    @Test @MainActor func testCloudEditRequestReservesHalfCandidatePoolForReviewUnderPressure() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        var clips: [Clip] = []

        for index in 0..<300 {
            let startTime = Double(index * 8)
            clips.append(
                Clip(
                    startTime: startTime,
                    endTime: startTime + 5,
                    eventCenter: startTime + 2.5,
                    action: .madeShot,
                    confidence: 0.82,
                    isKept: true,
                    label: "Made Shot",
                    audioScore: 0.5,
                    visualScore: 0.72,
                    motionScore: 0.74,
                    combinedScore: 0.78,
                    detectionMethod: .cloud
                )
            )
        }

        for index in 0..<220 {
            let startTime = 3_000.0 + Double(index * 7)
            clips.append(
                Clip(
                    startTime: startTime,
                    endTime: startTime + 5,
                    eventCenter: startTime + 2.3,
                    action: index.isMultiple(of: 2) ? .steal : .block,
                    confidence: 0.76,
                    isKept: false,
                    label: index.isMultiple(of: 2) ? "Possible Steal" : "Possible Block",
                    audioScore: 0.38,
                    visualScore: 0.68,
                    motionScore: 0.76,
                    combinedScore: 0.74,
                    detectionMethod: .cloud,
                    teamAttributionStatus: "uncertain"
                )
            )
        }
        viewModel.analysisService.clips = clips

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )
        let reviewCandidateCount = request.clips.filter { $0.userReviewDecision == "unreviewed" }.count

        #expect(request.clips.count == HighlightsViewModel.cloudEditCandidateRequestLimit)
        #expect(reviewCandidateCount == HighlightsViewModel.cloudEditCandidateRequestLimit / 2)
    }

    @Test @MainActor func testCloudEditCanStartFromCandidatePoolWithoutManualKeptClip() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        let reviewOnlyBlock = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000041")!,
            startTime: 12.0,
            endTime: 18.0,
            eventCenter: 15.0,
            action: .block,
            confidence: 0.82,
            isKept: false,
            label: "Possible Block",
            audioScore: 0.44,
            visualScore: 0.76,
            motionScore: 0.8,
            combinedScore: 0.83,
            detectionMethod: .cloud,
            teamAttributionStatus: "matched"
        )
        viewModel.analysisService.clips = [reviewOnlyBlock]

        #expect(viewModel.keptClips.isEmpty)
        #expect(viewModel.cloudEditCandidatePoolCount == 1)
        #expect(viewModel.canRequestCloudEdit)
        #expect(viewModel.cloudEditUnavailableReason == nil)

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )

        #expect(request.clips.map(\.label) == ["Possible Block"])
        #expect(request.clips.first?.userReviewDecision == "unreviewed")
    }

    @Test @MainActor func testCloudEditRequestReservesCrowdPopCandidateForGptReview() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        var clips: [Clip] = []

        for index in 0..<330 {
            let startTime = Double(index * 8)
            clips.append(
                Clip(
                    startTime: startTime,
                    endTime: startTime + 6,
                    eventCenter: startTime + 3,
                    action: .madeShot,
                    confidence: 0.96,
                    isKept: true,
                    label: "Made Shot",
                    audioScore: 0.7,
                    visualScore: 0.92,
                    motionScore: 0.9,
                    combinedScore: 0.94,
                    detectionMethod: .cloud
                )
            )
        }

        let crowdPopClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000091")!,
            startTime: 2_800.0,
            endTime: 2_806.0,
            eventCenter: 2_803.0,
            action: .unknown,
            confidence: 0.58,
            isKept: false,
            label: "Crowd Reaction",
            audioScore: 0.97,
            visualScore: 0.44,
            motionScore: 0.46,
            combinedScore: 0.56,
            detectionMethod: .cloud
        )
        clips.append(crowdPopClip)
        viewModel.analysisService.clips = clips

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )

        let crowdCandidate = try #require(request.clips.first { $0.id == crowdPopClip.id.uuidString })
        #expect(request.clips.count == HighlightsViewModel.cloudEditCandidateRequestLimit)
        #expect(crowdCandidate.userReviewDecision == "unreviewed")
        #expect(crowdCandidate.label == "Crowd Reaction")
        #expect(crowdCandidate.audioPeak >= 0.97)
    }

    @Test @MainActor func testCloudEditRequestLabelsGenericAudioPopCueForGptReview() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        let audioCueClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000092")!,
            startTime: 42.0,
            endTime: 48.0,
            eventCenter: 45.0,
            action: .unknown,
            confidence: 0.58,
            isKept: false,
            label: "Action",
            audioScore: 0.96,
            visualScore: 0.44,
            motionScore: 0.46,
            combinedScore: 0.56,
            detectionMethod: .cloud
        )
        viewModel.analysisService.clips = [audioCueClip]

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )

        let candidate = try #require(request.clips.first)
        #expect(candidate.id == audioCueClip.id.uuidString)
        #expect(candidate.label == "Audio Pop Cue")
        #expect(candidate.userReviewDecision == "unreviewed")
        #expect(candidate.audioPeak >= 0.96)
    }

    @Test @MainActor func testCloudEditRequestIncludesReviewOnlyUncertainCandidatesWithoutAutoKeepingThem() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        let keptClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
            startTime: 10.0,
            endTime: 16.0,
            eventCenter: 13.0,
            action: .madeShot,
            confidence: 0.93,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.72,
            visualScore: 0.88,
            motionScore: 0.82,
            combinedScore: 0.9,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.93,
                source: "quick_scan",
                evidenceFrameRefs: ["kept_setup", "kept_result"],
                evidenceRoleGroups: ["setup", "outcome"]
            ),
            teamAttributionStatus: "matched"
        )
        let reviewOnlySteal = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000002")!,
            startTime: 24.0,
            endTime: 29.0,
            eventCenter: 26.2,
            action: .steal,
            confidence: 0.81,
            isKept: false,
            label: "Possible Steal",
            audioScore: 0.48,
            visualScore: 0.74,
            motionScore: 0.78,
            combinedScore: 0.82,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.64,
                source: "gpt_frame_review"
            ),
            teamAttributionStatus: "uncertain"
        )
        let ordinaryDiscardedClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000003")!,
            startTime: 34.0,
            endTime: 40.0,
            eventCenter: 37.0,
            action: .unknown,
            confidence: 0.45,
            isKept: false,
            label: "Generic Clip",
            audioScore: 0.1,
            visualScore: 0.2,
            motionScore: 0.2,
            combinedScore: 0.18,
            detectionMethod: .cloud,
            teamAttributionStatus: "matched"
        )
        let reviewOnlyBlock = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000004")!,
            startTime: 44.0,
            endTime: 49.0,
            eventCenter: 46.2,
            action: .block,
            confidence: 0.8,
            isKept: false,
            label: "Clean Block",
            audioScore: 0.44,
            visualScore: 0.76,
            motionScore: 0.8,
            combinedScore: 0.82,
            detectionMethod: .cloud,
            teamAttributionStatus: "matched"
        )
        viewModel.analysisService.clips = [keptClip, reviewOnlySteal, ordinaryDiscardedClip, reviewOnlyBlock]

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )
        #expect(request.clips.map(\.label) == ["Made Shot", "Possible Steal", "Clean Block"])
        #expect(request.clips.first { $0.id == keptClip.id.uuidString }?.userReviewDecision == "kept")
        #expect(request.clips.first { $0.id == reviewOnlySteal.id.uuidString }?.userReviewDecision == "unreviewed")
        #expect(request.clips.first { $0.id == reviewOnlyBlock.id.uuidString }?.userReviewDecision == "unreviewed")
        #expect(request.clips.first { $0.id == ordinaryDiscardedClip.id.uuidString } == nil)
    }

    @Test @MainActor func testCloudEditRequestKeepsExpandedDefensiveMomentsForGptReview() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        let keptClip = Clip(
            startTime: 8.0,
            endTime: 14.0,
            eventCenter: 11.0,
            action: .madeShot,
            confidence: 0.9,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.6,
            visualScore: 0.82,
            motionScore: 0.8,
            combinedScore: 0.86,
            detectionMethod: .cloud
        )
        let deflection = Clip(
            startTime: 20.0,
            endTime: 25.0,
            eventCenter: 22.2,
            action: .unknown,
            confidence: 0.72,
            isKept: false,
            label: "Ball Deflection Into Runout",
            audioScore: 0.32,
            visualScore: 0.7,
            motionScore: 0.74,
            combinedScore: 0.71,
            detectionMethod: .cloud
        )
        let charge = Clip(
            startTime: 32.0,
            endTime: 37.0,
            eventCenter: 34.0,
            action: .unknown,
            confidence: 0.7,
            isKept: false,
            label: "Takes Charge",
            audioScore: 0.3,
            visualScore: 0.68,
            motionScore: 0.7,
            combinedScore: 0.69,
            detectionMethod: .cloud
        )
        let takeaway = Clip(
            startTime: 44.0,
            endTime: 49.0,
            eventCenter: 46.0,
            action: .unknown,
            confidence: 0.73,
            isKept: false,
            label: "Takeaway Steal",
            audioScore: 0.34,
            visualScore: 0.71,
            motionScore: 0.76,
            combinedScore: 0.73,
            detectionMethod: .cloud
        )
        viewModel.analysisService.clips = [keptClip, deflection, charge, takeaway]

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )

        #expect(request.clips.map(\.label) == [
            "Made Shot",
            "Ball Deflection Into Runout",
            "Takes Charge",
            "Takeaway Steal"
        ])
        #expect(request.clips.filter { $0.userReviewDecision == "unreviewed" }.map(\.label) == [
            "Ball Deflection Into Runout",
            "Takes Charge",
            "Takeaway Steal"
        ])
    }

    @Test @MainActor func testCloudEditRequestKeepsInterceptionsAndPokedLooseStealsForGptReview() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        let keptClip = Clip(
            startTime: 8.0,
            endTime: 14.0,
            eventCenter: 11.0,
            action: .madeShot,
            confidence: 0.9,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.6,
            visualScore: 0.82,
            motionScore: 0.8,
            combinedScore: 0.86,
            detectionMethod: .cloud
        )
        let interceptedPass = Clip(
            startTime: 20.0,
            endTime: 25.0,
            eventCenter: 22.2,
            action: .unknown,
            confidence: 0.73,
            isKept: false,
            label: "Intercepted Pass",
            audioScore: 0.32,
            visualScore: 0.7,
            motionScore: 0.74,
            combinedScore: 0.72,
            detectionMethod: .cloud
        )
        let pokedLoose = Clip(
            startTime: 32.0,
            endTime: 37.0,
            eventCenter: 34.0,
            action: .unknown,
            confidence: 0.72,
            isKept: false,
            label: "Poked Ball Loose",
            audioScore: 0.3,
            visualScore: 0.68,
            motionScore: 0.72,
            combinedScore: 0.7,
            detectionMethod: .cloud
        )
        let rejectedAtRim = Clip(
            startTime: 44.0,
            endTime: 49.0,
            eventCenter: 46.2,
            action: .unknown,
            confidence: 0.74,
            isKept: false,
            label: "Rejected At The Rim",
            audioScore: 0.36,
            visualScore: 0.72,
            motionScore: 0.78,
            combinedScore: 0.73,
            detectionMethod: .cloud
        )
        viewModel.analysisService.clips = [keptClip, interceptedPass, pokedLoose, rejectedAtRim]

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )

        #expect(request.clips.map(\.label) == [
            "Made Shot",
            "Intercepted Pass",
            "Poked Ball Loose",
            "Rejected At The Rim"
        ])
        #expect(request.clips.filter { $0.userReviewDecision == "unreviewed" }.map(\.label) == [
            "Intercepted Pass",
            "Poked Ball Loose",
            "Rejected At The Rim"
        ])
    }

    @Test @MainActor func testCloudEditRequestIncludesStrongSelectedTeamReserveCandidate() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        viewModel.settings.highlightTeamSelection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85
        )

        let keptClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000011")!,
            startTime: 10.0,
            endTime: 16.0,
            eventCenter: 13.0,
            action: .madeShot,
            confidence: 0.92,
            isKept: true,
            label: "Kept Dark Shot",
            audioScore: 0.7,
            visualScore: 0.85,
            motionScore: 0.82,
            combinedScore: 0.88,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.93,
                source: "team_scan"
            ),
            teamAttributionStatus: "matched"
        )
        let strongSelectedTeamClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000012")!,
            startTime: 30.0,
            endTime: 37.0,
            eventCenter: 33.4,
            action: .madeShot,
            confidence: 0.76,
            isKept: false,
            label: "Strong Dark Finish",
            audioScore: 0.58,
            visualScore: 0.73,
            motionScore: 0.76,
            combinedScore: 0.82,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.9,
                source: "team_scan"
            ),
            teamAttributionStatus: "matched"
        )
        let otherTeamClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000013")!,
            startTime: 48.0,
            endTime: 55.0,
            eventCenter: 51.1,
            action: .madeShot,
            confidence: 0.9,
            isKept: false,
            label: "Strong Light Finish",
            audioScore: 0.82,
            visualScore: 0.9,
            motionScore: 0.88,
            combinedScore: 0.94,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_light",
                label: "Light jerseys",
                colorLabel: "white",
                confidence: 0.95,
                source: "team_scan"
            ),
            teamAttributionStatus: "matched"
        )
        let lowSignalSelectedTeamClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000014")!,
            startTime: 62.0,
            endTime: 68.0,
            eventCenter: 65.0,
            action: .madeShot,
            confidence: 0.72,
            isKept: false,
            label: "Low Signal Dark Shot",
            audioScore: 0.2,
            visualScore: 0.52,
            motionScore: 0.55,
            combinedScore: 0.58,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.91,
                source: "team_scan"
            ),
            teamAttributionStatus: "matched"
        )
        viewModel.analysisService.clips = [
            keptClip,
            strongSelectedTeamClip,
            otherTeamClip,
            lowSignalSelectedTeamClip
        ]

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )

        #expect(request.clips.map(\.label) == ["Kept Dark Shot", "Strong Dark Finish"])
        #expect(request.clips.first { $0.id == keptClip.id.uuidString }?.userReviewDecision == "kept")
        #expect(request.clips.first { $0.id == strongSelectedTeamClip.id.uuidString }?.userReviewDecision == "unreviewed")
        #expect(request.clips.first { $0.id == otherTeamClip.id.uuidString } == nil)
        #expect(request.clips.first { $0.id == lowSignalSelectedTeamClip.id.uuidString } == nil)
        #expect(viewModel.cloudEditCandidatePoolCount == 2)
    }

    @Test @MainActor func testCloudEditRequestKeepsUncertainTeamCandidateForSelectedTeamReview() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        viewModel.settings.highlightTeamSelection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )

        let keptDarkClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000021")!,
            startTime: 10.0,
            endTime: 16.0,
            eventCenter: 13.0,
            action: .madeShot,
            confidence: 0.92,
            isKept: true,
            label: "Kept Dark Shot",
            audioScore: 0.7,
            visualScore: 0.85,
            motionScore: 0.82,
            combinedScore: 0.88,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.93,
                source: "team_scan"
            ),
            teamAttributionStatus: "matched"
        )
        let uncertainTeamClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000022")!,
            startTime: 24.0,
            endTime: 30.0,
            eventCenter: 27.0,
            action: .madeShot,
            confidence: 0.76,
            isKept: false,
            label: "No Team Finish",
            audioScore: 0.52,
            visualScore: 0.74,
            motionScore: 0.77,
            combinedScore: 0.8,
            detectionMethod: .cloud
        )
        let confidentOpponentClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000023")!,
            startTime: 38.0,
            endTime: 44.0,
            eventCenter: 41.0,
            action: .madeShot,
            confidence: 0.94,
            isKept: true,
            label: "Kept Light Shot",
            audioScore: 0.82,
            visualScore: 0.9,
            motionScore: 0.88,
            combinedScore: 0.94,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_light",
                label: "Light jerseys",
                colorLabel: "white",
                confidence: 0.95,
                source: "team_scan"
            ),
            teamAttributionStatus: "matched"
        )
        let weakUncertainClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000024")!,
            startTime: 52.0,
            endTime: 58.0,
            eventCenter: 55.0,
            action: .madeShot,
            confidence: 0.66,
            isKept: false,
            label: "Weak No Team Shot",
            audioScore: 0.2,
            visualScore: 0.48,
            motionScore: 0.5,
            combinedScore: 0.55,
            detectionMethod: .cloud
        )
        viewModel.analysisService.clips = [
            keptDarkClip,
            uncertainTeamClip,
            confidentOpponentClip,
            weakUncertainClip
        ]

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )

        #expect(request.clips.map(\.label) == ["Kept Dark Shot", "No Team Finish", "Weak No Team Shot"])
        #expect(request.clips.first { $0.id == keptDarkClip.id.uuidString }?.userReviewDecision == "kept")
        #expect(request.clips.first { $0.id == uncertainTeamClip.id.uuidString }?.userReviewDecision == "unreviewed")
        #expect(request.clips.first { $0.id == confidentOpponentClip.id.uuidString } == nil)
        #expect(request.clips.first { $0.id == weakUncertainClip.id.uuidString }?.userReviewDecision == "unreviewed")
    }

    @Test func testCloudEditAutoKeepRequiresEvidenceBackedQuickScanTeamMatch() {
        let selection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )
        var clip = Clip(
            startTime: 12.0,
            endTime: 18.0,
            eventCenter: 15.0,
            action: .madeShot,
            confidence: 0.94,
            isKept: false,
            label: "Dark Jersey Finish",
            audioScore: 0.65,
            visualScore: 0.88,
            motionScore: 0.84,
            combinedScore: 0.9,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.96,
                source: "quick_scan"
            )
        )

        #expect(!HighlightsViewModel.isAutoKeepHighConfidenceEligible(clip, teamSelection: selection))

        clip.teamAttribution?.evidenceFrameRefs = ["setup_frame", "outcome_frame"]
        clip.teamAttribution?.evidenceRoleGroups = ["setup", "outcome"]

        #expect(HighlightsViewModel.isAutoKeepHighConfidenceEligible(clip, teamSelection: selection))
    }

    @Test func testCloudEditAutoKeepTreatsMissingTeamSourceAsUnknownEvidence() {
        let selection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )
        var clip = Clip(
            startTime: 12.0,
            endTime: 18.0,
            eventCenter: 15.0,
            action: .madeShot,
            confidence: 0.94,
            isKept: false,
            label: "Dark Jersey Finish",
            audioScore: 0.65,
            visualScore: 0.88,
            motionScore: 0.84,
            combinedScore: 0.9,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.96,
                source: nil
            )
        )

        #expect(!HighlightsViewModel.isAutoKeepHighConfidenceEligible(clip, teamSelection: selection))

        clip.teamAttribution?.source = "   "

        #expect(!HighlightsViewModel.isAutoKeepHighConfidenceEligible(clip, teamSelection: selection))

        clip.teamAttribution?.evidenceFrameRefs = ["setup_frame", "outcome_frame"]
        clip.teamAttribution?.evidenceRoleGroups = ["setup", "outcome"]

        #expect(HighlightsViewModel.isAutoKeepHighConfidenceEligible(clip, teamSelection: selection))
    }

    @Test @MainActor func testCloudEditRequestKeepsWeakOpponentEvidenceReviewableWhenUncertainAllowed() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        viewModel.settings.highlightTeamSelection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )

        let keptDarkClip = Clip(
            startTime: 8.0,
            endTime: 14.0,
            eventCenter: 11.0,
            action: .madeShot,
            confidence: 0.92,
            isKept: true,
            label: "Kept Dark Shot",
            audioScore: 0.7,
            visualScore: 0.85,
            motionScore: 0.82,
            combinedScore: 0.88,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.93,
                source: "quick_scan",
                evidenceFrameRefs: ["dark_setup", "dark_outcome"],
                evidenceRoleGroups: ["setup", "outcome"]
            )
        )
        let weakOpponentEvidenceSteal = Clip(
            startTime: 24.0,
            endTime: 29.0,
            eventCenter: 26.2,
            action: .steal,
            confidence: 0.84,
            isKept: false,
            label: "Possible Opponent-Labeled Steal",
            audioScore: 0.48,
            visualScore: 0.74,
            motionScore: 0.78,
            combinedScore: 0.82,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_light",
                label: "Light jerseys",
                colorLabel: "white",
                confidence: 0.94,
                source: "quick_scan"
            )
        )
        viewModel.analysisService.clips = [keptDarkClip, weakOpponentEvidenceSteal]

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )

        #expect(request.clips.map(\.label) == ["Kept Dark Shot", "Possible Opponent-Labeled Steal"])
        #expect(request.clips.first { $0.id == weakOpponentEvidenceSteal.id.uuidString }?.userReviewDecision == "unreviewed")
    }

    @Test @MainActor func testCloudEditRequestCanDisableUncertainTeamCandidateReserve() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        viewModel.settings.highlightTeamSelection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85,
            includeUncertain: false
        )

        let keptDarkClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000031")!,
            startTime: 10.0,
            endTime: 16.0,
            eventCenter: 13.0,
            action: .madeShot,
            confidence: 0.92,
            isKept: true,
            label: "Kept Dark Shot",
            audioScore: 0.7,
            visualScore: 0.85,
            motionScore: 0.82,
            combinedScore: 0.88,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.93,
                source: "team_scan"
            ),
            teamAttributionStatus: "matched"
        )
        let uncertainTeamClip = Clip(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000032")!,
            startTime: 24.0,
            endTime: 30.0,
            eventCenter: 27.0,
            action: .madeShot,
            confidence: 0.78,
            isKept: false,
            label: "No Team Finish",
            audioScore: 0.52,
            visualScore: 0.74,
            motionScore: 0.77,
            combinedScore: 0.81,
            detectionMethod: .cloud
        )
        viewModel.analysisService.clips = [keptDarkClip, uncertainTeamClip]

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )

        #expect(request.clips.map(\.label) == ["Kept Dark Shot"])
    }

    @Test func testCloudEditCandidateRankingReservesDefenseAndReviewClipsBeforeCap() {
        var clips: [Clip] = []
        for index in 0..<42 {
            clips.append(
                Clip(
                    startTime: Double(index * 8),
                    endTime: Double(index * 8) + 6,
                    eventCenter: Double(index * 8) + 3,
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
            )
        }
        let selectedTeamBlock = Clip(
            startTime: 400.0,
            endTime: 405.0,
            eventCenter: 402.5,
            action: .block,
            confidence: 0.68,
            isKept: true,
            label: "Block",
            audioScore: 0.2,
            visualScore: 0.62,
            motionScore: 0.66,
            combinedScore: 0.64,
            detectionMethod: .cloud
        )
        let selectedTeamSteal = Clip(
            startTime: 410.0,
            endTime: 415.0,
            eventCenter: 412.5,
            action: .steal,
            confidence: 0.67,
            isKept: true,
            label: "Steal",
            audioScore: 0.2,
            visualScore: 0.61,
            motionScore: 0.65,
            combinedScore: 0.63,
            detectionMethod: .cloud
        )
        let reviewClip = Clip(
            startTime: 420.0,
            endTime: 425.0,
            eventCenter: 422.5,
            action: .madeShot,
            confidence: 0.66,
            isKept: true,
            label: "Possible Team Finish",
            audioScore: 0.2,
            visualScore: 0.6,
            motionScore: 0.64,
            combinedScore: 0.62,
            detectionMethod: .cloud,
            nativeShotSignals: NativeShotSignals(
                isShotLike: true,
                leadInSeconds: 2.5,
                followThroughSeconds: 2.5,
                setupContextScore: 0.6,
                outcomeContextScore: 0.3,
                eventCenterQuality: 0.6,
                contextQualityScore: 0.58,
                timingWindowOk: true,
                outcome: "uncertain",
                outcomeConfidence: 0.2
            ),
            teamAttributionStatus: "uncertain"
        )

        let ranked = HighlightsViewModel.rankedCloudEditCandidateClips(
            from: clips + [selectedTeamBlock, selectedTeamSteal, reviewClip],
            limit: 40
        )
        let labels = Set(ranked.map(\.label))

        #expect(ranked.count == 40)
        #expect(labels.contains("Block"))
        #expect(labels.contains("Steal"))
        #expect(labels.contains("Possible Team Finish"))
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

    @Test func testCloudEditCandidateRankingUsesBackendMinimumShotContext() {
        let marginalPreBasketWindow = Clip(
            startTime: 10.0,
            endTime: 13.0,
            eventCenter: 10.9,
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
            endTime: 25.0,
            eventCenter: 22.0,
            action: .madeShot,
            confidence: 0.76,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.46,
            visualScore: 0.68,
            motionScore: 0.7,
            combinedScore: 0.7,
            detectionMethod: .cloud
        )

        let ranked = HighlightsViewModel.rankedCloudEditCandidateClips(
            from: [marginalPreBasketWindow, completeShot],
            limit: 1
        )

        #expect(ranked.first?.startTime == 20.0)
    }

    @Test @MainActor func testCloudEditRequestDoesNotSendLatePreBasketShotCandidate() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        viewModel.settings.highlightTeamSelection = .allTeams
        let latePreBasketOnly = Clip(
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
        viewModel.analysisService.clips = [latePreBasketOnly, completeShot]

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )

        #expect(request.clips.map(\.start) == [20.0])
    }

    @Test @MainActor func testCloudEditRequestTagsOverlappingSameMomentDuplicateGroups() throws {
        let viewModel = HighlightsViewModel()
        viewModel.cloudEditSourceObjectKey = "uploads/source.mp4"
        viewModel.settings.highlightTeamSelection = .allTeams
        let firstWindow = Clip(
            startTime: 10.0,
            endTime: 16.0,
            eventCenter: 13.0,
            action: .madeShot,
            confidence: 0.82,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.5,
            visualScore: 0.7,
            motionScore: 0.74,
            combinedScore: 0.78,
            detectionMethod: .cloud
        )
        let overlappingWindow = Clip(
            startTime: 10.4,
            endTime: 16.2,
            eventCenter: 13.2,
            action: .madeShot,
            confidence: 0.80,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.48,
            visualScore: 0.68,
            motionScore: 0.72,
            combinedScore: 0.76,
            detectionMethod: .cloud
        )
        let separateWindow = Clip(
            startTime: 28.0,
            endTime: 34.0,
            eventCenter: 31.0,
            action: .madeShot,
            confidence: 0.79,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.5,
            visualScore: 0.69,
            motionScore: 0.73,
            combinedScore: 0.75,
            detectionMethod: .cloud
        )
        viewModel.analysisService.clips = [firstWindow, overlappingWindow, separateWindow]

        let request = try viewModel.createCloudEditRequest(
            preset: .personalHighlight,
            targetDurationSeconds: 30,
            isProUser: false
        )

        let firstGroup = try #require(request.clips.first { $0.start == 10.0 }?.duplicateGroup)
        let overlappingGroup = try #require(request.clips.first { $0.start == 10.4 }?.duplicateGroup)
        let separateGroup = request.clips.first { $0.start == 28.0 }?.duplicateGroup

        #expect(firstGroup == overlappingGroup)
        #expect(firstGroup.hasPrefix("dup_shot_"))
        #expect(separateGroup == nil)
    }

    @Test func testCloudEditDuplicateGroupsDoNotMergeDifferentAttributedTeams() {
        let firstTeam = ClipTeamAttribution(
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidence: 0.92,
            source: "quick_scan",
            evidenceFrameRefs: [],
            evidenceRoleGroups: []
        )
        let secondTeam = ClipTeamAttribution(
            teamId: "team_light",
            label: "Light jerseys",
            colorLabel: "white",
            confidence: 0.91,
            source: "quick_scan",
            evidenceFrameRefs: [],
            evidenceRoleGroups: []
        )
        let darkClip = Clip(
            startTime: 10.0,
            endTime: 16.0,
            eventCenter: 13.0,
            action: .madeShot,
            confidence: 0.82,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.5,
            visualScore: 0.7,
            motionScore: 0.74,
            combinedScore: 0.78,
            detectionMethod: .cloud,
            teamAttribution: firstTeam,
            teamAttributionStatus: "matched"
        )
        let lightClip = Clip(
            startTime: 10.3,
            endTime: 16.1,
            eventCenter: 13.1,
            action: .madeShot,
            confidence: 0.80,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.48,
            visualScore: 0.68,
            motionScore: 0.72,
            combinedScore: 0.76,
            detectionMethod: .cloud,
            teamAttribution: secondTeam,
            teamAttributionStatus: "matched"
        )

        let duplicateGroups = HighlightsViewModel.cloudEditDuplicateGroupAssignments(for: [darkClip, lightClip])

        #expect(duplicateGroups.isEmpty)
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
        #expect(CloudEditProTemplate.teamHighlightPro.durationOptions == [90, 120, 180, 240, 270])
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
            "aiClipGptEditorEnabled": true,
            "aiClipGptPlanEditEnabled": true,
            "aiClipGptRevisionEnabled": true,
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
        #expect(response.featureFlags?.allowsGptClipEditing == true)
        #expect(response.featureFlags?.allowsGptPlanEditing == true)
        #expect(response.featureFlags?.allowsGptRevisionEditing == true)
        #expect(response.featureFlags?.gptHighlightRerankerEnabled == true)
        #expect(response.featureFlags?.hasRequiredLaunchReadinessFlags == true)
        #expect(response.featureFlags?.missingLaunchReadinessFlagNames.isEmpty == true)
    }

    @Test @MainActor func testCloudEditVersionFlagsReportMissingLaunchReadinessKeys() throws {
        let payload = """
        {
          "service": "hoopclips-editing",
          "backendModelVersion": "editing-cloud-v1",
          "gitSha": "stale-sha",
          "featureFlags": {
            "aiEditEnabled": true,
            "aiEditRevisionEnabled": true,
            "aiEditTemplatePackEnabled": true,
            "gptHighlightRerankerEnabled": true
          }
        }
        """.data(using: .utf8)!

        let response = try JSONDecoder().decode(CloudEditVersionResponse.self, from: payload)
        let flags = try #require(response.featureFlags)

        #expect(flags.hasRequiredLaunchReadinessFlags == false)
        #expect(flags.missingLaunchReadinessFlagNames == [
            "aiEditLiveRenderEnabled",
            "aiClipGptEditorEnabled",
            "aiClipGptPlanEditEnabled",
            "aiClipGptRevisionEnabled"
        ])
        #expect(flags.allowsGptClipEditing == true)
        #expect(flags.allowsGptPlanEditing == false)
        #expect(flags.allowsGptRevisionEditing == false)
    }

    @Test func testCloudEditStatusRefreshPolicyDoesNotBlockTransientVersionFailures() {
        let gatewayTimeout = CloudEditError.backend(code: "http_504", message: "Request timed out.")
        let urlTimeout = URLError(.timedOut)

        #expect(!CloudEditStatusRefreshPolicy.blocksRendering(for: gatewayTimeout))
        #expect(!CloudEditStatusRefreshPolicy.blocksRendering(for: urlTimeout))
        #expect(CloudEditStatusRefreshPolicy.statusMessage(for: gatewayTimeout) == "Cloud status is slow. You can still start the edit.")
        #expect(CloudEditStatusRefreshPolicy.statusMessage(for: urlTimeout) == "Cloud status is slow. You can still start the edit.")
    }

    @Test func testCloudEditStatusRefreshPolicyBlocksRealConfigFailures() {
        let unauthorized = CloudEditError.backend(code: "http_401", message: "Cloud editing auth failed.")

        #expect(CloudEditStatusRefreshPolicy.blocksRendering(for: CloudEditError.notConfigured))
        #expect(CloudEditStatusRefreshPolicy.blocksRendering(for: CloudEditError.invalidResponse))
        #expect(CloudEditStatusRefreshPolicy.blocksRendering(for: unauthorized))
        #expect(CloudEditStatusRefreshPolicy.statusMessage(for: unauthorized) == "Cloud editing auth failed.")
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
        let teamAttribution = ClipTeamAttribution(
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidence: 0.91,
            source: "quick_scan",
            evidenceFrameRefs: ["clip_0_release", "clip_0_result"],
            evidenceRoleGroups: ["action", "outcome"]
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
            nativeShotSignals: nativeSignals,
            teamAttribution: teamAttribution,
            teamAttributionStatus: "matched"
        )

        let mapped = cloudClip.makeClip()

        #expect(mapped.action == .dunk)
        #expect(mapped.detectionMethod == .cloud)
        #expect(mapped.isKept)
        #expect(mapped.isSlowMotionEnabled)
        #expect(abs(mapped.duration - 4.5) < 0.001)
        #expect(mapped.eventCenter == 15.2)
        #expect(mapped.nativeShotSignals == nativeSignals)
        #expect(mapped.teamAttribution == teamAttribution)
        #expect(mapped.teamAttribution?.evidenceFrameRefs == ["clip_0_release", "clip_0_result"])
        #expect(mapped.teamAttribution?.evidenceRoleGroups == ["action", "outcome"])
        #expect(mapped.teamAttributionStatus == "matched")
    }

    @Test func testClipTeamAttributionDecodesWithoutEvidenceMetadataForCachedResults() throws {
        let data = Data(
            """
            {
              "teamId": "team_dark",
              "label": "Dark jerseys",
              "colorLabel": "black",
              "confidence": 0.91,
              "source": "quick_scan"
            }
            """.utf8
        )

        let decoded = try JSONDecoder().decode(ClipTeamAttribution.self, from: data)

        #expect(decoded.teamId == "team_dark")
        #expect(decoded.evidenceFrameRefs == nil)
        #expect(decoded.evidenceRoleGroups == nil)
    }

    @Test func testClipReviewBadgesMarkUncertainTeamOutcomeAndTiming() {
        let nativeSignals = NativeShotSignals(
            isShotLike: true,
            leadInSeconds: 0.2,
            followThroughSeconds: 0.1,
            setupContextScore: 0.12,
            outcomeContextScore: 0.08,
            eventCenterQuality: 0.2,
            contextQualityScore: 0.25,
            timingWindowOk: false,
            outcome: "uncertain",
            outcomeConfidence: 0.0
        )
        let clip = Clip(
            startTime: 10.0,
            endTime: 12.2,
            eventCenter: 10.1,
            action: .madeShot,
            confidence: 0.74,
            isKept: false,
            label: "Shot Attempt",
            audioScore: 0.4,
            visualScore: 0.5,
            motionScore: 0.62,
            combinedScore: 0.7,
            detectionMethod: .cloud,
            nativeShotSignals: nativeSignals,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.64,
                source: "gpt_frame_review"
            ),
            teamAttributionStatus: "uncertain"
        )

        #expect(clip.needsUserReview)
        #expect(clip.reviewBadges == [.teamUncertain, .outcomeUncertain, .timingUncertain])
        #expect(clip.reviewBadges.map(\.title) == ["Team?", "Outcome?", "Timing?"])
        #expect(clip.reviewEvidenceRows.map(\.id) == ["decision", "keyframes", "team", "outcome", "timing"])
        #expect(clip.reviewEvidenceRows.first?.title == "Why kept")
        #expect(clip.reviewEvidenceRows.first?.needsReview == true)
        #expect(clip.reviewEvidenceRows.contains { $0.title == "Team needs check" && $0.detail.contains("64% confidence") })
        #expect(clip.reviewEvidenceRows.contains { $0.title == "Outcome needs check" })
        #expect(clip.reviewEvidenceRows.contains { $0.title == "Timing needs check" && $0.detail.contains("setup 0.2s") })
    }

    @Test func testClipReviewBadgesMarkMissingTeamAttributionStatusUncertain() {
        let clip = Clip(
            startTime: 18.0,
            endTime: 22.0,
            eventCenter: 20.0,
            action: .block,
            confidence: 0.71,
            isKept: true,
            label: "Possible Block",
            audioScore: 0.42,
            visualScore: 0.72,
            motionScore: 0.69,
            combinedScore: 0.76,
            detectionMethod: .cloud,
            teamAttribution: nil,
            teamAttributionStatus: "uncertain"
        )

        #expect(clip.needsUserReview)
        #expect(clip.reviewBadges == [.teamUncertain])
        #expect(clip.reviewEvidenceRows.contains { $0.title == "Team needs check" && $0.detail.contains("No confident team evidence") })
    }

    @Test func testClipReviewEvidenceRowsShowConfidentTeamAndKeyMoments() {
        let clip = Clip(
            startTime: 8.0,
            endTime: 14.5,
            eventCenter: 11.0,
            action: .steal,
            confidence: 0.88,
            isKept: true,
            label: "Steal Into Layup",
            audioScore: 0.62,
            visualScore: 0.81,
            motionScore: 0.86,
            combinedScore: 0.9,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_blue",
                label: "Eastside 17U",
                colorLabel: "blue",
                confidence: 0.92,
                source: "quick_scan",
                evidenceFrameRefs: ["clip_start", "clip_finish"],
                evidenceRoleGroups: ["action", "outcome"]
            ),
            teamAttributionStatus: "matched"
        )

        #expect(clip.reviewEvidenceRows.map(\.id) == ["decision", "keyframes", "team", "defense"])
        #expect(clip.reviewEvidenceRows[0].detail.contains("defensive highlight"))
        #expect(clip.reviewEvidenceRows[1].detail == "Start 0:08.0 · Action 0:11.0 · Finish 0:14.5")
        #expect(clip.reviewEvidenceRows[2].title == "Team evidence")
        #expect(clip.reviewEvidenceRows[2].detail.contains("Eastside 17U, 92% confidence"))
        #expect(clip.reviewEvidenceRows[2].detail.contains("frames: action, outcome"))
        #expect(clip.reviewEvidenceRows[3].title == "Defensive cue")
        #expect(clip.reviewEvidenceRows[3].detail.contains("Blocks, steals"))
    }

    @Test func testClipReviewEvidenceRowsTreatTurnoverPressureAsDefense() {
        let clip = Clip(
            startTime: 18.0,
            endTime: 22.5,
            eventCenter: 20.2,
            action: .unknown,
            confidence: 0.79,
            isKept: true,
            label: "Loose Ball Takeaway",
            audioScore: 0.44,
            visualScore: 0.75,
            motionScore: 0.82,
            combinedScore: 0.78,
            detectionMethod: .cloud
        )

        #expect(clip.reviewEvidenceRows.map(\.id) == ["decision", "keyframes", "defense"])
        #expect(clip.reviewEvidenceRows[0].detail.contains("defensive highlight"))
        #expect(clip.reviewEvidenceRows[0].detail.contains("possession-change"))
        #expect(clip.reviewEvidenceRows[2].title == "Defensive cue")
        #expect(clip.reviewEvidenceRows[2].detail.contains("forced turnovers"))
    }

    @Test func testClipReviewEvidenceRowsShowCrowdAudioCueForLoudReactions() {
        let clip = Clip(
            startTime: 24.0,
            endTime: 29.0,
            eventCenter: 26.4,
            action: .unknown,
            confidence: 0.62,
            isKept: false,
            label: "Audio Pop Cue",
            audioScore: 0.94,
            visualScore: 0.48,
            motionScore: 0.52,
            combinedScore: 0.67,
            detectionMethod: .cloud
        )

        #expect(clip.reviewEvidenceRows.map(\.id) == ["decision", "keyframes", "audio"])
        #expect(clip.reviewEvidenceRows[2].title == "Crowd/audio cue")
        #expect(clip.reviewEvidenceRows[2].detail.contains("Audio peak 94%"))
        #expect(clip.reviewEvidenceRows[2].detail.contains("play outcome is visible"))
        #expect(clip.reviewEvidenceRows[2].needsReview)
    }

    @Test @MainActor func testViewModelExposesNeedsReviewClipsForReviewFilter() {
        let viewModel = HighlightsViewModel()
        let selectedTeam = HighlightTeamSelection(
            mode: .team,
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )
        viewModel.settings.highlightTeamSelection = selectedTeam
        defer { viewModel.settings.highlightTeamSelection = .allTeams }
        let cleanClip = Clip(
            startTime: 4.0,
            endTime: 8.0,
            eventCenter: 6.0,
            action: .madeShot,
            confidence: 0.93,
            isKept: true,
            label: "Made Shot",
            audioScore: 0.72,
            visualScore: 0.88,
            motionScore: 0.82,
            combinedScore: 0.9,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.93,
                source: "quick_scan"
            ),
            teamAttributionStatus: "matched"
        )
        let uncertainClip = Clip(
            startTime: 18.0,
            endTime: 22.0,
            eventCenter: 20.0,
            action: .steal,
            confidence: 0.71,
            isKept: true,
            label: "Possible Steal",
            audioScore: 0.42,
            visualScore: 0.72,
            motionScore: 0.69,
            combinedScore: 0.76,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.64,
                source: "gpt_frame_review"
            ),
            teamAttributionStatus: "uncertain"
        )

        viewModel.analysisService.clips = [cleanClip, uncertainClip]

        #expect(viewModel.needsReviewClips.map(\.label) == ["Possible Steal"])
    }

    @Test func testAllTeamsModeSuppressesTeamOnlyReviewNoise() {
        let uncertainTeamClip = Clip(
            startTime: 18.0,
            endTime: 22.0,
            eventCenter: 20.0,
            action: .madeShot,
            confidence: 0.88,
            isKept: true,
            label: "Ambiguous Jersey Bucket",
            audioScore: 0.42,
            visualScore: 0.72,
            motionScore: 0.69,
            combinedScore: 0.76,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.64,
                source: "gpt_frame_review"
            ),
            teamAttributionStatus: "uncertain"
        )

        #expect(!HighlightsViewModel.needsTeamReview(uncertainTeamClip, teamSelection: .allTeams))
        #expect(HighlightsViewModel.reviewBadges(for: uncertainTeamClip, teamSelection: .allTeams).isEmpty)
        #expect(!HighlightsViewModel.needsUserReview(uncertainTeamClip, teamSelection: .allTeams))
        #expect(!HighlightsViewModel.isPriorityReviewClip(uncertainTeamClip, teamSelection: .allTeams))
        #expect(HighlightsViewModel.isAutoKeepHighConfidenceEligible(uncertainTeamClip, teamSelection: .allTeams))
    }

    @Test func testSelectedTeamModeKeepsTeamReviewSignal() {
        let selectedTeam = HighlightTeamSelection(
            mode: .team,
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )
        let uncertainTeamClip = Clip(
            startTime: 18.0,
            endTime: 22.0,
            eventCenter: 20.0,
            action: .madeShot,
            confidence: 0.88,
            isKept: true,
            label: "Ambiguous Jersey Bucket",
            audioScore: 0.42,
            visualScore: 0.72,
            motionScore: 0.69,
            combinedScore: 0.76,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.64,
                source: "gpt_frame_review"
            ),
            teamAttributionStatus: "uncertain"
        )

        #expect(HighlightsViewModel.needsTeamReview(uncertainTeamClip, teamSelection: selectedTeam))
        #expect(HighlightsViewModel.reviewBadges(for: uncertainTeamClip, teamSelection: selectedTeam) == [.teamUncertain])
        #expect(HighlightsViewModel.needsUserReview(uncertainTeamClip, teamSelection: selectedTeam))
        #expect(HighlightsViewModel.isPriorityReviewClip(uncertainTeamClip, teamSelection: selectedTeam))
        #expect(!HighlightsViewModel.isAutoKeepHighConfidenceEligible(uncertainTeamClip, teamSelection: selectedTeam))
    }

    @Test func testDetectedTeamStatusCopyAvoidsCrammingLongTeamNames() {
        let labels = [
            "Westside Elite National 17U Black Jerseys",
            "Eastside Lightning Select White Jerseys"
        ]

        #expect(HighlightTeamTargetCopy.detectedStatusText(teamLabels: labels, requiresSelection: false) == "2 teams found. Choose one or All teams.")
        #expect(HighlightTeamTargetCopy.detectedStatusText(teamLabels: labels, requiresSelection: true) == "Choose one team or All teams.")
        #expect(HighlightTeamTargetCopy.detectedStatusText(teamLabels: [labels[0]], requiresSelection: false) == "1 team found. Choose it or All teams.")
    }

    @Test func testAllTeamsStillPrioritizesDefensiveClipsWithoutTeamReviewBadge() {
        let uncertainStealClip = Clip(
            startTime: 18.0,
            endTime: 22.0,
            eventCenter: 20.0,
            action: .steal,
            confidence: 0.71,
            isKept: false,
            label: "Possible Steal",
            audioScore: 0.42,
            visualScore: 0.72,
            motionScore: 0.69,
            combinedScore: 0.76,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.64,
                source: "gpt_frame_review"
            ),
            teamAttributionStatus: "uncertain"
        )

        #expect(HighlightsViewModel.reviewBadges(for: uncertainStealClip, teamSelection: .allTeams).isEmpty)
        #expect(HighlightsViewModel.isStealReviewClip(uncertainStealClip))
        #expect(HighlightsViewModel.isPriorityReviewClip(uncertainStealClip, teamSelection: .allTeams))
    }

    @Test func testContestReviewClipIsDefensiveStopNotBlock() {
        let contestedClip = Clip(
            startTime: 12.0,
            endTime: 17.5,
            eventCenter: 15.0,
            action: .unknown,
            confidence: 0.76,
            isKept: true,
            label: "Contested Jumper",
            audioScore: 0.5,
            visualScore: 0.78,
            motionScore: 0.8,
            combinedScore: 0.82,
            detectionMethod: .cloud
        )

        #expect(HighlightsViewModel.isDefensiveReviewClip(contestedClip))
        #expect(HighlightsViewModel.isDefensiveStopReviewClip(contestedClip))
        #expect(!HighlightsViewModel.isBlockReviewClip(contestedClip))
        #expect(!HighlightsViewModel.isStealReviewClip(contestedClip))
    }

    @Test @MainActor func testViewModelPriorityReviewClipsFocusTeamDefenseAndUncertainPlays() {
        let viewModel = HighlightsViewModel()
        let selectedTeam = HighlightTeamSelection(
            mode: .team,
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )
        viewModel.settings.highlightTeamSelection = selectedTeam
        defer { viewModel.settings.highlightTeamSelection = .allTeams }

        let cleanClip = Clip(
            startTime: 4.0,
            endTime: 8.0,
            eventCenter: 6.0,
            action: .madeShot,
            confidence: 0.93,
            isKept: true,
            label: "Clean Made Shot",
            visualScore: 0.88,
            motionScore: 0.82,
            combinedScore: 0.9,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.94,
                source: "quick_scan"
            ),
            teamAttributionStatus: "matched"
        )
        let blockClip = Clip(
            startTime: 12.0,
            endTime: 15.5,
            eventCenter: 13.7,
            action: .block,
            confidence: 0.48,
            isKept: false,
            label: "Weak Side Block",
            visualScore: 0.72,
            motionScore: 0.81,
            combinedScore: 0.56,
            detectionMethod: .cloud
        )
        let pressureClip = Clip(
            startTime: 18.0,
            endTime: 22.5,
            eventCenter: 20.1,
            action: .unknown,
            confidence: 0.62,
            isKept: true,
            label: "Full Court Pressure Stop",
            visualScore: 0.74,
            motionScore: 0.83,
            combinedScore: 0.67,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.91,
                source: "quick_scan"
            ),
            teamAttributionStatus: "matched"
        )
        let uncertainTeamClip = Clip(
            startTime: 28.0,
            endTime: 32.0,
            eventCenter: 30.0,
            action: .madeShot,
            confidence: 0.72,
            isKept: true,
            label: "Possible Dark Shot",
            visualScore: 0.69,
            motionScore: 0.73,
            combinedScore: 0.76,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.63,
                source: "gpt_frame_review"
            ),
            teamAttributionStatus: "uncertain"
        )
        let missingTeamClip = Clip(
            startTime: 36.0,
            endTime: 40.0,
            eventCenter: 38.0,
            action: .layup,
            confidence: 0.81,
            isKept: true,
            label: "Possible Dark Layup",
            visualScore: 0.78,
            motionScore: 0.8,
            combinedScore: 0.82,
            detectionMethod: .cloud
        )

        viewModel.analysisService.clips = [
            cleanClip,
            blockClip,
            pressureClip,
            uncertainTeamClip,
            missingTeamClip
        ]

        #expect(viewModel.priorityReviewClips.map(\.label) == [
            "Weak Side Block",
            "Full Court Pressure Stop",
            "Possible Dark Shot",
            "Possible Dark Layup"
        ])
        #expect(!HighlightsViewModel.isPriorityReviewClip(cleanClip, teamSelection: selectedTeam))
        #expect(HighlightsViewModel.isBlockReviewClip(blockClip))
        #expect(HighlightsViewModel.isDefensiveReviewClip(pressureClip))
        #expect(HighlightsViewModel.needsTeamReview(missingTeamClip, teamSelection: selectedTeam))
    }

    @Test @MainActor func testKeepHighConfidenceDoesNotAutoKeepNeedsReviewClips() {
        let viewModel = HighlightsViewModel()
        let cleanHighConfidence = Clip(
            startTime: 4.0,
            endTime: 8.5,
            eventCenter: 6.0,
            action: .madeShot,
            confidence: 0.91,
            isKept: false,
            label: "Made Shot",
            audioScore: 0.72,
            visualScore: 0.88,
            motionScore: 0.82,
            combinedScore: 0.9,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.93,
                source: "quick_scan"
            ),
            teamAttributionStatus: "matched"
        )
        let uncertainHighConfidence = Clip(
            startTime: 18.0,
            endTime: 22.5,
            eventCenter: 20.0,
            action: .steal,
            confidence: 0.94,
            isKept: false,
            label: "Possible Steal",
            audioScore: 0.42,
            visualScore: 0.72,
            motionScore: 0.69,
            combinedScore: 0.86,
            detectionMethod: .cloud,
            nativeShotSignals: NativeShotSignals(
                isShotLike: true,
                leadInSeconds: 2.0,
                followThroughSeconds: 2.5,
                setupContextScore: 0.6,
                outcomeContextScore: 0.3,
                eventCenterQuality: 0.6,
                contextQualityScore: 0.58,
                timingWindowOk: true,
                outcome: "uncertain",
                outcomeConfidence: 0.2
            ),
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.64,
                source: "gpt_frame_review"
            ),
            teamAttributionStatus: "uncertain"
        )

        viewModel.analysisService.clips = [cleanHighConfidence, uncertainHighConfidence]
        viewModel.keepHighConfidenceClips()

        #expect(viewModel.keptClips.map(\.label) == ["Made Shot"])
        #expect(viewModel.discardedClips.map(\.label) == ["Possible Steal"])
        #expect(viewModel.needsReviewClips.map(\.label) == ["Possible Steal"])
    }

    @Test @MainActor func testKeepHighConfidenceRespectsSelectedHighlightTeam() {
        let viewModel = HighlightsViewModel()
        viewModel.settings.highlightTeamSelection = HighlightTeamSelection(
            mode: .team,
            teamId: "team_dark",
            label: "Dark jerseys",
            colorLabel: "black",
            confidenceThreshold: 0.85,
            includeUncertain: true
        )
        defer { viewModel.settings.highlightTeamSelection = .allTeams }
        let darkTeamClip = Clip(
            startTime: 4.0,
            endTime: 8.5,
            eventCenter: 6.0,
            action: .madeShot,
            confidence: 0.91,
            isKept: false,
            label: "Dark Made Shot",
            audioScore: 0.72,
            visualScore: 0.88,
            motionScore: 0.82,
            combinedScore: 0.9,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black",
                confidence: 0.93,
                source: "quick_scan",
                evidenceFrameRefs: ["dark_setup", "dark_outcome"],
                evidenceRoleGroups: ["setup", "outcome"]
            ),
            teamAttributionStatus: "matched"
        )
        let otherTeamClip = Clip(
            startTime: 12.0,
            endTime: 16.5,
            eventCenter: 14.0,
            action: .madeShot,
            confidence: 0.92,
            isKept: false,
            label: "Light Made Shot",
            audioScore: 0.70,
            visualScore: 0.86,
            motionScore: 0.80,
            combinedScore: 0.88,
            detectionMethod: .cloud,
            teamAttribution: ClipTeamAttribution(
                teamId: "team_light",
                label: "Light jerseys",
                colorLabel: "white",
                confidence: 0.94,
                source: "quick_scan",
                evidenceFrameRefs: ["light_setup", "light_outcome"],
                evidenceRoleGroups: ["setup", "outcome"]
            ),
            teamAttributionStatus: "matched"
        )
        let noTeamClip = Clip(
            startTime: 22.0,
            endTime: 26.5,
            eventCenter: 24.0,
            action: .madeShot,
            confidence: 0.93,
            isKept: false,
            label: "No Team Shot",
            audioScore: 0.68,
            visualScore: 0.84,
            motionScore: 0.78,
            combinedScore: 0.87,
            detectionMethod: .cloud
        )

        viewModel.analysisService.clips = [darkTeamClip, otherTeamClip, noTeamClip]
        viewModel.keepHighConfidenceClips()

        #expect(viewModel.keptClips.map(\.label) == ["Dark Made Shot"])
        #expect(viewModel.discardedClips.map(\.label) == ["Light Made Shot", "No Team Shot"])
        #expect(HighlightsViewModel.isAutoKeepHighConfidenceEligible(darkTeamClip))
        #expect(HighlightsViewModel.isAutoKeepHighConfidenceEligible(otherTeamClip))
        #expect(!HighlightsViewModel.isAutoKeepHighConfidenceEligible(
            otherTeamClip,
            teamSelection: HighlightTeamSelection(
                mode: .team,
                teamId: "team_dark",
                label: "Dark jerseys",
                colorLabel: "black"
            )
        ))
    }

    @Test @MainActor func testDiscardLowConfidencePreservesReviewAndDefensiveClips() {
        let viewModel = HighlightsViewModel()
        let lowBoringClip = Clip(
            startTime: 2.0,
            endTime: 5.0,
            action: .unknown,
            confidence: 0.32,
            isKept: true,
            label: "Loose camera movement",
            combinedScore: 0.18
        )
        let lowUncertainSteal = Clip(
            startTime: 8.0,
            endTime: 12.0,
            eventCenter: 10.0,
            action: .steal,
            confidence: 0.42,
            isKept: true,
            label: "Possible Steal",
            combinedScore: 0.48,
            teamAttributionStatus: "uncertain"
        )
        let lowBlock = Clip(
            startTime: 18.0,
            endTime: 22.0,
            eventCenter: 20.0,
            action: .block,
            confidence: 0.44,
            isKept: true,
            label: "Possible Block",
            combinedScore: 0.52
        )
        let lowDefensiveStop = Clip(
            startTime: 26.0,
            endTime: 31.0,
            eventCenter: 28.0,
            action: .unknown,
            confidence: 0.38,
            isKept: true,
            label: "Defensive Stop",
            combinedScore: 0.46
        )

        viewModel.analysisService.clips = [
            lowBoringClip,
            lowUncertainSteal,
            lowBlock,
            lowDefensiveStop
        ]
        viewModel.discardLowConfidenceClips()

        #expect(viewModel.discardedClips.map(\.label) == ["Loose camera movement"])
        #expect(viewModel.keptClips.map(\.label) == ["Possible Steal", "Possible Block", "Defensive Stop"])
        #expect(HighlightsViewModel.protectsClipFromQuickSkip(lowUncertainSteal))
        #expect(HighlightsViewModel.protectsClipFromQuickSkip(lowBlock))
        #expect(HighlightsViewModel.protectsClipFromQuickSkip(lowDefensiveStop))
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
            "maxRenderSeconds": 270,
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
            "gptUncertainReviewClipCount": 1,
            "gptUncertainReviewClipIds": ["uncertain_steal"],
            "summaryRows": [
              "Selected 2 clips from 3 candidates.",
              "Kept 1 uncertain team candidate available for Review.",
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
        #expect(response.workReceipt?.gptUncertainReviewClipCount == 1)
        #expect(response.workReceipt?.gptUncertainReviewClipIds == ["uncertain_steal"])
        #expect(response.workReceipt?.summaryRows.contains("Kept 1 uncertain team candidate available for Review.") == true)
    }

    @Test @MainActor func testCloudEditJobResponseDecodesUncertainReviewClipIds() throws {
        let payload = """
        {
          "editJobId": "edit_123",
          "videoId": "video_123",
          "analysisJobId": "analysis_123",
          "status": "plan_ready",
          "preset": "personal_highlight",
          "templateId": "personal_highlight_v1",
          "planTier": "free",
          "policy": null,
          "targetDurationSeconds": 30,
          "aspectRatio": "9:16",
          "clipCount": 2,
          "validationErrors": [],
          "gptUncertainReviewClipIds": ["uncertain_steal"],
          "gptUncertainReviewClipCount": 1
        }
        """

        let response = try JSONDecoder().decode(CloudEditJobResponse.self, from: Data(payload.utf8))

        #expect(response.editJobId == "edit_123")
        #expect(response.gptUncertainReviewClipIds == ["uncertain_steal"])
        #expect(response.gptUncertainReviewClipCount == 1)
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
                finalSegments: 3,
                usedTeamQuickScan: nil,
                preTeamFilterSegments: nil,
                teamMatchedCandidateSegments: nil,
                teamUncertainCandidateSegments: nil,
                teamOpponentFilteredSegments: nil,
                teamMatchedReviewSegments: nil,
                teamUncertainReviewSegments: nil,
                defensiveReviewSegments: nil,
                blockReviewSegments: nil,
                stealReviewSegments: nil,
                forcedTurnoverReviewSegments: nil,
                defensiveStopReviewSegments: nil
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

private func makeCloudAnalysisSession(
    handler: @escaping (URLRequest) throws -> (HTTPURLResponse, Data)
) -> URLSession {
    CloudAnalysisMockURLProtocol.requestHandler = handler
    let configuration = URLSessionConfiguration.ephemeral
    configuration.protocolClasses = [CloudAnalysisMockURLProtocol.self]
    return URLSession(configuration: configuration)
}

private func cloudAnalysisJSONResponse(for request: URLRequest, body: String) throws -> (HTTPURLResponse, Data) {
    let url = try #require(request.url)
    let response = try #require(
        HTTPURLResponse(
            url: url,
            statusCode: 200,
            httpVersion: nil,
            headerFields: ["Content-Type": "application/json"]
        )
    )
    return (response, Data(body.utf8))
}

private func cloudAnalysisEmptyResponse(
    for request: URLRequest,
    statusCode: Int
) throws -> (HTTPURLResponse, Data) {
    let url = try #require(request.url)
    let response = try #require(
        HTTPURLResponse(
            url: url,
            statusCode: statusCode,
            httpVersion: nil,
            headerFields: nil
        )
    )
    return (response, Data())
}

private func cloudAnalysisJSONObject(from data: Data) throws -> [String: Any] {
    let value = try JSONSerialization.jsonObject(with: data)
    return try #require(value as? [String: Any])
}

private func cloudAnalysisRequestBodyData(from request: URLRequest) throws -> Data {
    if let body = request.httpBody {
        return body
    }
    guard let stream = request.httpBodyStream else {
        throw CloudAnalysisError.invalidResponse
    }
    stream.open()
    defer { stream.close() }

    var data = Data()
    var buffer = [UInt8](repeating: 0, count: 1024)
    while stream.hasBytesAvailable {
        let count = stream.read(&buffer, maxLength: buffer.count)
        if count < 0 {
            throw stream.streamError ?? CloudAnalysisError.invalidResponse
        }
        if count == 0 {
            break
        }
        data.append(buffer, count: count)
    }
    return data
}

private final class CloudAnalysisMockURLProtocol: URLProtocol {
    static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        guard let handler = Self.requestHandler else {
            client?.urlProtocol(self, didFailWithError: CloudAnalysisError.network("missing test handler"))
            return
        }

        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}
