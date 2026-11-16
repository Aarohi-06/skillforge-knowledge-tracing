"""Repeatable stable-key importer. Explicit operator command, never startup work."""
import argparse
import json
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from app.database import SessionLocal
from app.question_import import ImportConflict, load_questions, synchronize_questions

DATA_FILE = Path(__file__).resolve().parent.parent / "data/questions.json"


def seed_questions(path=DATA_FILE, *, dry_run=False):
    content = load_questions(Path(path))
    with SessionLocal.begin() as db:
        if dry_run:
            db.execute(text("SET TRANSACTION READ ONLY"))
        if not {'question_key', 'explanation'} <= {column['name'] for column in inspect(db.connection()).get_columns('questions')}:
            raise ValueError('Question bank schema requires approved migration 0004_question_bank before import. No changes made.')
        return synchronize_questions(db, content, dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DATA_FILE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        report = seed_questions(args.file, dry_run=args.dry_run)
    except (ValueError, OSError) as exc:
        if isinstance(exc, ImportConflict):
            print(json.dumps(exc.report, indent=2))
        else:
            print(f"Question import rejected: {exc}")
        return 1
    except SQLAlchemyError as exc:
        print(f"Database import failed ({type(exc).__name__}); transaction rolled back. Check database availability, schema revision, and key conflicts.")
        return 1
    print(json.dumps(report, indent=2))
    return 1 if report["conflicts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
