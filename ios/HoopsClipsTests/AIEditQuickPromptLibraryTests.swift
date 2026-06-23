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
}
