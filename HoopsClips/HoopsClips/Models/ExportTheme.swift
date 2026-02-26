import Foundation
import AVFoundation

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

    var requiresPro: Bool {
        switch self {
        case .neon, .cinematic, .hype:
            return true
        case .classic, .vibrant, .minimal:
            return false
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

    var requiresPro: Bool {
        switch self {
        case .dramatic, .trap, .orchestral, .custom:
            return true
        case .none, .energetic, .lofi:
            return false
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

nonisolated enum ExportFileFormat: String, CaseIterable, Codable, Sendable, Identifiable {
    case mp4 = "MP4"
    case mov = "MOV"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .mp4: return "play.rectangle.fill"
        case .mov: return "film.fill"
        }
    }

    var description: String {
        switch self {
        case .mp4: return "Best for sharing and compatibility"
        case .mov: return "Apple-native export container"
        }
    }

    var avFileType: AVFileType {
        switch self {
        case .mp4: return .mp4
        case .mov: return .mov
        }
    }

    var fileExtension: String {
        switch self {
        case .mp4: return "mp4"
        case .mov: return "mov"
        }
    }
}
