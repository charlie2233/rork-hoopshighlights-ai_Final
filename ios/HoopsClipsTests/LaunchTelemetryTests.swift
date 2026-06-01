import Testing
@testable import HoopsClips

struct LaunchTelemetryTests {
    @Test func testAIEditFailureReasonRedactsURLsObjectKeysAndSignedQueryValues() {
        let rawValue = """
        render failed for uploads/25a101ba8d234fd98094bd112276161f/source.mp4 \
        at https://cdn.hoopsclips.test/edits/edit_123/final.mp4?X-Amz-Signature=secret&X-Amz-Credential=credential \
        log edits/edit_123/render_jobs/render_789/render_log.json
        """

        let redacted = LaunchTelemetry.redactedAIEditFailureReason(rawValue)

        #expect(redacted.contains("[redacted_url]"))
        #expect(redacted.contains("[redacted_object_key]"))
        #expect(!redacted.contains("https://"))
        #expect(!redacted.contains("uploads/25a101ba8d234fd98094bd112276161f"))
        #expect(!redacted.contains("edits/edit_123"))
        #expect(!redacted.contains("X-Amz-Signature"))
        #expect(!redacted.contains("secret"))
    }

    @Test func testAIEditFailureReasonRedactionKeepsFriendlyMessages() {
        let redacted = LaunchTelemetry.redactedAIEditFailureReason("Cloud rendering failed. Try again in a moment.")

        #expect(redacted == "Cloud rendering failed. Try again in a moment.")
    }

    @Test func testStabilitySupportSummaryRedactsUnsafeContext() {
        let summary = LaunchTelemetry.stabilitySupportSummary(
            lifecycleState: "active",
            screen: "https://cdn.hoopsclips.test/render.mp4?X-Amz-Signature=secret",
            checkpoint: "video_import.persist uploads/abc123/source.mp4",
            memoryWarningCount: 2
        )

        #expect(summary.contains("Previous session may have ended unexpectedly."))
        #expect(summary.contains("[redacted_url]"))
        #expect(summary.contains("[redacted_object_key]"))
        #expect(summary.contains("Memory warnings: 2"))
        #expect(!summary.contains("https://"))
        #expect(!summary.contains("X-Amz-Signature"))
        #expect(!summary.contains("uploads/abc123"))
        #expect(!summary.contains("secret"))
    }
}
