import importlib
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4, uuid5
import pytest
from sqlalchemy import event, select

from app import adaptive_service as service
from app.adaptive_schemas import AdaptiveAnswer
from app.bkt import INITIAL_MASTERY, update_mastery
from app.mastery_rules import get_mastery_status
from app.models import AdaptiveAssignment, AdaptiveSession, Attempt, Concept, Mastery, Prerequisite, Question, Student
from conftest import TestingSessionLocal, test_engine
from test_diagnostics import setup as diagnostic_setup, answer_for, parallel
from seed_concepts import prerequisite_data

PREFIX='/students/10/adaptive-sessions'


@pytest.fixture
def setup(diagnostic_setup):
    with TestingSessionLocal.begin() as db:
        concepts={row.name:row.id for row in db.scalars(select(Concept))}
        db.add_all([Prerequisite(concept_id=concepts[concept],prerequisite_id=concepts[parent]) for concept,parent in prerequisite_data])
    return diagnostic_setup


def start(client):
    response=client.post(PREFIX+'/start')
    assert response.status_code==200,response.text
    return response.json()


def set_mastery(values):
    with TestingSessionLocal.begin() as db:
        for name,probability in values.items():
            concept=db.scalar(select(Concept).where(Concept.name==name))
            row=db.scalar(select(Mastery).where(Mastery.student_id==10,Mastery.concept_id==concept.id))
            if row: row.probability=probability
            else: db.add(Mastery(student_id=10,concept_id=concept.id,probability=probability))


def concept_name(question):
    with TestingSessionLocal() as db: return db.get(Concept,question['concept_id']).name


def finish(client,progress):
    replies=[];ids=[]
    while progress['status']=='in_progress':
        ids.append(progress['next_question']['id'])
        payload=answer_for(progress['next_question']['id'],len(ids)%2==1)
        reply=client.post(f"{PREFIX}/{progress['session_id']}/answers",json=payload)
        assert reply.status_code==200,reply.text
        replies.append((payload,reply.json()))
        progress=client.get(f"{PREFIX}/{progress['session_id']}").json()
    return progress,replies,ids


def test_start_resume_reload_and_only_one_assignment(setup):
    initial=start(setup)
    assert initial['target_questions']==5 and initial['assigned_questions']==1 and initial['answered_questions']==0
    assert initial['current_question_eligible'] is True
    assert initial['next_position']==0 and initial['selection_reason']
    assert start(setup)==initial
    assert setup.get(f"{PREFIX}/{initial['session_id']}").json()==initial
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(AdaptiveAssignment)).all())==1
        assert db.scalars(select(Attempt)).all()==[]
    # Reloading the module cannot change the persisted sequence/reason.
    reloaded=importlib.reload(service)
    with TestingSessionLocal() as db:
        assert reloaded.progress(db,reloaded.owned(db,10,UUID(initial['session_id']))).model_dump(mode='json')==initial


def test_weaker_concept_and_deterministic_ties(setup):
    set_mastery({'Arrays':0.35,'Time Complexity':0.10,'Recursion':0.25})
    initial=start(setup)
    assert concept_name(initial['next_question'])=='Time Complexity'
    assert '10.0%' in initial['selection_reason']
    assert 'lowest estimate' in initial['selection_reason']
    restart=setup.post(PREFIX+'/restart',json={'request_id':str(uuid4())}).json()
    assert restart['next_question']['id']==initial['next_question']['id']


def test_mastery_recalculated_after_each_answer_selects_another_concept(setup):
    first=start(setup)
    assert concept_name(first['next_question'])=='Arrays'
    path=f"{PREFIX}/{first['session_id']}"
    result=setup.post(path+'/answers',json=answer_for(first['next_question']['id'])).json()
    assert result['feedback']['mastery_probability']==pytest.approx(update_mastery(INITIAL_MASTERY,True))
    current=setup.get(path).json()
    assert current['assigned_questions']==2
    assert concept_name(current['next_question'])=='Recursion'
    with TestingSessionLocal() as db:
        assignments=db.scalars(select(AdaptiveAssignment).order_by(AdaptiveAssignment.position)).all()
        assert len(assignments)==2 and assignments[1].attempt_id is None


