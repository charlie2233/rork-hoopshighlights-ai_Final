//
//  HoopsClipsUITests.swift
//  HoopsClipsUITests
//
//  Created by Rork on February 25, 2026.
//

import XCTest

final class HoopsClipsUITests: XCTestCase {

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.

        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false

        // In UI tests it's important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    @MainActor
    func testExample() throws {
        // UI tests must launch the application that they test.
        let app = XCUIApplication()
        app.launch()

        // Use XCTAssert and related functions to verify your tests produce the correct results.
    }

    @MainActor
    func testSettingsLaunchStatusOpensForGuestSession() throws {
        XCUIDevice.shared.orientation = .portrait

        let app = XCUIApplication()
        app.launch()

        let guestButton = app.buttons["Continue as Guest"]
        if guestButton.waitForExistence(timeout: 5) {
            while !guestButton.isHittable && app.scrollViews.firstMatch.exists {
                app.scrollViews.firstMatch.swipeUp()
            }
            guestButton.tap()
        }

        let settingsTab = app.tabBars.buttons["Settings"]
        XCTAssertTrue(settingsTab.waitForExistence(timeout: 5), "Settings tab should be available after authentication.")
        settingsTab.tap()

        XCTAssertTrue(app.staticTexts["Launch Status"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Analysis Path"].waitForExistence(timeout: 5))
    }

    @MainActor
    func testLiveAIEditClientSmokeFlow() throws {
        try skipUnlessAIEditUISmokeIsEnabled()
        executionTimeAllowance = 600

        let smokeConfig = loadAIEditUISmokeConfig()
        let app = launchAIEditSmokeApp(
            fixture: "staging_render_ready",
            sourceObjectKey: smokeConfig.sourceObjectKey,
            workerURL: smokeConfig.workerURL,
            installID: smokeConfig.installID
        )

        openAIEditSheet(from: app)

        XCTAssertTrue(app.buttons["edit.style.personalHighlightButton"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["edit.duration.30sButton"].firstMatch.exists)
        attachScreenshot(named: "02 AI Edit Style Picker", app: app)

        app.buttons["edit.render.startButton"].tap()
        XCTAssertTrue(waitForRenderedState(in: app, timeout: 300), "Cloud render should reach Rendered through the live Worker path.")
        XCTAssertTrue(app.descendants(matching: .any)["edit.preview.player"].waitForExistence(timeout: 20))
        attachScreenshot(named: "03 AI Edit Rendered Preview", app: app)

        let shareButton = app.buttons["edit.share.button"]
        XCTAssertTrue(shareButton.waitForExistence(timeout: 20))
        shareButton.tap()
        XCTAssertTrue(waitForSystemShareSurface(in: app, timeout: 60), "System share sheet should open with the downloaded MP4 file.")
        attachScreenshot(named: "04 AI Edit Share Sheet", app: app)
    }

    @MainActor
    func testAIEditFailureFixtureShowsFailureReason() throws {
        try skipUnlessAIEditUISmokeIsEnabled()

        let smokeConfig = loadAIEditUISmokeConfig()
        let app = launchAIEditSmokeApp(
            fixture: "failing_render",
            sourceObjectKey: nil,
            workerURL: smokeConfig.workerURL,
            installID: "phase-edit3c-failure-ui-smoke"
        )
        openAIEditSheet(from: app)

        app.buttons["edit.render.startButton"].tap()
        let failureReason = app.staticTexts["edit.failure.reasonLabel"]
        XCTAssertTrue(failureReason.waitForExistence(timeout: 10), "Failed render fixture should show a user-facing failure reason.")
        attachScreenshot(named: "AI Edit Failure Fixture", app: app)
    }

    @MainActor
    func testLaunchPerformance() throws {
        // This measures how long it takes to launch your application.
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            XCUIApplication().launch()
        }
    }

    @MainActor
    private func waitForRenderedState(in app: XCUIApplication, timeout: TimeInterval) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        let statusLabel = app.descendants(matching: .any)["edit.status.label"]
        var lastStatus = "<missing>"
        while Date() < deadline {
            if statusLabel.exists {
                lastStatus = (statusLabel.value as? String) ?? statusLabel.label
            }
            if lastStatus == "Rendered" {
                return true
            }
            if lastStatus == "Failed" {
                attachScreenshot(named: "AI Edit Failed", app: app)
                let failureReason = app.staticTexts["edit.failure.reasonLabel"].firstMatch
                XCTFail(failureReason.exists ? failureReason.label : "AI edit failed before rendering.")
                return false
            }
            RunLoop.current.run(until: Date().addingTimeInterval(2))
        }
        attachScreenshot(named: "AI Edit Render Timeout", app: app)
        XCTFail("Timed out waiting for Rendered status. Last status: \(lastStatus)")
        return false
    }

    @MainActor
    private func waitForSystemShareSurface(in app: XCUIApplication, timeout: TimeInterval) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if app.sheets.firstMatch.exists ||
                app.otherElements["ActivityListView"].exists ||
                app.otherElements["ShareSheet.RemoteContainerView"].exists {
                return true
            }
            RunLoop.current.run(until: Date().addingTimeInterval(1))
        }
        return false
    }

    @MainActor
    private func launchAIEditSmokeApp(
        fixture: String,
        sourceObjectKey: String?,
        workerURL: String,
        installID: String
    ) -> XCUIApplication {
        XCUIDevice.shared.orientation = .portrait

        let app = XCUIApplication()
        app.launchArguments = ["--hoops-ai-edit-live-smoke"]
        app.launchEnvironment["HOOPS_UI_SMOKE_MODE"] = "1"
        app.launchEnvironment["HOOPS_AI_EDIT_TEST_FIXTURE"] = fixture
        app.launchEnvironment["HOOPS_CLOUD_ANALYSIS_BASE_URL"] = workerURL
        app.launchEnvironment["HOOPS_CLOUD_EDIT_BASE_URL"] = workerURL
        app.launchEnvironment["HOOPS_SMOKE_WORKER_URL"] = workerURL
        app.launchEnvironment["HOOPS_SMOKE_INSTALL_ID"] = installID
        if let sourceObjectKey {
            app.launchEnvironment["HOOPS_SMOKE_SOURCE_OBJECT_KEY"] = sourceObjectKey
        }
        app.launch()
        return app
    }

    private func skipUnlessAIEditUISmokeIsEnabled() throws {
        #if HOOPS_ENABLE_UI_SMOKE
        return
        #else
        throw XCTSkip("Skipped by default. Rebuild this test with OTHER_SWIFT_FLAGS='$(inherited) -D HOOPS_ENABLE_UI_SMOKE' to run AI Edit UI smoke.")
        #endif
    }

    private func loadAIEditUISmokeConfig() -> AIEditUISmokeConfig {
        let environment = ProcessInfo.processInfo.environment
        let configPath = environment["HOOPS_UI_SMOKE_CONFIG_PATH"] ?? "/tmp/hoopsclips-ai-edit-ui-smoke.json"
        let fileConfig: AIEditUISmokeConfig?
        if let data = try? Data(contentsOf: URL(fileURLWithPath: configPath)) {
            fileConfig = try? JSONDecoder().decode(AIEditUISmokeConfig.self, from: data)
        } else {
            fileConfig = nil
        }

        return AIEditUISmokeConfig(
            workerURL: environment["HOOPS_SMOKE_WORKER_URL"]
                ?? fileConfig?.workerURL
                ?? "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev",
            sourceObjectKey: environment["HOOPS_SMOKE_SOURCE_OBJECT_KEY"]
                ?? fileConfig?.sourceObjectKey
                ?? "uploads/25a101ba8d234fd98094bd112276161f/source.mp4",
            installID: environment["HOOPS_SMOKE_INSTALL_ID"]
                ?? fileConfig?.installID
                ?? "phase-edit3c-live-ui-smoke"
        )
    }

    @MainActor
    private func openAIEditSheet(from app: XCUIApplication) {
        let reviewTab = app.tabBars.buttons["Review"]
        XCTAssertTrue(reviewTab.waitForExistence(timeout: 10), "Review tab should be available in the smoke guest session.")
        reviewTab.tap()

        XCTAssertTrue(app.staticTexts["Make Highlight Reel"].waitForExistence(timeout: 10))
        let entryButton = app.buttons["review.makeHighlightReelButton"]
        XCTAssertTrue(entryButton.waitForExistence(timeout: 10))
        XCTAssertTrue(entryButton.isEnabled, "AI edit entry should be enabled for smoke-seeded cloud clips.")
        attachScreenshot(named: "01 Review Make Highlight Reel", app: app)
        entryButton.tap()

        XCTAssertTrue(app.navigationBars["AI Edit"].waitForExistence(timeout: 10))
    }

    @MainActor
    private func attachScreenshot(named name: String, app: XCUIApplication) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private struct AIEditUISmokeConfig: Decodable {
        var workerURL: String
        var sourceObjectKey: String?
        var installID: String
    }
}
