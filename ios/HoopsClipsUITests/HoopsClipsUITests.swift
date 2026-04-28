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
        let sourceObjectKey = ProcessInfo.processInfo.environment["HOOPS_SMOKE_SOURCE_OBJECT_KEY"]
            ?? "uploads/25a101ba8d234fd98094bd112276161f/source.mp4"
        let workerURL = ProcessInfo.processInfo.environment["HOOPS_SMOKE_WORKER_URL"]
            ?? "https://hoopsclips-control-plane-staging.charliehan-lifepage.workers.dev"
        let installID = ProcessInfo.processInfo.environment["HOOPS_SMOKE_INSTALL_ID"]
            ?? "phase-edit3b-live-ui-smoke"

        XCUIDevice.shared.orientation = .portrait

        let app = XCUIApplication()
        app.launchArguments = ["--hoops-ai-edit-live-smoke"]
        app.launchEnvironment["HOOPS_SMOKE_SOURCE_OBJECT_KEY"] = sourceObjectKey
        app.launchEnvironment["HOOPS_SMOKE_WORKER_URL"] = workerURL
        app.launchEnvironment["HOOPS_SMOKE_INSTALL_ID"] = installID
        app.launch()

        let reviewTab = app.tabBars.buttons["Review"]
        XCTAssertTrue(reviewTab.waitForExistence(timeout: 10), "Review tab should be available in the smoke guest session.")
        reviewTab.tap()

        XCTAssertTrue(app.staticTexts["Make Highlight Reel"].waitForExistence(timeout: 10))
        let entryButton = app.buttons["review.createAIEditButton"]
        XCTAssertTrue(entryButton.waitForExistence(timeout: 10))
        XCTAssertTrue(entryButton.isEnabled, "AI edit entry should be enabled for smoke-seeded cloud clips.")
        attachScreenshot(named: "01 Review Make Highlight Reel", app: app)
        entryButton.tap()

        XCTAssertTrue(app.navigationBars["AI Edit"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["Personal Highlight"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["30 seconds"].firstMatch.exists)
        attachScreenshot(named: "02 AI Edit Style Picker", app: app)

        app.buttons["aiEdit.createRenderButton"].tap()
        XCTAssertTrue(waitForRenderedState(in: app, timeout: 180), "Cloud render should reach Rendered through the live Worker path.")
        attachScreenshot(named: "03 AI Edit Rendered Preview", app: app)

        let shareButton = app.buttons["aiEdit.shareButton"]
        XCTAssertTrue(shareButton.waitForExistence(timeout: 20))
        shareButton.tap()
        XCTAssertTrue(waitForSystemShareSurface(in: app, timeout: 60), "System share sheet should open with the downloaded MP4 file.")
        attachScreenshot(named: "04 AI Edit Share Sheet", app: app)
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
        while Date() < deadline {
            if app.staticTexts["Rendered"].exists {
                return true
            }
            if app.staticTexts["Failed"].exists {
                attachScreenshot(named: "AI Edit Failed", app: app)
                XCTFail(app.staticTexts.containing(NSPredicate(format: "label CONTAINS[c] %@", "failed")).firstMatch.label)
                return false
            }
            RunLoop.current.run(until: Date().addingTimeInterval(2))
        }
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
    private func attachScreenshot(named name: String, app: XCUIApplication) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
