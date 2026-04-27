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

    var billingConfigured: Bool {
        !AppConstants.revenueCatAPIKey.isEmpty
    }

    var billingUnavailableMessage: String {
        "Subscriptions are unavailable in this build."
    }

    var canAnalyze: Bool {
        isProUser || freeUsesRemaining > 0
    }

    func checkSubscriptionStatus() async {
        guard billingConfigured else {
            isProUser = false
            return
        }

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
        guard billingConfigured else {
            errorMessage = billingUnavailableMessage
            return false
        }

        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let result = try await Purchases.shared.purchase(package: package)
            if result.userCancelled {
                return false
            }

            if result.customerInfo.entitlements[entitlementID]?.isActive == true {
                isProUser = true
                return true
            }

            LaunchTelemetry.shared.recordConfigurationIssue(
                "Purchase returned without active \(entitlementID) entitlement for product \(package.storeProduct.productIdentifier)."
            )
            errorMessage = "Purchase finished, but Pro access was not activated. Tap Restore Purchases once, then contact support if it still does not unlock."
            return false
        } catch {
            if (error as NSError).code == RevenueCat.ErrorCode.purchaseCancelledError.rawValue { return false }
            LaunchTelemetry.shared.recordConfigurationIssue("Purchase failed: \(error.localizedDescription)")
            errorMessage = "We couldn't complete the purchase. Please try again."
            return false
        }
    }

    func restorePurchases() async {
        guard billingConfigured else {
            errorMessage = billingUnavailableMessage
            return
        }

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
            LaunchTelemetry.shared.recordConfigurationIssue("Restore purchases failed: \(error.localizedDescription)")
            errorMessage = "We couldn't restore purchases. Please try again."
        }
    }
}
