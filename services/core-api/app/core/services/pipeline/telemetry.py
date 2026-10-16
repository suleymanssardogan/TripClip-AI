"""Stage metrics contain no prompt, location, file or user labels."""
import time
from prometheus_client import Counter, Histogram
STAGE_DURATION = Histogram("video_analysis_stage_seconds", "Stage execution time", ["stage", "status"],
                           buckets=(.1, .5, 1, 5, 15, 30, 60, 120, 300, 900))
STAGE_RUNS = Counter("video_analysis_stage_runs_total", "Stage outcomes", ["stage", "status"])
KNOWN_STAGES = {"YOLO", "Vision", "OCR", "Whisper", "Gemini", "BERT NER", "NER", "Geocoding",
                "Geocoding(Overpass)", "Geocoding(Nominatim)", "media_metadata", "media_frames",
                "media_thumbnail", "GeographicFix", "Dedup", "LocationSummary", "Route", "RAG", "Gemini(tips)",
                "Gemini(locations)", "BERT-NER(hybrid)", "NER(audio)", "RegionResolve",
                "Geocoding(NER)", "GeoOutlierFix", "LocSummary"}


def observe_stage(name, duration, status):
    if name.startswith("Geocoding(NER,"):
        name = "Geocoding(NER)"
    name = name if name in KNOWN_STAGES else "other"
    STAGE_DURATION.labels(stage=name, status=status).observe(max(0, duration))
    STAGE_RUNS.labels(stage=name, status=status).inc()


def timed_stage(name, function):
    start = time.perf_counter(); status = "success"
    try:
        return function()
    except BaseException:
        status = "error"
        raise
    finally:
        observe_stage(name, time.perf_counter() - start, status)
