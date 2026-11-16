from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Barrier, Event
from time import monotonic
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.bkt import INITIAL_MASTERY, update_mastery
from app.main import submit_attempt
from app.models import Attempt, Concept, Mastery, Question, Student
from app.schemas import AttemptCreate
from conftest import TestingSessionLocal


@pytest.fixture
def submission_data(client):
    with TestingSessionLocal() as db:
        students = [Student(username=name) for name in ['submitter', 'other_submitter']]
        concept = Concept(name='Idempotent Arrays')
        db.add_all([*students, concept])
        db.flush()
        questions = [Question(concept_id=concept.id, title=title, description='Choose one',
            difficulty='easy', options='["0","1"]', correct_answer=0) for title in ['First', 'Second']]
        db.add_all(questions)
        db.commit()
        return dict(student_id=students[0].id, other_id=students[1].id,
            question_id=questions[0].id, second_id=questions[1].id, concept_id=concept.id)


def payload(data, **overrides):
    return dict(student_id=data['student_id'], question_id=data['question_id'], selected_answer=0, **overrides)


@pytest.mark.parametrize('answer', [0, 1])
def test_identical_retry_returns_original_feedback_even_after_later_practice(client, submission_data, answer):
    data = submission_data
    request = payload(data, submission_id=str(uuid4()))
    request['selected_answer'] = answer
    first = client.post('/attempts', json=request)
    assert first.status_code == 200
    assert set(first.json()) == {'attempt_id', 'student_id', 'question_id', 'selected_answer', 'is_correct', 'correct_answer', 'mastery_probability', 'explanation'}
    later = client.post('/attempts', json=payload(data))
    assert later.status_code == 200
    repeated = client.post('/attempts', json=request)
    assert repeated.status_code == 200
    assert repeated.json() == first.json()
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all()) == 2
        assert db.scalar(select(Mastery)).probability == later.json()['mastery_probability']


@pytest.mark.parametrize('change', ['question', 'answer', 'invalid_answer'])
def test_conflicting_uuid_returns_409_without_changes(client, submission_data, change):
    request = payload(submission_data, submission_id=str(uuid4()))
    first = client.post('/attempts', json=request)
    assert first.status_code == 200
    if change == 'question':
        request['question_id'] = submission_data['second_id']
    else:
        request['selected_answer'] = 1 if change == 'answer' else -1
    assert client.post('/attempts', json=request).status_code == 409
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all()) == 1
        assert db.scalar(select(Mastery)).probability == first.json()['mastery_probability']


def test_uuid_is_scoped_to_student_and_new_uuids_are_new_attempts(client, submission_data):
    key = str(uuid4())
    request = payload(submission_data, submission_id=key)
    first = client.post('/attempts', json=request)
    other_request = {**request, 'student_id': submission_data['other_id'], 'selected_answer': 1}
    other = client.post('/attempts', json=other_request)
    assert first.status_code == other.status_code == 200
    assert first.json()['attempt_id'] != other.json()['attempt_id']
    assert other.json()['student_id'] == submission_data['other_id']
    assert client.post('/attempts', json=other_request).json() == other.json()
    new = client.post('/attempts', json={**request, 'submission_id': str(uuid4())})
    assert new.status_code == 200
    assert new.json()['mastery_probability'] == pytest.approx(update_mastery(first.json()['mastery_probability'], True))
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all()) == 3


def test_omitted_and_null_uuid_allow_repeated_practice(client, submission_data):
    for request in [payload(submission_data), payload(submission_data), payload(submission_data, submission_id=None)]:
        assert client.post('/attempts', json=request).status_code == 200
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all()) == 3


def test_malformed_uuid_does_not_create_attempt(client, submission_data):
    assert client.post('/attempts', json=payload(submission_data, submission_id='invalid')).status_code == 422
    with TestingSessionLocal() as db:
        assert db.scalars(select(Attempt)).all() == []


