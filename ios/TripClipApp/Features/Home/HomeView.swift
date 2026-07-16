import SwiftUI
import PhotosUI

struct HomeView: View {

    @Environment(AuthEnvironment.self) private var auth
    @State private var vm           = HomeViewModel()
    @State private var navPath      = NavigationPath()

    // Camera roll upload state
    @State private var pickerItem:   PhotosPickerItem?
    @State private var uploadState:  UploadState     = .idle
    @State private var uploadPct:    Double          = 0

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
                        .padding(.bottom, 12)

                    // Upload progress overlay when active
                    if case .loading = uploadState {
                        uploadProgressView(label: "Video hazırlanıyor…", percent: 0)
                    } else if case .uploading = uploadState {
                        uploadProgressView(label: "Sunucuya yükleniyor…", percent: uploadPct)
                    } else if case .failed(let msg) = uploadState {
                        uploadErrorBanner(msg)
                    } else if vm.isLoading && vm.plans.isEmpty {
                        Spacer()
                        ProgressView().tint(AppColors.neon)
                        Spacer()
                    } else if let error = vm.error {
                        errorState(error)
                    } else if vm.plans.isEmpty {
                        emptyState
                    } else {
                        planList
                    }
                }
            }
            .navigationBarHidden(true)
            .navigationDestination(for: PlanSummary.self) { plan in
                if plan.isCompleted {
                    ResultsView(planID: plan.id)
                } else {
                    ProcessingView(
                        videoID:   plan.id,
                        apiClient: auth.apiClient,
                        token:     auth.user?.token ?? ""
                    ) { _ in
                        Task { await vm.load(auth: auth) }
                    }
                }
            }
        }
        .task { await vm.load(auth: auth) }
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

    // MARK: - Upload Flow

    private func handlePickedItem(_ item: PhotosPickerItem) async {
        uploadState = .loading
        uploadPct   = 0

        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                uploadState = .failed("Video yüklenemedi.")
                return
            }

            uploadState = .uploading
            let filename = "\(UUID().uuidString).mp4"
            let token    = auth.user?.token ?? ""

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

        } catch {
            uploadState = .failed(error.localizedDescription)
            pickerItem  = nil
        }
    }

    // MARK: - Subviews

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("Gezi Planlarım")
                    .font(.system(size: 26, weight: .black, design: .rounded))
                    .foregroundStyle(.white)
                if let email = auth.user?.email, !email.isEmpty {
                    Text(email.components(separatedBy: "@").first ?? email)
                        .font(.system(size: 13))
                        .foregroundStyle(AppColors.muted)
                }
            }
            Spacer()

            // Camera Roll upload button
            PhotosPicker(
                selection: $pickerItem,
                matching: .videos,
                photoLibrary: .shared()
            ) {
                Image(systemName: "video.badge.plus")
                    .font(.system(size: 20))
                    .foregroundStyle(uploadState.isActive ? AppColors.muted : AppColors.neon)
            }
            .disabled(uploadState.isActive)
            .padding(.trailing, 8)

            // Offline history
            NavigationLink(destination: HistoryView()) {
                Image(systemName: "clock.arrow.trianglehead.counterclockwise.rotate.90")
                    .font(.system(size: 18))
                    .foregroundStyle(AppColors.muted)
            }
            .padding(.trailing, 12)

            Button {
                auth.logout()
            } label: {
                Image(systemName: "rectangle.portrait.and.arrow.right")
                    .font(.system(size: 18))
                    .foregroundStyle(AppColors.muted)
            }
        }
    }

    private func uploadProgressView(label: String, percent: Double) -> some View {
        VStack(spacing: 20) {
            Spacer()
            ZStack {
                Circle()
                    .stroke(Color.white.opacity(0.08), lineWidth: 5)
                    .frame(width: 80, height: 80)
                Circle()
                    .trim(from: 0, to: percent)
                    .stroke(AppColors.neon, style: StrokeStyle(lineWidth: 5, lineCap: .round))
                    .frame(width: 80, height: 80)
                    .rotationEffect(.degrees(-90))
                    .animation(.easeInOut(duration: 0.3), value: percent)
                Image(systemName: "icloud.and.arrow.up")
                    .font(.title2)
                    .foregroundStyle(AppColors.neon)
            }
            Text(label)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(.white)
            Text("Sayfa kapatılmayın")
                .font(.caption)
                .foregroundStyle(AppColors.muted)
            Spacer()
        }
    }

    private func uploadErrorBanner(_ message: String) -> some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 40))
                .foregroundStyle(AppColors.coral)
            Text(message)
                .font(.system(size: 15))
                .foregroundStyle(.white)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tamam") { uploadState = .idle }
                .foregroundStyle(AppColors.neon)
            Spacer()
        }
    }

    private var planList: some View {
        ScrollView {
            LazyVStack(spacing: 10) {
                ForEach(vm.plans) { plan in
                    Button {
                        navPath.append(plan)
                    } label: {
                        PlanRowView(plan: plan)
                    }
                    .buttonStyle(PressableButtonStyle())
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .refreshable { await vm.load(auth: auth) }
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "map")
                .font(.system(size: 56))
                .foregroundStyle(AppColors.muted)
            Text("Henüz gezi yok")
                .font(.system(size: 20, weight: .bold))
                .foregroundStyle(.white)
            Text("Instagram'da bir video paylaşarak\nveya kamera rolünden yükleyerek\nilk gezini oluştur.")
                .font(.system(size: 15))
                .foregroundStyle(AppColors.muted)
                .multilineTextAlignment(.center)
            // Camera roll shortcut in empty state
            PhotosPicker(
                selection: $pickerItem,
                matching: .videos,
                photoLibrary: .shared()
            ) {
                Label("Video Yükle", systemImage: "video.badge.plus")
                    .font(.system(size: 15, weight: .semibold))
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
                    .background(AppColors.neon.opacity(0.12))
                    .foregroundStyle(AppColors.neon)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppColors.neon.opacity(0.3)))
            }
            .buttonStyle(PressableButtonStyle())
            Spacer()
        }
    }

    private func errorState(_ error: APIError) -> some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 48))
                .foregroundStyle(AppColors.coral)
            Text(error.localizedDescription ?? "Bir hata oluştu.")
                .font(.system(size: 15))
                .foregroundStyle(AppColors.muted)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button("Tekrar Dene") { Task { await vm.load(auth: auth) } }
                .foregroundStyle(AppColors.neon)
            Spacer()
        }
    }
}
