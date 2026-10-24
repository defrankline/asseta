#if os(iOS)
import AssetaAppShell
import AssetaCapture
import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaStore
import AssetaSync
import Foundation

/// Non-UI dependency graph of the field app for one signed-in tenant: encrypted store, evidence
/// files, sync engine, recorder and read-side directory. Everything is scoped to the signed-in
/// `account`: opening the field resets the tenant's sync state when another user synced it last
/// (fresh bootstrap), and that user's unsynced work is held for them.
final class FieldServices: Sendable {
    let tenantID: UUID
    let account: AccountIdentity
    let deviceID: String
    let databaseURL: URL
    let keyProvider: DatabaseKeyProvider
    let tokens: TokenStore
    let store: LocalStore
    let evidence: EvidenceStore
    let engine: SyncEngine
    let recorder: FieldRecorder
    let directory: FieldDirectory
    /// The supervisor's own records (server copies merged with this phone's) behind every tab.
    let inbox: InboxDirectory
    let online: SupervisorOnline
    /// Saved accountability policies and lists (custodians, cash to acknowledge, purchases, reasons).
    let accountability: AccountabilityDirectory

    /// `launchAccount` is the user signed in when the app launched: owner of data written before
    /// owners were recorded.
    init(tenantID: UUID, account: AccountIdentity, launchAccount: AccountIdentity?, client: APIClient,
         secrets: any SecretStore, appVersion: String) throws {
        self.tenantID = tenantID
        self.account = account
        deviceID = try DeviceIdentity.loadOrCreate(store: secrets)
        databaseURL = try LocalStore.defaultURL()
        keyProvider = DatabaseKeyProvider(store: secrets)
        tokens = TokenStore(store: secrets)
        store = try LocalStore.open(at: databaseURL, keyProvider: keyProvider)
        try store.adoptLegacyData(owner: launchAccount)
        // Before anything is shown: another user's synced data for this tenant is reset.
        try store.syncState.claim(tenantID: tenantID, owner: account.subject)
        evidence = EvidenceStore(directory: try EvidenceStore.defaultDirectory())
        engine = SyncEngine(store: store, evidence: evidence, api: SyncAPI(client: client, deviceID: deviceID),
                            tenantID: tenantID, configuration: SyncConfiguration(appVersion: appVersion), account: account)
        recorder = FieldRecorder(store: store, tenantID: tenantID, deviceID: deviceID, owner: account)
        directory = FieldDirectory(store: store, tenantID: tenantID, owner: account)
        inbox = InboxDirectory(store: store, tenantID: tenantID, owner: account)
        online = SupervisorOnline(client: client, store: store, tenantID: tenantID)
        accountability = AccountabilityDirectory(store: store, tenantID: tenantID, owner: account)
    }

    /// `DEVICE_REVOKED`: erase database + key, tokens and evidence files.
    func wipe() -> [any Error] {
        DeviceWipe.wipe(database: store.database, databaseURL: databaseURL, keyProvider: keyProvider, tokens: tokens,
                        evidence: evidence)
    }

    static var appVersion: String {
        let info = Bundle.main.infoDictionary ?? [:]
        let short = info["CFBundleShortVersionString"] as? String ?? "0"
        let build = info["CFBundleVersion"] as? String ?? "0"
        return "\(short) (\(build))"
    }
}
#endif
