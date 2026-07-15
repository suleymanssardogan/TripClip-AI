# TripClip AI — Proje Özeti

> ⚠️ **Bu belge belirli bir tarihteki geliştirme notudur, canlı doküman değildir.**
> Güncel mimari ve kurulum talimatları için [README.md](README.md) ve [CLAUDE.md](CLAUDE.md) kaynak alınmalıdır (ör. iOS artık `services/ios/TripClipAI` değil, üst dizindeki `ios/` altında).

**Fırat Üniversitesi · Yazılım Mühendisliği 3. Sınıf Bitirme Projesi**
**Öğrenci:** Süleyman Sardoğan · **Dönem:** Mart–Haziran 2026

---

## Proje Nedir?

Instagram Reels gezisi videolarını yapay zeka ile analiz ederek otomatik seyahat planı oluşturan iOS uygulaması. Kullanıcı bir video paylaşır; sistem arka planda video içindeki mekanları çıkarır, koordinatlarını bulur, rotayı optimize eder ve AI destekli seyahat ipuçları üretir.

---

## Mimari Genel Bakış

```
iPhone (iOS App + Share Extension)
        │
        ▼ :8001
Mobile-BFF (FastAPI)  ←→  transformation layer
        │
        ▼ :8000
Core-API (FastAPI)
        ├── Celery Worker  ←── Redis Queue
        ├── PostgreSQL
        ├── Redis (cache + progress)
        ├── MongoDB (log)
        └── Qdrant (vector DB)
```

---

## Servisler

| Servis | Port | Teknoloji | Durum |
|--------|------|-----------|-------|
| core-api | 8000 | FastAPI + SQLAlchemy | ✅ Sağlıklı |
| mobile-bff | 8001 | FastAPI | ✅ Sağlıklı |
| web-bff | 8002 | FastAPI | ✅ Sağlıklı |
| celery-worker | — | Celery + Redis | ✅ Çalışıyor |
| PostgreSQL | 5432 | postgres:15 | ✅ Sağlıklı |
| Redis | 6379 | redis:7-alpine | ✅ Sağlıklı |
| MongoDB | 27017 | mongo:7 | ✅ Sağlıklı |
| Qdrant | 6333 | qdrant:latest | ✅ Sağlıklı (healthcheck düzeltildi) |

---

## ML Pipeline — 10 Aşamalı AI İşlem Hattı

Her aşama bağımsız `try/except` ile sarılıdır; bir servis düşerse diğerleri çalışmaya devam eder (graceful degradation).

| # | Aşama | Teknoloji | Çalışıyor mu? |
|---|-------|-----------|---------------|
| 1 | Video metadata | FFmpeg probe | ✅ |
| 2 | Frame extraction | FFmpeg (adaptive FPS) | ✅ |
| 3a | Nesne tespiti | YOLOv8n | ✅ |
| 3b | Landmark tespiti | Google Vision API | ⚠️ Billing gerekiyor |
| 3c | OCR | RapidOCR (ONNX) | ✅ |
| 3d | Ses transkripsiyonu | Whisper (base) | ✅ |
| 4 | NER (yer adı) | Turkish BERT (savasy) | ✅ (45s timeout) |
| 5 | Geocoding | Nominatim (TR) + Overpass | ✅ |
| 6 | Coğrafi outlier düzeltme | Haversine + Nominatim bbox | ✅ |
| 7 | Deduplikasyon | Haversine 2km eşiği | ✅ |
| 8 | Rota optimizasyonu | TSP (nearest-neighbor) | ✅ |
| 9 | Seyahat ipuçları | RAG (Qdrant + Ollama) | ✅ |
| 10 | Vektör gömme | Qdrant + sentence-transformers | ✅ |

### Çözülen Kritik Sorunlar

| Sorun | Çözüm |
|-------|-------|
| NER 361s pipeline bloğu | ThreadPoolExecutor + 45s timeout → OCR fallback |
| Overpass Docker'dan erişilemiyor | 3 endpoint zinciri; timeout → tüm POI'lar Nominatim'e |
| Nominatim yanlış şehir (Kaleköy→Amasya) | `countrycodes=tr` + `limit=3` + importance sıralaması |
| Coğrafi outlier (Kaleiçi→İstanbul) | `_fix_geographic_outliers()`: dominant il tespiti + bbox re-query |
| Boş route (ordered_locations key hatası) | `"route"` key'i düzeltildi, `place_data.location.lat/lng` yolu |

