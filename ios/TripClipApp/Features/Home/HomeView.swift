import SwiftUI
import PhotosUI

struct HomeView: View {

    @Environment(AuthEnvironment.self) private var auth
    @State private var vm           = HomeViewModel()
    // NavigationPath değil tipli dizi: analiz bitince yığının tepesindeki
    // "işleniyor" kaydını tamamlanmış planla YERİNDE değiştirebilmek için
    // elemanlara erişmemiz gerekiyor (NavigationPath tip silinmiş olduğundan
    // buna izin vermiyor). Bkz. `showResults(for:)`.
    @State private var navPath: [PlanSummary] = []

    // Camera roll upload state
    @State private var pickerItem:   PhotosPickerItem?
    @State private var uploadState:  UploadState     = .idle
    @State private var uploadPct:    Double          = 0

    /// Silme onayı bekleyen plan. Silme geri alınamıyor, o yüzden tek dokunuşla
    /// değil onaydan sonra gidiyor.
    @State private var planPendingDeletion: PlanSummary?

    /// Çıkış onayı bekleniyor mu — plan silme/undo geri alma ile AYNI desen
    /// (M34 audit bulgusu: çıkış tek dokunuşla ANINDA gerçekleşiyordu, bu
    /// ekrandaki diğer geri-alınamaz işlemlerle tutarsızdı).
    @State private var showLogoutConfirmation = false
    @State private var showDeleteAccountConfirmation = false
    @State private var accountDeleteError: String?
    @State private var showAIConsent = false

    private enum UploadState {
        case idle
        case loading         // loading from Photos library
        case uploading       // sending to server
        case done(videoID: Int)
        case failed(String)

        var isActive: Bool {
            switch self {
            case .loading, .uploading: return true
            default: return false
            }
        }
    }

