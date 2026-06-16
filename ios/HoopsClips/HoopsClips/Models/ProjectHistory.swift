import Foundation

nonisolated struct PersistedProjectLibrary: Codable, Sendable {
    static let currentSchemaVersion = 1

    var schemaVersion: Int
    var currentProjectID: UUID?
    var projects: [PersistedProjectRecord]

    init(
        schemaVersion: Int = Self.currentSchemaVersion,
        currentProjectID: UUID? = nil,
        projects: [PersistedProjectRecord] = []
    ) {
        self.schemaVersion = schemaVersion
        self.currentProjectID = currentProjectID
        self.projects = projects
    }

    static var empty: PersistedProjectLibrary {
        PersistedProjectLibrary()
    }
}

nonisolated struct PersistedProjectRecord: Identifiable, Codable, Sendable {
    let id: UUID
    var title: String
    var sourceFilename: String
    var sourceRelativePath: String
    var sourceDuration: Double
    var thumbnailRelativePath: String
    var customAudioRelativePath: String?
    var latestExportRelativePath: String?
    var latestExportFilename: String?
    var createdAt: Date
    var updatedAt: Date
    var lastOpenedAt: Date
    var lastAnalyzedAt: Date?
    var lastExportedAt: Date?
    var analysisMode: AnalysisExecutionMode?
    var analysisStatusSummary: String?
    var cloudAnalysisJobID: String?
    var cloudEditSourceObjectKey: String?
    var highlightTeamSelection: HighlightTeamSelection?
    var opponentTeamName: String?
    var cloudDetectedTeams: [CloudTeamOption]?
    var cloudDiagnostics: CloudDiagnostics?
    var totalClipCount: Int
    var keptClipCount: Int
    var clips: [Clip]
    var selectedTheme: ExportTheme
    var selectedMusic: MusicTrack
    var selectedQuality: ExportQuality
    var selectedFormat: ExportFileFormat
    var exportPostProcessing: ExportPostProcessingOptions
    var events: [ProjectEventRecord]

    init(
        id: UUID = UUID(),
        title: String,
        sourceFilename: String,
        sourceRelativePath: String,
        sourceDuration: Double,
        thumbnailRelativePath: String,
        customAudioRelativePath: String? = nil,
        latestExportRelativePath: String? = nil,
        latestExportFilename: String? = nil,
        createdAt: Date,
        updatedAt: Date,
        lastOpenedAt: Date,
        lastAnalyzedAt: Date? = nil,
        lastExportedAt: Date? = nil,
        analysisMode: AnalysisExecutionMode? = nil,
        analysisStatusSummary: String? = nil,
        cloudAnalysisJobID: String? = nil,
        cloudEditSourceObjectKey: String? = nil,
        highlightTeamSelection: HighlightTeamSelection? = nil,
        opponentTeamName: String? = nil,
        cloudDetectedTeams: [CloudTeamOption]? = nil,
        cloudDiagnostics: CloudDiagnostics? = nil,
        totalClipCount: Int = 0,
        keptClipCount: Int = 0,
        clips: [Clip] = [],
        selectedTheme: ExportTheme = .vibrant,
        selectedMusic: MusicTrack = .none,
        selectedQuality: ExportQuality = .high,
        selectedFormat: ExportFileFormat = .mp4,
        exportPostProcessing: ExportPostProcessingOptions = ExportPostProcessingOptions(),
        events: [ProjectEventRecord] = []
    ) {
        self.id = id
        self.title = title
        self.sourceFilename = sourceFilename
        self.sourceRelativePath = sourceRelativePath
        self.sourceDuration = sourceDuration
        self.thumbnailRelativePath = thumbnailRelativePath
        self.customAudioRelativePath = customAudioRelativePath
        self.latestExportRelativePath = latestExportRelativePath
        self.latestExportFilename = latestExportFilename
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.lastOpenedAt = lastOpenedAt
        self.lastAnalyzedAt = lastAnalyzedAt
        self.lastExportedAt = lastExportedAt
        self.analysisMode = analysisMode
        self.analysisStatusSummary = analysisStatusSummary
        self.cloudAnalysisJobID = cloudAnalysisJobID
        self.cloudEditSourceObjectKey = cloudEditSourceObjectKey
        self.highlightTeamSelection = highlightTeamSelection
        self.opponentTeamName = opponentTeamName
        self.cloudDetectedTeams = cloudDetectedTeams
        self.cloudDiagnostics = cloudDiagnostics
        self.totalClipCount = totalClipCount
        self.keptClipCount = keptClipCount
        self.clips = clips
        self.selectedTheme = selectedTheme
        self.selectedMusic = selectedMusic
        self.selectedQuality = selectedQuality
        self.selectedFormat = selectedFormat
        self.exportPostProcessing = exportPostProcessing
        self.events = events
    }

    var displayTitle: String {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let sourceBasename = (sourceFilename as NSString).deletingPathExtension
        if !trimmedTitle.isEmpty,
           !Self.shouldReplaceGeneratedTitle(trimmedTitle, sourceBasename: sourceBasename) {
            return trimmedTitle
        }
        return Self.friendlyProjectTitle(
            sourceFilename: sourceFilename,
            sourceDuration: sourceDuration,
            createdAt: createdAt
        )
    }

    var hasLatestExport: Bool {
        latestExportRelativePath != nil
    }

    var historyClipBadgeText: String {
        "\(max(0, keptClipCount)) kept"
    }

    var historyClipBadgeAccessibilityText: String {
        let kept = max(0, keptClipCount)
        let total = max(0, totalClipCount)
        if total > 0 {
            return "\(kept) kept clips out of \(total) total clips"
        }
        return "\(kept) kept clips"
    }

    var historyExportBadgeText: String {
        "Saved reel"
    }

    mutating func appendEvent(kind: ProjectEventKind, message: String, limit: Int) {
        events.append(
            ProjectEventRecord(
                timestamp: Date(),
                kind: kind,
                message: message
            )
        )
        if events.count > limit {
            events = Array(events.suffix(limit))
        }
    }

    static func friendlyProjectTitle(
        sourceFilename: String,
        sourceDuration: Double,
        createdAt: Date
    ) -> String {
        let basename = (sourceFilename as NSString).deletingPathExtension
        let cleaned = cleanedSourceTitle(basename)
        if !cleaned.isEmpty,
           !looksLikeRandomCode(cleaned) {
            return cleaned
        }

        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d, h:mm a"
        let dateTitle = formatter.string(from: createdAt)
        if sourceDuration.isFinite, sourceDuration > 0 {
            let minutes = max(1, Int((sourceDuration / 60).rounded()))
            return "HoopClips \(dateTitle) - \(minutes) min"
        }
        return "HoopClips \(dateTitle)"
    }

    private static func shouldReplaceGeneratedTitle(_ title: String, sourceBasename: String) -> Bool {
        let trimmedSource = sourceBasename.trimmingCharacters(in: .whitespacesAndNewlines)
        guard title == trimmedSource || title.hasPrefix("YTDown_") || title.hasPrefix("VID_") || title.hasPrefix("IMG_") else {
            return looksLikeRandomCode(title)
        }
        return true
    }

    private static func cleanedSourceTitle(_ basename: String) -> String {
        var value = basename
            .replacingOccurrences(of: "YTDown_YouTube_", with: "")
            .replacingOccurrences(of: "YTDown_", with: "")
            .replacingOccurrences(of: "_YouTube_", with: " ")
            .replacingOccurrences(of: "_Media_", with: " ")

        if let mediaRange = value.range(of: "_Media", options: [.caseInsensitive]) {
            value = String(value[..<mediaRange.lowerBound])
        }

        value = value
            .replacingOccurrences(of: "-vs-", with: " vs ", options: [.caseInsensitive])
            .replacingOccurrences(of: "_vs_", with: " vs ", options: [.caseInsensitive])
            .replacingOccurrences(of: "_", with: " ")
            .replacingOccurrences(of: "-", with: " ")
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)

        return titleCased(value)
    }

    private static func titleCased(_ value: String) -> String {
        value
            .split(separator: " ")
            .map { token in
                let lower = token.lowercased()
                if lower == "vs" { return "vs" }
                if lower.count <= 2, lower.allSatisfy(\.isLetter) {
                    return lower.uppercased()
                }
                let first = lower.prefix(1).uppercased()
                let rest = String(lower.dropFirst())
                return first + rest
            }
            .joined(separator: " ")
    }

    private static func looksLikeRandomCode(_ value: String) -> Bool {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return true }
        let compact = trimmed
            .replacingOccurrences(of: "-", with: "")
            .replacingOccurrences(of: "_", with: "")
        if UUID(uuidString: trimmed) != nil { return true }
        if compact.count >= 18 {
            let alphaNumericCount = compact.filter { $0.isLetter || $0.isNumber }.count
            let digitCount = compact.filter(\.isNumber).count
            if alphaNumericCount == compact.count, digitCount >= compact.count / 3 {
                return true
            }
        }
        return false
    }
}

nonisolated struct ProjectEventRecord: Identifiable, Codable, Sendable {
    let id: UUID
    let timestamp: Date
    let kind: ProjectEventKind
    let message: String

    init(
        id: UUID = UUID(),
        timestamp: Date = Date(),
        kind: ProjectEventKind,
        message: String
    ) {
        self.id = id
        self.timestamp = timestamp
        self.kind = kind
        self.message = message
    }
}

nonisolated enum ProjectEventKind: String, Codable, Sendable, CaseIterable {
    case imported
    case analysisStarted
    case analysisCompleted
    case analysisFailed
    case exportCompleted
    case saveToPhotos
    case reopened
    case renamed

    var label: String {
        switch self {
        case .imported:
            return "Imported"
        case .analysisStarted:
            return "Analysis Started"
        case .analysisCompleted:
            return "Analysis Completed"
        case .analysisFailed:
            return "Analysis Failed"
        case .exportCompleted:
            return "Exported"
        case .saveToPhotos:
            return "Saved to Photos"
        case .reopened:
            return "Reopened"
        case .renamed:
            return "Renamed"
        }
    }
}