def test_locked_weaker_concept_is_not_selected_and_unlock_uses_shared_threshold(setup):
    set_mastery({'Binary Search':0.01,'Merge Sort':0.01,'Bubble Sort':0.01,'Arrays':0.79,'Time Complexity':0.9,'Recursion':0.9})
    initial=start(setup)
    assert concept_name(initial['next_question'])=='Arrays'
    # Arrays becomes mastered: Bubble Sort now becomes eligible (Time already mastered).
    assert setup.post(f"{PREFIX}/{initial['session_id']}/answers",json=answer_for(initial['next_question']['id'])).status_code==200
    current=setup.get(f"{PREFIX}/{initial['session_id']}").json()
    assert concept_name(current['next_question'])=='Bubble Sort'


def test_recency_uses_all_attempts_of_requested_student_only(setup):
    set_mastery({'Arrays':0.1})
    with TestingSessionLocal.begin() as db:
        array=db.scalar(select(Concept).where(Concept.name=='Arrays'))
        questions=db.scalars(select(Question).where(Question.concept_id==array.id).order_by(Question.question_key)).all()
        now=datetime.now(timezone.utc)
        db.add_all([Attempt(student_id=10,question_id=questions[0].id,selected_answer=0,is_correct=False,attempted_at=now),
                    Attempt(student_id=20,question_id=questions[1].id,selected_answer=0,is_correct=False,attempted_at=now)])
        never_by_student=questions[1].id
        question_ids=[row.id for row in questions]
    first=start(setup)
    assert first['next_question']['id']==never_by_student
    assert 'never attempted' in first['selection_reason']
    with TestingSessionLocal.begin() as db:
        for index,question_id in enumerate(question_ids):
            db.add(Attempt(student_id=10,question_id=question_id,selected_answer=0,is_correct=False,attempted_at=now-timedelta(days=10-index)))
        # First question remains newest because MAX includes the original now timestamp.
    newer=setup.post(PREFIX+'/restart',json={'request_id':str(uuid4())}).json()
    assert newer['next_question']['id']==never_by_student
    assert 'least recently attempted' in newer['selection_reason']


def test_equal_mastery_prefers_unseen_question_over_lower_concept_id(setup):
    with TestingSessionLocal.begin() as db:
        array=db.scalar(select(Concept).where(Concept.name=='Arrays'))
        for question in db.scalars(select(Question).where(Question.concept_id==array.id)):
            db.add(Attempt(student_id=10,question_id=question.id,selected_answer=0,is_correct=False))
    first=start(setup)
    assert concept_name(first['next_question'])=='Recursion'


def test_five_questions_no_repeats_results_history_and_snapshot_stability(setup):
    completed,replies,ids=finish(setup,start(setup))
    assert len(ids)==len(set(ids))==5
    assert completed['completion_reason']=='target_reached'
    assert completed['next_question'] is None and completed['answered_questions']==5
    path=f"{PREFIX}/{completed['session_id']}"
    result=setup.get(path+'/results').json()
    assert result['answered_questions']==5 and result['correct_answers']==3 and result['accuracy']==0.6
    assert result['mastery_basis']=='last_adaptive_attempt'
    assert [row['question_id'] for row in result['questions']]==ids
    assert all(row['selection_reason'] for row in result['questions'])
    assert all(row['status']==get_mastery_status(row['estimated_mastery']) for row in result['concepts'])
    assert start(setup)['session_id']==completed['session_id']
    payload,replay=replies[-1]
    assert setup.post(path+'/answers',json=payload).json()==replay
    assert setup.post(path+'/answers',json={**payload,'submission_id':str(uuid4())}).status_code==409
    assert setup.post('/attempts',json={'student_id':10,**{key:payload[key] for key in ['question_id','selected_answer']}}).status_code==200
    assert setup.get(path+'/results').json()==result
    history=setup.get('/students/10/history?limit=2').json()
    assert all(row['origin']=='adaptive_practice' for row in history['attempts'])
    following=setup.get('/students/10/history',params={'cursor':history['next_cursor'],'limit':100}).json()['attempts']
    assert [row['origin'] for row in following]==['adaptive_practice']*3+['ordinary_practice']


