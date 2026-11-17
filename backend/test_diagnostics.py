import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4, uuid5

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select

from app import diagnostic_service as service
from app.bkt import INITIAL_MASTERY, update_mastery
from app.diagnostic_schemas import DiagnosticAnswer
from app.models import Attempt, Concept, DiagnosticAssignment, DiagnosticSession, Mastery, Prerequisite, Question, Student
from app.question_import import load_questions, synchronize_questions
from conftest import TestingSessionLocal, test_engine

PREFIX = '/students/10/diagnostics'


@pytest.fixture
def setup(client):
    content = load_questions(Path(__file__).resolve().parents[1] / 'data/questions.json')
    with TestingSessionLocal.begin() as db:
        db.add_all([Student(id=10, username='diagnostic-one'), Student(id=20, username='diagnostic-two')])
        db.add_all([Concept(id=100 + index * 9, name=name) for index, name in enumerate(sorted({row.concept for row in content}))])
        db.flush()
        synchronize_questions(db, content)
    return client


def start(client):
    response = client.post(PREFIX + '/start')
    assert response.status_code == 200, response.text
    return response.json()


def answer_for(question_id, correct=True, submission_id=None):
    with TestingSessionLocal() as db:
        question = db.get(Question, question_id)
        selected = question.correct_answer if correct else (question.correct_answer + 1) % len(json.loads(question.options))
    return {'question_id':question_id,'selected_answer':selected,'submission_id':str(submission_id or uuid4())}


def finish(client, progress):
    replies = []
    for index in range(6):
        payload = answer_for(progress['next_question']['id'], index % 2 == 0)
        response = client.post(f"{PREFIX}/{progress['session_id']}/answers", json=payload)
        assert response.status_code == 200, response.text
        replies.append((payload,response.json()))
        progress = client.get(f"{PREFIX}/{progress['session_id']}").json()
    return progress, replies


def test_start_resume_persisted_balanced_order_and_no_leak(setup):
    initial = start(setup)
    assert initial['status'] == 'in_progress'
    assert initial['answered_questions'] == 0 and initial['total_questions'] == 6
    assert initial['next_position'] == 0
    assert start(setup) == initial
    assert setup.get(f"{PREFIX}/{initial['session_id']}").json() == initial
    assert set(initial['next_question']) == {'id','concept_id','title','description','difficulty','options'}
    with TestingSessionLocal() as db:
        session = db.get(DiagnosticSession, UUID(initial['session_id']))
        assignments = service.assignments(db, session)
        assert [row.position for row in assignments] == list(range(6))
        assert len({row.question_id for row in assignments}) == 6
        counts = {}
        for row in assignments:
            concept = db.get(Concept, db.get(Question,row.question_id).concept_id)
            counts[concept.name] = counts.get(concept.name,0) + 1
        assert counts == {'Arrays':2,'Time Complexity':2,'Recursion':2}
        assert len(db.scalars(select(DiagnosticSession)).all()) == 1
        assert db.scalars(select(Attempt)).all() == []
        assert db.scalars(select(Mastery)).all() == []


def test_full_completion_exact_bkt_results_and_results_do_not_drift(setup):
    progress,replies = finish(setup,start(setup))
    assert progress['status'] == 'completed' and progress['completed_at']
    assert progress['next_question'] is None and progress['answered_questions'] == 6
    path = f"{PREFIX}/{progress['session_id']}"
    result = setup.get(path + '/results').json()
    assert setup.post(path + '/complete').json() == result
    assert result['correct_answers'] == 3 and result['accuracy'] == 0.5
    assert result['mastery_basis'] == 'last_diagnostic_attempt'
    assert len(result['concepts']) == 3
    with TestingSessionLocal() as db:
        attempts = db.scalars(select(Attempt).order_by(Attempt.id)).all()
        assert len(attempts) == 6
        expected = INITIAL_MASTERY
        for index,attempt in enumerate(attempts):
            if index % 2 == 0: expected = INITIAL_MASTERY
            assert attempt.mastery_before == pytest.approx(expected)
            expected = update_mastery(expected, index % 2 == 0)
            assert attempt.mastery_after == pytest.approx(expected)
            assert replies[index][1]['feedback']['explanation'] == attempt.feedback_explanation
        assert all(item['estimated_mastery'] == pytest.approx(expected) for item in result['concepts'])
    payload,replay = replies[-1]
    assert setup.post(path + '/answers',json=payload).json() == replay
    assert setup.post(path + '/answers',json={**payload,'submission_id':str(uuid4())}).status_code == 409
    assert start(setup)['session_id'] == progress['session_id']
    # Results summarize recorded diagnostic snapshots, not later ordinary practice.
    assert setup.post('/attempts',json={'student_id':10,**{key:payload[key] for key in ['question_id','selected_answer']}}).status_code == 200
    assert setup.get(path + '/results').json() == result
    history = setup.get('/students/10/history').json()['attempts']
    assert [row['origin'] for row in history] == ['diagnostic'] * 6 + ['ordinary_practice']
    assert setup.get('/recommendations/10').status_code == 200


