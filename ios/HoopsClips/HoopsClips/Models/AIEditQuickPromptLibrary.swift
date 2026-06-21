import Foundation

struct AIEditQuickPrompt: Identifiable, Equatable, Sendable {
    let id: String
    let title: String
    let prompt: String
    let icon: String
}

enum AIEditQuickPromptLibrary {
    static let options: [AIEditQuickPrompt] = [
        AIEditQuickPrompt(
            id: "hype",
            title: "Hype",
            prompt: "More hype. Prioritize clear made shots, blocks, steals, and big stops.",
            icon: "bolt.fill"
        ),
        AIEditQuickPrompt(
            id: "personal",
            title: "Solo",
            prompt: "Solo/player highlight: focus on one player when clear. Do not require team scan; use visible player cues, full makes, assists, blocks, steals, and best defense.",
            icon: "person.crop.circle.fill"
        ),
        AIEditQuickPrompt(
            id: "team-recap",
            title: "Team",
            prompt: "Clean team recap: balanced players, offense, defense, and game flow.",
            icon: "person.3.fill"
        ),
        AIEditQuickPrompt(
            id: "defense",
            title: "Defense",
            prompt: "Defense only: blocks, steals, forced turnovers, stops, deflections, and loose balls.",
            icon: "shield.lefthalf.filled"
        ),
        AIEditQuickPrompt(
            id: "recruiting",
            title: "Recruit",
            prompt: "Recruiting reel: keep full plays with clear outcomes, strong scoring, assists, defense, hustle, and no weak or unclear clips.",
            icon: "star.circle.fill"
        ),
        AIEditQuickPrompt(
            id: "recap",
            title: "Recap",
            prompt: "NBA-style recap: story flow, best makes, stops, assists, crowd pops, clean pacing, and clear outcomes.",
            icon: "sparkles"
        ),
        AIEditQuickPrompt(
            id: "long-reel",
            title: "Long",
            prompt: "Make this a longer 4:30 highlight reel with clear outcomes, defense, and crowd pops.",
            icon: "timer"
        )
    ]
}
