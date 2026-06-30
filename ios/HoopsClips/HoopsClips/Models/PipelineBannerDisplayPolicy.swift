import Foundation

nonisolated enum PipelineBannerDisplayPolicy {
    static func shouldShow(
        videoLoaded: Bool,
        hasVideoURL: Bool,
        importInProgress: Bool,
        analysisIsAnalyzing: Bool,
        activeTabIsReview: Bool,
        rookieGuideVisible: Bool
    ) -> Bool {
        guard !activeTabIsReview, !rookieGuideVisible else { return false }
        guard importInProgress || analysisIsAnalyzing else { return false }

        let hasSelectedVideo = videoLoaded && hasVideoURL
        return importInProgress || hasSelectedVideo
    }

    static func compactUploadDetail(
        liveDetail: String?,
        savedResumeDetail: String?,
        optimizationFact: String?
    ) -> String? {
        [liveDetail, savedResumeDetail, optimizationFact]
            .compactMap { $0?.trimmingCharacters(in: .whitespacesAndNewlines) }
            .first { !$0.isEmpty }
    }
}
