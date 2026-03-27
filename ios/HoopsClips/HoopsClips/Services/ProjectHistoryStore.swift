import Foundation
import AVFoundation
import UIKit

enum ProjectHistoryStoreError: LocalizedError {
    case projectNotFound
    case invalidThumbnail

    var errorDescription: String? {
        switch self {
        case .projectNotFound:
            return "The selected project could not be found."
        case .invalidThumbnail:
            return "The project thumbnail could not be generated."
        }
    }
}

final class ProjectHistoryStore {
    private let fileManager: FileManager
    private let libraryRootURL: URL
    private let projectsRootURL: URL
    private let manifestURL: URL
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(fileManager: FileManager = .default) {
        self.fileManager = fileManager

        let applicationSupportURL = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL.temporaryDirectory
        libraryRootURL = applicationSupportURL.appending(path: "ProjectLibrary", directoryHint: .isDirectory)
        projectsRootURL = libraryRootURL.appending(path: "projects", directoryHint: .isDirectory)
        manifestURL = libraryRootURL.appending(path: "library.json", directoryHint: .notDirectory)

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        self.encoder = encoder

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        self.decoder = decoder
    }

    func loadLibrary() throws -> PersistedProjectLibrary {
        try ensureDirectories()

        guard fileManager.fileExists(atPath: manifestURL.path) else {
            return .empty
        }

        do {
            let data = try Data(contentsOf: manifestURL)
            return try decoder.decode(PersistedProjectLibrary.self, from: data)
        } catch {
            let timestamp = ISO8601DateFormatter().string(from: Date()).replacingOccurrences(of: ":", with: "-")
            let corruptURL = libraryRootURL.appending(path: "library.corrupt.\(timestamp).json", directoryHint: .notDirectory)
            try? fileManager.removeItem(at: corruptURL)
            try? fileManager.moveItem(at: manifestURL, to: corruptURL)
            return .empty
        }
    }

    func saveLibrary(_ library: PersistedProjectLibrary) throws {
        try ensureDirectories()

        let data = try encoder.encode(library)
        let tempURL = libraryRootURL.appending(path: "library.json.tmp", directoryHint: .notDirectory)
        try? fileManager.removeItem(at: tempURL)
        try data.write(to: tempURL, options: .atomic)

        if fileManager.fileExists(atPath: manifestURL.path) {
            _ = try fileManager.replaceItemAt(manifestURL, withItemAt: tempURL)
        } else {
            try fileManager.moveItem(at: tempURL, to: manifestURL)
        }
    }

    func createProjectFromImportedVideo(sourceURL: URL) async throws -> PersistedProjectRecord {
        try ensureDirectories()

        let projectID = UUID()
        let projectDirectoryURL = self.projectDirectoryURL(for: projectID)
        try fileManager.createDirectory(at: projectDirectoryURL, withIntermediateDirectories: true)

        do {
            let sourceExtension = preferredExtension(for: sourceURL.pathExtension, fallback: "mov")
            let persistedSourceURL = projectDirectoryURL.appending(path: "source.\(sourceExtension)", directoryHint: .notDirectory)
            try copyReplacingItem(at: sourceURL, to: persistedSourceURL)

            let asset = AVURLAsset(url: persistedSourceURL)
            let duration = try await asset.load(.duration)
            let durationSeconds = CMTimeGetSeconds(duration)

            let thumbnailURL = projectDirectoryURL.appending(path: "thumbnail.jpg", directoryHint: .notDirectory)
            try await writeThumbnail(for: asset, to: thumbnailURL)

            let filename = sourceURL.lastPathComponent
            let basename = (filename as NSString).deletingPathExtension
            let now = Date()

            return PersistedProjectRecord(
                id: projectID,
                title: basename.isEmpty ? filename : basename,
                sourceFilename: filename,
                sourceRelativePath: relativePath(for: persistedSourceURL),
                sourceDuration: durationSeconds,
                thumbnailRelativePath: relativePath(for: thumbnailURL),
                createdAt: now,
                updatedAt: now,
                lastOpenedAt: now
            )
        } catch {
            try? fileManager.removeItem(at: projectDirectoryURL)
            throw error
        }
    }

    func updateProjectSnapshot(_ project: PersistedProjectRecord) throws {
        var library = try loadLibrary()
        if let existingIndex = library.projects.firstIndex(where: { $0.id == project.id }) {
            library.projects[existingIndex] = project
        } else {
            library.projects.append(project)
        }
        try saveLibrary(library)
    }

    func attachLatestExport(
        for projectID: UUID,
        from tempURL: URL,
        preferredExtension preferredFileExtension: String
    ) throws -> PersistedProjectRecord {
        try ensureDirectories()

        var library = try loadLibrary()
        guard let projectIndex = library.projects.firstIndex(where: { $0.id == projectID }) else {
            throw ProjectHistoryStoreError.projectNotFound
        }

        let projectDirectoryURL = self.projectDirectoryURL(for: projectID)
        try fileManager.createDirectory(at: projectDirectoryURL, withIntermediateDirectories: true)

        let normalizedExtension = preferredExtension(for: preferredFileExtension, fallback: "mp4")
        let destinationURL = projectDirectoryURL.appending(path: "latest-export.\(normalizedExtension)", directoryHint: .notDirectory)
        try copyReplacingItem(at: tempURL, to: destinationURL)

        let previousRelativePath = library.projects[projectIndex].latestExportRelativePath
        if let previousRelativePath,
           let previousURL = url(for: previousRelativePath),
           previousURL != destinationURL,
           fileManager.fileExists(atPath: previousURL.path) {
            try? fileManager.removeItem(at: previousURL)
        }

        library.projects[projectIndex].latestExportRelativePath = relativePath(for: destinationURL)
        library.projects[projectIndex].latestExportFilename = destinationURL.lastPathComponent
        library.projects[projectIndex].updatedAt = Date()
        try saveLibrary(library)
        return library.projects[projectIndex]
    }