def test_restart_preserves_learning_and_retries_across_sessions_are_separate(setup):
    old = start(setup)
    payload = answer_for(old['next_question']['id'])
    path = f"{PREFIX}/{old['session_id']}"
    recorded = setup.post(path+'/answers',json=payload).json()
    with TestingSessionLocal() as db:
        prior = db.scalar(select(Mastery)).probability
    request = {'request_id':str(uuid4())}
    new = setup.post(PREFIX+'/restart',json=request).json()
    assert new['session_id'] != old['session_id']
    assert setup.post(PREFIX+'/restart',json=request).json() == new
    assert setup.get(path).json()['status'] == 'abandoned'
    assert setup.get(path).json()['next_question'] is None
    assert setup.post(path+'/answers',json=payload).json() == recorded
    assert setup.post(path+'/answers',json={**payload,'submission_id':str(uuid4())}).status_code == 409
    with TestingSessionLocal() as db:
        assert db.scalar(select(Mastery)).probability == prior
    # Same external UUID in a new session represents a distinct diagnostic attempt.
    assert setup.post(f"{PREFIX}/{new['session_id']}/answers",json=payload).status_code == 200
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all()) == 2
        assert db.scalar(select(Mastery)).probability == pytest.approx(update_mastery(prior,True))
    later = setup.post(PREFIX+'/restart',json={'request_id':str(uuid4())}).json()
    assert setup.post(PREFIX+'/restart',json=request).json()['status'] == 'abandoned'
    assert start(setup)['session_id'] == later['session_id']


def test_conflicting_uuid_skip_duplicate_and_invalid_answer_do_not_update_bkt(setup):
    progress = start(setup)
    path = f"{PREFIX}/{progress['session_id']}"
    with TestingSessionLocal() as db:
        rows = service.assignments(db,db.get(DiagnosticSession,UUID(progress['session_id'])))
        later = rows[1].question_id
    assert setup.post(path+'/complete').status_code == 409
    assert setup.get(path+'/results').status_code == 409
    assert setup.post(path+'/answers',json=answer_for(later)).status_code == 409
    valid = answer_for(progress['next_question']['id'])
    assert setup.post(path+'/answers',json={**valid,'selected_answer':999}).status_code == 422
    assert setup.get(path).json()['answered_questions'] == 0
    recorded = setup.post(path+'/answers',json=valid).json()
    assert setup.post(path+'/answers',json=valid).json() == recorded
    assert setup.post(path+'/answers',json={**valid,'selected_answer':(valid['selected_answer']+1)%4}).status_code == 409
    assert setup.post(path+'/answers',json={**valid,'question_id':later}).status_code == 409
    assert setup.post(path+'/answers',json={**valid,'submission_id':str(uuid4())}).status_code == 409
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all()) == 1


def test_student_isolation_missing_students_and_uuid_validation(setup):
    progress = start(setup)
    other = f"/students/20/diagnostics/{progress['session_id']}"
    assert setup.get(other).status_code == 404
    assert setup.get(other+'/results').status_code == 404
    assert setup.post(other+'/answers',json=answer_for(progress['next_question']['id'])).status_code == 404
    assert setup.post(other+'/complete').status_code == 404
    assert setup.post('/students/999/diagnostics/start').status_code == 404
    assert setup.get(PREFIX+'/'+str(uuid4())).status_code == 404
    assert setup.get(PREFIX+'/invalid-uuid').status_code == 422
    assert setup.post(PREFIX+'/restart',json={}).status_code == 422
    path = f"{PREFIX}/{progress['session_id']}/answers"
    assert setup.post(path,json={'question_id':progress['next_question']['id'],'selected_answer':0}).status_code == 422
    assert setup.post(path,json={**answer_for(progress['next_question']['id']),'selected_answer':True}).status_code == 422


def test_insufficient_selection_does_not_abandon_existing_session(setup):
    progress = start(setup)
    with TestingSessionLocal.begin() as db:
        # Keep assigned questions referenced: move the unassigned third recursion
        # question to another concept and change the concept's name instead.
        concept = db.scalar(select(Concept).where(Concept.name=='Recursion'))
        concept.name = 'Temporarily unavailable recursion'
    response = setup.post(PREFIX+'/restart',json={'request_id':str(uuid4())})
    assert response.status_code == 409
    assert 'Recursion' in response.json()['detail']
    assert setup.get(f"{PREFIX}/{progress['session_id']}").json()['status'] == 'in_progress'
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(DiagnosticSession)).all()) == 1


def test_prerequisite_locking_does_not_restrict_diagnostic_assignments(setup):
    with TestingSessionLocal.begin() as db:
        concepts = {row.name:row.id for row in db.scalars(select(Concept))}
        db.add(Prerequisite(concept_id=concepts['Arrays'],prerequisite_id=concepts['Recursion']))
    progress = start(setup)
    assert setup.post(f"{PREFIX}/{progress['session_id']}/answers",json=answer_for(progress['next_question']['id'])).status_code == 200


