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

        if let results = video.aiResults,
           let data = try? JSONEncoder().encode(results) {
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
}

// MARK: - AIResults Codable helper on SavedVideo

extension SavedVideo {
    var decodedAIResults: AIResults? {
        guard let data = aiResultsData else { return nil }
        return try? JSONDecoder().decode(AIResults.self, from: data)
    }
}
