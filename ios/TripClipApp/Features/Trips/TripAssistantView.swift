import SwiftUI

private let suggestedPrompts = [
    "Bugünü özetle",
    "Yarın ne yapacağım?",
    "Bu gezide kaç farklı yer var?",
    "En yoğun gün hangisi?",
    "Bu gezide yürüyerek gezmek mantıklı mı?",
]

/// AI Trip Assistant (M26) — trip'in gerçek durak/itinerary verisine
/// grounded, salt-okunur bir sohbet. `TripDetailView`'dan tek bir
/// NavigationLink ile açılır (Req 9 "prefer Trip Detail → AI Assistant
/// button → sheet/navigation destination", "avoid a giant full-screen
/// redesign").
struct TripAssistantView: View {

    let tripID: Int
    let trip: TripDetail
    /// Bir referans durağa dokunulduğunda çağrılır — `TripDetailView`
    /// kendi paylaşılan seçimini (`OptimizerSelection`) bununla günceller
    /// ve bu ekranı kapatır (Req 8 "the UI should be capable of
    /// identifying that stop without parsing the text" — metin ASLA
    /// ayrıştırılmaz, yalnızca sunucunun döndürdüğü day_index/place_id
    /// kullanılır).
    var onFocusStop: ((Int, Int) -> Void)? = nil

    @Environment(AuthEnvironment.self) private var auth
    @Environment(\.dismiss) private var dismiss
    @State private var vm = TripAssistantViewModel()
    @State private var inputText = ""
    @FocusState private var inputFocused: Bool

    var body: some View {
        ZStack {
            AppColors.background.ignoresSafeArea()

            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 12) {
                            if vm.messages.isEmpty {
                                suggestedPromptsView
                            }
                            ForEach(vm.messages) { message in
                                messageBubble(message)
                                    .id(message.id)
                            }
                            if vm.sending {
                                HStack(spacing: 8) {
                                    ProgressView().controlSize(.small)
                                    Text("Düşünüyor…")
                                        .font(.system(size: 13))
                                        .foregroundStyle(AppColors.textSecondary)
                                }
                                .padding(12)
                                .background(AppColors.surface)
                                .clipShape(RoundedRectangle(cornerRadius: 14))
                            }
                        }
                        .padding(16)
                    }
                    .onChange(of: vm.messages.count) {
                        if let last = vm.messages.last {
                            withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                        }
                    }
                }

                if let error = vm.sendError {
                    HStack(spacing: 10) {
                        Text(error)
                            .font(.system(size: 13))
                            .foregroundStyle(AppColors.destructive)
                        Spacer()
                        Button("Tekrar Dene") {
                            Task { await vm.retryLastFailedMessage(tripID: tripID, auth: auth) }
                        }
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(AppColors.accentText)
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(AppColors.destructive.opacity(0.08))
                }

                inputBar
            }
        }
        .navigationTitle("AI Asistan")
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Sohbet baloncukları

    private func messageBubble(_ message: ChatMessage) -> some View {
        VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 6) {
            Text(message.content)
                .font(.system(size: 14))
                .foregroundStyle(AppColors.text)
                .padding(12)
                .background(message.role == .user ? AppColors.accent.opacity(0.15) : AppColors.surface)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)

            if message.role == .assistant, !message.references.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(message.references, id: \.self) { ref in
                            referenceChip(ref)
                        }
                    }
                }
            }
        }
        // Ekran okuyucu her mesajı KİM söylediğiyle birlikte anons eder
        // (Req 9 "VoiceOver") — yalnızca içerik metni değil.
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(message.role == .user ? "Sen" : "Asistan"): \(message.content)")
    }

    private func referenceChip(_ ref: AssistantReference) -> some View {
        let stopName = trip.allStops.first { $0.placeId == ref.placeId }?.name ?? "Durak"
        return Button {
            onFocusStop?(ref.dayIndex, ref.placeId)
            dismiss()
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "mappin.circle.fill")
                    .font(.system(size: 12))
                Text(stopName)
                    .font(.system(size: 12, weight: .semibold))
            }
            .foregroundStyle(AppColors.route)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(AppColors.route.opacity(0.12))
            .clipShape(Capsule())
        }
        .buttonStyle(PressableButtonStyle())
        .accessibilityLabel("\(stopName) durağına git")
    }

    // MARK: - Önerilen sorular

    private var suggestedPromptsView: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Bu gezi hakkında bana soru sorabilirsin — yalnızca gezinin gerçek verisine bakarak cevap veririm.")
                .font(.system(size: 13))
                .foregroundStyle(AppColors.textSecondary)

            ForEach(suggestedPrompts, id: \.self) { prompt in
                Button {
                    Task { await vm.send(prompt, tripID: tripID, auth: auth) }
                } label: {
                    Text(prompt)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(AppColors.textSecondary)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(AppColors.surface2)
                        .clipShape(Capsule())
                }
                .buttonStyle(PressableButtonStyle())
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Giriş çubuğu

    private var inputBar: some View {
        HStack(spacing: 10) {
            TextField("Bu gezi hakkında bir şey sor…", text: $inputText, axis: .vertical)
                .focused($inputFocused)
                .font(.system(size: 15))
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(AppColors.surface2)
                .clipShape(RoundedRectangle(cornerRadius: 20))
                .lineLimit(1...4)
                // Dynamic Type ile taşan girdi büyüse bile gönder düğmesi
                // her zaman erişilebilir kalır (Req 9 "Dynamic Type").
                .accessibilityLabel("Asistana mesaj yaz")

            Button {
                let text = inputText
                inputText = ""
                Task { await vm.send(text, tripID: tripID, auth: auth) }
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 30))
                    .foregroundStyle(
                        inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || vm.sending
                            ? AppColors.textTertiary : AppColors.accentText
                    )
            }
            .disabled(inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || vm.sending)
            .accessibilityLabel("Gönder")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(AppColors.background)
    }
}
