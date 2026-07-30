import SwiftUI

struct ResultsView: View {

    let planID:        Int
    var preloadedPlan: PlanDetail? = nil

    @Environment(AuthEnvironment.self) private var auth
    @State private var vm          = ResultsViewModel()
    @State private var sharePayload: SharePayload?
    @State private var exportFailed = false
    /// Mekan kartına basıldığında haritanın odaklanacağı pin.
    @State private var focusedPin: LocationPin?

    /// Karta basınca haritaya geri kaydırmak için ScrollView çapası.
    private static let mapAnchor = "trip-map"

    /// `.sheet(item:)` kullanabilmek için Identifiable sarmalayıcı.
    ///
    /// `.sheet(isPresented:)` ile içerik closure'ı, state güncellemesi yayılmadan
    /// önce değerlendiriliyor ve ilk açılışta paylaşım sayfası HENÜZ BOŞ olan
    /// diziyi alıyordu — sayfa açılıyor ama içi boş görünüyordu. `.sheet(item:)`
    /// içeriği tetikleyen değerden kurduğu için bu yarış ortadan kalkıyor.
    private struct SharePayload: Identifiable {
        let id = UUID()
        let url: URL
    }

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            if vm.isLoading {
                ProgressView()
                    .tint(AppColors.accentText)
            } else if let error = vm.error {
                errorView(error)
            } else if let plan = vm.plan {
                planContent(plan)
            }
        }
        .navigationTitle("Gezi Detayı")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if let plan = vm.plan {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        Button {
                            share(PDFExportService.exportToFile(plan: plan, title: plan.displayTitle))
                        } label: {
                            Label("PDF İndir", systemImage: "doc.fill")
                        }
                        Button {
                            share(TripShareCard.exportToFile(plan: plan, title: plan.displayTitle))
                        } label: {
                            Label("Story Kartı", systemImage: "square.and.arrow.up")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                            .foregroundStyle(AppColors.accentText)
                    }
                }
            }
        }
        .sheet(item: $sharePayload) { payload in
            ShareSheet(items: [payload.url])
        }
        .alert("Dosya oluşturulamadı", isPresented: $exportFailed) {
            Button("Tamam", role: .cancel) { }
        } message: {
            Text("Paylaşım dosyası hazırlanamadı. Lütfen tekrar deneyin.")
        }
        .task { await vm.load(planID: planID, auth: auth, preloaded: preloadedPlan) }
        .onDisappear { vm.stopTipsPolling() }
    }

    /// Dışa aktarım başarısızsa sessizce boş bir paylaşım sayfası açmak yerine
    /// kullanıcıya söyle.
    private func share(_ url: URL?) {
        guard let url else {
            exportFailed = true
            return
        }
        sharePayload = SharePayload(url: url)
    }

    // MARK: - Plan Content

    @ViewBuilder
    private func planContent(_ plan: PlanDetail) -> some View {
        ScrollViewReader { proxy in
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {

                if !plan.locations.isEmpty {
                    TripMapView(locations: plan.locations,
                                route: plan.route,
                                focusedPin: focusedPin)
                        .frame(height: 260)
                        .clipShape(RoundedRectangle(cornerRadius: 20))
                        .padding(.horizontal, 16)
                        .id(Self.mapAnchor)
                }

                statsStrip(plan).padding(.horizontal, 16)

                if !plan.locations.isEmpty {
                    sectionHeader("Keşfedilen Mekanlar (\(plan.locations.count))")
                    VStack(spacing: 8) {
                        ForEach(plan.locations) { pin in
                            // Karta basınca haritayı o mekana odakla ve yukarı
                            // kaydır — aşağıdaki bir karta basıldığında harita
                            // ekran dışında kalırsa hiçbir şey olmamış görünüyor.
                            Button {
                                focusedPin = pin
                                withAnimation {
                                    proxy.scrollTo(Self.mapAnchor, anchor: .top)
                                }
                            } label: {
                                LocationCard(pin: pin)
                            }
                            .buttonStyle(PressableButtonStyle())
                        }
                    }
                    .padding(.horizontal, 16)
                }

                if !plan.travelTips.isEmpty {
                    sectionHeader("Seyahat İpuçları")
                    TravelTipsSection(tips: plan.travelTips)
                        .padding(.horizontal, 16)
                } else if vm.isWaitingForTips {
                    // İpuçları analizden sonra ayrı task'ta üretiliyor; bölümü
                    // sessizce gizlemek yerine hazırlandığını söylüyoruz.
                    sectionHeader("Seyahat İpuçları")
                    tipsPlaceholder
                } else if vm.tipsUnavailable {
                    sectionHeader("Seyahat İpuçları")
                    tipsFailedNotice
                }

                if let transcript = plan.transcription, !transcript.isEmpty {
                    sectionHeader("Video Transkripsiyonu")
                    Text(transcript)
                        .font(.system(size: 13))
                        .foregroundStyle(AppColors.textSecondary)
                        .padding(.horizontal, 16)
                }

                Color.clear.frame(height: 40)
            }
            .padding(.top, 16)
        }
        }
    }

    // MARK: - Ertelenmiş İpuçları Durumları

    private var tipsPlaceholder: some View {
        HStack(spacing: 10) {
            ProgressView()
                .controlSize(.small)
                .tint(AppColors.accentText)
            Text("İpuçları hazırlanıyor…")
                .font(.system(size: 14))
                .foregroundStyle(AppColors.textSecondary)
            Spacer()
        }
        .padding(14)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppColors.border, lineWidth: 1))
        .padding(.horizontal, 16)
    }

    private var tipsFailedNotice: some View {
        HStack(spacing: 10) {
            Image(systemName: "lightbulb.slash")
                .font(.system(size: 15))
                .foregroundStyle(AppColors.textTertiary)
            Text("İpuçları şu anda alınamadı. Daha sonra tekrar bakabilirsin.")
                .font(.system(size: 13))
                .foregroundStyle(AppColors.textSecondary)
            Spacer()
        }
        .padding(14)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppColors.border, lineWidth: 1))
        .padding(.horizontal, 16)
    }

    // MARK: - Helpers

    private func statsStrip(_ plan: PlanDetail) -> some View {
        HStack(spacing: 0) {
            statCell(icon: "mappin.circle.fill", value: "\(plan.locations.count)", label: "Mekan")
            Divider().frame(height: 36).background(AppColors.border)
            statCell(icon: "clock.fill",          value: durationString(plan.duration),             label: "Süre")
            Divider().frame(height: 36).background(AppColors.border)
            statCell(icon: "cpu.fill",             value: processingString(plan.processingTime),     label: "Analiz")
        }
        .padding(.vertical, 14)
        .background(AppColors.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(AppColors.border, lineWidth: 1))
    }

    private func statCell(icon: String, value: String, label: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon).foregroundStyle(AppColors.textTertiary).font(.system(size: 16))
            Text(value).font(.system(size: 15, weight: .bold)).foregroundStyle(AppColors.text)
            Text(label).font(.system(size: 11)).foregroundStyle(AppColors.textSecondary)
        }
        .frame(maxWidth: .infinity)
    }

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(AppColors.textSecondary)
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
                .foregroundStyle(AppColors.destructive)
            Text(error.localizedDescription ?? "Yüklenemedi.")
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tekrar Dene") {
                Task { await vm.load(planID: planID, auth: auth) }
            }
            .foregroundStyle(AppColors.accentText)
        }
    }
}

// MARK: - UIActivityViewController wrapper

private struct ShareSheet: UIViewControllerRepresentable {
    let items: [URL]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}
