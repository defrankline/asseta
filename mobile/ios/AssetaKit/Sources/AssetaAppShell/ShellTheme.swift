import SwiftUI
#if canImport(UIKit)
import UIKit
#endif

/// ADR-008 app shell colours (approved Supervisor and Owner designs; dark is the reference, light derived). Same values as
/// Android `ShellColors`.
public enum Shell {
    public static let background = dynamic(light: 0xF4F6F8, dark: 0x0B1722)
    public static let card = dynamic(light: 0xFFFFFF, dark: 0x15283A)
    public static let raised = dynamic(light: 0xE6EDF4, dark: 0x1E3A52)
    public static let drawer = dynamic(light: 0xFFFFFF, dark: 0x102030)
    public static let sunken = dynamic(light: 0xEDF1F5, dark: 0x0F1F2D)
    public static let accent = Color(red: 0xF5 / 255, green: 0xA3 / 255, blue: 0x00 / 255)
    public static let onAccent = Color(red: 0x1A / 255, green: 0x12 / 255, blue: 0x03 / 255)
    public static let text = dynamic(light: 0x0F2A3D, dark: 0xF3F6F9)
    public static let muted = dynamic(light: 0x5B6B7A, dark: 0xB7C4D1)
    public static let faint = dynamic(light: 0x7A8896, dark: 0x8597A8)
    public static let border = dynamic(light: 0xDCE3EA, dark: 0x22394D)
    public static let outline = dynamic(light: 0xC5D0DA, dark: 0x2D4A63)
    public static let disabled = dynamic(light: 0xD5DCE3, dark: 0x3A4B5B)
    public static let goodText = dynamic(light: 0x1E7A44, dark: 0x7BE0A0)
    public static let goodFill = dynamic(light: 0xDDF3E6, dark: 0x10331F)
    public static let goodInfo = dynamic(light: 0x14532D, dark: 0xCFF5DD)
    public static let warnText = dynamic(light: 0x8A5A00, dark: 0xF5C04A)
    public static let warnFill = dynamic(light: 0xFCEFCF, dark: 0x3A2E10)
    public static let badText = dynamic(light: 0xB3261E, dark: 0xFF8A80)
    public static let badFill = dynamic(light: 0xFBE3E1, dark: 0x3D1714)
    public static let badge = Color(red: 0xD9 / 255, green: 0x48 / 255, blue: 0x3B / 255)
    public static let check = dynamic(light: 0x1E7A44, dark: 0x5FD08A)
    /// Split-bar series (customers amber shades, non-productive blues).
    public static let series: [Color] = [accent, dynamic(light: 0xF7C766, dark: 0xF7C766), dynamic(light: 0x3E7CB8, dark: 0x6FA8DC),
                                         dynamic(light: 0x7FAAD3, dark: 0x9DC3E6), dynamic(light: 0x9AA9B7, dark: 0x8597A8)]
    public static let nonProductive = dynamic(light: 0x3E7CB8, dark: 0x6FA8DC)
    public static let scrim = Color(red: 3 / 255, green: 8 / 255, blue: 13 / 255).opacity(0.62)

    static func dynamic(light: UInt32, dark: UInt32) -> Color {
        #if canImport(UIKit)
        Color(uiColor: UIColor { traits in
            let rgb = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: c(rgb, 16), green: c(rgb, 8), blue: c(rgb, 0), alpha: 1)
        })
        #else
        Color(red: c(dark, 16), green: c(dark, 8), blue: c(dark, 0))
        #endif
    }

    private static func c(_ rgb: UInt32, _ shift: UInt32) -> Double { Double((rgb >> shift) & 0xFF) / 255 }
}

// MARK: - Building blocks shared by both apps

/// A rounded card on the shell background.
public struct ShellCard<Content: View>: View {
    let padding: CGFloat
    let fill: Color
    let content: Content

    public init(padding: CGFloat = 16, fill: Color = Shell.card, @ViewBuilder content: () -> Content) {
        self.padding = padding
        self.fill = fill
        self.content = content()
    }

