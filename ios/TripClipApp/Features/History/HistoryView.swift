import SwiftUI
import CoreData

struct HistoryView: View {

    @FetchRequest(
        entity: SavedVideo.entity(),
        sortDescriptors: [NSSortDescriptor(keyPath: \SavedVideo.savedAt, ascending: false)]
    ) private var saved: FetchedResults<SavedVideo>

    @Environment(\.managedObjectContext) private var context
    @Environment(AuthEnvironment.self)   private var auth

    @State private var selectedPlan: PlanDetail?
    @State private var showPlan      = false

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            if saved.isEmpty {
                emptyState
            } else {
                list
            }
        }
        .navigationTitle("Geçmiş Geziler")
        .navigationBarTitleDisplayMode(.inline)
        .navigationDestination(isPresented: $showPlan) {
            if let plan = selectedPlan {
                ResultsView(planID: plan.id, preloadedPlan: plan)
            }
        }
    }

    private var list: some View {
        ScrollView {
            LazyVStack(spacing: 10) {
                ForEach(saved, id: \.videoId) { record in
                    Button {
                        if let plan = record.decodedPlanDetail {
                            selectedPlan = plan
                            showPlan     = true
                        }
                    } label: {
                        HistoryRowView(record: record)
                    }
                    .buttonStyle(.plain)
                    .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                        Button(role: .destructive) {
                            PersistenceController.shared.delete(record)
                        } label: {
                            Label("Sil", systemImage: "trash")
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "clock.arrow.trianglehead.counterclockwise.rotate.90")
                .font(.system(size: 52))
                .foregroundStyle(AppColors.textTertiary)
            Text("Henüz kaydedilmiş gezi yok")
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(AppColors.text)
            Text("Tamamlanan geziler otomatik olarak\nburada saklanır.")
                .font(.system(size: 14))
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
        }
    }
}

// MARK: - History Row

private struct HistoryRowView: View {

    let record: SavedVideo

    private var title: String {
        if let loc = record.topLocation, !loc.isEmpty {
            return loc.prefix(1).uppercased() + loc.dropFirst() + " Gezisi"
        }
        return record.filename ?? "Gezi #\(record.videoId)"
    }

    private var savedDate: String {
        guard let d = record.savedAt else { return "" }
        return d.formatted(.dateTime.day().month(.wide).year())
    }

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 14)
                    .fill(AppColors.route.opacity(0.1))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppColors.route.opacity(0.2)))
                Image(systemName: "mappin.circle.fill")
                    .font(.system(size: 22))
                    .foregroundStyle(AppColors.route)
            }
            .frame(width: 50, height: 50)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(AppColors.text)
                    .lineLimit(1)
                if !savedDate.isEmpty {
                    Text(savedDate)
                        .font(.system(size: 12))
                        .foregroundStyle(AppColors.textSecondary)
                }
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(AppColors.textTertiary)
        }
        .padding(14)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay(
            RoundedRectangle(cornerRadius: 18)
                .stroke(AppColors.border, lineWidth: 1)
        )
    }
}
