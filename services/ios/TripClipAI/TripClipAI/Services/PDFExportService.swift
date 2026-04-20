import UIKit
import PDFKit

struct PDFExportService {

    static func generateTripPDF(video: VideoResponse) -> Data {
        let pageRect = CGRect(x: 0, y: 0, width: 595, height: 842) // A4
        let renderer = UIGraphicsPDFRenderer(bounds: pageRect)

        return renderer.pdfData { ctx in
            ctx.beginPage()
            var y: CGFloat = 40

            // Başlık
            y = drawText("TripClip AI - Gezi Planı", rect: CGRect(x: 40, y: y, width: 515, height: 36),
                         font: .boldSystemFont(ofSize: 24), color: .black)
            y += 8

            // Alt başlık
            let dateStr = DateFormatter.localizedString(from: Date(), dateStyle: .long, timeStyle: .none)
            y = drawText(dateStr, rect: CGRect(x: 40, y: y, width: 515, height: 20),
                         font: .systemFont(ofSize: 12), color: .gray)
            y += 20

            // Lokasyonlar
            if let locations = video.aiResults?.nominatim?.deduplicatedLocations, !locations.isEmpty {
                y = drawSectionTitle("Gezilecek Yerler", y: y, pageRect: pageRect)
                for loc in locations {
                    let coordText: String
                    if let lat = loc.placeData?.location?.lat, let lng = loc.placeData?.location?.lng {
                        coordText = "  (\(String(format: "%.4f", lat)), \(String(format: "%.4f", lng)))"
                    } else { coordText = "" }
                    y = drawText("📍 \(loc.originalName)\(coordText)",
                                 rect: CGRect(x: 50, y: y, width: 495, height: 20),
                                 font: .systemFont(ofSize: 12), color: .darkGray)
                    y += 4
                    if y > pageRect.height - 60 { ctx.beginPage(); y = 40 }
                }
                y += 12
            }

            // Mekanlar
            if let pois = video.aiResults?.ocrPois, !pois.isEmpty {
                y = drawSectionTitle("Mekanlar", y: y, pageRect: pageRect)
                for poi in pois {
                    y = drawText("🏪 \(poi)", rect: CGRect(x: 50, y: y, width: 495, height: 20),
                                 font: .systemFont(ofSize: 12), color: .darkGray)
                    y += 4
                    if y > pageRect.height - 60 { ctx.beginPage(); y = 40 }
                }
                y += 12
            }

            // Seyahat İpuçları
            if let tips = video.aiResults?.rag?.travelTips?.tips, !tips.isEmpty {
                y = drawSectionTitle("Seyahat İpuçları", y: y, pageRect: pageRect)
                for tip in tips {
                    y = drawText("📌 \(tip.location)", rect: CGRect(x: 50, y: y, width: 495, height: 18),
                                 font: .boldSystemFont(ofSize: 11), color: .black)
                    y += 2
                    y = drawText(tip.tip, rect: CGRect(x: 60, y: y, width: 475, height: 60),
                                 font: .systemFont(ofSize: 10), color: .gray)
                    y += 8
                    if y > pageRect.height - 60 { ctx.beginPage(); y = 40 }
                }
                y += 12
            }

            // Özet
            if let summary = video.aiResults?.rag?.travelTips?.summary {
                y = drawSectionTitle("Gezi Özeti", y: y, pageRect: pageRect)
                _ = drawText(summary, rect: CGRect(x: 50, y: y, width: 495, height: 200),
                             font: .systemFont(ofSize: 11), color: .darkGray)
            }

            // Footer
            drawText("Oluşturan: TripClip AI • \(dateStr)",
                     rect: CGRect(x: 40, y: pageRect.height - 30, width: 515, height: 16),
                     font: .systemFont(ofSize: 9), color: .lightGray)
        }
    }

    @discardableResult
    private static func drawText(_ text: String, rect: CGRect, font: UIFont, color: UIColor) -> CGFloat {
        let attrs: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: color]
        let str = NSString(string: text)
        str.draw(in: rect, withAttributes: attrs)
        let boundingRect = str.boundingRect(with: CGSize(width: rect.width, height: .greatestFiniteMagnitude),
                                            options: .usesLineFragmentOrigin, attributes: attrs, context: nil)
        return rect.origin.y + boundingRect.height
    }

    @discardableResult
    private static func drawSectionTitle(_ title: String, y: CGFloat, pageRect: CGRect) -> CGFloat {
        let titleRect = CGRect(x: 40, y: y, width: 515, height: 24)
        UIColor.systemBlue.setFill()
        UIBezierPath(rect: CGRect(x: 40, y: y + 20, width: 515, height: 1)).fill()
        return drawText(title, rect: titleRect, font: .boldSystemFont(ofSize: 14), color: .systemBlue) + 8
    }
}
