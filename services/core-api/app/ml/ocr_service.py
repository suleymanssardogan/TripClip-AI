from typing import List
import logging
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class OCRService:
    """PaddleOCR v3 ile text extraction (EasyOCR'dan 3-5x hızlı)"""

    def __init__(self):
        self.ocr = None
        logger.info("OCRService initialized (lazy — PaddleOCR v3)")

    def _load_model(self):
        if self.ocr is not None:
            return
        import warnings
        warnings.filterwarnings("ignore")
        logger.info("Loading PaddleOCR model (ilk kez ~40s sürebilir)...")
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(
            lang="en",                              # Latin alfabesi → Türkçe dahil
            use_textline_orientation=False,         # Yatay metin → hız kazanımı
            use_doc_orientation_classify=False,     # Belge orientasyonu atla
            use_doc_unwarping=False,                # Perspektif düzeltme atla
            text_detection_model_name="PP-OCRv4_mobile_det",   # Hafif detection
            text_recognition_model_name="en_PP-OCRv4_mobile_rec",  # Hafif rec
            text_rec_score_thresh=0.5,
        )
        logger.info("✅ PaddleOCR v3 initialized")

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
        threshold=0.96 → %96 benzer pixel → aynı metin → atla
        """
        if not frame_paths:
            return []

        selected = [frame_paths[0]]
        prev_hash = self._frame_hash(frame_paths[0])

        for path in frame_paths[1:]:
            curr_hash = self._frame_hash(path)
            max_val = max(prev_hash.max(), curr_hash.max(), 1.0)
            diff = np.mean(np.abs(prev_hash - curr_hash)) / max_val
            if (1.0 - diff) < similarity_threshold:   # farklı → al
                selected.append(path)
                prev_hash = curr_hash

        logger.info(f"Frame dedup: {len(frame_paths)} → {len(selected)} "
                    f"(threshold={similarity_threshold})")
        return selected

    # ─────────────────────────────────────────────────────────────
    # Tek frame OCR
    # ─────────────────────────────────────────────────────────────

    def extract_text(self, image_path: str) -> List[dict]:
        self._load_model()
        import warnings
        warnings.filterwarnings("ignore")
        try:
            result = self.ocr.ocr(image_path)
            if not result:
                return []

            res = result[0].json.get("res", {})
            texts = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            boxes = res.get("rec_boxes", [])

            out = []
            for text, score, box in zip(texts, scores, boxes):
                text = text.strip()
                if text and float(score) >= 0.5:
                    out.append({
                        "text":       text,
                        "confidence": round(float(score), 3),
                        "bbox":       box,
                    })
            return out

        except Exception as e:
            logger.error(f"PaddleOCR error on {image_path}: {e}")
            return []

    # ─────────────────────────────────────────────────────────────
    # Tüm frame'ler
    # ─────────────────────────────────────────────────────────────

    def extract_text_from_frames(self, frame_paths: List[str]) -> List[str]:
        """
        1. Frame differencing ile benzer frame'leri filtrele
        2. Kalan frame'lere PaddleOCR uygula
        3. Duplicate metinleri kaldır
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
