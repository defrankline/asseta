import SwiftUI
#if canImport(UIKit)
import UIKit
#endif

/// Status colours shared with the Android apps (`AssetaPalette` in core/ui `AssetaTheme.kt`), with the same light and
/// dark values: live green, recent blue, stale amber, offline red and neutral grey for pills, markers and tinted figures.
public enum Palette {
    public static let live = dynamic(light: 0x248A3D, dark: 0x30D158)
    public static let recent = dynamic(light: 0x0071A4, dark: 0x64D2FF)
    public static let stale = dynamic(light: 0xB87A00, dark: 0xF5A300)
    public static let offline = dynamic(light: 0xD70015, dark: 0xFF453A)
    public static let neutral = dynamic(light: 0x6C6C70, dark: 0x98989F)

    public static var critical: Color { offline }
    public static var warning: Color { stale }
    public static var info: Color { recent }

    private static func dynamic(light: UInt32, dark: UInt32) -> Color {
        #if canImport(UIKit)
        Color(uiColor: UIColor { traits in
            let rgb = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: component(rgb, 16), green: component(rgb, 8), blue: component(rgb, 0), alpha: 1)
        })
        #else
        Color(red: component(light, 16), green: component(light, 8), blue: component(light, 0))
        #endif
    }

    private static func component(_ rgb: UInt32, _ shift: UInt32) -> Double { Double((rgb >> shift) & 0xFF) / 255 }
}
