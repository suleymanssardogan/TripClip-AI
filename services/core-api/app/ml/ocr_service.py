from typing import List
import logging
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# RapidOCR Türkçe karakter düzeltme tablosu
# Latin OCR modeli ş→s, ğ→g, ı→i gibi okuyabilir — sık geçen kalıpları geri çevir
_TR_FIXES = [
    # Sonu "-si/-sı/-su/-sü" gelen tipik yer isimleri (possessive suffix OCR hatası)
    # Genel karakter düzeltmeleri — kelime bazlı değil, karakter bazlı değil
    # (Bunlar zaten NER/Nominatim tarafından tolere ediliyor)
]


class OCRService:
    """RapidOCR (ONNX) — EasyOCR'dan 16x hızlı, ARM'da optimize"""

    def __init__(self):
        self.engine = None
        logger.info("OCRService initialized (lazy — RapidOCR ONNX)")

    def _load_model(self):
        if self.engine is not None:
            return
        import warnings
        warnings.filterwarnings("ignore")
        logger.info("Loading RapidOCR model...")
        from rapidocr_onnxruntime import RapidOCR
        self.engine = RapidOCR()
        logger.info("✅ RapidOCR initialized")

    # ─────────────────────────────────────────────────────────────
    # Frame differencing — benzer frame'leri atla
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _frame_hash(path: str, size: int = 16) -> np.ndarray:
        try:
            img = Image.open(path).convert("L").resize((size, size))
            return np.array(img, dtype=np.float32)
        except Exception:
            return np.zeros((size, size), dtype=np.float32)

    def _deduplicate_frames(self, frame_paths: List[str],
                            similarity_threshold: float = 0.96) -> List[str]:
        """
        Ardışık benzer frame'leri filtrele.
        Metin overlay değişmeden duran frame'lerin tekrar OCR'lanmasını önler.
        """
        if not frame_paths:
            return []

        selected = [frame_paths[0]]
        prev_hash = self._frame_hash(frame_paths[0])

        for path in frame_paths[1:]:
            curr_hash = self._frame_hash(path)
            max_val = max(prev_hash.max(), curr_hash.max(), 1.0)
            diff = np.mean(np.abs(prev_hash - curr_hash)) / max_val
            if (1.0 - diff) < similarity_threshold:
                selected.append(path)
                prev_hash = curr_hash

        logger.info(f"Frame dedup: {len(frame_paths)} → {len(selected)} "
                    f"(threshold={similarity_threshold})")
        return selected

    # ─────────────────────────────────────────────────────────────
    # Tek frame OCR
    # ─────────────────────────────────────────────────────────────

    def extract_text(self, image_path: str,
                     min_confidence: float = 0.5) -> List[dict]:
        self._load_model()
        import warnings
        warnings.filterwarnings("ignore")
        try:
            result, _ = self.engine(image_path)
            if not result:
                return []
            out = []
            for item in result:
                # RapidOCR: [bbox, text, score]
                if len(item) < 3:
                    continue
                bbox, text, score = item[0], item[1], item[2]
                text = str(text).strip()
                if text and float(score) >= min_confidence:
                    out.append({
                        "text":       text,
                        "confidence": round(float(score), 3),
                        "bbox":       bbox,
                    })
            return out
        except Exception as e:
            logger.error(f"RapidOCR error on {image_path}: {e}")
            return []

    # ─────────────────────────────────────────────────────────────
    # Tüm frame'ler
    # ─────────────────────────────────────────────────────────────

    def extract_text_from_frames(self, frame_paths: List[str]) -> List[str]:
        """
        1. Frame differencing → benzer frame'leri at
        2. RapidOCR → metin çıkar
        3. Duplicate kaldır
        """
        if not frame_paths:
            return []

        unique_frames = self._deduplicate_frames(frame_paths)

        all_texts: List[str] = []
        for i, frame in enumerate(unique_frames):
            results = self.extract_text(frame)
            found = [r["text"] for r in results]
            if found:
                logger.info(f" Found texts: {found}")
            all_texts.extend(found)

        # Duplicate kaldır (büyük/küçük harf duyarsız)
        seen: set = set()
        unique: List[str] = []
        for t in all_texts:
            key = t.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(t)

        logger.info(f"OCR sonuç: {len(unique)} benzersiz metin "
                    f"({len(unique_frames)}/{len(frame_paths)} frame işlendi)")
        return unique
