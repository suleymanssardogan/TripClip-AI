"""
Domain katmanı — RAG retrieval'ın ne zaman TETİKLENECEĞİNE karar veren saf
fonksiyon (M30). DB/HTTP/Qdrant'a hiç DOKUNMAZ — `context_builder.py`'nin
AYNI ilkesi.

Neden ayrı bir fonksiyon (ve neden `PlaceKnowledgeRetriever`'ın İÇİNDE
DEĞİL): "retrieval her mesajda mı çalışsın" sorusu SAF bir metin sınıflandırma
kararı — I/O gerektirmez, dolayısıyla domain katmanında, hiçbir mock'a
gerek kalmadan test edilebilir. `TripAssistantService` bunu retriever'ı
ÇAĞIRMADAN ÖNCE kontrol eder (bkz. milestone Req 12 "no RAG when it adds
no value" + Req 14 "no unnecessary network calls") — böylece "sadece boş
sonuç dönsün" değil, "Qdrant'a/DB'ye HİÇ gidilmesin" garantisi verilir;
bu, testlerde retriever'ın .calls listesinin BOŞ kaldığı doğrulanarak
kanıtlanabilir (bkz. tests/test_trip_assistant_service.py).

Milestone'un kendi örnekleri BİREBİR bu listeden karşılanacak şekilde
seçildi (bkz. tests/test_retrieval_heuristic.py):
  - "Zeugma Müzesi hakkında ne biliyorsun?"                    → True
  - "Gaziantep'te bu geziye yakın başka tarihi yerler neler?"  → True
  - "Bugün kaç durağımız var?"                                  → False
  - "İlk durağımız saat kaçta?"                                 → False
"""
from app.ml.location_deduplicator import normalize_place_name

# `normalize_place_name`, adı "mekan adı" gibi görünse de aslında GENEL bir
# Türkçe-ASCII katlama + noktalama temizleme yardımcısı (bkz. kendi doc
# yorumu) — burada tam bir kullanıcı mesajını normalize etmek için TEKRAR
# KULLANILIR, ikinci bir çeviri tablosu İCAT EDİLMEZ.
#
# Liste kasıtlı olarak "bilgi arayan" (knowledge-seeking) niyeti yakalayan,
# İYİMSER (permissive) bir anahtar kelime kümesi: yanlış-pozitif (gereksiz
# ama zararsız bir retrieval denemesi — Trip Context yine de otorite kalır)
# yanlış-negatiften (gerçekten faydalı olacak bir soruda retrieval'ın hiç
# denenmemesi) daha ucuz bir hata. Sabit bir modül seviyesi liste — yeni bir
# sınıflandırıcı/agent İCAT EDİLMEDİ (bkz. milestone Req 5 "do not build a
# complex classifier/agent system").
_KNOWLEDGE_INTENT_KEYWORDS = (
    # Türkçe (normalize_place_name çıktısı formatında: ascii, küçük harf)
    "hakkinda", "tarihce", "tarihi", "bilgi", "anlat", "acikla",
    "onemli", "onemi", "neden", "yakin", "civar", "baska",
    "gezilecek", "gorulecek", "oner", "tavsiye", "nedir", "kimdir",
    # M31: mekanın kendi açılış/kapanış saatiyle ilgili sorular — "kaçta"
    # KASITLI OLARAK burada YOK ("İlk durağımız saat kaçta?" hâlâ False
    # kalmalı, bkz. yukarıdaki M30 örneği: bu, gezinin KENDİ çizelgesi
    # hakkında, Trip Context'in zaten cevapladığı bir soru) — ama "açılış"/
    # "kapanış" gövdeleri (açılıyor/açılış/açık mı/kapanıyor/kapalı) bir
    # MEKANIN kendi (Place.opening_hours, M31'de RAG'e eklendi) bilgisini
    # arar, retrieval GEREKİR. Gerçek doğrulama sırasında bulunan bir
    # boşluk (bkz. docs/trip-assistant.md "Bugs found/fixed") — bu
    # eklenmeden "Zeugma Müzesi kaçta açılıyor?" YANLIŞLIKLA False
    # dönüyordu, RAG'e eklenen opening_hours verisi hiç ERİŞİLEMEZ kalıyordu.
    "acil", "acik", "kapan", "kapali", "giris ucret",
    # İngilizce (test/geliştirici girdisi ihtimaline karşı)
    "about", "history", "historical", "nearby", "attraction",
    "recommend", "describe", "information", "museum", "open", "closing",
)


def should_retrieve_place_knowledge(message: str) -> bool:
    """Kullanıcının sorusu, Trip Context'in ZATEN sahip olduğu bilginin
    (durak/gün/saat/sıra) ÖTESİNDE bir mekan bilgisinden fayda görür mü?

    Yalnızca aşağıdaki anahtar kelimelerden biri geçiyorsa `True` döner —
    "Bugün kaç durağımız var?"/"İlk durağımız saat kaçta?" gibi salt
    itinerary sorularının BÜYÜK ÇOĞUNLUĞU hiçbirini içermez, bu yüzden
    varsayılan (opt-in, opt-out DEĞİL) davranış retrieval'ı ATLAMAKTIR —
    bkz. milestone Req 12."""
    normalized = normalize_place_name(message)
    return any(keyword in normalized for keyword in _KNOWLEDGE_INTENT_KEYWORDS)
