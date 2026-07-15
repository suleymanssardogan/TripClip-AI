import CoreData
import OSLog

// MARK: - PersistenceController

// @unchecked Sendable: CoreData's context is accessed on main actor only;
// PersistenceController does not expose mutable state across concurrency domains.
final class PersistenceController: @unchecked Sendable {

    static let shared = PersistenceController()

    let container: NSPersistentContainer

    private init() {
        container = NSPersistentContainer(name: "TripClipAI")
        container.loadPersistentStores { _, error in
            if let error {
                Logger.auth.critical("CoreData load failed: \(error)")
                fatalError("CoreData load failed: \(error)")
            }
        }
        container.viewContext.automaticallyMergesChangesFromParent = true
        // .mergePolicy assigned on main thread at init — safe
        container.viewContext.mergePolicy = NSMergePolicy(merge: .mergeByPropertyObjectTrumpMergePolicyType)
    }

    var context: NSManagedObjectContext { container.viewContext }

    // MARK: - Save

    func save(planDetail: PlanDetail) {
        let request = NSFetchRequest<SavedVideo>(entityName: "SavedVideo")
        request.predicate = NSPredicate(format: "videoId == %d", planDetail.id)

        let record: SavedVideo
        if let existing = try? context.fetch(request).first {
            record = existing
        } else {
            record = SavedVideo(context: context)
            record.videoId  = Int32(planDetail.id)
            record.savedAt  = Date()
        }

        record.filename    = planDetail.filename
        record.status      = planDetail.status
        record.duration    = Int32(planDetail.duration ?? 0)
        record.topLocation = planDetail.locations.first?.name

        if let data = try? JSONEncoder().encode(planDetail) {
            record.aiResultsData = data
        }

        try? context.save()
        Logger.auth.info("CoreData: saved plan \(planDetail.id)")
    }

    // MARK: - Fetch

    func fetchAll() -> [SavedVideo] {
        let request = NSFetchRequest<SavedVideo>(entityName: "SavedVideo")
        request.sortDescriptors = [NSSortDescriptor(key: "savedAt", ascending: false)]
        return (try? context.fetch(request)) ?? []
    }

    func fetch(id: Int) -> SavedVideo? {
        let request = NSFetchRequest<SavedVideo>(entityName: "SavedVideo")
        request.predicate = NSPredicate(format: "videoId == %d", id)
        return try? context.fetch(request).first
    }

    // MARK: - Delete

    func delete(_ record: SavedVideo) {
        context.delete(record)
        try? context.save()
    }

    func deleteAll() {
        let batch = NSBatchDeleteRequest(
            fetchRequest: NSFetchRequest<NSFetchRequestResult>(entityName: "SavedVideo")
        )
        try? context.execute(batch)
        try? context.save()
    }

    // MARK: - Sync from backend after login

    @MainActor
    func syncFromBackend(apiClient: APIClient, userID: Int, token: String) async {
        do {
            let response: PlanListResponse = try await apiClient.send(
                .userVideos(userID: userID), token: token
            )
            for summary in response.plans where summary.isCompleted {
                guard fetch(id: summary.id) == nil else { continue }
                if let detail: PlanDetail = try? await apiClient.send(
                    .videoDetail(videoID: summary.id), token: token
                ) {
                    save(planDetail: detail)
                }
            }
            Logger.auth.info("CoreData: backend sync complete (\(response.plans.count) plans)")
        } catch {
            Logger.auth.warning("CoreData: backend sync failed — \(error.localizedDescription)")
        }
    }
}

// MARK: - SavedVideo Codable helpers

extension SavedVideo {
    var decodedPlanDetail: PlanDetail? {
        guard let data = aiResultsData else { return nil }
        return try? JSONDecoder().decode(PlanDetail.self, from: data)
    }
}
