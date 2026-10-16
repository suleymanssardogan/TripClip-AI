import pytest
from app.ml.benchmark_evaluation import dataset_identity, evaluate_videos
from app.ml.retrieval_evaluation import evaluate


def test_real_data_cannot_silently_skip_review_or_authorization():
    for data in ({}, {"synthetic": False}, {"synthetic": False, "provenance": {"reviewed": True}}):
        with pytest.raises(ValueError):
            dataset_identity(data)
    real = {"synthetic": False, "provenance": {"reviewed": True, "authorized": True,
            "anonymized": True, "source": "reviewed internal corpus v1"}}
    assert dataset_identity(real)["synthetic_dataset"] is False


def test_video_metrics_include_missed_and_hallucinated_locations():
    data = {"synthetic": True, "videos": [{"id": "a", "location_ids": [1, 2]},
                                         {"id": "b", "location_ids": []}]}
    report = evaluate_videos(data, [{"id": "a", "location_ids": [1, 3], "duration_s": 4},
                                   {"id": "b", "location_ids": []}])
    assert report["precision"] == .5
    assert report["recall"] == .5
    assert report["f1"] == .5
    assert report["exact_match_rate"] == .5
    assert report["duration_sample_count"] == 1
    assert report["mean_duration_s"] == 4


@pytest.mark.parametrize("predictions", [[], [{"id": "a", "location_ids": [1, 1]}],
    [{"id": "a", "location_ids": [], "duration_s": float("nan")}],
    [{"id": "a", "location_ids": []}, {"id": "extra", "location_ids": []}]])
def test_video_invalid_or_partial_runs_are_rejected(predictions):
    with pytest.raises(ValueError):
        evaluate_videos({"synthetic": True, "videos": [{"id": "a", "location_ids": [1]}]}, predictions)


@pytest.mark.parametrize("scores", [[1], [float("nan"), 0], [float("inf"), 1]])
def test_retrieval_rejects_incomplete_or_invalid_scores(scores):
    with pytest.raises(ValueError):
        evaluate({"documents": [{"id": 1}, {"id": 2}],
                  "queries": [{"text": "test", "relevant_ids": [1]}]}, lambda _: scores)


def test_retrieval_rejects_unknown_gold():
    with pytest.raises(ValueError):
        evaluate({"documents": [{"id": 1}], "queries": [{"text": "test", "relevant_ids": [2]}]}, lambda _: [1])
