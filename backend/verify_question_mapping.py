"""Read-only preflight for the frozen Stage 9 identity mapping; never stamps/imports."""
import importlib.util
from pathlib import Path

from sqlalchemy import text
from app.database import engine


def main():
    path = Path(__file__).parent / 'migrations/versions/0004_question_bank.py'
    spec = importlib.util.spec_from_file_location('frozen_question_mapping', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        with engine.connect() as connection:
            connection.execute(text('SET TRANSACTION READ ONLY'))
            plan = module.plan_legacy_questions(connection)
        for item in plan:
            print(f"Question ID {item['id']} -> {item['key']}")
        print(f'Verified {len(plan)} legacy question identities. No database changes made.')
        return 0
    except (ValueError, RuntimeError) as exc:
        print(f'Identity verification failed: {exc}')
        return 1
    finally:
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
