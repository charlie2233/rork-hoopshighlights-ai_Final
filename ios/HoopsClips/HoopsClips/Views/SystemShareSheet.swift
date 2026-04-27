import SwiftUI
import UIKit
import LinkPresentation
import UniformTypeIdentifiers

struct SystemShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    var subject: String? = nil
    var completion: ((UIActivity.ActivityType?, Bool, [Any]?, Error?) -> Void)? = nil

    static func videoItems(for fileURL: URL, title: String) -> [Any] {
        [VideoActivityItemSource(fileURL: fileURL, title: title)]
    }

    func makeUIViewController(context: Context) -> UIActivityViewController {
        let controller = UIActivityViewController(activityItems: items, applicationActivities: nil)

        if let subject, !subject.isEmpty {
            controller.setValue(subject, forKey: "subject")
        }

        controller.completionWithItemsHandler = { activityType, completed, returnedItems, error in
            completion?(activityType, completed, returnedItems, error)
        }

        return controller
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

private final class VideoActivityItemSource: NSObject, UIActivityItemSource {
    private let fileURL: URL
    private let title: String

    init(fileURL: URL, title: String) {
        self.fileURL = fileURL
        self.title = title
    }

    func activityViewControllerPlaceholderItem(_ activityViewController: UIActivityViewController) -> Any {
        fileURL
    }

    func activityViewController(
        _ activityViewController: UIActivityViewController,
        itemForActivityType activityType: UIActivity.ActivityType?
    ) -> Any? {
        fileURL
    }

    func activityViewController(
        _ activityViewController: UIActivityViewController,
        subjectForActivityType activityType: UIActivity.ActivityType?
    ) -> String {
        title
    }

    func activityViewController(
        _ activityViewController: UIActivityViewController,
        dataTypeIdentifierForActivityType activityType: UIActivity.ActivityType?
    ) -> String {
        let fallbackType: UTType = fileURL.pathExtension.lowercased() == "mp4" ? .mpeg4Movie : .quickTimeMovie
        return UTType(filenameExtension: fileURL.pathExtension)?.identifier ?? fallbackType.identifier
    }

    func activityViewControllerLinkMetadata(_ activityViewController: UIActivityViewController) -> LPLinkMetadata? {
        let metadata = LPLinkMetadata()
        metadata.title = title
        metadata.originalURL = fileURL
        metadata.url = fileURL
        return metadata
    }
}
