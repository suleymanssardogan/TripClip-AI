from app.ml.retrieval_evaluation import evaluate, lexical_scores
import pytest


def test_metrics_measure_misses_and_irrelevant_query_matches():
    data = {"documents": [{"id": 1}, {"id": 2}], "queries": [
        {"text": "known", "relevant_ids": [1]}, {"text": "unknown", "relevant_ids": []}]}
    report = evaluate(data, lambda _: [.9, .8], k=2)
    assert report["recall_at_k"] == 1
    assert report["precision_at_k"] == .5
    assert report["mrr_at_k"] == 1
    assert report["irrelevant_query_match_rate"] == 1
    report = evaluate(data, lambda _: [.1, .05], k=2, threshold=.2)
    assert report["recall_at_k"] == 0
    assert report["irrelevant_query_match_rate"] == 0


def test_lexical_baseline_folds_turkish_characters():
    assert lexical_scores("İSTANBUL", ["istanbul"])[0] == pytest.approx(1)
