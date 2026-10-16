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

import hashlib
import logging
import os
import time
import json as _json
import re as _re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.core.redis import set_progress, get_redis
from app.core.services.pipeline.runtime import ServiceResult, _safe_run
from app.core.services.pipeline.media import MediaStages, _FFmpegTimeout, _FFmpegTimeoutGuard
from app.core.services.pipeline.locations import LocationStages
from app.core.services.pipeline.ocr import OCRStages
from app.core.services.pipeline.parallel import StageSpec, run_parallel
from app.core.services.pipeline.telemetry import timed_stage

logger = logging.getLogger(__name__)

# ── Gemini lokasyon çıktısı için içerik-adresli cache ─────────────────────────
#
# Gemini bit-düzeyinde tekrarlanabilir değil (sunucu tarafı batching, kayan
# nokta toplama sırası, model sürüm yönlendirmesi) ve seed sunmuyor.
#
# Determinizmi temperature=0 ile almaya çalışmak PAHALIYA MAL OLDU: tutarlılık
# geldi ama sonuç düşük değerde sabitlendi (antalya videosunda 9 isim yerine 5).
# Doğru yer burası — çıktıyı içerik hash'iyle sabitlemek, modeli kısıtlamak
# değil. Bkz. gemini_service._call içindeki temperature notu.
#
# Videonun SHA-256'sını anahtar yapıp çıktıyı cache'lemek üç sorunu birden
# çözüyor: aynı video HER ZAMAN aynı sonucu verir (determinizm), tekrar
# yükleme Gemini'yi hiç çağırmaz (kota + maliyet), ve idempotency sağlanır.

_GEMINI_CACHE_TTL = 60 * 60 * 24 * 30   # 30 gün

# Gemini lokasyon prompt'unun sürümü. Prompt değiştiğinde ARTIRILMALI, yoksa
# cache eski çıktıyı servis etmeye devam eder (bkz. _gemini_cache_key).
# v2: ekran yazıları (OCR) prompt'a eklendi + bozuk yazımı düzeltme talimatı.
# v5: koordinat istemi kaldırıldı, yerine bölge (region) + mekan başına şehir.
_GEMINI_PROMPT_VERSION = 5


