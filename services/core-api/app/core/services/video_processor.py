"""
TripClip AI — Video Processing Pipeline (Graceful Degradation).

Her AI servisi bağımsız çalışır. Biri başarısız olursa:
  - Hata loglanır
  - Fallback değer kullanılır
  - Diğer servisler etkilenmez
  - Pipeline tamamlanır

Degradasyon raporu her işlem sonunda loglanır:
  ✅ OCR        — 14 metin bulundu
  ⚠️  Vision    — FALLBACK (quota aşıldı: 429)
  ✅ Whisper    — 312 karakter transkript
  ✅ YOLO       — 47 nesne
"""

from __future__ import annotations

import logging
import os
import time
import json as _json
import re as _re
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.core.redis import set_progress

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# ServiceResult — Her AI servisinin çıktısını taşır
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ServiceResult:
    """Bir AI servisinin sonucunu ve durumunu tutar."""
    name:          str
    data:          Any
    success:       bool
    fallback_used: bool = False
    error:         Optional[str] = None
    duration_s:    float = 0.0

    @property
    def status_icon(self) -> str:
        if self.success and not self.fallback_used:
            return "✅"
        if self.fallback_used:
            return "⚠️ "
        return "❌"

    def __str__(self) -> str:
        dur = f"{self.duration_s:.1f}s"
        if self.fallback_used:
            return f"{self.status_icon} {self.name:<12} — FALLBACK ({self.error}) [{dur}]"
        if self.success:
            return f"{self.status_icon} {self.name:<12} — OK [{dur}]"
        return f"{self.status_icon} {self.name:<12} — HATA: {self.error} [{dur}]"


def _safe_run(
    name: str,
    fn: Callable,
    fallback: Any,
    *,
    timeout: Optional[float] = None,
    future: Optional[Future] = None,
) -> ServiceResult:
    """
    Bir fonksiyonu veya Future'ı güvenli şekilde çalıştırır.

    Hata durumunda:
      - Exception loglanır
      - fallback değer döner
      - Pipeline durmaz

    Args:
        name:    Servis adı (log ve rapor için)
        fn:      Çağrılacak fonksiyon (future=None ise)
        fallback: Hata durumunda kullanılacak değer
        timeout: future.result() için timeout (saniye)
        future:  Zaten submit edilmiş ThreadPoolExecutor future'ı
    """
    t0 = time.perf_counter()
    try:
        if future is not None:
            data = future.result(timeout=timeout)
        else:
            data = fn()

        dur = time.perf_counter() - t0
        return ServiceResult(name=name, data=data, success=True, duration_s=dur)

    except TimeoutError:
        dur = time.perf_counter() - t0
        error = f"timeout ({timeout}s)"
        logger.warning("⏰ %s zaman aşımı — fallback kullanılıyor", name)
        return ServiceResult(name=name, data=fallback, success=False,
                             fallback_used=True, error=error, duration_s=dur)

    except Exception as exc:
        dur = time.perf_counter() - t0
        error = type(exc).__name__ + ": " + str(exc)[:120]
        logger.warning("⚠️  %s başarısız — fallback kullanılıyor | %s", name, error)
        return ServiceResult(name=name, data=fallback, success=False,
                             fallback_used=True, error=error, duration_s=dur)


def _log_degradation_report(results: List[ServiceResult], video_id: int) -> None:
    """İşlem sonunda hangi servislerin çalıştığını/düştüğünü loglar."""
    lines = [f"\n{'─'*55}", f"  Degradasyon Raporu — video_id={video_id}", f"{'─'*55}"]
    for r in results:
        lines.append(f"  {r}")

    failed = [r for r in results if not r.success]
    if failed:
        lines.append(f"\n  ⚠️  {len(failed)} servis fallback kullandı — plan eksik veriyle tamamlandı.")
    else:
        lines.append(f"\n  🎉 Tüm servisler başarıyla tamamlandı.")
    lines.append(f"{'─'*55}")
    logger.info("\n".join(lines))


# ─────────────────────────────────────────────────────────────────────────────
# VideoProcessingService
# ─────────────────────────────────────────────────────────────────────────────

