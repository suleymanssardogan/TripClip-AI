import easyocr
from typing import List,Dict
import logging

logger = logging.getLogger(__name__)

class OCRService:
    """ EasyOCR ile text extraction"""

    def __init__(self):
        # Turkish + English
        self.reader = easyocr.Reader(['tr','en'],gpu=False)
        logger.info("EasyOCR initialized (TR + ENG)")

        def exract_tect(self,image_path:str) ->List[Dict]:
            """Frame'dan text çıkar"""
            try:
                results = self.reader.readtext(image_path)

                texts =[]
                for(bbox,text,confidence) in results:
                    if confidence >0.5:
                        texts.append({
                            "text":text,
                            "confidence":confidence,
                            "bbox": bbox
                        })
                logger.info(f"Extracted{len(texts)} texts")
                return texts
            except Exception as e:
                logger.error(f"OCR Error: {e}")
                return []
        
        def extract_text_from_frames(self,frame_paths: List[str]) ->List[str]:
            """Tüm frame'lerden text topla"""

            all_texts =[]
            for frame in frame_paths:
                texts = self.extract_text(frame)
                all_texts.extend([t['texxt'] for t in texts])
            
            #Duplicateleri kaldır
            unique_texts = list(set(all_texts))

            logger.info(f"Total unique texts:{len(unique_texts)} ")
            return unique_texts
