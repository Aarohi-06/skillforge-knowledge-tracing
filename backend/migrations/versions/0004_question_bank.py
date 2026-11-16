"""Stable question identities and authored, snapshotted feedback.

The frozen manifest is deliberately independent of the evolving import source.
Legacy adoption compares every original field, never a title alone or an ID.
"""
import json
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = "0004_question_bank"
down_revision = "0003_idempotent_submissions"
branch_labels = None
depends_on = None


def plan_legacy_questions(connection):
    """Read-only identity verification, also used by the operator preflight CLI."""
    manifest = json.loads((Path(__file__).resolve().parents[1] / "data/0004_legacy_questions.json").read_text(encoding="utf-8"))["questions"]
    fields = ("concept", "title", "description", "difficulty", "options", "correct_answer")
    def identity(item):
        return json.dumps({key: item[key] for key in fields}, ensure_ascii=False, sort_keys=True)
    mapping = {identity(item): item for item in manifest}
    if len(mapping) != 25 or len({item["question_key"] for item in manifest}) != 25:
        raise RuntimeError("Invalid frozen question identity manifest")
    rows = connection.execute(sa.text("""SELECT q.id,c.name AS concept,q.title,q.description,q.difficulty,q.options,q.correct_answer
        FROM questions q JOIN concepts c ON c.id=q.concept_id ORDER BY q.id""")).mappings().all()
    adopted = []
    used = set()
    for row in rows:
        original = dict(row)
        original["options"] = json.loads(original["options"])
        match = mapping.get(identity(original))
        if match is None or match["question_key"] in used:
            raise RuntimeError(f"Cannot safely adopt legacy question id={row['id']}; unknown or ambiguous complete-record identity. Review mapping before migration.")
        used.add(match["question_key"])
        adopted.append({"id": row["id"], "key": match["question_key"], "explanation": match["explanation"]})
    return adopted


def upgrade():
    connection = op.get_bind()
    # Take the lock DDL needs before verifying identities, so a legacy writer
    # cannot change a record between verification and key assignment.
    connection.execute(sa.text("LOCK TABLE questions IN ACCESS EXCLUSIVE MODE"))
    adopted = plan_legacy_questions(connection)

    op.add_column("questions", sa.Column("question_key", sa.String(100), nullable=True))
    op.add_column("questions", sa.Column("explanation", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_question_key", "questions", ["question_key"])
    op.create_index("ix_questions_concept_id_id", "questions", ["concept_id", "id"])
    op.add_column("attempts", sa.Column("feedback_explanation", sa.Text(), nullable=True))
    op.add_column("attempts", sa.Column("feedback_correct_answer", sa.Integer(), nullable=True))
    for item in adopted:
        connection.execute(sa.text("UPDATE questions SET question_key=:key, explanation=:explanation WHERE id=:id"), item)
    # Preserve the answer index known at adoption, but do not fabricate a lesson
    # explanation that was never shown to a historical attempt.
    connection.execute(sa.text("""UPDATE attempts a SET feedback_correct_answer=q.correct_answer
        FROM questions q WHERE q.id=a.question_id"""))
    op.execute("""CREATE FUNCTION prevent_question_rekey() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.question_key IS NOT NULL AND NEW.question_key IS DISTINCT FROM OLD.question_key THEN
            RAISE EXCEPTION 'Question keys are immutable';
          END IF;
          RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER immutable_question_key BEFORE UPDATE OF question_key ON questions
        FOR EACH ROW EXECUTE FUNCTION prevent_question_rekey()""")


def downgrade():
    op.execute("DROP TRIGGER immutable_question_key ON questions")
    op.execute("DROP FUNCTION prevent_question_rekey()")
    op.drop_column("attempts", "feedback_correct_answer")
    op.drop_column("attempts", "feedback_explanation")
    op.drop_index("ix_questions_concept_id_id", table_name="questions")
    op.drop_constraint("uq_question_key", "questions", type_="unique")
    op.drop_column("questions", "explanation")
    op.drop_column("questions", "question_key")
