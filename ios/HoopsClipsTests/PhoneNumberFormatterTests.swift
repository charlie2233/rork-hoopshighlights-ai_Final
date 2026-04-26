import Testing
@testable import HoopsClips

struct PhoneNumberFormatterTests {
    @Test func testFormatsNorthAmericanNumbers() {
        let region = PhoneRegion.unitedStates

        #expect(PhoneNumberFormatter.formattedNationalNumber(from: "5551234567", region: region) == "(555) 123-4567")
        #expect(PhoneNumberFormatter.normalizedNumber(from: "(555) 123-4567", region: region) == "+15551234567")
    }

    @Test func testRemovesTypedDialCodeForSelectedRegion() {
        let region = PhoneRegion.unitedStates

        #expect(PhoneNumberFormatter.formattedNationalNumber(from: "+1 555 123 4567", region: region) == "(555) 123-4567")
        #expect(PhoneNumberFormatter.normalizedNumber(from: "+1 555 123 4567", region: region) == "+15551234567")
    }

    @Test func testFormatsInternationalRegionGroups() {
        let china = PhoneRegion.supported.first { $0.id == "CN" }!

        #expect(PhoneNumberFormatter.formattedNationalNumber(from: "13800138000", region: china) == "138 0013 8000")
        #expect(PhoneNumberFormatter.normalizedNumber(from: "138 0013 8000", region: china) == "+8613800138000")
    }
}
