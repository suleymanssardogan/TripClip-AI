import time
from unittest import mock
import pytest
from app.core.services.pipeline.parallel import StageSpec, run_parallel
from app.core.services.pipeline.telemetry import timed_stage, STAGE_RUNS
from app.ml.provider_usage import record_gemini_usage


def test_parallel_stage_time_measures_execution_not_collection_wait():
    def slow():
        time.sleep(.04)
        return "slow"
    results = run_parallel([StageSpec("YOLO", slow, [], 1), StageSpec("OCR", lambda: "fast", [], 1)])
    assert [r.data for r in results] == ["slow", "fast"]
    assert results[0].duration_s >= .03
    assert results[1].duration_s < .03


def test_failed_parallel_stage_does_not_disable_other_stage():
    def fail():
        raise ValueError("failed")
    results = run_parallel([StageSpec("OCR", fail, [], 1), StageSpec("YOLO", lambda: [1], [], 1)])
    assert results[0].fallback_used and results[0].data == []
    assert results[1].success and results[1].data == [1]


def test_parallel_deadline_is_not_reset_when_collecting_second_result():
    def slow():
        time.sleep(.04)
        return "late"
    results = run_parallel([StageSpec("YOLO", slow, [], 1), StageSpec("OCR", slow, [], .005)])
    assert results[0].success
    assert results[1].fallback_used and results[1].data == []


def test_media_failure_is_measured_and_propagated():
    before = STAGE_RUNS.labels("media_metadata", "error")._value.get()
    with pytest.raises(ValueError):
        timed_stage("media_metadata", lambda: (_ for _ in ()).throw(ValueError("corrupt")))
    assert STAGE_RUNS.labels("media_metadata", "error")._value.get() == before + 1


def test_cost_uses_configured_model_rates_and_reported_tokens(monkeypatch):
    monkeypatch.setenv("AI_PRICING_JSON", '{"test-model":{"input":2,"output":8,"cached_input":0.5}}')
    cost = record_gemini_usage("test-model", "locations", {"usageMetadata": {
        "promptTokenCount": 1000, "candidatesTokenCount": 100, "cachedContentTokenCount": 200,
        "thoughtsTokenCount": 50}})
    assert cost == pytest.approx((800*2 + 200*.5 + 150*8)/1_000_000)


@pytest.mark.parametrize("pricing,usage", [("{}", {"promptTokenCount":100}),
    ('{"m":{"input":-1,"output":8}}', {"promptTokenCount":100,"candidatesTokenCount":10}),
    ('{"m":{"input":2,"output":8}}', {}), ("malformed", {})])
def test_missing_or_invalid_pricing_never_fabricates_cost(monkeypatch, pricing, usage):
    monkeypatch.setenv("AI_PRICING_JSON", pricing)
    assert record_gemini_usage("m", "tips", {"usageMetadata":usage}) is None


def test_orchestrator_preserves_result_contract_with_extracted_stages(tmp_path):
    from app.core.services.video_processor import VideoProcessingService
    processor = VideoProcessingService.__new__(VideoProcessingService)
    processor._ml_available = True; processor._use_gemini = False; processor._use_hybrid = False
    processor.frames_dir = tmp_path
    processor._get_metadata = mock.Mock(return_value={"duration":1,"width":320,"height":240,"fps":30})
    processor._extract_frames = mock.Mock(return_value=[])
    processor._create_thumbnail = mock.Mock(return_value=None)
    processor.detector = mock.Mock(); processor.detector.detect_objects_in_frames.return_value = []
    processor.vision_detector = mock.Mock(); processor.vision_detector.detect_landmarks_in_frames.return_value = []
    processor.ocr = mock.Mock(); processor.ocr.extract_text_from_frames.return_value = []
    processor.audio_processor = mock.Mock(); processor.audio_processor.process_video_audio.return_value = None
    processor.ner = mock.Mock(); processor.places = mock.Mock(); processor.places.enrich_locations.return_value = []
    processor.deduplicator = mock.Mock(); processor.deduplicator.deduplicate_locations.return_value = []
    processor.deduplicator.generate_location_summary.return_value = {}
    processor.route_optimizer = mock.Mock(); processor.route_optimizer.optimize_route.return_value = {}
    with mock.patch("app.core.services.video_processor.set_progress"):
        result = processor.process_video("/unused.mp4", 1, defer_tips=True)
    assert result["duration"] == 1 and result["travel_tips"] == {}
    assert {"YOLO", "OCR", "Whisper"} <= {r["name"] for r in result["degradation"]["stages"]}
    assert all(r["duration_s"] >= 0 for r in result["degradation"]["stages"])
