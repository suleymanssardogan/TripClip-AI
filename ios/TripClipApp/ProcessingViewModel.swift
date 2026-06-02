/// ProcessingViewModel.swift — TripClip
///
/// ── Neden bu dosya var? ──────────────────────────────────────────────────────
///
/// Eski kod `video.createdAt` (sunucudan gelen timestamp) ile `Date()` arasındaki
/// farkı elapsed time olarak gösteriyordu. Video çok önce oluşturulduysa (test
/// sırasında kalan kayıtlar gibi) "7d 10s" hatası çıkıyordu.
///
/// Kurallar:
///   1. Elapsed time → view appear anında başlayan LOCAL timer (createdAt değil)
///   2. Backend'den gelen `stale: true` → hata ekranına geç
///   3. Polling: her 2 saniyede bir; completed/failed/stale → dur
///   4. Maksimum bekleme: 5 dakika → otomatik timeout

import Foundation
import Combine

// MARK: - ProgressStage

enum ProgressStage: Equatable {
    case uploading
    case queued
    case downloading
    case processing(percent: Int)
    case done
    case failed(message: String)
    case timedOut

    var displayTitle: String {
        switch self {
        case .uploading:         return "Yükleniyor"
        case .queued:            return "Kuyrukta Bekliyor"
        case .downloading:       return "Video İndiriliyor"
        case .processing:        return "AI Analiz Ediyor"
        case .done:              return "Analiz Tamamlandı"
        case .failed:            return "Bir Sorun Oluştu"
        case .timedOut:          return "Zaman Aşımı"
        }
    }

    var displaySubtitle: String {
        switch self {
        case .uploading:              return "Sunucuya gönderiliyor…"
        case .queued:                 return "İşlem sırası bekleniyor…"
        case .downloading:            return "Instagram'dan çekiliyor…"
        case .processing(let pct):    return pct > 5 ? "%\(pct) tamamlandı" : "İşleniyor…"
        case .done:                   return "Güzergahınız hazır!"
        case .failed(let msg):        return msg
        case .timedOut:               return "İşlem çok uzun sürdü. Lütfen tekrar deneyin."
        }
    }

    var percent: Int {
        switch self {
        case .uploading:           return 2
        case .queued:              return 8
        case .downloading:         return 15
        case .processing(let p):   return max(15, p)
        case .done:                return 100
        case .failed, .timedOut:   return 0
        }
    }

    var isTerminal: Bool {
        switch self {
        case .done, .failed, .timedOut: return true
        default: return false
        }
    }
}

// MARK: - ProcessingViewModel

@MainActor
final class ProcessingViewModel: ObservableObject {

    // MARK: Published

    @Published private(set) var stage: ProgressStage = .queued
    @Published private(set) var elapsedSeconds: Int  = 0   // LOCAL timer — createdAt DEĞİL

    // MARK: Config

    private let videoID:         Int
    private let apiBaseURL:      String
    private let authToken:       String
    private let pollingInterval: TimeInterval = 2.0
    private let maxWaitSeconds:  TimeInterval = 300  // 5 dk → timeout

    // MARK: Private

    private var pollingTask:   Task<Void, Never>?
    private var elapsedTask:   Task<Void, Never>?

    // ── LOCAL start time — view appear anında atanır ────────────────────────
    // ⚠️ video.createdAt'tan türetilmez; her zaman şimdi'yi başlangıç alır.
    private let startedAt = Date()

    // MARK: Init

    init(videoID: Int, apiBaseURL: String, authToken: String) {
        self.videoID    = videoID
        self.apiBaseURL = apiBaseURL
        self.authToken  = authToken
    }

    // MARK: - Lifecycle

    func startMonitoring() {
        startElapsedTimer()
        startPolling()
    }

    func stopMonitoring() {
        pollingTask?.cancel()
        elapsedTask?.cancel()
    }

    // MARK: - Elapsed Timer (LOCAL)

    private func startElapsedTimer() {
        elapsedTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 1_000_000_000) // 1 sn
                guard !Task.isCancelled else { break }

                let elapsed = Int(Date().timeIntervalSince(self.startedAt))
                self.elapsedSeconds = elapsed

                // Maksimum bekleme aşıldı
                if TimeInterval(elapsed) >= self.maxWaitSeconds {
                    self.stage = .timedOut
                    self.pollingTask?.cancel()
                    break
                }
            }
        }
    }

    // MARK: - Polling

    private func startPolling() {
        pollingTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                await self.fetchProgress()
                if self.stage.isTerminal { break }
                try? await Task.sleep(nanoseconds: UInt64(pollingInterval * 1_000_000_000))
            }
        }
    }

    private func fetchProgress() async {
        guard
            let url = URL(string: "\(apiBaseURL)/api/mobile/videos/\(videoID)/progress")
        else { return }

        var request = URLRequest(url: url)
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 10

        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            let response  = try JSONDecoder().decode(ProgressAPIResponse.self, from: data)
            apply(response: response)
        } catch {
            // Ağ hatası — terminal değil, polling devam eder
            print("[ProcessingVM] Polling error: \(error.localizedDescription)")
        }
    }

    private func apply(response: ProgressAPIResponse) {
        // Backend "stale" bildirdiyse → direkt hata ekranına geç
        if response.stale == true {
            stage = .failed(message: "Video işlenemedi. Lütfen tekrar yükleyin.")
            pollingTask?.cancel()
            elapsedTask?.cancel()
            return
        }

        switch response.stage {
        case "uploading":                stage = .uploading
        case "downloading":              stage = .downloading
        case "queued":                   stage = .queued
        case "processing":               stage = .processing(percent: response.percent)
        case "done", "completed":
            stage = .done
            pollingTask?.cancel()
            elapsedTask?.cancel()
        case "failed":
            stage = .failed(message: "İşlem başarısız. Lütfen tekrar deneyin.")
            pollingTask?.cancel()
            elapsedTask?.cancel()
        default:
            // Bilinmeyen stage — polling sürsün
            stage = .processing(percent: response.percent)
        }
    }
}

// MARK: - API Response DTO

private struct ProgressAPIResponse: Decodable {
    let stage:   String
    let percent: Int
    let stale:   Bool?          // backend 10dk+ takılı videolarda True gönderir
    // elapsed_seconds intentionally IGNORED — local timer kullanıyoruz
}

// MARK: - Elapsed Time Formatter

extension ProcessingViewModel {

    /// "2d 7h" gibi saçma değerler üretmez çünkü startedAt = şimdi.
    /// Max 5 dakika beklenebildiğinden "4m 32s" gibi değerler gösterilir.
    var formattedElapsed: String {
        let s = elapsedSeconds
        if s < 60    { return "\(s)s" }
        if s < 3600  { return "\(s / 60)m \(s % 60)s" }
        return "\(s / 3600)h \((s % 3600) / 60)m"   // pratikte bu case görülmez
    }
}
