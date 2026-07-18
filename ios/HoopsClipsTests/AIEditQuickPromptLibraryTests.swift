import Testing
@testable import HoopsClips

struct AIEditQuickPromptLibraryTests {
    @Test func keepsCommonEditIntentsFirst() {
        #expect(AIEditQuickPromptLibrary.options.map(\.id) == [
            "hype",
            "personal",
            "team-recap",
            "defense",
            "recruiting",
            "recap",
            "long-reel",
            "clear-outcomes"
        ])
        #expect(AIEditQuickPromptLibrary.options.map(\.title) == [
            "Hype",
            "Solo",
            "Team",
            "Defense",
            "Recruit",
            "Recap",
            "Long reel",
            "Full plays"
        ])
    }

    @Test func keepsStudioAndProgressSurfacesMutuallyExclusive() {
        #expect(AIEditSurfaceDisplayPolicy.showsStudio(
            phase: .planning,
            isWorking: false,
            hasStartedJob: false
        ))
        #expect(!AIEditSurfaceDisplayPolicy.showsStudio(
            phase: .planning,
            isWorking: true,
            hasStartedJob: true
        ))
        #expect(!AIEditSurfaceDisplayPolicy.showsStudio(
            phase: .queued,
            isWorking: false,
            hasStartedJob: true
        ))
        #expect(AIEditSurfaceDisplayPolicy.showsStudio(
            phase: .rendered,
            isWorking: false,
            hasStartedJob: true
        ))
        #expect(AIEditSurfaceDisplayPolicy.showsStudio(
            phase: .failed,
            isWorking: false,
            hasStartedJob: true
        ))
    }

    @Test func matchesProgressStagesToThePostAnalysisFlow() {
        #expect(AIEditSurfaceDisplayPolicy.progressStageTitles == ["Plan", "Render", "Share"])
        #expect(!AIEditSurfaceDisplayPolicy.progressStageTitles.contains("Analyze"))
    }
}