    public var body: some View {
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(fill, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

/// "WHAT DO YOU WANT TO DO?", "RECENT": small caps label above a group.
public struct SectionLabel: View {
    let text: String
    public init(_ text: String) { self.text = text }

    public var body: some View {
        Text(text).font(.system(size: 13, weight: .semibold)).tracking(0.6).foregroundStyle(Shell.muted)
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityAddTraits(.isHeader)
    }
}

/// A status pill ("Awaiting approval", "Paid", "Report due").
public struct ShellPill: View {
    public enum Tone: Sendable { case waiting, good, due, bad, neutral }
    let text: String
    let tone: Tone

    public init(_ text: String, tone: Tone) {
        self.text = text
        self.tone = tone
    }

    public var body: some View {
        Text(text)
            .font(.system(size: 12, weight: tone == .due ? .bold : .semibold))
            .lineLimit(1)
            .padding(.horizontal, 10).padding(.vertical, 4)
            .foregroundStyle(foreground)
            .background(background, in: Capsule())
    }

    private var foreground: Color {
        switch tone {
        case .waiting: Shell.warnText
        case .good: Shell.goodText
        case .due: Shell.onAccent
        case .bad: Shell.badText
        case .neutral: Shell.muted
        }
    }

    private var background: Color {
        switch tone {
        case .waiting: Shell.warnFill
        case .good: Shell.goodFill
        case .due: Shell.accent
        case .bad: Shell.badFill
        case .neutral: Shell.raised
        }
    }
}

/// A small count badge (amber, or red for the inbox).
public struct CountBadge: View {
    let text: String
    let red: Bool
    public init(_ text: String, red: Bool = false) {
        self.text = text
        self.red = red
    }

    public var body: some View {
        Text(text).font(.system(size: 12, weight: .bold))
            .padding(.horizontal, 8).padding(.vertical, 2)
            .foregroundStyle(red ? Color.white : Shell.onAccent)
            .background(red ? Shell.badge : Shell.accent, in: Capsule())
    }
}

/// The amber primary action at the bottom of a screen ("Save sale", "Submit for approval"); grey when disabled.
public struct PrimaryButton: View {
    let title: String
    let enabled: Bool
    let identifier: String?
    let action: () -> Void

    public init(_ title: String, enabled: Bool = true, identifier: String? = nil, action: @escaping () -> Void) {
        self.title = title
        self.enabled = enabled
        self.identifier = identifier
        self.action = action
    }

    public var body: some View {
        Button(action: action) {
            Text(title).font(.system(size: 16, weight: .bold)).multilineTextAlignment(.center)
                .frame(maxWidth: .infinity, minHeight: 54)
                .foregroundStyle(enabled ? Shell.onAccent : Shell.muted)
                .background(enabled ? Shell.accent : Shell.disabled, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityIdentifier(identifier ?? title)
    }
}

/// An outlined secondary button ("+ Customer", "Retake photo").
public struct OutlineButton: View {
    let title: String
    let height: CGFloat
    let action: () -> Void

    public init(_ title: String, height: CGFloat = 48, action: @escaping () -> Void) {
        self.title = title
        self.height = height
        self.action = action
    }

    public var body: some View {
        Button(action: action) {
            Text(title).font(.system(size: 14, weight: .semibold)).foregroundStyle(Shell.text)
                .frame(maxWidth: .infinity, minHeight: height)
                .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(Shell.outline, lineWidth: 1))
        }
        .buttonStyle(.plain)
    }
}

/// Today / Week / Month (or List / Map) segmented chips on a card.
public struct ShellSegments<Value: Hashable>: View {
    let options: [(Value, String)]
    @Binding var selection: Value
    let compact: Bool

    public init(_ options: [(Value, String)], selection: Binding<Value>, compact: Bool = false) {
        self.options = options
        _selection = selection
        self.compact = compact
    }

    public var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(options.enumerated()), id: \.offset) { _, option in
                let on = option.0 == selection
                Button { selection = option.0 } label: {
                    Text(option.1).font(.system(size: compact ? 12 : 13, weight: on ? .semibold : .regular))
                        .foregroundStyle(on ? Shell.text : Shell.muted)
                        .padding(.horizontal, 10).padding(.vertical, compact ? 5 : 7)
                        .background(on ? Shell.raised : Color.clear, in: RoundedRectangle(cornerRadius: compact ? 8 : 9))
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
        .padding(3)
        .background(Shell.card, in: RoundedRectangle(cornerRadius: compact ? 10 : 12))
    }
}

/// The square icon well of a tile or a header button.
public struct IconWell: View {
    let systemImage: String
    let onAccent: Bool

    public init(_ systemImage: String, onAccent: Bool = false) {
        self.systemImage = systemImage
        self.onAccent = onAccent
    }

    public var body: some View {
        Image(systemName: systemImage).font(.system(size: 20, weight: .semibold))
            .foregroundStyle(onAccent ? Shell.onAccent : Shell.accent)
            .frame(width: 44, height: 44)
            .background(onAccent ? Shell.onAccent.opacity(0.12) : Shell.raised, in: RoundedRectangle(cornerRadius: 12))
    }
}

/// A home tile (Sell hours, Machine report, Money, Dashboard / Approvals, Customers, Machines, Money).
public struct HomeTile: View {
    let title: String
    let subtitle: String
    let systemImage: String
    let primary: Bool
    let badge: String?
    let action: () -> Void

    public init(_ title: String, subtitle: String, systemImage: String, primary: Bool = false, badge: String? = nil,
                action: @escaping () -> Void) {
        self.title = title
        self.subtitle = subtitle
        self.systemImage = systemImage
        self.primary = primary
        self.badge = badge
        self.action = action
    }

    public var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .top) {
                    IconWell(systemImage, onAccent: primary)
                    Spacer()
                    if let badge { CountBadge(badge) }
                }
                Spacer(minLength: 8)
                Text(title).font(.system(size: 18, weight: .bold)).foregroundStyle(primary ? Shell.onAccent : Shell.text)
                Text(subtitle).font(.system(size: 13)).foregroundStyle(primary ? Shell.onAccent.opacity(0.85) : Shell.muted)
                    .lineLimit(2).padding(.top, 2)
            }
            .padding(16)
            .frame(maxWidth: .infinity, minHeight: 150, alignment: .leading)
            .background(primary ? Shell.accent : Shell.card, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("tile.\(title)")
    }
}

/// The screen header: a back (or menu) button, the title, and trailing content.
public struct ShellHeader<Trailing: View>: View {
    let title: String
    let subtitle: String?
    let systemImage: String
    let label: String
    let action: () -> Void
    let trailing: Trailing

    public init(_ title: String, subtitle: String? = nil, systemImage: String = "chevron.left", label: String = "Back",
                action: @escaping () -> Void, @ViewBuilder trailing: () -> Trailing) {
        self.title = title
        self.subtitle = subtitle
        self.systemImage = systemImage
        self.label = label
        self.action = action
        self.trailing = trailing()
    }

    public var body: some View {
        HStack(spacing: 12) {
            SquareButton(systemImage, label: label, action: action)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.system(size: 20, weight: .bold)).foregroundStyle(Shell.text).lineLimit(1).minimumScaleFactor(0.7)
                if let subtitle { Text(subtitle).font(.system(size: 13)).foregroundStyle(Shell.muted) }
            }
            Spacer(minLength: 0)
            trailing
        }
        .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 8)
    }
}

