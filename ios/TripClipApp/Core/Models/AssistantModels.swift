import Foundation

// MARK: - Trip Assistant (M26) — mobile-bff'nin AssistantRequest/AssistantResponse'uyla birebir eşleşir

/// İstemcinin bounded konuşma geçmişindeki tek bir tur. `role` "user"/
/// "assistant" ham string olarak taşınır (Endpoint.body'nin kendi
/// serileştirmesiyle birebir aynı) — ChatMessage (View-katmanı) bunu
/// kendi enum'una çevirir.
struct AssistantMessage {
    let role: String
    let content: String
}

struct AssistantReference: Decodable, Hashable {
    let type: String
    let dayIndex: Int
    let placeId: Int
}

struct AssistantResponse: Decodable {
    let answer: String
    let references: [AssistantReference]
}
