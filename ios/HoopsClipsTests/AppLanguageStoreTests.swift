import Foundation
import Testing
@testable import HoopsClips

struct AppLanguageStoreTests {
    @Test func defaultsToEnglish() {
        let defaults = isolatedDefaults()
        let store = AppLanguageStore(defaults: defaults)

        #expect(store.selectedLanguage == .english)
        #expect(store.text(.tabSettings) == "Settings")
    }

    @Test func persistsSelectedLanguage() {
        let defaults = isolatedDefaults()
        let store = AppLanguageStore(defaults: defaults)

        store.selectedLanguage = .spanish

        let reloaded = AppLanguageStore(defaults: defaults)
        #expect(reloaded.selectedLanguage == .spanish)
        #expect(reloaded.text(.tabSettings) == "Ajustes")
    }

    @Test func exposesLaunchCopyForSupportedLanguages() {
        #expect(AppLanguage.english.text(.playerTitle) == "HoopClips")
        #expect(AppLanguage.english.text(.turnGamesTitle) == "Get Your Highlights Seen")
        #expect(AppLanguage.english.text(.getExposure) == "Get Exposure")
        #expect(AppLanguage.chinese.text(.selectVideo) == "选择视频")
        #expect(AppLanguage.spanish.text(.selectVideo) == "Seleccionar video")
        #expect(AppLanguage.french.text(.selectVideo) == "Choisir une vidéo")
    }

    private func isolatedDefaults() -> UserDefaults {
        let suiteName = "HoopsClipsTests.AppLanguageStore.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defaults.removePersistentDomain(forName: suiteName)
        return defaults
    }
}
