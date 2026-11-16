"""Validated, authored lessons. Reading content never writes student state."""
import json
import logging
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, ValidationError, model_validator

Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
CONTENT_PATH = Path(__file__).resolve().parents[2] / "data" / "concept_resources.json"
logger = logging.getLogger(__name__)


class ContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Overview(ContentModel):
    explanation: Text
    why_it_matters: Text


class KeyIdea(ContentModel):
    term: Text
    explanation: Text


class WorkedExample(ContentModel):
    title: Text
    steps: Annotated[list[Text], Field(min_length=2)]
    language: Literal["python"]
    code: Text
    expected_output: Text


class CommonMistake(ContentModel):
    mistake: Text
    explanation: Text


class ComplexityOperation(ContentModel):
    operation: Text
    time: Text
    auxiliary_space: Text


class Complexity(ContentModel):
    assumptions: Annotated[list[Text], Field(min_length=1)]
    notes: Text
    operations: Annotated[list[ComplexityOperation], Field(min_length=1)]


class ResourceLink(ContentModel):
    title: Text
    url: HttpUrl
    resource_type: Literal["documentation", "interactive_textbook", "article", "video"]
    verification_status: Literal["verified", "unverified"]
    verified_on: date | None

    @model_validator(mode="after")
    def check_verification(self):
        if (self.verification_status == "verified") != (self.verified_on is not None):
            raise ValueError("Verified links require a verification date; unverified links must not have one")
        return self


class Lesson(ContentModel):
    concept_name: Text
    overview: Overview
    key_ideas: Annotated[list[KeyIdea], Field(min_length=2)]
    worked_example: WorkedExample
    common_mistakes: Annotated[list[CommonMistake], Field(min_length=2)]
    complexity: Complexity
    resources: list[ResourceLink]


class ResourceCatalog(ContentModel):
    schema_version: Literal[1]
    content_version: Text
    lessons: Annotated[list[Lesson], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_concepts(self):
        names = [lesson.concept_name.casefold() for lesson in self.lessons]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate concept lesson")
        return self


class ConceptResourcesResponse(Lesson):
    concept_id: int
    schema_version: Literal[1]
    content_version: Text


class ContentError(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContentError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def load_catalog(path: Path | None = None) -> ResourceCatalog:
    """Validate the whole catalog before returning any lesson; no partial fallback."""
    try:
        data = json.loads((path or CONTENT_PATH).read_text(encoding="utf-8"), object_pairs_hook=unique_object)
        return ResourceCatalog.model_validate(data)
    except (OSError, ValueError, ValidationError) as exc:
        raise ContentError(f"Invalid learning resource catalog: {exc}") from exc


def resources_for_concept(concept):
    try:
        catalog = load_catalog()
    except ContentError:
        logger.exception("Learning resource catalog failed validation")
        raise HTTPException(status_code=500, detail="Learning resource content is invalid or unavailable") from None
    lesson = next((item for item in catalog.lessons if item.concept_name == concept.name), None)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Learning resources not found for this concept")
    return ConceptResourcesResponse(
        **lesson.model_dump(), concept_id=concept.id,
        schema_version=catalog.schema_version, content_version=catalog.content_version,
    )
