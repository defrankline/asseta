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
/// files, sync engine, recorder and read-side directory.
final class FieldServices: Sendable {
    let tenantID: UUID
    let deviceID: String
    let databaseURL: URL
    let keyProvider: DatabaseKeyProvider
    let tokens: TokenStore
    let store: LocalStore
    let evidence: EvidenceStore
    let engine: SyncEngine
    let recorder: FieldRecorder
    let directory: FieldDirectory

    init(tenantID: UUID, client: APIClient, secrets: any SecretStore, appVersion: String) throws {
        self.tenantID = tenantID
        deviceID = try DeviceIdentity.loadOrCreate(store: secrets)
        databaseURL = try LocalStore.defaultURL()
        keyProvider = DatabaseKeyProvider(store: secrets)
        tokens = TokenStore(store: secrets)
        store = try LocalStore.open(at: databaseURL, keyProvider: keyProvider)
        evidence = EvidenceStore(directory: try EvidenceStore.defaultDirectory())
        engine = SyncEngine(store: store, evidence: evidence, api: SyncAPI(client: client, deviceID: deviceID),
                            tenantID: tenantID, configuration: SyncConfiguration(appVersion: appVersion))
        recorder = FieldRecorder(store: store, tenantID: tenantID, deviceID: deviceID)
        directory = FieldDirectory(store: store, tenantID: tenantID)
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
