import Foundation

struct PersistedProjectLibrary: Codable, Sendable {
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

struct PersistedProjectRecord: Identifiable, Codable, Sendable {
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
        if !title.isEmpty {
            return title
        }
        let basename = (sourceFilename as NSString).deletingPathExtension
        return basename.isEmpty ? sourceFilename : basename
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
}

struct ProjectEventRecord: Identifiable, Codable, Sendable {
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

enum ProjectEventKind: String, Codable, Sendable, CaseIterable {
    case imported
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
