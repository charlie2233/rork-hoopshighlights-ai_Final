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
            title: "More hype",
            prompt: "More hype. Prioritize clear made shots, blocks, steals, and big stops.",
            icon: "bolt.fill"
        ),
        AIEditQuickPrompt(
            id: "defense",
            title: "Defense only",
            prompt: "Defense only: blocks, steals, forced turnovers, stops, deflections, and loose balls.",
            icon: "shield.lefthalf.filled"
        ),
        AIEditQuickPrompt(
            id: "long-reel",
            title: "Long reel",
            prompt: "Make this a longer 4:30 highlight reel with clear outcomes, defense, and crowd pops.",
            icon: "timer"
        ),
        AIEditQuickPrompt(
            id: "clear-outcomes",
            title: "Clear outcomes",
            prompt: "Keep clips with visible outcomes. Leave uncertain strong moments for review.",
            icon: "scope"
        ),
        AIEditQuickPrompt(
            id: "crowd-pop",
            title: "Crowd pops",
            prompt: "Use loud crowd pops as nearby highlight clues; keep only clear plays.",
            icon: "waveform"
        ),
        AIEditQuickPrompt(
            id: "team-recap",
            title: "Team recap",
            prompt: "Clean team recap: balanced players, offense, defense, and game flow.",
            icon: "person.3.fill"
        )
    ]
}
