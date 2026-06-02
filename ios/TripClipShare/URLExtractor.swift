/// URLExtractor.swift — TripClip Share Extension
///
/// NSExtensionItem içindeki attachment'lardan Instagram URL'i çıkarır.
/// Strateji (sırayla):
///   1. public.url   → doğrudan URL nesnesi
///   2. public.plain-text → NSDataDetector ile ilk URL'i bul
///
/// Her iki kanalda da bulunan URL validate() ile Instagram'a özgü
/// path pattern'larına karşı kontrol edilir.

import Foundation
import MobileCoreServices
import UniformTypeIdentifiers

// MARK: - URLExtractor

enum URLExtractor {

    // MARK: Public API

    typealias Completion = (Result<URL, ExtractionError>) -> Void

    /// Asenkron çıkarma — ana thread'den çağırılabilir,
    /// completion her zaman caller'ın thread'inde dönmez; main'e dispatch edin.
    static func extract(from context: NSExtensionContext,
                        completion: @escaping Completion) {
        guard
            let item      = context.inputItems.first as? NSExtensionItem,
            let providers = item.attachments, !providers.isEmpty
        else {
            completion(.failure(.noItems))
            return
        }

        // Strateji 1: public.url
        if let provider = providers.first(where: {
            $0.hasItemConformingToTypeIdentifier(urlUTI)
        }) {
            loadURL(from: provider) { result in
                switch result {
                case .success(let url): completion(validate(url))
                case .failure:
                    // Strateji 2: public.plain-text
                    Self.loadText(providers: providers, completion: completion)
                }
            }
        } else {
            // Strateji 2 doğrudan
            loadText(providers: providers, completion: completion)
        }
    }

    // MARK: Error

    enum ExtractionError: LocalizedError {
        case noItems
        case noCompatibleProvider
        case notSupportedURL(String)
        case loadFailed(Error)

        var errorDescription: String? {
            switch self {
            case .noItems:                  return "Paylaşılacak içerik bulunamadı."
            case .noCompatibleProvider:     return "Desteklenmeyen içerik türü."
            case .notSupportedURL(let u):   return "Desteklenmeyen link:\n\(u)"
            case .loadFailed(let e):        return e.localizedDescription
            }
        }
    }

    // MARK: UTI Helpers (iOS 14+ / öncesi uyumlu)

    private static let urlUTI: String = {
        if #available(iOSApplicationExtension 14.0, *) {
            return UTType.url.identifier
        }
        return kUTTypeURL as String
    }()

    private static let plainTextUTI: String = {
        if #available(iOSApplicationExtension 14.0, *) {
            return UTType.plainText.identifier
        }
        return kUTTypePlainText as String
    }()

    // MARK: - Strateji 1: public.url

    private static func loadURL(from provider: NSItemProvider,
                                completion: @escaping (Result<URL, ExtractionError>) -> Void) {
        provider.loadItem(forTypeIdentifier: urlUTI, options: nil) { item, error in
            if let error = error {
                completion(.failure(.loadFailed(error)))
                return
            }
            // NSItemProvider bazen URL, bazen String döndürür
            if let url = item as? URL {
                completion(.success(url))
            } else if let str = item as? String, let url = URL(string: str.trimmingCharacters(in: .whitespacesAndNewlines)) {
                completion(.success(url))
            } else {
                completion(.failure(.noCompatibleProvider))
            }
        }
    }

    // MARK: - Strateji 2: public.plain-text → NSDataDetector

    private static func loadText(providers: [NSItemProvider],
                                 completion: @escaping Completion) {
        guard let provider = providers.first(where: {
            $0.hasItemConformingToTypeIdentifier(plainTextUTI)
        }) else {
            completion(.failure(.noCompatibleProvider))
            return
        }

        provider.loadItem(forTypeIdentifier: plainTextUTI, options: nil) { item, error in
            if let error = error {
                completion(.failure(.loadFailed(error)))
                return
            }
            guard let text = item as? String else {
                completion(.failure(.noCompatibleProvider))
                return
            }

            // NSDataDetector: Apple'ın kendi URL ayıklayıcısı.
            // Regex'ten daha güvenilir — kısaltılmış linkleri ve
            // "Şuraya bak: https://..." formatını da yakalar.
            guard let url = firstURL(in: text) else {
                completion(.failure(.noCompatibleProvider))
                return
            }
            completion(validate(url))
        }
    }

    // MARK: - URL detection (NSDataDetector)

    private static func firstURL(in text: String) -> URL? {
        guard
            let detector = try? NSDataDetector(
                types: NSTextCheckingResult.CheckingType.link.rawValue
            )
        else { return nil }

        let range = NSRange(text.startIndex..., in: text)
        return detector
            .matches(in: text, options: [], range: range)
            .compactMap(\.url)
            .first
    }

    // MARK: - Validation

    /// Yakalanan URL'in desteklenen bir platforma ait olup olmadığını kontrol eder.
    ///
    /// Desteklenen pattern'lar:
    ///   - instagram.com/reel/   (Reels)
    ///   - instagram.com/p/      (normal post)
    ///   - instagram.com/tv/     (IGTV)
    ///   - instagr.am            (kısaltılmış link)
    ///
    /// Gelecekte TikTok / YouTube Shorts eklemek için bu listeyi genişletin.
    private static let supportedPatterns: [String] = [
        "instagram.com/reel/",
        "instagram.com/p/",
        "instagram.com/tv/",
        "instagr.am",
    ]

    private static func validate(_ url: URL) -> Result<URL, ExtractionError> {
        let lower = url.absoluteString.lowercased()
        let isSupported = supportedPatterns.contains { lower.contains($0) }
        return isSupported
            ? .success(normalised(url))
            : .failure(.notSupportedURL(url.absoluteString))
    }

    /// Tracking parametrelerini (utm_*, igshid vb.) temizler.
    private static func normalised(_ url: URL) -> URL {
        guard var components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        else { return url }

        let blocked = ["utm_source", "utm_medium", "utm_campaign",
                       "utm_content", "utm_term", "igshid", "fbclid"]
        components.queryItems = components.queryItems?.filter {
            !blocked.contains($0.name.lowercased())
        }
        if components.queryItems?.isEmpty == true { components.queryItems = nil }
        return components.url ?? url
    }
}
