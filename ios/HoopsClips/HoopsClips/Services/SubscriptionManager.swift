import Foundation
import CryptoKit
import RevenueCat

@Observable
@MainActor
final class SubscriptionManager {
    var isProUser = false
    var freeUsesRemaining: Int = AppConstants.cloudAnalysisDailyQuota
    var isLoading = false
    var errorMessage: String?
    var revenueCatAppUserID: String?
    var lastCustomerInfoUpdatedAt: Date?

    private let freeUsesKey = "hoops_free_uses_remaining"
    private let entitlementID = "pro"

    init() {
        let storedUses = UserDefaults.standard.object(forKey: freeUsesKey) as? Int
        let initialUses = min(max(storedUses ?? AppConstants.cloudAnalysisDailyQuota, 0), AppConstants.cloudAnalysisDailyQuota)
        freeUsesRemaining = initialUses
        UserDefaults.standard.set(initialUses, forKey: freeUsesKey)
    }

    var billingConfigured: Bool {
        !AppConstants.revenueCatAPIKey.isEmpty
    }

    var billingUnavailableMessage: String {
        "Subscriptions are unavailable in this build."
    }

    var proEntitlementID: String {
        entitlementID
    }

    var canAnalyze: Bool {
        isProUser || freeUsesRemaining > 0
    }

    func syncAuthenticatedUser(_ user: AuthUser?) async {
        guard billingConfigured else {
            isProUser = false
            revenueCatAppUserID = nil
            return
        }

        guard let user, user.authMethod != .anonymous else {
            await resetRevenueCatForSignedOutUser()
            return
        }

        guard let appUserID = revenueCatUserID(for: user) else {
            isProUser = false
            LaunchTelemetry.shared.recordConfigurationIssue("RevenueCat sync skipped because the app user ID was empty.")
            return
        }

        if revenueCatAppUserID == appUserID {
            await checkSubscriptionStatus()
            return
        }

        do {
            let result = try await Purchases.shared.logIn(appUserID)
            updateEntitlementState(from: result.customerInfo)
        } catch {
            isProUser = false
            LaunchTelemetry.shared.recordConfigurationIssue("RevenueCat login failed: \(error.localizedDescription)")
        }
    }

    func checkSubscriptionStatus() async {
        guard billingConfigured else {
            isProUser = false
            return
        }

        do {
            let customerInfo = try await Purchases.shared.customerInfo()
            updateEntitlementState(from: customerInfo)
        } catch {
            isProUser = false
            LaunchTelemetry.shared.recordConfigurationIssue("RevenueCat customer info refresh failed: \(error.localizedDescription)")
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

            updateEntitlementState(from: result.customerInfo)
            if isProUser {
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
            updateEntitlementState(from: customerInfo)
            if !isProUser {
                errorMessage = "No active subscription found."
            }
        } catch {
            LaunchTelemetry.shared.recordConfigurationIssue("Restore purchases failed: \(error.localizedDescription)")
            errorMessage = "We couldn't restore purchases. Please try again."
        }
    }

    private func updateEntitlementState(from customerInfo: CustomerInfo) {
        isProUser = customerInfo.entitlements[entitlementID]?.isActive == true
        revenueCatAppUserID = Purchases.shared.appUserID
        lastCustomerInfoUpdatedAt = Date()
    }

    private func resetRevenueCatForSignedOutUser() async {
        guard billingConfigured else {
            isProUser = false
            revenueCatAppUserID = nil
            return
        }

        guard revenueCatAppUserID != nil else {
            isProUser = false
            return
        }

        do {
            _ = try await Purchases.shared.logOut()
        } catch {
            LaunchTelemetry.shared.recordConfigurationIssue("RevenueCat logout failed: \(error.localizedDescription)")
        }

        isProUser = false
        revenueCatAppUserID = nil
        lastCustomerInfoUpdatedAt = Date()
    }

    private func revenueCatUserID(for user: AuthUser) -> String? {
        let trimmedID = user.id.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedID.isEmpty else { return nil }

        let digest = SHA256.hash(data: Data(trimmedID.utf8))
        let hexDigest = digest.map { String(format: "%02x", $0) }.joined()
        return "hoops_\(user.authMethod.rawValue)_\(hexDigest)"
    }
}
