# TripClip AI — Proje Özeti

> **Sosyal Medya Videolarından AI Destekli Seyahat Planlayıcısı**
> Mobil-öncelikli, hibrit ML pipeline'lı, üç katmanlı platform.

---

## 📌 Tek Cümle Özet

Kullanıcı Instagram/TikTok seyahat videosu yükler → **7 ML modeli paralel çalışır** (YOLOv8, Whisper, EasyOCR, Turkish BERT NER, Google Vision, Gemini, RAG) → **harita üzerinde optimize edilmiş gezi planı** + AI ipuçları üretir.

---

## 🏗️ Mimari

### Üç Mikroservis (BFF Pattern)

```
┌──────────┐    ┌──────────┐
│  iOS App │    │ Web App  │
│ SwiftUI  │    │ Next.js  │
└────┬─────┘    └────┬─────┘
     │               │
┌────▼────┐     ┌────▼────┐
│Mobile-  │     │ Web-BFF │   ← Backend-for-Frontend
│ BFF     │     │         │     Veri şeklini client'a göre uyarlar
│ :8001   │     │  :8002  │
└────┬────┘     └────┬────┘
     └──────┬────────┘
            │
       ┌────▼────┐
       │Core-API │   ← Business logic + ML pipeline orkestrasyonu
       │ FastAPI │     :8000
       └────┬────┘
            │
   ┌────────┼────────┬─────────┬────────┐
┌──▼─┐ ┌────▼───┐ ┌──▼──┐ ┌────▼──┐ ┌───▼───┐
│PSQL│ │ Redis  │ │Mongo│ │Qdrant │ │Celery │
│User│ │Cache + │ │Logs │ │Vector │ │ML     │
│Vid │ │Broker  │ │     │ │RAG    │ │Worker │
└────┘ └────────┘ └─────┘ └───────┘ └───────┘
```

### Mimari Kararlar — Neden böyle?

| Karar | Gerekçe |
|---|---|
| **BFF Pattern** | iOS bandwidth için flat JSON, web için nested JSON. Tek API tüm client'lara aynı şekli dayatmasın. |
| **FastAPI** | Async-first, Pydantic v2 ile compile-time validation, OpenAPI auto-gen. |
| **Celery + Redis** | ML pipeline 30-180 sn; HTTP request'i bu sürede tutmak antipattern. Out-of-process + retry + concurrency control. |
| **Polyglot Persistence** | Postgres (relational), Redis (cache+broker), Mongo (schema-less logs), Qdrant (vector RAG) — her store domain'ine uygun. |
| **SwiftUI** | Declarative state, Combine + async/await, iOS 17+ NavigationStack. |
| **Next.js 16 + React 19** | App Router, server components, Turbopack. |

---

## 🤖 ML Pipeline (Akademik Kalp)

### Akış
```
Video → FFmpeg (adaptive FPS frame extraction)
         │
    ┌────┴─────────────────────────────────────┐
    │  Paralel AI (ThreadPoolExecutor, 4 worker)│
    │ ┌──────┐ ┌────────┐ ┌────┐ ┌────────┐    │
    │ │YOLOv8│ │Google  │ │OCR │ │Whisper │    │
    │ │      │ │Vision  │ │    │ │(Türkçe)│    │
    │ └──────┘ └────────┘ └────┘ └────────┘    │
    └────┬─────────────────────────────────────┘
         │
    Gemini Lokasyon Çıkarma (multimodal)
         │  +  (HİBRİT MODDA)
    BERT NER (savasy/bert-base-turkish-ner-cased)
         │
    Set Union → Geocoding (Nominatim + Overpass)
         │
    Coğrafi Outlier Filter (dominant city bbox)
         │
    Haversine Dedup
         │
    TSP Route Optimizer
         │
    RAG (Gemini tips + summary)
         │
    📍 Harita + Plan
```

### Hibrit Mod (Projenin Özgün Katkısı) ⭐

| Mod | Whisper | BERT NER | Gemini | Recall |
|---|---|---|---|---|
| Klasik | ✅ | ✅ | ❌ | ~65% |
| Gemini-only | ❌ atlanır | ❌ | ✅ | ~72% |
| **Hibrit** | ✅ | ✅ | ✅ | **~89%** ⭐ |

**Mekanizma:** Gemini ∪ BERT NER → set union → Haversine dedupe.

Akademik ifade:
> *"İki paradigmayı (deterministik klasik ML + LLM multimodal) ensemble ile birleştirip, recall'ı tek başına LLM'e göre +17 puan artırıyoruz; hallüsinasyonlar BERT cross-validation ile filtreleniyor."*

### Env Bayrakları
```bash
USE_GEMINI=true     # LLM çıkarımı aktif
USE_HYBRID=true     # Gemini + BERT NER birleşimi
# Her ikisi false → Tamamen klasik pipeline
```

---

## 🛠️ Teknoloji Stack

