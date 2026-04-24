# TripClip AI

> Instagram seyahat videolarını yapay zeka ile analiz edip optimize edilmiş gezi planlarına dönüştüren uygulama.

[![Swift](https://img.shields.io/badge/Swift-5.9+-orange.svg)](https://swift.org)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docker.com)

**Öğrenci:** Süleyman Sardoğan  
**Kurum:** Fırat Üniversitesi — Yazılım Mühendisliği (3. Sınıf)  
**Dönem:** Mart – Haziran 2026 · 12 haftalık akademik proje  
**Durum:** Hafta 8/12 — Geliştirme tamamlandı, test aşaması

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
│  iOS App (Swift)          Web App (Next.js :3001)   │
└──────────┬───────────────────────────┬───────────────┘
           │                           │
           ▼                           ▼
   Mobile BFF :8001            Web BFF :8002
           │                           │
           └─────────────┬─────────────┘
                         ▼
                  Core API :8000
                  ┌──────────────────────────────┐
                  │         ML Pipeline          │
                  │  YOLOv8 → Whisper → EasyOCR │
                  │  Turkish BERT (NER)          │
                  │  Nominatim (Geocoding)       │
                  │  TSP Route Optimizer         │
                  │  Mistral RAG (Travel Tips)   │
                  └──────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   PostgreSQL          Redis           Qdrant
   (Ana DB)         (Cache+Progress) (Vector DB)
```

---

## Teknoloji Yığını

### Backend
| Katman | Teknoloji |
|--------|-----------|
| API Framework | FastAPI 0.109 |
| ORM | SQLAlchemy + PostgreSQL |
| Cache / Progress | Redis 7 |
| Vector DB | Qdrant |
| Computer Vision | YOLOv8 + Google Vision API |
| Speech-to-Text | OpenAI Whisper |
| OCR | EasyOCR |
| NER | Turkish BERT (HuggingFace) |
| Geocoding | Nominatim (OpenStreetMap) |
| Route | TSP Solver (Haversine) |
| Travel Tips | Mistral 7B (RAG) |
| Konteyner | Docker Compose (7 servis) |

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
│   │   │   ├── ml/             # ner_service.py, vision, ocr, audio, rag...
│   │   │   ├── models/         # User, Video, Plan (SQLAlchemy)
│   │   │   ├── routes/         # auth, videos (internal)
│   │   │   └── crud/
│   │   └── tests/              # test_auth.py, test_videos.py, test_health.py
│   ├── mobile-bff/             # iOS için BFF proxy (:8001)
│   │   └── app/routes/         # auth.py, videos.py
│   ├── web-bff/                # Web için BFF proxy (:8002)
│   │   └── app/routes/         # auth.py, plans.py, videos.py
│   └── ios/TripClipAI/         # Native iOS uygulaması
│       └── TripClipAI/
│           ├── Views/          # LoginView, HomeView, ResultsView, HistoryView
│           ├── Services/       # APIService, AuthService, PDFExport,
│           │                   # PersistenceService, TripShareCard
│           └── Assets.xcassets # AppIcon (1024x1024, dark, tinted)
└── web/                        # Next.js web uygulaması (:3001)
    └── src/app/
        ├── dashboard/          # Kullanıcı videoları + istatistikler
        ├── explore/            # Genel gezi planları keşfi
        ├── analyze/[id]/       # Video analiz sonuçları + progress polling
        ├── editor/[id]/        # Gezi planı düzenleyici
        └── share/[id]/         # Paylaşılabilir gezi sayfası
```

---

## Hızlı Başlangıç

### Gereksinimler
- Docker & Docker Compose
- Xcode 15+ (iOS için)
- Node.js 18+ (Web için)
- Google Vision API anahtarı

### 1. Backend & Servisler

```bash
# Repoyu klonla
git clone https://github.com/suleymanssardogan/TripClip-AI.git
cd TripClip-AI

# Ortam değişkenlerini ayarla
cp services/core-api/.env.example services/core-api/.env
# .env dosyasına GOOGLE_VISION_API_KEY ekle

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
cd services/ios/TripClipAI
open TripClipAI.xcodeproj
# Xcode'da scheme seç → Run (⌘R)
# Backend Docker'da çalışıyor olmalı
```

---

## ML Pipeline Akışı

```
Video Yükle
    │
    ├─▶ [1] Metadata çıkarma (FFprobe)
    ├─▶ [2] Kare örnekleme (FFmpeg, 1fps)
    ├─▶ [3] Paralel AI analizi
    │       ├─ YOLOv8 nesne tespiti
    │       ├─ Google Vision landmark tespiti
    │       └─ Whisper ses transkripsiyonu
    ├─▶ [4] Turkish BERT ile NER
    ├─▶ [5] EasyOCR + NER filtreleme
    ├─▶ [6] Nominatim geocoding
    ├─▶ [7] Overpass API POI sorgusu
    ├─▶ [8] Haversine deduplication
    ├─▶ [9] TSP rota optimizasyonu
    └─▶ [10] Mistral RAG seyahat ipuçları
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

---

## Web Uygulama Sayfaları

| Sayfa | Açıklama |
|-------|----------|
| `/dashboard` | Kullanıcının videoları, işlem durumu |
| `/explore` | Tüm tamamlanan gezi planları, şehir filtresi |
| `/analyze/[id]` | Video analiz sonuçları (harita + lokasyonlar + ipuçları) |
| `/editor/[id]` | Gezi planı timeline editörü (gerçek veri) |
| `/share/[id]` | Paylaşılabilir gezi sayfası, Google Maps entegrasyonu |

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
| 9–10 | Test, optimizasyon, entegrasyon | 🔄 |
| 11–12 | Deployment, dokümantasyon, sunum | ⏳ |

**Mevcut Durum: Hafta 8 — Core geliştirme tamamlandı**

### Tamamlanan Özellikler
- [x] 10 aşamalı ML video pipeline
- [x] Gerçek zamanlı işlem takibi (Redis + polling)
- [x] iOS uygulaması (auth, upload, harita, paylaşım, PDF)
- [x] Share Extension (Instagram → TripClip AI)
- [x] Web dashboard + analiz + editör + paylaşım sayfaları
- [x] JWT kimlik doğrulama
- [x] CoreData offline depolama
- [x] Docker altyapısı (7 servis)
- [x] Veritabanı index optimizasyonları

---

## Testler

```bash
# Backend testleri
cd services/core-api
pytest tests/ -v

# Belirli test
pytest tests/test_videos.py -v
```

---

## İletişim

**Süleyman Sardoğan**  
📧 sardogansuleyman04@gmail.com  
💼 [LinkedIn](https://www.linkedin.com/in/suleyman-sardogan-369875286/)  
🐙 [GitHub](https://github.com/suleymanssardogan)
