
import json

from app.recommendation_engine import get_recommendations
from app.concept_graph import build_concept_graph

from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Question, Student, Mastery, Concept
from app.bkt import INITIAL_MASTERY
from app.attempt_service import create_attempt
from app.history_service import get_learning_history
from app.resource_service import ConceptResourcesResponse, resources_for_concept
from app.mastery_rules import get_mastery_status
from app.schemas import (
    QuestionResponse, AttemptCreate, AttemptResponse,
    ConceptProgressResponse, ProgressSummary, ProgressResponse,
    ConceptGraphResponse,
    LearningHistoryResponse,
)

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="SkillForge API",
    description="Adaptive DSA learning platform using Bayesian Knowledge Tracing",
    version="0.1.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/")
def root():
    return {
        "message": "Welcome to SkillForge!",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}



@app.get("/questions", response_model=list[QuestionResponse])
def get_questions(
    concept_id: int | None = Query(default=None, gt=0, le=2147483647),
    limit: int | None = Query(default=None, ge=1, le=100),
    after_id: int | None = Query(default=None, ge=0, le=2147483647),
    db: Session = Depends(get_db),
):
    query = select(Question).order_by(Question.id)
    if concept_id is not None:
        query = query.where(Question.concept_id == concept_id)
    if after_id is not None:
        query = query.where(Question.id > after_id)
    if limit is not None:
        query = query.limit(limit)
    questions = db.scalars(query).all()

    return [
        QuestionResponse(
            id=question.id,
            concept_id=question.concept_id,
            title=question.title,
            description=question.description,
            difficulty=question.difficulty,
            options=json.loads(question.options),
        )
        for question in questions
    ]




@app.post("/attempts", response_model=AttemptResponse)
def submit_attempt(
    attempt: AttemptCreate,
    db: Session = Depends(get_db),
):
    try:
        feedback = create_attempt(db, attempt)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return feedback


@app.get("/students/{student_id}/history", response_model=LearningHistoryResponse)
def student_history(
    student_id: int,
    concept_id: int | None = Query(default=None, gt=0, le=2147483647),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, min_length=1, max_length=1024),
    db: Session = Depends(get_db),
):
    return get_learning_history(db, student_id, concept_id, limit, cursor)


@app.get("/recommendations/{student_id}")
def student_recommendations(
    student_id: int,
    db: Session = Depends(get_db),
):
    student = db.get(Student, student_id)

    if student is None:
        raise HTTPException(
            status_code=404,
            detail="Student not found",
        )

    recommendations = get_recommendations(db, student_id)

    return {
        "student_id": student_id,
        "total_recommendations": len(recommendations),
        "recommendations": recommendations,
    }


@app.get("/progress/{student_id}", response_model=ProgressResponse)
def student_progress(student_id: int, db: Session = Depends(get_db)):
    if db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="Student not found")

    rows = db.execute(
        select(Concept, Mastery)
        .outerjoin(
            Mastery,
            (Mastery.concept_id == Concept.id)
            & (Mastery.student_id == student_id),
        )
        .order_by(Concept.id)
    ).all()

    concepts = []
    for concept, mastery in rows:
        # Submission creates a mastery record on the first attempt.
        probability = mastery.probability if mastery is not None else INITIAL_MASTERY
        concepts.append(ConceptProgressResponse(
            concept_id=concept.id,
            concept_name=concept.name,
            mastery_probability=probability,
            status=get_mastery_status(probability),
            attempted=mastery is not None,
        ))

    return ProgressResponse(
        student_id=student_id,
        summary=ProgressSummary(
            total_concepts=len(concepts),
            attempted_concepts=sum(item.attempted for item in concepts),
            mastered_concepts=sum(item.status == "mastered" for item in concepts),
        ),
        concepts=concepts,
    )


@app.get("/concept-graph", response_model=ConceptGraphResponse)
def concept_graph(db: Session = Depends(get_db)):
    graph = build_concept_graph(db)
    return {
        "nodes": [
            {"id": node_id, "name": graph.nodes[node_id]["name"]}
            for node_id in sorted(graph.nodes)
        ],
        "edges": [
            {"source": source, "target": target}
            for source, target in sorted(graph.edges)
        ],
    }


@app.get("/concepts")
def get_concepts(db: Session = Depends(get_db)):
    concepts = db.scalars(
        select(Concept).order_by(Concept.id)
    ).all()

    return [
        {
            "id": concept.id,
            "name": concept.name,
            "description": concept.description,
        }
        for concept in concepts
    ]


@app.get("/concepts/{concept_id}/resources", response_model=ConceptResourcesResponse)
def concept_resources(concept_id: int, db: Session = Depends(get_db)):
    concept = db.get(Concept, concept_id)
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    return resources_for_concept(concept)
