"""
Application katmanı — Trip Assistant DTO'ları.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AssistantMessageDTO(BaseModel):
    """İstemcinin (bounded, kısaltılmış) taşıdığı konuşma geçmişindeki tek
    bir tur — bkz. AssistantRequestDTO.history."""
    role: Literal["user", "assistant"]
    content: str


class AssistantRequestDTO(BaseModel):
    message: str
    # Sunucu HİÇBİR konuşma kalıcılığı taşımıyor (bkz. docs/trip-assistant.md
    # "Conversation model" — bilinçli olarak session/DB şeması İCAT EDİLMEDİ).
    # İstemci son birkaç turu isterse gönderir; sunucu yine de kendi
    # MAX_HISTORY_TURNS sınırını uygular (bkz. trip_assistant_service.py) —
    # istemci sınırı aşsa bile prompt sınırsız büyüyemez.
    history: List[AssistantMessageDTO] = Field(default_factory=list)


class AssistantReferenceDTO(BaseModel):
    """Yanıtın işaret ettiği bir durak — array index DEĞİL, trip'in kendi
    kararlı kimliği (day_index + place_id). Sunucu tarafında context'e karşı
    DOĞRULANMIŞ (bkz. trip_assistant_service._validate_references) — model
    var olmayan bir durağa referans veremez."""
    type: Literal["stop"] = "stop"
    day_index: int
    place_id: int


class AssistantResponseDTO(BaseModel):
    answer: str
    references: List[AssistantReferenceDTO] = Field(default_factory=list)
