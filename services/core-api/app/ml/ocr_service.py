import easyocr
from typing import List, Dict
import logging
from PIL import Image

if not hasattr(Image,'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

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
        
        # Her 3 frame'den 1'ini sample et
        sample_frames = frame_paths[::3]
        logger.info(f"Sampling {len(sample_frames)} frames for OCR (from {len(frame_paths)} total)")
        
        for i, frame in enumerate(sample_frames):
            logger.info(f"OCR processing frame {i+1}/{len(sample_frames)}: {frame}")
            texts = self.extract_text(frame)
            if texts:
                logger.info(f" Found texts: {[t['text'] for t in texts]}")
            else:
                logger.info(f"No text found in frame {i+1}")
            all_texts.extend([t['text'] for t in texts])
            
        # Duplicate'leri kaldır
        unique_texts = list(set(all_texts))
        
        logger.info(f"Total unique texts: {len(unique_texts)}")
        return unique_texts
