"""Progressive adaptive selection. Caller owns the complete database transaction."""
import json
from datetime import timezone
from uuid import uuid4, uuid5
from fastapi import HTTPException
from sqlalchemy import func, select
from app.attempt_service import create_attempt
from app.bkt import INITIAL_MASTERY
from app.concept_graph import build_concept_graph
from app.diagnostic_service import lock_student
from app.mastery_rules import get_mastery_status
from app.models import AdaptiveAssignment, AdaptiveSession, Attempt, Concept, Mastery, Question, utc_now
from app.schemas import AttemptCreate, QuestionResponse
from app.adaptive_schemas import AdaptiveAnswer, AdaptiveFeedback, AdaptiveProgress, AdaptiveResults

TARGET = 5


def eligibility(db, student_id):
    graph = build_concept_graph(db)
    probabilities = {row.concept_id:row.probability for row in db.scalars(select(Mastery).where(Mastery.student_id == student_id))}
    eligible = [node for node in graph.nodes if all(get_mastery_status(probabilities.get(parent, INITIAL_MASTERY)) == 'mastered' for parent in graph.predecessors(node))]
    return graph, probabilities, eligible


def owned(db, student_id, session_id):
    session = db.scalar(select(AdaptiveSession).where(AdaptiveSession.id == session_id, AdaptiveSession.student_id == student_id).execution_options(populate_existing=True))
    if session is None:
        raise HTTPException(404, 'Adaptive session not found')
    return session


def assignments(db, session):
    return db.scalars(select(AdaptiveAssignment).where(AdaptiveAssignment.session_id == session.id).order_by(AdaptiveAssignment.position).execution_options(populate_existing=True)).all()


def assign_next(db, session, position):
    graph, probabilities, eligible = eligibility(db, session.student_id)
    # Rank in SQL: weakest concept, never/least-recently attempted question,
    # concept ID, stable key, question ID. Never materialize the question bank.
    used = select(AdaptiveAssignment.question_id).where(AdaptiveAssignment.session_id == session.id)
    recent = select(Attempt.question_id.label('question_id'), func.max(Attempt.attempted_at).label('last_attempt'))\
        .where(Attempt.student_id == session.student_id).group_by(Attempt.question_id).subquery()
    candidate = db.execute(select(Question, recent.c.last_attempt).outerjoin(recent, recent.c.question_id == Question.id)
        .outerjoin(Mastery, (Mastery.concept_id == Question.concept_id) & (Mastery.student_id == session.student_id))
        .where(Question.concept_id.in_(eligible), ~Question.id.in_(used))
        .order_by(func.coalesce(Mastery.probability, INITIAL_MASTERY), recent.c.last_attempt.asc().nulls_first(),
                  Question.concept_id, Question.question_key.asc().nulls_last(), Question.id).limit(1)).one_or_none()
    if candidate is None:
        session.status = 'completed'
        session.completion_reason = 'eligible_pool_exhausted'
        session.updated_at = session.completed_at = utc_now()
        return
    question, last_attempt = candidate
    concept_id = question.concept_id
    probability = probabilities.get(concept_id, INITIAL_MASTERY)
    initial = ' (initial estimate; no recorded mastery)' if concept_id not in probabilities else ''
    access = 'all immediate prerequisites are mastered' if list(graph.predecessors(concept_id)) else 'it has no prerequisites'
    recency = 'never attempted by this student' if last_attempt is None else 'least recently attempted among the remaining equally weak eligible candidates'
    reason = (f"{graph.nodes[concept_id]['name']} is eligible because {access}. Its BKT estimate is {probability:.1%}{initial}; "
              f"it has the lowest estimate among eligible concepts with unused questions. "
              f"This question is {recency}; remaining ties use concept ID, stable question key, then question ID.")
    db.add(AdaptiveAssignment(session_id=session.id, position=position, question_id=question.id, selection_reason=reason))


def progress(db, session):
    rows = assignments(db, session)
    current = next((row for row in rows if row.attempt_id is None),None) if session.status == 'in_progress' else None
    question = db.get(Question,current.question_id) if current else None
    public = QuestionResponse(id=question.id,concept_id=question.concept_id,title=question.title,description=question.description,
        difficulty=question.difficulty,options=json.loads(question.options)) if question else None
    eligible = None
    if question:
        _,_,ids = eligibility(db,session.student_id)
        eligible = question.concept_id in ids
    return AdaptiveProgress(session_id=session.id,student_id=session.student_id,status=session.status,
        created_at=session.created_at.astimezone(timezone.utc),updated_at=session.updated_at.astimezone(timezone.utc),
        completed_at=session.completed_at.astimezone(timezone.utc) if session.completed_at else None,
        assigned_questions=len(rows),answered_questions=sum(row.attempt_id is not None for row in rows),
        next_position=current.position if current else None,next_question=public,selection_reason=current.selection_reason if current else None,
        current_question_eligible=eligible,blocked_reason='Prerequisites changed. Master the unmet prerequisites or explicitly restart this session.' if eligible is False else None,
        completion_reason=session.completion_reason)


