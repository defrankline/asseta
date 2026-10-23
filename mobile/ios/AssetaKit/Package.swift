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
        .library(name: "AssetaCapture", targets: ["AssetaCapture"]),
        .library(name: "AssetaSync", targets: ["AssetaSync"]),
        .library(name: "AssetaField", targets: ["AssetaField"]),
        .library(name: "AssetaOwnerKit", targets: ["AssetaOwnerKit"]),
        .library(name: "AssetaOwnerUI", targets: ["AssetaOwnerUI"]),
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
        // Gate 4: on-device meter capture (OCR parser + Vision pipeline, GPS, evidence files, validation).
        .target(name: "AssetaCapture", dependencies: ["AssetaModel"], swiftSettings: strict),
        // Gate 4: offline sync engine (device identity, pull, outbox push, resumable blobs, clock, wipe).
        .target(
            name: "AssetaSync",
            dependencies: ["AssetaModel", "AssetaNetwork", "AssetaSecurity", "AssetaStore", "AssetaCapture"],
            swiftSettings: strict
        ),
        // Gate 4: Supervisor field UI (SwiftUI, iOS only; compiles empty on macOS).
        .target(
            name: "AssetaField",
            dependencies: [
                "AssetaAppShell", "AssetaCapture", "AssetaSync", "AssetaStore", "AssetaSecurity", "AssetaNetwork",
                "AssetaModel",
            ],
            swiftSettings: strict
        ),
        // Gate 7: Owner app logic (API, encrypted read-only snapshot cache, staleness, mutation guard,
        // deep links, push registration, realtime feed). Platform-independent and unit-tested on macOS.
        .target(
            name: "AssetaOwnerKit",
            dependencies: ["AssetaModel", "AssetaNetwork", "AssetaStore", "AssetaSecurity"],
            swiftSettings: strict
        ),
        // Gate 7: Owner SwiftUI screens (iOS only; compiles empty on macOS).
        .target(
            name: "AssetaOwnerUI",
            dependencies: ["AssetaAppShell", "AssetaOwnerKit", "AssetaModel", "AssetaNetwork", "AssetaStore", "AssetaSecurity"],
            swiftSettings: strict
        ),
        // Test doubles shared by test targets only (not exported as a product).
        .target(name: "AssetaTestSupport", dependencies: ["AssetaNetwork"], swiftSettings: strict),
        .testTarget(name: "AssetaModelTests", dependencies: ["AssetaModel"]),
        .testTarget(name: "AssetaSecurityTests", dependencies: ["AssetaSecurity"]),
        .testTarget(
            name: "AssetaStoreTests",
            dependencies: [
                "AssetaStore", "AssetaSecurity", "AssetaModel", .product(name: "SQLCipher", package: "SQLCipher.swift"),
            ]
        ),
        .testTarget(name: "AssetaNetworkTests", dependencies: ["AssetaNetwork", "AssetaModel", "AssetaTestSupport"]),
        .testTarget(name: "AssetaAuthTests", dependencies: ["AssetaAuth", "AssetaNetwork", "AssetaSecurity", "AssetaTestSupport"]),
        .testTarget(name: "AssetaCaptureTests", dependencies: ["AssetaCapture", "AssetaModel"]),
        .testTarget(
            name: "AssetaSyncTests",
            dependencies: [
                "AssetaSync", "AssetaCapture", "AssetaStore", "AssetaSecurity", "AssetaNetwork", "AssetaModel",
                "AssetaTestSupport",
            ]
        ),
        .testTarget(
            name: "AssetaOwnerKitTests",
            dependencies: [
                "AssetaOwnerKit", "AssetaModel", "AssetaNetwork", "AssetaStore", "AssetaSecurity", "AssetaTestSupport",
            ]
        ),
        .testTarget(
            name: "AssetaAppShellTests",
            dependencies: [
                "AssetaAppShell", "AssetaAuth", "AssetaNetwork", "AssetaModel", "AssetaSecurity", "AssetaTestSupport",
            ]
        ),
    ],
    swiftLanguageModes: [.v6]
)
