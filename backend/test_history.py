import base64
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from app.bkt import INITIAL_MASTERY, update_mastery
from app.models import Attempt, Concept, Mastery, Question, Student
from conftest import TestingSessionLocal, test_engine


WHEN = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def history_data(client):
    with TestingSessionLocal() as db:
        students = [Student(username=name) for name in ['history_student', 'other_history_student']]
        concepts = [Concept(name=name) for name in ['Arrays', 'Search', 'Unattempted']]
        db.add_all([*students, *concepts])
        db.flush()
        questions = [Question(concept_id=concept.id, title=concept.name, description='Choose one',
            difficulty='easy', options='["0","1"]', correct_answer=0) for concept in concepts[:2]]
        db.add_all(questions)
        db.commit()
        return dict(student=students[0].id, other=students[1].id,
            concepts=[concept.id for concept in concepts], questions=[question.id for question in questions])


def record(data, entries):
    with TestingSessionLocal() as db:
        attempts = []
        for entry in entries:
            correct = entry.get('correct', True)
            attempts.append(Attempt(
                student_id=entry.get('student', data['student']),
                question_id=data['questions'][entry.get('question', 0)],
                attempted_at=entry.get('when', WHEN), selected_answer=0 if correct else 1,
                is_correct=correct, mastery_before=entry.get('before'), mastery_after=entry.get('after'),
            ))
        db.add_all(attempts)
        db.commit()
        return [attempt.id for attempt in attempts]


def history(client, data, **params):
    return client.get(f"/students/{data['student']}/history", params=params)


def test_empty_history_for_existing_student(client, history_data):
    response = history(client, history_data)
    assert response.status_code == 200
    assert response.json() == {'student_id': history_data['student'], 'concept_id': None, 'attempts': [], 'next_cursor': None}


def test_missing_student_returns_404(client):
    response = client.get('/students/999999/history')
    assert response.status_code == 404
    assert response.json() == {'detail': 'Student not found'}


def test_single_legacy_attempt_contains_only_public_recorded_fields(client, history_data):
    ids = record(history_data, [{'correct': False}])
    response = history(client, history_data)
    assert response.status_code == 200
    assert response.json()['next_cursor'] is None
    assert response.json()['attempts'] == [{
        'attempt_id': ids[0], 'question_id': history_data['questions'][0],
        'concept_id': history_data['concepts'][0], 'attempted_at': WHEN.isoformat().replace('+00:00', 'Z'),
        'is_correct': False, 'mastery_before': None, 'mastery_after': None,
        'origin': 'ordinary_practice', 'snapshots_available': False,
    }]


def test_history_orders_by_time_then_id_and_paginates_tied_timestamps(client, history_data):
    ids = record(history_data, [
        {'when': WHEN + timedelta(seconds=2)}, {}, {},
        {'when': WHEN + timedelta(microseconds=1)}, {},
    ])
    expected = [ids[1], ids[2], ids[4], ids[3], ids[0]]
    all_ids = []
    cursor = None
    for _ in expected:
        params = {'limit': 1}
        if cursor is not None:
            params['cursor'] = cursor
        response = history(client, history_data, **params)
        assert response.status_code == 200
        body = response.json()
        all_ids.extend(item['attempt_id'] for item in body['attempts'])
        cursor = body['next_cursor']
    assert all_ids == expected
    assert len(set(all_ids)) == 5
    assert cursor is None


def test_next_cursor_requires_an_extra_record_and_limit_can_change(client, history_data):
    ids = record(history_data, [{}, {}, {}, {}])
    first = history(client, history_data, limit=2).json()
    assert first['next_cursor']
    second = history(client, history_data, limit=2, cursor=first['next_cursor']).json()
    assert [item['attempt_id'] for item in second['attempts']] == ids[2:]
    assert second['next_cursor'] is None
    repeat = history(client, history_data, limit=100, cursor=first['next_cursor']).json()
    assert repeat['attempts'] == second['attempts']
    assert repeat['next_cursor'] is None


def test_valid_cursor_beyond_history_returns_an_empty_terminal_page(client, history_data):
    ids = record(history_data, [{}])
    position = dict(version=1, student_id=history_data['student'], concept_id=None,
        attempted_at=(WHEN + timedelta(days=1)).isoformat(), attempt_id=ids[0])
    cursor = base64.urlsafe_b64encode(json.dumps(position).encode()).decode().rstrip('=')
    response = history(client, history_data, cursor=cursor)
    assert response.status_code == 200
    assert response.json()['attempts'] == []
    assert response.json()['next_cursor'] is None


def test_new_later_attempts_remain_visible_when_continuing_pagination(client, history_data):
    ids = record(history_data, [{}, {}])
    first = history(client, history_data, limit=1).json()
    new_id = record(history_data, [{'when': WHEN + timedelta(seconds=1)}])[0]
    second = history(client, history_data, cursor=first['next_cursor']).json()
    assert [item['attempt_id'] for item in second['attempts']] == [ids[1], new_id]
    assert second['next_cursor'] is None


def test_concept_filter_and_filtered_pagination(client, history_data):
    ids = record(history_data, [{}, {'question': 1}, {}, {'question': 1}])
    concept = history_data['concepts'][1]
    first = history(client, history_data, concept_id=concept, limit=1).json()
    assert first['concept_id'] == concept
    assert [item['attempt_id'] for item in first['attempts']] == [ids[1]]
    second = history(client, history_data, concept_id=concept, cursor=first['next_cursor']).json()
    assert [item['attempt_id'] for item in second['attempts']] == [ids[3]]
    assert second['next_cursor'] is None
    assert history(client, history_data, concept_id=history_data['concepts'][2]).json()['attempts'] == []


