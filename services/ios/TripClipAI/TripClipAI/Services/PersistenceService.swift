import CoreData
import Foundation

class PersistenceService {
    static let shared = PersistenceService()

    let container: NSPersistentContainer

    init() {
        container = NSPersistentContainer(name: "TripClipAI")
        container.loadPersistentStores { _, error in
            if let error { fatalError("CoreData load failed: \(error)") }
        }
        container.viewContext.automaticallyMergesChangesFromParent = true
    }

    var context: NSManagedObjectContext { container.viewContext }

    // MARK: - Save

    func saveVideoResult(_ video: VideoResponse) {
        let fetch = NSFetchRequest<SavedVideo>(entityName: "SavedVideo")
        fetch.predicate = NSPredicate(format: "videoId == %d", video.id)

        let saved: SavedVideo
        if let existing = try? context.fetch(fetch).first {
            saved = existing
        } else {
            saved = SavedVideo(context: context)
            saved.videoId = Int32(video.id)
            saved.savedAt = Date()
        }

        saved.filename = video.filename
        saved.status = video.status
        saved.duration = Int32(video.duration ?? 0)

        // Tam VideoResponse'u kaydet (enrichedLocations dahil)
        if let data = try? JSONEncoder().encode(video) {
            saved.aiResultsData = data
        }

        try? context.save()
    }

    // MARK: - Fetch

    func fetchAll() -> [SavedVideo] {
        let fetch = NSFetchRequest<SavedVideo>(entityName: "SavedVideo")
        fetch.sortDescriptors = [NSSortDescriptor(key: "savedAt", ascending: false)]
        return (try? context.fetch(fetch)) ?? []
    }

    func fetchVideo(id: Int) -> SavedVideo? {
        let fetch = NSFetchRequest<SavedVideo>(entityName: "SavedVideo")
        fetch.predicate = NSPredicate(format: "videoId == %d", id)
        return try? context.fetch(fetch).first
    }

    // MARK: - Delete

    func delete(_ video: SavedVideo) {
        context.delete(video)
        try? context.save()
    }

    /// Backend'den kullanıcının video listesini alıp eksik olanları CoreData'ya çek.
    /// Login sonrası HistoryView senkronizasyonu için.
    @MainActor
    func syncFromBackend() async {
        do {
            let summaries = try await APIService.shared.getMyVideos()
            for summary in summaries where summary.status.lowercased() == "completed" {
                // Zaten cache'te varsa atla
                if fetchVideo(id: summary.id) != nil { continue }
                // Yoksa detayını çek ve kaydet
                if let detail = try? await APIService.shared.getVideoStatus(id: summary.id) {
                    saveVideoResult(detail)
                }
            }
        } catch {
            // Sessizce yut — offline ise mevcut cache'i göster
            print("⚠️ syncFromBackend hata: \(error.localizedDescription)")
        }
    }

    /// Tüm yerel kayıtları siler — yalnızca kullanıcı DEĞİŞTİĞİNDE çağrılır.
    /// Logout'ta çağrılmaz; aynı kullanıcı tekrar girince geçmişi görür.
    func clearAll() {
        let fetch: NSFetchRequest<NSFetchRequestResult> = NSFetchRequest(entityName: "SavedVideo")
        let batch = NSBatchDeleteRequest(fetchRequest: fetch)
        do {
            try context.execute(batch)
            try context.save()
        } catch {
            // Batch delete'in alt sürüm desteği yoksa fallback: tek tek sil
            let videos = (try? context.fetch(NSFetchRequest<SavedVideo>(entityName: "SavedVideo"))) ?? []
            videos.forEach { context.delete($0) }
            try? context.save()
        }

        // Kayıtlı plan başlıkları (UserDefaults'ta) — onları da sil
        let prefix = "tripplan_"
        for key in UserDefaults.standard.dictionaryRepresentation().keys
                where key.hasPrefix(prefix) {
            UserDefaults.standard.removeObject(forKey: key)
        }
    }
}

// MARK: - Codable helpers on SavedVideo

extension SavedVideo {
    /// Tam VideoResponse (yeni format — enrichedLocations dahil)
    var decodedVideoResponse: VideoResponse? {
        guard let data = aiResultsData else { return nil }
        return try? JSONDecoder().decode(VideoResponse.self, from: data)
    }

    /// Geriye dönük uyumluluk — eski kayıtlar için
    var decodedAIResults: AIResults? {
        guard let data = aiResultsData else { return nil }
        return try? JSONDecoder().decode(AIResults.self, from: data)
    }
}
