import easyocr
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class OCRService:
    """EasyOCR ile text extraction"""
    
    def __init__(self):
        """Initialize EasyOCR reader"""
        logger.info("Loading EasyOCR model (TR + EN)...")
        self.reader = easyocr.Reader(['tr', 'en'], gpu=False)
        logger.info("✅ EasyOCR initialized (TR + ENG)")
    
    def extract_text(self, image_path: str) -> List[Dict]:
        """Frame'den text çıkar"""
        try:
            results = self.reader.readtext(image_path)
            
            texts = []
            for (bbox, text, confidence) in results:
                if confidence > 0.5:
                    texts.append({
                        'text': text,
                        'confidence': confidence,
                        'bbox': bbox
                    })
            
            logger.info(f"Extracted {len(texts)} texts from frame")
            return texts
        
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return []
    
    def extract_text_from_frames(self, frame_paths: List[str]) -> List[str]:
        """Tüm frame'lerden text topla"""
        
        all_texts = []
        
        # Her 5 frame'den 1'ini sample et
        sample_frames = frame_paths[::5]
        logger.info(f"Sampling {len(sample_frames)} frames for OCR")
        
        for frame in sample_frames:
            texts = self.extract_text(frame)
            all_texts.extend([t['text'] for t in texts])
        
        # Duplicate'leri kaldır
        unique_texts = list(set(all_texts))
        
        logger.info(f"✅ Total unique texts: {len(unique_texts)}")
        return unique_texts
