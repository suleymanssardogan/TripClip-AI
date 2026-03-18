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
    
    def extract_entities(self, text: str) -> List[Dict]:
        """Extract named entities from text"""
        
        if not text or len(text.strip()) < 10:
            return []
        
        self._load_model()
        
        try:
            entities = self.model(text)
            
            locations = [
                {
                    "text": ent["word"],
                    "type": ent["entity_group"],
                    "score": round(ent["score"], 2)
                }
                for ent in entities
                if ent["entity_group"] in ["LOC", "GPE","ORG"]
                and ent["score"] > 0.6
            ]
            
            logger.info(f"Extracted {len(locations)} location entities")
            return locations
        
        except Exception as e:
            logger.error(f"NER extraction failed: {e}")
            return []
    
    def extract_locations_from_transcript(self, transcript: str) -> List[str]:
        """Extract unique locations from transcript"""
        
        if not transcript:
            return []
        
        entities = self.extract_entities(transcript)
        unique_locations = list(set([ent["text"] for ent in entities]))
        
        logger.info(f"Total unique locations: {len(unique_locations)}")
        return unique_locations