def test_rolled_back_uuid_can_be_retried(submission_data):
    request = AttemptCreate(**payload(submission_data, submission_id=uuid4()))
    with TestingSessionLocal() as db:
        with patch.object(db, 'commit', side_effect=SQLAlchemyError('Commit failed')):
            with pytest.raises(SQLAlchemyError):
                submit_attempt(request, db)
        assert db.scalars(select(Attempt)).all() == []
        assert db.scalars(select(Mastery)).all() == []
        first = submit_attempt(request, db)
        assert submit_attempt(request, db) == first
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all()) == 1


@pytest.mark.parametrize('mode', ['legacy', 'different_uuids', 'identical', 'conflicting'])
def test_concurrent_first_submissions_are_serialized(submission_data, mode):
    barrier = Barrier(2)
    shared_key = uuid4()

    def worker(index):
        request = payload(submission_data)
        if mode != 'legacy':
            request['submission_id'] = uuid4() if mode == 'different_uuids' else shared_key
        if mode == 'conflicting':
            request['selected_answer'] = index
        with TestingSessionLocal() as db:
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            db.execute(text("SET LOCAL statement_timeout = '10s'"))
            barrier.wait(timeout=5)
            try:
                return submit_attempt(AttemptCreate(**request), db)
            except HTTPException as error:
                assert mode == 'conflicting' and error.status_code == 409
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, index) for index in range(2)]
        results = [future.result(timeout=15) for future in futures]
    with TestingSessionLocal() as db:
        attempts = db.scalars(select(Attempt).order_by(Attempt.id)).all()
        assert len(attempts) == (1 if mode in ['identical', 'conflicting'] else 2)
        probability = INITIAL_MASTERY
        for attempt in attempts:
            assert attempt.mastery_before == pytest.approx(probability)
            probability = update_mastery(probability, attempt.is_correct)
            assert attempt.mastery_after == pytest.approx(probability)
        masteries = db.scalars(select(Mastery)).all()
        assert len(masteries) == 1
        assert masteries[0].probability == pytest.approx(probability)
    if mode == 'identical':
        assert results[0] == results[1]
    if mode == 'conflicting':
        assert results.count(None) == 1


def test_first_attempt_waits_for_student_lock_before_mastery_exists(submission_data):
    worker_pid = Queue()
    pause = Event()
    request = AttemptCreate(**payload(submission_data))

    def worker():
        with TestingSessionLocal() as db:
            db.execute(text("SET LOCAL lock_timeout='5s'"))
            worker_pid.put(db.scalar(text('SELECT pg_backend_pid()')))
            return submit_attempt(request, db)

    with TestingSessionLocal() as db, ThreadPoolExecutor(max_workers=1) as pool:
        db.scalar(select(Student).where(Student.id == request.student_id).with_for_update())
        assert db.scalar(select(Mastery)) is None
        holder_pid = db.scalar(text('SELECT pg_backend_pid()'))
        future = pool.submit(worker)
        pid = worker_pid.get(timeout=5)
        deadline = monotonic() + 3
        blocked = False
        try:
            with TestingSessionLocal() as observer:
                while monotonic() < deadline:
                    blockers = observer.scalar(text('SELECT pg_blocking_pids(:pid)'), {'pid': pid})
                    if holder_pid in blockers:
                        blocked = True
                        break
                    pause.wait(0.01)
            assert blocked, 'Submission did not wait for the Student row lock'
            first = submit_attempt(request, db)
            second = future.result(timeout=10)
            assert second.mastery_probability == pytest.approx(update_mastery(first.mastery_probability, True))
        finally:
            db.rollback()


def test_cached_mastery_is_refreshed_after_student_lock(submission_data):
    request = AttemptCreate(**payload(submission_data))
    with TestingSessionLocal() as db:
        first = submit_attempt(request, db)
        cached = db.scalar(select(Mastery))
        with TestingSessionLocal() as other:
            second = submit_attempt(request, other)
        assert cached.probability == first.mastery_probability
        third = submit_attempt(request, db)
        assert third.mastery_probability == pytest.approx(update_mastery(second.mastery_probability, True))
