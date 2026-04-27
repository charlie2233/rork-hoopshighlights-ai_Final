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
    case arenaBounce = "Arena Bounce"
    case fastBreak = "Fast Break"
    case dramatic = "Dramatic"
    case lofi = "Lo-Fi"
    case halftimeFunk = "Halftime Funk"
    case clutchTime = "Clutch Time"
    case trap = "Trap Beat"
    case retroArcade = "Retro Arcade"
    case victoryLap = "Victory Lap"
    case orchestral = "Orchestral"
    case custom = "Custom Audio"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .none: return "speaker.slash.fill"
        case .energetic: return "bolt.heart.fill"
        case .arenaBounce: return "basketball.fill"
        case .fastBreak: return "hare.fill"
        case .dramatic: return "music.note.list"
        case .lofi: return "headphones"
        case .halftimeFunk: return "figure.dance"
        case .clutchTime: return "timer"
        case .trap: return "waveform"
        case .retroArcade: return "gamecontroller.fill"
        case .victoryLap: return "trophy.fill"
        case .orchestral: return "music.quarternote.3"
        case .custom: return "doc.badge.plus"
        }
    }

    var requiresPro: Bool {
        switch self {
        case .dramatic, .halftimeFunk, .clutchTime, .trap, .retroArcade, .victoryLap, .orchestral, .custom:
            return true
        case .none, .energetic, .arenaBounce, .fastBreak, .lofi:
            return false
        }
    }

    var description: String {
        switch self {
        case .none: return "Keep the original clip audio only"
        case .energetic: return "Bright, clean tempo for quick recaps"
        case .arenaBounce: return "Crowd-ready bounce with a simple game-day pulse"
        case .fastBreak: return "Fast tempo for transition buckets and quick cuts"
        case .dramatic: return "Big build for cinematic moments"
        case .lofi: return "Chill warmup feel for smooth edits"
        case .halftimeFunk: return "Groovy halftime rhythm for mixtape cuts"
        case .clutchTime: return "Darker tension for close-game moments"
        case .trap: return "Bass-forward beat for hype reels"
        case .retroArcade: return "Playful arcade synth for fun edits"
        case .victoryLap: return "Upbeat finish for trophy-style reels"
        case .orchestral: return "Epic soundtrack for dramatic reels"
        case .custom: return "Use an audio file from Files"
        }
    }

    var filename: String? {
        switch self {
        case .none, .custom: return nil
        case .energetic: return "energetic.mp3"
        case .arenaBounce: return "arena_bounce.m4a"
        case .fastBreak: return "fast_break.m4a"
        case .dramatic: return "dramatic.mp3"
        case .lofi: return "lofi.mp3"
        case .halftimeFunk: return "halftime_funk.m4a"
        case .clutchTime: return "clutch_time.m4a"
        case .trap: return "trap.mp3"
        case .retroArcade: return "retro_arcade.m4a"
        case .victoryLap: return "victory_lap.m4a"
        case .orchestral: return "orchestral.mp3"
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
