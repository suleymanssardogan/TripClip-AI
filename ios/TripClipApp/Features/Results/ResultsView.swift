import SwiftUI

struct ResultsView: View {

    let planID:        Int
    var preloadedPlan: PlanDetail? = nil

    @Environment(AuthEnvironment.self) private var auth
    @State private var vm          = ResultsViewModel()
    @State private var shareItems: [Any] = []
    @State private var showShare   = false

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            if vm.isLoading {
                ProgressView()
                    .tint(AppColors.neon)
            } else if let error = vm.error {
                errorView(error)
            } else if let plan = vm.plan {
                planContent(plan)
            }
        }
        .navigationTitle("Gezi Detayı")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            if let plan = vm.plan {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        Button {
                            let pdf = PDFExportService.generate(plan: plan)
                            shareItems = [pdf]
                            showShare  = true
                        } label: {
                            Label("PDF İndir", systemImage: "doc.fill")
                        }
                        Button {
                            let img = TripShareCard.render(plan: plan)
                            shareItems = [img]
                            showShare  = true
                        } label: {
                            Label("Story Kartı", systemImage: "square.and.arrow.up")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                            .foregroundStyle(AppColors.neon)
                    }
                }
            }
        }
        .sheet(isPresented: $showShare) {
            ShareSheet(items: shareItems)
        }
        .task { await vm.load(planID: planID, auth: auth, preloaded: preloadedPlan) }
    }

    // MARK: - Plan Content

    @ViewBuilder
    private func planContent(_ plan: PlanDetail) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {

                if !plan.locations.isEmpty {
                    TripMapView(locations: plan.locations, route: plan.route)
                        .frame(height: 260)
                        .clipShape(RoundedRectangle(cornerRadius: 20))
                        .padding(.horizontal, 16)
                }

                statsStrip(plan).padding(.horizontal, 16)

                if !plan.locations.isEmpty {
                    sectionHeader("Keşfedilen Mekanlar (\(plan.locations.count))")
                    VStack(spacing: 8) {
                        ForEach(plan.locations) { pin in
                            LocationCard(pin: pin)
                        }
                    }
                    .padding(.horizontal, 16)
                }

                if !plan.travelTips.isEmpty {
                    sectionHeader("Seyahat İpuçları")
                    TravelTipsSection(tips: plan.travelTips)
                        .padding(.horizontal, 16)
                }

                if let transcript = plan.transcription, !transcript.isEmpty {
                    sectionHeader("Video Transkripsiyonu")
                    Text(transcript)
                        .font(.system(size: 13))
                        .foregroundStyle(AppColors.muted)
                        .padding(.horizontal, 16)
                }

                Color.clear.frame(height: 40)
            }
            .padding(.top, 16)
        }
    }

    // MARK: - Helpers

    private func statsStrip(_ plan: PlanDetail) -> some View {
        HStack(spacing: 0) {
            statCell(icon: "mappin.circle.fill", value: "\(plan.locations.count)", label: "Mekan",  color: AppColors.neon)
            Divider().frame(height: 36).background(Color.white.opacity(0.1))
            statCell(icon: "clock.fill",          value: durationString(plan.duration),             label: "Süre",   color: AppColors.violet)
            Divider().frame(height: 36).background(Color.white.opacity(0.1))
            statCell(icon: "cpu.fill",             value: processingString(plan.processingTime),     label: "Analiz", color: AppColors.coral)
        }
        .padding(.vertical, 14)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.white.opacity(0.07), lineWidth: 1))
    }

    private func statCell(icon: String, value: String, label: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon).foregroundStyle(color).font(.system(size: 16))
            Text(value).font(.system(size: 15, weight: .bold)).foregroundStyle(.white)
            Text(label).font(.system(size: 11)).foregroundStyle(AppColors.muted)
        }
        .frame(maxWidth: .infinity)
    }

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(AppColors.muted)
            .textCase(.uppercase)
            .tracking(0.8)
            .padding(.horizontal, 16)
    }

    private func durationString(_ seconds: Int?) -> String {
        guard let s = seconds, s > 0 else { return "—" }
        return s < 60 ? "\(s)s" : "\(s / 60)d \(s % 60)s"
    }

    private func processingString(_ seconds: Double?) -> String {
        guard let s = seconds, s > 0 else { return "—" }
        return String(format: "%.0fs", s)
    }

    private func errorView(_ error: APIError) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundStyle(AppColors.coral)
            Text(error.localizedDescription ?? "Yüklenemedi.")
                .foregroundStyle(AppColors.muted)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tekrar Dene") {
                Task { await vm.load(planID: planID, auth: auth) }
            }
            .foregroundStyle(AppColors.neon)
        }
    }
}

// MARK: - UIActivityViewController wrapper

private struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}