---

## iOS Uygulaması

### Uygulama Yapısı

```
TripClipAI (ana uygulama)
├── TripClipAIApp.swift       — @main, deep link handler (tripclip://processing/{id})
├── Views/
│   ├── Auth/LoginView        — Email/şifre + Apple Sign In
│   ├── Home/HomeView         — Video yükleme, son geziler carousel
│   ├── Home/Results/ResultsView — Harita, lokasyonlar, rota, ipuçları, PDF/paylaşım
│   ├── Processing/ProcessingView     — Share Extension akışı için progress ekranı
│   ├── Processing/ProcessingViewModel — Polling + yerel sayaç (createdAt kullanmaz)
│   └── History/HistoryView   — CoreData'dan geçmiş geziler, swipe-to-delete
├── Services/
│   ├── APIService            — REST çağrıları (upload, progress, status, queue-url)
│   ├── AuthService           — Keychain token yönetimi, login/register/Apple
│   ├── PersistenceService    — CoreData wrapper (SavedVideo entity)
│   ├── PDFExportService      — A4 PDF render (lokasyonlar, POI'lar, ipuçları)
│   └── TripShareCard         — 9:16 Instagram Stories kartı (UIImage)

TripClipShare (Share Extension)
└── ShareViewController       — Video yükleme + Instagram URL kuyruğa alma
```

### İki Farklı Kullanım Akışı

**1. Uygulama içi video yükleme:**
```
HomeView → [video seç] → upload → ResultsView
                                  └── progress polling (kendi içinde)
                                  └── tamamlanınca sonuçları göster
```

