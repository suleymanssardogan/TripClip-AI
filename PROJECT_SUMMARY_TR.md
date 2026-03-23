# 🚀 TripClip AI - Proje Özeti & Mimarisi

## 📋 Proje Hakkında

**TripClip AI**, Instagram'da bulduğunuz seyahat videolarını otomatik olarak analiz ederek, optimize edilmiş bir seyahat planı oluşturan **AI-destekli mobil uygulamasıdır**.

- **Amaç**: Video → Konum Analizi → Optimized İtinerary
- **Teknoloji**: Python (FastAPI), Swift (iOS), AI/ML
- **Akademik**: Fırat Üniversitesi, Yazılım Mühendisliği, 12 hafta

---

## 🏗️ SİSTEM MİMARİSİ

```
┌──────────────────────────────────────────────────────────────┐
│                    İNSTAGRAM VİDEO                           │
└────────────────────────┬─────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        ▼                                  ▼
┌──────────────────┐            ┌──────────────────┐
│  İOS ŞMobil Uygul│            │  Web İnterface  │
│    (Swift)       │            │  (React/Vue)    │
└────────┬─────────┘            └────────┬────────┘
         │                               │
         └───────────┬───────────────────┘
                     │
        ┌────────────▼─────────────┐
        │   Mobile-BFF (Port 8001) │
        │    Web-BFF (Port 8002)   │
        │   (API Gateways)         │
        └────────────┬─────────────┘
                     │
        ┌────────────▼──────────────────────────┐
        │     CORE-API (Port 8000)              │
        │   (Business Logic & ML Pipeline)      │
        └────────────┬───────────────────────────┘
                     │
        ┌────────────┴────────────────────────────┐
        │                                         │
        ▼                                         ▼
┌───────────────────────────────┐    ┌──────────────────────┐
│   ML PROCESSING PIPELINE      │    │  DATABASE LAYER      │
├───────────────────────────────┤    ├──────────────────────┤
│ • YOLOv8 (Nesne Algılama)    │    │ • PostgreSQL         │
│ • Google Vision (Landmark)    │    │ • Redis (Cache)      │
│ • Whisper (Sesi Metin'e Çevir)│   │ • MongoDB (Backup)  │
│ • EasyOCR (Metin Çıkarma)    │    │                      │
│ • NER (Konum Çıkarma)        │    │ Models:              │
│ • Nominatim (Geocoding)      │    │ - User               │
│ • Location Deduplication      │    │ - Video              │
│ • Route Optimizer (TSP)       │    │ - Plan               │
└───────────────────────────────┘    └──────────────────────┘
```

---

## 🔧 BACKEND SERVİSLERİ

### 1️⃣ CORE-API (Port 8000)
**Ana hizmet** - Tüm AI/ML işlemlerini yönetir

**Dosya Yapısı**:
```
core-api/app/
├── main.py          # FastAPI uygulaması
├── models/          # Veritabanı modelleri (User, Video, Plan)
├── ml/              # AI/ML modülleri
├── services/        # İş mantığı servisleri
├── api/             # API endpointleri
└── core/            # Temel konfigürasyonlar
```

**API Endpointleri**:
```
GET  /                    → Hizmet durumu
GET  /health              → Sağlık kontrolü
POST /internal/videos/process    → Video yükleme
GET  /internal/videos/{id}       → Video sonuçlarını al
```

---

## 🧠 ML PIPELINE - 11 ADIM

### Video İşleme Adımları:

```
1. Video Yükleme
   ↓
2. FFmpeg ile Frame ve Ses Çıkarma
   │
   ├─→ 3. YOLOv8 Nesne Algılama
   │
   ├─→ 4. Google Vision Landmark Algılama
   │
   ├─→ 5. OpenAI Whisper → Ses Transkripsiyonu
   │
   ├─→ 6. EasyOCR → Metni Çıkarma
   │
   ├─→ 7. NER (Named Entity Recognition) → Konum Çıkarma
   │
   ├─→ 8. Nominatim Geocoding → Koordinat Belirleme
   │
   ├─→ 9. Location Deduplicator → Kopya Konum Kaldırma
   │
   └─→ 10. Route Optimizer (TSP) → En İyi Rota Bulma
   
   ↓
11. Sonuçları Veritabanına Kaydet
```

---

## 📦 ML MODÜLLERI (app/ml/)

### Computer Vision (`computer_vision.py`)
```python
• ObjectDetectionService (YOLOv8)
  - Karelerdeki nesneleri algılar
  - Güven skoru >%40
  
• LandmarkDetectionService (Google Vision API)
  - Ünlü yapıları/yerleri tanır
  - Koordinat bilgisi döndürür
```

### Speech Recognition (`speech_to_text.py`)
```python
• AudioProcessingService (Whisper)
  - Video sesini metne çevirir
  - Türkçe dil desteği
  - Segment bilgisi ile döndürür
```

### OCR (`ocr_service.py`)
```python
• OCRService (EasyOCR)
  - Karelerdeki yazıları tanır
  - Türkçe + İngilizce desteği
  - Güven skoru >%50
```

