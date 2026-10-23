import AssetaSecurity
import Foundation

/// Entry point used by the apps: opens (or creates) the encrypted database with the device key
/// from the Keychain and brings the schema up to date.
public struct LocalStore: Sendable {
    public let database: EncryptedDatabase
    public let outbox: any ClientOperationRepository
    public let attachments: AttachmentRepository
    public let syncState: SyncStateStore
    public let inbox: InboxStore

    public init(database: EncryptedDatabase) {
        self.database = database
        self.outbox = SQLiteClientOperationRepository(database: database)
        self.attachments = AttachmentRepository(database: database)
        self.syncState = SyncStateStore(database: database)
        self.inbox = InboxStore(database: database)
    }

    public static func open(at url: URL, keyProvider: DatabaseKeyProvider) throws -> LocalStore {
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let database = try EncryptedDatabase(url: url, key: try keyProvider.loadOrCreateKey())
        try Migrator.asseta.migrate(database)
        return LocalStore(database: database)
    }

    /// Irreversibly destroys the local database: closes `database` (if given), deletes the file and
    /// its WAL/SHM/journal companions, then deletes the Keychain key so no copy can ever be opened.
    /// Every step is attempted even if an earlier one fails; the first error is rethrown.
    public static func destroy(at url: URL, keyProvider: DatabaseKeyProvider, closing database: EncryptedDatabase? = nil) throws {
        database?.close()
        var firstError: (any Error)?
        for suffix in ["", "-wal", "-shm", "-journal"] {
            let file = URL(fileURLWithPath: url.path + suffix)
            guard FileManager.default.fileExists(atPath: file.path) else { continue }
            do { try FileManager.default.removeItem(at: file) } catch { firstError = firstError ?? error }
        }
        do { try keyProvider.destroyKey() } catch { firstError = firstError ?? error }
        if let firstError { throw firstError }
    }

    /// Default location: Application Support (not backed-up caches), excluded from backups.
    public static func defaultURL(fileName: String = "asseta.sqlite") throws -> URL {
        var directory = try FileManager.default.url(
            for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true
        ).appendingPathComponent("AssetaStore", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try directory.setResourceValues(values)
        #if os(iOS)
        // New files in the directory (WAL, SHM, temp) inherit this class.
        try FileManager.default.setAttributes(
            [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication],
            ofItemAtPath: directory.path
        )
        #endif
        return directory.appendingPathComponent(fileName)
    }
}