def test_empty_pool_and_early_exhaustion_are_explicit(client):
    with TestingSessionLocal.begin() as db: db.add(Student(id=10,username='empty-pool'))
    empty=start(client)
    assert empty['status']=='completed' and empty['completion_reason']=='eligible_pool_exhausted'
    result=client.get(f"{PREFIX}/{empty['session_id']}/results").json()
    assert result['answered_questions']==0 and result['accuracy'] is None and result['concepts']==[]
    with TestingSessionLocal.begin() as db:
        concept=Concept(name='Standalone');db.add(concept);db.flush()
        db.add(Question(concept_id=concept.id,title='Only one',description='Pick one',difficulty='easy',options='["a","b"]',correct_answer=0))
    fresh=client.post(PREFIX+'/restart',json={'request_id':str(uuid4())}).json()
    completed,_,ids=finish(client,fresh)
    assert len(ids)==1 and completed['completion_reason']=='eligible_pool_exhausted'


def test_eligibility_loss_blocks_assigned_question_without_changing_progress(setup):
    set_mastery({'Arrays':0.8,'Linear Search':0.01,'Time Complexity':0.9,'Recursion':0.9})
    initial=start(setup)
    assert concept_name(initial['next_question'])=='Linear Search'
    set_mastery({'Arrays':0.79})
    path=f"{PREFIX}/{initial['session_id']}"
    current=setup.get(path).json()
    assert current['current_question_eligible'] is False and current['blocked_reason']
    assert setup.post(path+'/answers',json=answer_for(initial['next_question']['id'])).status_code==409
    with TestingSessionLocal() as db: assert db.scalars(select(Attempt)).all()==[]


def test_restarts_preserve_mastery_and_closed_session_replays(setup):
    initial=start(setup);path=f"{PREFIX}/{initial['session_id']}"
    payload=answer_for(initial['next_question']['id'])
    recorded=setup.post(path+'/answers',json=payload).json()
    key={'request_id':str(uuid4())}
    new=setup.post(PREFIX+'/restart',json=key).json()
    assert setup.post(PREFIX+'/restart',json=key).json()==new
    assert setup.get(path).json()['status']=='abandoned'
    assert setup.post(path+'/answers',json=payload).json()==recorded
    assert setup.post(path+'/answers',json={**payload,'submission_id':str(uuid4())}).status_code==409
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all())==1
        assert db.scalar(select(Mastery)).probability==recorded['feedback']['mastery_probability']


def test_isolation_invalid_answers_conflicts_and_no_answer_leakage(setup):
    initial=start(setup);path=f"{PREFIX}/{initial['session_id']}"
    assert set(initial['next_question'])=={'id','concept_id','title','description','difficulty','options'}
    for route in [path,path+'/results']:
        assert setup.get(route.replace('/students/10/','/students/20/')).status_code==404
    payload=answer_for(initial['next_question']['id'])
    assert setup.post(path.replace('/students/10/','/students/20/')+'/answers',json=payload).status_code==404
    assert setup.post('/students/999/adaptive-sessions/start').status_code==404
    assert setup.get(path+'/results').status_code==409
    assert setup.post(path+'/answers',json={**payload,'question_id':2147483647}).status_code==409
    assert setup.post(path+'/answers',json={**payload,'selected_answer':999}).status_code==422
    assert setup.post(path+'/answers',json={**payload,'selected_answer':True}).status_code==422
    assert setup.post(PREFIX+'/restart',json={}).status_code==422
    recorded=setup.post(path+'/answers',json=payload).json()
    assert recorded['feedback']['explanation']
    assert setup.post(path+'/answers',json={**payload,'selected_answer':(payload['selected_answer']+1)%4}).status_code==409
    assert setup.post(path+'/answers',json={**payload,'submission_id':str(uuid4())}).status_code==409


def test_collision_with_ordinary_submission_is_not_reused(setup):
    initial=start(setup);payload=answer_for(initial['next_question']['id'])
    internal=uuid5(UUID(initial['session_id']),payload['submission_id'])
    assert setup.post('/attempts',json={'student_id':10,**payload,'submission_id':str(internal)}).status_code==200
    assert setup.post(f"{PREFIX}/{initial['session_id']}/answers",json=payload).status_code==409
    with TestingSessionLocal() as db: assert db.scalar(select(AdaptiveAssignment)).attempt_id is None


