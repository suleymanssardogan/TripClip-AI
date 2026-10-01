import argparse
import json
from pathlib import Path
from app.application.services.knowledge_ingestion import KnowledgeInput, ingest_documents


def main():
    parser = argparse.ArgumentParser(description="Reviewed source ingestion and AI index maintenance")
    sub = parser.add_subparsers(dest="command", required=True)
    load = sub.add_parser("import")
    load.add_argument("file", type=Path)
    load.add_argument("--dry-run", action="store_true")
    index = sub.add_parser("reindex")
    index.add_argument("--after-id", type=int, default=0)
    replay = sub.add_parser("replay")
    replay.add_argument("--job-id", type=int, required=True)
    args = parser.parse_args()
    if args.command == "import":
        records = json.loads(args.file.read_text())
        if not isinstance(records, list) or not 1 <= len(records) <= 500:
            parser.error("Input must be a JSON list of 1–500 reviewed source excerpts")
        for row in records:
            KnowledgeInput.model_validate(row)
        if args.dry_run:
            print(f"Validated {len(records)} source excerpts; database unchanged")
            return
    from app.core.database import SessionLocal
    from app.application.services.deferred_work import enqueue
    from app.models.place import Place
    from app.models.deferred_job import DeferredJob
    from datetime import datetime
    with SessionLocal.begin() as db:
        if args.command == "import":
            print(f"Imported {ingest_documents(db, records)} reviewed excerpts")
        elif args.command == "reindex":
            rows = db.query(Place.id).filter(Place.id > args.after_id).order_by(Place.id).limit(500).all()
            for (place_id,) in rows:
                enqueue(db, "place_index", place_id)
            print(f"Scheduled {len(rows)} places; next after-id={rows[-1][0] if rows else args.after_id}")
        else:
            changed = db.query(DeferredJob).filter_by(id=args.job_id, status="failed").update({
                "status": "pending", "attempts": 0, "available_at": datetime.utcnow(),
                "lease_until": None, "last_error": None,
            }, synchronize_session=False)
            print(f"Rearmed {changed} failed job")


if __name__ == "__main__":
    main()
