import UIKit
import SwiftUI

/// Instagram Story / sosyal medya paylaşımı için 9:16 kart oluşturur
struct TripShareCard {

    static func render(video: VideoResponse) -> UIImage {
        let locations  = video.aiResults?.nominatim?.deduplicatedLocations ?? []
        let city       = locations.first?.originalName.capitalized ?? "Türkiye"
        let count      = locations.count
        let allNames   = locations.prefix(5).map { $0.originalName.capitalized }.joined(separator: " · ")

        // 9:16 Instagram Story boyutu
        let size = CGSize(width: 1080, height: 1920)
        let renderer = UIGraphicsImageRenderer(size: size)

        return renderer.image { ctx in
            let context = ctx.cgContext

            // ── Arka plan gradient ──────────────────────────────────────────
            let bgColors = [
                UIColor(red: 0.04, green: 0.06, blue: 0.10, alpha: 1).cgColor,
                UIColor(red: 0.05, green: 0.08, blue: 0.20, alpha: 1).cgColor,
            ]
            let bgGradient = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(),
                                        colors: bgColors as CFArray,
                                        locations: [0, 1])!
            context.drawLinearGradient(bgGradient,
                                       start: CGPoint(x: 0, y: 0),
                                       end:   CGPoint(x: size.width, y: size.height),
                                       options: [])

            // ── Grid pattern ────────────────────────────────────────────────
            context.setStrokeColor(UIColor(white: 1, alpha: 0.04).cgColor)
            context.setLineWidth(1)
            let gridSize: CGFloat = 80
            var x: CGFloat = 0
            while x <= size.width { context.move(to: CGPoint(x: x, y: 0)); context.addLine(to: CGPoint(x: x, y: size.height)); x += gridSize }
            var y: CGFloat = 0
            while y <= size.height { context.move(to: CGPoint(x: 0, y: y)); context.addLine(to: CGPoint(x: size.width, y: y)); y += gridSize }
            context.strokePath()

            // ── Neon glow orb ────────────────────────────────────────────────
            let orbColors = [
                UIColor(red: 0.30, green: 1.0, blue: 0.76, alpha: 0.18).cgColor,
                UIColor.clear.cgColor
            ]
            let orbGradient = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(),
                                         colors: orbColors as CFArray,
                                         locations: [0, 1])!
            let orbCenter = CGPoint(x: size.width * 0.8, y: size.height * 0.25)
            context.drawRadialGradient(orbGradient,
                                       startCenter: orbCenter, startRadius: 0,
                                       endCenter: orbCenter, endRadius: 500,
                                       options: [])

            // ── Logo / Marka ────────────────────────────────────────────────
            let logoAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 52, weight: .black),
                .foregroundColor: UIColor.white
            ]
            let neonAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 52, weight: .black),
                .foregroundColor: UIColor(red: 0.30, green: 1.0, blue: 0.76, alpha: 1)
            ]
            let logoStr = NSMutableAttributedString(string: "Trip", attributes: logoAttrs)
            logoStr.append(NSAttributedString(string: "Clip", attributes: neonAttrs))
            logoStr.draw(at: CGPoint(x: 80, y: 100))

            let aiTag = "AI" as NSString
            let aiRect = CGRect(x: 80 + logoStr.size().width + 16, y: 110, width: 70, height: 36)
            UIColor(red: 0.30, green: 1.0, blue: 0.76, alpha: 0.15).setFill()
            UIBezierPath(roundedRect: aiRect, cornerRadius: 8).fill()
            UIColor(red: 0.30, green: 1.0, blue: 0.76, alpha: 0.5).setStroke()
            UIBezierPath(roundedRect: aiRect, cornerRadius: 8).stroke()
            let aiAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.monospacedSystemFont(ofSize: 18, weight: .bold),
                .foregroundColor: UIColor(red: 0.30, green: 1.0, blue: 0.76, alpha: 0.8)
            ]
            aiTag.draw(in: aiRect.insetBy(dx: 12, dy: 8), withAttributes: aiAttrs)

            // ── Ana içerik — orta ───────────────────────────────────────────
            let midY: CGFloat = size.height * 0.38

            // Şehir adı (büyük)
            let cityAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 110, weight: .black),
                .foregroundColor: UIColor.white
            ]
            let cityStr = city as NSString
            let citySize = cityStr.size(withAttributes: cityAttrs)
            cityStr.draw(at: CGPoint(x: (size.width - citySize.width) / 2, y: midY), withAttributes: cityAttrs)

            // "Gezi Planı" subtitle
            let subAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 42, weight: .medium),
                .foregroundColor: UIColor(white: 1, alpha: 0.5)
            ]
            let subStr = "Gezi Planı" as NSString
            let subSize = subStr.size(withAttributes: subAttrs)
            subStr.draw(at: CGPoint(x: (size.width - subSize.width) / 2, y: midY + citySize.height + 10), withAttributes: subAttrs)

            // ── Mekan sayısı badge ──────────────────────────────────────────
            let badgeY = midY + citySize.height + 80
            let badgeRect = CGRect(x: (size.width - 300) / 2, y: badgeY, width: 300, height: 72)
            UIColor(red: 0.30, green: 1.0, blue: 0.76, alpha: 0.12).setFill()
            UIBezierPath(roundedRect: badgeRect, cornerRadius: 36).fill()
            UIColor(red: 0.30, green: 1.0, blue: 0.76, alpha: 0.3).setStroke()
            UIBezierPath(roundedRect: badgeRect, cornerRadius: 36).stroke()

            let badgeText = "\(count) Mekan Keşfedildi" as NSString
            let badgeAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 28, weight: .bold),
                .foregroundColor: UIColor(red: 0.30, green: 1.0, blue: 0.76, alpha: 1)
            ]
            let badgeSize = badgeText.size(withAttributes: badgeAttrs)
            badgeText.draw(at: CGPoint(x: (size.width - badgeSize.width) / 2,
                                       y: badgeY + (72 - badgeSize.height) / 2),
                          withAttributes: badgeAttrs)

            // ── Mekan listesi ───────────────────────────────────────────────
            if !allNames.isEmpty {
                let namesAttrs: [NSAttributedString.Key: Any] = [
                    .font: UIFont.systemFont(ofSize: 30, weight: .regular),
                    .foregroundColor: UIColor(white: 1, alpha: 0.45)
                ]
                let namesStr = allNames as NSString
                let namesSize = namesStr.size(withAttributes: namesAttrs)
                namesStr.draw(at: CGPoint(x: max(80, (size.width - namesSize.width) / 2),
                                          y: badgeY + 90), withAttributes: namesAttrs)
            }

            // ── Alt çizgi ve url ────────────────────────────────────────────
            context.setStrokeColor(UIColor(white: 1, alpha: 0.08).cgColor)
            context.setLineWidth(1)
            context.move(to: CGPoint(x: 80, y: size.height - 200))
            context.addLine(to: CGPoint(x: size.width - 80, y: size.height - 200))
            context.strokePath()

            let urlAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.monospacedSystemFont(ofSize: 28, weight: .regular),
                .foregroundColor: UIColor(white: 1, alpha: 0.3)
            ]
            ("tripclip.ai  ·  AI ile oluşturuldu" as NSString)
                .draw(at: CGPoint(x: 80, y: size.height - 160), withAttributes: urlAttrs)
        }
    }
}
