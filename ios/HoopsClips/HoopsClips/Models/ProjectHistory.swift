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
        if let contextTitle = contextualProjectTitle {
            return contextTitle
        }
        return Self.friendlyProjectTitle(
            sourceFilename: sourceFilename,
            sourceDuration: sourceDuration,
            createdAt: createdAt
        )
    }

    private var contextualProjectTitle: String? {
        guard let selection = highlightTeamSelection,
              selection.mode == .team else {
            return nil
        }

        let selectedTeam = Self.sanitizedContextName(selection.displayTitle)
        guard let selectedTeam else { return nil }

        if let opponent = Self.sanitizedContextName(opponentTeamName) {
            return "\(Self.titleCased(selectedTeam)) vs \(Self.titleCased(opponent))"
        }
        return "\(Self.titleCased(selectedTeam)) Highlights"
    }

    var sourceDisplayName: String {
        Self.friendlyProjectTitle(
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
            let kind: String
            if minutes >= 20 {
                kind = "Full Game"
            } else if minutes >= 6 {
                kind = "Basketball Run"
            } else {
                kind = "Short Clip"
            }
            return "\(kind) - \(minutes) min, \(dateTitle)"
        }
        return "Basketball Video \(dateTitle)"
    }

    private static func shouldReplaceGeneratedTitle(_ title: String, sourceBasename: String) -> Bool {
        let trimmedSource = sourceBasename.trimmingCharacters(in: .whitespacesAndNewlines)
        let lowerTitle = title.lowercased()
        guard title == trimmedSource
                || lowerTitle.hasPrefix("ytdown_")
                || lowerTitle.hasPrefix("vid_")
                || lowerTitle.hasPrefix("img_")
                || lowerTitle.hasPrefix("hoopclips ")
                || looksLikeGenericSourceTitle(cleanedTitleTokens(title)) else {
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
            .replacingOccurrences(of: "yt1s.com - ", with: "", options: [.caseInsensitive])
            .replacingOccurrences(of: "youtube video", with: "", options: [.caseInsensitive])
            .replacingOccurrences(of: "video download", with: "", options: [.caseInsensitive])
            .replacingOccurrences(of: "downloaded video", with: "", options: [.caseInsensitive])
            .replacingOccurrences(of: "screenrecording", with: "screen recording", options: [.caseInsensitive])
            .replacingOccurrences(of: "videoplayback", with: "", options: [.caseInsensitive])

        if let mediaRange = value.range(of: "_Media", options: [.caseInsensitive]) {
            value = String(value[..<mediaRange.lowerBound])
        }

        value = value
            .replacingOccurrences(of: "-vs-", with: " vs ", options: [.caseInsensitive])
            .replacingOccurrences(of: "_vs_", with: " vs ", options: [.caseInsensitive])
            .replacingOccurrences(of: " versus ", with: " vs ", options: [.caseInsensitive])
            .replacingOccurrences(of: " v ", with: " vs ", options: [.caseInsensitive])
            .replacingOccurrences(of: "_", with: " ")
            .replacingOccurrences(of: "-", with: " ")
            .replacingOccurrences(of: ".", with: " ")
            .replacingOccurrences(of: "(", with: " ")
            .replacingOccurrences(of: ")", with: " ")
            .replacingOccurrences(of: "[", with: " ")
            .replacingOccurrences(of: "]", with: " ")
            .split(whereSeparator: \.isWhitespace)
            .joined(separator: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)

        let tokens = cleanedTitleTokens(value)
        guard !tokens.isEmpty,
              !looksLikeCameraRollTitle(tokens),
              !looksLikeGenericSourceTitle(tokens) else {
            return ""
        }

        return titleCased(tokens.joined(separator: " "))
    }

    private static func cleanedTitleTokens(_ value: String) -> [String] {
        var tokens = value
            .split(whereSeparator: \.isWhitespace)
            .map(String.init)

        while let first = tokens.first,
              shouldDropLeadingGeneratedToken(first) {
            tokens.removeFirst()
        }

        while let last = tokens.last,
              shouldDropTrailingGeneratedToken(last) {
            tokens.removeLast()
        }

        return tokens.filter { !shouldDropEmbeddedGeneratedToken($0) }
    }

    private static func shouldDropEmbeddedGeneratedToken(_ token: String) -> Bool {
        let lower = token.lowercased()
        if generatedWrapperTokens.contains(lower) {
            return true
        }
        if lower.range(of: #"^\d{3,4}p$"#, options: .regularExpression) != nil {
            return true
        }
        if looksLikeRandomCode(token) {
            return true
        }
        if lower.count >= 6 {
            let alphanumeric = lower.filter { $0.isLetter || $0.isNumber }
            let digitCount = alphanumeric.filter(\.isNumber).count
            let letterCount = alphanumeric.filter(\.isLetter).count
            if alphanumeric.count == lower.count,
               digitCount > 0,
               letterCount > 0 {
                return true
            }
        }
        return false
    }

    private static func shouldDropTrailingGeneratedToken(_ token: String) -> Bool {
        let lower = token.lowercased()
        if generatedWrapperTokens.contains(lower) {
            return true
        }
        if lower == "4k" || lower == "uhd" || lower == "hd" {
            return true
        }
        if lower.range(of: #"^\d{3,4}p$"#, options: .regularExpression) != nil {
            return true
        }
        if lower.range(of: #"^\d{3,}$"#, options: .regularExpression) != nil {
            return !isLikelyYear(lower)
        }
        if lower.count >= 8 {
            let alphanumeric = lower.filter { $0.isLetter || $0.isNumber }
            let digitCount = alphanumeric.filter(\.isNumber).count
            let letterCount = alphanumeric.filter(\.isLetter).count
            if alphanumeric.count == lower.count,
               digitCount > 0,
               letterCount > 0 {
                return true
            }
        }
        return false
    }

    private static func shouldDropLeadingGeneratedToken(_ token: String) -> Bool {
        let lower = token.lowercased()
        if generatedWrapperTokens.contains(lower) {
            return true
        }
        if lower.range(of: #"^(img|vid|mov|dsc|pxl|trim)\d*$"#, options: .regularExpression) != nil {
            return true
        }
        if lower.range(of: #"^\d{3,}$"#, options: .regularExpression) != nil {
            return !isLikelyYear(lower)
        }
        return false
    }

    private static let generatedWrapperTokens: Set<String> = [
        "clip",
        "copy",
        "download",
        "downloaded",
        "file",
        "fullsizeoutput",
        "hd",
        "import",
        "imported",
        "media",
        "movie",
        "project",
        "source",
        "temp",
        "temporary",
        "trim",
        "uhd",
        "video",
        "videoplayback",
        "youtube",
        "ytdown"
    ]

    private static func looksLikeCameraRollTitle(_ tokens: [String]) -> Bool {
        guard let first = tokens.first?.lowercased() else { return true }
        let cameraPrefixes: Set<String> = ["img", "vid", "mov", "dsc", "pxl", "trim"]
        guard cameraPrefixes.contains(first) else { return false }

        let rest = tokens.dropFirst().joined()
        guard !rest.isEmpty else { return true }
        let digitCount = rest.filter(\.isNumber).count
        return digitCount >= max(3, rest.count / 2)
    }

    private static func looksLikeGenericSourceTitle(_ tokens: [String]) -> Bool {
        let lowerTokens = tokens
            .map { $0.lowercased() }
            .filter { !$0.isEmpty }
        guard !lowerTokens.isEmpty else { return true }

        let joined = lowerTokens.joined(separator: " ")
        let exactGenericTitles: Set<String> = [
            "clip",
            "download",
            "downloaded video",
            "file",
            "import",
            "imported",
            "imported video",
            "movie",
            "new project",
            "source",
            "source video",
            "temp",
            "temporary video",
            "tmp",
            "video"
        ]
        if exactGenericTitles.contains(joined) {
            return true
        }

        if lowerTokens.first?.hasPrefix("fullsizeoutput") == true {
            return true
        }

        let meaningfulTokens = lowerTokens.filter { token in
            token.range(of: #"^\d+$"#, options: .regularExpression) == nil
        }
        guard !meaningfulTokens.isEmpty else { return true }

        let genericWords: Set<String> = [
            "clip",
            "copy",
            "download",
            "downloaded",
            "edited",
            "file",
            "import",
            "imported",
            "movie",
            "new",
            "project",
            "source",
            "temp",
            "temporary",
            "tmp",
            "trim",
            "video"
        ]
        return meaningfulTokens.allSatisfy { genericWords.contains($0) }
    }

    private static func isLikelyYear(_ value: String) -> Bool {
        guard value.count == 4,
              let year = Int(value) else {
            return false
        }
        return (1900...2100).contains(year)
    }

    private static func titleCased(_ value: String) -> String {
        value
            .split(separator: " ")
            .map { token in
                let lower = token.lowercased()
                if lower == "vs" { return "vs" }
                let upper = token.uppercased()
                if preservedUppercaseTitleTokens.contains(upper) {
                    return upper
                }
                if lower.count <= 2, lower.allSatisfy(\.isLetter) {
                    return lower.uppercased()
                }
                let first = lower.prefix(1).uppercased()
                let rest = String(lower.dropFirst())
                return first + rest
            }
            .joined(separator: " ")
    }

    private static let preservedUppercaseTitleTokens: Set<String> = [
        "AAU",
        "AI",
        "ESPN",
        "HS",
        "JV",
        "NBA",
        "NCAA",
        "UCLA",
        "USA",
        "USC",
        "WNBA"
    ]

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

    private static func sanitizedContextName(_ value: String?) -> String? {
        guard let value else { return nil }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty,
              !looksLikeRandomCode(trimmed),
              !looksLikeGenericSourceTitle(cleanedTitleTokens(trimmed)) else {
            return nil
        }
        return trimmed
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
