/// ProcessingViewModel.swift — TripClip
///
/// Rules:
///   1. Elapsed time → LOCAL timer starting at view appear (not createdAt)
///   2. Backend `stale: true` → transition to error state
///   3. Polling every 2 seconds; terminal stages stop the poll loop
///   4. Maximum wait 5 minutes → timeout

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
        case .uploading:   return "Yükleniyor"
        case .queued:      return "Kuyrukta Bekliyor"
        case .downloading: return "Video İndiriliyor"
        case .processing:  return "AI Analiz Ediyor"
        case .done:        return "Analiz Tamamlandı"
        case .failed:      return "Bir Sorun Oluştu"
        case .timedOut:    return "Zaman Aşımı"
        }
    }

    var displaySubtitle: String {
        switch self {
        case .uploading:           return "Sunucuya gönderiliyor…"
        case .queued:              return "İşlem sırası bekleniyor…"
        case .downloading:         return "Instagram'dan çekiliyor…"
        case .processing(let pct): return pct > 5 ? "%\(pct) tamamlandı" : "İşleniyor…"
        case .done:                return "Güzergahınız hazır!"
        case .failed(let msg):     return msg
        case .timedOut:            return "İşlem çok uzun sürdü. Lütfen tekrar deneyin."
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

    @Published private(set) var stage:          ProgressStage = .queued
    @Published private(set) var elapsedSeconds: Int           = 0

    private let videoID:         Int
    private let apiClient:       APIClientProtocol
    private let token:           String
    private let pollingInterval: TimeInterval = 2.0
    private let maxWaitSeconds:  TimeInterval = 300

    private var pollingTask: Task<Void, Never>?
    private var elapsedTask: Task<Void, Never>?
    // retry() sonrası yeni bir 5dk sabır penceresi için resetlenebilmeli — bu yüzden var.
    private var startedAt = Date()

    init(videoID: Int, apiClient: APIClientProtocol, token: String) {
        self.videoID   = videoID
        self.apiClient = apiClient
        self.token     = token
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

    /// Yalnızca `.timedOut` durumunda anlamlıdır — istemci 5dk'lık sabır süresini
    /// aştı ama sunucudaki iş hâlâ sürüyor olabilir (bkz. `.failed` ise burası
    /// çağrılmaz, çünkü sunucu zaten kalıcı olarak vazgeçmiştir). Eskiden bu
    /// ekranda hiçbir aksiyon yoktu — kullanıcı çıkmaz sokakta kalıyordu.
    func retryAfterTimeout() {
        guard stage == .timedOut else { return }
        stage = .queued
        startedAt = Date()
        elapsedSeconds = 0
        startMonitoring()
    }

    // MARK: - Elapsed Timer (LOCAL — not from server timestamp)

    private func startElapsedTimer() {
        elapsedTask = Task { [weak self] in
            guard let self else { return }
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                guard !Task.isCancelled else { break }

                let elapsed = Int(Date().timeIntervalSince(self.startedAt))
                self.elapsedSeconds = elapsed

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
        do {
            let response: ProgressAPIResponse = try await apiClient.send(
                .videoProgress(videoID: videoID),
                token: token
            )
            apply(response: response)
        } catch {
            // Network error — not terminal, polling continues
        }
    }

    private func apply(response: ProgressAPIResponse) {
        if response.stale == true {
            stage = .failed(message: "Video işlenemedi. Lütfen tekrar yükleyin.")
            pollingTask?.cancel()
            elapsedTask?.cancel()
            return
        }

        switch response.stage {
        case "uploading":             stage = .uploading
        case "downloading":           stage = .downloading
        case "queued":                stage = .queued
        case "processing":            stage = .processing(percent: response.percent)
        case "done", "completed":
            stage = .done
            pollingTask?.cancel()
            elapsedTask?.cancel()
        case "failed":
            stage = .failed(message: "İşlem başarısız. Lütfen tekrar deneyin.")
            pollingTask?.cancel()
            elapsedTask?.cancel()
        default:
            stage = .processing(percent: response.percent)
        }
    }

    var formattedElapsed: String {
        let s = elapsedSeconds
        if s < 60   { return "\(s)s" }
        if s < 3600 { return "\(s / 60)m \(s % 60)s" }
        return "\(s / 3600)h \((s % 3600) / 60)m"
    }
}

// MARK: - Response DTO

private struct ProgressAPIResponse: Decodable {
    let stage:   String
    let percent: Int
    let stale:   Bool?
}
