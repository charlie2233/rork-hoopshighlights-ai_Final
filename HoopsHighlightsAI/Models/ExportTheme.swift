import Foundation

nonisolated enum ExportTheme: String, CaseIterable, Codable, Sendable, Identifiable {
    case classic = "Classic"
    case vibrant = "Vibrant"
    case neon = "Neon"
    case cinematic = "Cinematic"
    case hype = "Hype"
    case minimal = "Minimal"

    var id: String { rawValue }

    var description: String {
        switch self {
        case .classic: return "Clean transitions with subtle overlays"
        case .vibrant: return "Bold colors and energetic motion"
        case .neon: return "Glowing edges with dark backgrounds"
        case .cinematic: return "Film-grade color grading and letterbox"
        case .hype: return "Fast cuts with bass-heavy transitions"
        case .minimal: return "Simple cuts, no effects"
        }
    }

    var icon: String {
        switch self {
        case .classic: return "film"
        case .vibrant: return "paintpalette.fill"
        case .neon: return "light.max"
        case .cinematic: return "theatermasks.fill"
        case .hype: return "bolt.circle.fill"
        case .minimal: return "square.split.1x2.fill"
        }
    }
}

nonisolated enum MusicTrack: String, CaseIterable, Codable, Sendable, Identifiable {
    case none = "No Music"
    case energetic = "Energetic"
    case dramatic = "Dramatic"
    case lofi = "Lo-Fi"
    case trap = "Trap Beat"
    case orchestral = "Orchestral"
    case custom = "Custom Audio"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .none: return "speaker.slash.fill"
        case .energetic: return "bolt.heart.fill"
        case .dramatic: return "music.note.list"
        case .lofi: return "headphones"
        case .trap: return "waveform"
        case .orchestral: return "music.quarternote.3"
        case .custom: return "doc.badge.plus"
        }
    }
}

nonisolated enum ExportQuality: String, CaseIterable, Codable, Sendable, Identifiable {
    case standard = "720p"
    case high = "1080p"
    case ultra = "4K"

    var id: String { rawValue }

    var description: String {
        switch self {
        case .standard: return "Fast export, smaller file"
        case .high: return "Recommended quality"
        case .ultra: return "Maximum resolution"
        }
    }
}
