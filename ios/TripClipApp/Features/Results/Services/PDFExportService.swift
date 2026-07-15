import UIKit

// Generates an A4 PDF from a PlanDetail.
// Ported from services/ios/TripClipAI — adapted to new PlanDetail model.
struct PDFExportService {

    static func generate(plan: PlanDetail) -> Data {
        let pageRect = CGRect(x: 0, y: 0, width: 595, height: 842) // A4
        let renderer = UIGraphicsPDFRenderer(bounds: pageRect)

        return renderer.pdfData { ctx in
            ctx.beginPage()
            var y: CGFloat = 40

            // Title
            let city = plan.locations.first?.name.capitalized ?? "Gezi Planı"
            y = drawText("TripClip AI — \(city)",
                         rect: CGRect(x: 40, y: y, width: 515, height: 36),
                         font: .boldSystemFont(ofSize: 22), color: .black)
            y += 6

            let dateStr = DateFormatter.localizedString(from: Date(), dateStyle: .long, timeStyle: .none)
            y = drawText(dateStr, rect: CGRect(x: 40, y: y, width: 515, height: 20),
                         font: .systemFont(ofSize: 11), color: .gray)
            y += 20

            // Locations
            if !plan.locations.isEmpty {
                y = sectionTitle("Gezilecek Yerler", y: y, page: pageRect)
                for loc in plan.locations {
                    let coord = "(\(String(format: "%.4f", loc.latitude)), \(String(format: "%.4f", loc.longitude)))"
                    y = drawText("📍 \(loc.name)  \(coord)",
                                 rect: CGRect(x: 50, y: y, width: 495, height: 20),
                                 font: .systemFont(ofSize: 11), color: .darkGray)
                    y += 3
                    if y > pageRect.height - 60 { ctx.beginPage(); y = 40 }
                }
                y += 10
            }

            // OCR POIs
            if !plan.ocrPois.isEmpty {
                y = sectionTitle("Mekanlar", y: y, page: pageRect)
                for poi in plan.ocrPois {
                    y = drawText("🏪 \(poi)", rect: CGRect(x: 50, y: y, width: 495, height: 20),
                                 font: .systemFont(ofSize: 11), color: .darkGray)
                    y += 3
                    if y > pageRect.height - 60 { ctx.beginPage(); y = 40 }
                }
                y += 10
            }

            // Travel tips
            if !plan.travelTips.isEmpty {
                y = sectionTitle("Seyahat İpuçları", y: y, page: pageRect)
                for tip in plan.travelTips {
                    y = drawText("📌 \(tip.location)", rect: CGRect(x: 50, y: y, width: 495, height: 18),
                                 font: .boldSystemFont(ofSize: 10), color: .black)
                    y += 1
                    y = drawText(tip.tip, rect: CGRect(x: 60, y: y, width: 475, height: 60),
                                 font: .systemFont(ofSize: 10), color: .gray)
                    y += 6
                    if y > pageRect.height - 60 { ctx.beginPage(); y = 40 }
                }
                y += 10
            }

            // Transcription
            if let transcript = plan.transcription, !transcript.isEmpty {
                y = sectionTitle("Ses Transkripsiyonu", y: y, page: pageRect)
                _ = drawText(transcript, rect: CGRect(x: 50, y: y, width: 495, height: 200),
                             font: .systemFont(ofSize: 10), color: .darkGray)
            }

            // Footer
            drawText("Oluşturan: TripClip AI · \(dateStr)",
                     rect: CGRect(x: 40, y: pageRect.height - 30, width: 515, height: 16),
                     font: .systemFont(ofSize: 8), color: .lightGray)
        }
    }

    @discardableResult
    private static func drawText(_ text: String, rect: CGRect, font: UIFont, color: UIColor) -> CGFloat {
        let attrs: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: color]
        let ns = text as NSString
        ns.draw(in: rect, withAttributes: attrs)
        let bound = ns.boundingRect(
            with: CGSize(width: rect.width, height: .greatestFiniteMagnitude),
            options: .usesLineFragmentOrigin, attributes: attrs, context: nil
        )
        return rect.origin.y + bound.height
    }

    @discardableResult
    private static func sectionTitle(_ title: String, y: CGFloat, page: CGRect) -> CGFloat {
        let rect = CGRect(x: 40, y: y, width: 515, height: 24)
        UIColor.systemBlue.setFill()
        UIBezierPath(rect: CGRect(x: 40, y: y + 20, width: 515, height: 1)).fill()
        return drawText(title, rect: rect, font: .boldSystemFont(ofSize: 13), color: .systemBlue) + 6
    }
}