extension ShellHeader where Trailing == EmptyView {
    public init(_ title: String, subtitle: String? = nil, systemImage: String = "chevron.left", label: String = "Back",
                action: @escaping () -> Void) {
        self.init(title, subtitle: subtitle, systemImage: systemImage, label: label, action: action) { EmptyView() }
    }
}

/// The 44 pt square button of the header (menu, back).
public struct SquareButton: View {
    let systemImage: String
    let label: String
    let action: () -> Void

    public init(_ systemImage: String, label: String, action: @escaping () -> Void) {
        self.systemImage = systemImage
        self.label = label
        self.action = action
    }

    public var body: some View {
        Button(action: action) {
            Image(systemName: systemImage).font(.system(size: 18, weight: .semibold)).foregroundStyle(Shell.text)
                .frame(width: 44, height: 44)
                .background(Shell.card, in: RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }
}

/// A labelled input box ("Customer", "Hours", "New reading (check the number)").
public struct FieldBox<Content: View>: View {
    let label: String
    let content: Content

    public init(_ label: String, @ViewBuilder content: () -> Content) {
        self.label = label
        self.content = content()
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label).font(.system(size: 12)).foregroundStyle(Shell.muted)
            content.foregroundStyle(Shell.text)
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Shell.card, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

/// The 3-step progress bar of the machine report.
public struct StepBar: View {
    let step: Int
    let of: Int
    public init(step: Int, of: Int = 3) {
        self.step = step
        self.of = of
    }

    public var body: some View {
        HStack(spacing: 6) {
            ForEach(1...of, id: \.self) { i in
                RoundedRectangle(cornerRadius: 4).fill(i <= step ? Shell.accent : Shell.border).frame(height: 4)
            }
        }
        .accessibilityElement()
        .accessibilityLabel("Step \(step) of \(of)")
    }
}

/// A horizontal bar split in coloured parts (report split, productive vs non-productive).
public struct SplitBar: View {
    let parts: [(Double, Color)]
    let height: CGFloat

    public init(_ parts: [(Double, Color)], height: CGFloat = 10) {
        self.parts = parts
        self.height = height
    }

    public var body: some View {
        GeometryReader { geo in
            HStack(spacing: 0) {
                ForEach(Array(parts.enumerated()), id: \.offset) { _, part in
                    Rectangle().fill(part.1).frame(width: max(0, geo.size.width * min(1, part.0)))
                }
                Spacer(minLength: 0)
            }
        }
        .frame(height: height)
        .background(Shell.border)
        .clipShape(RoundedRectangle(cornerRadius: height / 2))
        .accessibilityHidden(true)
    }
}

/// A row of a card list (title, subtitle, trailing view), with a divider below unless last.
public struct CardRow<Trailing: View>: View {
    let title: String
    let subtitle: String?
    let last: Bool
    let trailing: Trailing

    public init(_ title: String, subtitle: String? = nil, last: Bool = false, @ViewBuilder trailing: () -> Trailing) {
        self.title = title
        self.subtitle = subtitle
        self.last = last
        self.trailing = trailing()
    }

    public var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.system(size: 15, weight: .semibold)).foregroundStyle(Shell.text)
                    if let subtitle, !subtitle.isEmpty {
                        Text(subtitle).font(.system(size: 13)).foregroundStyle(Shell.muted)
                    }
                }
                Spacer(minLength: 8)
                trailing
            }
            .padding(.horizontal, 16).padding(.vertical, 13)
            .contentShape(Rectangle())
            if !last { Divider().overlay(Shell.border) }
        }
    }
}