def _video_content_hash(video_path: str) -> Optional[str]:
    """Video dosyasının SHA-256'sı. Okunamazsa None (cache devre dışı kalır)."""
    try:
        digest = hashlib.sha256()
        with open(video_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception as exc:
        logger.warning("Video hash hesaplanamadı, cache atlanıyor: %s", exc)
        return None


def _gemini_cache_key(content_hash: str) -> str:
    # Model adı anahtarın parçası: model değişirse eski çıktı kullanılmasın.
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    # Prompt sürümü de anahtarın parçası. Aksi hâlde prompt iyileştirildiğinde
    # cache eski (kötü) çıktıyı sonsuza kadar servis ediyor — ekran yazılarını
    # prompt'a eklediğimizde tam bu oldu, aynı video eski 3 lokasyonu döndürdü.
    # Prompt her değiştiğinde bu sayı artırılmalı.
    return f"gemini:locations:v{_GEMINI_PROMPT_VERSION}:{model}:{content_hash}"


def _gemini_cache_get(content_hash: Optional[str]) -> Optional[Dict]:
    if not content_hash:
        return None
    try:
        client = get_redis()
        if not client:
            return None
        raw = client.get(_gemini_cache_key(content_hash))
        return _json.loads(raw) if raw else None
    except Exception as exc:
        logger.debug("Gemini cache okunamadı: %s", exc)
        return None


def _gemini_cache_set(content_hash: Optional[str], extraction: Dict) -> None:
    # Boş çıkarım cache'lenmez — geçici bir 429'u 30 günlük bir hataya çevirirdi.
    if not content_hash or not (extraction or {}).get("locations"):
        return
    try:
        client = get_redis()
        if not client:
            return
        client.setex(_gemini_cache_key(content_hash), _GEMINI_CACHE_TTL,
                     _json.dumps(extraction))
    except Exception as exc:
        logger.debug("Gemini cache yazılamadı: %s", exc)


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

class VideoProcessingService(MediaStages, OCRStages, LocationStages):
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

        # FFmpeg is required for the video path. Optional ML imports and
        # model initialization are isolated per stage below.
        try:
            import ffmpeg as _ffmpeg_module  # noqa: F401
        except ImportError as e:
            logger.warning("ML servisleri yüklenemedi (test modu?): %s", e)
            self._ml_available = False
            return

        # Her servis bağımsız başlatılır — biri (örn. YOLO ağırlığı indirilemedi)
        # başarısız olsa bile diğerleri kurulmaya devam eder. Pipeline
        # çalışırken bu servisin sonucu None üzerinden fallback'e düşer
        # (bkz. _safe_run çağrıları), tüm işlem çökmez.
        self.detector        = self._init_ml_service("YOLO", "computer_vision", "ObjectDetectionService")
        self.vision_detector = self._init_ml_service("Vision", "computer_vision", "LandmarkDetectionService")
        self.ocr             = self._init_ml_service("OCR", "ocr_service", "OCRService")
        self.audio_processor = self._init_ml_service("Whisper", "speech_to_text", "AudioProcessingService")
        self.ner             = self._init_ml_service("NER", "ner_service", "NERService")
        self.places          = self._init_ml_service("Places", "places_service", "PlacesService")
        self.deduplicator    = self._init_ml_service("Dedup", "location_deduplicator", "LocationDeduplicator", distance_threshold_km=2.0)
        self.route_optimizer = self._init_ml_service("Route", "route_optimizer", "RouteOptimizer")
        self.rag             = self._init_ml_service("Ollama", "rag_service", "RAGService")
        self._ml_available    = True

        # ── Gemini / Hibrit modu (opsiyonel) ──────────────────────────────
        # USE_GEMINI=true  → Sadece Gemini (NER + Vision + RAG yerine tek API)
        # USE_HYBRID=true  → Gemini + klasik BERT NER paralel, sonuçlar birleştirilir
        # Her ikisi false → Tamamen klasik ML pipeline (BERT, YOLO, Whisper, RAG)
        # Nominatim geocoding + outlier filter + TSP her durumda çalışır
        self._use_hybrid = os.getenv("USE_HYBRID", "false").lower() == "true"
        self._use_gemini = self._use_hybrid or os.getenv("USE_GEMINI", "false").lower() == "true"

        if self._use_gemini:
            self.gemini = self._init_ml_service("Gemini", "gemini_service", "GeminiService")
            mode = "🔀 HİBRİT" if self._use_hybrid else "🤖 GEMINI"
            logger.info("%s modu AKTİF (model=%s)",
                        mode, os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
        else:
            self.gemini = None
            logger.info("🔧 Klasik pipeline modu (Gemini devre dışı)")

    @classmethod
    def _init_ml_service(cls, label, module, class_name, **kwargs):
        from importlib import import_module
        return cls._try_init(label, lambda: getattr(import_module(f"app.ml.{module}"), class_name)(**kwargs))

    # ─────────────────────────────────────────────────────────────────────────
    # Ana pipeline
    # ─────────────────────────────────────────────────────────────────────────

    def _run_travel_tips(self, deduplicated_locations: List[Dict], video_id: int):
        """İpuçlarını üretir. Pipeline içinden de, ertelenmiş task'tan da çağrılır."""
        if self._use_gemini and self.gemini:
            tip_names = [loc.get("original_name", "") for loc in deduplicated_locations]
            return _safe_run(
                "Gemini(tips)",
                lambda: self.gemini.generate_travel_tips(tip_names, video_id=video_id) if tip_names else {},
                fallback={},
            )
        return _safe_run(
            "RAG",
            lambda: (
                self.rag.generate_travel_tips(deduplicated_locations)
                if deduplicated_locations else {}
            ),
            fallback={},
        )

    def generate_travel_tips(self, deduplicated_locations: List[Dict],
                             video_id: int) -> Dict:
        """
        Yalnızca seyahat ipuçlarını üretir — `defer_tips=True` ile çalışan
        pipeline'ın ardından çağrılmak üzere.

        Pipeline'daki `_safe_run` ile aynı graceful-degradation davranışını
        korur: hata olursa boş dict döner, çağıran task patlamaz.
        """
        return self._run_travel_tips(deduplicated_locations, video_id).data

    def process_video(self, video_path: str, video_id: int,
                      defer_tips: bool = False) -> Dict:
        """
        Video → AI pipeline → sonuç dict.

        Graceful degradation garantisi:
          Her AI aşaması try/except ile sarılmıştır.
          Herhangi bir hata → fallback değer, işlem devam eder.

        Args:
            defer_tips: True ise seyahat ipuçları üretilmez ve sonuçtaki
                `travel_tips` boş döner. Çağıran, video COMPLETED olduktan
                sonra `generate_travel_tips` ile ayrıca üretmelidir —
                kullanıcıyı ~6 saniye daha az bekletir.
        """
        if not self._ml_available:
            raise RuntimeError("ML servisleri mevcut değil — Docker ortamında çalıştırın")

        import ffmpeg  # noqa: F401 — Docker'da her zaman mevcut
        start_time = time.perf_counter()
        degradation_log: List[ServiceResult] = []

        logger.info("🎬 Video işleme başlıyor | video_id=%s | path=%s", video_id, video_path)

        # ── 1. Metadata ───────────────────────────────────────────────────────
        set_progress(video_id, "metadata", 5)
        metadata = timed_stage("media_metadata", lambda: self._get_metadata(video_path))     # kritik — hata fırlatır
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
        frames    = timed_stage("media_frames", lambda: self._extract_frames(video_path, frame_dir, fps=adaptive_fps))
        thumbnail = timed_stage("media_thumbnail", lambda: self._create_thumbnail(frames[0] if frames else None))
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
        specs = [
            StageSpec("YOLO", lambda: self.detector.detect_objects_in_frames(frames), [], 180),
            StageSpec("Vision", lambda: self.vision_detector.detect_landmarks_in_frames(frames[:5]), [], 120),
            StageSpec("OCR", lambda: self.ocr.extract_text_from_frames(frames), [], 180),
        ]
        if run_whisper:
            specs.append(StageSpec("Whisper", lambda: self.audio_processor.process_video_audio(video_path, video_id), None, 300))
        results = run_parallel(specs)
        r_yolo, r_vision, r_ocr = results[:3]
        r_whisper = results[3] if run_whisper else ServiceResult("Whisper(skipped/gemini)", None, True)

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

            # Aynı video daha önce işlendiyse Gemini'yi hiç çağırma — hem
            # sonuç birebir aynı olur (determinizm) hem kota harcanmaz.
            content_hash = _video_content_hash(video_path)
            cached_locations = _gemini_cache_get(content_hash)

            if cached_locations is not None:
                logger.info("⚡ Gemini lokasyon cache hit (%s…) — %d lokasyon",
                            (content_hash or "")[:12], len(cached_locations))
                r_gemini = ServiceResult(
                    name="Gemini(locations,cached)",
                    data=cached_locations,
                    success=True,
                )
            else:
                logger.info("🤖 Gemini lokasyon çıkarma başlıyor…")
                r_gemini = _safe_run(
                    "Gemini(locations)",
                    lambda: self.gemini.extract_locations(
                        frames, transcript_text,
                        video_id=video_id,
                        # Ekran yazıları: Gemini seyrek frame örneklemesi yüzünden
                        # bunları göremiyor, OCR ise okuyor. Bkz. extract_locations.
                        ocr_texts=extracted_texts,
                    ),
                    fallback=[],
                )
                # Yalnızca başarılı çıktıyı cache'le — fallback boş listeyi
                # kalıcılaştırmak, geçici bir 429'u kalıcı bir hataya çevirirdi.
                if r_gemini.success and not r_gemini.fallback_used:
                    _gemini_cache_set(content_hash, r_gemini.data or [])

            # Gemini artık {"region": {...}, "locations": [{"name","type","city"}]}
            # döndürüyor — koordinat YOK. normalize_extraction eski formatları
            # (koordinatlı liste, düz string listesi) da bu şekle indirger.
            gemini_result = self.gemini.normalize_extraction(r_gemini.data)
            gemini_region = gemini_result["region"]
            gemini_raw: List[Dict] = gemini_result["locations"]
            degradation_log.append(r_gemini)
            logger.info("🤖 Gemini: %d lokasyon, bölge=%s/%s",
                        len(gemini_raw),
                        gemini_region.get("city") or "?",
                        gemini_region.get("country_code") or "?")

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
                            "name": loc, "type": "place",
                            # BERT sadece isim verir; şehri bilmiyoruz →
                            # çözümleme videonun genel bölgesine düşer.
                            "city": None, "source": "bert_ner",
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
            gemini_region: Dict = {}
            gemini_raw: List[Dict] = []
            regions: Dict = {}

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

        # Bölge ipucu artık Gemini'den geliyor. Eskiden `_detect_city_from_list`
        # ile HARDCODE bir Türkiye şehirleri kümesine bakılıyordu; Barselona ya
        # da Tiflis'ten gelen bir Reels'te o liste hiçbir zaman eşleşmiyordu ve
        # geocoding bölgesiz — yani dünya genelinde ilk benzeyen isme — kalıyordu.
        gemini_city_hint    = gemini_region.get("city")
        gemini_country_code = gemini_region.get("country_code")
        if self._use_gemini:
            logger.info("🌍 Gemini bölge: şehir='%s' ülke='%s' (%s)",
                        gemini_city_hint or "?",
                        gemini_region.get("country") or "?",
                        gemini_country_code or "?")

        # ── ÇÖZÜMLEME (resolve): isim → gerçek konum ─────────────────────────
        #
        # Gemini artık koordinat vermiyor (bkz. gemini_service._LOCATIONS_SCHEMA).
        # HER isim coğrafi veritabanından çözülüyor — böylece plandaki her
        # koordinatın arkasında gerçek bir gazetteer kaydı oluyor.
        #
        # Aramalar mekanın kendi şehrine göre gruplanır: tek bir videoda birden
        # fazla şehir gezilebiliyor ve hepsini tek bir city_hint'e zorlamak
        # (eski davranış) ikinci şehirdeki mekanları yanlış yere çekiyordu.
        # Empty extraction has no resolved region; it must still complete.
        regions: Dict = {}
        if self._use_gemini and gemini_raw:
            by_city: Dict[str, List[str]] = {}
            for item in gemini_raw:
                hint = (item.get("city") or gemini_city_hint or "").strip()
                by_city.setdefault(hint, []).append(item["name"])

            # Her grubun sınırı ARAMADAN ÖNCE çözülüyor. Bu, "önce yanlış bul
            # sonra düzelt" (_fix_geographic_outliers) sıralamasının yerine
            # geçiyor — bkz. PlacesService.resolve_region'daki gerekçe.
            r_regions = _safe_run(
                "RegionResolve",
                lambda: {
                    hint: self.places.resolve_region(
                        city=hint or None,
                        country=gemini_region.get("country"),
                        country_code=gemini_country_code,
                        # Videonun baskın şehri üst bağlam olarak veriliyor:
                        # ilçe adları ülke genelinde tekil değil.
                        parent=gemini_city_hint,
                    )
                    for hint in by_city
                },
                fallback={},
            )
            regions: Dict = r_regions.data or {}
            degradation_log.append(r_regions)

            ner_enriched: List = []
            for hint, names in by_city.items():
                region  = regions.get(hint) or {}
                bbox    = region.get("bbox")
                if not bbox:
                    # Bölge çözülemedi → kısıtsız ara. Kötü ama hiç aramamaktan
                    # iyi; sonuçlar aşağıdaki outlier filtresine kalıyor.
                    logger.warning("⚠️ '%s' için bölge sınırı yok, arama kısıtsız yapılacak",
                                   hint or "bölgesiz")
                r_ner_geo = _safe_run(
                    f"Geocoding(NER,{hint or 'bölgesiz'})",
                    # Varsayılan argümanlar geç bağlanmayı (late binding) önlüyor:
                    # lambda döngü bittikten sonra çağrılırsa son grubu değil
                    # kendi grubunu kullansın.
                    lambda names=names, hint=hint, bbox=bbox: self.places.enrich_locations(
                        names,
                        use_overpass=True,
                        city_bbox=bbox,
                        city_hint=hint or None,
                        country_code=gemini_country_code,
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

        # City bounding box (Overpass isabetini artırır).
        # Çözülmüş bölge sınırı varsa onu kullan — `_extract_city_bbox` ilk
        # lokasyonun etrafına körlemesine ±2° (~220 km) koyuyor ve o lokasyon
        # yanlış geocode edilmişse kutu da yanlış yere oturuyor.
        primary_region = next((r for r in (regions or {}).values() if r and r.get("bbox")), None) \
            if self._use_gemini else None
        city_bbox = (primary_region or {}).get("bbox") or self._extract_city_bbox(ner_enriched)
        # City hint: "Nohut Durumu Gaziantep" gibi qualifier aramaları için
        city_hint = self._extract_city_hint(ner_enriched)
        if city_hint:
            logger.info("🏙️ City hint: '%s'", city_hint)

        # OCR POI'larını zenginleştir
        set_progress(video_id, "overpass", 75)
        ocr_enriched = self._enrich_ocr_pois(ocr_pois, city_bbox, degradation_log, city_hint=city_hint)

        # Vision landmarks → zenginleştirilmiş formata çevir
        vision_enriched = self._convert_vision_landmarks(vision_landmarks)

        # ── ÇÖZÜLEMEYEN MEKANLAR ─────────────────────────────────────────────
        #
        # Coğrafi veritabanı bu isimleri bulamadı (Nominatim'in POI kapsamı
        # zayıf: "Ciğerci Aziz Usta", "Safi Künefe" hiç yok). Mekanı LİSTEDEN
        # ATMIYORUZ — video gerçekten oradan bahsediyor, kullanıcı görmeli.
        #
        # Ama koordinatını da UYDURMUYORUZ. Şehir merkezine düşen pin artık
        # precision="approximate" ile işaretleniyor ve arayüz bunu kullanıcıya
        # söyleyebiliyor. Tatil planında sessizce yanlış bir noktaya
        # yönlendirmek "bulamadım" demekten daha zararlı: kullanıcı 30 km
        # öteye gidiyor ve hatayı ancak oraya varınca anlıyor.
        if self._use_gemini and extracted_locations:
            enriched_names = {
                e["original_name"].lower().strip() for e in ner_enriched
            }
            # Yaklaşık pin için ŞEHİR MERKEZİ tercih ediliyor, bölge merkezi
            # değil. `primary_region` artık idari sınırdan geliyor (arama
            # kutusunu geniş tutmak için, bkz. prefer_area) ve onun merkezi
            # ilin coğrafi ağırlık noktası — Gaziantep'te şehrin 11 km
            # güneyine düşüyor. Kullanıcıya "yaklaşık" bir pin gösterecekse
            # en makul nokta şehrin kendisi.
            #
            # NOT: bilerek ner_enriched[0] alınmıyor. Sıradaki ilk eleman şehir
            # olmayabilir (örn. ülke adı veya yanlış geocode edilmiş bir POI) —
            # o zaman alakasız bir koordinata pin basmak yerine bu lokasyonu
            # tamamen atlıyoruz (aşağıdaki `if city_coords:`).
            city_entry = next(
                (e for e in ner_enriched
                 if (e.get("place_data") or {}).get("type") in ("city", "town", "administrative")),
                None,
            )
            city_coords = (city_entry or {}).get("place_data", {}).get("location") if city_entry else None

            if not city_coords and primary_region and primary_region.get("center"):
                r_lat, r_lng = primary_region["center"]
                city_coords = {"lat": r_lat, "lng": r_lng}
            fallback_city = gemini_city_hint or city_hint or ""

            approximate = 0
            dropped: List[str] = []

            for loc in extracted_locations:
                if loc.lower().strip() in enriched_names:
                    continue  # zaten çözüldü
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
                            # `gemini_` öneki dedup'ta "adı güven, koordinatı
                            # güvenme" kuralını tetikliyor — bu kayıtların hepsi
                            # AYNI koordinatta olduğu için mesafe kontrolü
                            # hepsini tek mekana indirirdi.
                            # Bkz. LocationDeduplicator.deduplicate_locations.
                            "source":     "gemini_unresolved",
                            "precision":  "approximate",
                        },
                    })
                    approximate += 1
                    logger.info("📍 Çözülemedi, yaklaşık konum: '%s' → %s merkezi",
                                loc, fallback_city)
                else:
                    dropped.append(loc)

            if approximate:
                logger.warning(
                    "⚠️ %d mekan coğrafi veritabanında bulunamadı — "
                    "şehir merkezi koordinatıyla 'yaklaşık' işaretlendi", approximate)
            if dropped:
                logger.warning(
                    "⚠️ %d mekan hem çözülemedi hem de şehir merkezi bilinmiyor, "
                    "listeye alınmadı: %s", len(dropped), dropped)

        enriched_locations = ner_enriched + ocr_enriched + vision_enriched

        # Konum kalitesi etiketi. Yukarıda "approximate" olarak işaretlenmemiş
        # her kayıt gerçek bir gazetteer eşleşmesinden geliyor (Nominatim,
        # Overpass, Vision landmark) — setdefault mevcut etiketi ezmez.
        for entry in enriched_locations:
            (entry.get("place_data") or {}).setdefault("precision", "exact")

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
        # ─────────────────────────────────────────────────────────────────────
        set_progress(video_id, "dedup", 85)

        # Gemini modunda mesafe eşiği çok küçük tutuluyor: şehir merkezindeki
        # mekanlar birbirine yüzlerce metre uzaklıkta ve hepsi ayrı duraklar
        # (Elmacı Pazarı ↔ Gümrük Hanı gibi). Gerçek tekrarları ad ve kök
        # eşleşmesi yakalıyor, mesafe değil.
        # Klasik pipeline: 2km korunur (NER+OCR+Vision aynı yeri tekrar üretir).
        #
        # NOT: koordinatlar artık Gemini'den değil gazetteer'dan geliyor, yani
        # bu eşik yeniden değerlendirilebilir — ama tek seferde tek değişken:
        # önce çözümleme ayrımının etkisi ölçülsün.
        if self._use_gemini:
            dedup_threshold = 0.001  # 1 metre
        else:
            dedup_threshold = 2.0    # 2 km

        # Çözülemeyen kayıtlar (source="gemini_unresolved") mesafe kontrolünden
        # muaf — hepsi aynı şehir merkezi koordinatını paylaştığı için mesafe
        # onları tek mekana indirirdi. Ad ve kök eşleşmesi onlarda da çalışır.
        # Bkz. LocationDeduplicator.deduplicate_locations.
        from app.ml.location_deduplicator import LocationDeduplicator
        deduplicator = LocationDeduplicator(distance_threshold_km=dedup_threshold)

        r_dedup = _safe_run(
            "Dedup",
            lambda: deduplicator.deduplicate_locations(enriched_locations),
            fallback=enriched_locations,
        )
        deduplicated_locations: List = r_dedup.data

        # `deduplicated_locations` veriliyor, ham liste değil: özet kullanıcının
        # gördüğü duraklarla birebir aynı olmalı. (get_location_summary kendi
        # içinde tekrar dedup çalıştırır — saf hesaplama, zaten temiz veride
        # sonucu değiştirmez.)
        #
        # Buraya eskiden tanımsız bir `geocoded_locs` veriliyordu; NameError'ı
        # _safe_run yutup fallback={} döndürdüğü için location_summary sessizce
        # hep boş kaydediliyordu. Pipeline'ın "hata yutma" tasarımının bedeli:
        # bir yazım hatası aylarca sessiz veri kaybı olarak yaşayabiliyor.
        r_loc_summary = _safe_run(
            "LocSummary",
            lambda: deduplicator.get_location_summary(deduplicated_locations),
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
        # `defer_tips=True` ise burada üretilmez — kullanıcının sonucu görmesi
        # için ipuçları gerekmiyor ve bu adım ölçümde ~6s tutuyordu. Çağıran
        # (video_tasks) videoyu COMPLETED işaretledikten SONRA ayrı bir task ile
        # üretip kaydeder.
        if defer_tips:
            travel_tips: Dict = {}
            logger.info("💡 Seyahat ipuçları ertelendi — ayrı task üretecek")
        else:
            set_progress(video_id, "rag", 95)
            r_rag = self._run_travel_tips(deduplicated_locations, video_id)
            travel_tips = r_rag.data
            degradation_log.append(r_rag)

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
            "stages": [{"name": r.name, "duration_s": round(r.duration_s, 4),
                        "status": "fallback" if r.fallback_used else "success"}
                       for r in degradation_log if "skipped" not in r.name],
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
