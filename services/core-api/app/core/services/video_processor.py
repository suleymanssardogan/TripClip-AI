from pathlib import Path
import uuid
import re as _re
from difflib import SequenceMatcher
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
import json as _json

# Redis progress store (opsiyonel — bağlantı yoksa atla)
try:
    import redis as _redis
    _progress_redis = _redis.Redis(host="redis", port=6379, db=1, decode_responses=True)
    _progress_redis.ping()
except Exception:
    _progress_redis = None


def _set_progress(video_id: int, stage: str, percent: int):
    """İşlem aşamasını Redis'e yaz (API üzerinden polling yapılabilir)"""
    if _progress_redis:
        try:
            _progress_redis.setex(
                f"progress:{video_id}",
                600,   # 10 dk TTL
                _json.dumps({"stage": stage, "percent": percent})
            )
        except Exception:
            pass


logger = logging.getLogger(__name__)

class VideoProcessingService:
    """Video processing: metadata,frames,thumbnails"""

    def __init__(self):
        self.frames_dir = Path("/app/uploads/frames")
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        # Hız: video uzunluğuna göre adaptif FPS seçimi
        self.base_fps = 0.25   # her 4 saniyede 1 frame (0.5'ten düşürüldü)

        # ML servisleri — lazy import (test ortamında kurulu olmayabilir)
        try:
            import ffmpeg as _ffmpeg_module  # noqa: F401 — varlık kontrolü
            from app.ml.computer_vision import ObjectDetectionService, LandmarkDetectionService
            from app.ml.ocr_service import OCRService
            from app.ml.speech_to_text import AudioProcessingService
            from app.ml.ner_service import NERService
            from app.ml.places_service import PlacesService
            from app.ml.location_deduplicator import LocationDeduplicator
            from app.ml.qdrant_service import QdrantService
            from app.ml.route_optimizer import RouteOptimizer
            from app.ml.rag_service import RAGService
            self.detector = ObjectDetectionService()
            self.vision_detector = LandmarkDetectionService()
            self.ocr = OCRService()
            self.audio_processor = AudioProcessingService()
            self.ner = NERService()
            self.places = PlacesService()
            self.deduplicator = LocationDeduplicator(distance_threshold_km=2.0)
            self.qdrant = QdrantService()
            self.route_optimizer = RouteOptimizer()
            self.rag = RAGService()
            self._ml_available = True
        except ImportError as e:
            logger.warning(f"ML servisleri yüklenemedi (test modu?): {e}")
            self._ml_available = False


    
    def process_video(self, video_path: str, video_id: int) -> Dict:
        """
        Videoyu İşle
        1. Metadata çıkar
        2. Frame'leri extract et
        3. Thumbnail oluştur
        4. Google Vision: Landmark Detection
        5. Text Exraction (OCR)
        """
        if not self._ml_available:
            raise RuntimeError("ML servisleri mevcut değil — Docker ortamında çalıştırın")

        import ffmpeg  # Docker'da her zaman mevcut

        start_time = time.time()
        try:
            logger.info(f"Processing video {video_id}")
            _set_progress(video_id, "metadata", 5)

            # 1. Video Metadata
            metadata = self._get_metadata(video_path)
            logger.info(f"Metadata: {metadata}")

            # 2. Frame Extraction
            frame_dir = self.frames_dir / str(video_id)
            duration = metadata["duration"]
            # Kısa liste videoları hızla değişen metin overlay'leri içerir → yoğun örnekleme
            adaptive_fps = 2.0 if duration < 20 else (1.0 if duration < 60 else (0.5 if duration < 120 else 0.25))
            _set_progress(video_id, "frames", 10)
            frames = self._extract_frames(video_path, frame_dir, fps=adaptive_fps)
            logger.info(f"Extracted {len(frames)} frames at {adaptive_fps}fps")

            # 3. Thumbnail
            thumbnail = self._create_thumbnail(frames[0] if frames else None)

            t_frames = time.time()
            logger.info(f"⏱ Frame extraction: {t_frames - start_time:.1f}s")

            # ── PARALEL AŞAMA: Vision + OCR + Audio aynı anda ─────────────────
            # Her biri farklı kaynak kullandığından paralel çalıştırmak güvenli:
            #   Vision  → YOLOv8 (CPU) + Google API (IO)
            #   OCR     → EasyOCR (CPU)
            #   Audio   → Whisper (CPU) + FFmpeg (IO)
            _set_progress(video_id, "ai_parallel", 20)
            logger.info("🚀 Paralel AI aşaması başlıyor (Vision + OCR + Audio)...")

            with ThreadPoolExecutor(max_workers=3) as pool:
                f_detect  = pool.submit(self.detector.detect_objects_in_frames, frames)
                f_vision  = pool.submit(self.vision_detector.detect_landmarks_in_frames, frames[:5])
                f_ocr     = pool.submit(self.ocr.extract_text_from_frames, frames)
                f_audio   = pool.submit(self.audio_processor.process_video_audio, video_path, video_id)

                detections       = f_detect.result()
                vision_landmarks = f_vision.result()
                extracted_texts  = f_ocr.result()
                transcription    = f_audio.result()

            detections = self.detector.remove_duplicate_detections(detections)
            landmarks  = self.detector.get_landmark_candidates(detections)
            summary    = self.detector.get_detection_summary(detections)
            t_parallel = time.time()
            logger.info(f"⏱ Paralel AI (Vision+OCR+Whisper): {t_parallel - t_frames:.1f}s")
            logger.info(f"✅ Paralel AI tamamlandı — OCR: {len(extracted_texts)} metin, "
                        f"Vision: {len(vision_landmarks)} landmark")

            # 7. NER: sadece audio transcript üzerinden lokasyon çıkar
            # OCR metinleri zaten display_pois pipeline'ından geçiyor — NER'e de
            # verilirse 7+ tekrar lokasyon çıkıyor ve geocoding 2x yavaşlıyor.
            _set_progress(video_id, "ner", 55)
            extracted_locations = []
            transcript_text = (transcription.get("transcript", "") if transcription else "").strip()
            if transcript_text:
                extracted_locations = self.ner.extract_locations_from_transcript(transcript_text)
                logger.info(f"NER ({len(transcript_text)} char transcript) → {len(extracted_locations)} lokasyon")

            # ── OCR POI filtreleme ──────────────────────────────────────────────

            def tr_lower(s: str) -> str:
                """Python .lower() İ→i\u0307 yapar (yanlış). Türkçe-doğru lowercase."""
                return s.replace("İ", "i").replace("I", "ı").lower()

            # Gürültü desenleri (URL, sosyal medya vs.)
            noise_patterns = {
                "www.", "http", "@", "#", ".com", ".tr", "₺", "$", "€",
                "follow", "like", "share", "subscribe", "abone", "takip",
            }

            # Türkçe sıradan / eksik kelimeler — filtrelenecek
            tr_stopwords = {
                # Eylem/sıfat kelimeleri
                "içecek", "yiyecek", "giriş", "çıkış", "bilgi", "lütfen", "teşekkür",
                "devam", "dikkat", "uyarı", "yasak", "serbest", "açık", "kapalı",
                "indirim", "fiyat", "menü", "sipariş", "ödeme", "nakit", "kart",
                "telefon", "adres", "saat", "tarih", "numara", "adet", "toplam",
                "olan", "olur", "oldu", "için", "ile", "veya", "hem", "ama",
                "büyük", "küçük", "yeni", "eski", "güzel", "iyi", "kötü",
                "başka", "diğer", "tüm", "her", "bazı", "çok", "az", "daha",
                # 2-3 harflik OCR çöpleri
                "dis", "bis", "ecs", "aci", "bey", "ecek", "acak", "mis",
                "yo", "ve", "da", "de", "ki", "mi", "mu", "mü",
                # Eksik isimler (Türkçe iyelik ekleri — tek başına anlamsız)
                "kahvesi", "çayı", "kebabı", "mantısı", "baklavası", "köftesi",
                "pidesi", "böreği", "tatlısı", "döneri", "lahmacunu", "çorbası",
                "büfesi", "fırını", "pastanesi", "lokantası", "restoranı",
                # Büyük şehirler NER'den gelsin, OCR'dan değil
                "istanbul", "ankara", "izmir",
                # Menü / tabela / sosyal medya kelimeleri
                "market", "deneme", "gerekenler", "durumu", "masaya", "masasi",
                "lutfen", "yiyecek", "icecek", "siparis", "ucretsiz", "ucret",
                "ntep", "disin", "disi", "bufe", "bufesi",
            }

            # Mekan türü sinyal kelimeleri (tarihi/turistik/doğa)
            geo_signals = {
                "han", "kafe", "cafe", "restoran", "müze", "cami", "kilise",
                "köprü", "kale", "kalesi", "kaleici", "sarayı", "parkı", "gölü",
                "plajı", "plaji",         # ASCII-OCR varyantı (ı→i)
                "şelalesi", "selalesi",   # ASCII-OCR varyantı
                "mağarası", "magarasi", "tepesi", "dağı", "dagi", "vadisi",
                "konak", "çarşı", "carsi", "pazar", "hamam", "türbe", "turbe",
                "anıt", "anit", "kervansaray", "ören",
                "sokağı", "sokagi", "mahallesi", "kapısı", "kapisi",
                "kulesi", "camii", "hamamı", "hamami",
                "bahçesi", "bahcesi", "ormanı", "ormani", "göleti", "barajı",
                "köprüsü", "koprüsü",
                # Doğal coğrafya
                "koyu", "körfez", "korfez", "limanı", "limani",
                "kayalığı", "kayaligi", "adası", "adasi", "yarımadası",
                "kanyonu", "platosu", "göleti", "çayı", "cayi", "irmağı",
                "yaylası", "yaylasi", "milliparkı",
                # Ören / tarihi
                "harabeleri", "höyüğü", "hoyugu", "mezarlığı", "mezarligi",
                "kilisesi", "manastırı", "manastiri", "kalıntıları",
            }

            def _ascii_fold(s: str) -> str:
                """OCR hatalarını tolere etmek için Türkçe → ASCII dönüşümü."""
                return (s.replace("ğ", "g").replace("ü", "u").replace("ş", "s")
                         .replace("ı", "i").replace("ö", "o").replace("ç", "c")
                         .replace("â", "a").replace("î", "i").replace("û", "u"))

            def _has_geo_signal(text: str) -> bool:
                """Geo sinyal içeriyor mu? ASCII-fold ile OCR ı→i hatalarını tolere eder."""
                t_l = tr_lower(text)
                if any(s in t_l for s in geo_signals):
                    return True
                # Geo sinyal ASCII-folded olarak da dene
                t_f = _ascii_fold(t_l)
                if any(_ascii_fold(s) in t_f for s in geo_signals):
                    return True
                return False

            # İşletme türü sinyal kelimeleri (Nominatim'e gönderilmez, sadece gösterimde)
            biz_signals = {
                "dürümcü", "kebapçı", "pideci", "börekçi", "çorbacı", "tatlıcı",
                "fırın", "pastane", "büfe", "lokanta", "ocakbaşı", "mangal",
                "kahveci", "kahvesi", "çaycı", "çayevi", "nargile",
                "berber", "kuaför", "eczane", "market", "bakkal",
                "otel", "pansiyon", "apart",
            }

            all_poi_signals = geo_signals | biz_signals

            # Video overlay / açıklama kalıpları — mekan ismi değil
            # NOT: Şehir adı hardcode edilmez; kalıp herhangi bir kelimeyle çalışır.
            # Türkçe büyük→küçük dönüşümü regex'ten önce yapılır (t_l üzerinde çalışır).
            description_patterns = [
                r"\d+\s*(yer|tane|adet|durak|mekan|kafe|sahil|plaj)",
                # "[ŞEHİR]'DA/DE/TA/TE GEZİLECEK" — apostrof/tırnak olsun olmasın
                # "antalya'da gezilecek", "istanbul da gezilecek", "da gezilecek"
                r"\w+['\u2018\u2019]?\s*(?:da|de|ta|te)\s+gezilecek",
                r"(?:da|de|ta|te)\s+gezilecek",   # bare "da gezilecek"
                r"(en iyi|mutlaka|kesinlikle|illa)",
                r"(gidilecek|gorilecek|gorulebilecek)",
                r"(yenilecek|icilecek|icekilecek)",
                r"(nasil|nerede|nereden|hangi)",
                r"(bolum|part|episode|vlog|video)",
                r"\d+\.\s*(bolum|part|video)",
                # Genel başlık/liste kalıpları
                r"gezilecek",          # "gezilecek" geçen her şey → başlık
                r"(listesi|rehberi|onerileri|tavsiyeleri)",
                r"(top\s*\d+|en\s+iyi\s+\d+)",
            ]
            desc_regexes = [_re.compile(p, _re.IGNORECASE) for p in description_patterns]

            def is_noise(t: str) -> bool:
                t_l = tr_lower(t).strip()
                t_orig = t.strip()
                if len(t_l) < 4: return True
                if t_l.replace(" ", "").isnumeric(): return True
                if t_l.endswith(("?", "-", ":", ".", ",")): return True
                if t_l.startswith(("-", ".", ":")): return True
                if any(p in t_l for p in noise_patterns): return True
                if t_l in tr_stopwords: return True
                # Sosyal medya kullanıcı adı: alt çizgi içeriyorsa (bayramyildiz_)
                if "_" in t_orig: return True
                # Sayı + birim kalıbı: "16 YER", "3 TANE"
                tokens = t_l.split()
                if tokens and tokens[0].isnumeric(): return True
                # Video başlığı / açıklama kalıbı
                if any(r.search(t_l) for r in desc_regexes): return True
                # Çok kısa tokenlar: "EMİZ YO", "VE i"
                short_tokens = [tok for tok in tokens if len(tok) <= 2 and tok not in {"ve", "da", "de", "ya"}]
                if len(tokens) > 0 and len(short_tokens) / len(tokens) > 0.5: return True
                # Tek kelime ALL-CAPS kısa
                if t_orig.isupper() and len(t_l) < 6 and len(tokens) == 1: return True
                return False

            # ── Liste 1: Gösterim POI'ları ────────────────────────────────────
            # Karar hiyerarşisi (sırayla):
            #   1. NER modeli LOC/GPE dedi → kesinlikle yer ismi
            #   2. Geo/biz sinyal kelimesi var → muhtemelen yer ismi
            #   3. 2+ kelime + gürültü değil → muhtemelen yer ismi (fallback)

            # Tek başına anlamsız olan generic tip kelimeleri ("Koyu", "Plaj" gibi)
            # yer ismi değil, sınıflandırıcı kelimedir — geocoding'e gönderilmez.
            generic_type_words = {
                "koyu", "koy", "plaj", "plaji", "sahil", "dağ", "dag", "gol", "göl",
                "şelale", "selale", "orman", "vadi", "kanyon", "tepe", "kale",
                "cami", "camii", "köy", "koy", "mahalle", "sokak", "cadde",
                "park", "bahçe", "bahce", "ada", "kıyı", "kiyi", "liman",
            }

            def _split_camelcase(t: str) -> str:
                """ManavgatSelalesi → Manavgat Selalesi (OCR boşluk atlama düzeltmesi)"""
                # küçük→BÜYÜK sınırı: "gatSe" → "gat Se"
                t = _re.sub(r'([a-zğüşıöç])([A-ZĞÜŞİÖÇ])', r'\1 \2', t)
                # BÜYÜK→BÜYÜK+küçük: "SELAlesi" gibi durumlar
                t = _re.sub(r'([A-ZĞÜŞİÖÇ]{2,})([A-ZĞÜŞİÖÇ][a-zğüşıöç])', r'\1 \2', t)
                return t.strip()

            def _norm_for_dedup(t: str) -> str:
                """Fuzzy dedup için: boşluk + noktalama kaldır, tr_lower uygula."""
                return _re.sub(r'[^a-z0-9ğüşıöç]', '', tr_lower(t))

            def _is_fuzzy_dup(t: str, seen_norms: list) -> bool:
                """Benzer metinleri fuzzy eşleştir (OCR hatalarına karşı)."""
                norm = _norm_for_dedup(t)
                if len(norm) < 4:
                    return False
                for s in seen_norms:
                    ratio = SequenceMatcher(None, norm, s).ratio()
                    if ratio >= 0.82:
                        return True
                return False

            # ── Aşama 1: Noise filtresi + dedup (hızlı) ─────────────────────────
            candidate_pois = []
            seen_display = set()
            seen_norms: list = []

            if extracted_texts:
                for t in extracted_texts:
                    t_clean = _split_camelcase(t.strip())
                    t_lower = tr_lower(t_clean)
                    if is_noise(t_clean): continue
                    if t_lower in seen_display: continue
                    if _is_fuzzy_dup(t_clean, seen_norms): continue
                    words = t_clean.split()
                    if len(words) == 1 and t_lower in generic_type_words:
                        continue
                    seen_display.add(t_lower)
                    seen_norms.append(_norm_for_dedup(t_clean))
                    candidate_pois.append(t_clean)

            # ── Aşama 2: Batch NER filtresi (1 inference — hardcode yok) ─────────
            # Tüm adaylar tek seferde NER'den geçer. Model LOC/GPE olmayanları atar.
            # "LUTFEN BU MASAYA" → LOC değil → atılır (video bağımsız, genellenebilir)
            # "Duden Selalesi"   → LOC       → geçer
            #
            # Fallback: NER modeli ASCII Türkçe ("Goynuk" yerine "Göynük") isimlerini
            # düşük skorda ret edebilir. Sıfır sonuçta geo_signal heuristic devreye girer.
            MAX_DISPLAY_POIS = 18
            if candidate_pois:
                _set_progress(video_id, "ner_ocr", 58)
                ner_filtered = self.ner.filter_locations_from_ocr(candidate_pois)
                if ner_filtered:
                    display_pois = ner_filtered[:MAX_DISPLAY_POIS]
                    logger.info(f"NER batch filter: {len(candidate_pois)} → {len(display_pois)} POI")
                else:
                    # NER hiçbir şey döndürmedi (ASCII OCR veya model belirsizliği).
                    # Heuristic fallback: geo sinyal içeren VEYA 2+ kelimeli adlar.
                    display_pois = [
                        t for t in candidate_pois
                        if _has_geo_signal(t) or len(t.split()) >= 2
                    ][:MAX_DISPLAY_POIS]
                    logger.info(
                        f"NER batch: 0 sonuç → heuristic fallback: "
                        f"{len(candidate_pois)} aday → {len(display_pois)} POI"
                    )
            else:
                display_pois = []

            # Geriye dönük uyumluluk: ocr_pois = gösterim listesi
            ocr_pois = display_pois
            logger.info(f"OCR display POIs ({len(display_pois)}): {display_pois}")

            t_ner = time.time()
            logger.info(f"⏱ NER extraction: {t_ner - t_parallel:.1f}s")

            # 8. Nominatim: NER lokasyonlarını zenginleştir
            _set_progress(video_id, "geocoding", 65)
            ner_enriched = []
            if extracted_locations:
                logger.info(f"Enriching {len(extracted_locations)} NER locations...")
                ner_enriched = self.places.enrich_locations(extracted_locations)

            # City bounding box → Overpass araması daha isabetli olur
            city_bbox = None
            if ner_enriched:
                first_city = ner_enriched[0].get("place_data", {})
                if first_city.get("location"):
                    lat = first_city["location"]["lat"]
                    lng = first_city["location"]["lng"]
                    # Şehir etrafında ~220km box — Kaş (~190km) ve Alanya'yı kapsar
                    city_bbox = (lat - 2.0, lng - 2.0, lat + 2.0, lng + 2.0)
                    logger.info(f"City bbox for Overpass: {city_bbox}")

            # OCR POI'ları zenginleştir
            # Overpass community API rate limit var → sadece geo-sinyalli adları gönder.
            # Geo sinyal = fiziksel yer (plaj, koyu, şelale, cami...) belirten kelimeler.
            # Geo sinyali olmayan adlar (kafeler, çarşılar vb.) → sadece Nominatim.
            _set_progress(video_id, "overpass", 75)
            # ASCII-fold farkına karşı _has_geo_signal kullan
            overpass_pois  = [p for p in display_pois if _has_geo_signal(p)]
            nominatim_pois = [p for p in display_pois if not _has_geo_signal(p)]

            logger.info(f"OCR POI split → Overpass: {len(overpass_pois)}, "
                        f"Nominatim-only: {len(nominatim_pois)}")

            ocr_enriched = []
            if overpass_pois:
                ocr_enriched += self.places.enrich_locations(
                    overpass_pois, use_overpass=True, city_bbox=city_bbox
                )
            if nominatim_pois:
                ocr_enriched += self.places.enrich_locations(
                    nominatim_pois, use_overpass=False, city_bbox=city_bbox
                )

            # Vision landmarks'ı enriched formatına çevir
            vision_enriched = []
            for lm in vision_landmarks:
                if lm.get("latitude") and lm.get("longitude") and lm.get("confidence", 0) > 0.5:
                    vision_enriched.append({
                        "original_name": lm["name"],
                        "place_data": {
                            "name": lm["name"],
                            "location": {"lat": lm["latitude"], "lng": lm["longitude"]},
                            "type": "landmark",
                            "importance": lm["confidence"]
                        }
                    })

            # Tüm kaynakları birleştir (NER + OCR + Vision)
            enriched_locations = ner_enriched + ocr_enriched + vision_enriched
            logger.info(f"Total enriched: {len(ner_enriched)} NER + {len(ocr_enriched)} OCR + {len(vision_enriched)} Vision = {len(enriched_locations)}")

            t_geocode = time.time()
            logger.info(f"⏱ Geocoding (Nominatim+Overpass): {t_geocode - t_ner:.1f}s")

            # 9. Deduplication
            _set_progress(video_id, "dedup", 85)
            deduplicated_locations = []
            location_summary = {}
            if enriched_locations:
                deduplicated_locations = self.deduplicator.deduplicate_locations(enriched_locations)
                location_summary = self.deduplicator.get_location_summary(enriched_locations)

            # 10. Route Optimization
            _set_progress(video_id, "route", 90)
            optimized_route = {}
            if deduplicated_locations:
                optimized_route = self.route_optimizer.optimize_route(deduplicated_locations)

            # 11. RAG: Travel Tips
            _set_progress(video_id, "rag", 95)
            travel_tips = {}
            if deduplicated_locations:
                travel_tips = self.rag.generate_travel_tips(deduplicated_locations)
            
            # 12. Qdrant: Location embeddings
            if enriched_locations:
                try:
                    self.qdrant.add_locations(enriched_locations)
                    logger.info(f"✅ Added {len(enriched_locations)} locations to Qdrant")
                except Exception as e:
                    logger.warning(f"Qdrant error (non-critical): {e}")
            t_end = time.time()
            logger.info(f"⏱ Dedup+Route+RAG+Qdrant: {t_end - t_geocode:.1f}s")
            total_time = t_end - start_time
            logger.info(f"Performance: ")
            logger.info(f"Total Time: {total_time:.2f}s")
            logger.info(f" Frames/sec: {len(frames)/total_time:.2f}")
            logger.info(f" Time per frame: {total_time/len(frames):.2f}s")


            return{
                "duration": metadata["duration"],
                "resolution": f"{metadata['width']}x{metadata['height']}",
                "fps": metadata["fps"],
                "frame_count":len(frames),
                "frames_dir": str(frame_dir),
                "thumbnail": thumbnail,
                "detections_count": len(detections),
                "landmarks_count":len(landmarks),
                "processing_time": round(total_time,2),
                "fps_processed": round(len(frames)/total_time, 2),
                "vision_landmarks": vision_landmarks,
                "extracted_texts": extracted_texts,
                "transcription": transcription,
                "extracted_locations": extracted_locations,
                "enriched_locations": enriched_locations,
                "location_summary":location_summary,
                "deduplicated_locations": deduplicated_locations,
                "optimized_route": optimized_route,
                "travel_tips": travel_tips,
                "ocr_pois": ocr_pois,
                "top_objects": summary["top_5_classes"]
                

            }
        
        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            raise
    
    def _get_metadata(self, video_path: str) -> Dict:
        """FFmpeg ile metadata çıkar"""
        import ffmpeg
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next(
                s for s in probe['streams'] 
                if s['codec_type'] == 'video'
            )
            
            # FPS hesaplama (fraction olabilir)
            fps_str = video_stream.get('r_frame_rate', '30/1')
            fps_parts = fps_str.split('/')
            fps = float(fps_parts[0]) / float(fps_parts[1])
            
            return {
                "duration": float(probe['format']['duration']),
                "width": int(video_stream['width']),
                "height": int(video_stream['height']),
                "fps": round(fps, 2)
            }
        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")
            raise
    
    # Optimize edildi 1 fps 1 saniye idi şimdi her 2 saniyede 1 frame
    def _extract_frames(self, video_path: str, output_dir: Path, fps: int = 0.5) -> List[str]:
        """
        Video'dan frame'ler çıkar
        fps=1 → saniyede 1 frame
        """
        import ffmpeg
        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            # FFmpeg ile frame extraction
            (
                ffmpeg
                .input(video_path)
                .filter('fps', fps=fps)
                .output(
                    str(output_dir / 'frame_%04d.jpg'),
                    quality=2  # JPEG quality
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            # Extract edilen frame'lerin listesi
            frames = sorted(output_dir.glob('*.jpg'))
            return [str(f) for f in frames if f.name.startswith('frame_')]
        
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise
    
    def _create_thumbnail(self, first_frame: str) -> str:
        """İlk frame'den thumbnail oluştur (320px width)"""
        if not first_frame:
            return None

        import ffmpeg
        try:
            thumb_path = Path(first_frame).parent / "thumbnail.jpg"

            (
                ffmpeg
                .input(first_frame)
                .filter('scale', 320, -1)  # Width 320, height auto
                .output(str(thumb_path))
                .overwrite_output()
                .run(quiet=True)
            )
            
            return str(thumb_path)
        
        except Exception as e:
            logger.error(f"Thumbnail creation failed: {e}")
            return None
    