/// A value row ("Cash 5,400,000").
public struct ValueRow: View {
    let title: String
    let value: String
    let bold: Bool
    let last: Bool

    public init(_ title: String, _ value: String, bold: Bool = false, last: Bool = false) {
        self.title = title
        self.value = value
        self.bold = bold
        self.last = last
    }

    public var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(title).font(.system(size: 15, weight: bold ? .bold : .regular))
                Spacer()
                Text(value).font(.system(size: 15, weight: bold ? .bold : .semibold)).monospacedDigit()
            }
            .foregroundStyle(Shell.text)
            .padding(.horizontal, 16).padding(.vertical, 13)
            if !last { Divider().overlay(Shell.border) }
        }
    }
}

// MARK: - Side menu

/// The sliding side menu over the content (a 304 pt panel with a scrim; swipe or tap outside to close).
public struct SideDrawer<Content: View, Menu: View>: View {
    @Binding var isOpen: Bool
    let content: Content
    let menu: Menu
    @GestureState private var drag: CGFloat = 0
    private let width: CGFloat = 304

    public init(isOpen: Binding<Bool>, @ViewBuilder content: () -> Content, @ViewBuilder menu: () -> Menu) {
        _isOpen = isOpen
        self.content = content()
        self.menu = menu()
    }

    public var body: some View {
        ZStack(alignment: .leading) {
            content
                .accessibilityHidden(isOpen)
            if isOpen {
                Shell.scrim.ignoresSafeArea()
                    .onTapGesture { withAnimation(.easeOut(duration: 0.2)) { isOpen = false } }
                    .accessibilityLabel("Close menu")
                    .accessibilityAddTraits(.isButton)
                    .transition(.opacity)
                menu
                    .frame(width: width)
                    .frame(maxHeight: .infinity)
                    .background(Shell.drawer)
                    .clipShape(UnevenRoundedRectangle(topLeadingRadius: 0, bottomLeadingRadius: 0, bottomTrailingRadius: 28,
                                                      topTrailingRadius: 28, style: .continuous))
                    .ignoresSafeArea(edges: .vertical)
                    .offset(x: min(0, drag))
                    .gesture(DragGesture().updating($drag) { value, state, _ in state = value.translation.width }
                        .onEnded { value in
                            if value.translation.width < -80 { withAnimation(.easeOut(duration: 0.2)) { isOpen = false } }
                        })
                    .transition(.move(edge: .leading))
                    .accessibilityAddTraits(.isModal)
            }
        }
        .animation(.easeOut(duration: 0.22), value: isOpen)
    }
}

