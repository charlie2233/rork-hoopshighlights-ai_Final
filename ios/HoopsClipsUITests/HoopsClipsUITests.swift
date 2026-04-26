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
    func testLaunchPerformance() throws {
        // This measures how long it takes to launch your application.
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            XCUIApplication().launch()
        }
    }
}