### NER Service (`ner_service.py`)
```python
• NERService (HuggingFace Turkish BERT)
  - Metin içinde konum, kişi, kuruluş adlarını bulur
  - Model: savasy/bert-base-turkish-ner-cased
  - Güven skoru >%60
```

### Places Service (`places_service.py`)
```python
• PlacesService (Nominatim/OpenStreetMap)
  - Konum adını lat/lng'ye çevirir
  - Redis cache (7 gün)
  - Rate limit: 1 istek/saniye
```

### Location Deduplicator (`location_deduplicator.py`)
```python
• LocationDeduplicator
  - Haversine formülü ile mesafe hesaplar
  - Default: 5km içinde kopya siler
  - En önemli lokasyonu tutar
```

### Route Optimizer (`route_optimizer.py`)
```python
• RouteOptimizer (TSP Çözücü)
  - Komşu algoritması ile en kısa rotayı bulur
  - Koordinat mesafeleri hesaplar
  - Sıralanmış konumları döndürür
```

---

## 💾 VERİTABANI MODELLERİ

### User Modeli
```python
id: Integer (Primary Key)
email: String (Unique)
username: String (Unique)
hashed_password: String
is_active: Boolean
created_at: DateTime
updated_at: DateTime
```

### Video Modeli
```python
id: Integer (Primary Key)
user_id: Integer (Foreign Key)
filename: String
file_path: String
status: Enum (UPLOADED, PROCESSING, COMPLETED, FAILED)
duration: Float
fps_processed: Float
created_at: DateTime

# AI Sonuçları (JSON formatında):
detections_count: Integer
landmarks_count: Integer
top_objects: JSON
extracted_texts: JSON
transcription: String
extracted_locations: JSON
enriched_locations: JSON
deduplicated_locations: JSON
location_summary: JSON
processing_time: Float
```

### Plan Modeli
```python
id: Integer (Primary Key)
user_id: Integer (Foreign Key)
video_id: Integer (Foreign Key)
title: String
locations: JSON (Konum listesi)
timeline: JSON (Gün bazlı itinerary)
budget: JSON (Bütçe bilgisi)
is_public: Boolean
created_at: DateTime
updated_at: DateTime
```

---

## 🔗 API GATEWAY SERVİSLERİ

### Mobile BFF (Port 8001)
```python
# Video yükleme
POST /api/mobile/videos/upload
- Validasyon: MIME type, Max 100MB
- Core-API'ya ilet
- Basit response: {id, status, message}

# Sonuçları getir
GET /api/mobile/videos/{video_id}
- Core-API'dan tüm sonuçları al
```

### Web BFF (Port 8002)
```python
# Şu an yer tutucu
- Health check: GET /health
- Routes henüz gelecek
```

---

## 🐳 ALTYAPI & DEPLOYMENT

### Docker Compose Servisleri
```yaml
postgresql:   Port 5432  # Veritabanı
redis:        Port 6379  # Cache
mongodb:      Port 27017 # Doküman DB (opsiyonel)
core-api:     Port 8000  # Ana API
mobile-bff:   Port 8001  # Mobil gateway
web-bff:      Port 8002  # Web gateway
```

### Stack
- **Framework**: FastAPI (Python 3.11+)
- **ORM**: SQLAlchemy
- **Veritabanı**: PostgreSQL + Redis + MongoDB
- **Container**: Docker & Docker Compose
- **Video İşleme**: FFmpeg
- **Job Queue**: Celery (kurulu ama aktif değil)

---

## ✅ TAMAMLANAN BÖLÜMLERİ

- ✅ Tüm ML servisleri (Computer Vision, NLP, OCR, NER, Route Optimizer)
- ✅ Video işleme orkestratörü
- ✅ Veritabanı modelleri ve ORM
- ✅ Core-API endpointleri
- ✅ Mobile/Web BFF temel yapısı
- ✅ Docker deployment
- ✅ Redis cache entegrasyonu

---

## ⚠️ YAPILACAK BÖLÜMLERİ

- ⚠️ İOS uygulaması (Swift/SwiftUI)
- ⚠️ Web frontend'i
- ⚠️ Kimlik doğrulama (Auth)
- ⚠️ Celery task queue aktivasyonu
- ⚠️ Embedding servisi (Vector DB)
- ⚠️ Tam API dokümantasyonu

---

## 📊 KÖŞELİ METRÎKLER

```
Video İşleme:
- Frame Extraction: 0.5 FPS (her 2 saniye)
- YOLOv8: Confidence >%40
- Google Vision: Sampling her 3. frame (API maliyet)
- Whisper: Tüm ses
- EasyOCR: Sampling her 3. frame
- NER: Transkripsiyondan
- Nominatim: Cache hits ile optimize
- Deduplication: 5km eşik
```

---

## 🎯 PRoje Hedefi

Instagram'da paylaşılan seyahat videolarını otomatik olarak analiz ederek:
1. Ziyaret edilen yerleri tanıt
2. Konut, restoran, aktiviteleri belirle
3. En iyi rotayı hesapla
4. Takvim, harita, PDF olarak export et
5. Bütçe tahminleri sağla

**Sonuç**: Zaman kaybetmeden, organize seyahat planı!

---

*Belge oluşturma tarihi: 22 Mart 2026*