/// One side-menu entry; `selected` highlights it (raised fill, amber text).
public struct DrawerRow: View {
    let title: String
    let systemImage: String
    let selected: Bool
    let badge: String?
    let redBadge: Bool
    let small: Bool
    let iconColor: Color?
    let action: () -> Void

    public init(_ title: String, systemImage: String, selected: Bool = false, badge: String? = nil, redBadge: Bool = false,
                small: Bool = false, iconColor: Color? = nil, action: @escaping () -> Void) {
        self.title = title
        self.systemImage = systemImage
        self.selected = selected
        self.badge = badge
        self.redBadge = redBadge
        self.small = small
        self.iconColor = iconColor
        self.action = action
    }

    public var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Image(systemName: systemImage).font(.system(size: small ? 17 : 19))
                    .foregroundStyle(selected ? Shell.accent : iconColor ?? Shell.muted).frame(width: 24)
                Text(title).font(.system(size: small ? 14 : 15, weight: selected ? .semibold : .regular))
                    .foregroundStyle(selected ? Shell.accent : small ? Shell.muted : Shell.text)
                Spacer(minLength: 0)
                if let badge { CountBadge(badge, red: redBadge) }
            }
            .padding(.horizontal, 12)
            .frame(height: small ? 44 : 48)
            .background(selected ? Shell.raised : Color.clear, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("menu.\(title)")
    }
}

/// The side menu's header: initials, name and "Role · Company".
public struct DrawerHeader: View {
    let name: String
    let detail: String

    public init(name: String, detail: String) {
        self.name = name
        self.detail = detail
    }

    public var body: some View {
        HStack(spacing: 12) {
            Text(Self.initials(name)).font(.system(size: 18, weight: .bold)).foregroundStyle(Shell.onAccent)
                .frame(width: 48, height: 48).background(Shell.accent, in: Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(name).font(.system(size: 16, weight: .bold)).foregroundStyle(Shell.text).lineLimit(1)
                Text(detail).font(.system(size: 13)).foregroundStyle(Shell.muted).lineLimit(2)
            }
        }
        .padding(.horizontal, 8).padding(.bottom, 20)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// "Daudi Mollel" → "DM".
    public static func initials(_ name: String) -> String {
        let letters = name.split(separator: " ").prefix(2).compactMap(\.first).map { String($0).uppercased() }
        return letters.isEmpty ? "?" : letters.joined()
    }
}
