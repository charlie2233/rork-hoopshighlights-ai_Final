import SwiftUI

struct ContentView: View {
    @State private var viewModel = HighlightsViewModel()
    @State private var selectedTab = 0

    var body: some View {
        ZStack {
            AppTheme.darkBg.ignoresSafeArea()

            TabView(selection: $selectedTab) {
                Tab("Player", systemImage: "play.circle.fill", value: 0) {
                    VideoPlayerView(viewModel: viewModel)
                }
                Tab("Review", systemImage: "film.stack.fill", value: 1) {
                    ReviewView(viewModel: viewModel)
                }
                Tab("Export", systemImage: "square.and.arrow.up.fill", value: 2) {
                    ExportView(viewModel: viewModel)
                }
                Tab("Settings", systemImage: "gearshape.fill", value: 3) {
                    SettingsView(viewModel: viewModel)
                }
            }
            .tint(AppTheme.neonPurple)
        }
        .preferredColorScheme(.dark)
    }
}
