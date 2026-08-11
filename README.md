# TripClip AI

> Instagram seyahat videolarını yapay zeka ile analiz edip optimize edilmiş gezi planlarına dönüştüren uygulama.

[![Swift](https://img.shields.io/badge/Swift-5.9+-orange.svg)](https://swift.org)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docker.com)

**Öğrenci:** Süleyman Sardoğan  
**Kurum:** Fırat Üniversitesi — Yazılım Mühendisliği (3. Sınıf)  
**Dönem:** Mart – Haziran 2026 · 12 haftalık akademik proje (devam eden ek geliştirmelerle)  
**Durum:** 12 haftalık plan tamamlandı; plan sonrası ek geliştirme: Trip Builder, AI Trip Optimizer (rota optimizasyonu, uygula/geri al), Trip Detail deneyimi ve AI Trip Assistant (gezi verisine dayalı sohbet) eklendi

---

## Problem & Çözüm

Kullanıcılar Instagram'da yüzlerce gezi videosu kaydeder; bu videolar organize edilmeden unutulur ve gerçek bir seyahat planına dönüşmez.

**TripClip AI** bir videoyu paylaşır paylaşmaz şunları yapar:
1. Video karelerini ve sesini yapay zeka ile analiz eder
2. Lokasyonları, mekanları ve yerleri otomatik tespit eder
3. Koordinatları haritaya işler, rotayı optimize eder
4. Seyahat ipuçları ve özet oluşturur

---

## Mimari

```
┌──────────────────────────────────────────────────────┐
│                   İstemciler                         │
│  iOS App (Swift)          Web App (Next.js :3000)   │
└──────────┬───────────────────────────┬───────────────┘
           │                           │
           ▼                           ▼
   Mobile BFF :8001            Web BFF :8002
           │                           │
           └─────────────┬─────────────┘
                         ▼
                  Core API :8000  ──▶  Celery Worker (async pipeline)
                  ┌──────────────────────────────┐
                  │         ML Pipeline          │
                  │  Gemini (multimodal, tek çağrı) │
                  │  veya klasik: YOLOv8 + Whisper  │
                  │  + RapidOCR + Turkish BERT NER  │
                  │  Nominatim (Geocoding)       │
                  │  TSP Route Optimizer         │
                  │  Qdrant RAG (Travel Tips)    │
                  └──────────────────────────────┘
                         │
        ┌────────────────┼──────────┬─────────────┐
        ▼                ▼          ▼             ▼
   PostgreSQL          Redis     MongoDB       Qdrant
   (Ana DB)      (Cache+Broker) (Secondary)  (Vector DB)
```

`USE_GEMINI=true` (varsayılan) tek bir Gemini çağrısıyla lokasyon çıkarımı yapar; `false` ise YOLOv8 + Google Vision + RapidOCR + Whisper + Turkish BERT NER klasik hattı çalışır. `USE_HYBRID=true` ikisini birleştirir.

### Video pipeline'ın ötesinde: Trip Builder katmanı

Video analizinden çıkan mekanlar bir Library'ye kaydedildikten sonra, ayrı ve bağımsız bir katman devreye girer — **Trip Builder**: kullanıcı Library'den mekan seçip bir **Trip** oluşturur (yalnızca iOS'ta — bkz. [docs/web-trip-optimizer.md](docs/web-trip-optimizer.md) "Why a Trip Detail page had to be built first"), **AI Trip Optimizer** bu durakları gün/saat kısıtlarına göre rotalar (greedy_distance veya OR-Tools stratejisi), sonucu Trip'e **uygular** (apply/undo geçmişiyle), ve **AI Trip Assistant** o gezinin gerçek verisine dayanarak soruları yanıtlar. Bu katman core-api'nin kendi `/internal/trips/...` uç noktalarında yaşar, video pipeline'ından tamamen ayrı çalışır — video analizi hiçbir trip/optimizer mantığını bilmez. Detaylar: [docs/trip-optimizer.md](docs/trip-optimizer.md), [docs/web-trip-optimizer.md](docs/web-trip-optimizer.md), [docs/ios-trip-optimizer.md](docs/ios-trip-optimizer.md), [docs/trip-assistant.md](docs/trip-assistant.md).

---

## Teknoloji Yığını

### Backend
| Katman | Teknoloji |
|--------|-----------|
| API Framework | FastAPI 0.109 |
| ORM | SQLAlchemy + PostgreSQL |
| Cache / Broker | Redis 7 (Celery broker + progress) |
| Secondary DB | MongoDB |
| Vector DB | Qdrant |
| Multimodal AI | Google Gemini 2.5 Flash (`USE_GEMINI=true`, default) |
| Computer Vision (klasik mod) | YOLOv8 + Google Vision API (opsiyonel, `USE_GOOGLE_VISION`) |
| Speech-to-Text (klasik mod) | OpenAI Whisper |
| OCR (klasik mod) | RapidOCR (ONNX) |
| NER (klasik mod) | Turkish BERT (HuggingFace) |
| Geocoding | Nominatim (OpenStreetMap) |
| Route | TSP Solver (Haversine) |
| Travel Tips | `USE_GEMINI=true` (varsayılan): Gemini üretir. Klasik modda (`USE_GEMINI=false`): Qdrant + sentence-transformers + opsiyonel Ollama (`OLLAMA_URL` boşsa devre dışı — bkz. [docs/deployment.md](docs/deployment.md)) |
| Rota Optimizasyonu | `greedy_distance` (varsayılan) veya `ortools` stratejisi — gün/saat kısıtlı çok-günlü itinerary (bkz. [docs/trip-optimizer.md](docs/trip-optimizer.md)) |
| AI Trip Assistant | Gemini (sağlayıcı-agnostik `AIProvider` arayüzü arkasında), trip'in gerçek durak/itinerary verisine grounded, salt-okunur sohbet (bkz. [docs/trip-assistant.md](docs/trip-assistant.md)) |
| Konteyner | Docker Compose (8 servis: core-api, celery-worker, mobile-bff, web-bff, postgres, redis, mongodb, qdrant) |

### iOS (Swift)
| Katman | Teknoloji |
|--------|-----------|
| UI | SwiftUI |
| Harita | MapKit (MKMapView) |
| Yerel Depolama | CoreData |
| Auth | JWT + Apple Sign In + Keychain |
| Paylaşım | Share Extension + UIActivityViewController |
| Dışa Aktarma | PDF (UIGraphicsPDFRenderer), Instagram Story Card |

### Web (Next.js)
| Katman | Teknoloji |
|--------|-----------|
| Framework | Next.js 16 (App Router) |
| UI | React 19 + Tailwind CSS |
| Animasyon | Framer Motion |
| Harita | Leaflet + react-leaflet |
| İkonlar | Lucide React |

---

## Proje Yapısı

```
TripClip-AI/
├── docker-compose.yml          # 7 servis: core-api, mobile-bff, web-bff,
│                               #           postgres, redis, qdrant, mongodb
├── services/
│   ├── core-api/               # Ana ML pipeline & iş mantığı (:8000)
│   │   ├── app/
│   │   │   ├── core/services/  # video_processor.py — tam pipeline
│   │   │   ├── ml/             # ner_service.py, vision, ocr, audio, rag,
│   │   │   │                   #   gemini_service.py, ai_provider.py
│   │   │   ├── domain/         # optimization/, assistant/ (saf iş mantığı)
│   │   │   ├── application/    # services/, dto/ (use case katmanı)
│   │   │   ├── models/         # User, Video, Trip, TripStop, TripItinerary...
│   │   │   ├── api/internal/   # auth, videos, trips, trip_optimization,
│   │   │   │                   #   trip_sharing, trip_assistant
│   │   │   └── infrastructure/ # SQLAlchemy repository implementasyonları
│   │   └── tests/
│   ├── mobile-bff/             # iOS için BFF proxy (:8001)
│   │   └── app/routes/         # auth, videos, trips, trip_optimization,
│   │                           #   trip_sharing, trip_assistant
│   └── web-bff/                # Web için BFF proxy (:8002)
│       └── app/routes/         # auth, plans, videos, trips, trip_optimization,
│                               #   trip_sharing, trip_assistant
├── ios/                         # Native iOS uygulaması (top-level, XcodeGen)
│   ├── project.yml              # xcodegen ile TripClipApp.xcodeproj üretir
│   ├── TripClipApp/
│   │   ├── App/                 # AppDelegate, RootView, TripClipApp (@main)
│   │   ├── Core/                # Network, Models, Storage (Keychain, CoreData)
│   │   ├── Features/             # Auth, Home, Processing, Results, History,
│   │   │                         #   Trips (TripDetail, Optimizer, Assistant)
│   │   └── Resources/            # Assets.xcassets, Info.plist, entitlements
│   ├── TripClipShare/            # Share Extension (Instagram → TripClip)
│   └── Shared/                   # Kod her iki target'ta da paylaşılır
└── web/                        # Next.js web uygulaması (:3000)
    └── src/app/
        ├── dashboard/          # Kullanıcı videoları + istatistikler
        ├── explore/            # Genel gezi planları keşfi
        ├── analyze/[id]/       # Video analiz sonuçları + progress polling
        ├── editor/[id]/        # Gezi planı düzenleyici
        ├── share/[id]/         # Paylaşılabilir gezi sayfası
        └── trips/              # Trip Detail, AI Optimizer, geçmiş, Assistant
```

---

## Hızlı Başlangıç

### Gereksinimler
- Docker & Docker Compose
- Xcode 16+ (iOS için)
- Node.js 20+ (Web için)
- Google Gemini API anahtarı ([aistudio.google.com](https://aistudio.google.com))

### 1. Backend & Servisler

```bash
# Repoyu klonla
git clone https://github.com/suleymanssardogan/TripClip-AI.git
cd TripClip-AI

# Ortam değişkenlerini ayarla
cp .env.example .env
# .env dosyasına GEMINI_API_KEY ekle (JWT_SECRET_KEY de gerekli)

# Tüm servisleri başlat
docker compose up -d

# Servis durumlarını kontrol et
docker compose ps
```

| Servis | URL |
|--------|-----|
| Core API | http://localhost:8000 |
| Core API Docs | http://localhost:8000/docs |
| Mobile BFF | http://localhost:8001 |
| Web BFF | http://localhost:8002 |

### 2. Web Uygulaması

```bash
cd web
npm install
npm run dev
# http://localhost:3001 adresinde açılır
```

### 3. iOS Uygulaması

```bash
cd ios
xcodegen generate      # project.yml'den TripClipApp.xcodeproj üretir
open TripClipApp.xcodeproj
# Xcode'da TripClipApp scheme'i seç → Run (⌘R)
# Backend Docker'da çalışıyor olmalı
```

---

## ML Pipeline Akışı

Video yükleme, Celery kuyruğuna (`video_processing`) düşer; her aşama `_safe_run()` ile sarılıdır — bir servis başarısız olursa pipeline durmaz, fallback ile devam eder.

```
Video Yükle (Celery task)
    │
    ├─▶ [1] Metadata çıkarma (FFprobe)
    ├─▶ [2] Kare örnekleme (FFmpeg)
    ├─▶ [3] USE_GEMINI=true  → Gemini multimodal (lokasyon çıkarımı, tek çağrı)
    │       USE_GEMINI=false → Paralel klasik analiz:
    │           ├─ YOLOv8 nesne tespiti
    │           ├─ Google Vision landmark tespiti (opsiyonel)
    │           ├─ RapidOCR metin çıkarma
    │           ├─ Whisper ses transkripsiyonu
    │           └─ Turkish BERT ile NER
    ├─▶ [4] Nominatim geocoding
    ├─▶ [5] Haversine deduplication
    ├─▶ [6] TSP rota optimizasyonu
    └─▶ [7] Qdrant + sentence-transformers RAG — seyahat ipuçları
```

Her aşama Redis'e yazılır → iOS & Web gerçek zamanlı progress gösterir.

---

## iOS Uygulama Özellikleri

| Özellik | Açıklama |
|---------|----------|
| **Giriş** | Email/şifre + Apple Sign In, JWT + Keychain |
| **Video Yükleme** | PhotosPicker → multipart upload |
| **Gerçek Zamanlı Progress** | Redis polling, 10 aşamalı ilerleme çubuğu |
| **Harita** | MapKit, numaralı pinler + optimize rota çizgisi |
| **Lokasyon Detayı** | Koordinat, tür, Google/Apple Maps yönlendirme |
| **Geçmiş** | CoreData ile offline erişim |
| **Paylaşım** | Instagram Story kartı, görsel paylaşım, PDF dışa aktarma |
| **Share Extension** | Instagram'dan direkt TripClip AI'a paylaş |
| **Trip Builder** | Library'den mekan seçip çok-günlü bir Trip oluşturma (yalnızca iOS) |
| **AI Trip Optimizer** | Gün/saat kısıtlı rota optimizasyonu, gün seçici + harita↔liste senkron seçim, Trip'e uygula |
| **Apply Geçmişi & Geri Al** | Her uygulama/geri alma kalıcı olarak loglanır, yalnızca en son kayıt geri alınabilir |
| **Trip Detail** | Gün navigasyonu, MapKit ile çift yönlü harita↔liste seçimi, uygulanan itinerary göstergesi |
| **AI Trip Assistant** | Gezinin gerçek durak/itinerary verisine dayalı, salt-okunur sohbet asistanı |

### TODO — App Icon (App Store gönderimi öncesi)

`ios/TripClipApp/Resources/Assets.xcassets/AppIcon.appiconset/` şu an sadece `Contents.json` içeriyor, gerçek görsel yok. `project.yml` modern **tek boyutlu App Icon** formatını kullanıyor (`ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon`, Contents.json'da tek "universal / 1024x1024" girişi) — bu yüzden Xcode 14+ ile tüm diğer boyutlar (Home Screen, Spotlight, Settings, App Store) otomatik türetiliyor. Gerekli olan:

- **1 adet 1024×1024 px PNG**, alfa kanalı / şeffaflık **olmadan** (App Store Connect bu formatı reddeder).
- Dosyayı Xcode'da `AppIcon.appiconset`'e sürükleyip bırakmak yeterli (Contents.json otomatik güncellenir).
- Bu görsel aynı zamanda App Store Connect'teki "1024x1024 App Store icon" alanına da yüklenir — ayrı bir dosyaya gerek yok.

Bu depo bir placeholder ikon üretmez; gerçek marka/logo asseti proje sahibi tarafından sağlanmalıdır.

---

## Web Uygulama Sayfaları

| Sayfa | Açıklama |
|-------|----------|
| `/dashboard` | Kullanıcının videoları, işlem durumu |
| `/explore` | Tüm tamamlanan gezi planları, şehir filtresi |
| `/analyze/[id]` | Video analiz sonuçları (harita + lokasyonlar + ipuçları) |
| `/editor/[id]` | Gezi planı timeline editörü (gerçek veri) |
| `/share/[id]` | Paylaşılabilir gezi sayfası, Google Maps entegrasyonu |
| `/invite/[token]` | Trip collaborator daveti kabul/red |
| `/trips` | Kullanıcının Trip'leri (Trip'ler yalnızca iOS'ta oluşturulur, web salt-okunur listeler) |
| `/trips/[id]` | Trip Detail — gün navigasyonu, harita↔liste senkron seçim, uygulanan itinerary göstergesi |
| `/trips/[id]/optimize` | AI Trip Optimizer — yapılandırma + sonuç (yeni üretilen veya kayıtlı itinerary) |
| `/trips/[id]/history` | Optimizasyon geçmişi |
| `/trips/[id]/apply-history` | Uygulama geçmişi + geri al (undo) |
| `/trips/[id]/assistant` | AI Trip Assistant — gezinin gerçek verisine dayalı sohbet |

> Not: Video yükleme artık yalnızca iOS Share Extension üzerinden yapılır — web'de bir upload sayfası yoktur (bilinçli ürün kararı).

---

## Geliştirme Durumu

| Hafta | Milestone | Durum |
|-------|-----------|-------|
| 1–2 | Altyapı kurulumu, Docker, temel API | ✅ |
| 3–4 | Computer Vision pipeline (YOLOv8 + Google Vision) | ✅ |
| 5 | Ses tanıma (Whisper) + EasyOCR | ✅ |
| 6 | NER (Turkish BERT) + Nominatim geocoding | ✅ |
| 7 | TSP rota optimizasyonu + Haversine dedup | ✅ |
| 8 | iOS uygulama + Web frontend + Share Extension | ✅ |
| 9–10 | Test, optimizasyon, entegrasyon, Gemini pipeline | ✅ |
| 11–12 | Deployment altyapısı (nginx, SSL, CI/CD), dokümantasyon, sunum | 🔄 |

### Tamamlanan Özellikler (12 haftalık plan kapsamında)
- [x] Gemini multimodal pipeline (+ hibrit/klasik mod fallback)
- [x] Gerçek zamanlı işlem takibi (Redis + polling)
- [x] iOS uygulaması (auth, upload, harita, paylaşım, PDF)
- [x] Share Extension (Instagram → TripClip AI)
- [x] Web dashboard + analiz + editör + paylaşım sayfaları
- [x] JWT kimlik doğrulama + rate limiting + production secret validation
- [x] CoreData offline depolama
- [x] Docker altyapısı (8 servis dev, +nginx/celery-worker/web prod)
- [x] Production deployment altyapısı (nginx + TLS, deploy/SSL scriptleri, GitHub Actions CI)
- [x] Veritabanı index optimizasyonları

### Ek Geliştirmeler (12 haftalık planın ötesinde)

12 haftalık akademik planın tamamlanmasının ardından, projeyi tek seferlik bir
video-analiz aracından gerçek bir gezi planlama ürününe taşımak için devam
eden bağımsız bir geliştirme hattı:

- [x] **Trip Builder** — Library'den mekan seçip Trip oluşturma (iOS)
- [x] **AI Trip Optimizer** — `greedy_distance` ve `ortools` stratejileri,
      gün-farkında açılış-saati kısıtları, gece yarısını aşan planlama
      aralıkları, taşıma modu seçimi, planlama tarihi
- [x] **Trip'e Uygula + Apply Geçmişi & Geri Al** — kalıcı, denetlenebilir
      uygulama geçmişi; yalnızca en son kayıt güvenle geri alınabilir
- [x] **Kayıtlı İtinerary Geçmişi + Silme** — anti-enumeration korumalı
- [x] **Web AI Trip Optimizer** — iOS'takiyle aynı Web BFF uç noktalarını
      kullanan, tam işlevsel web deneyimi (harita↔liste senkron seçimi dahil)
- [x] **Trip Detail deneyimi** — çok günlü gün navigasyonu (iOS + Web),
      MapKit/Leaflet çift yönlü harita↔liste seçimi, uygulanan itinerary
      göstergesi
- [x] **AI Trip Assistant** — trip'in gerçek verisine grounded, salt-okunur
      sohbet asistanı (iOS + Web); halüsinasyon referansları sunucu
      tarafında doğrulanıp elenir, hiçbir API anahtarı istemciye sızmaz

Bu hattaki her adım kapsamlı otomatik testlerle (core-api, Mobile BFF, Web
BFF, iOS `XCTest`, web `Vitest`) ve ilgili `docs/*.md` dosyalarıyla
belgelenmiştir — bkz. [docs/trip-optimizer.md](docs/trip-optimizer.md),
[docs/web-trip-optimizer.md](docs/web-trip-optimizer.md),
[docs/ios-trip-optimizer.md](docs/ios-trip-optimizer.md),
[docs/trip-assistant.md](docs/trip-assistant.md).

---

## Testler

```bash
# Core API
cd services/core-api && pytest tests/ -v
pytest tests/test_videos.py -v          # belirli bir test dosyası

# Mobile BFF / Web BFF
cd services/mobile-bff && pytest tests/ -v
cd services/web-bff    && pytest tests/ -v

# Web (Vitest)
cd web && npm test

# iOS (XCTest)
cd ios && xcodebuild -project TripClipApp.xcodeproj -scheme TripClipApp \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' test
```

---

## İletişim

**Süleyman Sardoğan**  
📧 sardogansuleyman04@gmail.com  
💼 [LinkedIn](https://www.linkedin.com/in/suleyman-sardogan-369875286/)  
🐙 [GitHub](https://github.com/suleymanssardogan)