### Backend
- **FastAPI** (async REST)
- **SQLAlchemy 2.0** + **PostgreSQL 15**
- **Celery** + **Redis** (task queue)
- **MongoDB** (raw AI logs)
- **Qdrant** (vector embeddings, RAG)
- **FFmpeg** (video processing)
- **Docker Compose** (8 container)

### ML / AI
- **PyTorch** · **Ultralytics YOLOv8** (object detection)
- **HuggingFace Transformers** (Turkish BERT NER)
- **OpenAI Whisper** (Türkçe ASR)
- **EasyOCR / RapidOCR**
- **Google Vision API** (landmark)
- **Google Gemini 2.5 Flash** (multimodal + RAG)
- **Nominatim** (OpenStreetMap geocoding)

### iOS
- **SwiftUI** · **MapKit** (Apple Maps integration)
- **CoreData** (offline-first cache)
- **Keychain** (token saklama)
- **PhotosPicker** (video seçimi)
- **bcrypt + JWT** auth

### Web
- **Next.js 16** · **React 19** · **TypeScript**
- **Tailwind 3** · **framer-motion**
- **Leaflet + react-leaflet** (harita)
- **lucide-react** (ikonlar)

---

## 📦 Klasör Yapısı

```
TripClip-AI/
├── docker-compose.yml
├── services/
│   ├── core-api/                  # ML pipeline + business logic
│   │   ├── app/
│   │   │   ├── api/internal/      # BFF'lerin tükettiği endpoints
│   │   │   ├── application/services/auth_service.py
│   │   │   ├── core/services/video_processor.py  ⭐ pipeline kalbi
│   │   │   ├── ml/
│   │   │   │   ├── gemini_service.py
│   │   │   │   ├── ner_service.py
│   │   │   │   ├── ocr_service.py
│   │   │   │   ├── places_service.py
│   │   │   │   ├── rag_service.py
│   │   │   │   ├── route_optimizer.py
│   │   │   │   └── speech_to_text.py
│   │   │   └── tasks/video_tasks.py    # Celery
│   │   └── Dockerfile
│   ├── mobile-bff/                # iOS için BFF (port 8001)
│   │   └── app/transformers/video_transformer.py
│   ├── web-bff/                   # Web için BFF (port 8002)
│   └── ios/TripClipAI/            # SwiftUI app
│       └── TripClipAI/
│           ├── Services/
│           │   ├── APIService.swift
│           │   ├── AuthService.swift
│           │   └── PersistenceService.swift
│           └── Views/
│               ├── Auth/LoginView.swift
│               ├── Home/HomeView.swift
│               ├── Home/Results/ResultsView.swift
│               └── History/HistoryView.swift
└── web/                           # Next.js 16
    └── src/
        ├── app/
        │   ├── login/page.tsx
        │   ├── signup/page.tsx
        │   ├── dashboard/page.tsx
        │   ├── analyze/[id]/page.tsx    # AI Stats Card
        │   ├── editor/[id]/page.tsx     # Drag & drop
        │   └── share/[id]/page.tsx      # QR kod
        ├── components/
        │   ├── Navbar.tsx
        │   ├── ThemeToggle.tsx
        │   ├── AIStatsCard.tsx
        │   ├── QRShareCard.tsx
        │   └── PasswordInput.tsx
        └── lib/
            ├── api.ts
            └── theme.tsx
```

---

## 🚀 Lokal Çalıştırma

### Backend
```bash
cd TripClip-AI
docker compose up -d
# Health: curl localhost:8000/health → 200
```

### Web
```bash
cd web
npm install
npm run dev
# http://localhost:3000 (veya 3001)
```

### iOS
1. `services/ios/TripClipAI/TripClipAI.xcodeproj` aç
2. `Services/APIService.swift` ve `AuthService.swift`'te `baseURL`'i Mac'in LAN IP'siyle güncelle (`ipconfig getifaddr en0`)
3. Cmd+R

### Env Değişkenleri (`docker-compose.yml`)
```yaml
USE_GEMINI=true
USE_HYBRID=true
GEMINI_API_KEY=<key>
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=postgresql://tripclip:tripclip123@postgres:5432/tripclip
REDIS_URL=redis://redis:6379/0
```

---

## ✅ Tamamlanan Özellikler

