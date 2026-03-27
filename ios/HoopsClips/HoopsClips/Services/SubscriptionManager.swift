import Foundation
import RevenueCat

@Observable
@MainActor
final class SubscriptionManager {
    var isProUser = false
    var freeUsesRemaining: Int = AppConstants.cloudAnalysisDailyQuota
    var isLoading = false
    var errorMessage: String?

    private let freeUsesKey = "hoops_free_uses_remaining"
    private let entitlementID = "pro"

    init() {
        let storedUses = UserDefaults.standard.object(forKey: freeUsesKey) as? Int
        let initialUses = max(storedUses ?? 0, AppConstants.cloudAnalysisDailyQuota)
        freeUsesRemaining = initialUses
        UserDefaults.standard.set(initialUses, forKey: freeUsesKey)
    }

    var canAnalyze: Bool {
        isProUser || freeUsesRemaining > 0
    }

    func checkSubscriptionStatus() async {
        do {
            let customerInfo = try await Purchases.shared.customerInfo()
            isProUser = customerInfo.entitlements[entitlementID]?.isActive == true
        } catch {
            isProUser = false
        }
    }

    func consumeFreeUse() {
        guard !isProUser, freeUsesRemaining > 0 else { return }
        freeUsesRemaining -= 1
        UserDefaults.standard.set(freeUsesRemaining, forKey: freeUsesKey)
    }

    func purchase(package: Package) async -> Bool {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let result = try await Purchases.shared.purchase(package: package)
            if result.customerInfo.entitlements[entitlementID]?.isActive == true {
                isProUser = true
                return true
            }
            return false
        } catch {
            if (error as NSError).code == RevenueCat.ErrorCode.purchaseCancelledError.rawValue { return false }
            errorMessage = error.localizedDescription
            return false
        }
    }

    func restorePurchases() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let customerInfo = try await Purchases.shared.restorePurchases()
            isProUser = customerInfo.entitlements[entitlementID]?.isActive == true
            if !isProUser {
                errorMessage = "No active subscription found."
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
