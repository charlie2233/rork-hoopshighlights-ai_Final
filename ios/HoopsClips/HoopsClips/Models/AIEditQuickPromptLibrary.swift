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
            id: "personal",
            title: "Solo",
            prompt: "Solo/player highlight: focus on one player when clear. Do not require team scan; use visible player cues, full makes, assists, blocks, steals, and best defense.",
            icon: "person.crop.circle.fill"
        ),
        AIEditQuickPrompt(
            id: "hype",
            title: "Hype",
            prompt: "More hype. Prioritize clear made shots, blocks, steals, and big stops.",
            icon: "bolt.fill"
        ),
        AIEditQuickPrompt(
            id: "defense",
            title: "Defense",
            prompt: "Defense only: blocks, steals, forced turnovers, stops, deflections, and loose balls.",
            icon: "shield.lefthalf.filled"
        ),
        AIEditQuickPrompt(
            id: "long-reel",
            title: "Long",
            prompt: "Make this a longer 4:30 highlight reel with clear outcomes, defense, and crowd pops.",
            icon: "timer"
        ),
        AIEditQuickPrompt(
            id: "clear-outcomes",
            title: "Full",
            prompt: "Full plays: action-to-result, visible outcome; unsure clips stay for review.",
            icon: "scope"
        ),
        AIEditQuickPrompt(
            id: "crowd-pop",
            title: "Crowd",
            prompt: "Use loud crowd pops as nearby highlight clues; keep only clear plays.",
            icon: "waveform"
        ),
        AIEditQuickPrompt(
            id: "team-recap",
            title: "Team",
            prompt: "Clean team recap: balanced players, offense, defense, and game flow.",
            icon: "person.3.fill"
        )
    ]
}