def test_transaction_failure_rolls_back_attempt_mastery_and_assignment(setup):
    progress = start(setup)
    def fail(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith('UPDATE diagnostic_assignments'):
            raise RuntimeError('Injected association failure')
    event.listen(test_engine,'before_cursor_execute',fail)
    try:
        with pytest.raises(RuntimeError,match='Injected'):
            setup.post(f"{PREFIX}/{progress['session_id']}/answers",json=answer_for(progress['next_question']['id']))
    finally:
        event.remove(test_engine,'before_cursor_execute',fail)
    with TestingSessionLocal() as db:
        assert db.scalars(select(Attempt)).all() == []
        assert db.scalars(select(Mastery)).all() == []
    assert setup.get(f"{PREFIX}/{progress['session_id']}").json()['answered_questions'] == 0


def parallel(operations):
    barrier = Barrier(len(operations))
    def run(operation):
        with TestingSessionLocal() as db:
            barrier.wait(timeout=10)
            try:
                result = operation(db)
                db.commit()
                return result
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        return list(pool.map(run,operations))


def test_concurrent_start_and_identical_submission_are_exactly_once(setup):
    starts = parallel([lambda db:service.start(db,10),lambda db:service.start(db,10)])
    assert starts[0].session_id == starts[1].session_id
    progress = starts[0]
    answer = DiagnosticAnswer(**answer_for(progress.next_question.id))
    replies = parallel([lambda db:service.submit(db,10,progress.session_id,answer)]*2)
    assert replies[0] == replies[1]
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(DiagnosticSession)).all()) == 1
        assert len(db.scalars(select(Attempt)).all()) == 1
        assert db.scalar(select(Mastery)).probability == pytest.approx(update_mastery(INITIAL_MASTERY,True))


def test_concurrent_distinct_submissions_cannot_answer_one_assignment_twice(setup):
    progress = start(setup)
    session_id = UUID(progress['session_id'])
    first = DiagnosticAnswer(**answer_for(progress['next_question']['id']))
    second = DiagnosticAnswer(**answer_for(progress['next_question']['id']))
    replies = parallel([lambda db:service.submit(db,10,session_id,first),lambda db:service.submit(db,10,session_id,second)])
    assert sum(reply==409 for reply in replies) == 1
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all()) == 1


def test_concurrent_restart_and_answer_preserve_history_and_one_active_session(setup):
    progress = start(setup)
    session_id = UUID(progress['session_id'])
    answer = DiagnosticAnswer(**answer_for(progress['next_question']['id']))
    replies = parallel([lambda db:service.start(db,10,uuid4()),lambda db:service.submit(db,10,session_id,answer)])
    assert replies[0].status == 'in_progress'
    with TestingSessionLocal() as db:
        sessions = db.scalars(select(DiagnosticSession)).all()
        assert len(sessions) == 2
        assert sum(row.status=='in_progress' for row in sessions) == 1
        assert db.get(DiagnosticSession,session_id).status == 'abandoned'
        assert len(db.scalars(select(Attempt)).all()) == (0 if replies[1]==409 else 1)


def test_concurrent_retried_restart_creates_one_new_session(setup):
    start(setup)
    key = uuid4()
    replies = parallel([lambda db:service.start(db,10,key)]*2)
    assert replies[0].session_id == replies[1].session_id
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(DiagnosticSession)).all()) == 2


def test_first_start_with_missing_coverage_creates_nothing(client):
    with TestingSessionLocal.begin() as db:
        db.add(Student(id=10,username='insufficient'))
    assert client.post(PREFIX+'/start').status_code == 409
    with TestingSessionLocal() as db:
        assert db.scalars(select(DiagnosticSession)).all() == []
        assert db.scalars(select(DiagnosticAssignment)).all() == []


def test_existing_mastery_is_used_and_ordinary_uuid_collision_cannot_be_attached(setup):
    progress = start(setup)
    question_id = progress['next_question']['id']
    with TestingSessionLocal.begin() as db:
        concept_id = db.get(Question,question_id).concept_id
        db.add(Mastery(student_id=10,concept_id=concept_id,probability=0.75))
    payload = answer_for(question_id)
    path = f"{PREFIX}/{progress['session_id']}/answers"
    response = setup.post(path,json=payload).json()
    assert response['feedback']['mastery_probability'] == pytest.approx(update_mastery(0.75,True))
    current = setup.get(f"{PREFIX}/{progress['session_id']}").json()
    external_id = uuid4()
    internal_id = uuid5(UUID(progress['session_id']),str(external_id))
    ordinary = answer_for(current['next_question']['id'])
    assert setup.post('/attempts',json={**ordinary,'student_id':10,'submission_id':str(internal_id)}).status_code == 200
    assert setup.post(path,json={**ordinary,'submission_id':str(external_id)}).status_code == 409
    assert setup.get(f"{PREFIX}/{progress['session_id']}").json()['answered_questions'] == 1
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all()) == 2
        assert len(db.scalars(select(DiagnosticAssignment).where(DiagnosticAssignment.attempt_id.is_not(None))).all()) == 1
