import XCTest
@testable import TripClipApp

final class AIConsentStoreTests: XCTestCase {
    private var storage: UserDefaults!
    private var suite: String!

    override func setUp() {
        super.setUp()
        suite = "tripclip.consent.tests.\(UUID().uuidString)"
        storage = UserDefaults(suiteName: suite)
    }

    override func tearDown() {
        storage.removePersistentDomain(forName: suite)
        storage = nil
        super.tearDown()
    }

    func test_permissionDefaultsToDeniedAndIsAccountScoped() {
        XCTAssertFalse(AIConsentStore.hasConsent(userID: 1, in: storage))
        XCTAssertTrue(AIConsentStore.grant(userID: 1, in: storage))
        XCTAssertTrue(AIConsentStore.hasConsent(userID: 1, in: storage))
        XCTAssertFalse(AIConsentStore.hasConsent(userID: 2, in: storage))
        XCTAssertFalse(AIConsentStore.hasConsent(userID: 0, in: storage))
    }

    func test_changedDisclosureOrServerRequiresNewPermission() {
        AIConsentStore.grant(userID: 1, in: storage)
        storage.set(["userID": 1, "signature": "previous-provider-or-server"], forKey: AIConsentStore.key)
        XCTAssertFalse(AIConsentStore.hasConsent(userID: 1, in: storage))
    }

    func test_revokeStopsNewSharingAndMissingStorageCannotGrant() {
        AIConsentStore.grant(userID: 1, in: storage)
        AIConsentStore.revoke(in: storage)
        XCTAssertFalse(AIConsentStore.hasConsent(userID: 1, in: storage))
        XCTAssertFalse(AIConsentStore.grant(userID: 0, in: storage))
        XCTAssertFalse(AIConsentStore.grant(userID: 1, in: nil))
    }
}
