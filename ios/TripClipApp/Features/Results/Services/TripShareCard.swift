import UIKit

// Renders a 9:16 Instagram Story-format share card.
// Ported from services/ios/TripClipAI — adapted to new LocationPin model.
struct TripShareCard {

    /// Kartı PNG olarak geçici dosyaya yazar. Dosya URL'i paylaşıldığında
    /// paylaşım sayfasında gerçek önizleme ve düzgün bir dosya adı görünür —
    /// ham `UIImage` ile jenerik bir yer tutucu çıkıyordu.
    static func exportToFile(plan: PlanDetail, title: String) -> URL? {
        guard let png = render(plan: plan).pngData() else { return nil }
        let name = ShareExport.sanitizedFilename(title, fallback: "TripClip-Gezi-\(plan.id)")
        return ShareExport.writeTemporaryFile(png, filename: "\(name).png")
    }

    static func render(plan: PlanDetail) -> UIImage {
        let city     = plan.locations.first?.name.capitalized ?? "Türkiye"
        let count    = plan.locations.count
        let allNames = plan.locations.prefix(5).map { $0.name.capitalized }.joined(separator: " · ")

        let size     = CGSize(width: 1080, height: 1920)
        let renderer = UIGraphicsImageRenderer(size: size)

        // Fixed dark card — a shareable branded export, not an app screen,
        // so it always renders in the dark ground regardless of system appearance.
        let accent = UIColor(red: 1.0, green: 0.690, blue: 0.125, alpha: 1) // Ember

        return renderer.image { ctx in
            let cg = ctx.cgContext

            // Background — same dark ground as the app itself, not an invented gradient.
            let bgColors = [
                UIColor(red: 0.047, green: 0.051, blue: 0.063, alpha: 1).cgColor, // bg
                UIColor(red: 0.102, green: 0.110, blue: 0.129, alpha: 1).cgColor, // surface
            ]
            let bgGrad = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(),
                                    colors: bgColors as CFArray, locations: [0, 1])!
            cg.drawLinearGradient(bgGrad,
                                  start: .zero, end: CGPoint(x: size.width, y: size.height),
                                  options: [])

            // Grid pattern
            cg.setStrokeColor(UIColor(white: 1, alpha: 0.04).cgColor)
            cg.setLineWidth(1)
            stride(from: CGFloat(0), through: size.width,  by: 80).forEach {
                cg.move(to: CGPoint(x: $0, y: 0)); cg.addLine(to: CGPoint(x: $0, y: size.height))
            }
            stride(from: CGFloat(0), through: size.height, by: 80).forEach {
                cg.move(to: CGPoint(x: 0, y: $0)); cg.addLine(to: CGPoint(x: size.width, y: $0))
            }
            cg.strokePath()

            // Brand
            let logoAttrs:  [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 52, weight: .black), .foregroundColor: UIColor.white
            ]
            let clipAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 52, weight: .black), .foregroundColor: accent
            ]
            let logo = NSMutableAttributedString(string: "Trip", attributes: logoAttrs)
            logo.append(NSAttributedString(string: "Clip", attributes: clipAttrs))
            logo.draw(at: CGPoint(x: 80, y: 100))

            // Main city label
            let midY: CGFloat  = size.height * 0.38
            let cityAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 110, weight: .black), .foregroundColor: UIColor.white
            ]
            let cityStr  = city as NSString
            let citySize = cityStr.size(withAttributes: cityAttrs)
            cityStr.draw(at: CGPoint(x: (size.width - citySize.width) / 2, y: midY),
                         withAttributes: cityAttrs)

            // Subtitle
            let subAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 40, weight: .medium),
                .foregroundColor: UIColor(white: 1, alpha: 0.5)
            ]
            let sub     = "Gezi Planı" as NSString
            let subSize = sub.size(withAttributes: subAttrs)
            sub.draw(at: CGPoint(x: (size.width - subSize.width) / 2, y: midY + citySize.height + 10),
                     withAttributes: subAttrs)

            // Count badge
            let badgeY    = midY + citySize.height + 80
            let badgeRect = CGRect(x: (size.width - 300) / 2, y: badgeY, width: 300, height: 72)
            accent.withAlphaComponent(0.12).setFill()
            UIBezierPath(roundedRect: badgeRect, cornerRadius: 36).fill()
            accent.withAlphaComponent(0.3).setStroke()
            UIBezierPath(roundedRect: badgeRect, cornerRadius: 36).stroke()

            let badgeText  = "\(count) Mekan Keşfedildi" as NSString
            let badgeAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 28, weight: .bold), .foregroundColor: accent
            ]
            let bs = badgeText.size(withAttributes: badgeAttrs)
            badgeText.draw(at: CGPoint(x: (size.width - bs.width) / 2, y: badgeY + (72 - bs.height) / 2),
                           withAttributes: badgeAttrs)

            // Location names
            if !allNames.isEmpty {
                let namesAttrs: [NSAttributedString.Key: Any] = [
                    .font: UIFont.systemFont(ofSize: 28, weight: .regular),
                    .foregroundColor: UIColor(white: 1, alpha: 0.4)
                ]
                let ns     = allNames as NSString
                let nsSize = ns.size(withAttributes: namesAttrs)
                ns.draw(at: CGPoint(x: max(80, (size.width - nsSize.width) / 2), y: badgeY + 90),
                        withAttributes: namesAttrs)
            }

            // Footer separator
            cg.setStrokeColor(UIColor(white: 1, alpha: 0.08).cgColor)
            cg.setLineWidth(1)
            cg.move(to: CGPoint(x: 80, y: size.height - 200))
            cg.addLine(to: CGPoint(x: size.width - 80, y: size.height - 200))
            cg.strokePath()

            let urlAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.monospacedSystemFont(ofSize: 26, weight: .regular),
                .foregroundColor: UIColor(white: 1, alpha: 0.3)
            ]
            ("tripclip.ai  ·  AI ile oluşturuldu" as NSString)
                .draw(at: CGPoint(x: 80, y: size.height - 160), withAttributes: urlAttrs)
        }
    }
}
