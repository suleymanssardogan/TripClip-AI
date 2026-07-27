"""
OCRService — güven eşiği filtresi, hata durumunda sessiz [] fallback,
frame-dedup ve metin-birleştirme mantığı için testler.

RapidOCR motoru gerçek modelle çalıştırılmıyor (ağır/yavaş) — self.engine
mock'lanıyor, aynı NERService testlerindeki yaklaşım.
"""
from unittest import mock

import pytest
from PIL import Image

from app.ml.ocr_service import OCRService


@pytest.fixture
def service():
    return OCRService()


# ─── extract_text ─────────────────────────────────────────────────────────────

def test_extract_text_filters_by_confidence(service):
    service.engine = mock.MagicMock(return_value=(
        [
            [[[0, 0], [1, 0], [1, 1], [0, 1]], "Gaziantep", 0.95],
            [[[0, 0], [1, 0], [1, 1], [0, 1]], "belirsiz", 0.20],
        ],
        None,
    ))

    result = service.extract_text("fake.jpg", min_confidence=0.5)

    texts = [r["text"] for r in result]
    assert "Gaziantep" in texts
    assert "belirsiz" not in texts


def test_extract_text_empty_result_returns_empty_list(service):
    service.engine = mock.MagicMock(return_value=(None, None))
    assert service.extract_text("fake.jpg") == []


def test_extract_text_swallows_engine_exception_and_returns_empty(service):
    # OCR per-frame çalışır; tek bir bozuk frame tüm video'yu düşürmemeli —
    # bu yüzden burası (Gemini/Whisper'ın aksine) bilerek [] döndürüyor.
    service.engine = mock.MagicMock(side_effect=RuntimeError("bozuk görüntü"))
    assert service.extract_text("corrupt.jpg") == []


def test_extract_text_skips_malformed_items(service):
    service.engine = mock.MagicMock(return_value=(
        [["bbox_only"]],  # len < 3, atlanmalı
        None,
    ))
    assert service.extract_text("fake.jpg") == []


# ─── extract_text_from_frames ─────────────────────────────────────────────────

def test_extract_text_from_frames_empty_input(service):
    assert service.extract_text_from_frames([]) == []


def test_extract_text_from_frames_deduplicates_case_insensitive(service, tmp_path):
    frame = tmp_path / "frame1.png"
    Image.new("RGB", (8, 8), color="white").save(frame)

    with mock.patch.object(service, "_deduplicate_frames", return_value=[str(frame)]), \
         mock.patch.object(service, "extract_text", return_value=[
             {"text": "Gaziantep", "confidence": 0.9, "bbox": []},
             {"text": "gaziantep", "confidence": 0.9, "bbox": []},
         ]):
        result = service.extract_text_from_frames([str(frame)])

    assert result == ["Gaziantep"]  # ikinci (küçük harf) tekrar sayılır, atlanır


def test_extract_text_from_frames_aggregates_across_frames(service):
    with mock.patch.object(service, "_deduplicate_frames", return_value=["f1.jpg", "f2.jpg"]), \
         mock.patch.object(service, "extract_text", side_effect=[
             [{"text": "Kaleiçi", "confidence": 0.9, "bbox": []}],
             [{"text": "Düden Şelalesi", "confidence": 0.9, "bbox": []}],
         ]):
        result = service.extract_text_from_frames(["f1.jpg", "f2.jpg"])

    assert result == ["Kaleiçi", "Düden Şelalesi"]


# ─── _deduplicate_frames ──────────────────────────────────────────────────────

def test_deduplicate_frames_empty_input(service):
    assert service._deduplicate_frames([]) == []


def test_deduplicate_frames_keeps_first_frame_always(service, tmp_path):
    frame = tmp_path / "only.png"
    Image.new("RGB", (8, 8), color="white").save(frame)
    assert service._deduplicate_frames([str(frame)]) == [str(frame)]


def test_deduplicate_frames_drops_near_identical_consecutive_frames(service, tmp_path):
    identical_a = tmp_path / "a.png"
    identical_b = tmp_path / "b.png"
    Image.new("RGB", (16, 16), color="white").save(identical_a)
    Image.new("RGB", (16, 16), color="white").save(identical_b)

    result = service._deduplicate_frames([str(identical_a), str(identical_b)])

    assert result == [str(identical_a)]


def test_deduplicate_frames_keeps_visually_different_frames(service, tmp_path):
    white = tmp_path / "white.png"
    black = tmp_path / "black.png"
    Image.new("RGB", (16, 16), color="white").save(white)
    Image.new("RGB", (16, 16), color="black").save(black)

    result = service._deduplicate_frames([str(white), str(black)])

    assert result == [str(white), str(black)]
