import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError

from app.bkt import INITIAL_MASTERY, update_mastery
from app.models import Attempt, Concept, Mastery, Question, Student
from app.question_import import ImportConflict, load_questions, synchronize_questions, validate_questions
from conftest import TestingSessionLocal, test_engine

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/questions.json"
CONTENT = json.loads(SOURCE.read_text(encoding="utf-8"))


def import_content(content=None, dry_run=False):
    with TestingSessionLocal.begin() as db:
        if dry_run:
            db.execute(text("SET TRANSACTION READ ONLY"))
        return synchronize_questions(db, validate_questions(CONTENT if content is None else content), dry_run=dry_run)


def seed_concepts():
    with TestingSessionLocal.begin() as db:
        db.add_all([Concept(id=200 + index * 7, name=name) for index, name in enumerate(sorted({row['concept'] for row in CONTENT}))])


def test_source_preserves_all_original_fields_and_has_reviewed_explanations():
    frozen = json.loads((ROOT / "backend/migrations/data/0004_legacy_questions.json").read_text(encoding="utf-8"))["questions"]
    assert CONTENT == frozen
    assert len(load_questions(SOURCE)) == len({item['question_key'] for item in CONTENT}) == 25
    expected_answers = [2,1,0,1,2,2,1,2,0,0,2,0,1,2,1,2,1,0,1,2,2,1,2,0,2]
    reviewed_terms = ['O(1)', 'O(n)', 'n elements', 'upper bound', 'n squared', 'halving', 'sequentially', 'O(n)', 'first', 'sorted', 'O(log n)', 'fixed-width', 'adjacent', 'O(n^2)', 'complete pass', 'divide and conquer', 'O(n log n)', 'sorted subarrays', 'base case', '24', 'stack', 'equal keys', 'comparing keys', 'O(1)', 'Omega(n log n)']
    for item, index, term in zip(CONTENT, expected_answers, reviewed_terms):
        assert item['correct_answer'] == index
        assert term.lower() in item['explanation'].lower()


@pytest.mark.parametrize('change', [
    {'question_key': 'INVALID KEY'}, {'question_key': ''}, {'correct_answer': -1}, {'correct_answer': 9},
    {'correct_answer': True}, {'correct_answer': '2'}, {'explanation': None}, {'explanation': '   '},
    {'options': ['one']}, {'options': ['same', 'same']}, {'options': [3, 'text']},
    {'description': ''}, {'difficulty': 'extreme'}, {'extra': 'field'},
])
def test_invalid_content_rejected(change):
    with pytest.raises(ValueError):
        validate_questions([{**CONTENT[0], **change}])


def test_duplicate_keys_records_and_json_fields_rejected(tmp_path):
    for rows in [[CONTENT[0], CONTENT[0]], [CONTENT[0], {**CONTENT[0], 'question_key': 'different-001'}]]:
        with pytest.raises(ValueError, match='Duplicate'):
            validate_questions(rows)
    path = tmp_path / 'bad.json'
    path.write_text('[{"question_key":"a-001","question_key":"b-001"}]')
    with pytest.raises(ValueError, match='Duplicate JSON'):
        load_questions(path)
    with pytest.raises(ValueError, match='array'):
        validate_questions({})


def test_import_reimport_new_insert_updates_and_omission_preserve_ids(client):
    seed_concepts()
    assert import_content() == {'inserts':25,'updates':0,'unchanged':0,'conflicts':[]}
    with TestingSessionLocal() as db:
        old_ids = {row.question_key: row.id for row in db.scalars(select(Question))}
    assert import_content()['unchanged'] == 25
    edited = copy.deepcopy(CONTENT[0])
    edited.update(explanation='Indexing computes the slot directly in constant time.', title='Array indexing (reviewed)')
    assert import_content([edited])['updates'] == 1
    added = {**CONTENT[1], 'question_key':'arrays-004','title':'Additional array question','description':'A new authored question for importer testing.'}
    assert import_content([added])['inserts'] == 1
    with TestingSessionLocal() as db:
        rows = db.scalars(select(Question)).all()
        assert len(rows) == 26
        assert {row.question_key: row.id for row in rows if row.question_key in old_ids} == old_ids
        assert db.scalar(select(Question).where(Question.question_key == edited['question_key'])).explanation == edited['explanation']


def test_dry_run_reports_all_plan_categories_without_writes(client):
    seed_concepts()
    assert import_content(dry_run=True)['inserts'] == 25
    with TestingSessionLocal() as db:
        assert db.scalars(select(Question)).all() == []
    import_content(CONTENT[:2])
    plan = [CONTENT[0], {**CONTENT[1], 'explanation':'A reviewed explanation edit.'}, CONTENT[2]]
    report = import_content(plan, dry_run=True)
    assert report == {'inserts':1,'updates':1,'unchanged':1,'conflicts':[]}
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Question)).all()) == 2
        assert db.scalar(select(Question).where(Question.question_key == CONTENT[1]['question_key'])).explanation == CONTENT[1]['explanation']


@pytest.mark.parametrize('change', [
    {'concept':'Unknown'}, {'concept':'Recursion'}, {'options':['new','options'], 'correct_answer':0},
    {'correct_answer':1}, {'question_key':'alias-001'},
])
def test_conflicts_reject_entire_import_and_dry_run_reports_them(client, change):
    seed_concepts()
    import_content(CONTENT[:1])
    rows = [CONTENT[1], {**CONTENT[0], **change}]
    report = import_content(rows, dry_run=True)
    assert report['conflicts']
    with pytest.raises(ImportConflict):
        import_content(rows)
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Question)).all()) == 1


