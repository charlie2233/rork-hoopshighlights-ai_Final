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
    func testSettingsLaunchStatusOpensFromUploadsForGuestSession() throws {
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

        let settingsButton = app.buttons["uploads.settingsButton"]
        XCTAssertTrue(settingsButton.waitForExistence(timeout: 5), "Uploads should expose Settings as a utility route.")
        settingsButton.tap()

        XCTAssertTrue(app.staticTexts["Launch Status"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Analysis Path"].waitForExistence(timeout: 5))

        let closeButton = app.buttons["settings.closeButton"]
        XCTAssertTrue(closeButton.waitForExistence(timeout: 5))
        closeButton.tap()
        XCTAssertTrue(app.descendants(matching: .any)["uploads.screen"].waitForExistence(timeout: 5))
    }

    @MainActor
    func testVideoImportProgressHidesLandingClutter() throws {
        XCUIDevice.shared.orientation = .portrait

        let app = XCUIApplication()
        app.terminate()
        app.launchArguments = [
            "--hoops-import-progress-smoke",
            "-hoopsclips.rookieGuide.completed.v1",
            "YES",
        ]
        app.launch()

        XCTAssertTrue(app.descendants(matching: .any)["import.status.card"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["import.progress.stage"].exists)
        XCTAssertTrue(app.buttons["import.status.cancelButton"].exists)
        XCTAssertFalse(app.descendants(matching: .any)["import.landing.content"].exists)
        XCTAssertFalse(app.buttons["import.selectVideoButton"].exists)
        XCTAssertFalse(app.descendants(matching: .any)["app.tabBar"].exists)
        XCTAssertFalse(app.buttons["uploads.historyButton"].exists)
        XCTAssertFalse(app.buttons["uploads.settingsButton"].exists)
        XCTAssertFalse(app.descendants(matching: .any)["player.unexpectedExitRecoveryCard"].exists)
        attachScreenshot(named: "Import Focused Progress", app: app)
    }

    @MainActor
    func testWorkflowSectionsNavigateEndToEndWithSmokeFixture() throws {
        let app = launchAIEditSmokeApp(
            fixture: "staging_render_ready",
            sourceObjectKey: "uploads/25a101ba8d234fd98094bd112276161f/source.mp4",
            workerURL: "http://127.0.0.1:9",
            installID: "workflow-sections-ui-smoke"
        )

        XCTAssertTrue(waitForAppTab(named: "Uploads", identifier: "app.tab.uploads", in: app, timeout: 10).exists)
        XCTAssertTrue(app.descendants(matching: .any)["uploads.screen"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.descendants(matching: .any)["uploads.queue.panel"].exists)
        XCTAssertTrue(waitForAppTab(named: "Review", identifier: "app.tab.review", in: app, timeout: 10).exists)
        XCTAssertTrue(waitForAppTab(named: "AI Edit", identifier: "app.tab.aiEdit", in: app, timeout: 10).exists)
        XCTAssertTrue(waitForAppTab(named: "Exports", identifier: "app.tab.export", in: app, timeout: 10).exists)

        let reviewTab = waitForAppTab(named: "Review", identifier: "app.tab.review", in: app, timeout: 5)
        tapWhenReady(reviewTab, in: app)
        assertElementEventuallyExists(app.descendants(matching: .any)["review.carousel"], in: app, timeout: 10)
        assertElementEventuallyExists(app.buttons["review.carousel.keepButton"], in: app, timeout: 10)
        assertElementEventuallyExists(app.descendants(matching: .any)["review.carousel.boundaryNudgeControls"], in: app, timeout: 10)

        tapWhenReady(app.buttons["review.continueToExportButton"], in: app)
        XCTAssertTrue(app.descendants(matching: .any)["aiEdit.workflow.header"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.descendants(matching: .any)["export.aiEdit.section"].waitForExistence(timeout: 10))

        let exportsTab = waitForAppTab(named: "Exports", identifier: "app.tab.export", in: app, timeout: 5)
        exportsTab.tap()
        XCTAssertTrue(app.descendants(matching: .any)["exports.renderOutput.section"].waitForExistence(timeout: 10))
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

        openAIEditExportFlow(from: app)

        assertElementEventuallyExists(app.descendants(matching: .any)["export.aiEdit.smartSetupCard"], in: app)
        openAIEditSetupControls(in: app)
        XCTAssertTrue(app.buttons["export.aiEdit.style.personalHighlight"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["export.aiEdit.style.fullGameHighlight"].exists)
        XCTAssertTrue(app.buttons["export.aiEdit.style.coachReview"].exists)
        XCTAssertTrue(app.staticTexts["export.aiEdit.policy.limitLabel"].exists)
        XCTAssertTrue(app.descendants(matching: .any)["export.aiEdit.planCard.free"].exists)
        XCTAssertTrue(app.descendants(matching: .any)["export.aiEdit.proValueCard"].exists)
        XCTAssertTrue(app.buttons["export.aiEdit.proTemplate.recruitingReel"].exists)
        XCTAssertTrue(app.buttons["export.aiEdit.length.30s"].firstMatch.exists)
        XCTAssertTrue(app.staticTexts["export.aiEdit.policy.limitLabel"].firstMatch.exists)
        attachScreenshot(named: "02 Export AI Edit Style Picker", app: app)

        tapWhenReady(app.buttons["export.aiEdit.generateButton"], in: app)
        XCTAssertTrue(app.descendants(matching: .any)["export.aiEdit.timeline"].waitForExistence(timeout: 10))
        XCTAssertTrue(waitForRenderedState(in: app, timeout: 300), "Cloud render should reach Rendered through the live Worker path.")
        XCTAssertTrue(app.descendants(matching: .any)["export.aiEdit.preview"].waitForExistence(timeout: 20))
        XCTAssertTrue(app.descendants(matching: .any)["export.aiEdit.workReceipt"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.descendants(matching: .any)["export.aiEdit.revision.card"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "thinking")).firstMatch.exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "ETA")).firstMatch.exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "almost there")).firstMatch.exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "hang tight")).firstMatch.exists)
        attachScreenshot(named: "03 Export AI Edit Rendered Preview", app: app)

        tapWhenReady(app.descendants(matching: .any)["export.aiEdit.revision.moreHype"], in: app)
        let renderRevisionButton = app.buttons["export.aiEdit.renderRevisionButton"]
        XCTAssertTrue(renderRevisionButton.waitForExistence(timeout: 60))
        tapWhenReady(renderRevisionButton, in: app)
        XCTAssertTrue(waitForRenderedState(in: app, timeout: 300), "Cloud revision render should reach Rendered through the live Worker path.")
        XCTAssertTrue(app.descendants(matching: .any)["export.aiEdit.preview"].waitForExistence(timeout: 20))
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "thinking")).firstMatch.exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "ETA")).firstMatch.exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "almost there")).firstMatch.exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "hang tight")).firstMatch.exists)
        attachScreenshot(named: "04 Export AI Edit Revised Preview", app: app)

        let shareButton = app.buttons["export.aiEdit.shareButton"]
        XCTAssertTrue(shareButton.waitForExistence(timeout: 20))
        tapWhenReady(shareButton, in: app)
        XCTAssertTrue(waitForSystemShareSurface(in: app, timeout: 60), "System share sheet should open with the downloaded MP4 file.")
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "thinking")).firstMatch.exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "ETA")).firstMatch.exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "almost there")).firstMatch.exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "hang tight")).firstMatch.exists)
        attachScreenshot(named: "05 Export AI Edit Share Sheet", app: app)
    }

    @MainActor
    func testAIEditFreemiumProUXSmoke() throws {
        try skipUnlessAIEditUISmokeIsEnabled()

        let smokeConfig = loadAIEditUISmokeConfig()
        let app = launchAIEditSmokeApp(
            fixture: "staging_render_ready",
            sourceObjectKey: smokeConfig.sourceObjectKey,
            workerURL: smokeConfig.workerURL,
            installID: "phase-ux2b-freemium-pro-ui-smoke"
        )
        openAIEditExportFlow(from: app)

        assertElementEventuallyExists(app.descendants(matching: .any)["export.aiEdit.smartSetupCard"], in: app)
        assertElementEventuallyExists(app.descendants(matching: .any)["export.aiEdit.planCard.free"], in: app)
        assertStaticTextEventuallyExists("Current plan: Free", in: app)
        for text in [
            "Standard render queue",
            "720p max export",
            "HoopClips watermark/outro included",
            "3 AI edits/day",
            "3 revisions/edit",
            "Failed HoopClips jobs do not use a free edit.",
            "Videos stored for 14 days",
            "My AI Edits: rendered videos expire in 14 days on Free."
        ] {
            assertStaticTextEventuallyExists(text, in: app)
        }

        assertElementEventuallyExists(app.descendants(matching: .any)["export.aiEdit.proValueCard"], in: app)
        let proCardUpgradeButton = app.buttons["Upgrade with App Store"]
        assertElementEventuallyExists(proCardUpgradeButton, in: app)
        XCTAssertEqual(proCardUpgradeButton.label, "Upgrade with App Store")
        let proInfoButton = app.buttons["See Pro benefits"]
        assertElementEventuallyExists(proInfoButton, in: app)
        XCTAssertEqual(proInfoButton.label, "See Pro benefits")
        for text in [
            "Priority rendering",
            "1080p clean exports",
            "No required watermark",
            "No required HoopClips outro",
            "25 AI edits/day",
            "10 revisions/edit",
            "60-day cloud locker",
            "Pro template packs"
        ] {
            assertStaticTextEventuallyExists(text, in: app)
        }
        attachScreenshot(named: "UX2B Free Plan And Pro Value Cards", app: app)

        openAIEditSetupControls(in: app)
        for identifier in [
            "export.aiEdit.proTemplate.recruitingReel",
            "export.aiEdit.proTemplate.cinematicMixtape",
            "export.aiEdit.proTemplate.nbaRecap",
            "export.aiEdit.proTemplate.teamHighlight"
        ] {
            assertElementEventuallyExists(app.buttons[identifier], in: app)
        }

        let lockedTemplate = app.buttons["export.aiEdit.proTemplate.teamHighlight"]
        tapWhenReady(lockedTemplate, in: app)
        assertElementEventuallyExists(app.descendants(matching: .any)["export.aiEdit.proInfoSheet"], in: app)
        let sheetUpgradeButton = app.buttons["export.aiEdit.proInfoSheet.upgradeButton"]
        assertElementEventuallyExists(sheetUpgradeButton, in: app)
        XCTAssertEqual(sheetUpgradeButton.label, "Upgrade with App Store")
        XCTAssertFalse(app.buttons["Buy"].exists)
        XCTAssertFalse(app.buttons["Subscribe"].exists)
        XCTAssertFalse(app.buttons["Render Revision"].exists)
        XCTAssertFalse(app.buttons["export.aiEdit.renderRevisionButton"].exists)
        XCTAssertFalse(app.descendants(matching: .any)["export.aiEdit.preview"].exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", "thinking")).firstMatch.exists)
        XCTAssertFalse(app.staticTexts.matching(NSPredicate(format: "label MATCHES[c] %@", #".*\bETA\b.*"#)).firstMatch.exists)
        attachScreenshot(named: "UX2B Locked Pro Template Info Sheet", app: app)

        tapWhenReady(app.buttons["Close"].firstMatch, in: app)
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
        openAIEditExportFlow(from: app)

        tapWhenReady(app.buttons["export.aiEdit.generateButton"], in: app)
        let failureReason = app.staticTexts["export.aiEdit.failure.reasonLabel"]
        XCTAssertTrue(failureReason.waitForExistence(timeout: 10), "Failed render fixture should show a user-facing failure reason.")
        attachScreenshot(named: "Export AI Edit Failure Fixture", app: app)
    }

    @MainActor
    func testPreanalysisTeamChoiceSmoke() throws {
        try skipUnlessAIEditUISmokeIsEnabled()

        let app = launchTeamChoiceSmokeApp()
        let allTeamsChoice = app.buttons["Target All teams"]
        let blueTeamChoice = app.buttons["Target Blue jerseys"]
        let whiteTeamChoice = app.buttons["Target White jerseys"]

        assertElementEventuallyExists(app.descendants(matching: .any)["analysis.teamTarget.section"], in: app)
        assertElementEventuallyExists(app.descendants(matching: .any)["analysis.teamTarget.status"], in: app)
        assertElementEventuallyExists(allTeamsChoice, in: app)
        assertElementEventuallyExists(blueTeamChoice, in: app)
        assertElementEventuallyExists(whiteTeamChoice, in: app)

        let analyzeButton = app.buttons["analysis.startButton"]
        assertElementEventuallyExists(analyzeButton, in: app)
        XCTAssertFalse(analyzeButton.isEnabled, "Analysis should wait until the user confirms All teams or one detected jersey-color team.")
        attachScreenshot(named: "Team Choice Before Confirmation", app: app)

        tapWhenReady(blueTeamChoice, in: app)
        XCTAssertTrue(analyzeButton.waitForExistence(timeout: 5))
        XCTAssertTrue(analyzeButton.isEnabled, "Selecting a detected team should unlock cloud analysis.")
        attachScreenshot(named: "Team Choice Blue Confirmed", app: app)
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
        let statusLabel = app.descendants(matching: .any)["export.aiEdit.statusLabel"]
        var lastStatus = "<missing>"
        while Date() < deadline {
            if statusLabel.exists {
                lastStatus = (statusLabel.value as? String) ?? statusLabel.label
            }
            if lastStatus == "Rendered" || lastStatus == "Ready" || lastStatus == "Your reel is ready" {
                return true
            }
            if lastStatus == "Failed" || lastStatus == "Render failed" {
                attachScreenshot(named: "AI Edit Failed", app: app)
                let failureReason = app.staticTexts["export.aiEdit.failure.reasonLabel"].firstMatch
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
        app.terminate()
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

    @MainActor
    private func launchTeamChoiceSmokeApp() -> XCUIApplication {
        XCUIDevice.shared.orientation = .portrait

        let app = XCUIApplication()
        app.terminate()
        app.launchArguments = ["--hoops-team-choice-ui-smoke"]
        app.launchEnvironment["HOOPS_UI_SMOKE_MODE"] = "team_choice"
        app.launchEnvironment["HOOPS_CLOUD_ANALYSIS_BASE_URL"] = "http://127.0.0.1:9"
        app.launchEnvironment["HOOPS_CLOUD_EDIT_BASE_URL"] = "http://127.0.0.1:9"
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
    private func openAIEditExportFlow(from app: XCUIApplication) {
        let reviewTab = waitForAppTab(named: "Review", identifier: "app.tab.review", in: app, timeout: 10)
        XCTAssertTrue(reviewTab.exists, "Review tab should be available in the smoke guest session.")
        reviewTab.tap()

        let entryButton = app.buttons["review.continueToExportButton"]
        if !app.staticTexts["Make Highlight Reel"].waitForExistence(timeout: 4) {
            _ = entryButton.waitForExistence(timeout: 6)
        }
        XCTAssertTrue(entryButton.waitForExistence(timeout: 10), "Review should expose the AI Edit export entry.")
        XCTAssertTrue(entryButton.isEnabled, "AI edit entry should be enabled for smoke-seeded cloud clips.")
        attachScreenshot(named: "01 Review Continue To Export", app: app)
        tapWhenReady(entryButton, in: app)

        let exportTab = waitForAppTab(named: "AI Edit", identifier: "app.tab.aiEdit", in: app, timeout: 10)
        XCTAssertTrue(exportTab.exists, "AI Edit tab should be visible after routing from Review.")
        XCTAssertTrue(app.descendants(matching: .any)["export.aiEdit.section"].waitForExistence(timeout: 10))
        attachScreenshot(named: "02 AI Edit Agent", app: app)
    }

    @MainActor
    private func openAIEditSetupControls(in app: XCUIApplication) {
        let changeSetupButton = app.buttons["export.aiEdit.smartSetup.changeButton"]
        let setupCardButton = app.buttons["export.aiEdit.smartSetupCard"]
        let usesFlattenedCardToggle = !changeSetupButton.exists
        let setupToggle = usesFlattenedCardToggle ? setupCardButton : changeSetupButton
        if setupToggle.value as? String == "Setup choices shown" {
            return
        }
        tapWhenReady(
            setupToggle,
            in: app,
            normalizedOffset: usesFlattenedCardToggle ? CGVector(dx: 0.5, dy: 0.86) : nil
        )
    }

    @MainActor
    private func waitForAppTab(
        named name: String,
        identifier: String,
        in app: XCUIApplication,
        timeout: TimeInterval
    ) -> XCUIElement {
        let customTab = app.buttons[identifier]
        let systemTab = app.tabBars.buttons[name]
        let deadline = Date().addingTimeInterval(timeout)

        while Date() < deadline {
            if customTab.exists {
                return customTab
            }
            if systemTab.exists {
                return systemTab
            }
            RunLoop.current.run(until: Date().addingTimeInterval(0.25))
        }

        return customTab
    }

    @MainActor
    private func tapWhenReady(
        _ element: XCUIElement,
        in app: XCUIApplication,
        timeout: TimeInterval = 20,
        normalizedOffset: CGVector? = nil
    ) {
        let deadline = Date().addingTimeInterval(timeout)
        var scrollAttempt = 0
        while !element.exists && Date() < deadline {
            scrollThroughContent(in: app, attempt: scrollAttempt)
            scrollAttempt += 1
            RunLoop.current.run(until: Date().addingTimeInterval(0.5))
        }
        XCTAssertTrue(element.exists)
        scrollAttempt = 0
        while !element.isHittable && Date() < deadline {
            scrollThroughContent(in: app, attempt: scrollAttempt)
            scrollAttempt += 1
            RunLoop.current.run(until: Date().addingTimeInterval(0.5))
        }
        if let normalizedOffset {
            element.coordinate(withNormalizedOffset: normalizedOffset).tap()
        } else if element.isHittable {
            element.tap()
        } else {
            element.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        }
    }

    @MainActor
    private func scrollTowardBottom(in app: XCUIApplication) {
        if let scrollView = largestScrollView(in: app) {
            scrollView.swipeUp()
            return
        }
        let start = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.66))
        let end = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.14))
        start.press(forDuration: 0.05, thenDragTo: end)
    }

    @MainActor
    private func scrollTowardTop(in app: XCUIApplication) {
        if let scrollView = largestScrollView(in: app) {
            scrollView.swipeDown()
            return
        }
        let start = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.14))
        let end = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.66))
        start.press(forDuration: 0.05, thenDragTo: end)
    }

    @MainActor
    private func largestScrollView(in app: XCUIApplication) -> XCUIElement? {
        app.scrollViews.allElementsBoundByIndex
            .filter { $0.exists && $0.frame.height > 300 }
            .max { $0.frame.height < $1.frame.height }
    }

    @MainActor
    private func scrollThroughContent(in app: XCUIApplication, attempt: Int) {
        if attempt % 6 < 4 {
            scrollTowardBottom(in: app)
        } else {
            scrollTowardTop(in: app)
        }
    }

    @MainActor
    private func assertStaticTextEventuallyExists(
        _ text: String,
        in app: XCUIApplication,
        timeout: TimeInterval = 10,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        assertElementEventuallyExists(app.staticTexts[text], in: app, timeout: timeout, file: file, line: line)
    }

    @MainActor
    private func assertElementEventuallyExists(
        _ element: XCUIElement,
        in app: XCUIApplication,
        timeout: TimeInterval = 10,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        let deadline = Date().addingTimeInterval(timeout)
        var scrollAttempt = 0
        while !element.exists && Date() < deadline {
            scrollThroughContent(in: app, attempt: scrollAttempt)
            scrollAttempt += 1
            RunLoop.current.run(until: Date().addingTimeInterval(0.5))
        }
        XCTAssertTrue(element.exists, "Expected UI element to exist: \(element)", file: file, line: line)
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
