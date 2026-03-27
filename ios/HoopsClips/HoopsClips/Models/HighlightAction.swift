import Foundation

nonisolated enum HighlightAction: String, CaseIterable, Codable, Sendable, Identifiable {
    case dunk = "Dunk"
    case layup = "Layup"
    case madeShot = "Made Shot"
    case threePointer = "Three Pointer"
    case steal = "Steal"
    case block = "Block"
    case fastBreak = "Fast Break"
    case alleyOop = "Alley-Oop"
    case crossover = "Crossover"
    case posterize = "Posterize"
    case buzzerBeater = "Buzzer Beater"
    case unknown = "Highlight"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .dunk: return "flame.fill"
        case .layup: return "figure.basketball"
        case .madeShot: return "target"
        case .threePointer: return "3.circle.fill"
        case .steal: return "hand.raised.fill"
        case .block: return "shield.fill"
        case .fastBreak: return "bolt.fill"
        case .alleyOop: return "arrow.up.forward"
        case .crossover: return "arrow.left.arrow.right"
        case .posterize: return "star.fill"
        case .buzzerBeater: return "clock.fill"
        case .unknown: return "sportscourt.fill"
        }
    }
}