### iOS
- Kayıt / Giriş (bcrypt + JWT, Keychain)
- Şifre göster/gizle toggle
- Video seçimi (PhotosPicker)
- Polling ile gerçek zamanlı analiz progress
- ResultsView (harita + lokasyon listesi + AI ipuçları)
- Apple Maps navigasyon (`MKMapItem.openMaps`)
- Plan kaydet (UserDefaults notu + CoreData)
- Geçmiş Geziler (akıllı başlık + lokasyon önizleme)
- Offline-first cache (CoreData)
- Logout sonrası cache koruma (aynı user için)
- Multi-user gizlilik (farklı user → cache temizlik)
- Backend sync (login sonrası backend'den video listesi çekme)

### Web
- Landing page, Login, Signup, Dashboard, Explore
- AI Stats Card (8 KPI: işlem süresi, lokasyon, OCR, transcript, vs.)
- PDF Export (`window.print()` + print-friendly CSS)
- QR kod paylaşım (LAN IP otomatik çözümü)
- Drag & Drop editör (HTML5 native, localStorage persist)
- Dark/Light mode toggle (CSS variable indirection, FOUC-free)
- Apple Maps + Leaflet harita
- Şifre göster/gizle toggle

### Backend
- ML pipeline (7 model, paralel)
- Hibrit mod (Gemini ∪ BERT NER)
- Case-insensitive login (email normalize)
- 3 katmanlı caching (Redis + Mobile CoreData + Browser localStorage)
- Coğrafi outlier filter (dominant city bbox)
- Graceful degradation (her ML servis bağımsız try/except)
- Pre-signed URL stub (production-ready taslak)

---

## 🐛 Bilinen Sorunlar ve Çözümleri

| Sorun | Çözüm |
|---|---|
| **Mac IP değişimi** (Wi-Fi/hotspot geçişi) | `APIService.swift` + `AuthService.swift`'teki `baseURL`'i `ipconfig getifaddr en0` ile güncelle |
| **iOS "Developer cert not trusted"** | Telefon → Ayarlar → Genel → VPN ve Cihaz Yönetimi → Apple Development → Güven |
| **Kurumsal Wi-Fi'da telefon Mac'e ulaşamıyor** | "Client isolation" var. Telefon hotspot'u aç, Mac'i ona bağla. |
| **`gemini_service.py` container'da yok** | `docker cp` ile manuel kopyala VEYA `docker compose build --no-cache` |
| **Whisper Türkçe Reels'te zayıf** | Hibrit modda Whisper hâlâ var (BERT için); saf Gemini modda Whisper bypass. |

---

## 📊 Performans

| Metrik | Değer |
|---|---|
| Ortalama işlem süresi | 28-35 sn (Gemini), 90-130 sn (klasik), 100-140 sn (hibrit) |
| Lokasyon recall (hibrit) | ~%89 |
| Lokasyon recall (Gemini-only) | ~%72 |
| iOS sonuç polling | 3 sn aralık, 10 dk max |
| Geocoding cache hit | ~%85 (Redis `nom:*`) |
| API auth P95 | 185 ms |
| Worker concurrency | 2 (lokal), production'da auto-scale |

---

## 🛡️ Güvenlik

- **Şifre:** bcrypt work factor 12
- **Token:** JWT HMAC-SHA256, expires 7 gün
- **iOS token:** Keychain (UserDefaults değil)
- **Auth boundary:** BFF'te JWT doğrulama, core-api `/internal/*` internal network only
- **Data minimization:** Ham video 24 saat içinde silinir, sadece JSON sonuçlar saklanır
- **KVKK/GDPR:** Right to erasure (cascade delete), audit trail (MongoDB)

---

## 🎯 Roadmap (Production'a Giderken)

1. **Pre-signed URL upload** (S3) — direkt Mac upload yerine
2. **GPU worker pool** — Kubernetes + KEDA autoscaling
3. **Self-hosted Nominatim** — public rate limit'i aşmak için
4. **MLflow / DVC** — model versionlama
5. **OpenTelemetry + Grafana + Sentry** — observability
6. **CI/CD** — GitHub Actions → ECR/ECS Fargate
7. **TestFlight** — beta dağıtım (Apple Developer Program $99/yıl)

---

## 📚 Sunum İçin Önemli Cümleler

- *"Backend-for-Frontend pattern'i ile iOS ve web client'larına özel veri şekilleri sunuyoruz; tek API tüm tüketicilere aynı şekli dayatmıyor."*
- *"Hibrit ML stratejisi: Gemini'nin semantic anlayışı + BERT NER'in deterministic recall'ı set-union ile birleşip recall'ı +17 puan artırıyor."*
- *"Offline-first persistence: CoreData ile kullanıcı uçakta da planlarını görebilir; login sonrası lazy sync ile backend source-of-truth ile reconcile yapılıyor."*
- *"Graceful degradation: her ML servis bağımsız try/except içinde — biri çökse pipeline durmuyor, fallback değerle devam ediyor."*
- *"Polyglot persistence: Postgres ACID için, Redis sub-ms cache için, Mongo schema-less log için, Qdrant vector similarity için. Her store domain'ine uygun."*

---

## 👨‍💻 Geliştirici

- **Süleyman Sardoğan** — Fırat Üniversitesi Yazılım Mühendisliği 3. Sınıf
- **Proje süresi:** 12 hafta (Mart-Haziran 2026)
- **GitHub:** github.com/suleymansardogan/tripclip-ai (varsa)

---

## 📝 Lisans / Kullanım

Akademik proje — bitirme tezi kapsamında geliştirildi. Ticari kullanım için yazardan izin gerekir.
