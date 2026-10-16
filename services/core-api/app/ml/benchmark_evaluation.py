"""Offline evaluation of reviewed datasets; never invokes a model or production service."""
import hashlib
import json
import math


def dataset_identity(data):
    synthetic = data.get("synthetic")
    if type(synthetic) is not bool:
        raise ValueError("Dataset must explicitly declare synthetic: true or false")
    if not synthetic:
        provenance = data.get("provenance", {})
        for field in ("reviewed", "authorized", "anonymized"):
            if provenance.get(field) is not True:
                raise ValueError(f"Real dataset requires provenance.{field}=true")
        if not isinstance(provenance.get("source"), str) or not provenance["source"].strip():
            raise ValueError("Real dataset requires a provenance source")
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"dataset_sha256": digest, "synthetic_dataset": synthetic,
            "evaluation_scope": "offline_saved_outputs", "provenance": data.get("provenance", {})}


def unique_ids(values, label):
    if not isinstance(values, list) or any(type(v) not in (str, int) or isinstance(v, str) and not v.strip() for v in values):
        raise ValueError(f"{label} must contain nonempty string or integer IDs")
    # Prevent ambiguous equality between differently typed identifiers.
    if len({str(v) for v in values}) != len(values):
        raise ValueError(f"{label} contains duplicate IDs")
    return set(values)


def validate_retrieval(data):
    documents, queries = data.get("documents"), data.get("queries")
    if not isinstance(documents, list) or not documents or not isinstance(queries, list) or not queries:
        raise ValueError("Nonempty documents and queries are required")
    ids = unique_ids([row["id"] for row in documents], "documents")
    for row in queries:
        if not isinstance(row.get("text"), str) or not row["text"].strip():
            raise ValueError("Queries need nonempty text")
        if not unique_ids(row.get("relevant_ids"), "relevant_ids") <= ids:
            raise ValueError("Gold references an unknown document")


def evaluate_videos(dataset, predictions):
    identity = dataset_identity(dataset)
    cases = dataset.get("videos")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Nonempty videos are required")
    ids = unique_ids([r["id"] for r in cases], "videos")
    if not isinstance(predictions, list):
        raise ValueError("Predictions must be a list")
    predicted_ids = unique_ids([r["id"] for r in predictions], "predictions")
    if predicted_ids != ids:
        raise ValueError("Predictions must cover exactly the dataset video IDs")
    by_id = {r["id"]: r for r in predictions}
    if set(by_id) != ids:
        raise ValueError("Prediction ID types must match dataset IDs")
    tp = fp = fn = exact = 0
    details = []
    durations = []
    for case in cases:
        gold = unique_ids(case.get("location_ids"), "gold locations")
        row = by_id[case["id"]]
        actual = unique_ids(row.get("location_ids"), "predicted locations")
        hits, extra, missing = len(gold & actual), len(actual - gold), len(gold - actual)
        tp += hits; fp += extra; fn += missing; exact += gold == actual
        details.append({"id": case["id"], "true_positives": hits,
                        "false_positives": extra, "false_negatives": missing,
                        "exact_match": gold == actual})
        duration = row.get("duration_s")
        if duration is not None:
            if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
                raise ValueError("duration_s must be finite and nonnegative")
            durations.append(duration)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {**identity, "video_count": len(cases), "precision": precision, "recall": recall,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            "exact_match_rate": exact / len(cases), "false_positives": fp, "false_negatives": fn,
            "mean_duration_s": sum(durations) / len(durations) if durations else None,
            "duration_sample_count": len(durations), "details": details}
