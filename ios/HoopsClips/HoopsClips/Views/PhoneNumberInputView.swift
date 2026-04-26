import SwiftUI

nonisolated struct PhoneRegion: Identifiable, Hashable {
    let id: String
    let flag: String
    let name: String
    let dialCode: String
    let digitGroups: [Int]

    var menuLabel: String {
        "\(flag) \(id) \(dialCode)"
    }

    var fullLabel: String {
        "\(flag) \(name) \(dialCode)"
    }

    static let unitedStates = PhoneRegion(id: "US", flag: "🇺🇸", name: "United States", dialCode: "+1", digitGroups: [3, 3, 4])

    static let supported: [PhoneRegion] = [
        .unitedStates,
        PhoneRegion(id: "CA", flag: "🇨🇦", name: "Canada", dialCode: "+1", digitGroups: [3, 3, 4]),
        PhoneRegion(id: "CN", flag: "🇨🇳", name: "China", dialCode: "+86", digitGroups: [3, 4, 4]),
        PhoneRegion(id: "TW", flag: "🇹🇼", name: "Taiwan", dialCode: "+886", digitGroups: [3, 3, 4]),
        PhoneRegion(id: "HK", flag: "🇭🇰", name: "Hong Kong", dialCode: "+852", digitGroups: [4, 4]),
        PhoneRegion(id: "JP", flag: "🇯🇵", name: "Japan", dialCode: "+81", digitGroups: [3, 4, 4]),
        PhoneRegion(id: "KR", flag: "🇰🇷", name: "South Korea", dialCode: "+82", digitGroups: [3, 4, 4]),
        PhoneRegion(id: "GB", flag: "🇬🇧", name: "United Kingdom", dialCode: "+44", digitGroups: [4, 3, 4]),
        PhoneRegion(id: "AU", flag: "🇦🇺", name: "Australia", dialCode: "+61", digitGroups: [4, 3, 3]),
        PhoneRegion(id: "SG", flag: "🇸🇬", name: "Singapore", dialCode: "+65", digitGroups: [4, 4])
    ]
}

nonisolated enum PhoneNumberFormatter {
    static func digits(in value: String) -> String {
        value.filter(\.isNumber)
    }

    static func nationalDigits(from value: String, region: PhoneRegion) -> String {
        var phoneDigits = digits(in: value)
        let dialDigits = digits(in: region.dialCode)
        let typedWithDialCode = value.trimmingCharacters(in: .whitespacesAndNewlines).hasPrefix("+")

        if typedWithDialCode,
           !dialDigits.isEmpty,
           phoneDigits.hasPrefix(dialDigits) {
            phoneDigits.removeFirst(dialDigits.count)
        }

        return phoneDigits
    }

    static func formattedNationalNumber(from value: String, region: PhoneRegion) -> String {
        let digits = nationalDigits(from: value, region: region)
        guard !digits.isEmpty else { return "" }

        if region.dialCode == "+1" {
            return formatNorthAmerican(digits)
        }

        return formatGroupedDigits(digits, groups: region.digitGroups)
    }

    static func normalizedNumber(from value: String, region: PhoneRegion) -> String {
        let digits = nationalDigits(from: value, region: region)
        guard !digits.isEmpty else { return "" }
        return "\(region.dialCode)\(digits)"
    }

    static func hasEnoughDigits(_ value: String, region: PhoneRegion) -> Bool {
        nationalDigits(from: value, region: region).count >= 6
    }

    private static func formatNorthAmerican(_ digits: String) -> String {
        if digits.count <= 3 {
            return digits
        }

        let areaEnd = digits.index(digits.startIndex, offsetBy: 3)
        let area = String(digits[..<areaEnd])
        let rest = String(digits[areaEnd...])

        if rest.count <= 3 {
            return "(\(area)) \(rest)"
        }

        let prefixEnd = rest.index(rest.startIndex, offsetBy: 3)
        let prefix = String(rest[..<prefixEnd])
        let line = String(rest[prefixEnd...])
        return "(\(area)) \(prefix)-\(line)"
    }

    private static func formatGroupedDigits(_ digits: String, groups: [Int]) -> String {
        var cursor = digits.startIndex
        var chunks: [String] = []

        for groupSize in groups where cursor < digits.endIndex {
            let next = digits.index(cursor, offsetBy: groupSize, limitedBy: digits.endIndex) ?? digits.endIndex
            chunks.append(String(digits[cursor..<next]))
            cursor = next
        }

        if cursor < digits.endIndex {
            chunks.append(String(digits[cursor...]))
        }

        return chunks.joined(separator: " ")
    }
}

struct PhoneNumberInputView: View {
    let title: String
    @Binding var selectedRegion: PhoneRegion
    @Binding var nationalNumber: String
    @Environment(AppLanguageStore.self) private var languageStore

    var normalizedNumber: String {
        PhoneNumberFormatter.normalizedNumber(from: nationalNumber, region: selectedRegion)
    }

    var hasEnoughDigits: Bool {
        PhoneNumberFormatter.hasEnoughDigits(nationalNumber, region: selectedRegion)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.subtleText)

            HStack(spacing: 10) {
                Picker(languageStore.text(.region), selection: $selectedRegion) {
                    ForEach(PhoneRegion.supported) { region in
                        Text(region.fullLabel)
                            .tag(region)
                    }
                }
                .pickerStyle(.menu)
                .tint(AppTheme.neonPurple)
                .frame(minWidth: 116, alignment: .leading)

                TextField(phonePlaceholder, text: $nationalNumber)
                    .keyboardType(.phonePad)
                    .textContentType(.telephoneNumber)
                    .foregroundStyle(.white)
            }
            .padding(14)
            .background(AppTheme.surfaceBg.opacity(0.55), in: .rect(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(AppTheme.softBorder, lineWidth: 1))
            .onChange(of: nationalNumber) { _, newValue in
                let formatted = PhoneNumberFormatter.formattedNationalNumber(from: newValue, region: selectedRegion)
                if formatted != newValue {
                    nationalNumber = formatted
                }
            }
            .onChange(of: selectedRegion) { _, newRegion in
                nationalNumber = PhoneNumberFormatter.formattedNationalNumber(from: nationalNumber, region: newRegion)
            }

            if !normalizedNumber.isEmpty {
                Text("\(languageStore.text(.willSendTo)) \(normalizedNumber)")
                    .font(.caption2.monospacedDigit())
                    .foregroundStyle(AppTheme.subtleText)
            }
        }
    }

    private var phonePlaceholder: String {
        switch selectedRegion.id {
        case "US", "CA":
            return "(555) 123-4567"
        case "CN":
            return "138 0013 8000"
        case "TW":
            return "912 345 678"
        case "HK", "SG":
            return "9123 4567"
        case "JP", "KR":
            return "90 1234 5678"
        case "GB":
            return "7700 900 123"
        case "AU":
            return "0412 345 678"
        default:
            return "Phone number"
        }
    }
}