class VideoProcessingService:
    """
    Video işleme pipeline'ı.

    Her AI aşaması bağımsız hata toleransına sahiptir.
    Bir servis çökerse sadece o servisin verisi eksik olur;
    pipeline tamamlanmaya devam eder.
    """

    @staticmethod
    def _try_init(label: str, factory: Callable[[], Any]) -> Any:
        """
        Bir ML servisini başlatır; başarısız olursa (örn. model ağırlığı
        indirilemedi, ağ hatası, disk dolu) None döner ve SADECE o servisi
        etkiler. Eskiden tüm __init__ tek bir try/except ImportError içindeydi
        — bir servisin kurulum hatası (ImportError DIŞINDA herhangi bir istisna)
        yakalanmadan dışarı sızıp VideoProcessingService'in tamamen
        oluşturulamamasına, dolayısıyla pipeline'ın "graceful degradation"
        yerine tümden çökmesine yol açıyordu.
        """
        try:
            return factory()
        except Exception as exc:
            logger.warning("⚠️  %s başlatılamadı — bu aşama fallback ile devam edecek: %s", label, exc)
            return None

    def __init__(self):
        self.frames_dir = Path("/app/uploads/frames")
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.base_fps = 0.25

        # Modül importları — test ortamında (torch/ultralytics vb. kurulu değilse)
        # ImportError fırlatır; bu durumda ML pipeline'ın TAMAMI kullanılamaz
        # (process_video en başta RuntimeError fırlatır, bkz. aşağı).
        try:
            import ffmpeg as _ffmpeg_module  # noqa: F401
            from app.ml.computer_vision import ObjectDetectionService, LandmarkDetectionService
            from app.ml.ocr_service import OCRService
            from app.ml.speech_to_text import AudioProcessingService
            from app.ml.ner_service import NERService
            from app.ml.places_service import PlacesService
            from app.ml.location_deduplicator import LocationDeduplicator
            from app.ml.qdrant_service import QdrantService
            from app.ml.route_optimizer import RouteOptimizer
            from app.ml.rag_service import RAGService
        except ImportError as e:
            logger.warning("ML servisleri yüklenemedi (test modu?): %s", e)
            self._ml_available = False
            return

        # Her servis bağımsız başlatılır — biri (örn. YOLO ağırlığı indirilemedi)
        # başarısız olsa bile diğerleri kurulmaya devam eder. Pipeline
        # çalışırken bu servisin sonucu None üzerinden fallback'e düşer
        # (bkz. _safe_run çağrıları), tüm işlem çökmez.
        self.detector        = self._try_init("YOLO/ObjectDetection", ObjectDetectionService)
        self.vision_detector = self._try_init("Landmark/Vision",      LandmarkDetectionService)
        self.ocr             = self._try_init("OCR",                  OCRService)
        self.audio_processor = self._try_init("Whisper",               AudioProcessingService)
        self.ner              = self._try_init("NER",                  NERService)
        self.places           = self._try_init("Places/Nominatim",     PlacesService)
        self.deduplicator     = self._try_init(
            "LocationDeduplicator", lambda: LocationDeduplicator(distance_threshold_km=2.0)
        )
        self.qdrant           = self._try_init("Qdrant",        QdrantService)
        self.route_optimizer  = self._try_init("RouteOptimizer", RouteOptimizer)
        self.rag              = self._try_init("RAG",           RAGService)
        self._ml_available    = True

        # ── Gemini / Hibrit modu (opsiyonel) ──────────────────────────────
        # USE_GEMINI=true  → Sadece Gemini (NER + Vision + RAG yerine tek API)
        # USE_HYBRID=true  → Gemini + klasik BERT NER paralel, sonuçlar birleştirilir
        # Her ikisi false → Tamamen klasik ML pipeline (BERT, YOLO, Whisper, RAG)
        # Nominatim geocoding + outlier filter + TSP her durumda çalışır
        self._use_hybrid = os.getenv("USE_HYBRID", "false").lower() == "true"
        self._use_gemini = self._use_hybrid or os.getenv("USE_GEMINI", "false").lower() == "true"

        if self._use_gemini:
            from app.ml.gemini_service import GeminiService
            self.gemini = self._try_init("Gemini", GeminiService)
            mode = "🔀 HİBRİT" if self._use_hybrid else "🤖 GEMINI"
            logger.info("%s modu AKTİF (model=%s)",
                        mode, os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
        else:
            self.gemini = None
            logger.info("🔧 Klasik pipeline modu (Gemini devre dışı)")

    # ─────────────────────────────────────────────────────────────────────────
    # Ana pipeline
    # ─────────────────────────────────────────────────────────────────────────

    def process_video(self, video_path: str, video_id: int) -> Dict:
        """
        Video → AI pipeline → sonuç dict.

        Graceful degradation garantisi:
          Her AI aşaması try/except ile sarılmıştır.
          Herhangi bir hata → fallback değer, işlem devam eder.
        """
        if not self._ml_available:
            raise RuntimeError("ML servisleri mevcut değil — Docker ortamında çalıştırın")

        import ffmpeg  # noqa: F401 — Docker'da her zaman mevcut
        start_time = time.perf_counter()
        degradation_log: List[ServiceResult] = []

        logger.info("🎬 Video işleme başlıyor | video_id=%s | path=%s", video_id, video_path)

        # ── 1. Metadata ───────────────────────────────────────────────────────
        set_progress(video_id, "metadata", 5)
        metadata = self._get_metadata(video_path)     # kritik — hata fırlatır
        logger.info("Metadata: %s", metadata)

        # ── 2. Frame extraction ──────────────────────────────────────────────
        frame_dir = self.frames_dir / str(video_id)
        duration  = metadata["duration"]
        adaptive_fps = (
            2.0 if duration < 20  else
            1.0 if duration < 60  else
            0.5 if duration < 120 else
            0.25
        )
        set_progress(video_id, "frames", 10)
        frames    = self._extract_frames(video_path, frame_dir, fps=adaptive_fps)
        thumbnail = self._create_thumbnail(frames[0] if frames else None)
        t_frames  = time.perf_counter()
        logger.info("🖼  %d frame @ %.2f fps | %.1fs",
                    len(frames), adaptive_fps, t_frames - start_time)

        # ─────────────────────────────────────────────────────────────────────
        # ── 3. PARALEL AI AŞAMASI ────────────────────────────────────────────
        #
        #   YOLO      → GPU/CPU  (nesne tespiti)
        #   Vision    → Google API (landmark tespiti)
        #   OCR       → CPU     (metin çıkarma)
        #   Whisper   → CPU     (ses → metin)
        #
        #   Her servis bağımsız try/except içinde — biri düşse diğerleri devam eder.
        # ─────────────────────────────────────────────────────────────────────
        set_progress(video_id, "ai_parallel", 20)
        # Hibrit modda Whisper çalışır (BERT NER için transkript şart)
        # Saf Gemini modunda Whisper atlanır (Gemini frame'lerden direkt okur)
        run_whisper = (not self._use_gemini) or self._use_hybrid

        if self._use_hybrid:
            logger.info("🚀 Paralel AI başlıyor (YOLO + Vision + OCR + Whisper) — HİBRİT modu")
        elif self._use_gemini:
            logger.info("🚀 Paralel AI başlıyor (YOLO + Vision + OCR) — Whisper atlanıyor [Gemini modu]")
        else:
            logger.info("🚀 Paralel AI başlıyor (YOLO + Vision + OCR + Whisper) — Klasik mod")

        # NOT: self.detector/vision_detector/ocr/audio_processor init sırasında
        # başarısız olduysa None olabilir (bkz. _try_init). Çağrıyı lambda içine
        # sarmak, None.<method> AttributeError'ının submit() anında (thread pool
        # dışında, yakalanmadan) değil; future çalışırken (future.result() →
        # _safe_run'ın except'i tarafından) fırlatılmasını sağlar — tek bir
        # servisin başlatma hatası tüm pipeline'ı çökertmez.
        with ThreadPoolExecutor(max_workers=4) as pool:
            f_yolo    = pool.submit(lambda: self.detector.detect_objects_in_frames(frames))
            f_vision  = pool.submit(lambda: self.vision_detector.detect_landmarks_in_frames(frames[:5]))
            f_ocr     = pool.submit(lambda: self.ocr.extract_text_from_frames(frames))
            if run_whisper:
                f_whisper = pool.submit(lambda: self.audio_processor.process_video_audio(video_path, video_id))

            # Her future bağımsız — biri exception fırlatsa diğerleri toplanır
            r_yolo    = _safe_run("YOLO",    None, fallback=[],   future=f_yolo,    timeout=180)
            r_vision  = _safe_run("Vision",  None, fallback=[],   future=f_vision,  timeout=120)
            r_ocr     = _safe_run("OCR",     None, fallback=[],   future=f_ocr,     timeout=180)
            if run_whisper:
                r_whisper = _safe_run("Whisper", None, fallback=None, future=f_whisper, timeout=300)
            else:
                r_whisper = ServiceResult("Whisper(skipped/gemini)", None, True)

        degradation_log.extend([r_yolo, r_vision, r_ocr, r_whisper])

        # Sonuçları aç
        detections: List       = r_yolo.data
        vision_landmarks: List = r_vision.data
        extracted_texts: List  = r_ocr.data
        transcription: Optional[Dict] = r_whisper.data

        # YOLO post-processing (verisi varsa)
        if detections:
            try:
                detections = self.detector.remove_duplicate_detections(detections)
                landmarks  = self.detector.get_landmark_candidates(detections)
                summary    = self.detector.get_detection_summary(detections)
            except Exception as e:
                logger.warning("YOLO post-process başarısız: %s", e)
                landmarks = []
                summary   = {"top_5_classes": []}
        else:
            landmarks = []
            summary   = {"top_5_classes": []}

        t_parallel = time.perf_counter()
        logger.info("⏱ Paralel AI: %.1fs | OCR=%d metin, Vision=%d landmark, "
                    "Whisper=%s, YOLO=%d nesne",
                    t_parallel - t_frames,
                    len(extracted_texts), len(vision_landmarks),
                    "✓" if transcription else "✗",
                    len(detections))

        # ─────────────────────────────────────────────────────────────────────
        # ── 4 & 5. Lokasyon çıkarma: Gemini VEYA klasik NER+OCR ─────────────
        # ─────────────────────────────────────────────────────────────────────
        transcript_text = (
            (transcription.get("transcript", "") if transcription else "").strip()
        )

        if self._use_gemini and self.gemini:
            # ── Gemini modu: frame + transcript → tek API çağrısı ────────────
            set_progress(video_id, "ner", 55)
            logger.info("🤖 Gemini lokasyon çıkarma başlıyor…")
            r_gemini = _safe_run(
                "Gemini(locations)",
                lambda: self.gemini.extract_locations(frames, transcript_text, video_id=video_id),
                fallback=[],
            )
            # Gemini artık List[Dict] döndürüyor: [{"name":..,"lat":..,"lng":..,"type":..}]
            gemini_raw: List[Dict] = r_gemini.data or []
            # Geriye dönük uyumluluk: eski string listesi gelirse dönüştür
            if gemini_raw and isinstance(gemini_raw[0], str):
                gemini_raw = [{"name": s, "lat": None, "lng": None, "type": "place"}
                              for s in gemini_raw]
            degradation_log.append(r_gemini)
            logger.info("🤖 Gemini: %d lokasyon", len(gemini_raw))

            # ── HİBRİT: BERT NER ile transkripti de tara, sonuçları birleştir ──
            if self._use_hybrid and transcript_text:
                r_bert = _safe_run(
                    "BERT-NER(hybrid)",
                    lambda: self.ner.extract_locations_from_transcript(transcript_text),
                    fallback=[],
                )
                bert_locations: List[str] = r_bert.data or []
                degradation_log.append(r_bert)
                logger.info("🧠 BERT NER (hibrit): %d lokasyon → %s",
                            len(bert_locations), bert_locations)

                # Gemini'de olmayanları gemini_raw'a ekle (case-insensitive merge)
                gemini_names_lc = {d["name"].lower().strip() for d in gemini_raw}
                added_count = 0
                for loc in bert_locations:
                    if loc.lower().strip() not in gemini_names_lc:
                        gemini_raw.append({
                            "name": loc, "lat": None, "lng": None,
                            "type": "place", "source": "bert_ner",
                        })
                        added_count += 1
                if added_count:
                    logger.info("🔀 Hibrit birleştirme: BERT'ten +%d yeni lokasyon eklendi", added_count)

            extracted_locations: List[str] = [d["name"] for d in gemini_raw]
            logger.info("✅ Toplam lokasyon adayı: %d → %s",
                        len(extracted_locations), extracted_locations)
            set_progress(video_id, "ner_ocr", 58)
            # Gemini/Hibrit modunda da OCR metin filtresi çalıştır (işletme isimleri için)
            ocr_pois: List = self._filter_ocr_pois(extracted_texts, video_id)

        else:
            # ── Klasik pipeline: NER (audio) + OCR NER ───────────────────────
            set_progress(video_id, "ner", 55)
            extracted_locations = []

            if transcript_text:
                r_ner = _safe_run(
                    "NER(audio)",
                    lambda: self.ner.extract_locations_from_transcript(transcript_text),
                    fallback=[],
                )
                extracted_locations = r_ner.data
                degradation_log.append(r_ner)
                logger.info("NER: %d karakter → %d lokasyon",
                            len(transcript_text), len(extracted_locations))
            else:
                logger.info("NER atlandı — transkript yok (Whisper fallback veya sessiz video)")

            set_progress(video_id, "ner_ocr", 58)
            ocr_pois = self._filter_ocr_pois(extracted_texts, video_id)

        # ─────────────────────────────────────────────────────────────────────
        # ── 6. Geocoding — Nominatim + Overpass ──────────────────────────────
        # ─────────────────────────────────────────────────────────────────────
        set_progress(video_id, "geocoding", 65)

        # NER lokasyonlarını zenginleştir
        gemini_city_hint = (
            self._detect_city_from_list(extracted_locations)
            if self._use_gemini else None
        )
        if gemini_city_hint:
            logger.info("🏙️ Gemini pre-geocoding city hint: '%s'", gemini_city_hint)

        # ── Gemini modunda: koordinat gelen mekanları direkt ekle ─────────────
        # Koordinat gelmeyen mekanlar için Nominatim / city_fallback devreye girer.
        if self._use_gemini and gemini_raw:
            ner_enriched: List = []
            nominatim_needed: List[str] = []

            for item in gemini_raw:
                name = item["name"]
                lat, lng = item.get("lat"), item.get("lng")
                if lat is not None and lng is not None:
                    # Gemini koordinat verdi → direkt kullan
                    ner_enriched.append({
                        "original_name": name,
                        "place_data": {
                            "name":       name,
                            "address":    name,
                            "location":   {"lat": lat, "lng": lng},
                            "type":       item.get("type", "place"),
                            "class":      "place",
                            "importance": 0.15,
                            "source":     "gemini_coords",
                        },
                    })
                    logger.info("📍 Gemini koordinat: '%s' → (%.4f, %.4f)", name, lat, lng)
                else:
                    nominatim_needed.append(name)

            # Koordinatsızlar için Nominatim dene
            if nominatim_needed:
                r_ner_geo = _safe_run(
                    "Geocoding(NER)",
                    lambda: self.places.enrich_locations(
                        nominatim_needed,
                        use_overpass=True,
                        city_hint=gemini_city_hint,
                    ),
                    fallback=[],
                )
                ner_enriched.extend(r_ner_geo.data)
                degradation_log.append(r_ner_geo)
        else:
            r_ner_geo = _safe_run(
                "Geocoding(NER)",
                lambda: self.places.enrich_locations(
                    extracted_locations,
                    use_overpass=False,
                    city_hint=gemini_city_hint,
                ) if extracted_locations else [],
                fallback=[],
            )
            ner_enriched: List = r_ner_geo.data
            degradation_log.append(r_ner_geo)

        # City bounding box (Overpass isabetini artırır)
        city_bbox = self._extract_city_bbox(ner_enriched)
        # City hint: "Nohut Durumu Gaziantep" gibi qualifier aramaları için
        city_hint = self._extract_city_hint(ner_enriched)
        if city_hint:
            logger.info("🏙️ City hint: '%s'", city_hint)

        # OCR POI'larını zenginleştir
        set_progress(video_id, "overpass", 75)
        ocr_enriched = self._enrich_ocr_pois(ocr_pois, city_bbox, degradation_log, city_hint=city_hint)

        # Vision landmarks → zenginleştirilmiş formata çevir
        vision_enriched = self._convert_vision_landmarks(vision_landmarks)

        # ── Gemini modu: geocode edilemeyen lokasyonları şehir koordinatıyla ekle ──
        # Nominatim'de olmayan restoranlar/mekanlar için şehir merkezini kullan.
        # Böylece "7 Mekan" görünür, haritada şehir konumuna pin düşer.
        if self._use_gemini and extracted_locations:
            enriched_names = {
                e["original_name"].lower().strip() for e in ner_enriched
            }
            # NOT: buradaki fallback'e bilerek ner_enriched[0] atanmıyor. Sıradaki ilk
            # eleman şehir/kasaba olmayabilir (örn. bir ülke adı veya yanlış geocode
            # edilmiş bir POI) — o zaman gerçekte alakasız bir koordinata pin basmak
            # yerine, bu lokasyonu tamamen atlıyoruz (aşağıdaki `if city_coords:` kontrolü).
            city_entry = next(
                (e for e in ner_enriched
                 if (e.get("place_data") or {}).get("type") in ("city", "town", "administrative")),
                None,
            )
            city_coords = (city_entry or {}).get("place_data", {}).get("location") if city_entry else None
            fallback_city = gemini_city_hint or city_hint or ""

            for loc in extracted_locations:
                if loc.lower().strip() in enriched_names:
                    continue  # zaten geocode edildi
                if loc.lower().strip() == fallback_city.lower().strip():
                    continue  # şehrin kendisi, tekrar ekleme
                if city_coords:
                    ner_enriched.append({
                        "original_name": loc,
                        "place_data": {
                            "name":       loc,
                            "address":    f"{loc}, {fallback_city}",
                            "location":   city_coords,   # şehir merkezi koordinatı
                            "type":       "point_of_interest",
                            "class":      "amenity",
                            "importance": 0.08,
                            "source":     "gemini_city_fallback",
                        },
                    })
                    logger.info("📍 Şehir fallback ile eklendi: '%s' → %s", loc, fallback_city)

        enriched_locations = ner_enriched + ocr_enriched + vision_enriched
        logger.info("Enriched toplam: %d NER + %d OCR + %d Vision = %d",
                    len(ner_enriched), len(ocr_enriched),
                    len(vision_enriched), len(enriched_locations))

        # ─────────────────────────────────────────────────────────────────────
        # ── 6b. Coğrafi Tutarlılık Filtresi ──────────────────────────────────
        # Dominant il tespit edilir, uzak outlier'lar aynı il bbox'ıyla
        # yeniden sorgulanır.
        # Örnek: 7× Antalya, 1× Amasya (Kaleköy) → Kaleköy'ü Antalya'da yeniden ara
        # ─────────────────────────────────────────────────────────────────────
        # _fix_geographic_outliers self.places'i doğrudan çağırır (_safe_run
        # dışında) — places init'te başarısız olduysa (None) veya outlier
        # yeniden sorgusu sırasında ağ hatası olursa, bu tek adımın tüm
        # pipeline'ı çökertmemesi için burada sarmalanır; başarısızlıkta
        # orijinal (düzeltilmemiş) liste ile devam edilir.
        r_geo_fix = _safe_run(
            "GeoOutlierFix",
            lambda: self._fix_geographic_outliers(enriched_locations, degradation_log),
            fallback=enriched_locations,
        )
        enriched_locations = r_geo_fix.data
        degradation_log.append(r_geo_fix)

        # ─────────────────────────────────────────────────────────────────────
        # ── 7. Deduplication ─────────────────────────────────────────────────
        # Gemini city_fallback lokasyonları aynı koordinata sahip olduğundan
        # dedup'dan ayrı tutuyoruz — yoksa 7→1 olur.
        # ─────────────────────────────────────────────────────────────────────
        set_progress(video_id, "dedup", 85)

        # Gemini modunda: koordinatlar birbirine çok yakın (aynı çarşı/semt içinde)
        # 2km threshold hepsini tek mekan sayar → Gemini modunda 0.05km (50m) kullan.
        # Sadece tam aynı adreste olanları birleştirsin.
        # Klasik pipeline: 2km threshold korunur (NER+OCR+Vision tekrarlarını temizler).
        if self._use_gemini:
            dedup_threshold = 0.001  # 1 metre — sadece birebir aynı koordinat (Gemini farklı isim = farklı mekan)
        else:
            dedup_threshold = 2.0    # 2 km   — klasik pipeline için

        # Fallback lokasyonları (aynı koordinat) dedup'a sokma, sonradan ekle
        geocoded_locs = [l for l in enriched_locations
                         if (l.get("place_data") or {}).get("source") != "gemini_city_fallback"]
        fallback_locs = [l for l in enriched_locations
                         if (l.get("place_data") or {}).get("source") == "gemini_city_fallback"]

        from app.ml.location_deduplicator import LocationDeduplicator
        deduplicator = LocationDeduplicator(distance_threshold_km=dedup_threshold)

        r_dedup = _safe_run(
            "Dedup",
            lambda: deduplicator.deduplicate_locations(geocoded_locs),
            fallback=geocoded_locs,
        )
        deduplicated_locations: List = r_dedup.data + fallback_locs

        r_loc_summary = _safe_run(
            "LocSummary",
            lambda: deduplicator.get_location_summary(geocoded_locs),
            fallback={},
        )
        location_summary: Dict = r_loc_summary.data
        degradation_log.extend([r_dedup, r_loc_summary])

        # ─────────────────────────────────────────────────────────────────────
        # ── 8. Route Optimization ────────────────────────────────────────────
        # ─────────────────────────────────────────────────────────────────────
        set_progress(video_id, "route", 90)
        r_route = _safe_run(
            "Route",
            lambda: (
                self.route_optimizer.optimize_route(deduplicated_locations)
                if deduplicated_locations else {}
            ),
            fallback={},
        )
        optimized_route: Dict = r_route.data
        degradation_log.append(r_route)

        # ─────────────────────────────────────────────────────────────────────
        # ── 9. Travel Tips: Gemini VEYA Ollama/RAG ───────────────────────────
        # ─────────────────────────────────────────────────────────────────────
        set_progress(video_id, "rag", 95)
        if self._use_gemini and self.gemini:
            tip_names = [loc.get("original_name", "") for loc in deduplicated_locations]
            r_rag = _safe_run(
                "Gemini(tips)",
                lambda: self.gemini.generate_travel_tips(tip_names, video_id=video_id) if tip_names else {},
                fallback={},
            )
        else:
            r_rag = _safe_run(
                "RAG",
                lambda: (
                    self.rag.generate_travel_tips(deduplicated_locations)
                    if deduplicated_locations else {}
                ),
                fallback={},
            )
        travel_tips: Dict = r_rag.data
        degradation_log.append(r_rag)

        # ─────────────────────────────────────────────────────────────────────
        # ── 10. Qdrant — Vektör Embedding ────────────────────────────────────
        # ─────────────────────────────────────────────────────────────────────
        r_qdrant = _safe_run(
            "Qdrant",
            lambda: self.qdrant.add_locations(enriched_locations) if enriched_locations else None,
            fallback=None,
        )
        degradation_log.append(r_qdrant)

        # ─────────────────────────────────────────────────────────────────────
        # ── Degradasyon Raporu ────────────────────────────────────────────────
        # ─────────────────────────────────────────────────────────────────────
        total_time = time.perf_counter() - start_time
        _log_degradation_report(degradation_log, video_id)
        logger.info("⏱ Toplam işlem süresi: %.2fs | Frame/sn: %.2f",
                    total_time, len(frames) / total_time if frames else 0)

        # Kaç servis fallback kullandı?
        fallback_count = sum(1 for r in degradation_log if r.fallback_used)
        degradation_summary = {
            "total_services": len(degradation_log),
            "successful":     len(degradation_log) - fallback_count,
            "fallback_used":  fallback_count,
            "failed_services": [r.name for r in degradation_log if r.fallback_used],
        }

        return {
            # ── Video meta ────────────────────────────────────────────────────
            "duration":         metadata["duration"],
            "resolution":       f"{metadata['width']}x{metadata['height']}",
            "fps":              metadata["fps"],
            "frame_count":      len(frames),
            "frames_dir":       str(frame_dir),
            "thumbnail":        thumbnail,
            "processing_time":  round(total_time, 2),
            "fps_processed":    round(len(frames) / total_time, 2) if frames else 0,
            # ── AI çıktıları ──────────────────────────────────────────────────
            "detections_count":      len(detections),
            "landmarks_count":       len(landmarks),
            "vision_landmarks":      vision_landmarks,
            "extracted_texts":       extracted_texts,
            "transcription":         transcription,
            "extracted_locations":   extracted_locations,
            "enriched_locations":    enriched_locations,
            "location_summary":      location_summary,
            "deduplicated_locations":deduplicated_locations,
            "optimized_route":       optimized_route,
            "travel_tips":           travel_tips,
            "ocr_pois":              ocr_pois,
            "top_objects":           summary["top_5_classes"],
            # ── Degradasyon bilgisi ───────────────────────────────────────────
            "degradation":           degradation_summary,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Yardımcı metodlar
    # ─────────────────────────────────────────────────────────────────────────

    def _filter_ocr_pois(self, extracted_texts: List[str], video_id: int) -> List[str]:
        """OCR metinlerinden POI'ları filtrele. OCR başarısızsa boş liste döner."""
        if not extracted_texts:
            return []

        try:
            return self._run_ocr_filter_pipeline(extracted_texts, video_id)
        except Exception as e:
            logger.warning("OCR POI filtresi başarısız — boş liste fallback | %s", e)
            return []

    def _enrich_ocr_pois(
        self,
        ocr_pois: List[str],
        city_bbox: Optional[tuple],
        degradation_log: List[ServiceResult],
        city_hint: Optional[str] = None,
    ) -> List[Dict]:
        """OCR POI'larını geocoding ile zenginleştir."""
        if not ocr_pois:
            return []

        geo_signals = self._geo_signal_set()

        def _has_geo_signal(text: str) -> bool:
            t_l = self._tr_lower(text)
            t_f = self._ascii_fold(t_l)
            return any(s in t_l or self._ascii_fold(s) in t_f for s in geo_signals)

        overpass_pois  = [p for p in ocr_pois if _has_geo_signal(p)]
        nominatim_pois = [p for p in ocr_pois if not _has_geo_signal(p)]

        enriched: List[Dict] = []

        if overpass_pois:
            r = _safe_run(
                "Geocoding(Overpass)",
                lambda: self.places.enrich_locations(
                    overpass_pois, use_overpass=True, city_bbox=city_bbox,
                    city_hint=city_hint,
                ),
                fallback=[],
            )
            # Overpass fail/boş döndüyse → aynı lokasyonları Nominatim'e yönlendir
            if r.data:
                enriched.extend(r.data)
                degradation_log.append(r)
            else:
                logger.info("🔄 Overpass başarısız → %d POI Nominatim'e yönlendiriliyor",
                            len(overpass_pois))
                nominatim_pois = overpass_pois + nominatim_pois  # hepsini birleştir
                degradation_log.append(r)

        if nominatim_pois:
            r = _safe_run(
                "Geocoding(Nominatim)",
                lambda: self.places.enrich_locations(
                    nominatim_pois, use_overpass=False, city_bbox=city_bbox,
                    city_hint=city_hint,
                ),
                fallback=[],
            )
            enriched.extend(r.data)
            degradation_log.append(r)

        return enriched

    @staticmethod
    def _convert_vision_landmarks(vision_landmarks: List[Dict]) -> List[Dict]:
        """Google Vision landmark'larını enriched formatına çevir."""
        result = []
        for lm in vision_landmarks:
            if lm.get("latitude") and lm.get("longitude") and lm.get("confidence", 0) > 0.5:
                result.append({
                    "original_name": lm["name"],
                    "place_data": {
                        "name":       lm["name"],
                        "location":   {"lat": lm["latitude"], "lng": lm["longitude"]},
                        "type":       "landmark",
                        "importance": lm["confidence"],
                    },
                })
        return result

    def _fix_geographic_outliers(
        self,
        locations: List[Dict],
        degradation_log: List,
    ) -> List[Dict]:
        """
        Dominant ili bul, çok uzaktaki lokasyonları aynı il bbox'ıyla yeniden sorgula.

        Algoritma:
          1. Her lokasyonun il bilgisini çek (address_details.province)
          2. En sık geçen il → dominant_province
          3. Dominant ile ait lokasyonların merkez koordinatını hesapla (centroid)
          4. Centroid'e MAX_OUTLIER_KM'den uzak olanları yeniden sorgula
          5. Yeni sonuç bulunursa değiştir, bulunamazsa orijinali koru

        Örnek:
          7× Antalya + 1× Amasya (Kaleköy) + 1× İstanbul (Kaleiçi)
          → dominant = Antalya, centroid ≈ (36.5, 30.5)
          → Kaleköy Amasya 490km uzak → Antalya'da yeniden ara → Kaleköy/Kaş ✅
          → Kaleiçi İstanbul 590km uzak → Antalya'da yeniden ara → Kaleiçi/Antalya ✅
        """
        from collections import Counter
        from math import radians, sin, cos, sqrt, atan2

        MAX_OUTLIER_KM = 180   # bu kadar uzaksa outlier say
        DOMINANT_MIN   = 2     # dominant il için minimum lokasyon sayısı

        if len(locations) < 3:
            return locations   # çok az veri → filtre anlamsız

        def _haversine(lat1, lon1, lat2, lon2):
            R = 6371.0
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
            return R * 2 * atan2(sqrt(a), sqrt(1-a))

        def _get_coords(loc):
            pd = loc.get("place_data") or {}
            c  = pd.get("location") or {}
            return c.get("lat"), c.get("lng")

        def _get_province(loc):
            pd   = loc.get("place_data") or {}
            addr = pd.get("address_details") or {}
            return addr.get("province") or addr.get("state")

        # Adım 1: İl sayımı
        province_counter: Counter = Counter()
        for loc in locations:
            p = _get_province(loc)
            if p:
                province_counter[p] += 1

        if not province_counter:
            return locations

        dominant_province, dominant_count = province_counter.most_common(1)[0]
        if dominant_count < DOMINANT_MIN:
            return locations   # dominant yok → filtre gerekli değil

        # Adım 2: Dominant ilin centroid'i
        dominant_locs = [
            loc for loc in locations
            if _get_province(loc) == dominant_province
        ]
        valid_coords = [
            _get_coords(loc) for loc in dominant_locs
            if all(_get_coords(loc))
        ]
        if not valid_coords:
            return locations

        centroid_lat = sum(c[0] for c in valid_coords) / len(valid_coords)
        centroid_lng = sum(c[1] for c in valid_coords) / len(valid_coords)

        # Bbox: centroid ± 2°  (~220km)
        dominant_bbox = (
            centroid_lat - 2.0, centroid_lng - 2.0,
            centroid_lat + 2.0, centroid_lng + 2.0,
        )

        logger.info(
            "🌍 Coğrafi tutarlılık: dominant=%s (%d/%d lokasyon), centroid=(%.2f, %.2f)",
            dominant_province, dominant_count, len(locations),
            centroid_lat, centroid_lng,
        )

        # Adım 3: Outlier'ları tespit et ve yeniden sorgula
        result = []
        for loc in locations:
            lat, lng = _get_coords(loc)
            if lat is None or lng is None:
                result.append(loc)
                continue

            km = _haversine(centroid_lat, centroid_lng, lat, lng)
            if km <= MAX_OUTLIER_KM:
                result.append(loc)
                continue

            # Outlier — yeniden sorgula
            name = loc.get("original_name", "")
            logger.info(
                "🔄 Outlier yeniden sorgulanıyor: '%s' (%.0fkm uzak, il=%s)",
                name, km, _get_province(loc),
            )
            new_place = self.places.search_place(
                name, city_bbox=dominant_bbox, city_hint=dominant_province
            )
            if new_place:
                new_lat = (new_place.get("location") or {}).get("lat")
                new_lng = (new_place.get("location") or {}).get("lng")
                if new_lat and new_lng:
                    new_km = _haversine(centroid_lat, centroid_lng, new_lat, new_lng)
                    if new_km <= MAX_OUTLIER_KM:
                        logger.info(
                            "  ✅ '%s' düzeltildi: %s → %s (%.0fkm)",
                            name, _get_province(loc),
                            (new_place.get("address_details") or {}).get("province", "?"),
                            new_km,
                        )
                        loc = {**loc, "place_data": new_place}
                    else:
                        logger.info("  ⚠️ '%s' yeni sonuç da uzak (%.0fkm) — orijinal korundu", name, new_km)
            else:
                logger.info("  ⚠️ '%s' yeniden sorgu sonuç vermedi — orijinal korundu", name)

            result.append(loc)

        return result

    @staticmethod
    def _extract_city_bbox(ner_enriched: List[Dict]) -> Optional[tuple]:
        """İlk NER lokasyonundan şehir bounding box'ı çıkar (Overpass için)."""
        if not ner_enriched:
            return None
        loc = ner_enriched[0].get("place_data", {}).get("location")
        if not loc:
            return None
        lat, lng = loc["lat"], loc["lng"]
        return (lat - 2.0, lng - 2.0, lat + 2.0, lng + 2.0)

    @staticmethod
    def _extract_city_hint(ner_enriched: List[Dict]) -> Optional[str]:
        """
        Dominant şehir adını çıkar — OCR geocoding için qualifier.
        "Nohut Durumu" → "Nohut Durumu Gaziantep" şeklinde Nominatim'de aranır.

        Çoğunluk oyu (mode) kullanılır — sadece listedeki İLK eşleşen giriş
        kullanılırsa, tek bir yanlış/alakasız geocoding sonucu (örn. BERT-NER'in
        transkriptte hayal ettiği bir yer adı) tüm videonun city_hint'ini
        yanlış yöne çekebilir. Çoğunluk arasında birden fazla doğru lokasyon
        aynı şehri işaret ediyorsa o kazanır.
        """
        if not ner_enriched:
            return None

        from collections import Counter
        votes: Counter = Counter()
        for loc in ner_enriched:
            addr = (loc.get("place_data") or {}).get("address_details") or {}
            # Nominatim address hierarchy: city > town > province > state
            for key in ("city", "town", "province", "state"):
                if name := addr.get(key):
                    votes[name] += 1
                    break
            else:
                # Fallback: original_name eğer şehir seviyesindeyse
                place = loc.get("place_data") or {}
                if place.get("type") in ("city", "town"):
                    votes[loc.get("original_name")] += 1

        if not votes:
            return None
        return votes.most_common(1)[0][0]

    @staticmethod
    def _detect_city_from_list(locations: List[str]) -> Optional[str]:
        """
        Gemini lokasyon listesinden şehir adını önceden tespit et.
        Geocoding'den ÖNCE çağrılır → city_hint olarak kullanılır.
        Örn: ['Gaziantep', 'Bişirici Kebap', ...] → 'Gaziantep'
        """
        _tr_cities = {
            "gaziantep", "antalya", "istanbul", "ankara", "izmir", "bursa",
            "adana", "konya", "mersin", "kayseri", "eskişehir", "eskisehir",
            "trabzon", "diyarbakır", "diyarbakir", "samsun", "malatya",
            "kahramanmaraş", "kahramanmaras", "erzurum", "kocaeli", "gebze",
            "denizli", "pamukkale", "bodrum", "muğla", "mugla", "fethiye",
            "alanya", "kapadokya", "cappadocia", "nevşehir", "nevsehir",
            "mardin", "şanlıurfa", "sanliurfa", "urfa", "hatay", "antakya",
        }
        for loc in locations:
            if loc.lower().strip() in _tr_cities:
                return loc
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # OCR filtre pipeline (ayrı metod — test edilebilir)
    # ─────────────────────────────────────────────────────────────────────────

    def _run_ocr_filter_pipeline(self, extracted_texts: List[str], video_id: int) -> List[str]:
        """OCR POI filtresi — gürültü eleme + NER batch + heuristic fallback."""

        tr_lower    = self._tr_lower
        ascii_fold  = self._ascii_fold
        geo_signals = self._geo_signal_set()
        noise_set   = self._noise_pattern_set()
        stopwords   = self._tr_stopword_set()
        generic_set = self._generic_type_set()

        desc_regexes = [
            _re.compile(p, _re.IGNORECASE) for p in [
                r"\d+\s*(yer|tane|adet|durak|mekan|kafe|sahil|plaj)",
                r"\w+['\u2018\u2019]?\s*(?:da|de|ta|te)\s+gezilecek",
                r"(?:da|de|ta|te)\s+gezilecek",
                r"(en iyi|mutlaka|kesinlikle|illa)",
                r"(gidilecek|gorilecek|gorulebilecek)",
                r"(yenilecek|icilecek|icekilecek)",
                r"(nasil|nerede|nereden|hangi)",
                r"(bolum|part|episode|vlog|video)",
                r"\d+\.\s*(bolum|part|video)",
                r"gezilecek",
                r"(listesi|rehberi|onerileri|tavsiyeleri)",
                r"(top\s*\d+|en\s+iyi\s+\d+)",
            ]
        ]

        def _has_geo_signal(text: str) -> bool:
            t_l = tr_lower(text)
            t_f = ascii_fold(t_l)
            return any(s in t_l or ascii_fold(s) in t_f for s in geo_signals)

        def _split_camelcase(t: str) -> str:
            t = _re.sub(r'([a-zğüşıöç])([A-ZĞÜŞİÖÇ])', r'\1 \2', t)
            t = _re.sub(r'([A-ZĞÜŞİÖÇ]{2,})([A-ZĞÜŞİÖÇ][a-zğüşıöç])', r'\1 \2', t)
            return t.strip()

        def _norm(t: str) -> str:
            return _re.sub(r'[^a-z0-9ğüşıöç]', '', tr_lower(t))

        def _is_fuzzy_dup(t: str, seen: list) -> bool:
            norm = _norm(t)
            if len(norm) < 4:
                return False
            return any(
                SequenceMatcher(None, norm, s).ratio() >= 0.82
                for s in seen
            )

        def is_noise(t: str) -> bool:
            t_l  = tr_lower(t).strip()
            t_orig = t.strip()
            if len(t_l) < 4: return True
            if t_l.replace(" ", "").isnumeric(): return True
            if t_l.endswith(("?", "-", ":", ".", ",")): return True
            if t_l.startswith(("-", ".", ":")): return True
            if any(p in t_l for p in noise_set): return True
            if t_l in stopwords: return True
            if "_" in t_orig: return True
            tokens = t_l.split()
            if tokens and tokens[0].isnumeric(): return True
            if any(r.search(t_l) for r in desc_regexes): return True
            short_tokens = [tok for tok in tokens if len(tok) <= 2]
            if tokens and len(short_tokens) / len(tokens) > 0.5: return True
            if t_orig.isupper() and len(t_l) < 6 and len(tokens) == 1: return True
            return False

        # ── Aşama 1: Noise filtresi + fuzzy dedup ────────────────────────────
        candidates, seen_display, seen_norms = [], set(), []
        for t in extracted_texts:
            t_clean = _split_camelcase(t.strip())
            t_lower = tr_lower(t_clean)
            if is_noise(t_clean): continue
            if t_lower in seen_display: continue
            if _is_fuzzy_dup(t_clean, seen_norms): continue
            words = t_clean.split()
            if len(words) == 1 and t_lower in generic_set: continue
            seen_display.add(t_lower)
            seen_norms.append(_norm(t_clean))
            candidates.append(t_clean)

        if not candidates:
            return []

        # ── Aşama 2: Batch NER filtresi ──────────────────────────────────────
        MAX_POIS = 18
        try:
            ner_filtered = self.ner.filter_locations_from_ocr(candidates)
            if ner_filtered:
                logger.info("NER batch: %d → %d POI", len(candidates), len(ner_filtered))
                return ner_filtered[:MAX_POIS]
            # NER 0 sonuç → heuristic fallback
            fallback_pois = [
                t for t in candidates
                if _has_geo_signal(t) or len(t.split()) >= 2
            ][:MAX_POIS]
            logger.info("NER batch 0 sonuç → heuristic fallback: %d POI", len(fallback_pois))
            return fallback_pois
        except Exception as e:
            logger.warning("NER batch OCR filtresi başarısız — heuristic fallback | %s", e)
            return [
                t for t in candidates
                if _has_geo_signal(t) or len(t.split()) >= 2
            ][:MAX_POIS]

    # ─────────────────────────────────────────────────────────────────────────
    # Statik yardımcılar
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _tr_lower(s: str) -> str:
        return s.replace("İ", "i").replace("I", "ı").lower()

    @staticmethod
    def _ascii_fold(s: str) -> str:
        return (s.replace("ğ", "g").replace("ü", "u").replace("ş", "s")
                 .replace("ı", "i").replace("ö", "o").replace("ç", "c")
                 .replace("â", "a").replace("î", "i").replace("û", "u"))

    @staticmethod
    def _geo_signal_set() -> set:
        return {
            "han", "kafe", "cafe", "restoran", "müze", "cami", "kilise",
            "köprü", "kale", "kalesi", "kaleici", "sarayı", "parkı", "gölü",
            "plajı", "plaji", "şelalesi", "selalesi",
            "mağarası", "magarasi", "tepesi", "dağı", "dagi", "vadisi",
            "konak", "çarşı", "carsi", "pazar", "hamam", "türbe", "turbe",
            "anıt", "anit", "kervansaray", "ören",
            "sokağı", "sokagi", "mahallesi", "kapısı", "kapisi",
            "kulesi", "camii", "hamamı", "hamami",
            "bahçesi", "bahcesi", "ormanı", "ormani", "göleti", "barajı",
            "köprüsü", "koprüsü",
            "koyu", "körfez", "korfez", "limanı", "limani",
            "kayalığı", "kayaligi", "adası", "adasi", "yarımadası",
            "kanyonu", "platosu", "çayı", "cayi", "irmağı",
            "yaylası", "yaylasi", "milliparkı",
            "harabeleri", "höyüğü", "hoyugu", "mezarlığı", "mezarligi",
            "kilisesi", "manastırı", "manastiri", "kalıntıları",
            # Yemek & işletme sinyalleri — Gaziantep/şehir lokali içerik
            "yeri", "durumu", "evi", "ocağı", "ocagi", "fırını", "firini",
            "pastanesi", "lokantası", "lokantasi", "kebabçısı", "kebabcisi",
            "büfesi", "bufesi", "dönercisi", "donercisi", "tatlıcısı",
            "çiğköftecisi", "cigkoftecisi", "pidecisi", "lahmacuncusu",
            "muhallebicisi", "baklavacısı", "baklavacisi",
        }

    @staticmethod
    def _noise_pattern_set() -> set:
        return {
            "www.", "http", "@", "#", ".com", ".tr", "₺", "$", "€",
            "follow", "like", "share", "subscribe", "abone", "takip",
        }

    @staticmethod
    def _tr_stopword_set() -> set:
        return {
            "içecek", "yiyecek", "giriş", "çıkış", "bilgi", "lütfen", "teşekkür",
            "devam", "dikkat", "uyarı", "yasak", "serbest", "açık", "kapalı",
            "indirim", "fiyat", "menü", "sipariş", "ödeme", "nakit", "kart",
            "telefon", "adres", "saat", "tarih", "numara", "adet", "toplam",
            "olan", "olur", "oldu", "için", "ile", "veya", "hem", "ama",
            "büyük", "küçük", "yeni", "eski", "güzel", "iyi", "kötü",
            "başka", "diğer", "tüm", "her", "bazı", "çok", "az", "daha",
            "dis", "bis", "ecs", "aci", "bey", "ecek", "acak", "mis",
            "yo", "ve", "da", "de", "ki", "mi", "mu", "mü",
            "kahvesi", "çayı", "kebabı", "mantısı", "baklavası", "köftesi",
            "pidesi", "böreği", "tatlısı", "döneri", "lahmacunu", "çorbası",
            "büfesi", "fırını", "pastanesi", "lokantası", "restoranı",
            "istanbul", "ankara", "izmir",
            "market", "deneme", "gerekenler", "durumu", "masaya", "masasi",
            "lutfen", "yiyecek", "icecek", "siparis", "ucretsiz", "ucret",
            "ntep", "disin", "disi", "bufe", "bufesi",
        }

    @staticmethod
    def _generic_type_set() -> set:
        return {
            "koyu", "koy", "plaj", "plaji", "sahil", "dağ", "dag", "gol", "göl",
            "şelale", "selale", "orman", "vadi", "kanyon", "tepe", "kale",
            "cami", "camii", "köy", "koy", "mahalle", "sokak", "cadde",
            "park", "bahçe", "bahce", "ada", "kıyı", "kiyi", "liman",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Video işleme (metadata, frame, thumbnail)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_metadata(self, video_path: str) -> Dict:
        import ffmpeg
        try:
            probe        = ffmpeg.probe(video_path)
            video_stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
            fps_str      = video_stream.get("r_frame_rate", "30/1")
            num, den     = fps_str.split("/")
            return {
                "duration": float(probe["format"]["duration"]),
                "width":    int(video_stream["width"]),
                "height":   int(video_stream["height"]),
                "fps":      round(float(num) / float(den), 2),
            }
        except Exception as e:
            logger.error("Metadata çıkarma başarısız: %s", e)
            raise

    def _extract_frames(self, video_path: str, output_dir: Path, fps: float = 0.5) -> List[str]:
        import ffmpeg
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            (
                ffmpeg.input(video_path)
                .filter("fps", fps=fps)
                .output(str(output_dir / "frame_%04d.jpg"), quality=2)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            frames = sorted(output_dir.glob("*.jpg"))
            return [str(f) for f in frames if f.name.startswith("frame_")]
        except ffmpeg.Error as e:
            logger.error("FFmpeg hatası: %s", e.stderr.decode())
            raise

    def _create_thumbnail(self, first_frame: Optional[str]) -> Optional[str]:
        if not first_frame:
            return None
        import ffmpeg
        try:
            thumb_path = Path(first_frame).parent / "thumbnail.jpg"
            (
                ffmpeg.input(first_frame)
                .filter("scale", 320, -1)
                .output(str(thumb_path))
                .overwrite_output()
                .run(quiet=True)
            )
            return str(thumb_path)
        except Exception as e:
            logger.error("Thumbnail oluşturulamadı: %s", e)
            return None
