import AssetaSecurity
import Foundation

/// Entry point used by the apps: opens (or creates) the encrypted database with the device key
/// from the Keychain and brings the schema up to date.
public struct LocalStore: Sendable {
    public let database: EncryptedDatabase
    public let outbox: any ClientOperationRepository

    public static func open(at url: URL, keyProvider: DatabaseKeyProvider) throws -> LocalStore {
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let database = try EncryptedDatabase(url: url, key: try keyProvider.loadOrCreateKey())
        try Migrator.asseta.migrate(database)
        return LocalStore(database: database, outbox: SQLiteClientOperationRepository(database: database))
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
