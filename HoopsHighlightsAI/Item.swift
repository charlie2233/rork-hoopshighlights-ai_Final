//
//  Item.swift
//  HoopsHighlightsAI
//
//  Created by Rork on February 25, 2026.
//

import Foundation
import SwiftData

@Model
final class Item {
    var timestamp: Date

    init(timestamp: Date) {
        self.timestamp = timestamp
    }
}