def test_import_database_failure_rolls_back_entire_batch(client):
    seed_concepts()
    import_content(CONTENT[:1])
    calls = 0
    def fail_insert_after_update(conn, cursor, statement, parameters, context, executemany):
        nonlocal calls
        if statement.startswith('INSERT INTO questions'):
            calls += 1
            raise RuntimeError('Injected persistence failure')
    event.listen(test_engine, 'before_cursor_execute', fail_insert_after_update)
    try:
        with pytest.raises(RuntimeError, match='Injected'):
            with TestingSessionLocal.begin() as db:
                synchronize_questions(db, validate_questions([{**CONTENT[0], 'explanation':'Should roll back'}]))
                # A successful flush has occurred; a subsequent persistence
                # failure must still undo the earlier update in this transaction.
                synchronize_questions(db, validate_questions(CONTENT[1:]))
    finally:
        event.remove(test_engine, 'before_cursor_execute', fail_insert_after_update)
    assert calls
    with TestingSessionLocal() as db:
        rows = db.scalars(select(Question)).all()
        assert len(rows) == 1
        assert rows[0].explanation == CONTENT[0]['explanation']


def test_keys_unique_and_immutable_in_database(client):
    seed_concepts()
    import_content(CONTENT[:1])
    with pytest.raises(IntegrityError):
        with TestingSessionLocal.begin() as db:
            original = db.scalar(select(Question))
            db.add(Question(question_key=original.question_key, concept_id=original.concept_id, title='Other', description='Other', difficulty='easy', options='["a","b"]', correct_answer=0))
    with pytest.raises(Exception, match='immutable'):
        with TestingSessionLocal.begin() as db:
            db.execute(text("UPDATE questions SET question_key='replacement-001'"))


@pytest.mark.parametrize('index', range(25))
def test_authored_feedback_only_after_submission_and_snapshots_unchanged(client, index):
    seed_concepts()
    import_content([CONTENT[index]])
    with TestingSessionLocal.begin() as db:
        db.add(Student(id=900, username='explanation-reader'))
        question = db.scalar(select(Question))
        question_id = question.id
    public = client.get('/questions').json()
    assert len(public) == 1
    assert set(public[0]) == {'id','concept_id','title','description','difficulty','options'}
    assert client.post('/attempts', json={'student_id':999,'question_id':question_id,'selected_answer':0}).status_code == 404
    selected = CONTENT[index]['correct_answer'] if index % 2 == 0 else (CONTENT[index]['correct_answer'] + 1) % len(CONTENT[index]['options'])
    result = client.post('/attempts', json={'student_id':900,'question_id':question_id,'selected_answer':selected}).json()
    assert result['explanation'] == CONTENT[index]['explanation']
    assert result['is_correct'] == (index % 2 == 0)
    expected = update_mastery(INITIAL_MASTERY, index % 2 == 0)
    assert result['mastery_probability'] == pytest.approx(expected)
    with TestingSessionLocal() as db:
        attempt = db.scalar(select(Attempt))
        assert attempt.mastery_before == INITIAL_MASTERY
        assert attempt.mastery_after == pytest.approx(expected)
        assert attempt.feedback_explanation == result['explanation']


@pytest.mark.parametrize('explanation', [None, 'The first option is correct.'])
def test_retry_keeps_recorded_feedback_after_question_edits(client, explanation):
    with TestingSessionLocal.begin() as db:
        db.add_all([Concept(id=901, name='Arrays'), Student(id=902, username='retry')])
        db.flush()
        db.add(Question(id=903, concept_id=901, title='Index', description='Which?', difficulty='easy', options='["a","b"]', correct_answer=0, explanation=explanation))
    payload = {'student_id':902,'question_id':903,'selected_answer':0,'submission_id':str(uuid4())}
    original = client.post('/attempts', json=payload)
    assert original.status_code == 200
    assert original.json()['explanation'] == explanation
    with TestingSessionLocal.begin() as db:
        question = db.get(Question, 903)
        question.explanation = 'Later edited explanation.'
        question.correct_answer = 1
    assert client.post('/attempts', json=payload).json() == original.json()
    assert client.post('/attempts', json={**payload,'selected_answer':1}).status_code == 409
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all()) == 1
        assert db.scalar(select(Mastery)).probability == original.json()['mastery_probability']
    # A genuinely new submission sees the current authored explanation.
    assert client.post('/attempts', json={**payload,'submission_id':str(uuid4())}).json()['explanation'] == 'Later edited explanation.'


def test_filtered_question_query_is_bounded_in_sql_and_never_leaks_answers(client):
    seed_concepts()
    import_content()
    with TestingSessionLocal() as db:
        first = db.scalar(select(Question).where(Question.question_key == 'arrays-001'))
        concept_id = first.concept_id
        first_id = first.id
    statements = []
    def track(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(test_engine, 'before_cursor_execute', track)
    try:
        result = client.get(f'/questions?concept_id={concept_id}&after_id={first_id}&limit=1')
    finally:
        event.remove(test_engine, 'before_cursor_execute', track)
    assert result.status_code == 200
    assert len(result.json()) == 1
    assert result.json()[0]['id'] > first_id
    assert 'WHERE' in statements[0] and 'LIMIT' in statements[0]
    assert set(result.json()[0]) == {'id','concept_id','title','description','difficulty','options'}
    for query in ['limit=0','limit=101','concept_id=-1','after_id=-1']:
        assert client.get('/questions?' + query).status_code == 422
