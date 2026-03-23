# 🔧 TripClip AI - Servisler ve Fonksiyonlar Detaylı

## 📚 Hızlı İçindekiler
- [1. Core-API Servisleri](#1-core-api-servisleri)
- [2. ML Modülleri ve Fonksiyonları](#2-ml-modülleri-ve-fonksiyonları)
- [3. API Endpointleri](#3-api-endpointleri)
- [4. Veri Modelleri](#4-veri-modelleri)
- [5. Gateway Servisleri](#5-gateway-servisleri)

---

## 1. Core-API Servisleri

### 🎬 VideoProcessingService (`services/video_processor.py`)

**Amaç**: Tüm ML pipeline'ını orkestralamak

**Ana Metodu**: `process_video(video_path: str) → dict`

**Adımlar**:
```python
1. extract_metadata()           # Video metadata çıkarma (duration, fps, resolution)
2. extract_frames()            # 0.5 FPS ile frame'leri çıkarma
3. create_thumbnail()          # İlk frame'den thumbnail
4. detect_objects()            # YOLOv8 ile nesne algılama
5. detect_landmarks()          # Google Vision ile landmark algılama
6. extract_ocr_text()          # EasyOCR ile metin çıkarma
7. transcribe_audio()          # Whisper ile ses transkripsiyonu
8. extract_locations_ner()     # NER ile konum çıkarma
9. enrich_locations()          # Nominatim ile geocoding
10. deduplicate_locations()    # Haversine ile kopya kaldırma
11. optimize_route()           # TSP ile rota optimizasyonu
12. save_results()             # Veritabanına kaydetme
```

**Çıktı** (Python Dictionary):
```python
{
    "video_id": 123,
    "metadata": {
        "filename": "istanbul.mp4",
        "duration": 300.0,
        "fps": 30,
        "resolution": "1920x1080",
        "thumbnail": "data:image/jpeg;base64,..."
    },
    "detections": {
        "objects": ["mosque", "car", "people"],
        "detection_summary": {"mosque": 12, "car": 8}
    },
    "landmarks": {
        "landmarks": ["Blue Mosque", "Hagia Sophia"],
        "count": 2
    },
    "transcription": {
        "text": "Merhaba Istanbul'dan...",
        "segments": [
            {"text": "Merhaba", "start": 0.0, "end": 1.5}
        ]
    },
    "ocr_results": {
        "texts": ["Welcome to Istanbul", "Price: 50₺"],
        "count": 2
    },
    "extracted_locations": ["Istanbul", "Blue Mosque", "Hagia Sophia"],
    "enriched_locations": [
        {
            "name": "Blue Mosque",
            "latitude": 41.0053,
            "longitude": 28.9770,
            "display_name": "Blue Mosque, Istanbul, Turkey"
        }
    ],
    "deduplicated_locations": [
        "Blue Mosque",
        "Hagia Sophia",
        "Topkapi Palace"
    ],
    "optimized_route": {
        "locations": ["Blue Mosque", "Hagia Sophia", "Topkapi Palace"],
        "distances": [0.0, 0.4, 1.2],
        "total_distance_km": 1.6
    },
    "processing_metrics": {
        "frames_extracted": 150,
        "processing_time_seconds": 45.3,
        "frames_per_second": 3.3
    }
}
```

---

## 2. ML Modülleri ve Fonksiyonları

### 👁️ Computer Vision (`ml/computer_vision.py`)

#### ObjectDetectionService (YOLOv8)

```python
class ObjectDetectionService:
    """YOLOv8 nano model kullanarak nesne algılama"""
    
    def detect_objects_in_frames(frames: List[np.ndarray]) → dict
        """
        Karelerdeki nesneleri algıla
        
        Args:
            frames: Video kareleri
            
        Returns:
            {
                "detections": [
                    {
                        "class": "person",
                        "confidence": 0.95,
                        "bbox": [10, 20, 100, 150]
                    }
                ],
                "summary": {"person": 15, "car": 3}
            }
        """
    
    def get_landmark_candidates() → List[str]
        """Ülkeler, şehirler, binalar filtrele"""
    
    def remove_duplicate_detections() → dict
        """Çerçeveler arasında tekrar eden deteksiyonları kaldır"""
```

#### LandmarkDetectionService (Google Vision API)

```python
class LandmarkDetectionService:
    """Google Cloud Vision API ile landmark algılama"""
    
    def detect_landmarks_in_frames(frames: List[np.ndarray]) → dict
        """
        Her 3. frame'de landmark algıla
        
        Returns:
            {
                "landmarks": [
                    {
                        "name": "Eiffel Tower",
                        "confidence": 0.98,
                        "latitude": 48.8584,
                        "longitude": 2.2945
                    }
                ]
            }
        """
    
    def detect_landmarks(image: np.ndarray) → List[dict]
        """Tek bir resimde landmark algıla"""
```

---

### 🎙️ Speech Recognition (`ml/speech_to_text.py`)

```python
class AudioProcessingService:
    """OpenAI Whisper kullanarak ses transkripsiyonu"""
    
    def extract_audio(video_path: str) → str
        """
        FFmpeg ile video'dan ses çıkar
        - Output: 16kHz WAV formatı
        """
    
    def transcribe_audio(audio_path: str) → dict
        """
        Türkçe ses transkripsiyonu
        
        Returns:
            {
                "text": "Merhaba Istanbul'dan günaydın",
                "segments": [
                    {
                        "id": 0,
                        "text": "Merhaba",
                        "start": 0.0,
                        "end": 1.5
                    }
                ]
            }
        """
    
    def process_video_audio(video_path: str) → dict
        """Completo: extract_audio() + transcribe_audio()"""
```

---

### 📄 OCR Service (`ml/ocr_service.py`)

```python
class OCRService:
    """EasyOCR ile metin algılama (Türkçe + İngilizce)"""
    
    def extract_text_from_frames(frames: List[np.ndarray]) → dict
        """
        Her 3. frame'den metin çıkar
        Güven skoru >%50 olan sonuçları döndür
        
        Returns:
            {
                "texts": [
                    {
                        "text": "Welcome to Istanbul",
                        "confidence": 0.92,
                        "bbox": [[10, 20], [100, 20], [100, 50], [10, 50]]
                    }
                ]
            }
        """
    
    def extract_text(image: np.ndarray) → List[dict]
        """Tek frame'den metin çıkar"""
```

---

### 🏷️ NER Service (`ml/ner_service.py`)

```python
class NERService:
    """HuggingFace Turkish BERT - Named Entity Recognition"""
    
    def extract_locations_from_transcript(transcript: str) → List[str]
        """
        Transkripsiyon metinden konum isimleri çıkar
        - Model: savasy/bert-base-turkish-ner-cased
        - Güven skoru >%60
        
        Returns:
            ["Istanbul", "Eiffel Tower", "Blue Mosque"]
        """
    
    def extract_entities(text: str) → dict
        """
        Tüm entity'leri çıkar (LOC, GPE, ORG)
        
        Returns:
            {
                "locations": [...],
                "organizations": [...],
                "persons": [...]
            }
        """
```

---

### 🗺️ Places Service (`ml/places_service.py`)

```python
class PlacesService:
    """Nominatim/OpenStreetMap Geocoding + Redis Cache"""
    
    def enrich_locations(locations: List[str]) → List[dict]
        """
        Konum isimlerini lat/lng koordinatlarına çevir
        
        Args:
            ["Istanbul", "Blue Mosque", "Hagia Sophia"]
            
        Returns:
            [
                {
                    "name": "Istanbul",
                    "latitude": 41.0082,
                    "longitude": 28.9784,
                    "display_name": "Istanbul, Turkey",
                    "place_id": 123456,
                    "osm_id": "7654321",
                    "importance": 0.8,
                    "address": {
                        "country": "Turkey",
                        "country_code": "tr"
                    }
                },
                ...
            ]
        """
    
    def search_place(place_name: str) → dict
        """Tekil konum arama ve geocoding"""
    
    def cache_results(duration: int = 604800)  # 7 gün
        """Redis'e cache et"""
```

---

### 🎯 Location Deduplicator (`ml/location_deduplicator.py`)

```python
class LocationDeduplicator:
    """Haversine formülü ile kopya konum kaldırma"""
    
    def deduplicate_locations(
        locations: List[dict],
        threshold_km: float = 5.0
    ) → dict
        """
        5km içinde olan konumları birleştir
        En yüksek 'importance' skoruna sahip olanı tut
        
        Returns:
            {
                "deduplicated": [
                    {
                        "name": "Blue Mosque",
                        "latitude": 41.0053,
                        "longitude": 28.9770,
                        "merged_count": 2,  # 2 konum birleştirildi
                        "importance": 0.95
                    }
                ],
                "removed_count": 3
            }
        """
    
    def haversine_distance(lat1, lon1, lat2, lon2) → float
        """İki nokta arasında mesafe (km)"""
    
    def get_location_summary(deduplicated_locations: List[dict]) → dict
        """Özet bilgi üret"""
```

---

### 🚗 Route Optimizer (`ml/route_optimizer.py`)

```python
class RouteOptimizer:
    """Traveling Salesman Problem (TSP) çözücü"""
    
    def optimize_route(locations: List[dict]) → dict
        """
        En kısa rotayı hesapla (komşu algoritması)
        
        Args:
            [
                {"name": "A", "latitude": 41.0, "longitude": 28.9},
                {"name": "B", "latitude": 41.1, "longitude": 29.0},
                {"name": "C", "latitude": 41.2, "longitude": 29.1}
            ]
        
        Returns:
            {
                "optimized_route": ["A", "B", "C"],
                "total_distance_km": 25.3,
                "route_segments": [
                    {"from": "A", "to": "B", "distance_km": 12.1},
                    {"from": "B", "to": "C", "distance_km": 13.2}
                ]
            }
        """
    
    def build_distance_matrix(locations: List[dict]) → np.ndarray
        """Tüm konum çiftleri arasında mesafe matrixi"""
    
    def nearest_neighbor_tsp(distance_matrix) → List[int]
        """Greedy heuristic: komşu algoritması"""
```

---

## 3. API Endpointleri

### CORE-API (Port 8000)

```python
@app.get("/")
async def root()
    """
    Hizmet durumu kontrolü
    
    Response:
    {
        "service": "Core API",
        "message": "Business logic layer",
        "status": "running"
    }
    """

@app.get("/health")
async def health_check()
    """
    Sağlık kontrolü
    
    Response:
    {
        "status": "healthy",
        "service": "core-api"
    }
    """

@app.post("/internal/videos/process")
async def process_video(file: UploadFile)
    """
    Video yükleme ve işleme başlatma
    
    - Dosya türü validasyonu (video/*)
    - Dosya boyutu: Max 500MB
    - Video'yu /app/uploads/videos/ klaöörüne kaydet
    - Veritabanında Video kaydı oluştur (status: UPLOADED)
    - Background task'a gönder
    
    Response:
    {
        "video_id": 123,
        "filename": "istanbul.mp4",
        "status": "PROCESSING",
        "message": "Video processing started"
    }
    """

@app.get("/internal/videos/{video_id}")
async def get_video_results(video_id: int)
    """
    İşlenen video'nun tüm sonuçlarını al
    
    Response:
    {
        "id": 123,
        "filename": "istanbul.mp4",
        "status": "COMPLETED",
        "created_at": "2026-03-22T10:00:00Z",
        "detections_count": 45,
        "landmarks_count": 8,
        "top_objects": ["mosque", "car", "person"],
        "extracted_texts": ["Welcome to Istanbul", "Price: 50₺"],
        "transcription": "Merhaba Istanbul'dan...",
        "extracted_locations": ["Istanbul", "Blue Mosque"],
        "enriched_locations": [...],
        "deduplicated_locations": [...],
        "optimized_route": [...],
        "processing_time": 45.3
    }
    """
```

### MOBILE-BFF (Port 8001)

```python
@app.post("/api/mobile/videos/upload")
async def upload_video(file: UploadFile)
    """
    Mobil uygulamadan video yükleme
    
    - Validasyon: MIME type (video/*)
    - Size limit: 100MB
    - Core-API'ya proxy (POST /internal/videos/process)
    - Basit response döndür
    
    Response:
    {
        "id": 123,
        "status": "PROCESSING",
        "message": "Video uploaded successfully"
    }
    """

@app.get("/api/mobile/videos/{video_id}")
async def get_video(video_id: int)
    """
    Mobil cihaz için optimize edilmiş sonuç
    
    - Core-API'ya proxy
    - Sadece gerekli alanları döndür
    - Minimize response
    """
```

---

## 4. Veri Modelleri

### User Model (SQLAlchemy ORM)

```python
class User(Base):
    __tablename__ = "users"
    
    id: int = Column(Integer, primary_key=True)
    email: str = Column(String(255), unique=True, nullable=False)
    username: str = Column(String(100), unique=True, nullable=False)
    hashed_password: str = Column(String(255), nullable=False)
    is_active: bool = Column(Boolean, default=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    videos = relationship("Video", back_populates="user")
    plans = relationship("Plan", back_populates="user")
```

### Video Model (SQLAlchemy ORM)

```python
class Video(Base):
    __tablename__ = "videos"
    
    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename: str = Column(String(255), nullable=False)
    file_path: str = Column(String(500), nullable=False)
    status: str = Column(String(50), default="UPLOADED")  # UPLOADED, PROCESSING, COMPLETED, FAILED
    duration: float = Column(Float)
    fps_processed: float = Column(Float)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    
    # AI Sonuçları (JSON formatında saklanır)
    detections_count: int = Column(Integer)
    landmarks_count: int = Column(Integer)
    top_objects: dict = Column(JSON)  # ["mosque", "car", "people"]
    
    extracted_texts: dict = Column(JSON)  # [{"text": "...", "confidence": 0.92}]
    vision_landmarks: dict = Column(JSON)  # Doğrudan Google Vision API sonuçları
    
    transcription: str = Column(Text)  # Ses metne çevirme
    transcription_segments: dict = Column(JSON)  # Segment bilgileri
    
    extracted_locations: list = Column(JSON)  # ["Istanbul", "Blue Mosque"]
    enriched_locations: dict = Column(JSON)  # Nominatim sonuçları
    deduplicated_locations: dict = Column(JSON)  # Deduplicated konum listesi
    location_summary: dict = Column(JSON)  # Özet bilgi
    
    optimized_route: dict = Column(JSON)  # TSP çözümü
    
    processing_time: float = Column(Float)
    
    # İlişkiler
    user = relationship("User", back_populates="videos")
    plans = relationship("Plan", back_populates="video")
```

### Plan Model (SQLAlchemy ORM)

```python
class Plan(Base):
    __tablename__ = "plans"
    
    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    video_id: int = Column(Integer, ForeignKey("videos.id"), nullable=False)
    
    title: str = Column(String(255), nullable=False)
    description: str = Column(Text)
    
    locations: dict = Column(JSON)  # İtinerary'nin konum listesi
    timeline: dict = Column(JSON)  # Gün bazlı plan {"day_1": [...], "day_2": [...]}
    budget: dict = Column(JSON)  # {"estimated_total": 5000, "currency": "USD"}
    
    is_public: bool = Column(Boolean, default=False)
    is_deleted: bool = Column(Boolean, default=False)
    
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = relationship("User", back_populates="plans")
    video = relationship("Video", back_populates="plans")
```

---

## 5. Gateway Servisleri

### Mobile BFF Yapısı (`services/mobile-bff/app/`)

```
mobile-bff/
├── main.py
│   └─ FastAPI app (Port 8001)
│
├── routes/
│   ├── __init__.py
│   └── videos.py
│       ├── POST /api/mobile/videos/upload
│       │   • Dosya validasyonu
│       │   • Core-API proxy
│       │   • Mobil-friendly response
│       │
│       └── GET /api/mobile/videos/{video_id}
│           • Sonuç alma
│           • Core-API proxy
│
└── services/
    └── core_api_client.py
        └─ Core-API'ya HTTP istek gönderme
```

### Web BFF Yapısı (`services/web-bff/app/`)

```
web-bff/
├── main.py
│   └─ FastAPI app (Port 8002)
│       • Health check
│       • CORS config
│
├── routes/
│   └─ (henüz geliştirilmedi)
│       • Dashboard endpoints
│       • Plan management
│       • Analytics
│
└── services/
    └─ (henüz geliştirilmedi)
```

---

## 📊 Data Flow Özeti

```
Client Request
    │
    ├─→ Mobile-BFF (8001)
    │   └─→ Validasyon (MIME, Size)
    │       └─→ Core-API
    │
    └─→ Web-BFF (8002)
        └─→ Core-API
        
Core-API (8000)
    │
    ├─→ Database Check/Create
    │
    ├─→ Background Task
    │   └─→ VideoProcessingService
    │       ├─→ Extract Frames & Audio
    │       ├─→ YOLOv8 Detection
    │       ├─→ Google Vision Landmarks
    │       ├─→ Whisper Transcription
    │       ├─→ EasyOCR Text
    │       ├─→ NER Location Extraction
    │       ├─→ Nominatim Geocoding
    │       ├─→ Location Deduplication
    │       └─→ Route Optimization
    │
    └─→ Update Database
        └─→ Return Results
```

---

## ✅ Özet

| Bileşen | Dosya | Amaç |
|---------|-------|------|
| VideoProcessingService | `services/video_processor.py` | 11-adım ML pipeline |
| ObjectDetectionService | `ml/computer_vision.py` | YOLOv8 nesne algılama |
| LandmarkDetectionService | `ml/computer_vision.py` | Google Vision landmark |
| AudioProcessingService | `ml/speech_to_text.py` | Whisper transkripsiyonu |
| OCRService | `ml/ocr_service.py` | EasyOCR metin çıkarma |
| NERService | `ml/ner_service.py` | Turkish BERT entity extraction |
| PlacesService | `ml/places_service.py` | Nominatim geocoding + Redis cache |
| LocationDeduplicator | `ml/location_deduplicator.py` | Haversine deduplication |
| RouteOptimizer | `ml/route_optimizer.py` | TSP rota optimizasyonu |
| User/Video/Plan Models | `models/*.py` | SQLAlchemy ORM |
| Core-API | `services/core-api/` | Ana business logic |
| Mobile-BFF | `services/mobile-bff/` | Mobil gateway |
| Web-BFF | `services/web-bff/` | Web gateway |

---

**Belge Tarihi**: 22 Mart 2026  
**Proje**: TripClip AI - AI-Powered Travel Video Analysis
