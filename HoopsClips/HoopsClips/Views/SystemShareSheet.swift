import SwiftUI
import UIKit

struct SystemShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    var subject: String? = nil
    var completion: ((UIActivity.ActivityType?, Bool, [Any]?, Error?) -> Void)? = nil

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
