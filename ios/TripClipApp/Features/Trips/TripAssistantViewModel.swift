import Foundation
import OSLog

enum ChatRole {
    case user, assistant
}

struct ChatMessage: Identifiable {
    let id = UUID()
    let role: ChatRole
    let content: String
    var references: [AssistantReference] = []
}

@Observable
@MainActor
final class TripAssistantViewModel {

    private(set) var messages: [ChatMessage] = []
    private(set) var sending = false
    var sendError: String?

    // İstemci de sunucuyla AYNI üst sınırı uygular — bkz.
    // trip_assistant_service.py MAX_HISTORY_TURNS. Sunucu kendi sınırını
    // zaten uyguluyor, burası yalnızca gereksiz büyük bir payload
    // OLUŞTURMAMAK için.
    private static let maxHistoryTurns = 6
    private var lastFailedMessage: String?

    func send(_ text: String, tripID: Int, auth: AuthEnvironment) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !sending else { return }  // boş mesaj / çift-gönderim koruması
        // Token kontrolü mesaj sohbete EKLENMEDEN önce yapılır — aksi halde
        // token yoksa kullanıcı mesajı sohbette "takılı" kalır, ne API'ye
        // gider ne bir hata gösterir (diğer ViewModel'lerin AYNI "no token
        // → never calls API" ilkesi, bkz. ItineraryApplyHistoryViewModel).
        guard let token = auth.user?.token else { return }

        sendError = nil
        let history = Array(messages.suffix(Self.maxHistoryTurns)).map {
            AssistantMessage(role: $0.role == .user ? "user" : "assistant", content: $0.content)
        }
        messages.append(ChatMessage(role: .user, content: trimmed))

        sending = true
        defer { sending = false }

        do {
            let response: AssistantResponse = try await auth.apiClient.send(
                .assistant(tripID: tripID, message: trimmed, history: history), token: token
            )
            messages.append(ChatMessage(role: .assistant, content: response.answer, references: response.references))
        } catch let apiError as APIError {
            // Başarısız kullanıcı mesajı sohbette KALMAZ — web'in AYNI
            // davranışı (yeniden gönderilecek, kalıcı bir "gönderilemedi"
            // baloncuğu yerine tek bir hata + Tekrar Dene).
            messages.removeLast()
            lastFailedMessage = trimmed
            if apiError.isUnauthorized { auth.handleUnauthorized(); return }
            sendError = apiError.localizedDescription ?? "Asistana ulaşılamadı."
            Logger.network.warning("Assistant request failed: \(apiError.localizedDescription ?? "")")
        } catch {
            messages.removeLast()
            lastFailedMessage = trimmed
            sendError = "Asistana ulaşılamadı."
        }
    }

    func retryLastFailedMessage(tripID: Int, auth: AuthEnvironment) async {
        guard let message = lastFailedMessage else { return }
        await send(message, tripID: tripID, auth: auth)
    }
}
