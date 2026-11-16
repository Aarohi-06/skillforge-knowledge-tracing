"""Offline validated question synchronization; no startup hooks or public API."""
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Concept, Question

Text = Annotated[str, StringConstraints(strict=True, min_length=1)]
Key = Annotated[str, StringConstraints(strict=True, max_length=100, pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")]


class QuestionContent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question_key: Key
    concept: Text
    title: Annotated[Text, Field(max_length=200)]
    description: Text
    difficulty: Literal["easy", "medium", "hard"]
    options: Annotated[list[Text], Field(min_length=2)]
    correct_answer: int
    explanation: Text

    @model_validator(mode="after")
    def complete(self):
        if any(not item.strip() for item in [self.concept, self.title, self.description, self.explanation, *self.options]):
            raise ValueError(f"{self.question_key}: blank text is not allowed")
        if len(set(self.options)) != len(self.options):
            raise ValueError(f"{self.question_key}: duplicate options")
        if not 0 <= self.correct_answer < len(self.options):
            raise ValueError(f"{self.question_key}: answer index is outside options")
        return self


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def identity(item):
    return json.dumps({key: item[key] for key in ("concept", "title", "description", "difficulty", "options", "correct_answer")}, sort_keys=True, ensure_ascii=False)


def validate_questions(data) -> list[QuestionContent]:
    if not isinstance(data, list):
        raise ValueError("Question source must be an array")
    questions = [QuestionContent.model_validate(item) for item in data]
    keys = [item.question_key for item in questions]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate question keys in source")
    signatures = [identity(item.model_dump()) for item in questions]
    if len(signatures) != len(set(signatures)):
        raise ValueError("Duplicate question records with different keys")
    return questions


def load_questions(path: Path) -> list[QuestionContent]:
    return validate_questions(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object))


class ImportConflict(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__("Question import conflicts: " + "; ".join(report["conflicts"]))


def synchronize_questions(db: Session, content: list[QuestionContent], *, dry_run=False):
    """Plan first; caller owns commit/rollback, including flush errors.

    Permitted edits: title, description, difficulty, explanation. Concept,
    options, and answer-key edits need separate reviewed versioning work.
    """
    content = validate_questions([item.model_dump() for item in content])
    concepts = {item.name: item.id for item in db.scalars(select(Concept)).all()}
    # Administrative batch scan detects alias keys against omitted rows too.
    existing = db.execute(select(Question, Concept.name).join(Concept)).all()
    by_key = {row.question_key: row for row, _ in existing if row.question_key is not None}
    by_identity = {}
    for row, concept_name in existing:
        signature = identity(dict(concept=concept_name, title=row.title, description=row.description,
                                  difficulty=row.difficulty, options=json.loads(row.options), correct_answer=row.correct_answer))
        by_identity.setdefault(signature, []).append(row)
    report = {"inserts": 0, "updates": 0, "unchanged": 0, "conflicts": []}
    plan = []
    for item in content:
        key = item.question_key
        if item.concept not in concepts:
            report["conflicts"].append(f"{key}: unknown concept {item.concept!r}")
            continue
        row = by_key.get(key)
        aliases = by_identity.get(identity(item.model_dump()), [])
        if any(other is not row for other in aliases):
            report["conflicts"].append(f"{key}: complete content already belongs to another row/key; do not rekey legacy records")
            continue
        if row and (row.concept_id != concepts[item.concept] or json.loads(row.options) != item.options or row.correct_answer != item.correct_answer):
            report["conflicts"].append(f"{key}: concept/options/answer identity conflicts with the existing question")
            continue
        values = {field: getattr(item, field) for field in ("title", "description", "difficulty", "explanation")}
        if row is None:
            report["inserts"] += 1
        elif any(getattr(row, field) != value for field, value in values.items()):
            report["updates"] += 1
        else:
            report["unchanged"] += 1
            continue
        plan.append((row, item, values))
    if report["conflicts"]:
        if dry_run:
            return report
        raise ImportConflict(report)
    if not dry_run:
        for row, item, values in plan:
            if row is None:
                db.add(Question(question_key=item.question_key, concept_id=concepts[item.concept],
                                options=json.dumps(item.options), correct_answer=item.correct_answer, **values))
            else:
                for field, value in values.items():
                    setattr(row, field, value)
        db.flush()
    return report
