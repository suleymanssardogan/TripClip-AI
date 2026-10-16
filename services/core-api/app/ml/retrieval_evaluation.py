"""Offline Turkish retrieval benchmark; never changes the production index."""
import math
import time
import unicodedata
from collections import Counter
from app.ml.benchmark_evaluation import validate_retrieval


def _ngrams(text):
    folded = text.replace("İ", "i").replace("I", "ı").lower().replace("ı", "i")
    folded = "".join(c for c in unicodedata.normalize("NFKD", folded) if not unicodedata.combining(c))
    return Counter(folded[i:i + 3] for i in range(max(0, len(folded) - 2)))


def lexical_scores(query, texts):
    q = _ngrams(query)
    scores = []
    q_norm = math.sqrt(sum(v * v for v in q.values()))
    for text in texts:
        doc = _ngrams(text)
        norm = math.sqrt(sum(v * v for v in doc.values())) * q_norm
        scores.append(sum(v * doc[k] for k, v in q.items()) / norm if norm else 0)
    return scores


def evaluate(dataset, score_query, k=3, threshold=0):
    validate_retrieval(dataset)
    if type(k) is not int or k < 1 or not math.isfinite(threshold):
        raise ValueError("Invalid k or threshold")
    ids = [d["id"] for d in dataset["documents"]]
    details = []
    for row in dataset["queries"]:
        start = time.perf_counter()
        scores = list(score_query(row["text"]))
        if len(scores) != len(ids) or any(not math.isfinite(v) for v in scores):
            raise ValueError("Scores must be finite and cover every document")
        ranking = sorted(zip(ids, scores), key=lambda p: (-p[1], str(p[0])))
        ranked = [pid for pid, score in ranking if score >= threshold][:k]
        gold = set(row["relevant_ids"])
        hits = len(gold.intersection(ranked))
        rr = next((1 / (i + 1) for i, pid in enumerate(ranked) if pid in gold), 0)
        details.append({"query": row["text"], "ranked_ids": ranked,
                        "recall": hits / len(gold) if gold else None,
                        "precision": hits / len(ranked) if ranked else 0, "rr": rr,
                        "unexpected_match": bool(ranked) if not gold else None,
                        "latency_ms": round((time.perf_counter() - start) * 1000, 2)})
    known = [r for r in details if r["recall"] is not None]
    unknown = [r for r in details if r["recall"] is None]
    mean = lambda rows, key: sum(r[key] for r in rows) / len(rows) if rows else None
    return {"k": k, "threshold": threshold, "query_count": len(details),
            "recall_at_k": mean(known, "recall"), "precision_at_k": mean(known, "precision"),
            "mrr_at_k": mean(known, "rr"), "irrelevant_query_match_rate": mean(unknown, "unexpected_match"),
            "details": details}
