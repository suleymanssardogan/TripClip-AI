"""
NER Service — Turkish BERT tabanlı yer ismi çıkarımı.

Performans notları:
  - Model ilk yüklemede ~30-60s sürer (CPU'da)
  - Yüklendikten sonra inference ~1-3s/batch
  - NER_TIMEOUT_SECONDS: model yüklenemez / inference takılırsa OCR fallback'e geçer
  - max_text_chars: BERT max 512 token → çok uzun metin parçalanır
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from transformers import pipeline
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

# NER için maksimum bekleme süresi — bu aşılırsa OCR heuristic devreye girer
NER_TIMEOUT_SECONDS = 45
# BERT max token ≈ 512 — güvenli karakter limiti
MAX_TEXT_CHARS = 1800


class NERService:
    """Named Entity Recognition for location extraction"""

    def __init__(self):
        self.model = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ner")
        logger.info("NERService initialized (lazy loading)")

    def _load_model(self):
        """Load NER model when needed (thread-safe lazy init)"""
        if self.model is None:
            logger.info("NER modeli yükleniyor (Turkish BERT)…")
            self.model = pipeline(
                "ner",
                model="savasy/bert-base-turkish-ner-cased",
                aggregation_strategy="simple",
            )
            logger.info("✅ NER modeli yüklendi")

    def _run_with_timeout(self, fn, *args, timeout: float = NER_TIMEOUT_SECONDS):
        """
        fn'i ayrı thread'de çalıştır, timeout aşılırsa None döner.
        BERT CPU inference takılırsa pipeline'ı bloke etmez.
        """
        future = self._executor.submit(fn, *args)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeout:
            logger.warning("⏰ NER %ds timeout aşıldı — OCR fallback'e geçiliyor", timeout)
            return None
        except Exception as e:
            logger.error("NER hata: %s", e)
            return None

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def extract_entities(self, text: str, min_len: int = 10) -> List[Dict]:
        """Metinden yer ismi entity'leri çıkar."""
        if not text or len(text.strip()) < min_len:
            return []

        def _infer():
            self._load_model()
            # BERT max token sınırı — kırp
            safe_text = text[:MAX_TEXT_CHARS]
            return self.model(safe_text)

        entities = self._run_with_timeout(_infer)
        if entities is None:
            return []

        ner_noise = {
            "dis", "bis", "yo", "aci", "mis", "bey", "ey", "ah",
            "bi", "bir", "bu", "şu", "o", "ne", "ki",
            # Dini ifadeler / ünlemler — yer ismi değil
            "ya", "allah", "valla", "vallah", "vay", "helal", "haram",
            "maşallah", "masallah", "inşallah", "insallah", "elhamdulillah",
            "subhanallah", "yok", "var", "ne", "evet", "hayır", "tamam",
        }
        locations = [
            {
                "text":  ent["word"],
                "type":  ent["entity_group"],
                "score": round(ent["score"], 2),
            }
            for ent in entities
            if ent["entity_group"] in ["LOC", "GPE"]
            and ent["score"] > 0.65
            and len(ent["word"]) >= 3
            and ent["word"].lower().strip() not in ner_noise
            and not ent["word"].startswith("##")
        ]
        logger.info("NER: %d entity çıkarıldı", len(locations))
        return locations

    def extract_locations_from_transcript(self, transcript: str) -> List[str]:
        """
        Transcript'ten benzersiz yer ve işletme isimleri — transkript NER.
        LOC/GPE: yer isimleri (score > 0.65)
        ORG: restoran/işletme adları (score > 0.80, en az 2 karakter, özel isim)
        """
        if not transcript:
            return []

        # LOC/GPE locations (standart)
        entities = self.extract_entities(transcript, min_len=10)
        found = set(ent["text"] for ent in entities)

        # ORG entities — restoran/işletme adları (yüksek eşik)
        def _infer_all():
            self._load_model()
            safe_text = transcript[:MAX_TEXT_CHARS]
            return self.model(safe_text)

        all_entities = self._run_with_timeout(_infer_all)
        if all_entities:
            # Türkçe dini/genel kelimeler ORG sayılmasın
            org_noise = {
                "allah", "bismillah", "türk", "türkiye", "türklerin",
                "devlet", "hükümet", "belediye", "bakanlık",
            }
            for ent in all_entities:
                if (
                    ent["entity_group"] == "ORG"
                    and ent["score"] > 0.80
                    and len(ent["word"]) >= 4
                    and not ent["word"].startswith("##")
                    and ent["word"].lower().strip() not in org_noise
                    # Baş harfi büyük olmayan ORG'ları atla (genellikle yanlış)
                    and ent["word"][0].isupper()
                ):
                    found.add(ent["word"])
                    logger.info("ORG (işletme) bulundu: '%s' (%.2f)", ent["word"], ent["score"])

        unique = list(found)
        logger.info("Transkript NER: %d benzersiz yer/işletme", len(unique))
        return unique

    def filter_locations_from_ocr(self, ocr_texts: List[str]) -> List[str]:
        """
        OCR metinlerini tek batch'te NER'den geçir → yer ismi olanları döndür.

        30 ayrı is_location() çağrısı yerine (30 × ~2s = 60s),
        tüm metinler birleştirilip 1 inference yapılır (~2-3s).

        Timeout aşılırsa orijinal listeyi döndürür (OCR heuristic fallback
        video_processor.py'de zaten devreye girer).
        """
        if not ocr_texts:
            return []

        # Çok uzun metni parçala — BERT max token
        separator = " [SEP] "
        combined  = separator.join(ocr_texts)[:MAX_TEXT_CHARS]

        def _infer():
            self._load_model()
            return self.model(combined)

        entities = self._run_with_timeout(_infer)
        if entities is None:
            # Timeout → tüm OCR listeyi geri ver, heuristic filtreler
            logger.warning("NER OCR filter timeout — heuristic'e düşüldü (%d metin)", len(ocr_texts))
            return ocr_texts

        # Türkçe dini/genel kelimeler ORG sayılmasın (extract_locations_from_transcript ile aynı liste)
        org_noise = {
            "allah", "bismillah", "türk", "türkiye", "türklerin",
            "devlet", "hükümet", "belediye", "bakanlık",
        }

        # OCR ASCII Türkçe içerebilir → LOC/GPE eşiği 0.50.
        # ORG (restoran/işletme adı — tabela metinlerinde çok yaygın, örn.
        # "Ciğerci Aziz Usta", "Şafi Künefe") daha önce hiç kabul edilmiyordu;
        # bu yüzden storefront/tabela POI'leri sessizce düşüyordu. Transcript
        # NER'deki (extract_locations_from_transcript) ORG eşiğiyle aynı mantık.
        found_words = set()
        for ent in entities:
            if ent["word"].startswith("##"):
                continue
            word = ent["word"]
            if (
                ent["entity_group"] in ("LOC", "GPE")
                and ent["score"] > 0.50
                and len(word) >= 3
            ):
                found_words.add(word.lower().strip())
            elif (
                ent["entity_group"] == "ORG"
                and ent["score"] > 0.65
                and len(word) >= 4
                and word.lower().strip() not in org_noise
            ):
                found_words.add(word.lower().strip())

        result = []
        for text in ocr_texts:
            words_lower = {w.lower().strip(".,!?'") for w in text.split()}
            if words_lower & found_words:
                result.append(text)

        logger.info("NER OCR filter: %d → %d yer ismi (timeout=%ds)",
                    len(ocr_texts), len(result), NER_TIMEOUT_SECONDS)
        return result