    var body: some View {
        NavigationStack(path: $navPath) {
            ZStack {
                AppColors.background.ignoresSafeArea()

                VStack(spacing: 0) {
                    header
                        .padding(.horizontal, 20)
                        .padding(.top, 16)
                        .padding(.bottom, 22)

                    // Upload progress overlay when active
                    if case .loading = uploadState {
                        uploadProgressView(label: "Video hazırlanıyor…", percent: 0)
                    } else if case .uploading = uploadState {
                        uploadProgressView(label: "Sunucuya yükleniyor…", percent: uploadPct)
                    } else if case .failed(let msg) = uploadState {
                        uploadErrorBanner(msg)
                    } else if vm.isLoading && vm.plans.isEmpty {
                        Spacer()
                        ProgressView().tint(AppColors.accentText)
                            .accessibilityLabel("Yükleniyor")
                        Spacer()
                    } else if let error = vm.error, vm.plans.isEmpty {
                        errorState(error)
                    } else if vm.plans.isEmpty {
                        emptyState
                    } else {
                        planList
                    }
                }
            }
            .navigationTitle("TripClip")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItemGroup(placement: .topBarTrailing) {
                    NavigationLink(destination: HistoryView()) {
                        Image(systemName: "clock.arrow.circlepath")
                    }
                    .accessibilityLabel("Geçmiş")

                    Menu {
                        NavigationLink(destination: PrivacySettingsView()) {
                            Label("Gizlilik ve veri paylaşımı", systemImage: "hand.raised")
                        }
                        Button {
                            (UIApplication.shared.delegate as? AppDelegate)?.requestNotificationPermission()
                        } label: {
                            Label("Bildirimleri aç", systemImage: "bell")
                        }
                        Button { showLogoutConfirmation = true } label: {
                            Label("Çıkış Yap", systemImage: "rectangle.portrait.and.arrow.right")
                        }
                        Button(role: .destructive) { showDeleteAccountConfirmation = true } label: {
                            Label("Hesabı Sil", systemImage: "trash")
                        }
                    } label: {
                        Image(systemName: "person.crop.circle")
                    }
                    .accessibilityLabel("Hesap menüsü")
                }
            }
            .navigationDestination(for: PlanSummary.self) { plan in
                if plan.isCompleted {
                    ResultsView(planID: plan.id)
                } else {
                    ProcessingView(
                        videoID:   plan.id,
                        apiClient: auth.apiClient,
                        token:     auth.user?.token ?? ""
                    ) { completedID in
                        Task { await showResults(for: completedID) }
                    }
                }
            }
        }
        .task { await vm.load(auth: auth) }
        // Detaydan köke dönüldüğünde listeyi tazele: kullanıcı orada durak
        // silmiş/sıralamış olabilir ve kart eski sayıyı ("12 mekan") göstermeye
        // devam ediyordu.
        .onChange(of: navPath.count) { old, new in
            guard new == 0, old > 0 else { return }
            Task { await vm.load(auth: auth) }
        }
        .confirmationDialog(
            "Bu planı silmek istiyor musun?",
            isPresented: Binding(
                get: { planPendingDeletion != nil },
                set: { if !$0 { planPendingDeletion = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button("Sil", role: .destructive) {
                guard let plan = planPendingDeletion else { return }
                planPendingDeletion = nil
                Task { await vm.deletePlan(plan, auth: auth) }
            }
            Button("Vazgeç", role: .cancel) { planPendingDeletion = nil }
        } message: {
            Text("Plan ve yüklenen video kalıcı olarak silinir. Bu işlem geri alınamaz.")
        }
        .confirmationDialog(
            "Hesabını silmek istiyor musun?",
            isPresented: $showDeleteAccountConfirmation,
            titleVisibility: .visible
        ) {
            Button("Hesabı Kalıcı Olarak Sil", role: .destructive) {
                Task {
                    do { try await auth.deleteAccount() }
                    catch { accountDeleteError = error.localizedDescription }
                }
            }
            Button("Vazgeç", role: .cancel) {}
        } message: {
            Text("Tüm videoların, planların ve gezilerin kalıcı olarak silinir. Bu işlem geri alınamaz. Apple ile giriş yaptıysan bağlantını ayrıca iPhone Ayarlar > adın > Apple ile Giriş bölümünden kaldırabilirsin.")
        }
        .alert("Hesap silinemedi", isPresented: Binding(
            get: { accountDeleteError != nil },
            set: { if !$0 { accountDeleteError = nil } }
        )) {
            Button("Tamam", role: .cancel) { accountDeleteError = nil }
        } message: {
            Text(accountDeleteError ?? "Lütfen tekrar deneyin.")
        }
        .confirmationDialog(
            "Çıkış yapmak istiyor musun?",
            isPresented: $showLogoutConfirmation,
            titleVisibility: .visible
        ) {
            Button("Çıkış Yap", role: .destructive) { auth.logout() }
            Button("Vazgeç", role: .cancel) {}
        }
        // `TripDetailViewModel.stopEditError`/`ItineraryHistoryView`'in kendi
        // silme hatası alert'iyle AYNI desen — bir silme başarısız olduğunda
        // liste TAM EKRAN bir hatayla DEĞİL, yerinde kalıp bir alert gösterir
        // (M36 audit bulgusu — bkz. HomeViewModel.deleteError'ın doc yorumu).
        .alert(
            "Silinemedi",
            isPresented: Binding(
                get: { vm.deleteError != nil },
                set: { if !$0 { vm.deleteError = nil } }
            )
        ) {
            Button("Tamam", role: .cancel) { vm.deleteError = nil }
        } message: {
            Text(vm.deleteError ?? "")
        }
        .sheet(isPresented: $showAIConsent, onDismiss: {
            if !AIConsentStore.hasConsent(userID: auth.user?.id ?? 0) { pickerItem = nil }
        }) {
            AIConsentView(userID: auth.user?.id ?? 0, onGranted: {
                showAIConsent = false
                if let item = pickerItem { Task { await handlePickedItem(item) } }
            }, onDeclined: { showAIConsent = false; pickerItem = nil })
        }
        .onChange(of: pickerItem) { _, item in
            guard let item else { return }
            Task { await handlePickedItem(item) }
        }
        .onReceive(
            NotificationCenter.default.publisher(for: .tripClipNavigateToVideo)
        ) { note in
            if let videoID = note.object as? Int {
                let stub = PlanSummary(
                    id: videoID, filename: "", status: "processing",
                    duration: nil, createdAt: nil,
                    locationsCount: 0, topLocation: nil, processingTime: nil
                )
                navPath.append(stub)
            }
        }
    }

    // MARK: - Navigation

    /// Analiz bittiğinde çağrılır: listeyi tazeler ve navigasyon yığınının
    /// tepesindeki "işleniyor" kaydını tamamlanmış planla değiştirir.
    ///
    /// Push/pop yerine yerinde değiştirme yapıyoruz — `navigationDestination`
    /// zaten `plan.isCompleted` üzerinden dallandığı için aynı yığın seviyesi
    /// ProcessingView'dan ResultsView'a geçer. Böylece geri tuşu doğrudan
    /// listeye döner, kullanıcı bitmiş bir işleme ekranına düşmez.
    private func showResults(for videoID: Int) async {
        // Başarı ekranı bir an görünsün, ani geçiş olmasın.
        try? await Task.sleep(for: .seconds(1))

        await vm.load(auth: auth)

        guard
            let completed = vm.plans.first(where: { $0.id == videoID }),
            completed.isCompleted,
            let index = navPath.lastIndex(where: { $0.id == videoID })
        else { return }

        navPath[index] = completed
    }

    // MARK: - Upload Flow

    private func handlePickedItem(_ item: PhotosPickerItem) async {
        guard AIConsentStore.hasConsent(userID: auth.user?.id ?? 0) else {
            showAIConsent = true
            return
        }
        uploadState = .loading
        uploadPct   = 0

        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                uploadState = .failed("Video yüklenemedi.")
                return
            }

            guard data.count <= 100 * 1024 * 1024 else {
                uploadState = .failed("Video 100 MB sınırını aşıyor. Daha kısa bir video seç.")
                pickerItem = nil
                return
            }
            uploadState = .uploading
            let filename = "\(UUID().uuidString).mp4"

            // Yükleme APIClient.send'in 401-yenile-tekrarla yolundan geçmiyor;
            // 16MB'ı boşa göndermemek için token'ı önden tazele.
            guard let token = await auth.validAccessToken() else {
                uploadState = .failed("Oturum süresi doldu. Lütfen tekrar giriş yapın.")
                pickerItem  = nil
                return
            }

            let result = try await auth.apiClient.uploadVideoFile(
                data: data,
                filename: filename,
                token: token
            ) { pct in
                Task { @MainActor in uploadPct = pct }
            }

            uploadState = .idle
            pickerItem  = nil

            let stub = PlanSummary(
                id: result.id, filename: filename, status: "processing",
                duration: nil, createdAt: nil,
                locationsCount: 0, topLocation: nil, processingTime: nil
            )
            navPath.append(stub)
            await vm.load(auth: auth)

        } catch let apiError as APIError where apiError.isUnauthorized {
            // Yükleme başlamadan ÖNCE token tazelenir (yukarıdaki
            // `validAccessToken()`), ama `uploadVideoFile` `APIClient.send`'in
            // 401-yenile-tekrarla sarmalayıcısından GEÇMEDİĞİ için, oturum
            // yükleme SIRASINDA (600sn'ye kadar sürebilir) sona ererse bunu
            // KENDİSİ hiç ele almıyordu — diğer TÜM authenticated çağrıların
            // aksine (M37 audit bulgusu). Kullanıcı "logged in" GÖRÜNMEYE
            // devam edip, bir sonraki AYRI eylemi 401 alana kadar farkına
            // varmıyordu.
            auth.handleUnauthorized()
            pickerItem = nil
        } catch {
            uploadState = .failed(error.localizedDescription)
            pickerItem  = nil
        }
    }