**2. Share Extension (Instagram'dan paylaş):**
```
Instagram → Paylaş → TripClip AI → ShareViewController
                                    ├── Video: multipart upload → deep link
                                    └── URL: queue-url API → deep link
                                          ↓
                              tripclip://processing/{id}
                                          ↓
                              TripClipAIApp.onOpenURL
                                          ↓
                              ProcessingView → ResultsView
```

### iOS Özellik Durumu

| Özellik | Durum |
|---------|-------|
| Email/şifre giriş | ✅ |
| Apple Sign In | ✅ |
| Video yükleme (galeri) | ✅ |
| Real-time progress (10 aşama) | ✅ |
| Lokasyon haritası (MapKit, numaralı pinler) | ✅ |
| Rota polilini | ✅ |
| OCR POI listesi (Apple Maps butonu) | ✅ |
| Ses transkripsiyonu gösterimi | ✅ |
| Seyahat ipuçları | ✅ |
| PDF export | ✅ |
| Instagram Stories paylaşımı | ✅ |
| Geçmiş geziler (CoreData) | ✅ |
| Offline mod (kayıtlı verilerden) | ✅ |
| Share Extension (video + URL) | ✅ (cihaza yükleme → paid Apple hesabı gerekiyor) |
| Deep link (tripclip://) | ✅ |
| Stale detection (>10dk takılı) | ✅ |

---

## API Endpoint Haritası

### Core API (`:8000/internal`)
| Method | Path | Açıklama |
|--------|------|----------|
| POST | `/videos/process` | Video yükle → Celery kuyruğa al |
| POST | `/videos/queue-url` | Instagram URL kuyruğa al |
| GET | `/videos/{id}` | Video detayı (tüm AI sonuçları) |
| GET | `/videos/{id}/progress` | Canlı ilerleme (stage, %, stale) |
| GET | `/videos/user/{user_id}` | Kullanıcı geçmişi |
| GET | `/videos/public` | Genel feed (şehir filtreli) |
| GET | `/videos/stats` | Platform istatistikleri |
| POST | `/auth/login` | Email/şifre giriş |
| POST | `/auth/register` | Kayıt |
| POST | `/auth/apple` | Apple Sign In |

### Mobile BFF (`:8001/api/mobile`)
| Method | Path | iOS'un çağırdığı |
|--------|------|-----------------|
| POST | `/videos/upload` | APIService.upload() |
| POST | `/videos/queue-url` | APIService.queueURL() |
| GET | `/videos/{id}` | APIService.getVideoStatus() → transformer |
| GET | `/videos/{id}/progress` | APIService.getVideoProgress() |
| GET | `/videos` | Kullanıcı listesi |

### Web BFF (`:8002/api/web`)
| Method | Path | Açıklama |
|--------|------|----------|
| POST | `/auth/login` | Web login |
| POST | `/auth/register` | Web kayıt |
| POST | `/auth/apple` | Apple Sign In (eklendi) |
| GET/POST | `/videos/*` | Video işlemleri |
| GET | `/plans/*` | Seyahat planları |

---

## Bilinen Sorunlar

| # | Sorun | Etki | Durum |
|---|-------|------|-------|
| 1 | Google Vision API billing kapalı | Landmark tespiti çalışmıyor | ⚠️ Ücretli hesap gerekiyor |
| 2 | Share Extension fiziksel cihaza yüklenemiyor | Personal Team → App Extension imzalanamıyor | ⚠️ $99/yıl Apple Developer gerekiyor |
| 3 | Overpass API community sunucuları yavaş | Geocoding bazen 20-30s sürebilir | ⚠️ 600s cooldown ile yönetiliyor |
| 4 | Whisper base model hassasiyeti düşük | Gürültülü videolarda transkripsiyon boş | ⚠️ Whisper small/medium ile iyileşir |
| 5 | MapKit offline harita yok | Harita internet gerektiriyor | 🔵 Düşük öncelik |

---

## Düzeltilen Buglar (Bu Oturumda)

1. ✅ `to_mobile_detail` null AI fields crash — `or {}` pattern ile düzeltildi
2. ✅ "3d 12s" elapsed timer — `Date()` local sayaç, `createdAt` kullanılmıyor
3. ✅ Celery task hiç queue'a girmiyordu — `celery_app` import sırası düzeltildi
4. ✅ Boş route (`[]`) — yanlış key `ordered_locations` → `route`
5. ✅ NER 361s pipeline bloğu — 45s ThreadPoolExecutor timeout
6. ✅ Overpass tüm endpoint'ler başarısız — Nominatim fallback
7. ✅ Nominatim yanlış şehir eşleşmesi — `countrycodes=tr` + bbox
8. ✅ Coğrafi outlier (Kaleköy→Amasya, Kaleiçi→İstanbul) — dominant il + re-query
9. ✅ `queueURL()` class dışında kalmış — APIService brace hatası
10. ✅ `ProcessingStage` Equatable hatası — enum yerine `@Published` değişkenler
11. ✅ Qdrant healthcheck hep fail — `/dev/tcp` bash ile düzeltildi
12. ✅ ShareViewController `source_url` → `url` field adı düzeltildi
13. ✅ Web-BFF Apple Sign In endpoint eksikti — eklendi

---

## Proje Boyutu (yaklaşık)

| Katman | Dosya sayısı | Satır sayısı |
|--------|-------------|-------------|
| core-api (Python) | ~40 dosya | ~4.500+ satır |
| mobile-bff (Python) | ~15 dosya | ~800+ satır |
| web-bff (Python) | ~12 dosya | ~600+ satır |
| iOS (Swift) | 12 dosya | ~3.000+ satır |
| **Toplam** | **~80 dosya** | **~9.000+ satır** |

---

## Test Edilmiş Senaryo

**Antalya videosu** (`35be0790-…mp4`, 95s):

```
Pipeline çıktısı:
  ✅ YOLO         — 10 nesne tespit [10.9s]
  ✅ Whisper      — Sessiz video (0 karakter) [11.4s]
  ⏰ NER          — 45s timeout → OCR fallback [45s]
  ✅ Nominatim    — 9 lokasyon geocoded [4.8s]
  ✅ Outlier Fix  — Kaleköy: Amasya→Antalya (69km), Kaleiçi: İstanbul→Antalya (42km)
  ✅ Dedup        — 9 → 8 lokasyon
  ✅ Route        — 8 durak, 291.64km TSP rotası
  ✅ RAG          — Seyahat ipuçları üretildi
  ✅ Qdrant       — 9 vektör eklendi [20.5s]
  Toplam: ~105 saniye
```

---

*Son güncelleme: 25 Nisan 2026*
