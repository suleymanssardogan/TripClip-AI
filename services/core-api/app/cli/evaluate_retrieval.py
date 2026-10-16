import argparse
import json
from pathlib import Path
from app.ml.retrieval_evaluation import evaluate, lexical_scores
from app.ml.benchmark_evaluation import dataset_identity, validate_retrieval


def main():
    parser = argparse.ArgumentParser(description="Offline lexical or embedding retrieval evaluation")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--backend", choices=["lexical", "embedding"], default="lexical")
    parser.add_argument("--model", default="all-MiniLM-L6-v2")
    parser.add_argument("--threshold", type=float, default=0)
    parser.add_argument("--k", type=int, choices=range(1, 11), default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.dataset.read_text())
    identity = dataset_identity(data)
    validate_retrieval(data)
    texts = [", ".join(p for p in (d["name"], d.get("city"), d.get("category")) if p)
             + (". " + d["content"] if d.get("content") else "") for d in data["documents"]]
    if args.backend == "embedding":
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(args.model)
        vectors = model.encode(texts, normalize_embeddings=True)
        score = lambda q: (vectors @ model.encode(q, normalize_embeddings=True)).tolist()
    else:
        score = lambda q: lexical_scores(q, texts)
    report = {"backend": args.backend, "model": args.model if args.backend == "embedding" else None,
              **identity, "evaluation_scope": "offline_retrieval",
              **evaluate(data, score, args.k, args.threshold)}
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
