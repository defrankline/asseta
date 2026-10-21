// swift-tools-version: 6.0
// AssetaKit — shared foundation for the Asseta Supervisor and Owner iOS apps.
// Business rules live here (or on the server), never duplicated in app targets.

import PackageDescription

let strict: [SwiftSetting] = [
    .enableUpcomingFeature("ExistentialAny"),
]

let package = Package(
    name: "AssetaKit",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
    ],
    products: [
        .library(name: "AssetaModel", targets: ["AssetaModel"]),
        .library(name: "AssetaSecurity", targets: ["AssetaSecurity"]),
        .library(name: "AssetaStore", targets: ["AssetaStore"]),
        .library(name: "AssetaNetwork", targets: ["AssetaNetwork"]),
        .library(name: "AssetaAuth", targets: ["AssetaAuth"]),
        .library(name: "AssetaAppShell", targets: ["AssetaAppShell"]),
    ],
    dependencies: [
        // Official Zetetic SQLCipher binary distribution. Pinned exactly; bump deliberately.
        .package(url: "https://github.com/sqlcipher/SQLCipher.swift.git", exact: "4.19.0"),
    ],
    targets: [
        .target(name: "AssetaModel", swiftSettings: strict),
        .target(name: "AssetaSecurity", swiftSettings: strict),
        .target(
            name: "AssetaStore",
            dependencies: [
                "AssetaModel",
                "AssetaSecurity",
                .product(name: "SQLCipher", package: "SQLCipher.swift"),
            ],
            cSettings: [.define("SQLITE_HAS_CODEC")],
            swiftSettings: strict + [.define("SQLITE_HAS_CODEC")]
        ),
        .target(name: "AssetaNetwork", dependencies: ["AssetaModel"], swiftSettings: strict),
        .target(
            name: "AssetaAuth",
            dependencies: ["AssetaModel", "AssetaNetwork", "AssetaSecurity"],
            swiftSettings: strict
        ),
        .target(
            name: "AssetaAppShell",
            dependencies: ["AssetaModel", "AssetaNetwork", "AssetaAuth", "AssetaSecurity"],
            swiftSettings: strict
        ),
        // Test doubles shared by test targets only (not exported as a product).
        .target(name: "AssetaTestSupport", dependencies: ["AssetaNetwork"], swiftSettings: strict),
        .testTarget(name: "AssetaModelTests", dependencies: ["AssetaModel"]),
        .testTarget(name: "AssetaSecurityTests", dependencies: ["AssetaSecurity"]),
        .testTarget(
            name: "AssetaStoreTests",
            dependencies: ["AssetaStore", "AssetaSecurity", .product(name: "SQLCipher", package: "SQLCipher.swift")]
        ),
        .testTarget(name: "AssetaNetworkTests", dependencies: ["AssetaNetwork", "AssetaModel", "AssetaTestSupport"]),
        .testTarget(name: "AssetaAuthTests", dependencies: ["AssetaAuth", "AssetaNetwork", "AssetaSecurity", "AssetaTestSupport"]),
        .testTarget(
            name: "AssetaAppShellTests",
            dependencies: [
                "AssetaAppShell", "AssetaAuth", "AssetaNetwork", "AssetaModel", "AssetaSecurity", "AssetaTestSupport",
            ]
        ),
    ],
    swiftLanguageModes: [.v6]
)