def test_failure_selecting_next_rolls_back_bkt_attempt_and_assignment(setup,monkeypatch):
    initial=start(setup)
    def fail(*args): raise RuntimeError('Injected next-selection failure')
    monkeypatch.setattr(service,'assign_next',fail)
    with pytest.raises(RuntimeError,match='Injected'):
        setup.post(f"{PREFIX}/{initial['session_id']}/answers",json=answer_for(initial['next_question']['id']))
    with TestingSessionLocal() as db:
        assert db.scalars(select(Attempt)).all()==[]
        assert db.scalars(select(Mastery)).all()==[]
        assert db.scalar(select(AdaptiveAssignment)).attempt_id is None


def test_concurrent_starts_and_identical_answers_update_bkt_exactly_once(setup):
    starts=parallel([lambda db:service.start(db,10)]*2)
    assert starts[0].session_id==starts[1].session_id
    session_id=starts[0].session_id
    answer=AdaptiveAnswer(**answer_for(starts[0].next_question.id))
    replies=parallel([lambda db:service.submit(db,10,session_id,answer)]*2)
    assert replies[0]==replies[1]
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(Attempt)).all())==1
        assert db.scalar(select(Mastery)).probability==pytest.approx(update_mastery(INITIAL_MASTERY,True))
        assert len(db.scalars(select(AdaptiveAssignment)).all())==2


def test_concurrent_distinct_answers_and_restarts_are_serialized(setup):
    initial=start(setup);session_id=UUID(initial['session_id'])
    a=AdaptiveAnswer(**answer_for(initial['next_question']['id']))
    b=AdaptiveAnswer(**answer_for(initial['next_question']['id']))
    replies=parallel([lambda db:service.submit(db,10,session_id,a),lambda db:service.submit(db,10,session_id,b)])
    assert sum(reply==409 for reply in replies)==1
    current=setup.get(f'{PREFIX}/{session_id}').json()
    c=AdaptiveAnswer(**answer_for(current['next_question']['id']))
    replies=parallel([lambda db:service.start(db,10,uuid4()),lambda db:service.submit(db,10,session_id,c)])
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(AdaptiveSession).where(AdaptiveSession.status=='in_progress')).all())==1
        assert db.get(AdaptiveSession,session_id).status=='abandoned'
        assert len(db.scalars(select(Attempt)).all())==(1 if replies[1]==409 else 2)


def test_concurrent_restart_retries_create_only_one_new_session(setup):
    start(setup);key=uuid4()
    replies=parallel([lambda db:service.start(db,10,key)]*2)
    assert replies[0].session_id==replies[1].session_id
    with TestingSessionLocal() as db: assert len(db.scalars(select(AdaptiveSession)).all())==2


def test_diagnostic_coexistence_and_recommendations_preserved_by_session_reads(setup):
    before=setup.get('/recommendations/10').json()
    diagnostic=setup.post('/students/10/diagnostics/start').json()
    adaptive=start(setup)
    assert setup.get('/recommendations/10').json()==before
    payload=answer_for(adaptive['next_question']['id'])
    assert setup.post(f"{PREFIX}/{adaptive['session_id']}/answers",json=payload).status_code==200
    diagnostic_path=f"/students/10/diagnostics/{diagnostic['session_id']}"
    assert setup.post(diagnostic_path+'/answers',json=answer_for(diagnostic['next_question']['id'])).status_code==200
    assert setup.get(diagnostic_path).json()['answered_questions']==1
    assert [row['origin'] for row in setup.get('/students/10/history').json()['attempts']]==['adaptive_practice','diagnostic']


def test_sql_candidate_query_is_bounded_and_filters_used_questions(setup):
    statements=[]
    def track(conn,cursor,statement,parameters,context,executemany): statements.append(statement)
    event.listen(test_engine,'before_cursor_execute',track)
    try: start(setup)
    finally: event.remove(test_engine,'before_cursor_execute',track)
    candidate=next(statement for statement in statements if 'last_attempt' in statement and 'LIMIT' in statement)
    assert 'NOT IN' in candidate and 'adaptive_assignments' in candidate
    assert 'attempts.student_id' in candidate and 'max(attempts.attempted_at)' in candidate
    assert 'NULLS FIRST' in candidate and 'ORDER BY' in candidate