    // MARK: - Subviews

    private var header: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 6) {
                if let email = auth.user?.email, !email.isEmpty {
                    Text("Merhaba, \(email.components(separatedBy: "@").first ?? email)")
                        .font(.subheadline)
                        .foregroundStyle(AppColors.textSecondary)
                }
                Text("Bir video, yeni bir rota.")
                    .font(.system(.title2, design: .rounded, weight: .bold))
                    .foregroundStyle(AppColors.text)
            }

            VStack(alignment: .leading, spacing: 15) {
                Text("Beğendiğin videodaki yerleri keşfet")
                    .font(.headline)
                    .foregroundStyle(AppColors.text)
                Text("Gezi videosunu yükle; durakları bulup senin için düzenleyelim.")
                    .font(.subheadline)
                    .foregroundStyle(AppColors.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)

                PhotosPicker(selection: $pickerItem, matching: .videos, photoLibrary: .shared()) {
                    Label("Video seç", systemImage: "plus")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .tint(AppColors.accent)
                .disabled(uploadState.isActive)
                .accessibilityLabel("Gezi videosu yükle")
            }
            .padding(20)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(AppColors.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(AppColors.border))
        }
    }

    private func uploadProgressView(label: String, percent: Double) -> some View {
        VStack(spacing: 20) {
            Spacer()
            ZStack {
                Circle()
                    .stroke(AppColors.surface2, lineWidth: 5)
                    .frame(width: 80, height: 80)
                Circle()
                    .trim(from: 0, to: percent)
                    .stroke(AppColors.accent, style: StrokeStyle(lineWidth: 5, lineCap: .round))
                    .frame(width: 80, height: 80)
                    .rotationEffect(.degrees(-90))
                    .animation(.easeInOut(duration: 0.3), value: percent)
                Image(systemName: "icloud.and.arrow.up")
                    .font(.title2)
                    .foregroundStyle(AppColors.accentText)
            }
            // Daha önce yüzde HİÇBİR YERDE gösterilmiyordu — ne görsel
            // olarak (yalnızca dairenin dolma animasyonu) ne de VoiceOver'a
            // (M36 audit bulgusu). `accessibilityValue`, bu projede daha
            // önce hiç kullanılmamış olsa da tam olarak bu senaryo için var:
            // "ne kadar tamamlandı" bilgisini içeriğin KENDİSİNDEN ayrı
            // taşır.
            Text("%\(Int((percent * 100).rounded()))")
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundStyle(AppColors.accentText)
            Text(label)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(AppColors.text)
            Text("Sayfayı kapatmayın")
                .font(.caption)
                .foregroundStyle(AppColors.textSecondary)
            Spacer()
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(label)
        .accessibilityValue("Yüzde \(Int((percent * 100).rounded()))")
    }

    private func uploadErrorBanner(_ message: String) -> some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 40))
                .foregroundStyle(AppColors.destructive)
            Text(message)
                .font(.system(size: 15))
                .foregroundStyle(AppColors.text)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tamam") { uploadState = .idle }
                .foregroundStyle(AppColors.accentText)
            Spacer()
        }
    }

    private var planList: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Planların")
                        .font(.system(size: 21, weight: .bold, design: .rounded))
                        .foregroundStyle(AppColors.text)
                    Spacer()
                    Text("\(vm.plans.count) gezi")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(AppColors.textSecondary)
                }
                .padding(.bottom, 3)
                ForEach(vm.plans) { plan in
                    Button {
                        navPath.append(plan)
                    } label: {
                        PlanRowView(plan: plan)
                    }
                    .buttonStyle(PressableButtonStyle())
                    // Liste `List` değil `LazyVStack` (özel kart tasarımı için),
                    // dolayısıyla `.swipeActions` kullanılamıyor — uzun basma
                    // menüsü aynı işi tasarımı bozmadan yapıyor.
                    .contextMenu {
                        Button(role: .destructive) {
                            planPendingDeletion = plan
                        } label: {
                            Label("Planı Sil", systemImage: "trash")
                        }
                    }
                }
                if let error = vm.error {
                    Text(error.localizedDescription ?? "Yükleme başarısız.")
                        .font(.footnote).foregroundStyle(AppColors.destructive)
                }
                if vm.hasMore {
                    Button(vm.isLoading ? "Yükleniyor…" : "Daha fazla yükle") {
                        Task { await vm.loadMore(auth: auth) }
                    }
                    .disabled(vm.isLoading)
                    .padding(.vertical, 12)
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 24)
        }
        .refreshable { await vm.load(auth: auth) }
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Spacer()
            Text("İlk rotan burada başlayacak")
                .font(.system(size: 21, weight: .bold, design: .rounded))
                .foregroundStyle(AppColors.text)
            Text("Beğendiğin bir gezi videosunu paylaş veya yukarıdan yükle. Durakları senin için bulalım.")
                .font(.system(size: 15))
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
            Spacer()
        }
        .padding(.horizontal, 38)
    }

    private func errorState(_ error: APIError) -> some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 48))
                .foregroundStyle(AppColors.destructive)
            Text(error.localizedDescription ?? "Bir hata oluştu.")
                .font(.system(size: 15))
                .foregroundStyle(AppColors.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tekrar Dene") { Task { await vm.load(auth: auth) } }
                .foregroundStyle(AppColors.accentText)
            Spacer()
        }
    }
}
