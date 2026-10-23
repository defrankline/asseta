import SwiftUI

/// The Asseta brand mark ("A" whose apex is a GPS pin, crossbar a crawler track) drawn from
/// `branding/asseta-mark.svg` (64×64 view box), the same artwork as the Android `asseta_mark` drawable and the
/// app icon. Vector, so it stays sharp at any size.
public struct BrandMark: View {
    public init() {}

    public var body: some View {
        Canvas { context, size in
            let s = min(size.width, size.height) / 64
            context.translateBy(x: (size.width - 64 * s) / 2, y: (size.height - 64 * s) / 2)
            context.scaleBy(x: s, y: s)
            let slate = GraphicsContext.Shading.color(Brand.slate)
            let amber = GraphicsContext.Shading.color(Brand.amber)

            context.fill(Path(roundedRect: CGRect(x: 0, y: 0, width: 64, height: 64), cornerRadius: 14), with: slate)
            // Legs of the "A".
            var legs = Path()
            legs.move(to: CGPoint(x: 13, y: 53)); legs.addLine(to: CGPoint(x: 26, y: 27))
            legs.move(to: CGPoint(x: 38, y: 27)); legs.addLine(to: CGPoint(x: 51, y: 53))
            context.stroke(legs, with: amber, style: StrokeStyle(lineWidth: 6, lineCap: .round, lineJoin: .round))
            // Crawler track with three rollers.
            context.stroke(Path(roundedRect: CGRect(x: 18, y: 40, width: 28, height: 9), cornerRadius: 4.5), with: amber,
                           style: StrokeStyle(lineWidth: 3.5, lineJoin: .round))
            for x in [25.0, 32.0, 39.0] {
                context.fill(Path(ellipseIn: CGRect(x: x - 1.8, y: 44.5 - 1.8, width: 3.6, height: 3.6)), with: amber)
            }
            // GPS pin apex: slate outline under the amber body, then the slate hole.
            let pin = Self.pin()
            context.stroke(pin, with: slate, style: StrokeStyle(lineWidth: 3.5, lineJoin: .round))
            context.fill(pin, with: amber)
            context.fill(Path(ellipseIn: CGRect(x: 32 - 3.8, y: 18.5 - 3.8, width: 7.6, height: 7.6)), with: slate)
        }
        .aspectRatio(1, contentMode: .fit)
        .accessibilityLabel("Asseta logo")
    }

    /// `M32 33 C29 29.5 21.5 24.5 21.5 18.5 a10.5 10.5 0 0 1 21 0 C42.5 24.5 35 29.5 32 33 Z`
    static func pin() -> Path {
        var p = Path()
        p.move(to: CGPoint(x: 32, y: 33))
        p.addCurve(to: CGPoint(x: 21.5, y: 18.5), control1: CGPoint(x: 29, y: 29.5), control2: CGPoint(x: 21.5, y: 24.5))
        p.addArc(center: CGPoint(x: 32, y: 18.5), radius: 10.5, startAngle: .degrees(180), endAngle: .degrees(0), clockwise: false)
        p.addCurve(to: CGPoint(x: 32, y: 33), control1: CGPoint(x: 42.5, y: 24.5), control2: CGPoint(x: 35, y: 29.5))
        p.closeSubpath()
        return p
    }
}

