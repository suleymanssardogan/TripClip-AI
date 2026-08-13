"""
Domain katmanı — Trip Assistant salt-okunur ARAÇLARI (Milestone 32).

Saf fonksiyonlar — `context_builder.py`/`retrieval_heuristic.py`'nin AYNI
ilkesi: DB/HTTP/Qdrant'a hiç DOKUNMAZ. Her iki araç da (`get_trip_day`,
`find_trip_stop`) YALNIZCA çağıranın (`TripAssistantService`) ZATEN
oluşturmuş olduğu, ZATEN yetkilendirilmiş `TripContext` nesnesi üzerinde
çalışır — `trip_id`/`user_id` parametresi YOKTUR, ALINAMAZ da (bkz.
milestone Req 4 "security boundary"): modelin başka bir trip'e erişmesi
yalnızca "engelleniyor" değil, bu fonksiyonların imzasında böyle bir
alan bile YOK — sözdizimsel olarak İFADE EDİLEMEZ.

Neden yeni bir I/O katmanı GEREKMEDİ: `TripContext` (context_builder.py)
zaten her durağın place_id/day_index/order_index/city/category/
arrival_time/departure_time/visit_duration_minutes bilgisini taşıyor —
`get_trip_day`/`find_trip_stop`'un ihtiyaç duyduğu HER ŞEY zaten bellekte,
`TripAssistantService.ask()`'in ZATEN kurduğu context'te. Yeni bir
repository/SQL sorgusu YOK — tool çalıştırma, DB'ye SIFIR ek round-trip
demek (bkz. milestone Req 17).

## Neden yalnızca İKİ araç (üç değil)

Milestone kavramsal olarak üçüncü bir araç önerdi: `get_trip_schedule(day_index)`
— "o günün SIRALI programını döner". İncelemede doğrulandı:
`SqlTripRepository._stops_with_places()`, `.order_by(TripStop.day_index.asc(),
TripStop.order_index.asc())` — `ContextDay.stops` HER ZAMAN zaten sıralı
(hem uygulanmış-itinerary yolunda optimizer'ın kendi ürettiği ziyaret
sırasıyla, hem ham-trip yolunda bu SQL ORDER BY ile). Yani önerilen
`get_trip_schedule(day_index)` ile `get_trip_day(day_index)` AYNI VERİYİ,
AYNI SIRAYLA dönerdi — gerçek bir kopya, icat edilmiş bir ayrım değil.
Milestone'un kendi "if inspection shows that one of these tools is
redundant with another, do not create duplicate functionality" talimatına
göre BİLİNÇLİ OLARAK BİRLEŞTİRİLDİ.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from app.domain.assistant.context_builder import TripContext


@dataclass(frozen=True)
class ToolDefinition:
    """Aracın kendi kimliği — isim/açıklama TEK KAYNAKTAN (bu dosyadan)
    okunur, hem çalıştırma (`TOOL_NAMES`/`execute_tool`) hem prompt'a
    yazılan araç listesi (`TripAssistantService._build_system_prompt`)
    AYNI tanımı kullanır, ikisi asla BİRBİRİNDEN SAPMAZ."""
    name: str
    description: str


@dataclass
class ToolCallRequest:
    """Modelin JSON yanıtındaki `tool_call` alanının doğrulanmış hâli
    (bkz. `TripAssistantService._parse_tool_call`) — yalnızca ÜÇ alan
    taşır, hiçbiri trip/user kimliği İÇERMEZ."""
    name: str
    day_index: Optional[int] = None
    place_id: Optional[int] = None


def _get_trip_day(context: TripContext, request: ToolCallRequest) -> Dict[str, Any]:
    if request.day_index is None:
        return {"error": "day_index parametresi gerekli."}
    for day in context.days:
        if day.day_index == request.day_index:
            return {
                "day_index": day.day_index,
                "date": day.date,
                "stops": [s.to_dict() for s in day.stops],
            }
    return {"error": f"day_index={request.day_index} bu gezide bulunamadı."}


def _find_trip_stop(context: TripContext, request: ToolCallRequest) -> Dict[str, Any]:
    if request.place_id is None:
        return {"error": "place_id parametresi gerekli."}
    for day in context.days:
        for stop in day.stops:
            if stop.place_id == request.place_id:
                return {"day_index": day.day_index, "date": day.date, "stop": stop.to_dict()}
    return {"error": f"place_id={request.place_id} bu gezide bulunamadı."}


TOOL_DEFINITIONS: List[ToolDefinition] = [
    ToolDefinition(
        name="get_trip_day",
        description="Belirtilen günün (day_index) tüm duraklarını, sırasıyla ve varsa saatleriyle döner.",
    ),
    ToolDefinition(
        name="find_trip_stop",
        description="Belirtilen place_id'ye sahip durağı ve hangi günde/sırada olduğunu döner.",
    ),
]

_TOOL_EXECUTORS: Dict[str, Callable[[TripContext, ToolCallRequest], Dict[str, Any]]] = {
    "get_trip_day": _get_trip_day,
    "find_trip_stop": _find_trip_stop,
}

TOOL_NAMES = frozenset(_TOOL_EXECUTORS.keys())


def execute_tool(context: TripContext, request: ToolCallRequest) -> Dict[str, Any]:
    """Tüm araç çağrıları için TEK giriş noktası. Bilinmeyen bir araç adı
    GÜVENLİ bir hata sözlüğü döner (fırlatmaz) — çağıran
    (`TripAssistantService`) bunu normal bir "araç sonucu" turu olarak
    modele geri besleyip modele bir düzeltme şansı tanıyabilir, tüm
    isteği ÇÖKERTMEZ (bkz. milestone Req 14 "tool failures must never
    expose internals" — bu fonksiyon SAF olduğu için pratikte bir stack
    trace/SQL hatası üretecek bir yol yok, ama savunma amaçlı yine de
    ham `Exception` metni asla döndürülmez, yalnızca tipi)."""
    executor = _TOOL_EXECUTORS.get(request.name)
    if executor is None:
        return {"error": f"Bilinmeyen araç: {request.name!r}."}
    try:
        return executor(context, request)
    except Exception as exc:
        return {"error": f"Araç çalıştırılamadı ({type(exc).__name__})."}
