import SwiftUI

/// The Asseta brand mark (`branding/asseta-mark.svg`, 64×64 view box) drawn natively so it stays
/// sharp at any size; the same artwork as Android's `asseta_mark` vector.
public struct AssetaMark: View {
    public init() {}

    public var body: some View {
        Canvas { context, size in
            let s = min(size.width, size.height) / 64
            context.scaleBy(x: s, y: s)
            let tile = Path(roundedRect: CGRect(x: 0, y: 0, width: 64, height: 64), cornerRadius: 14)
            context.fill(tile, with: .color(Brand.slate))

            var legs = Path()
            legs.move(to: CGPoint(x: 13, y: 53)); legs.addLine(to: CGPoint(x: 26, y: 27))
            legs.move(to: CGPoint(x: 38, y: 27)); legs.addLine(to: CGPoint(x: 51, y: 53))
            context.stroke(legs, with: .color(Brand.amber), style: StrokeStyle(lineWidth: 6, lineCap: .round, lineJoin: .round))

            let track = Path(roundedRect: CGRect(x: 18, y: 40, width: 28, height: 9), cornerRadius: 4.5)
            context.stroke(track, with: .color(Brand.amber), style: StrokeStyle(lineWidth: 3.5, lineJoin: .round))
            for x in [25.0, 32, 39] {
                context.fill(Path(ellipseIn: CGRect(x: x - 1.8, y: 44.5 - 1.8, width: 3.6, height: 3.6)),
                             with: .color(Brand.amber))
            }

            var pin = Path()
            pin.move(to: CGPoint(x: 32, y: 33))
            pin.addCurve(to: CGPoint(x: 21.5, y: 18.5), control1: CGPoint(x: 29, y: 29.5), control2: CGPoint(x: 21.5, y: 24.5))
            pin.addArc(center: CGPoint(x: 32, y: 18.5), radius: 10.5, startAngle: .degrees(180), endAngle: .degrees(0),
                       clockwise: false)
            pin.addCurve(to: CGPoint(x: 32, y: 33), control1: CGPoint(x: 42.5, y: 24.5), control2: CGPoint(x: 35, y: 29.5))
            pin.closeSubpath()
            context.stroke(pin, with: .color(Brand.slate), lineWidth: 3.5) // outline under the fill (paint-order stroke)
            context.fill(pin, with: .color(Brand.amber))
            context.fill(Path(ellipseIn: CGRect(x: 32 - 3.8, y: 18.5 - 3.8, width: 7.6, height: 7.6)), with: .color(Brand.slate))
        }
        .aspectRatio(1, contentMode: .fit)
        .accessibilityLabel("Asseta logo")
    }
}