def test_student_isolation_and_cursor_scope(client, history_data):
    data = history_data
    ids = record(data, [{}, {}, {'student': data['other']}])
    first = history(client, data, limit=1).json()
    assert first['attempts'][0]['attempt_id'] == ids[0]
    other = client.get(f"/students/{data['other']}/history").json()
    assert [item['attempt_id'] for item in other['attempts']] == [ids[2]]
    wrong_student = client.get(f"/students/{data['other']}/history", params={'cursor': first['next_cursor']})
    assert wrong_student.status_code == 422
    assert history(client, data, cursor=first['next_cursor'], concept_id=data['concepts'][0]).status_code == 422
    filtered = history(client, data, limit=1, concept_id=data['concepts'][0]).json()
    assert history(client, data, cursor=filtered['next_cursor']).status_code == 422


@pytest.mark.parametrize('params', [
    {'limit': 0}, {'limit': -1}, {'limit': 101}, {'limit': 'abc'}, {'limit': '1.5'},
    {'concept_id': 0}, {'concept_id': -1}, {'concept_id': 'abc'}, {'concept_id': '1.5'},
    {'concept_id': 2147483648}, {'cursor': ''}, {'cursor': 'x' * 1025},
    {'cursor': 'not-base64!'}, {'cursor': 'e30'}, {'cursor': 'W10'},
])
def test_invalid_query_parameters_return_422(client, history_data, params):
    assert history(client, history_data, **params).status_code == 422


def test_nonexistent_concept_returns_404(client, history_data):
    response = history(client, history_data, concept_id=999999)
    assert response.status_code == 404
    assert response.json() == {'detail': 'Concept not found'}


@pytest.mark.parametrize('change', [
    {'version': 2}, {'version': True}, {'attempted_at': '2026-01-01T10:00:00'},
    {'attempted_at': 'invalid'}, {'attempt_id': 0}, {'attempt_id': '1'},
    {'attempt_id': 2147483648}, {'extra': 'unexpected'},
])
def test_structurally_invalid_cursors_are_rejected(client, history_data, change):
    position = dict(version=1, student_id=history_data['student'], concept_id=None,
        attempted_at=WHEN.isoformat(), attempt_id=1)
    position.update(change)
    cursor = base64.urlsafe_b64encode(json.dumps(position).encode()).decode().rstrip('=')
    response = history(client, history_data, cursor=cursor)
    assert response.status_code == 422
    assert response.json() == {'detail': 'Invalid history cursor'}


def test_partial_snapshots_are_preserved_without_claiming_complete_history(client, history_data):
    record(history_data, [{'before': 0.0}, {'after': 0.6}, {'before': 0.0, 'after': 0.1}])
    attempts = history(client, history_data).json()['attempts']
    assert [(item['mastery_before'], item['mastery_after'], item['snapshots_available']) for item in attempts] == [
        (0.0, None, False), (None, 0.6, False), (0.0, 0.1, True),
    ]


def test_real_submissions_expose_stored_snapshots_without_duplicate_history_on_retry(client, history_data):
    request = dict(student_id=history_data['student'], question_id=history_data['questions'][0],
        selected_answer=0, submission_id=str(uuid4()))
    first = client.post('/attempts', json=request)
    assert first.status_code == 200
    second = client.post('/attempts', json={**request, 'submission_id': str(uuid4()), 'selected_answer': 1})
    assert second.status_code == 200
    assert client.post('/attempts', json=request).json() == first.json()
    attempts = history(client, history_data).json()['attempts']
    assert len(attempts) == 2
    after_first = update_mastery(INITIAL_MASTERY, True)
    after_second = update_mastery(after_first, False)
    assert attempts[0]['mastery_before'] == INITIAL_MASTERY
    assert attempts[0]['mastery_after'] == pytest.approx(after_first)
    assert attempts[1]['mastery_before'] == pytest.approx(after_first)
    assert attempts[1]['mastery_after'] == pytest.approx(after_second)
    assert [item['is_correct'] for item in attempts] == [True, False]
    assert all(item['snapshots_available'] for item in attempts)


def test_default_limit_and_bounded_joined_read_only_query_count(client, history_data):
    record(history_data, [{} for _ in range(52)])
    statements = []

    def track(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    with TestingSessionLocal() as db:
        before = [(row.id, row.mastery_before, row.mastery_after, row.attempted_at) for row in db.scalars(select(Attempt)).all()]
    event.listen(test_engine, 'before_cursor_execute', track)
    try:
        response = history(client, history_data)
        assert response.status_code == 200
        assert len(response.json()['attempts']) == 50
        assert response.json()['next_cursor']
        assert len(statements) == 2
        assert all(statement.lstrip().upper().startswith('SELECT') for statement in statements)
        assert 'JOIN questions' in statements[-1]
        assert 'correct_answer' not in statements[-1]
        statements.clear()
        assert history(client, history_data, concept_id=history_data['concepts'][0]).status_code == 200
        assert len(statements) == 3
    finally:
        event.remove(test_engine, 'before_cursor_execute', track)
    with TestingSessionLocal() as db:
        after = [(row.id, row.mastery_before, row.mastery_after, row.attempted_at) for row in db.scalars(select(Attempt)).all()]
        assert after == before
        assert db.scalars(select(Mastery)).all() == []
