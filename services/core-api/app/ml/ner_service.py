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

    def is_location(self, text: str) -> bool:
        """
        Tek bir OCR satırının yer ismi olup olmadığını kontrol et.
        3+ karakter olan her metni NER modeline gönder.
        """
        text = text.strip()
        if not text or len(text) < 3:
            return False
        entities = self.extract_entities(text, min_len=3)
        return len(entities) > 0