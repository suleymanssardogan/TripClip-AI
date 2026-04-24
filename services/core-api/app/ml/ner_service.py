from transformers import pipeline
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class NERService:
    """Named Entity Recognition for location extraction"""
    
    def __init__(self):
        self.model = None
        logger.info("NERService initialized (lazy loading)")
    
    def _load_model(self):
        """Load NER model when needed"""
        if self.model is None:
            logger.info("Loading NER model (Turkish)...")
            
            self.model = pipeline(
                "ner",
                model="savasy/bert-base-turkish-ner-cased",
                aggregation_strategy="simple"
            )
            
            logger.info("NER model loaded!")
    
    def extract_entities(self, text: str, min_len: int = 10) -> List[Dict]:
        """Extract named entities from text"""

        if not text or len(text.strip()) < min_len:
            return []
        
        self._load_model()
        
        try:
            entities = self.model(text)
            
            # Kısa / gürültülü NER çıktılarını filtrele
            ner_noise = {
                "dis", "bis", "yo", "aci", "mis", "bey", "ey", "ah",
                "bi", "bir", "bu", "şu", "o", "ne", "ki",
            }
            locations = [
                {
                    "text": ent["word"],
                    "type": ent["entity_group"],
                    "score": round(ent["score"], 2)
                }
                for ent in entities
                if ent["entity_group"] in ["LOC", "GPE"]
                and ent["score"] > 0.65
                and len(ent["word"]) >= 3
                and ent["word"].lower().strip() not in ner_noise
                and not ent["word"].startswith("##")  # subword token
            ]
            
            logger.info(f"Extracted {len(locations)} location entities")
            return locations
        
        except Exception as e:
            logger.error(f"NER extraction failed: {e}")
            return []
    
    def extract_locations_from_transcript(self, transcript: str) -> List[str]:
        """Extract unique locations from transcript (ses metni için)"""
        if not transcript:
            return []
        entities = self.extract_entities(transcript, min_len=10)
        unique_locations = list(set([ent["text"] for ent in entities]))
        logger.info(f"Total unique locations: {len(unique_locations)}")
        return unique_locations

    def filter_locations_from_ocr(self, ocr_texts: List[str]) -> List[str]:
        """
        OCR metinlerini tek seferde NER'den geçir → yer ismi olanları döndür.

        30 ayrı is_location() çağrısı yerine (30 × ~2s = 60s),
        tüm metinler birleştirilip 1 inference yapılır (~2-3s).

        Model "LUTFEN BU MASAYA" → LOC değil (filtreler)
              "Duden Selalesi"   → LOC (geçer)
        """
        if not ocr_texts:
            return []

        self._load_model()

        # [SEP] ile ayır — model cümle sınırı olarak kullanır
        separator = " [SEP] "
        combined = separator.join(ocr_texts)

        try:
            entities = self.model(combined)

            # OCR girdisi ASCII Türkçe içerebilir ("Goynuk" yerine "Göynük").
            # Batch inference'da model güveni düşebilir → eşik 0.65→0.50.
            # Transcript NER'i daha katı (0.65) çalışır — bu OCR-özel fallback.
            found_words = {
                ent["word"].lower().strip()
                for ent in entities
                if ent["entity_group"] in ["LOC", "GPE"]
                and ent["score"] > 0.50          # ← 0.65'ten düşürüldü
                and len(ent["word"]) >= 3
                and not ent["word"].startswith("##")
            }

            logger.debug(f"NER found_words: {found_words}")

            # Orijinal metnin herhangi bir kelimesi NER entity olarak geçtiyse → yer ismi
            result = []
            for text in ocr_texts:
                words_lower = {w.lower().strip(".,!?'") for w in text.split()}
                if words_lower & found_words:
                    result.append(text)

            logger.info(f"NER OCR filter: {len(ocr_texts)} metin → {len(result)} yer ismi")
            return result

        except Exception as e:
            logger.error(f"NER OCR filter failed: {e}")
            # Hata durumunda orijinal listeyi döndür (daha iyi fallback)
            return ocr_texts