def start(db, student_id, restart_id=None):
    lock_student(db,student_id)
    if restart_id is not None:
        replay = db.scalar(select(AdaptiveSession).where(AdaptiveSession.student_id == student_id,AdaptiveSession.restart_id == restart_id))
        if replay:
            return progress(db,replay)
    latest = db.scalar(select(AdaptiveSession).where(AdaptiveSession.student_id == student_id)
        .order_by((AdaptiveSession.status == 'in_progress').desc(),AdaptiveSession.created_at.desc(),AdaptiveSession.id.desc()).limit(1))
    if latest and restart_id is None:
        return progress(db,latest)
    now = utc_now()
    if latest and latest.status == 'in_progress':
        latest.status='abandoned';latest.updated_at=now;db.flush()
    session = AdaptiveSession(id=uuid4(),student_id=student_id,restart_id=restart_id,status='in_progress',created_at=now,updated_at=now)
    db.add(session);db.flush()
    assign_next(db,session,0);db.flush()
    return progress(db,session)


def submit(db, student_id, session_id, answer: AdaptiveAnswer):
    lock_student(db,student_id)
    session=owned(db,student_id,session_id)
    rows=assignments(db,session)
    replay=next((row for row in rows if row.submission_id == answer.submission_id),None)
    internal_id=uuid5(session.id,str(answer.submission_id))
    if replay:
        saved=db.get(Attempt,replay.attempt_id)
        if replay.question_id != answer.question_id or saved.selected_answer != answer.selected_answer:
            raise HTTPException(409,'Adaptive submission UUID already used with a different question or answer')
        feedback=create_attempt(db,AttemptCreate(student_id=student_id,question_id=answer.question_id,selected_answer=answer.selected_answer,submission_id=internal_id))
        return AdaptiveFeedback(session_id=session.id,position=replay.position,feedback=feedback)
    if session.status != 'in_progress':
        raise HTTPException(409,'Adaptive session is not in progress')
    current=next((row for row in rows if row.attempt_id is None),None)
    if current is None or current.question_id != answer.question_id:
        raise HTTPException(409,'Answer the current assigned adaptive question; skipping or resubmitting is not allowed')
    question=db.get(Question,current.question_id)
    _,_,eligible=eligibility(db,student_id)
    if question.concept_id not in eligible:
        raise HTTPException(409,'The assigned concept is now locked. Master its prerequisites or restart the session.')
    if db.scalar(select(Attempt.id).where(Attempt.student_id==student_id,Attempt.submission_id==internal_id)) is not None:
        raise HTTPException(409,'Submission identifier is already associated with another attempt')
    feedback=create_attempt(db,AttemptCreate(student_id=student_id,question_id=answer.question_id,selected_answer=answer.selected_answer,submission_id=internal_id))
    current.attempt_id=feedback.attempt_id;current.submission_id=answer.submission_id
    session.updated_at=utc_now()
    db.flush()
    if len(rows) >= TARGET:
        session.status='completed';session.completion_reason='target_reached';session.completed_at=session.updated_at
    else:
        assign_next(db,session,len(rows))
    db.flush()
    return AdaptiveFeedback(session_id=session.id,position=current.position,feedback=feedback)


def results(db, session):
    if session.status != 'completed':
        raise HTTPException(409,'Adaptive session must be completed before retrieving results')
    rows=db.execute(select(AdaptiveAssignment,Attempt,Concept).join(Attempt,Attempt.id==AdaptiveAssignment.attempt_id)
        .join(Question,Question.id==AdaptiveAssignment.question_id).join(Concept,Concept.id==Question.concept_id)
        .where(AdaptiveAssignment.session_id==session.id).order_by(AdaptiveAssignment.position)).all()
    concepts={};questions=[]
    for assignment,attempt,concept in rows:
        previous=concepts.get(concept.id)
        concepts[concept.id]=dict(concept_id=concept.id,concept_name=concept.name,estimated_mastery=attempt.mastery_after,
            status=get_mastery_status(attempt.mastery_after) if attempt.mastery_after is not None else None,
            answered_questions=(previous['answered_questions'] if previous else 0)+1)
        questions.append(dict(position=assignment.position,question_id=assignment.question_id,concept_id=concept.id,
            selection_reason=assignment.selection_reason,is_correct=attempt.is_correct))
    correct=sum(attempt.is_correct for _,attempt,_ in rows)
    return AdaptiveResults(session_id=session.id,student_id=session.student_id,status='completed',answered_questions=len(rows),
        correct_answers=correct,accuracy=correct/len(rows) if rows else None,completion_reason=session.completion_reason,
        concepts=list(concepts.values()),questions=questions)
