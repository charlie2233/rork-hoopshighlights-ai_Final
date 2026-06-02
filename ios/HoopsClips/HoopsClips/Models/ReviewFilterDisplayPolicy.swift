import Foundation

nonisolated enum ReviewFilterDisplayPolicy {
    static func visibleItems<Item: Hashable>(
        available: [Item],
        primary: Set<Item>,
        active: Item,
        showAll: Bool
    ) -> [Item] {
        guard !showAll else { return available }

        var visible = available.filter { primary.contains($0) }
        if available.contains(active), !visible.contains(active) {
            visible.append(active)
        }
        return visible
    }

    static func hiddenItems<Item: Hashable>(
        available: [Item],
        primary: Set<Item>,
        active: Item,
        showAll: Bool
    ) -> [Item] {
        let visible = Set(
            visibleItems(
                available: available,
                primary: primary,
                active: active,
                showAll: showAll
            )
        )
        return available.filter { !visible.contains($0) }
    }

    static func moreFiltersTitle(hiddenCount: Int, showAll: Bool) -> String {
        showAll ? "Less" : "More \(hiddenCount)"
    }
}