    func attachCustomAudio(for projectID: UUID, from sourceURL: URL) throws -> PersistedProjectRecord {
        try ensureDirectories()

        var library = try loadLibrary()
        guard let projectIndex = library.projects.firstIndex(where: { $0.id == projectID }) else {
            throw ProjectHistoryStoreError.projectNotFound
        }

        let projectDirectoryURL = self.projectDirectoryURL(for: projectID)
        try fileManager.createDirectory(at: projectDirectoryURL, withIntermediateDirectories: true)

        let normalizedExtension = preferredExtension(for: sourceURL.pathExtension, fallback: "m4a")
        let destinationURL = projectDirectoryURL.appending(path: "custom-audio.\(normalizedExtension)", directoryHint: .notDirectory)
        try copyReplacingItem(at: sourceURL, to: destinationURL)

        let previousRelativePath = library.projects[projectIndex].customAudioRelativePath
        if let previousRelativePath,
           let previousURL = url(for: previousRelativePath),
           previousURL != destinationURL,
           fileManager.fileExists(atPath: previousURL.path) {
            try? fileManager.removeItem(at: previousURL)
        }

        library.projects[projectIndex].customAudioRelativePath = relativePath(for: destinationURL)
        library.projects[projectIndex].updatedAt = Date()
        try saveLibrary(library)
        return library.projects[projectIndex]
    }

    func restoreProject(id: UUID) throws -> PersistedProjectRecord {
        let library = try loadLibrary()
        guard let project = library.projects.first(where: { $0.id == id }) else {
            throw ProjectHistoryStoreError.projectNotFound
        }
        return project
    }

    func deleteProject(id: UUID) throws {
        var library = try loadLibrary()
        library.projects.removeAll { $0.id == id }
        if library.currentProjectID == id {
            library.currentProjectID = nil
        }
        try saveLibrary(library)

        let projectDirectoryURL = self.projectDirectoryURL(for: id)
        if fileManager.fileExists(atPath: projectDirectoryURL.path) {
            try fileManager.removeItem(at: projectDirectoryURL)
        }
    }

    func url(for relativePath: String?) -> URL? {
        guard let relativePath, !relativePath.isEmpty else { return nil }
        return libraryRootURL.appending(path: relativePath, directoryHint: .notDirectory)
    }

    func existingURL(for relativePath: String?) -> URL? {
        guard let fileURL = url(for: relativePath),
              fileManager.fileExists(atPath: fileURL.path) else {
            return nil
        }
        return fileURL
    }

    func managedRelativePath(for fileURL: URL?) -> String? {
        guard let fileURL else { return nil }

        let standardizedFileURL = fileURL.standardizedFileURL
        let rootPath = libraryRootURL.standardizedFileURL.path
        let filePath = standardizedFileURL.path
        let prefix = rootPath.hasSuffix("/") ? rootPath : rootPath + "/"

        guard filePath == rootPath || filePath.hasPrefix(prefix) else {
            return nil
        }

        let relative = filePath.replacingOccurrences(of: prefix, with: "")
        return relative.isEmpty ? nil : relative
    }

    func thumbnailImage(for project: PersistedProjectRecord) -> UIImage? {
        guard let thumbnailURL = existingURL(for: project.thumbnailRelativePath) else {
            return nil
        }
        return UIImage(contentsOfFile: thumbnailURL.path)
    }

    private func ensureDirectories() throws {
        if !fileManager.fileExists(atPath: libraryRootURL.path) {
            try fileManager.createDirectory(at: libraryRootURL, withIntermediateDirectories: true)
        }
        if !fileManager.fileExists(atPath: projectsRootURL.path) {
            try fileManager.createDirectory(at: projectsRootURL, withIntermediateDirectories: true)
        }
    }

    private func projectDirectoryURL(for projectID: UUID) -> URL {
        projectsRootURL.appending(path: projectID.uuidString, directoryHint: .isDirectory)
    }

    private func relativePath(for fileURL: URL) -> String {
        "projects/\(fileURL.deletingLastPathComponent().lastPathComponent)/\(fileURL.lastPathComponent)"
    }

    private func preferredExtension(for candidate: String, fallback: String) -> String {
        let trimmed = candidate.trimmingCharacters(in: CharacterSet(charactersIn: ". "))
        return trimmed.isEmpty ? fallback : trimmed.lowercased()
    }

    private func copyReplacingItem(at sourceURL: URL, to destinationURL: URL) throws {
        if fileManager.fileExists(atPath: destinationURL.path) {
            try fileManager.removeItem(at: destinationURL)
        }
        try fileManager.copyItem(at: sourceURL, to: destinationURL)
    }

    private func writeThumbnail(for asset: AVURLAsset, to outputURL: URL) async throws {
        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.maximumSize = CGSize(width: 400, height: 225)
        let (image, _) = try await generator.image(at: .zero)

        guard let data = UIImage(cgImage: image).jpegData(compressionQuality: 0.82) else {
            throw ProjectHistoryStoreError.invalidThumbnail
        }

        try data.write(to: outputURL, options: .atomic)
    }
}
